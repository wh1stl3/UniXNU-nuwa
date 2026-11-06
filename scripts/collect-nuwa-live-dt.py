"""Read only: select nuwa, retain its Android FDT and compare fixed firmware regions.

No reboot, kernel-memory read, flash, image generation or configuration edits.
Device serials remain in memory. Raw FDT stays under ignored out/.
"""
import argparse
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--output', type=Path, required=True)
    cli.add_argument('--firmware', type=Path, default=Path('D:/Code/PortingiOS/nuwa/uefi-nuwa'))
    args = cli.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / 'reports') or output.exists():
        raise ValueError('Choose a fresh reports/ output')
    devices = subprocess.check_output(['adb', 'devices'], text=True)
    matches = []
    for line in devices.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1] == 'device':
            value = subprocess.check_output([
                'adb', '-s', parts[0], 'shell', 'getprop', 'ro.product.device'], text=True).strip()
            if value == 'nuwa':
                matches.append(parts[0])
    if len(matches) != 1:
        raise RuntimeError('No unique nuwa ADB target')
    serial = matches[0]
    command = "su -c 'cat /sys/firmware/fdt'"
    raw = subprocess.check_output(['adb', '-s', serial, 'exec-out', command], timeout=30)
    spec = importlib.util.spec_from_file_location('dt_parser', ROOT / 'scripts/audit-trial-boot-inputs.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    nodes = module.properties(raw)
    if (b'nuwa' not in nodes['/']['model'].lower()
            or b'kalama' not in nodes['/']['compatible'].lower()):
        raise ValueError('Live FDT does not identify nuwa/kalama')
    directory = ROOT / 'out/live-nuwa-dt' / output.stem
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'android-live.dtb').write_bytes(raw)
    selected, reserved = [], []
    for node, properties in nodes.items():
        keep = {}
        for name, value in properties.items():
            if ((node.startswith(('/memory', '/reserved-memory')) and name in (
                    'reg', 'device_type', 'compatible', 'no-map', 'reusable', '#address-cells', '#size-cells'))
                    or (node == '/chosen' and name in ('linux,initrd-start', 'linux,initrd-end'))
                    or (node == '/' and name in ('model', 'compatible', '#address-cells', '#size-cells'))):
                keep[name] = {'bytes': len(value), 'hex': value.hex()}
        if keep:
            selected.append({'node': node, 'properties': keep})
        if node.startswith('/reserved-memory/') and 'reg' in properties:
            parent = nodes['/reserved-memory']
            address_bytes = int.from_bytes(parent.get('#address-cells', b'\0\0\0\2'), 'big') * 4
            size_bytes = int.from_bytes(parent.get('#size-cells', b'\0\0\0\1'), 'big') * 4
            width = address_bytes + size_bytes
            data = properties['reg']
            if width <= 0 or len(data) % width:
                raise ValueError('Malformed reserved-memory reg cells')
            for index in range(0, len(data), width):
                start = int.from_bytes(data[index:index + address_bytes], 'big')
                size = int.from_bytes(data[index + address_bytes:index + width], 'big')
                reserved.append({'node': node, 'start': start, 'end': start + size})
    source = args.firmware / 'Platforms/Xiaomi/nuwaPkg/Library/MemoryMapLib/MemoryMapLib.c'
    pattern = r'\{"([^"]+)",\s*(0x[0-9A-Fa-f]+),\s*(0x[0-9A-Fa-f]+),'
    regions = [{'name': n, 'start': int(a, 16), 'end': int(a, 16) + int(s, 16)}
               for n, a, s in re.findall(pattern, source.read_text())]
    if not regions:
        raise ValueError('No firmware map regions parsed')
    overlaps = []
    for reservation in reserved:
        for region in regions:
            start, end = max(reservation['start'], region['start']), min(reservation['end'], region['end'])
            if start < end:
                overlaps.append({'android_node': reservation['node'], 'firmware_region': region['name'],
                                 'start': hex(start), 'end_exclusive': hex(end), 'bytes': end - start})
    observations = {}
    for prop in ('sys.boot_completed', 'ro.boot.bootreason', 'ro.boot.slot_suffix'):
        observations[prop] = subprocess.check_output([
            'adb', '-s', serial, 'shell', 'getprop', prop], text=True, timeout=15).strip()
    result = {'at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'scope': 'Live Android FDT, not candidate ABL x0/DT or running UEFI map validation',
              'argv': ['adb', '-s', '<selected-nuwa>', 'exec-out', command],
              'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(), 'selected_nodes': selected,
              'firmware_map_source': str(source),
              'firmware_map_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'reservation_overlaps': overlaps, 'observations': observations,
              'interpretation': 'Overlap is a lifecycle/ownership question; not proof of a simultaneous conflict'}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'output': str(output), 'fdt_sha256': result['sha256'],
                      'overlaps': len(overlaps), 'boot_completed': observations['sys.boot_completed']}))


if __name__ == '__main__':
    main()
