"""Narrow PMAP continuation FAT/readback and r4 relative-layout audit; never boots.

This is a new profile-aware gate. The frozen diagnostic audit script is left
unchanged and keeps rejecting anything that is not the pmap-ret-stop package.
"""
import argparse
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import owner_bnch as O
import owner_payload as P

spec = importlib.util.spec_from_file_location(
    'owner_pmap_ret_diagnostic_audit', Path(__file__).with_name('audit-owner-pmap-ret-package.py'))
D = importlib.util.module_from_spec(spec)
spec.loader.exec_module(D)


def audit(candidate, base, loader_image, continuation_reference, output):
    candidate = Path(candidate).resolve(strict=True)
    report = O.read_json(candidate / 'payload-record.json')
    O.require(report['profile'] == P.CONTINUATION_PROFILE and report.get('continuation_only') is True and
              report.get('execution_mode') == 'continue-original' and
              report.get('pmap_ret_restored') is True and report.get('observer_unhooked') is True and
              report.get('renderer_retained') is True and report['readback_complete'] and
              not report['device_release'], 'Not a frozen continuation package')
    prepared = (candidate / 'inputs/kernel.macho').read_bytes()
    artifact, facts = P.qualify_continuation(prepared, report['prepared_kernel_sha256'], continuation_reference)
    O.require(report['artifact_binding'] == artifact, 'Continuation report artifact binding mismatch')
    recorded = dict(report['continuation'])
    recorded.pop('source_diagnostic_path', None)
    actual = dict(facts)
    actual.pop('source_diagnostic_path', None)
    O.require(recorded == actual, 'Continuation source/inverse-diff evidence mismatch')
    O.require(O.read_json(candidate / 'continuation.json') == report['continuation'],
              'Continuation sidecar differs from payload record')
    image = Path(report['payload_path']).resolve(strict=True)
    O.require(image.is_relative_to(candidate) and O.sha(image.read_bytes()) == report['payload_sha256'],
              'Actual FAT image hash mismatch')
    dtb = (candidate / 'adt-generation/input.dtb').read_bytes()
    board = O.read_json(candidate / 'runtime-board.json')
    kwargs = O.read_json(candidate / 'adt-generation/keywords.json')
    P.check_profile_arguments(P.CONTINUATION_PROFILE, board['payload']['kernel_args'], [])
    O.require(board['payload']['kernel_args'] == P.CONTINUATION_ARGS and
              board['payload']['panic_screen'] is False and
              board['payload']['entry_probe_reset_delay'] == 0, 'Continuation runtime board drift')
    O.require(report['effective_kernel_args'] == ' '.join(P.CONTINUATION_ARGS) and
              report['overrides']['kernel_args']['after'] == P.CONTINUATION_ARGS and
              report['overrides']['kernel_args']['before'] == P.DIAGNOSTIC_ARGS,
              'Continuation argument override/evidence mismatch')
    binding = O.binding(dtb, board, kwargs, artifact)
    record, token = O.load_record(candidate / 'adt-generation/record.json', binding)
    adt = (candidate / 'adt-generation/final.adt').read_bytes()
    O.require(O.sha(adt) == record['final_adt_sha256'] == report['adt_sha256'] and
              O.sha((candidate / 'adt-generation/record.json').read_bytes()) == report['owner_record_sha256'],
              'Continuation ADT/record report mismatch')
    tree = O.inspect_adt(adt, token)
    adt_facts = P.diagnostic_adt(adt)
    O.require(adt_facts == report['diagnostic_adt_facts'] and
              adt_facts['memory_map_DeviceTree_present'] is False, 'Continuation ADT facts mismatch')
    # Scope is the actual trust-only frozen artifact, not generic ramdisk/addon combinations.
    members = {'Payloads/kernel.macho', 'Payloads/kernel.macho.trustcache',
               'Payloads/kernel.macho.adt', 'unixnu.toml'}
    O.require(set(report['input_hashes']) == members and not kwargs['data'] and kwargs['trust'] and
              not kwargs['addon'] and not kwargs['root_policies'], 'Layout audit requires trust-only artifact')
    trust = (candidate / 'inputs/kernel.macho.trustcache').read_bytes()
    r4 = Path(loader_image).read_bytes()
    O.require(len(r4) == 1495040 and O.sha(r4) == D.R4_SHA, 'Fixed r4 loader image mismatch')
    source_repo = Path(base).resolve() / 'drivers/DarwinBoot'
    source = O.git(source_repo, 'show', D.R4_COMMIT + ':DarwinBootPkg/Driver/DarwinBoot.c')
    O.require(O.sha(source.replace(b'\r', b'')) == D.R4_SOURCE_SHA, 'Fixed r4 formula source mismatch')
    # Binding evidence is mandatory. It is evidence of origin, not a runtime window/stack observation.
    evidence = O.read_json(O.ROOT / 'out/verifier-loader-r4-binding-20261111/binding.json')
    O.require(evidence['image_sha256'] == D.R4_SHA and evidence['fd_matches_build'], 'r4 evidence mismatch')
    correction = O.read_json(O.ROOT / 'out/verifier-loader-r4-binding-20261111/completion-r2/source-pin-correction.json')
    O.require(correction['equal_after_cr_removal'] and correction['pinned_sha256'] == D.R4_SOURCE_SHA,
              'r4 corrected source evidence mismatch')
    out = P.reserve(output)
    extraction = out / 'extracted'
    extraction.mkdir()
    P.capture(['mcopy', '-s', '-i', image, '::/EFI', extraction], out / 'extract-command.json')
    expected = {'Payloads/kernel.macho': prepared, 'Payloads/kernel.macho.adt': adt,
                'Payloads/kernel.macho.trustcache': trust,
                'unixnu.toml': (candidate / 'extracted/EFI/UniXNU/unixnu.toml').read_bytes()}
    hashes = P.verify_extracted(extraction, expected, adt, candidate / 'adt-generation/record.json',
                                SimpleNamespace(board=board), ' '.join(P.CONTINUATION_ARGS), artifact)
    O.require(hashes == report['fat_hashes'], 'Re-extracted FAT differs from wrapper report')
    vm_base, vm_end, segments = D.vm_layout(prepared)
    chosen = dict(O.find(tree, '/chosen')[1])
    window = int.from_bytes(chosen['darwinboot-memory-size'], 'little')
    layout = D.relative_layout(vm_base, vm_end, len(adt), len(trust), window)
    old = (O.ROOT / 'out/mix-n-match-20261110/audit-final/new/kernel.macho').read_bytes()
    O.require(O.sha(old) == O.KERNEL_SHA, 'Historical baseline hash drift')
    old_base, old_end, _ = D.vm_layout(old)
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
        'adt_sha256': O.sha(adt), 'adt_facts': adt_facts, 'fat_readback': hashes,
        'continuation': report['continuation'], 'execution_mode': report['execution_mode'],
        'pmap_ret_restored': True, 'observer_unhooked': True, 'renderer_retained': True,
        'runtime_ret_executed': 'not observed',
        'r4_image_sha256': D.R4_SHA, 'r4_formula_source_commit': D.R4_COMMIT,
        'r4_formula_source_normalized_sha256': D.R4_SOURCE_SHA,
        'formula_reference': 'DarwinBoot.c:724-732; no data/addon/policy in this artifact',
        'historical_baseline_vm_span': old_end - old_base,
        'vm_span_delta_from_baseline': (vm_end - vm_base) - (old_end - old_base),
        'known_nuwa_ranges': ranges, 'memory_table_source_sha256': O.sha(memory_source),
        'baseline_relative_layout_using_same_sidecar_sizes': D.relative_layout(old_base, old_end, len(adt), len(trust), window),
        'range_evidence': ['docs/step5-firmware.md:57-75,142-152,240-246,311',
            'uefi-nuwa/Platforms/Xiaomi/nuwaPkg/Library/MemoryMapLib/MemoryMapLib.c:26,31-32'],
        'conditional_nonoverlap': 'If the actual owned window lies wholly in the ADT high DRAM, '
            'kernel/Args/ADT/sidecars are above all listed low ranges. First-fit inference is not measured allocation.',
        'adt_dram_base': dram_base, 'adt_dram_bytes': dram_bytes,
        'gaps': ['Actual allocated window PA for this artifact not observed; no absolute PA claim',
                 'Live native/bootstrap stack extents and SP/lifetime not established; 2MiB guard is not proof',
                 'Actual GOP framebuffer and pool-reclaim addresses/lifetimes for this boot not observed',
                 'BootArgs field ABI/runtime consumption is not proven by a disjoint 4KiB allocation',
                 'memory-map/DeviceTree absent in generated ADT; no property fabricated',
                 'The restored PMAP RET word is a static byte fact; its runtime execution is not observed'],
        'known_loader_free_scope': 'Fixed r4 static review: FreePool(file buffers), not owned window',
        'relative_ranges_disjoint': True, 'absolute_conflicts_cleared': False, 'device_release': False,
        'authentication': 'NOT REACHED'}
    O.write_json(out / 'layout.json', result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('candidate', 'base', 'loader-image', 'continuation-reference', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    audit(a.candidate, a.base, a.loader_image, a.continuation_reference, a.output)
    print('self-checked continuation FAT/relative layout; runtime RET/window/stack not observed; no device release')


if __name__ == '__main__':
    main()
