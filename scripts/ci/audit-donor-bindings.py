"""Inventory actual donor pointer bindings without emitting or rebinding an image."""
import argparse
from bisect import bisect_right
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[2]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--kernel', type=Path, required=True)
    cli.add_argument('--donor', type=Path, required=True)
    cli.add_argument('--selection-report', type=Path, required=True,
                     help='Existing report for this exact donor; selection is analytical, not board configuration')
    cli.add_argument('--parser', type=Path, default=Path(
        'D:/Code/PortingiOSLegacy/common/sources/UniXNU/kits/NativePrelink/native_prelink.py'))
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / 'reports'):
        raise ValueError('Only JSON reports in this repository may be written')
    kernel, donor = args.kernel.read_bytes(), args.donor.read_bytes()
    selection_data = args.selection_report.read_bytes()
    selection = json.loads(selection_data)
    if sha(donor) != selection['original_sha256']:
        raise ValueError('Selection report belongs to another donor')
    spec = importlib.util.spec_from_file_location('fixed_parser', args.parser)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    native, original = module.macho(kernel), module.macho(donor)
    if native['kind'] != 2 or original['kind'] != 2:
        raise ValueError('Need actual MH_EXECUTE kernel inputs')
    parent = original['segments']
    info = next(s for s in parent if s['name'] == '__PRELINK_INFO')
    at = module.backed_offset(parent, info['va'], info['filesize'], len(donor))
    metadata = module.unserialize_xml(donor[at:at + info['filesize']])
    entries = {}
    for entry in metadata['_PrelinkInfoDictionary']:
        identifier = entry['CFBundleIdentifier']
        if identifier in entries:
            raise ValueError('Duplicate donor identifier')
        entries[identifier] = entry
    selected, interfaces = set(), set()
    pending = list(selection['components']) + list(selection['codeless_components'])
    while pending:
        identifier = pending.pop()
        if identifier in selected or identifier in interfaces:
            continue
        entry = entries[identifier]
        if entry.get('OSKernelResource') is True:
            interfaces.add(identifier)
        else:
            selected.add(identifier)
            pending.extend(entry.get('OSBundleLibraries') or {})
    extents = []
    for identifier, entry in entries.items():
        va = entry.get('_PrelinkExecutableLoadAddr')
        if entry.get('OSKernelResource') is True or va is None or not entry.get('_PrelinkExecutableSize'):
            continue
        header = module.backed_offset(parent, va, 32, len(donor))
        image = module.macho(donor, header)
        if image['kind'] != 11:
            raise ValueError('Expected actual MH_KEXT_BUNDLE')
        for segment in image['segments']:
            if segment['size'] and segment['name'] != '__LINKEDIT':
                extents.append((segment['va'], segment['va'] + segment['size'], identifier))
    extents.sort()
    if any(a[1] > b[0] for a, b in zip(extents, extents[1:])):
        raise ValueError('Overlapping donor component extents')
    starts = [extent[0] for extent in extents]

    def owner(address):
        index = bisect_right(starts, address) - 1
        return extents[index] if index >= 0 and address < extents[index][1] else None

    native_names = {}
    for address, names in module.exports(kernel, native).items():
        for name in names:
            native_names.setdefault(name, set()).add(address)
    original_symbols = module.exports(donor, original)
    packed = metadata['_PrelinkLinkKASLROffsets']
    count, = struct.unpack_from('<I', packed)
    if len(packed) != 4 + 4 * count:
        raise ValueError('Invalid donor pointer table')
    offsets = struct.unpack_from(f'<{count}I', packed, 4)
    if len(set(offsets)) != count:
        raise ValueError('Duplicate pointer relocation site')
    base = next(s['va'] for s in parent if s['name'] == '__PRELINK_TEXT')
    pointer_counts = Counter()
    failures = []
    for offset in offsets:
        site = base + offset
        source = owner(site)
        if source is None or source[2] not in selected:
            continue
        if source != owner(site + 7):
            raise ValueError('Donor pointer spans a component extent')
        target, = struct.unpack_from('<Q', donor, module.backed_offset(parent, site, 8, len(donor)))
        target_owner = owner(target)
        if target_owner:
            pointer_counts['component'] += 1
            if target_owner[2] not in selected:
                failures.append({'module': source[2], 'site': hex(site),
                                 'error': 'undeclared component dependency', 'target_module': target_owner[2]})
            continue
        pointer_counts['kernel'] += 1
        try:
            native_target = module.unique_kernel_binding(target, original_symbols, native_names)
            if not any(s['va'] <= native_target < s['va'] + s['size'] for s in native['segments']):
                raise ValueError('Native binding outside mapped kernel')
        except ValueError as exc:
            failures.append({'module': source[2], 'site': hex(site), 'target': hex(target),
                             'names': original_symbols.get(target, []), 'error': str(exc)})
    report = {'scope': 'pointer-table name inventory only; no layout/PC-relative/ABI/runtime qualification',
              'native_sha256': sha(kernel), 'donor_sha256': sha(donor),
              'selection_report_sha256': sha(selection_data), 'parser_sha256': sha(args.parser.read_bytes()),
              'analytical_selection': sorted(selected), 'interfaces': sorted(interfaces),
              'pointer_counts': dict(pointer_counts), 'failure_count': len(failures), 'failures': failures,
              'missing_names': sorted({name for failure in failures for name in failure.get('names', [])
                                       if name not in native_names}),
              'board_configuration_adopted': False, 'images_modified': False, 'device_verified': False}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('native_sha256', 'pointer_counts', 'failure_count', 'missing_names')}, indent=2))


if __name__ == '__main__':
    main()
