"""Derive the three CHECK9 trial scripts from the reviewed CHECK8 templates.

Only the candidate identity, hashes, case counts and field-semantics gate are
changed. The device discipline (one nuwa, fresh getvar snapshot, exactly one
boot, no resend) is inherited verbatim.
"""
from pathlib import Path

ROOT = Path('D:/Code/PortingiOS/nuwa/UniXNU-nuwa')
SRC = ROOT/'reports/ufs-check-8-r1/trial-scripts'
DST = ROOT/'reports/ufs-check-9-r1/trial-scripts'
DST.mkdir(parents=True, exist_ok=True)
IMAGE8 = 'ff38f0b2fd8698833da93827d4cbc430a9fbe5cea0890d1c039576dc65024bb6'
IMAGE9 = '3bca1602a0bf0d03a41f5f721fa7bf5980c42318e4a5d657737e1c674c5f8b27'
KERNEL8 = 'db7540cc4501c0793f67c6db953f71b23867eca19eb3545f1f253c39b4b421ed'
KERNEL9 = '287a4e88499acc84bbb16d0b54139d835b6353282e7a3f12be5366c35d00a3c6'

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
    assert s.get('zero_draw') is True and s['framebuffer_writes_executed'] == 0
    assert s['draw_callsites_retained'] == 37, 'draw callsites must be retained'
    by_id = {f['field_id_decimal']: f for f in s['fields']}
    assert all(f['visible_in_check9'] is False for f in s['fields']), \\
        'zero-draw semantics violated: a field claims to be visible'
    assert by_id[10]['screen_label'] == 'FB0A' and by_id[16]['screen_label'] == 'FB10'
    assert 'blank' in s['screen_expectation']['f_region'].lower(), \\
        'blank F region must be the documented expectation'
    assert s['non_field_indicators']['centre_graphic'] == 'UniXNU logo (NOT the Apple logo)'
    assert len(s['non_field_indicators']['states']) == 4, 'RGB colour-block baseline required'

    # Single-variable guarantee, re-verified from the packaged bytes at the
    # gate: the whole kernel may differ from CHECK5 ONLY inside the draw body.
    import hashlib as _hl
    k9 = (ROOT / 'out/ufs-check-9-r1/kernel.macho').read_bytes()
    k5 = (ROOT / 'out/ufs-check-5-r1-qualified/kernel.macho').read_bytes()
    assert _hl.sha256(k9).hexdigest() == q['candidate']['kernel_sha256']
    lo, hi = q['observer']['single_variable']['diff_file_range']
    diff = [i for i, (x, y) in enumerate(zip(k9, k5)) if x != y]
    assert len(k9) == len(k5) and diff and all(lo <= i < hi for i in diff), \\
        'candidate is not a pure zero-draw control'
"""

OLD_CASES = """    assert sum(b.get('cases', 0) for b in t['reports'].values()) == 79, 'unexpected case count'
    assert t.get('total_cases') == 79 and t.get('inherited_cases') == 73 and t.get('new_cases') == 6
"""
NEW_CASES = """    assert sum(b.get('cases', 0) for b in t['reports'].values()) == 81, 'unexpected case count'
    assert t.get('total_cases') == 81 and t.get('inherited_cases') == 73 and t.get('new_cases') == 8
"""

names = {
 'check8-trial-preflight-20261104.py': 'check9-trial-preflight-20261104.py',
 'check8-trial-launch-20261104.py': 'check9-trial-launch-20261104.py',
 'check8-trial-postcondition-20261104.py': 'check9-trial-postcondition-20261104.py',
}
for old, new in names.items():
    text = (SRC/old).read_text(encoding='utf-8')
    text = text.replace('ufs-check-8-r1', 'ufs-check-9-r1')
    text = text.replace('UFS-CHECK-8-r1', 'UFS-CHECK-9-r1')
    text = text.replace('UFS-CHECK-8 r1', 'UFS-CHECK-9 r1')
    text = text.replace(IMAGE8, IMAGE9).replace(KERNEL8, KERNEL9)
    if old.startswith('check8-trial-preflight'):
        assert OLD_SEM in text, 'semantics gate anchor not found'
        assert OLD_CASES in text, 'case-count anchor not found'
        text = text.replace(OLD_SEM, NEW_SEM).replace(OLD_CASES, NEW_CASES)
    assert 'ufs-check-8' not in text and IMAGE8 not in text and KERNEL8 not in text, old
    (DST/new).write_text(text, encoding='utf-8')
    print('wrote', DST/new)
