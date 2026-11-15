"""Frozen PMAP diagnostic FAT/readback and r4 relative layout audit; never boots."""
import argparse
import struct
from pathlib import Path
from types import SimpleNamespace

import owner_bnch as O
import owner_payload as P

R4_SHA = '692cfcca51af81230fecbba15425cf598182fbe53abb362b6046dec0f24dc2e5'
R4_COMMIT = '3c75734014cdab0acd9541e88057b7606ee7ae08'
R4_SOURCE_SHA = 'f3815791ad63b87b11ee28118ad1f35a7d0c5258ea70b7b76eda68914fa2b8cf'


def align(value, size):
    return (value + size - 1) & -size


def vm_layout(raw):
    O.require(len(raw) >= 32 and struct.unpack_from('<I', raw)[0] == 0xfeedfacf, 'MachO header')
    count, size = struct.unpack_from('<II', raw, 16)
    at, end, segments = 32, 32 + size, []
    O.require(end <= len(raw), 'MachO load commands bounds')
    for _ in range(count):
        O.require(at + 8 <= end, 'MachO command header')
        kind, length = struct.unpack_from('<II', raw, at)
        O.require(length >= 8 and length % 8 == 0 and at + length <= end, 'MachO command size')
        if kind == 0x19:
            O.require(length >= 72, 'MachO segment command')
            va, vm, offset, file_bytes = struct.unpack_from('<QQQQ', raw, at + 24)
            if vm:
                O.require(file_bytes <= vm and offset + file_bytes <= len(raw) and va + vm < 1 << 64,
                          'MachO segment VM/file bounds')
                segments.append({'name': raw[at + 8:at + 24].rstrip(b'\0').decode(),
                                 'vmaddr': va, 'vmsize': vm, 'fileoff': offset, 'filesize': file_bytes})
        at += length
    O.require(at == end and segments, 'MachO commands/segments incomplete')
    ordered = sorted(segments, key=lambda x: x['vmaddr'])
    O.require(all(a['vmaddr'] + a['vmsize'] <= b['vmaddr'] for a, b in zip(ordered, ordered[1:])),
              'Root VM segments overlap')
    return min(x['vmaddr'] for x in segments), max(x['vmaddr'] + x['vmsize'] for x in segments), segments


def relative_layout(base, end, tree_bytes, trust_bytes, window):
    O.require(base % 4096 == 0 and end > base and tree_bytes > 0 and trust_bytes >= 0 and
              0x10000000 <= window <= 0x200000000 and window % 0x200000 == 0, 'Layout input bounds')
    # AllocateWindow: W = align(ConventionalStart, 2MiB) + (Kernel.Base & (2MiB-1)).
    # Use only this proven residue, NOT an assumed physical window allocation address.
    residue = base & 0x1fffff
    args = align(residue + end - base, 16384) - residue
    tree = args + 4096
    ramdisk = align(residue + tree + tree_bytes, 4096) - residue
    addon = align(residue + ramdisk + trust_bytes, 16384) - residue
    policy = align(residue + addon, 16384) - residue
    used = align(residue + policy, 16384) - residue
    O.require(used <= window - 0x200000, 'Used exceeds window minus loader 2MiB guard')
    intervals = [('kernel_vm_span', 0, end - base), ('boot_args_page', args, args + 4096),
                 ('adt', tree, tree + tree_bytes), ('trustcache', ramdisk, ramdisk + trust_bytes)]
    O.require(all(a[2] <= b[1] for a, b in zip(intervals, intervals[1:])), 'Relative layout overlap')
    return {'window_base_physical': None, 'window_base_symbol': 'W (actual allocator result not captured)',
            'window_base_mod_2MiB': residue, 'window_bytes': window,
            'kernel_vm_span': end - base, 'Args_offset': args, 'Tree_offset': tree,
            'Ramdisk_offset': ramdisk, 'Ramdisk_bytes': 0, 'TrustCache_offset': ramdisk,
            'Addon_offset': addon, 'Policy_offset': policy, 'Top_offset': used, 'Used': used,
            'limit': window - 0x200000, 'remaining_window_bytes': window - used,
            'loader_guard_bytes': 0x200000, 'guard_is_proven_stack_reservation': False,
            'boot_args_VA': base + args, 'DeviceTree_VA': base + tree,
            'intervals_relative_to_W': [{'name': n, 'start': lo, 'end': hi} for n, lo, hi in intervals]}


def audit(candidate, base, loader_image, output):
    candidate = Path(candidate).resolve(strict=True)
    report = O.read_json(candidate / 'payload-record.json')
    O.require(report['profile'] == P.DIAGNOSTIC_PROFILE and report['diagnostic_only'] and
              report['readback_complete'] and not report['device_release'], 'Not a frozen diagnostic package')
    prepared = (candidate / 'inputs/kernel.macho').read_bytes()
    artifact = P.qualify_prepared(prepared, report['prepared_kernel_sha256'], P.DIAGNOSTIC_PROFILE)
    image = Path(report['payload_path']).resolve(strict=True)
    O.require(image.is_relative_to(candidate) and O.sha(image.read_bytes()) == report['payload_sha256'],
              'Actual FAT image hash mismatch')
    dtb = (candidate / 'adt-generation/input.dtb').read_bytes()
    board = O.read_json(candidate / 'runtime-board.json')
    kwargs = O.read_json(candidate / 'adt-generation/keywords.json')
    O.require(board['payload']['kernel_args'] == P.DIAGNOSTIC_ARGS, 'Diagnostic args changed')
    binding = O.binding(dtb, board, kwargs, artifact)
    record, token = O.load_record(candidate / 'adt-generation/record.json', binding)
    adt = (candidate / 'adt-generation/final.adt').read_bytes()
    O.require(O.sha(adt) == record['final_adt_sha256'] == report['adt_sha256'] and
              O.sha((candidate / 'adt-generation/record.json').read_bytes()) == report['owner_record_sha256'],
              'Diagnostic ADT/record report mismatch')
    tree = O.inspect_adt(adt, token)
    facts = P.diagnostic_adt(adt)
    # Scope is deliberately the actual trust-only frozen artifact, not generic ramdisk/addon layouts.
    members = {'Payloads/kernel.macho', 'Payloads/kernel.macho.trustcache',
               'Payloads/kernel.macho.adt', 'unixnu.toml'}
    O.require(set(report['input_hashes']) == members and not kwargs['data'] and kwargs['trust'] and
              not kwargs['addon'] and not kwargs['root_policies'], 'Layout audit requires trust-only artifact')
    trust = (candidate / 'inputs/kernel.macho.trustcache').read_bytes()
    r4 = Path(loader_image).read_bytes()
    O.require(len(r4) == 1495040 and O.sha(r4) == R4_SHA, 'Fixed r4 loader image mismatch')
    source_repo = Path(base).resolve() / 'drivers/DarwinBoot'
    source = O.git(source_repo, 'show', R4_COMMIT + ':DarwinBootPkg/Driver/DarwinBoot.c')
    O.require(O.sha(source.replace(b'\r', b'')) == R4_SOURCE_SHA, 'Fixed r4 formula source mismatch')
    # Binding evidence is mandatory. It is evidence of origin, not a runtime window/stack observation.
    evidence = O.read_json(O.ROOT / 'out/verifier-loader-r4-binding-20261111/binding.json')
    O.require(evidence['image_sha256'] == R4_SHA and evidence['fd_matches_build'], 'r4 evidence mismatch')
    correction = O.read_json(O.ROOT / 'out/verifier-loader-r4-binding-20261111/completion-r2/source-pin-correction.json')
    O.require(correction['equal_after_cr_removal'] and correction['pinned_sha256'] == R4_SOURCE_SHA,
              'r4 corrected source evidence mismatch')
    out = P.reserve(output)
    extraction = out / 'extracted'
    extraction.mkdir()
    P.capture(['mcopy', '-s', '-i', image, '::/EFI', extraction], out / 'extract-command.json')
    expected = {'Payloads/kernel.macho': prepared, 'Payloads/kernel.macho.adt': adt,
                'Payloads/kernel.macho.trustcache': trust,
                'unixnu.toml': (candidate / 'extracted/EFI/UniXNU/unixnu.toml').read_bytes()}
    hashes = P.verify_extracted(extraction, expected, adt, candidate / 'adt-generation/record.json',
                                SimpleNamespace(board=board), ' '.join(P.DIAGNOSTIC_ARGS), artifact)
    O.require(hashes == report['fat_hashes'], 'Re-extracted FAT differs from wrapper report')
    vm_base, vm_end, segments = vm_layout(prepared)
    chosen = dict(O.find(tree, '/chosen')[1])
    window = int.from_bytes(chosen['darwinboot-memory-size'], 'little')
    layout = relative_layout(vm_base, vm_end, len(adt), len(trust), window)
    old = (O.ROOT / 'out/mix-n-match-20261110/audit-final/new/kernel.macho').read_bytes()
    O.require(O.sha(old) == O.KERNEL_SHA, 'Historical baseline hash drift')
    old_base, old_end, _ = vm_layout(old)
    dram_base = int.from_bytes(chosen['dram-base'], 'little')
    dram_bytes = int.from_bytes(chosen['dram-size'], 'little')
    ranges = [
        {'name': 'UEFI stack (source table, not live SP)', 'start': 0xa760d000, 'bytes': 0x40000},
        {'name': 'Display Reserved / historical live framebuffer', 'start': 0xb8000000, 'bytes': 0x2b00000},
        {'name': 'DXE Heap / potential pool reclamation region', 'start': 0xbab00000, 'bytes': 0xd1c0000}]
    for region in ranges:
        region['disjoint_from_entire_adt_high_dram'] = (region['start'] + region['bytes'] <= dram_base or
                                                       region['start'] >= dram_base + dram_bytes)
        O.require(region['disjoint_from_entire_adt_high_dram'], 'Known low source range intersects ADT high DRAM')
    O.require(window <= dram_bytes, 'Owned size exceeds ADT high DRAM span')
    memory_source_path = O.ROOT.parent / 'uefi-nuwa/Platforms/Xiaomi/nuwaPkg/Library/MemoryMapLib/MemoryMapLib.c'
    memory_source = memory_source_path.read_bytes()
    O.require(O.sha(memory_source) == '677967c096b5f789fc51191a867db821da2e35b08ddf7ff746a9a868959bc13c',
              'Known nuwa memory-table source drift')
    result = {'status': 'self-checked', 'candidate': str(candidate), 'kernel_sha256': artifact['kernel_sha256'],
        'kernel_file_bytes': len(prepared), 'root_segments': segments, 'kernel_vm_base': vm_base,
        'kernel_vm_end': vm_end, 'layout': layout, 'adt_bytes': len(adt), 'trust_bytes': len(trust),
        'adt_sha256': O.sha(adt), 'adt_facts': facts, 'fat_readback': hashes,
        'r4_image_sha256': R4_SHA, 'r4_formula_source_commit': R4_COMMIT,
        'r4_formula_source_normalized_sha256': R4_SOURCE_SHA,
        'formula_reference': 'DarwinBoot.c:724-732; no data/addon/policy in this artifact',
        'historical_baseline_vm_span': old_end - old_base,
        'vm_span_delta_from_baseline': (vm_end - vm_base) - (old_end - old_base),
        'known_nuwa_ranges': ranges, 'memory_table_source_sha256': O.sha(memory_source),
        'baseline_relative_layout_using_same_sidecar_sizes': relative_layout(old_base, old_end, len(adt), len(trust), window),
        'range_evidence': ['docs/step5-firmware.md:57-75,142-152,240-246,311',
            'uefi-nuwa/Platforms/Xiaomi/nuwaPkg/Library/MemoryMapLib/MemoryMapLib.c:26,31-32'],
        'conditional_nonoverlap': 'If actual owned window lies wholly in ADT high DRAM, '
            'kernel/Args/ADT/sidecars are above all listed low ranges. First-fit inference is not measured allocation.',
        'adt_dram_base': dram_base, 'adt_dram_bytes': dram_bytes,
        'gaps': ['Actual allocated window PA for this artifact not observed; no absolute PA claim',
                 'Live native/bootstrap stack extents and SP/lifetime not established; 2MiB guard is not proof',
                 'Actual GOP framebuffer and pool-reclaim addresses/lifetimes for this boot not observed',
                 'BootArgs field ABI/runtime consumption is not proven by a disjoint 4KiB allocation',
                 'memory-map/DeviceTree absent in generated ADT; no property fabricated'],
        'known_loader_free_scope': 'Fixed r4 static review: FreePool(file buffers), not owned window',
        'relative_ranges_disjoint': True, 'absolute_conflicts_cleared': False, 'device_release': False,
        'authentication': 'NOT REACHED'}
    O.write_json(out / 'layout.json', result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('candidate', 'base', 'loader-image', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    audit(a.candidate, a.base, a.loader_image, a.output)
    print('self-checked frozen FAT/relative layout; absolute window/stack gaps remain; no device release')


if __name__ == '__main__':
    main()
