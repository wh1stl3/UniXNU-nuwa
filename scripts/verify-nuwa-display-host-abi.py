#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Patent
"""Build and audit an incomplete, host-only 20H392 CPU display archive."""

import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DRIVER_REV = 'e47c1b8de169cd2bd0b885c7d85e433010e3cdf2'
BASE_REV = '693f5d9cae8a408dd18b39f3f9fdc4228c934241'
INIT = '__GLOBAL__sub_I_NativeLegacyDisplay.cpp'
DEFERRED = {'_native_legacy_set_refresh_properties', '_native_legacy_vsync_notify'}
# The pinned 8796 reference import list includes owner and weak-ref bits;
# different toolchains may need a deliberate requalification, not a whitelist
# that silently swallows new unresolved symbols.
UNRESOLVED_SHA256 = 'ec82b3611863f1cbca42d8525655c098fae248cc4a18ce020c4faa7d885f604d'
SLOTS = {
    184: '__ZN19NativeLegacyDisplay13isMainDisplayEv',
    188: '__ZN19NativeLegacyDisplay11getDotPitchEPj',
    212: '__ZN19NativeLegacyDisplay18supportedFrameInfoEjPjPc',
    321: '__ZN19NativeLegacyDisplay24collectCompletionReportsEjPvPjj',
    329: '__ZN19NativeLegacyDisplay9opaque329Ev',
    330: '__ZN25IOMobileFramebufferLegacy9opaque330Ev',
}
BASE_METHOD = '''    IOReturn supportedFrameInfo(uint32_t,uint32_t *count,char *key,uint32_t *mask) override {
        if(!count || !key || !mask)return kIOReturnBadArgument;
        *count=0;*mask=0;bzero(key,64);return kIOReturnUnsupported;
    }'''
NUWA_METHOD = '''    IOReturn supportedFrameInfo(uint32_t,uint32_t *count,char *key) override {
        if(!count || !key)return kIOReturnBadArgument;
        *count=0;bzero(key,64);return kIOReturnUnsupported;
    }'''


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n')


def compile_args(record, source, obj, driver):
    # Replay the previous real 8796 IOPMGR command, substituting inputs and
    # dropping that XNU TU's warning policy (including -Xclang -W pairs).
    original = record['arguments']
    if original.count('-c') != 1 or original.count('-o') != 1 or original.count(record['file']) != 1:
        raise SystemExit('expected a single XNU compile-only input/output')
    args = iter(original)
    command = []
    for arg in args:
        if arg == record['file']:
            command.append(str(source))
        elif arg in ('-MF', '-MJ', '-MT', '-MQ'):
            next(args)
        elif arg in ('-MD', '-MMD', '-MP'):
            continue
        elif arg == '-o':
            next(args)
            command.extend(['-o', str(obj)])
        elif arg == '-Xclang':
            value = next(args)
            if not value.startswith('-W'):
                command.extend([arg, value])
        elif not arg.startswith('-W'):
            command.append(arg)
    osfmk = Path(record['file']).parents[2] / 'osfmk'
    return command + ['-iquote', str(driver), '-I' + str(ROOT / 'package'),
                      '-I' + str(osfmk), '-DNATIVE_LEGACY_CANCEL_SWAPS=0',
                      '-ferror-limit=1']


def object_layout(base, blob):
    location = str(base / 'kits/XnuPrelink')
    if location not in sys.path:
        sys.path.insert(0, location)
    sys.dont_write_bytecode = True
    from native_prelink import macho

    if struct.unpack_from('<III', blob) != (0xfeedfacf, 0x0100000c, 0):
        raise SystemExit('expected an arm64 Mach-O object')
    if struct.unpack_from('<I', blob, 12)[0] != 1:  # MH_OBJECT
        raise SystemExit('expected MH_OBJECT')
    image = macho(blob)
    sym, = (at for cmd, at, _ in image['commands'] if cmd == 2)  # LC_SYMTAB
    symoff, nsyms, stroff, strsize = struct.unpack_from('<4I', blob, sym + 8)
    strings = blob[stroff:stroff + strsize]
    symbols = []
    for i in range(nsyms):
        ix, kind, section, desc, value = struct.unpack_from('<IBBHQ', blob, symoff + i * 16)
        symbols.append((strings[ix:strings.index(b'\0', ix)].decode(), kind, section, desc, value))
    sections = [s for segment in image['segments'] for s in segment['sections']]
    return sections, symbols


def inspect_object(base, blob):
    sections, symbols = object_layout(base, blob)
    table_name = '__ZTV19NativeLegacyDisplay'
    (_, kind, ordinal, _, value), = (sym for sym in symbols if sym[0] == table_name)
    if kind & 0x0e != 0x0e or not ordinal:  # N_SECT
        raise SystemExit(f'{table_name} is not defined in a section')
    section = sections[ordinal - 1]
    table = value - section['va']
    if not 0 <= table <= section['size'] - (2 + max(SLOTS)) * 8 - 8:
        raise SystemExit(f'{table_name} has no space for the audited slots')
    reloff, nreloc = struct.unpack_from('<II', blob, section['command_offset'] + 56)
    relocs = list(struct.iter_unpack('<II', blob[reloff:reloff + nreloc * 8]))
    results = {}
    for slot, expected in SLOTS.items():
        offset = table + 16 + slot * 8  # Skip offset-to-top and RTTI.
        words = [word for address, word in relocs if address == offset]
        # External, unsigned, non-PC-relative, 8-byte relocation with no addend.
        if len(words) != 1 or words[0] >> 24 != 0x0e or struct.unpack_from(
                '<Q', blob, section['fileoff'] + offset)[0] != 0:
            raise SystemExit(f'{table_name}[{slot}]: expected one plain pointer relocation')
        target = symbols[words[0] & 0xffffff][0]
        if target != expected:
            raise SystemExit(f'{table_name}[{slot}]: got {target}, expected {expected}')
        results[slot] = {'section_offset': hex(offset), 'symbol': target}
    return {'vtable': table_name, 'section': section['name'], 'slots': results}


def constructor_sections(blob, sections):
    return [s for s in sections if struct.unpack_from(
        '<I', blob, s['command_offset'] + 64)[0] & 0xff in (0x9, 0xA, 0x16)]


def inspect_initializers(base, raw, late):
    sections, symbols = object_layout(base, raw)
    auto = constructor_sections(raw, sections)
    if len(auto) != 1 or (auto[0]['name'], auto[0]['size']) != ('__mod_init_func', 8):
        raise SystemExit('expected exactly one original NativeLegacyDisplay initializer pointer')
    rel, count = struct.unpack_from('<II', raw, auto[0]['command_offset'] + 56)
    if count != 1:
        raise SystemExit('expected one relocation for the original initializer pointer')
    offset, word = struct.unpack_from('<II', raw, rel)
    if (offset, word >> 24, symbols[word & 0xffffff][0]) != (0, 0x0e, INIT) or \
            struct.unpack_from('<Q', raw, auto[0]['fileoff'])[0] != 0:
        raise SystemExit('initializer pointer does not reference the explicit board entry')
    sections, symbols = object_layout(base, late)
    if constructor_sections(late, sections):
        raise SystemExit('automatic initializer/terminator survived in the host archive member')
    if sum(n == INIT and k == 0x0f and s > 0 for n, k, s, _, _ in symbols) != 1:
        raise SystemExit('expected one external manual initializer in the host archive member')


def inspect_metaclass_import(blob, sections, symbols, name):
    got_page, got_pageoff = 0x5d, 0x6c  # ARM64_RELOC_GOT_LOAD_* plus width/extern/pcrel
    index, = (i for i, sym in enumerate(symbols) if sym[0] == name)
    if symbols[index][1:3] != (1, 0) or symbols[index][4] != 0:
        raise SystemExit(f'{name}: expected an undefined object import in the driver')
    pairs = []
    pointers = []
    for sec in sections:
        start, count = struct.unpack_from('<II', blob, sec['command_offset'] + 56)
        relocs = [(off, word >> 24) for off, word in
                  struct.iter_unpack('<II', blob[start:start + count * 8])
                  if word & (1 << 27) and word & 0xffffff == index]
        for off, kind in relocs:
            at = sec['fileoff'] + off
            if sec['name'] == '__text' and kind == got_page and (off + 4, got_pageoff) in relocs:
                if struct.unpack_from('<II', blob, at) != (0x90000002, 0xf9400042):
                    raise SystemExit(f'{name}: expected ADRP/LDR into x2')
                pairs.append(hex(sec['va'] + off))
            elif sec['name'] == '__text' and kind == got_pageoff and (off - 4, got_page) in relocs:
                continue
            elif sec['name'] == '__const' and kind == 0x0e and not struct.unpack_from('<Q', blob, at)[0]:
                pointers.append(hex(sec['va'] + off))
            else:
                raise SystemExit(f'{name}: unexpected relocation {sec["name"]}+{off:#x} ({kind:#x})')
    if len(pairs) != 3 or len(pointers) != 1:
        raise SystemExit(f'{name}: expected three GOT load pairs and one plain pointer')
    return {'got_pages': pairs, 'plain_pointers': pointers}


def inspect_archive(base, archive, members):
    names = subprocess.check_output(['llvm-ar', 't', archive], text=True).splitlines()
    if names != [obj.name for obj in members]:
        raise SystemExit('unexpected archive member list')
    definitions, undefined = {}, {}
    paths = {}
    abi = json.loads((ROOT / 'package/nuwa-display-abi.json').read_text())
    meta = abi['metaclass']
    for obj in members:
        blob = subprocess.check_output(['llvm-ar', 'p', archive, obj.name])
        original = obj.read_bytes()
        # Darwin archives include up to seven newline alignment bytes in
        # the extracted member. No other change to the object is permitted.
        if blob != original + b'\n' * (-len(original) % 8):
            raise SystemExit(f'{obj.name}: archive member does not match inspected object')
        sections, symbols = object_layout(base, blob)
        if constructor_sections(blob, sections):
            raise SystemExit(f'{obj.name}: archive contains automatic initialization/termination')
        if obj == members[0]:
            meta_relocs = inspect_metaclass_import(blob, sections, symbols, meta['symbol'])
        if obj == members[2]:
            binding, = (sym for sym in symbols if sym[0] == meta['symbol'])
            if binding[1:] != (0x03, 0, 0x20, int(meta['linked_address'], 16)):
                raise SystemExit(f'{obj.name}: expected absolute slid gMetaClass, not a definition of storage')
            for getter, info in abi['surfaces'].items():
                name = '_native_legacy_surface_' + getter
                (_, kind, section, _, value), = (sym for sym in symbols if sym[0] == name)
                sec = sections[section - 1]
                at = sec['fileoff'] + value - sec['va']
                bits = info['load_bits']
                load = (0xf9400000 if bits == 64 else 0xb9400000) | (
                    info['offset'] // (bits // 8) << 10)
                if kind != 0x0f or sec['name'] != '__text' or struct.unpack_from(
                        '<II', blob, at) != (load, 0xd65f03c0):
                    raise SystemExit(f'{name}: assembly does not match qualified getter')
        for name, kind, _, desc, value in symbols:
            if kind & 0xe0 or not kind & 1:
                continue
            if kind & 0x0e or value:  # includes tentative common symbols
                definitions.setdefault(name, []).append((obj.name, bool(desc & 0x80)))
            else:
                undefined.setdefault(name, []).append((obj.name, bool(desc & 0x40)))
        paths[obj.name] = sha256(obj)
    for name, owners in definitions.items():
        if sum(not weak for _, weak in owners) > 1:
            raise SystemExit(f'{name}: duplicate strong archive definitions: {owners}')
    if definitions.get(INIT) != [(members[0].name, False)] or undefined.get(INIT) != [
            (members[1].name, False)]:
        raise SystemExit('manual initializer must be defined by the driver and imported by the board TU')
    if definitions.get(meta['symbol']) != [(members[2].name, False)] or undefined.get(meta['symbol']) != [
            (members[0].name, False)]:
        raise SystemExit('original gMetaClass must be a strong binding only for the driver import')
    unresolved = {name: imports for name, imports in sorted(undefined.items()) if name not in definitions}
    missing_glue = {name for name in unresolved if name.startswith(
        ('_native_legacy_surface_', '_native_legacy_set_refresh_', '_native_legacy_vsync_'))}
    if missing_glue != DEFERRED:
        raise SystemExit(f'unexpected unresolved glue: {sorted(missing_glue)}')
    glued = ['descriptor', 'width', 'height', 'stride', 'allocation', 'format', 'planes']
    for getter in glued:
        name = '_native_legacy_surface_' + getter
        if definitions.get(name) != [(members[2].name, False)] or undefined.get(name) != [
                (members[0].name, False)]:
            raise SystemExit(f'{name}: expected one assembly definition and one driver import')
    fingerprint = hashlib.sha256(json.dumps(
        unresolved, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return {'members': paths, 'unresolved': unresolved, 'unresolved_sha256': fingerprint,
            'metaclass_relocations': meta_relocs,
            'automatic_initializers': 0,
            'manual_initializer': INIT, 'runtime_eligible': False, 'sha256': sha256(archive)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', required=True, type=Path)
    parser.add_argument('--cpo', required=True, type=Path, help='real 8796 IOPMGR.cpo.json')
    parser.add_argument('--out', required=True, type=Path, help='new directory below device out/')
    args = parser.parse_args()
    base, cpo, out = (p.resolve() for p in (args.base, args.cpo, args.out))
    if ROOT / 'out' not in out.parents:
        parser.error('--out must be below the device out/ directory')
    driver = base / 'drivers/GopFramebuffer'
    original = driver / 'NativeLegacyDisplay.cpp'
    # WSL reads the Windows checkout, whose tracked text may have CRLF.
    git = ['git', '--no-optional-locks', '-c', 'core.autocrlf=true', '-C', str(driver)]
    if subprocess.check_output(git[:-1] + [str(base), 'rev-parse', 'HEAD'],
                               text=True).strip() != BASE_REV:
        raise SystemExit(f'expected UniXNU at {BASE_REV}')
    if subprocess.check_output(git + ['rev-parse', 'HEAD'], text=True).strip() != DRIVER_REV:
        raise SystemExit(f'expected GopFramebuffer at {DRIVER_REV}')
    if subprocess.check_output(git + ['status', '--porcelain', '--', '.']):
        raise SystemExit('GopFramebuffer inputs are dirty')
    text = original.read_text()
    if text.count(BASE_METHOD) != 1:
        raise SystemExit(f'{original}: expected exactly one qualified frame-info body')
    record = json.loads(cpo.read_text().strip().rstrip(','))
    if Path(record['file']).name != 'IOPMGR.cpp' or not Path(record['directory']).is_absolute():
        raise SystemExit(f'{cpo}: expected the IOPMGR.cpp compilation record')
    out.mkdir(parents=True)
    source, obj = (out / ('NativeLegacyDisplay' + suffix) for suffix in ('.cpp', '.o'))
    # Clang's integrated assembler exports the exact synthetic constructor
    # while maintaining the normal Mach-O symbol ordering. Objcopy only
    # drops the automatic pointer; no handwritten rewriting of nlist.
    source.write_text(text.replace(BASE_METHOD, NUWA_METHOD, 1) +
                      f'\n__asm__(".globl {INIT}");\n')
    command = compile_args(record, source, obj, driver)
    provider = ROOT / 'package/NuwaLegacyDisplay.cpp'
    provider_obj = out / 'NuwaLegacyDisplay.o'
    provider_cmd = compile_args(record, provider, provider_obj, driver)
    bindings = ROOT / 'package/original-bindings.S'
    bindings_obj = out / 'original-bindings.o'
    target = [arg for arg in command if arg.startswith('--target=')][-1]
    bindings_cmd = [command[0], target, '-x', 'assembler-with-cpp', '-c',
                    str(bindings), '-o', str(bindings_obj)]
    write_json(out / 'compile.json', {
        'directory': record['directory'], 'arguments': command,
        'provider_arguments': provider_cmd, 'bindings_arguments': bindings_cmd,
        'cpo': str(cpo), 'cpo_sha256': sha256(cpo),
        'driver_revision': DRIVER_REV, 'adapted_source_sha256': sha256(source),
        'board_source_sha256': sha256(provider), 'bindings_source_sha256': sha256(bindings),
    })
    for argv in (command, provider_cmd, bindings_cmd):
        status = subprocess.run(argv, cwd=record['directory']).returncode
        if status:
            return status
    late = out / 'NativeLegacyDisplay.manual.o'
    subprocess.run(['llvm-objcopy', '--remove-section=__DATA,__mod_init_func', obj, late],
                   check=True)
    inspect_initializers(base, obj.read_bytes(), late.read_bytes())
    result = inspect_object(base, late.read_bytes())
    result.update(bytes=late.stat().st_size, sha256=sha256(late))
    write_json(out / 'object.json', result)
    archive = out / 'HOST-ONLY-incomplete-display.a'
    members = [late, provider_obj, bindings_obj]
    subprocess.run(['llvm-ar', '--format=darwin', 'rcs', archive, *members], check=True)
    audit = inspect_archive(base, archive, members)
    write_json(out / 'archive.json', audit)
    if audit['unresolved_sha256'] != UNRESOLVED_SHA256:
        raise SystemExit(f'unresolved symbol fingerprint changed: see {out / "archive.json"}')
    print(f'{archive}: {len(audit["unresolved"])} unresolved externals; not runtime-eligible')
    return 0


if __name__ == '__main__':
    sys.exit(main())
