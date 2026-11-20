#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Patent
"""Compile and inspect the complete 20H392 display TU; do not link or run it."""

import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DRIVER_REV = 'e47c1b8de169cd2bd0b885c7d85e433010e3cdf2'
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
    args = iter(record['arguments'])
    command = []
    for arg in args:
        if arg == record['file']:
            command.append(str(source))
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


def inspect_object(base, blob):
    sys.path.insert(0, str(base / 'kits/XnuPrelink'))
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
        ix, kind, section, _, value = struct.unpack_from('<IBBHQ', blob, symoff + i * 16)
        symbols.append((strings[ix:strings.index(b'\0', ix)].decode(), kind, section, value))
    table_name = '__ZTV19NativeLegacyDisplay'
    (_, kind, ordinal, value), = (sym for sym in symbols if sym[0] == table_name)
    if kind & 0x0e != 0x0e or not ordinal:  # N_SECT
        raise SystemExit(f'{table_name} is not defined in a section')
    sections = [s for segment in image['segments'] for s in segment['sections']]
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
    if subprocess.check_output(git + ['rev-parse', 'HEAD'], text=True).strip() != DRIVER_REV:
        raise SystemExit(f'expected GopFramebuffer at {DRIVER_REV}')
    if subprocess.check_output(git + ['status', '--porcelain', '--', '.']):
        raise SystemExit('GopFramebuffer inputs are dirty')
    text = original.read_text()
    if text.count(BASE_METHOD) != 1:
        raise SystemExit(f'{original}: expected exactly one qualified frame-info body')
    record = json.loads(cpo.read_text().strip().rstrip(','))
    if Path(record['file']).name != 'IOPMGR.cpp':
        raise SystemExit(f'{cpo}: expected the IOPMGR.cpp compilation record')
    out.mkdir(parents=True)
    source, obj = (out / ('NativeLegacyDisplay' + suffix) for suffix in ('.cpp', '.o'))
    source.write_text(text.replace(BASE_METHOD, NUWA_METHOD, 1))
    command = compile_args(record, source, obj, driver)
    write_json(out / 'compile.json', {
        'directory': record['directory'], 'arguments': command,
        'cpo': str(cpo), 'cpo_sha256': sha256(cpo),
        'driver_revision': DRIVER_REV, 'adapted_source_sha256': sha256(source),
    })
    status = subprocess.run(command, cwd=record['directory']).returncode
    if status:
        return status
    result = inspect_object(base, obj.read_bytes())
    result.update(bytes=obj.stat().st_size, sha256=sha256(obj))
    write_json(out / 'object.json', result)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
