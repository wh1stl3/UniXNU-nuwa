#!/usr/bin/env python3
"""Build a guarded PMGR discovery instrument for the pinned nuwa iOS16 carrier.

This publishes no real power controls. Unsupported calls stop at a panic. The
input reference is the independently verified pthread+renderer baseline kernel.
The provider ABI is verified against that carrier before any object is emitted.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, '/root/nuwa-pmap-ret-native-20261111/nuwa/ios-16.7.16-20H392/nuwa_pmap_ret/tree/kits/NativePrelink')
from native_prelink import macho, backed_offset, exports  # noqa: E402

CARRIER = Path('/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/pthread-renderer-20261112-r1/renderer-baseline.macho')
CARRIER_SHA = 'e0c235f1de499c858d6eb672f989de7692f1d97140e1064da59391642fa11f5d'
SOURCE = ROOT / 'package/NuwaPlatformPower.cpp'
COMPILE_RECORD = Path('/root/nuwa-pmap-ret-native-20261111/nuwa/ios-16.7.16-20H392/nuwa_pmap_ret/tree/build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/iokit/DEVELOPMENT/IOPMGR.cpo.json')
INIT_NAME = '__GLOBAL__sub_I_NuwaPlatformPower.cpp'


def run(command, **kwargs):
    return subprocess.check_output([str(v) for v in command], timeout=120, **kwargs)


def require(value, message):
    if not value:
        raise SystemExit(message)


def text_section(blob):
    section = next(s for seg in macho(blob)['segments'] for s in seg['sections'] if s['name'] == '__text')
    return blob[section['fileoff']:section['fileoff'] + section['size']]


def symtab_meta(blob):
    """Return (symoff, nsyms, stroff, strsize, dysymtab_cmd_offset)."""
    info = macho(blob)
    tables = [(offset, length) for cmd, offset, length in info['commands'] if cmd == 2]
    dysyms = [(offset, length) for cmd, offset, length in info['commands'] if cmd == 0x0b]
    if len(tables) != 1 or len(dysyms) != 1:
        raise SystemExit('Expected one symtab and one dysymtab')
    return struct.unpack_from('<4I', blob, tables[0][0] + 8) + (dysyms[0][0],)


def symbol_at(blob, symoff, strings, index):
    at = symoff + index * 16
    ix, kind = struct.unpack_from('<IB', blob, at)
    end = strings.find(b'\0', ix)
    name = strings[ix:end].decode() if 0 <= ix < len(strings) and end >= 0 else '?'
    return name, kind


def dysymtab(blob, offset):
    v = struct.unpack_from('<18I', blob, offset + 8)
    return dict(zip(('ilocalsym', 'nlocalsym', 'iextdefsym', 'nextdefsym', 'iundefsym', 'nundefsym'), v))


def late_transform(src, dst, init_name):
    """Globalize one local symbol and disable __mod_init_func, preserving
    Mach-O symbol-table partition invariants.

    The system llvm-objcopy (LLVM 14) cannot --globalize-symbol for Mach-O. A
    bare N_EXT flip leaves an external symbol inside the local partition, which
    violates LC_DYSYMTAB. The symbol is instead swapped with the last local
    symbol so it lands at the start of the external-defined partition, every
    relocation referencing either index is remapped, and the partition bounds
    are updated. __mod_init_func is then emptied so the loader never auto-runs
    the initializer.
    """
    blob = bytearray(src.read_bytes())
    symoff, nsyms, stroff, strsize, dysym_off = symtab_meta(bytes(blob))
    strings = bytes(blob[stroff:stroff + strsize])
    d = dysymtab(blob, dysym_off)
    ilocalsym, nlocalsym, iextdefsym, nextdefsym = d['ilocalsym'], d['nlocalsym'], d['iextdefsym'], d['nextdefsym']

    init_index = None
    for i in range(nsyms):
        name, kind = symbol_at(blob, symoff, strings, i)
        if name == init_name:
            init_index = i
            break
    if init_index is None:
        raise SystemExit(f'Static initializer {init_name} missing from object')
    init_kind = struct.unpack_from('<B', blob, symoff + init_index * 16 + 4)[0]
    if init_kind & 0x01:
        raise SystemExit('Initializer already external')
    if not (ilocalsym <= init_index < ilocalsym + nlocalsym):
        raise SystemExit('Initializer not inside the local partition')

    last_local = iextdefsym - 1
    # Move the initializer to the last local slot, which becomes the first
    # external-defined slot after the bounds are tightened.
    if init_index != last_local:
        a = symoff + init_index * 16
        b = symoff + last_local * 16
        blob[a:a + 16], blob[b:b + 16] = blob[b:b + 16], blob[a:a + 16]

    # Remap every relocation that referenced either swapped index.
    remap = {}
    if init_index != last_local:
        remap = {init_index: last_local, last_local: init_index}
    info = macho(bytes(blob))
    for seg in info['segments']:
        for section in seg['sections']:
            reloff, nreloc = struct.unpack_from('<2I', blob, section['command_offset'] + 56)
            for j in range(nreloc):
                at = reloff + j * 8
                rword = struct.unpack_from('<I', blob, at + 4)[0]
                symnum = rword & 0xffffff
                if (rword >> 27) & 1 and symnum in remap:  # r_extern set
                    struct.pack_into('<I', blob, at + 4, (rword & ~0xffffff) | remap[symnum])

    # Set N_EXT on the initializer (now at last_local).
    struct.pack_into('<B', blob, symoff + last_local * 16 + 4,
                     struct.unpack_from('<B', blob, symoff + last_local * 16 + 4)[0] | 0x01)

    # Tighten the local partition by one and grow the external-defined partition
    # by one, moving only the single globalized symbol across the boundary.
    struct.pack_into('<I', blob, dysym_off + 8 + 4, nlocalsym - 1)   # nlocalsym
    struct.pack_into('<I', blob, dysym_off + 8 + 8, iextdefsym - 1)  # iextdefsym
    struct.pack_into('<I', blob, dysym_off + 8 + 12, nextdefsym + 1)  # nextdefsym

    # Empty __mod_init_func so the loader never auto-runs the initializer.
    target = next(s for seg in info['segments'] for s in seg['sections'] if s['name'] == '__mod_init_func')
    for field_offset, value in ((40, 0), (48, 0), (56, 0), (60, 0)):  # size, offset, reloff, nreloc
        struct.pack_into('<Q' if field_offset == 40 else '<I', blob, target['command_offset'] + field_offset, value)
    dst.write_bytes(bytes(blob))


def verify_late(blob):
    """Check symbol/partition consistency, no auto-init, initializer resolvable."""
    symoff, nsyms, stroff, strsize, dysym_off = symtab_meta(blob)
    strings = bytes(blob[stroff:stroff + strsize])
    d = dysymtab(blob, dysym_off)
    ilocalsym, nlocalsym, iextdefsym, nextdefsym, iundefsym, nundefsym = \
        d['ilocalsym'], d['nlocalsym'], d['iextdefsym'], d['nextdefsym'], d['iundefsym'], d['nundefsym']
    for i in range(nsyms):
        kind = struct.unpack_from('<B', blob, symoff + i * 16 + 4)[0]
        ext = bool(kind & 0x01)
        if ilocalsym <= i < ilocalsym + nlocalsym:
            require(not ext, f'symbol {i} is external inside the local partition')
        elif iextdefsym <= i < iextdefsym + nextdefsym:
            require(ext and (kind & 0x0e) == 0x0e, f'symbol {i} is not an external defined symbol in extdef partition')
        elif iundefsym <= i < iundefsym + nundefsym:
            require(ext and (kind & 0x0e) == 0x00, f'symbol {i} is not an external undefined symbol in undef partition')
    init_kind = None
    init_in_ext = False
    for i in range(nsyms):
        name, kind = symbol_at(blob, symoff, strings, i)
        if name == INIT_NAME:
            init_kind = kind
            init_in_ext = iextdefsym <= i < iextdefsym + nextdefsym
    require(init_kind is not None and init_kind & 0x01 and init_in_ext,
            'Initializer is not an external defined symbol after transform')
    mod_init = next(s for seg in macho(blob)['segments'] for s in seg['sections'] if s['name'] == '__mod_init_func')
    _, nreloc = struct.unpack_from('<2I', blob, mod_init['command_offset'] + 56)
    require(nreloc == 0, '__mod_init_func still has relocations after transform')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, default=ROOT / 'out/nuwa-platform-power-20261113-r2')
    a = p.parse_args()
    out = a.out.resolve()
    if not out.is_relative_to(ROOT / 'out') or out.exists():
        raise ValueError('--out must be a fresh directory under device out/')
    out.mkdir(parents=True)

    candidate = CARRIER.read_bytes()
    require(hashlib.sha256(candidate).hexdigest() == CARRIER_SHA, 'PMGR carrier differs from the pinned renderer baseline')
    meta = macho(candidate)
    native_names = {n: va for va, names in exports(candidate, meta).items() for n in names}

    def ptr(va):
        return struct.unpack_from('<Q', candidate, backed_offset(meta['segments'], va, 8, len(candidate)))[0]

    # Verified against the actual carrier: the iOS16 ApplePMGR provider has
    # 0x36968 storage, 325 vtable slots, readAon/writeAon at 312/313, and AMFI
    # imports the original nub read/write through fixed addresses.
    provider_vtable = 0xfffffff005c9faf8
    require(ptr(provider_vtable + 312 * 8) == 0xfffffff004681e04 and
            ptr(provider_vtable + 313 * 8) == 0xfffffff004681e0c and
            ptr(provider_vtable + 325 * 8) == 0,
            'iOS16 ApplePMGR provider layout differs')
    require(ptr(0xfffffff005cb56b8) == 0xfffffff004685734 and
            ptr(0xfffffff005cb56c0) == 0xfffffff004683dbc,
            'AMFI ApplePMGRNub imported methods differ')

    header = '''// Generated exact storage/slot ABI; private fields stay opaque.
#pragma once
#include <IOKit/IOPMGR.h>
class ApplePMGR : public IOPMGR {
 OSDeclareAbstractStructors(ApplePMGR)
 unsigned char originalPrivate[0x36968-sizeof(IOPMGR)];
public:
'''
    guards = ''
    for i in range(177, 325):
        if i == 312:
            header += ' virtual uint32_t readAon();\n'
        elif i == 313:
            header += ' virtual void writeAon(uint64_t);\n'
        else:
            header += f' virtual void opaque{i}() = 0;\n'
            guards += f' void opaque{i}() override {{ unavailable({i}); }}\n'
    header += '};\nstatic_assert(sizeof(ApplePMGR)==0x36968,"Original provider storage");\n'
    (out / 'OriginalPMGRABI.h').write_text(header)
    (out / 'GuardedPMGRSlots.inc').write_text(guards)

    obj = out / 'NuwaPlatformPower.o'
    record = json.loads(COMPILE_RECORD.read_text().strip().rstrip(','))
    command, i = [], 0
    arguments = record['arguments']
    while i < len(arguments):
        arg = arguments[i]
        if arg == record['file']:
            command.append(str(SOURCE))
        elif arg == '-o':
            command += ['-o', str(obj)]
            i += 1
        elif arg == '-Xclang' and arguments[i + 1].startswith('-W'):
            i += 1
        elif not arg.startswith('-W'):
            command.append(arg)
        i += 1
    command += ['-Wall', '-Wextra', '-Werror', '-Wno-unused-parameter', '-Wno-c99-designator',
                '-Wno-reorder-init-list', '-Wno-deprecated-enum-enum-conversion',
                '-Wno-unknown-warning-option', '-Wno-unnecessary-virtual-specifier',
                '-Wno-missing-designated-field-initializers', '-I', str(out), '-I',
                '/root/nuwa-pmap-ret-native-20261111/nuwa/ios-16.7.16-20H392/nuwa_pmap_ret/tree/.cache/xnu-work/osfmk']
    run(command, cwd=record['directory'])
    raw = obj.read_bytes()
    info = macho(raw)
    require(info['kind'] == 1, 'Require actual ARM64 subtype-0 Mach-O object')
    build_version = [struct.unpack_from('<2I', raw, at + 8) for cmd, at, _ in info['commands'] if cmd == 0x32]
    require(build_version == [(2, 0x110000)], 'Object build version differs from carrier')
    sym_at = next(at for cmd, at, _ in info['commands'] if cmd == 2)
    at, count, strings, _ = struct.unpack_from('<4I', raw, sym_at + 8)
    symbols = []
    for i in range(count):
        ix, kind, _, _, address = struct.unpack_from('<IBBHQ', raw, at + i * 16)
        symbols.append((raw[strings + ix:raw.index(b'\0', strings + ix)].decode(), address, kind))
    vtable = next(va for name, va, _ in symbols if name == '__ZTV17NuwaPlatformPower')
    relocations = {}
    for segment in info['segments']:
        for section in segment['sections']:
            if section['va'] <= vtable < section['va'] + section['size']:
                at, count = struct.unpack_from('<2I', raw, section['command_offset'] + 56)
                for i in range(count):
                    offset, bits = struct.unpack_from('<2I', raw, at + i * 8)
                    if bits >> 27 & 1 and bits >> 28 == 0 and bits >> 25 & 3 == 3:
                        relocations[section['va'] + offset] = symbols[bits & 0xffffff][0]
    entries = [relocations.get(vtable + 16 + i * 8) for i in range(325)]
    require(len(entries) == 325 and all(entries) and
            vtable + 16 + 325 * 8 not in relocations, 'Exact 325-entry provider table')

    bindings = {'__ZN9ApplePMGRC2EPK11OSMetaClass': 0xfffffff00465703c,
                '__ZN9ApplePMGRD2Ev': 0xfffffff004657164,
                '__ZN9ApplePMGR10gMetaClassE': 0xfffffff006a0b410}
    native_inherited = {
        44: (0xfffffff00465aec0, '__ZN15IORegistryEntry13setPropertiesEP8OSObject'),
        81: (0xfffffff00465b7a4, '__ZN9IOService15configureReportEP19IOReportChannelListjPvS2_'),
        82: (0xfffffff00465b7ac, '__ZN9IOService12updateReportEP19IOReportChannelListjPvS2_'),
        86: (0xfffffff0046571e0, '__ZN9IOService5startEPS_'),
        87: (0xfffffff00465961c, '__ZN9IOService4stopEPS_'),
        117: (0xfffffff00465962c, '__ZN9IOService20callPlatformFunctionEPK8OSSymbolbPvS3_S3_S3_'),
        159: (0xfffffff004681974, '__ZN9IOService22powerStateWillChangeToEmmPS_'),
        160: (0xfffffff004681850, '__ZN9IOService21powerStateDidChangeToEmmPS_'),
    }
    for slot, name in enumerate(entries):
        if slot in (0, 1, 7) or 168 <= slot < 325 and slot not in (312, 313):
            require('17NuwaPlatformPower' in name, f'Own guard/lifecycle required at slot {slot}')
        elif slot in (312, 313):
            require('9ApplePMGR' in name, 'Only actual original AON implementations inherited')
            bindings[name] = ptr(provider_vtable + slot * 8)
        elif slot in native_inherited:
            original, native = native_inherited[slot]
            require(ptr(provider_vtable + slot * 8) == original and name == native and
                    native_names.get(name) == ptr(native_names['__ZTV6IOPMGR'] + 16 + slot * 8),
                    f'Audited native inheritance changed at slot {slot}')
        else:
            require(native_names.get(name) == ptr(native_names['__ZTV6IOPMGR'] + 16 + slot * 8),
                    f'Native IOPMGR/IOService entry differs at {slot}')
    undefined = {n for n, _, k in symbols if k == 1 and 'ApplePMGR' in n}
    require(undefined == set(bindings), 'All and only audited original base imports')
    bindings.update({'_nuwa_original_pmgr_nub_create': 0xfffffff0046832d4,
                     '_nuwa_original_pmgr_nub_read': 0xfffffff004685734,
                     '_nuwa_original_pmgr_nub_write': 0xfffffff004683dbc})
    asm = out / 'original-bindings.S'
    asm.write_text(''.join(f'.globl {name}\n.set {name}, {va:#x}\n' for name, va in bindings.items()))
    run(['/opt/unixnu-linux/llvm/bin/clang-24', '--target=arm64-apple-ios17.0', '-c', str(asm), '-o', str(out / 'original-bindings.o')])

    late = out / 'NuwaPlatformPower.late.o'
    late_transform(obj, late, INIT_NAME)
    require(text_section(raw) == text_section(late.read_bytes()), 'Late registration cannot change instructions')
    verify_late(late.read_bytes())
    archive = out / 'libNuwaPlatformPower.a'
    run(['/usr/bin/llvm-ar', 'rcs', str(archive), str(late), str(out / 'original-bindings.o')])
    report = {'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
              'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
              'carrier_sha256': CARRIER_SHA,
              'bindings': {name: hex(va) for name, va in bindings.items()}, 'virtual_entries': 325,
              'provider_vtable': hex(provider_vtable), 'class_size': 0x36968,
              'late_symbol': INIT_NAME, 'late_symbol_external': True, 'mod_init_disabled': True,
              'mode': 'nuwa opt-in lifecycle/publication/refusal instrument; not a functional power backend',
              'native_inherited_deviations': sorted(native_inherited),
              'runtime_qualified': False, 'original_executable_modified': False,
              'scope': 'Static original ABI + compiled guarded provider; IOKit lifecycle is modeled, not executed. '
                       'No power hardware support. Default off (nuwa-pmgr boot-arg).'}
    (out / 'build-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print('PASS: ordinary ARM64 build; exact native and original bindings; unimplemented power slots stop')
    print(json.dumps({'archive': str(archive), 'entries': 325, 'bindings': len(bindings)}, indent=2))


if __name__ == '__main__':
    main()
