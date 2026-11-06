"""Derive the three CHECK10 trial scripts from the reviewed CHECK8 templates.

Only candidate identity, hashes, case counts and the field-semantics gate are
changed. The device discipline (one nuwa, a fresh getvar snapshot, exactly one
boot, no resend) is inherited verbatim. No script is executed here.
"""
from pathlib import Path

ROOT = Path('D:/Code/PortingiOS/nuwa/UniXNU-nuwa')
SRC = ROOT / 'reports/ufs-check-8-r1/trial-scripts'
DST = ROOT / 'reports/ufs-check-10-r1/trial-scripts'
DST.mkdir(parents=True, exist_ok=True)
IMAGE8 = 'ff38f0b2fd8698833da93827d4cbc430a9fbe5cea0890d1c039576dc65024bb6'
KERNEL8 = 'db7540cc4501c0793f67c6db953f71b23867eca19eb3545f1f253c39b4b421ed'
IMAGE10 = '6b93b92bc26392e3b90ab2bc52000e5d75a4d3d96010ca5b0f89ace544dbcc26'
KERNEL10 = 'da23791bdecc5b4381c76114b3f9f1275719aef4f34307657841e5e22fbf4b28'

OLD_SEM = """    s = read(sem)
    assert s.get('generated_by_formula') is True and '0xFB00 + N' in s.get('encoding_formula', ''), \\
        'field semantics table must be generated from the 0xFB00+N formula'
    by_id = {f['field_id_decimal']: f for f in s['fields']}
    for n in (3, 6, 7):
        assert by_id[n]['screen_label'] == 'FB%02X' % n
        assert by_id[n]['writer_count'] == 1, 'field ID %d has colliding writers' % n
    assert by_id[10]['screen_label'] == 'FB0A' and by_id[16]['screen_label'] == 'FB10'
"""

NEW_SEM = """    s = read(sem)
    assert s.get('generated_by_formula') is True and '0xFB00 + N' in s.get('encoding_formula', ''), \\
        'field semantics table must be generated from the 0xFB00+N formula'
    by_id = {f['field_id_decimal']: f for f in s['fields']}
    for n in (3, 6, 7, 21, 22, 23):
        assert by_id[n]['screen_label'] == 'FB%02X' % n
        assert by_id[n]['writer_count'] == 1, 'field ID %d has colliding writers' % n
    assert by_id[21]['expected'] == 'C10A55AA', 'RET arrival magic changed'
    assert by_id[23]['expected'] == '0769BF94', 'expected x30 landing address changed'
    assert by_id[10]['screen_label'] == 'FB0A' and by_id[16]['screen_label'] == 'FB10'
    assert s['check8_reassessment']['site'] == '0xfffffff00769bfa4'
    assert s['single_variable']['outside_cave_diff_word_count'] == 1
    assert len(s['decision_matrix']) == 5, 'RET verdict matrix required'

    # Single-variable guarantee, re-verified from the packaged bytes at the
    # gate: outside the cave, CHECK10 may differ from CHECK8 by one word only.
    import hashlib as _hl
    k10 = (ROOT / 'out/ufs-check-10-r1/kernel.macho').read_bytes()
    k8 = (ROOT / 'out/ufs-check-8-r1/kernel.macho').read_bytes()
    pr = read(ROOT / 'out/ufs-check-10-r1/kernel-proof.json')
    assert _hl.sha256(k10).hexdigest() == q['candidate']['kernel_sha256']
    lo = pr['check5_delta']['observer_file_offset']
    hi = lo + pr['code_bytes']
    one = q['observer']['single_variable']['outside_cave_only_diff'][0]['file_offset']
    diff = [i for i, (x, y) in enumerate(zip(k10, k8)) if x != y]
    assert len(k10) == len(k8) and diff and \\
        all(lo <= i < hi or one <= i < one + 4 for i in diff), \\
        'candidate is not a single-variable control against CHECK8'
    assert k10[one + 4:one + 8].hex() == 'c0035fd6', 'native RET was modified'
"""

OLD_CASES = """    assert sum(b.get('cases', 0) for b in t['reports'].values()) == 79, 'unexpected case count'
    assert t.get('total_cases') == 79 and t.get('inherited_cases') == 73 and t.get('new_cases') == 6
"""
NEW_CASES = """    assert sum(b.get('cases', 0) for b in t['reports'].values()) == 82, 'unexpected case count'
    assert t.get('total_cases') == 82 and t.get('inherited_cases') == 73 and t.get('new_cases') == 9
"""

names = {
    'check8-trial-preflight-20261104.py': 'check10-trial-preflight-20261105.py',
    'check8-trial-launch-20261104.py': 'check10-trial-launch-20261105.py',
    'check8-trial-postcondition-20261104.py': 'check10-trial-postcondition-20261105.py',
}
for old, new in names.items():
    text = (SRC / old).read_text(encoding='utf-8')
    text = text.replace('ufs-check-8-r1', 'ufs-check-10-r1')
    text = text.replace('UFS-CHECK-8-r1', 'UFS-CHECK-10-r1')
    text = text.replace('UFS-CHECK-8 r1', 'UFS-CHECK-10 r1')
    text = text.replace(IMAGE8, IMAGE10).replace(KERNEL8, KERNEL10)
    if old.startswith('check8-trial-preflight'):
        assert OLD_SEM in text, 'semantics gate anchor not found'
        assert OLD_CASES in text, 'case-count anchor not found'
        text = text.replace(OLD_SEM, NEW_SEM).replace(OLD_CASES, NEW_CASES)
    # The preflight deliberately keeps ONE reference to the CHECK8 kernel as
    # the byte-level comparison baseline. No other CHECK8 residue is allowed.
    expected_refs = 1 if old.startswith('check8-trial-preflight') else 0
    assert text.count('ufs-check-8-r1') == expected_refs, (old, text.count('ufs-check-8-r1'))
    assert 'UFS-CHECK-8' not in text and IMAGE8 not in text and KERNEL8 not in text, old
    (DST / new).write_text(text, encoding='utf-8')
    print('wrote', DST / new)
