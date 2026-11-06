"""Offline qualification sign-out for UFS-CHECK-9 r1. No device access."""
import datetime, hashlib, json
from pathlib import Path

ROOT = Path('D:/Code/PortingiOS/nuwa/UniXNU-nuwa')
OUT = ROOT/'reports/ufs-check-9-r1'
def sha(p): return hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
def read(p): return json.loads((ROOT/p).read_bytes())

build = read('out/ufs-check-9-r1/build.json')
d9 = build['check9_delta']
tests = {
 'reports/ufs-check-9-r1/tests-qualified/target-lifetime.json': 7,
 'reports/ufs-check-9-r1/tests-qualified/native-el0-restore.json': 4,
 'reports/ufs-check-9-r1/tests-qualified/native-helpers.json': 14,
 'reports/ufs-check-9-r1/tests-qualified/native-continuation.json': 20,
 'reports/ufs-check-9-r1/tests-qualified/check9-zero-draw.json': 8,
 'out/ufs-check-9-r1/coarse-tests.json': 20,
 'out/ufs-check-9-r1/machine-tests.json': 8,
 'reports/ufs-check-9-r1/tests-qualified/regression-binding.json': None,
 'out/ufs-check-9-r1/coarse-tests-r2-base.json': None,
 'out/ufs-check-9-r1/layout-tests.json': None,
}
reports = {}
for path, cases in tests.items():
    entry = {'sha256': sha(path)}
    if cases is not None:
        doc = read(path)
        assert doc['passed'] and len(doc.get('cases', doc.get('tests', []))) == cases, path
        entry['cases'] = cases
    else:
        assert read(path)['passed'], path
    reports[path] = entry
assert sum(v.get('cases', 0) for v in reports.values()) == 81

c5 = read('out/ufs-check-5-r1-qualified/kernel-proof.json')
q = dict(
    schema='Nuwa.CandidateQualification.v1',
    status='offline-diagnostic-qualified',
    time=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
    stage='P2/S06',
    candidate=dict(
        image_path=str(ROOT/'out/ufs-check-9-r1/boot-ufs-check-9-r1.img'),
        image_sha256=build['image_sha256'],
        image_bytes=build['image_bytes'],
        kernel_sha256=build['kernel_sha256'],
        adt_sha256=sha('out/ufs-check-9-r1/launch/kernel.macho.adt')),
    parent=dict(
        kernel_macho_sha256='1449dc8b6b9b71345fa5f1731e85c12b0a8a46f9334e350a963fb86011aa17e4',
        base='out/ufs-check-4-r1-clean',
        inherited_observers='UFS-CHECK-5 r1 verbatim prefix (all repair patches retained)',
        comparison_candidate='out/ufs-check-5-r1-qualified',
        comparison_kernel_sha256=c5['kernel_sha256']),
    observer=dict(
        source='package\\kernel-mainline\\CoarseStages-ufs-check9-r1.S',
        source_sha256=sha('package/kernel-mainline/CoarseStages-ufs-check9-r1.S'),
        source_equals_check5_byte_for_byte=True,
        builder='scripts/build-ufs-check9-r1.py',
        builder_sha256=sha('scripts/build-ufs-check9-r1.py'),
        code_bytes=build['code_bytes'],
        hooks=[],
        framebuffer_writes_added=0,
        framebuffer_writes_executed_on_boot_path=0,
        dsb_sy_on_boot_path=0,
        draw_body=dict(
            symbol='0xfffffff0084bb680', font='0xfffffff0084bb75c',
            instructions=d9['draw_body_instructions'], pattern=d9['draw_body_pattern'],
            bytes=d9['draw_body_bytes'], hex=d9['draw_body_hex'],
            font_bitmap_preserved_verbatim=True),
        single_variable=dict(
            whole_kernel_diff_vs_check5_bytes=d9['whole_kernel_diff_vs_check5']['total_bytes'],
            all_diff_within_draw_body=True,
            diff_file_range=d9['whole_kernel_diff_vs_check5']['file_range'],
            symbol_addresses_unchanged=True,
            observer_bytes_before_draw_unchanged=True,
            bl_draw_callsites_retained=37,
            note='The ENTIRE kernel differs from qualified CHECK5 only inside the draw body. No hook, no repair patch, no callsite, no symbol address was changed.'),
        patch_count=len(build['check5_delta']['callers']),
        note='ZERO-DRAW CONTROL. CHECK8 extra hooks dropped. Source is byte-identical to CHECK5. Only the appended draw helper body is replaced by ret+nops. Inherited x30 defect preserved so the execution path matches CHECK5/6/7/8.'),
    field_semantics=dict(
        path=str(OUT/'field-semantics.json'),
        sha256=sha('reports/ufs-check-9-r1/field-semantics.json'),
        required_by='AGENTS.md section 6',
        generated_by_formula=True,
        zero_draw=True,
        screen_expectation='F region entirely blank for the whole recording; verdict comes from non-field RGB colour-block timeline'),
    repair_patches=dict(
        coarse_release_before=dict(address='0xfffffff00769d230', effect='stlr x17,[x16] publishes ip_new_thread before FINAL_WAIT release', preserved=True),
        phase_record=dict(address=hex(build['symbols']['phase_record']), effect='thread-scoped gate and coarse_state+256 phase bitmap', preserved=True),
        inherited_observer_prefix_sha256=sha('package/kernel-mainline/CoarseStages-ufs-check5-r1.S'),
        inherited_read_return_chain_defect=dict(
            x30_installed_by_coarse_read_before='0xfffffff00769bfa4',
            coarse_read_after_patched_at='0xfffffff00769bf94',
            consequence='phase 6 hook structurally unreachable; deliberately preserved for comparability')),
    independent_rebuild=dict(
        work='out/ufs-check-9-r1-reproduce',
        kernel_macho_identical=True,
        unixnu_toml_identical=True,
        payload_fat_differs_only_by_adt_nonce=True,
        note='FAT payload differs because kernel.macho.adt carries a per-build nonce; the kernel and menu bytes are identical.'),
    tests=dict(
        total_cases=81, inherited_cases=73, new_cases=8,
        reports=reports,
        runner='scripts/test-ufs-check9-r1.py',
        runner_sha256=sha('scripts/test-ufs-check9-r1.py'),
        adaptations='Four inherited rendering assertions were adapted to the zero-draw contract (pixels must stay zero, no write-address audit). Adapted texts are archived under tests-qualified/adapted-*.',
        scope='Unicorn machine-code replay of the packaged observer, real execution of the packaged draw body with interception removed, plus inherited carrier model. No QEMU, no device.'),
    payload_readback=dict(
        embedded_kernel_offset='0x402e40',
        embedded_kernel_sha256=build['kernel_sha256'],
        fat_entries=['unixnu.toml', 'kernel.macho', 'kernel.macho.adt'],
        note='All three FAT entries read back byte-identically in the builder.'),
    device_accessed=False,
    deployed=False,
    consumed=False,
    release_239_retained=True,
    limitations=[
        'Zero-draw removes framebuffer writes but NOT hook control flow, phase_record gating, or the inherited x30 defect. A negative result excludes only screen writes.',
        'A positive result (boot progresses) would implicate observation but does not by itself locate the real UFS defect.',
        'The verdict depends on a 60fps full-length recording: short or end-state-only footage cannot distinguish an unchanged stall from slow progress.',
        'No field values exist in this candidate. A blank F region is expected and carries no phase information.'],
    readiness='Ready for one fastboot boot after a fresh preflight and an explicit recording/recovery confirmation.',
    qualification_phase_device_accessed=False,
    control_question='With observer screen writes removed, does boot progress past the CHECK5/6/7/8 stall?')

path = OUT/'qualification.json'
assert not path.exists(), 'qualification already signed out'
path.write_text(json.dumps(q, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print('signed out', path, hashlib.sha256(path.read_bytes()).hexdigest())
