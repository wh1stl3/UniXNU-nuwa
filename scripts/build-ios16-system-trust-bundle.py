#!/usr/bin/env python3
"""Emit the two unchanged 20H392 trust modules (OS + SystemOS cryptex) as one loader bundle.

Both modules are the payloads of Apple's own StaticTrustCache and
Cryptex1,SystemTrustCache IM4Ps of the same donor build: no cdhash is rewritten,
no entry is added and no policy exception is created. The container format is
the one DarwinBoot's ValidTrustCaches accepts (DarwinBoot.c:369-397: u32 Count
1-128, offset table, exact version-2 modules with strictly ascending cdhashes);
that parser is compiled from the same source file for the offline checks.
"""
import argparse
import hashlib
import json
import shutil
import struct
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT.parent.parent / 'UniXNU'
IPSW = BASE / 'out/ipsw/20H392'
LOADER = BASE / 'drivers/DarwinBoot/DarwinBootPkg/Driver/DarwinBoot.c'
OS = {'member': 'Firmware/087-86698-044.dmg.trustcache', 'file': '087-86698-044.dmg.trustcache',
      'sha256': '63e01c03b31e1532a5581a24865490673f0b5c297b0199fe0095637c6100ef4b',
      'digest_sha384': '6aa93bf357fd7a96470428b72cd736062688cff7dbc5683ce7ef542426bd1348a43fbbdf55c8907af17dac02e74b8b89'}
SYSTEM = {'member': 'Firmware/087-86593-047.dmg.trustcache', 'file': '087-86593-047.dmg.trustcache',
          'sha256': '9cc478fe3525e2683b5b9ea1eea0851eaebebdab21d206556233400e59d2e361',
          'digest_sha384': '511a45a0f9cf5a4be75852521565074bb97a47e6cbdba42eb13be5b281508c4417bc4120ee90a53a9ac3fc1d2974fec6'}
MANIFEST_SHA256 = '2d1452103a2f5ad71cb78d94454977fc70632472201980a468c247fba14b10b7'
# The single-module bundle the r3-r7 payloads carry (board.toml [payload] trust_cache_sha256).
ONE_MODULE_BUNDLE = '367e051548f9f0407fa9fe9d40007fa4e7c5ff27c45f5a7a30cedf344e24d98e'
SOURCE_SHA256 = '283fd6024a27d9122c73b95c79aa00d650f423d4374a1815485230d2192599f6'
sha = lambda data: hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def der(data, at):
    """One DER TLV: tag, body, next offset."""
    require(at + 2 <= len(data), 'Truncated DER')
    tag, size = data[at:at + 2]
    at += 2
    if size & 128:
        count = size & 127
        require(0 < count <= 4 and at + count <= len(data), 'Invalid DER length')
        size = int.from_bytes(data[at:at + count], 'big')
        at += count
    require(at + size <= len(data), 'DER exceeds input')
    return tag, data[at:at + size], at + size


def im4p_payload(data):
    """The OCTET STRING payload of an IM4P (DER: IM4P, type, description, data)."""
    tag, sequence, end = der(data, 0)
    fields, cursor = [], 0
    while cursor < len(sequence):
        kind, body, cursor = der(sequence, cursor)
        fields.append((kind, body))
    require(tag == 0x30 and end == len(data) and len(fields) == 4 and
            [kind for kind, _ in fields] == [0x16, 0x16, 0x16, 4] and fields[0][1] == b'IM4P',
            'Require an IM4P with one payload')
    return fields[3][1]


def module(name, data):
    """Check one trust module against the loader's rules and return it with its entry count."""
    require(len(data) >= 24, name + ': short module')
    version, count = struct.unpack_from('<I16xI', data)
    require(version == 2, name + ': not version 2')
    require(count > 0 and len(data) == 24 + count * 24, name + ': entry count/size mismatch')
    for entry in range(count):
        entry_bytes = data[24 + entry * 24:48 + entry * 24]
        require(1 <= entry_bytes[20] <= 4, name + ': invalid hash type')
        require(entry == 0 or data[24 + (entry - 1) * 24:44 + (entry - 1) * 24] < entry_bytes[:20],
                name + ': cdhash order')
    return data, count


def valid(data):
    """Python port of DarwinBoot.c ValidTrustCaches (369-397) for the offline readback."""
    if len(data) < 8:
        return False
    count = struct.unpack_from('<I', data)[0]
    if count == 0 or count > 128 or count > (len(data) - 4) // 4:
        return False
    for index in range(count):
        start = struct.unpack_from('<I', data, 4 + index * 4)[0]
        end = struct.unpack_from('<I', data, 8 + index * 4)[0] if index + 1 < count else len(data)
        if (start < 4 + count * 4 or start & 3 or end > len(data) or end < start or end - start < 24 or
                struct.unpack_from('<I', data, start)[0] != 2):
            return False
        entries = struct.unpack_from('<I', data, start + 20)[0]
        if entries > (end - start - 24) // 24 or end - start != 24 + entries * 24:
            return False
        for entry in range(entries):
            entry_bytes = data[start + 24 + entry * 24:start + 48 + entry * 24]
            if (entry_bytes[20] < 1 or entry_bytes[20] > 4 or
                    (entry and data[start + 24 + (entry - 1) * 24:start + 44 + (entry - 1) * 24] >= entry_bytes[:20])):
                return False
    return True


def parsed(data):
    """Read a bundle back: header offsets and every module's entry count."""
    count = struct.unpack_from('<I', data)[0]
    offsets = [struct.unpack_from('<I', data, 4 + index * 4)[0] for index in range(count)]
    modules = []
    for index, start in enumerate(offsets):
        end = offsets[index + 1] if index + 1 < count else len(data)
        modules.append({'offset': start, 'bytes': end - start,
                        'entries': struct.unpack_from('<I', data, start + 20)[0]})
    return count, offsets, modules


def linux(path):
    value = path.resolve().as_posix()
    if value.startswith('/mnt/d/'):
        return value
    require(value.startswith('D:/'), 'Host path must be on D:')
    return '/mnt/d/' + value[3:]


def host(*argv):
    """Run on the clang side: through WSL from Windows, directly inside Linux."""
    return ['wsl', '--', *argv] if shutil.which('wsl') else [*argv]


def loader_checks(work, fixtures):
    """Compile the pinned ValidTrustCaches and run every fixture through it."""
    source = LOADER.read_text()
    require(sha(LOADER.read_bytes()) == SOURCE_SHA256, 'DarwinBoot.c changed')
    start = source.index('STATIC\nBOOLEAN\nValidTrustCaches')
    function = source[start:source.index('\nSTATIC\n', start + 1)]
    wrapper = '''#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define STATIC static
#define CONST const
#define TRUE 1
#define FALSE 0
#define CompareMem memcmp
typedef uint8_t UINT8;typedef uint32_t UINT32;typedef size_t UINTN;typedef int BOOLEAN;
static UINT32 U32(const void *p){UINT32 v;memcpy(&v,p,4);return v;}
''' + function + '''
int main(int argc,char **argv){if(argc!=2)return 3;FILE *f=fopen(argv[1],"rb");if(!f)return 4;
fseek(f,0,SEEK_END);long n=ftell(f);rewind(f);if(n<0||n>1048576)return 5;
unsigned char *p=malloc(n?n:1);if(!p)return 6;if(fread(p,1,n,f)!=(size_t)n)return 7;
fclose(f);int ok=ValidTrustCaches(p,n);free(p);return ok?0:2;}
'''
    exe = work / 'validate-trust'
    subprocess.run(host('/usr/bin/clang', '-std=c11', '-Wall', '-Wextra', '-Werror',
                        '-x', 'c', '-', '-o', linux(exe)), input=wrapper.encode(), check=True)
    results = []
    for name, data, want in fixtures:
        path = work / (name + '.fixture')
        path.write_bytes(data)
        result = subprocess.run(host(linux(exe), linux(path)), capture_output=True)
        require(result.returncode == (0 if want else 2),
                f'{name}: parser returned {result.returncode}: {result.stderr[:200].decode(errors="replace")}')
        results.append({'name': name, 'accepted': want})
    return {'source': str(LOADER.relative_to(BASE)), 'source_sha256': SOURCE_SHA256,
            'function_sha256': sha(function.encode()), 'checks': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='directory under out/ for the bundle')
    options = parser.parse_args()
    out = options.output.resolve()
    require(out.is_relative_to((ROOT / 'out').resolve()) and not out.exists(), 'Output must be a new directory under out/')
    inputs = []
    for component in (OS, SYSTEM):
        raw = (IPSW / component['file']).read_bytes()
        require(sha(raw) == component['sha256'], 'Donor member mismatch: ' + component['file'])
        require(hashlib.sha384(raw).hexdigest() == component['digest_sha384'],
                'Donor member differs from the BuildManifest Digest: ' + component['file'])
        payload, entries = module(component['file'], im4p_payload(raw))
        inputs.append({'component': 'Cryptex1,SystemTrustCache' if component is SYSTEM else 'StaticTrustCache',
                       'member': component['member'], 'file': str((IPSW / component['file']).relative_to(BASE)),
                       'im4p_sha256': component['sha256'], 'im4p_digest_sha384': component['digest_sha384'],
                       'module_sha256': sha(payload), 'entries': entries, 'module_bytes': len(payload)})
        inputs[-1]['module'] = payload
    os_module, system_module = inputs[0]['module'], inputs[1]['module']
    single = (IPSW / '087-86698-044.dmg.trustcache.bundle').read_bytes()
    require(sha(single) == ONE_MODULE_BUNDLE and valid(single) and single[8:] == os_module,
            'OS module differs from the deployed single-module bundle')
    count, offsets, modules = parsed(single)
    require(count == 1 and offsets == [8] and modules[0]['entries'] == inputs[0]['entries'],
            'Deployed single-module bundle shape changed')
    # Count 2 -> the offset table is 4 + 2 * 4 bytes, so the two modules start at 12 and after the OS module.
    header = struct.pack('<I', 2) + struct.pack('<II', 12, 12 + len(os_module))
    bundle = header + os_module + system_module
    require(valid(bundle), 'Bundle rejected by the local ValidTrustCaches port')
    count, offsets, modules = parsed(bundle)
    require(count == 2 and offsets == [12, 12 + len(os_module)] and
            [m['entries'] for m in modules] == [inputs[0]['entries'], inputs[1]['entries']] and
            bundle[offsets[0]:offsets[0] + len(os_module)] == os_module and
            bundle[offsets[1]:] == system_module, 'Bundle readback mismatch')
    out.mkdir(parents=True)
    target = out / 'kernel.macho.trustcache'
    target.write_bytes(bundle)
    work = out / 'parser'
    work.mkdir()
    shutil.copyfile(IPSW / '087-86698-044.dmg.trustcache.bundle', work / 'deployed-single.bundle')
    fixtures = [('two-module', bundle, True), ('deployed-single', single, True),
                ('raw-system-im4p', (IPSW / SYSTEM['file']).read_bytes(), False)]
    for name, mutate in (
            ('truncated', lambda b: b[:-1]),
            ('zero-count', lambda b: bytes(4) + b[4:]),
            ('misaligned-offset', lambda b: b[:4] + struct.pack('<I', 13) + b[8:]),
            ('offset-into-header', lambda b: b[:4] + struct.pack('<I', 8) + b[8:]),
            ('invalid-hash-type', lambda b: b[:12 + 24 + 20] + bytes(1) + b[13 + 24 + 20:]),
            ('duplicate-cdhash', lambda b: b[:12 + 48] + b[12 + 24:12 + 48] + b[12 + 72:]),
            ('module-version', lambda b: b[:12] + struct.pack('<I', 3) + b[16:])):
        fixtures.append((name, bytes(mutate(bytearray(bundle))), False))
    parser_report = loader_checks(work, fixtures)
    report = {'image_build': '20H392', 'image_product': 'iPhone10,3',
              'build_manifest_sha256': MANIFEST_SHA256, 'inputs': [{k: v for k, v in i.items() if k != 'module'} for i in inputs],
              'bundle': {'path': str(target.relative_to(ROOT)), 'bytes': len(bundle), 'sha256': sha(bundle),
                         'count': count, 'offsets': offsets},
              'deployed_single_module_bundle': {'sha256': ONE_MODULE_BUNDLE, 'bytes': len(single), 'offsets': [8]},
              'os_module_bytes_preserved': True, 'modules_added': ['Cryptex1,SystemTrustCache'],
              'parser': parser_report, 'host_source_sha256': sha(Path(__file__).read_bytes()),
              'device_accessed': False, 'device_release': False,
              'apple_personalization_claimed': False, 'runtime_trust_acceptance': False}
    (out / 'inputs.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'bundle': report['bundle'], 'entries': [i['entries'] for i in inputs],
                      'parser_checks': len(fixtures)}, indent=2))


if __name__ == '__main__':
    main()
