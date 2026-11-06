"""Single-use paired RAM experiment. check is offline; other phases access devices."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import sys

ROOT = Path(__file__).resolve().parents[1]
QUAL = ROOT / 'reports/log-retention-pair/2026-10-29/pair2-qualification.json'
WORK = ROOT / 'out/retention-pair2-20261029-r1'
LEDGER = ROOT / 'reports/log-retention-pair/consumed'
TRIALS = ROOT / 'reports/log-retention-trial'
MEDIA = ROOT.parent / 'Media-nuwa/RETENTION2'
HASHES = {'writer': '047ec297a8118016d5c68f94073a9f0fac74a2a5c472a1ccc5ce26d70df3cbee',
          'reader': 'ae311b55c787e45b37b2251bfdc1b32f67c5453c3c000090265c94c8e41a66cc'}
PARTS = {'/dev/block/by-name/' + p for p in ('boot_a', 'vendor_boot_a', 'init_boot_a')}
ORIGINAL = Path('D:/Code/PortingiOSLegacy/nuwa/backups/recovery-20261020T121245314787Z/boot_a.img')

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))

def save_new(p, data):
    with Path(p).open('x', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())

def require(value, message):
    if not value:
        raise ValueError(message)

def check():
    q = read(QUAL)
    require(q['nonce'] == '20bf35fd4e54fb5c343e9a6bccb24c4f', 'Wrong pair nonce')
    require({p['role'] for p in q['packages']} == set(HASHES), 'Incomplete pair')
    for p in q['packages']:
        image = WORK / p['role'] / 'boot-retention.img'
        require(sha(image) == p['image_sha256'] == HASHES[p['role']], 'Image drift')
        require(image.stat().st_size == p['image_bytes'] == 70266880, 'Image size')
        for e in p['dependencies']:
            require(sha(e['path']) == e['sha256'], 'Dependency drift: ' + e['path'])
    for e in q['source_seal'] + q['files']:
        require(sha(e['path']) == e['sha256'], 'Sealed input drift: ' + e['path'])
    return {'qualification_sha256': sha(QUAL), 'images': HASHES}

def fresh(record, seconds=900):
    age = (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(record['at'])).total_seconds()
    require(0 <= age <= seconds, 'Stale preflight; use a new trial directory')

def baseline(p):
    b = read(p)
    require(b.get('android_boot_completed') == '1' and b.get('slot') == '_a'
            and b.get('three_partition_hashes_unchanged') is True, 'Invalid recovery baseline')
    require(set(b['partition_hashes']) == PARTS, 'Missing partition hashes')
    require(sha(ORIGINAL) == b['partition_hashes']['/dev/block/by-name/boot_a'], 'Recovery image mismatch')
    return b

class Device:
    def __init__(self, trial):
        self.trial = trial
        self.serial = None

    def run(self, tool, args, selected=True, timeout=60):
        argv = [tool] + (['-s', self.serial] if selected else []) + args
        stamp = time.time_ns()
        record = {'at': now(), 'argv': [s.replace(self.serial, '<selected-nuwa>') if self.serial else s for s in argv]}
        try:
            r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
            text = (r.stdout + r.stderr).replace('\0', '\n')
            record.update(exit_code=r.returncode, output=text.replace(self.serial, '<selected-nuwa>') if self.serial else '<inventory redacted>')
            require(r.returncode == 0, 'Command failed: ' + tool + ' ' + args[0])
            return text.strip()
        except Exception as e:
            record['error'] = type(e).__name__
            raise
        finally:
            save_new(self.trial / ('command-' + str(stamp) + '.json'), record)

    def select(self, tool, expected=None):
        text = self.run(tool, ['devices'], selected=False)
        rows = [r.split() for r in text.splitlines()]
        targets = [r[0] for r in rows if len(r) == 2 and r[1] == ('device' if tool == 'adb' else 'fastboot')]
        if expected is not None:
            targets = [s for s in targets if hashlib.sha256(s.encode()).hexdigest() == expected]
        elif tool == 'adb':
            matching = []
            for candidate in targets:
                self.serial = candidate
                if self.run('adb', ['exec-out', 'getprop ro.product.device']) == 'nuwa':
                    matching.append(candidate)
            targets = matching
        require(len(targets) == 1, 'Need exactly one matching nuwa device')
        self.serial = targets[0]
        token = hashlib.sha256(self.serial.encode()).hexdigest()
        require(expected is None or token == expected, 'Device changed')
        return token

    def android(self, b, expected=None):
        token = self.select('adb', expected)
        require(self.run('adb', ['exec-out', 'getprop ro.product.device']) == 'nuwa', 'Wrong Android product')
        identity = self.run('adb', ['exec-out', "su -c 'cat /sys/firmware/devicetree/base/model; cat /sys/firmware/devicetree/base/compatible'"])
        require('nuwa' in identity.lower() and 'kalama' in identity.lower(), 'Wrong board')
        require(self.run('adb', ['exec-out', 'getprop sys.boot_completed']) == '1', 'Android incomplete')
        require(self.run('adb', ['exec-out', 'getprop ro.boot.slot_suffix']) == '_a', 'Wrong slot')
        raw = self.run('adb', ['exec-out', "su -c 'sha256sum " + ' '.join(sorted(PARTS)) + "'"])
        hashes = {r.split()[1]: r.split()[0] for r in raw.splitlines()}
        require(hashes == b['partition_hashes'], 'Partition drift')
        return dict(device_token=token, android_boot_completed='1', slot='_a',
                    partition_hashes=hashes, three_partition_hashes_unchanged=True)

    def fastboot(self, expected):
        self.select('fastboot', expected)
        for key, value in [('product', 'nuwa'), ('unlocked', 'yes'), ('current-slot', 'a')]:
            result = self.run('fastboot', ['getvar', key])
            require(any(line.strip().removeprefix('(bootloader)').strip() == key + ': ' + value
                        for line in result.splitlines()), 'Unconfirmed fastboot ' + key)

def reserve(role, trial):
    LEDGER.mkdir(parents=True, exist_ok=True)
    save_new(LEDGER / (HASHES[role] + '.json'), {'at': now(), 'role': role,
             'trial': str(trial), 'image_sha256': HASHES[role], 'state': 'consumed before boot; never resend'})

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('phase', choices=['check', 'prepare', 'writer', 'reader', 'postcondition'])
    p.add_argument('--trial', type=Path)
    p.add_argument('--baseline', type=Path, help='Latest reviewed Android recovery postcondition')
    p.add_argument('--现场确认', dest='confirmation', help='Actual current user capture/physical recovery statement')
    p.add_argument('--transition', type=Path, help='Reviewed JSON recording actual writer result and reset path')
    a = p.parse_args()
    if a.phase == 'check':
        print(json.dumps(check(), indent=2))
        return
    require(a.trial is not None, '--trial required')
    trial = a.trial.resolve()
    require(trial.is_relative_to(TRIALS.resolve()) and trial != TRIALS.resolve(), 'Dedicated trial path required')
    if a.phase == 'prepare':
        binding = check()
        require(a.baseline is not None and a.confirmation and a.confirmation.strip(), 'Baseline and current human statement required')
        b = baseline(a.baseline)
        trial.mkdir(parents=True, exist_ok=False)
        for sub in ('original', 'derived'):
            (MEDIA / sub).mkdir(parents=True, exist_ok=True)
        result = Device(trial).android(b)
        save_new(trial / 'preflight.json', dict(at=now(), **binding, **result,
                 baseline_path=str(a.baseline.resolve()), baseline_sha256=sha(a.baseline),
                 confirmation=a.confirmation, launcher_sha256=sha(__file__)))
        return
    gate = read(trial / 'preflight.json')
    device = Device(trial)
    if a.phase == 'postcondition':
        # Recovery collection must remain possible even if candidate sources later change.
        result = device.android(gate, gate['device_token'])
        save_new(trial / 'postcondition.json', dict(at=now(), **result))
        return
    require(not (trial / 'postcondition.json').exists(), 'Trial already closed')
    require(gate['launcher_sha256'] == sha(__file__), 'Launcher changed since preflight')
    require(check() == {k: gate[k] for k in ('qualification_sha256', 'images')}, 'Qualification changed')
    require(not (LEDGER / (HASHES[a.phase] + '.json')).exists(), 'Candidate consumed; never resend')
    if a.phase == 'writer':
        fresh(gate)
        require(sha(gate['baseline_path']) == gate['baseline_sha256'], 'Baseline changed')
        device.android(gate, gate['device_token'])
        device.run('adb', ['reboot', 'bootloader'])
        # No extra reset. Enumeration retries never invoke boot or reboot.
        for attempt in range(30):
            try:
                device.select('fastboot', gate['device_token'])
                break
            except ValueError:
                if attempt == 29:
                    raise
                time.sleep(2)
    else:
        writer = read(trial / 'writer-launch.json')
        require(writer.get('transport_accepted') is True, 'No completed writer transport record')
        require(read(LEDGER / (HASHES['writer'] + '.json'))['trial'] == str(trial), 'Writer belongs to other trial')
        require(a.transition is not None, 'Actual transition evidence required')
        transition = read(a.transition)
        fresh(transition)
        require(transition.get('trial') == str(trial) and transition.get('writer_launch_sha256') == sha(trial / 'writer-launch.json'), 'Transition binding mismatch')
        require(transition.get('writer_result') == 'both-step08-status0-held1-expected-crc', 'Writer result not verified')
        require(transition.get('nonce') == '20bf35fd4e54fb5c343e9a6bccb24c4f', 'Observation nonce mismatch')
        require(transition.get('android_between') is False and transition.get('power_loss') is False,
                'Interrupted direct path: preserve evidence, do not launch reader')
        require(transition.get('reset_steps') and transition.get('capture_confirmation'), 'Missing actual reset/capture record')
        require(transition.get('media') and all(Path(e['path']).resolve().is_relative_to(MEDIA.resolve())
                and sha(e['path']) == e['sha256'] for e in transition['media']), 'Missing/bad local writer media')
    device.fastboot(gate['device_token'])
    require(sha(WORK / a.phase / 'boot-retention.img') == HASHES[a.phase], 'Image drift before boot')
    if a.phase == 'reader':
        save_new(trial / 'transition.json', transition)
    reserve(a.phase, trial)
    result = dict(at=now(), image_sha256=HASHES[a.phase], transport_accepted=False,
                  scope='Transport only; camera evidence required')
    try:
        device.run('fastboot', ['boot', str(WORK / a.phase / 'boot-retention.img')])
        result['transport_accepted'] = True
    finally:
        save_new(trial / (a.phase + '-launch.json'), result)

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] in ('prepare', 'writer', 'reader', 'postcondition'):
        lock = ROOT / 'reports/log-retention-pair/device-operation.lock'
        lock.mkdir(exist_ok=False)
        try:
            main()
        finally:
            lock.rmdir()
    else:
        main()
