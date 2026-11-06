"""Offline qualification sign-out for UFS-CHECK-10 r1. No device access."""
import datetime, hashlib, json
from pathlib import Path

ROOT = Path('D:/Code/PortingiOS/nuwa/UniXNU-nuwa')
OUT = ROOT / 'reports/ufs-check-10-r1'


def sha(p):
    return hashlib.sha256((ROOT / p).read_bytes()).hexdigest()


def read(p):
    return json.loads((ROOT / p).read_bytes())


build = read('out/ufs-check-10-r1/build.json')
proof = read('out/ufs-check-10-r1/kernel-proof.json')
d10 = build['check10_delta']
tests = {
    'reports/ufs-check-10-r1/tests-qualified/target-lifetime.json': 7,
    'reports/ufs-check-10-r1/tests-qualified/native-el0-restore.json': 4,
    'reports/ufs-check-10-r1/tests-qualified/native-helpers.json': 14,
    'reports/ufs-check-10-r1/tests-qualified/native-continuation.json': 20,
    'reports/ufs-check-10-r1/tests-qualified/check8-selfcheck.json': 3,
    'reports/ufs-check-10-r1/tests-qualified/check8-read-return.json': 3,
    'reports/ufs-check-10-r1/tests-qualified/check10-ret-witness.json': 3,
    'out/ufs-check-10-r1/coarse-tests.json': 20,
    'out/ufs-check-10-r1/machine-tests.json': 8,
    'reports/ufs-check-10-r1/tests-qualified/regression-binding.json': None,
    'reports/ufs-check-10-r1/tests-qualified/check10-byte-binding.json': None,
    'out/ufs-check-10-r1/coarse-tests-r2-base.json': None,
    'out/ufs-check-10-r1/layout-tests.json': None,
}
reports = {}
for path, cases in tests.items():
    entry = {'sha256': sha(path)}
    doc = read(path)
    assert doc['passed'], path
    if cases is not None:
        assert len(doc.get('cases', doc.get('tests', []))) == cases, path
        entry['cases'] = cases
    reports[path] = entry
assert sum(v.get('cases', 0) for v in reports.values()) == 82, 'qualification case count'

q = dict(
    schema='Nuwa.CandidateQualification.v1',
    status='offline-diagnostic-qualified',
    time=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
    stage='P2/S06',
    candidate=dict(
        image_path=str(ROOT / 'out/ufs-check-10-r1/boot-ufs-check-10-r1.img'),
        image_sha256=build['image_sha256'],
        image_bytes=build['image_bytes'],
        kernel_sha256=build['kernel_sha256'],
        adt_sha256=sha('out/ufs-check-10-r1/launch/kernel.macho.adt')),
    parent=dict(
        kernel_macho_sha256='1449dc8b6b9b71345fa5f1731e85c12b0a8a46f9334e350a963fb86011aa17e4',
        base='out/ufs-check-4-r1-clean',
        inherited_observers='UFS-CHECK-8 r1 observer source verbatim prefix (CHECK5 repair patches retained)',
        comparison_candidate='out/ufs-check-8-r1 (consumed)',
        comparison_kernel_sha256=d10['baseline_kernel_sha256']),
    observer=dict(
        source='package/kernel-mainline/CoarseStages-ufs-check10-r1.S',
        source_sha256=sha('package/kernel-mainline/CoarseStages-ufs-check10-r1.S'),
        source_prefix_equals_check8_byte_for_byte=True,
        builder='scripts/build-ufs-check10-r1.py',
        builder_sha256=sha('scripts/build-ufs-check10-r1.py'),
        code_bytes=build['code_bytes'],
        new_hook='c10_vn_rdwr_ret',
        new_patch_site=d10['new_patch_site'],
        native_ret_preserved_at=d10['native_ret_preserved_at'],
        framebuffer_writes_added=3,
        control_flow_changed=False,
        single_variable=dict(
            outside_cave_diff_word_count=d10['outside_cave_diff_word_count'],
            outside_cave_only_diff=d10['outside_cave_only_diff'],
            repair_patches_removed=0,
            inherited_observations_removed=0,
            note='Cave 内部 draw/font 后移与 bl draw 重定位属追加 hook 的必然结果；cave 之外整颗内核相对 CHECK8 只有 0x74669C8 一个 word 改动，原生 ret 保持 c0035fd6。'),
        patch_count=len(build['check5_delta']['callers']),
        note='RET WITNESS. One new ungated hook on the _vn_rdwr epilogue captures w0 and the restored x30 into FB15/FB16/FB17. CHECK8 source is the byte-identical prefix; no repair patch, no observation and no control flow was removed or changed.'),
    field_semantics=dict(
        path=str(OUT / 'field-semantics.json'),
        sha256=sha('reports/ufs-check-10-r1/field-semantics.json'),
        required_by='AGENTS.md section 6',
        generated_by_formula=True,
        new_field_ids_decimal=[21, 22, 23],
        new_field_labels=['FB15', 'FB16', 'FB17'],
        screen_expectation='FB00..FB14 unchanged from CHECK8; FB15/FB16/FB17 are the verdict fields. Non-field colour blocks still require 60fps per-frame RGB classification.'),
    repair_patches=dict(
        coarse_release_before=dict(address='0xfffffff00769d230', effect='stlr x17,[x16] publishes ip_new_thread before FINAL_WAIT release', preserved=True),
        phase_record=dict(address=hex(build['symbols']['phase_record']), effect='thread-scoped gate and coarse_state+256 phase bitmap', preserved=True),
        inherited_observer_prefix_sha256=sha('package/kernel-mainline/CoarseStages-ufs-check5-r1.S'),
        inherited_read_return_chain=proof['repair_patches']['inherited_read_return_chain_defect']),
    corrections_from_offline_audit=dict(
        x30_immediate='movz #49044 == 0xBF94 (NOT 0xBFA4); CHECK8 source comment and build script string were wrong, machine code and the offline audit were right',
        check8_fb07='0x769BFA4 is the resid!=0 short-read path; 0x769BF9C cbz w23 skips it on resid==0. A blank FB07 cannot witness a missing vn_rdwr return. CHECK8 conclusion is withdrawn here, its archived result.md is not rewritten.',
        previous_p0='Dropping the 0x84D9BE4 legacy bridge would be pointless: it IS on the live return chain (0x769BF94 -> coarse_read_after -> 0x84D9BE4 cbz w0). CHECK10 instead observes the real RET.',
        archived_artifacts_not_modified=True),
    independent_rebuild=dict(
        work='out/ufs-check-10-r1-reproduce',
        kernel_macho_identical=True,
        unixnu_toml_identical=True,
        payload_fat_differs=True,
        payload_fat_diff_reason='kernel.macho.adt carries a per-build CSPRNG nonce (secrets.token_bytes(32) in nuwa_launch_context.create) plus FAT directory timestamps; this is a deliberate mix-and-match prevention contract, not a build defect. CHECK9 reproduce shows the same behaviour.',
        reproducible_units=['kernel.macho', 'fat/unixnu.toml', 'fat/kernel.macho', 'embedded kernel bytes in the boot image'],
        note='The boot image is therefore a single-consumption artifact; qualification binds its exact SHA256 rather than expecting byte reproduction.'),
    tests=dict(
        total_cases=82, inherited_cases=73, new_cases=9,
        reports=reports,
        runner='scripts/test-ufs-check10-r1.py',
        runner_sha256=sha('scripts/test-ufs-check10-r1.py'),
        new_cases_breakdown='3 inherited CHECK8 selfcheck + 3 inherited CHECK8 read_return + 3 new CHECK10 ret-witness',
        scope='Unicorn machine-code replay of the packaged observer; the new hook is executed for real from the packaged cave with three return-value/LR vectors. No QEMU, no device.'),
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
        'The hook sits on every _vn_rdwr return, so FB15/FB16/FB17 show the LAST return, not necessarily the one that precedes the stall. A blank FB15 is still conclusive; a populated one needs the phase/timeline context.',
        'draw silently skips when the framebuffer base in scratch is zero. CHECK8 proved the framebuffer live by f137 and FB12=A0000005 proved coarse_read_before could draw, so a blank FB15 is not expected to be a display-readiness artefact - but it is not a device proof either.',
        'This candidate does not test anything downstream of 0x769BF98 / bsd_init VFS_ROOT. A successful return only relocates the stall.',
        'The verdict depends on a full-length 60fps recording; end-state-only footage cannot separate a stall from slow progress.',
    ],
    readiness='Offline preparation complete. Requires an explicit recording/recovery confirmation before the fresh device preflight and the single fastboot boot.',
    qualification_phase_device_accessed=False,
    control_question='Did _vn_rdwr return at all, and if so with which w0 and to which x30 landing address?')

path = OUT / 'qualification.json'
assert not path.exists(), 'qualification already signed out'
path.write_text(json.dumps(q, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('signed out', path, hashlib.sha256(path.read_bytes()).hexdigest())
