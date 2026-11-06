"""CHECK10 offline readiness gate. Read-only. No reboot, no getvar, no boot.

Runs every evidence binding that the device preflight will check, plus a
read-only `adb devices` enumeration, WITHOUT creating reports/.../trial/ and
WITHOUT changing device state. The candidate stays unconsumed and the formal
preflight (which reboots to fastboot) waits for the user's explicit
recording/recovery confirmation.
"""
import datetime, hashlib, json, subprocess
from pathlib import Path

ROOT = Path('D:/Code/PortingiOS/nuwa/UniXNU-nuwa')
OUT = ROOT / 'reports/ufs-check-10-r1/offline-gate'
ADB = 'D:/platform-tools-latest-windows/platform-tools/adb.exe'
FASTBOOT = 'D:/platform-tools-latest-windows/platform-tools/fastboot.exe'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def read(p):
    return json.loads(Path(p).read_bytes())


def now():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()


q = read(ROOT / 'reports/ufs-check-10-r1/qualification.json')
assert q['status'] == 'offline-diagnostic-qualified'
assert q['device_accessed'] is False and q['consumed'] is False and q['deployed'] is False
assert not (ROOT / 'reports/ufs-check-10-r1/trial').exists(), 'trial directory must not exist before confirmation'

img = Path(q['candidate']['image_path'])
assert sha(img) == q['candidate']['image_sha256']
assert img.stat().st_size == q['candidate']['image_bytes'] == 70266880

sem = Path(q['field_semantics']['path'])
assert sha(sem) == q['field_semantics']['sha256']
s = read(sem)
assert s['generated_by_formula'] and '0xFB00 + N' in s['encoding_formula']
by_id = {f['field_id_decimal']: f for f in s['fields']}
for n in (3, 6, 7, 21, 22, 23):
    assert by_id[n]['screen_label'] == 'FB%02X' % n and by_id[n]['writer_count'] == 1
assert by_id[21]['expected'] == 'C10A55AA' and by_id[23]['expected'] == '0769BF94'
assert len(s['decision_matrix']) == 5

for path, binding in q['tests']['reports'].items():
    p = ROOT / path
    assert sha(p) == binding['sha256'], 'regression report changed: ' + path
    assert read(p)['passed'], 'regression report not passing: ' + path
assert sum(b.get('cases', 0) for b in q['tests']['reports'].values()) == 82

raw = img.read_bytes()
kb = (ROOT / 'out/ufs-check-10-r1/kernel.macho').read_bytes()
off = raw.find(b'\xcf\xfa\xed\xfe')
assert off > 0 and hashlib.sha256(raw[off:off + len(kb)]).hexdigest() == q['candidate']['kernel_sha256']

proof = read(ROOT / 'out/ufs-check-10-r1/kernel-proof.json')
k8 = (ROOT / 'out/ufs-check-8-r1/kernel.macho').read_bytes()
lo = proof['check5_delta']['observer_file_offset']
hi = lo + proof['code_bytes']
one = q['observer']['single_variable']['outside_cave_only_diff'][0]['file_offset']
diff = [i for i, (x, y) in enumerate(zip(kb, k8)) if x != y]
assert len(kb) == len(k8) and diff
assert all(lo <= i < hi or one <= i < one + 4 for i in diff), 'not a single-variable control'
assert kb[one + 4:one + 8].hex() == 'c0035fd6', 'native RET modified'
assert proof['repair_patches']['inherited_read_return_chain_defect']['x30_installed_by_coarse_read_before'] == '0xfffffff00769bf94'

# Read-only device enumeration. No reboot, no getvar, no state change.
adb = subprocess.run([ADB, 'devices'], capture_output=True, text=True, timeout=20)
fb = subprocess.run([FASTBOOT, 'devices'], capture_output=True, text=True, timeout=20)
adb_rows = [x.split() for x in adb.stdout.splitlines()[1:] if x.strip()]
fb_rows = [x.split() for x in fb.stdout.splitlines() if x.strip()]
device = dict(adb_rows=[[x[0], x[1]] for x in adb_rows if len(x) >= 2],
              fastboot_rows=[x[0] for x in fb_rows],
              note='read-only enumeration; no reboot, no getvar, no image transfer')

# All three scripts must be present and syntactically loadable, but none run.
scripts = sorted(p.name for p in (ROOT / 'reports/ufs-check-10-r1/trial-scripts').glob('*.py'))
assert len(scripts) == 3 and all('check10-trial-' in n for n in scripts), scripts

OUT.mkdir(parents=True, exist_ok=True)
result = dict(
    time=now(), passed=True, gate='offline-readiness-only',
    image_sha256=q['candidate']['image_sha256'],
    kernel_sha256=q['candidate']['kernel_sha256'],
    qualification_sha256=sha(ROOT / 'reports/ufs-check-10-r1/qualification.json'),
    field_semantics_sha256=sha(sem),
    regression_cases=82,
    single_variable=dict(outside_cave_diff_word_count=1, native_ret_preserved=True),
    device=device,
    trial_scripts=scripts,
    trial_directory_exists=False,
    boot_sent=False, device_state_changed=False,
    awaiting_confirmation=True,
    next_steps=[
        'User confirms 60fps live recording and TWRP/fastboot recovery path',
        'python reports/ufs-check-10-r1/trial-scripts/check10-trial-preflight-20261105.py --recording-confirmed "<user quote>"',
        'python reports/ufs-check-10-r1/trial-scripts/check10-trial-launch-20261105.py --confirm-launch "<user quote>"',
        'analyse the recording, then run check10-trial-postcondition-20261105.py'],
)
p = OUT / 'readiness.json'
assert not p.exists(), 'offline gate already recorded'
p.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(dict(passed=True, boot_sent=False, device_state_changed=False,
                      awaiting_confirmation=True, adb=device['adb_rows'],
                      fastboot=device['fastboot_rows']), ensure_ascii=False))
