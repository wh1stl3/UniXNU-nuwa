"""Read an existing source kernel with the pinned NativePrelink parser; never emit an image."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('kernel', type=Path)
parser.add_argument('--native-prelink', type=Path,
                    default=Path('D:/Code/PortingiOS/common/sources/UniXNU/kits/NativePrelink/native_prelink.py'))
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
output = args.output.resolve()
if not output.is_relative_to(ROOT / 'reports'):
    raise ValueError('Only JSON reports/ output is allowed')
data = args.kernel.read_bytes()
spec = importlib.util.spec_from_file_location('pinned_native_prelink', args.native_prelink)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
image = module.macho(data)
if image['kind'] != 2:
    raise ValueError('Expected MH_EXECUTE')
symbols = {}
for address, names in module.exports(data, image).items():
    for name in names:
        symbols.setdefault(name, set()).add(address)


def unique_symbol(name):
    addresses = symbols.get(name, set())
    if len(addresses) != 1:
        raise ValueError(f'Expected one exported symbol: {name}')
    return next(iter(addresses))


markers = {}
for name in ('_kalloc_sparse_prelink_index_version', '_native_prelink_security_init_version'):
    address = unique_symbol(name)
    offset = module.backed_offset(image['segments'], address, 4, len(data))
    value, = struct.unpack_from('<I', data, offset)
    if value != 1:
        raise ValueError(f'Unsupported marker: {name}={value}')
    markers[name] = {'value': value, 'address_from_binary': hex(address), 'file_offset': offset}
version_address = unique_symbol('_version')
version_offset = module.backed_offset(image['segments'], version_address, 1, len(data))
version_end = data.find(b'\0', version_offset, version_offset + 1024)
if version_end < 0:
    raise ValueError('Unterminated kernel version string')
module.backed_offset(image['segments'], version_address, version_end - version_offset + 1, len(data))
version = data[version_offset:version_end].decode('ascii')


def one_command(kind, minimum_size):
    matches = [(offset, size) for command, offset, size in image['commands'] if command == kind]
    if len(matches) != 1 or matches[0][1] < minimum_size:
        raise ValueError(f'Expected one load command {kind:#x}')
    return matches[0][0]


source_at = one_command(0x2a, 16)  # LC_SOURCE_VERSION
source_raw, = struct.unpack_from('<Q', data, source_at + 8)
source_parts = [(source_raw >> 40) & 0xffffff] + [
    (source_raw >> shift) & 0x3ff for shift in (30, 20, 10, 0)]
build_at = one_command(0x32, 24)  # LC_BUILD_VERSION
platform, minimum_os, sdk, _ = struct.unpack_from('<4I', data, build_at + 8)
dysym_at = one_command(0xb, 80)  # LC_DYSYMTAB
undefined_count, = struct.unpack_from('<I', data, dysym_at + 28)


def packed_version(value):
    return f'{value >> 16}.{(value >> 8) & 0xff}.{value & 0xff}'


segments = [{'name': s['name'], 'vmaddr': hex(s['va']), 'vmsize': s['size'],
             'fileoff': s['fileoff'], 'filesize': s['filesize'],
             'four_kib_start_alignment': (s['va'] % 4096 == 0 and s['fileoff'] % 4096 == 0)}
            for s in image['segments']]
report = {'kernel': str(args.kernel), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
          'format': 'ordinary ARM64 subtype0 MH_EXECUTE',
          'parser_sha256': hashlib.sha256(args.native_prelink.read_bytes()).hexdigest(),
          'version': {'symbol': '_version', 'string': version, 'file_offset': version_offset},
          'source_version_components': source_parts,
          'link_build_version': {'platform': platform, 'minimum_os': packed_version(minimum_os),
                                 'sdk_metadata': packed_version(sdk)},
          'undefined_symbol_count': undefined_count,
          'exported_symbol_count': len(symbols),
          'markers': markers, 'segments': segments,
          'prelink_executed': False, 'donor_compatibility': 'not validated',
          'device_verified': False}
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, indent=2))
