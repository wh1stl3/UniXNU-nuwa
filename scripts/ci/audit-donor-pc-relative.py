"""Enumerate unqualified donor PC-relative encodings; never relax emit or write an image."""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--donor', type=Path, required=True)
    cli.add_argument('--selection-report', type=Path, required=True)
    cli.add_argument('--existing-candidate', type=Path,
                     help='Read an existing candidate only; never create or modify it')
    cli.add_argument('--tool-directory', type=Path, default=Path(
        'D:/Code/PortingiOSLegacy/common/sources/UniXNU/kits/NativePrelink'))
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / 'reports'):
        raise ValueError('Only JSON reports in this repository are writable')
    sys.path.insert(0, str(args.tool_directory))
    import native_prelink as parser
    spec = importlib.util.spec_from_file_location('readonly_emit_functions', args.tool_directory / 'emit_prelink.py')
    emit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(emit)
    data = args.donor.read_bytes()
    selection = json.loads(args.selection_report.read_text())
    digest = hashlib.sha256(data).hexdigest()
    if digest != selection['original_sha256']:
        raise ValueError('Selection belongs to another donor')
    parent = parser.macho(data)['segments']
    info = next(s for s in parent if s['name'] == '__PRELINK_INFO')
    at = parser.backed_offset(parent, info['va'], info['filesize'], len(data))
    metadata = parser.unserialize_xml(data[at:at + info['filesize']])
    entries = {entry['CFBundleIdentifier']: entry for entry in metadata['_PrelinkInfoDictionary']}
    modules = {}
    for identifier in selection['components']:
        va = entries[identifier]['_PrelinkExecutableLoadAddr']
        modules[identifier] = parser.macho(data, parser.backed_offset(parent, va, 32, len(data)))
    official_digests = {emit.SHA256_K_DIGEST, emit.VECTOR_REPEAT_DIGEST, emit.ADLER32_VECTOR_DIGEST}
    official_digests.update(pool[2] for pool in emit.MATH_LITERAL_POOLS)
    literals = {}
    for region in selection['known_inline_data']:
        if region['sha256'] not in official_digests:
            raise ValueError('Reference report skips a pool not present in the pinned official tool')
        at = parser.backed_offset(parent, region['va'], region['size'], len(data))
        if hashlib.sha256(data[at:at + region['size']]).hexdigest() != region['sha256']:
            raise ValueError('Known pool bytes do not match their complete digest')
        literals.setdefault(region['module'], []).append((region['va'], region['va'] + region['size']))
    extents = [s for module in modules.values() for s in module['segments']
               if s['size'] and s['name'] != '__LINKEDIT']
    unqualified = []
    internal_count = 0
    for identifier, module in modules.items():
        for segment in module['segments']:
            if segment['name'] != '__TEXT_EXEC' or not segment['filesize']:
                continue
            at = parser.backed_offset(parent, segment['va'], segment['filesize'], len(data))
            blob = data[at:at + segment['filesize']]
            for offset in range(0, len(blob) - 3, 4):
                pc = segment['va'] + offset
                if any(start <= pc < end for start, end in literals.get(identifier, [])):
                    continue
                word, = struct.unpack_from('<I', blob, offset)
                decoded = emit.pc_relative_target(word, pc)
                if decoded is None:
                    continue
                target, page = decoded
                if page:
                    internal = any((s['va'] & ~4095) <= target < emit.align(s['va'] + s['size']) for s in extents)
                else:
                    internal = any(s['va'] <= target < s['va'] + s['size'] for s in extents)
                if internal:
                    internal_count += 1
                    continue
                unqualified.append({'module': identifier, 'va': hex(pc), 'word': hex(word),
                                    'decoded_target': hex(target), 'page_relative': page,
                                    'file_offset': at + offset,
                                    'context_hex': blob[max(0, offset - 16):offset + 20].hex(),
                                    'classification': 'unqualified; not automatically inline data'})
    try:
        emit.instruction_inventory(data, parent, modules)
        official_refusal = None
    except ValueError as exc:
        official_refusal = str(exc)
    reference_sites = {entry['va'] for entry in selection['inline_data_outside_image']}
    actual_sites = {int(entry['va'], 16) for entry in unqualified}
    preservation = None
    if args.existing_candidate:
        candidate = args.existing_candidate.read_bytes()
        candidate_sha = hashlib.sha256(candidate).hexdigest()
        if candidate_sha != selection['candidate_sha256']:
            raise ValueError('Existing candidate does not match the selection report')
        candidate_segments = parser.macho(candidate)['segments']
        checked = []
        for identifier, module in modules.items():
            for segment in module['segments']:
                if segment['name'] != '__TEXT_EXEC' or not segment['filesize']:
                    continue
                size = segment['filesize']
                before = parser.backed_offset(parent, segment['va'], size, len(data))
                after = parser.backed_offset(candidate_segments, segment['va'] + selection['slide'], size, len(candidate))
                checked.append({'module': identifier, 'bytes': size,
                    'original_sha256': hashlib.sha256(data[before:before + size]).hexdigest(),
                    'existing_sha256': hashlib.sha256(candidate[after:after + size]).hexdigest(),
                    'identical': data[before:before + size] == candidate[after:after + size]})
        preservation = {'candidate_sha256': candidate_sha, 'ranges': checked,
                        'all_identical': all(item['identical'] for item in checked),
                        'qualification': 'byte preservation only; code/data boundaries and target semantics remain unqualified'}
    report = {'scope': 'read-only instruction encoding inventory; no code/data/ABI qualification',
              'donor_sha256': digest, 'official_emit_sha256': hashlib.sha256(
                  (args.tool_directory / 'emit_prelink.py').read_bytes()).hexdigest(),
              'full_hash_checked_known_pools': len(selection['known_inline_data']),
              'internal_pc_relative_encoding_count': internal_count,
              'unqualified_count': len(unqualified),
              'unqualified_page_relative_count': sum(item['page_relative'] for item in unqualified),
              'unqualified_sites': unqualified,
              'official_inventory_refusal': official_refusal,
              'existing_candidate_text_preservation': preservation,
              'reference_exemption_kinds': dict(Counter(entry.get('kind', 'outside-image-window')
                  for entry in selection['inline_data_outside_image'])),
              'reference_only_sites': [hex(va) for va in sorted(reference_sites - actual_sites)],
              'new_only_sites': [hex(va) for va in sorted(actual_sites - reference_sites)],
              'emit_executed': False, 'images_modified': False, 'device_verified': False}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('unqualified_count', 'unqualified_page_relative_count',
        'official_inventory_refusal', 'reference_only_sites', 'new_only_sites')}, indent=2))


if __name__ == '__main__':
    main()
