"""Offline CLI state/transport tests. No subprocess or physical device access."""
import argparse
import datetime as dt
import importlib.util
import json
from pathlib import Path
import tempfile
import subprocess
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('trial', ROOT / 'scripts/trial-retention-pair.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def run_case(case):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp).resolve()
        trial = root / 'trials/one'
        trial.mkdir(parents=True)
        ledger = root / 'ledger'
        media = root / 'media'
        media.mkdir()
        photograph = media / 'writer.jpg'
        photograph.write_bytes(b'fixture only')
        binding = {'qualification_sha256': 'q', 'images': m.HASHES}
        gate = dict(at=m.now(), **binding, device_token='target', launcher_sha256=m.sha(m.__file__))
        m.save_new(trial / 'preflight.json', gate)
        calls = []
        class Fake:
            def __init__(self, path): pass
            def fastboot(self, expected):
                calls.append('query')
                m.require(case != 'wrong-device', 'Device changed')
            def run(self, tool, argv):
                assert tool == 'fastboot' and argv[0] == 'boot'
                assert (ledger / (m.HASHES['reader'] + '.json')).exists(), 'Consumption must precede transport'
                calls.append('boot')
                if case == 'transport-failure':
                    raise RuntimeError('fixture timeout')
        writer = {'transport_accepted': case != 'writer-failed'}
        m.save_new(trial / 'writer-launch.json', writer)
        ledger.mkdir()
        m.save_new(ledger / (m.HASHES['writer'] + '.json'), {'trial': str(trial)})
        transition = dict(at=m.now(), trial=str(trial), writer_launch_sha256=m.sha(trial / 'writer-launch.json'),
                          writer_result='both-step08-status0-held1-expected-crc',
                          nonce='95c6d74733de9bac8c1feede69d98bdd', android_between=False, power_loss=False,
                          reset_steps='Observed physical reset into bootloader', capture_confirmation='fixture',
                          media=[dict(path=str(photograph), sha256=m.sha(photograph))])
        if case == 'stale': transition['at'] = (dt.datetime.now(dt.timezone.utc)-dt.timedelta(hours=1)).isoformat()
        if case == 'android-between': transition['android_between'] = True
        if case == 'power-loss': transition['power_loss'] = True
        if case == 'bad-nonce': transition['nonce'] = 'bad'
        if case == 'bad-media': transition['media'][0]['sha256'] = 'bad'
        if case == 'bad-writer-result': transition['writer_result'] = 'unknown'
        if case == 'wrong-trial': transition['trial'] = str(root)
        if case == 'no-media': transition['media'] = []
        if case == 'closed': m.save_new(trial / 'postcondition.json', {})
        if case == 'consumed': m.save_new(ledger / (m.HASHES['reader'] + '.json'), {})
        transition_path = root / 'input.json'
        m.save_new(transition_path, transition)
        real_sha = m.sha
        def digest(p):
            return m.HASHES['reader'] if Path(p).name == 'boot-retention.img' else real_sha(p)
        error = None
        with patch.multiple(m, TRIALS=root/'trials', LEDGER=ledger, MEDIA=media, Device=Fake), \
             patch.object(m, 'check', return_value=binding), patch.object(m, 'sha', side_effect=digest), \
             patch.object(m.subprocess, 'run', side_effect=AssertionError('Real subprocess forbidden')), \
             patch('sys.argv', ['trial', 'reader', '--trial', str(trial), '--transition', str(transition_path)]):
            try: m.main()
            except (ValueError, RuntimeError, FileExistsError) as e: error = type(e).__name__ + ': ' + str(e)
        if case in ('success', 'transport-failure'):
            assert calls == ['query', 'boot'], (case, calls, error)
            assert m.read(trial/'reader-launch.json')['transport_accepted'] == (case == 'success')
            assert (ledger/(m.HASHES['reader']+'.json')).exists()
            try:
                with patch.object(m, 'LEDGER', ledger): m.reserve('reader', trial)
            except FileExistsError: pass
            else: raise AssertionError('Resend allowed')
        else:
            assert error and 'boot' not in calls, (case, calls, error)
        return dict(case=case, passed=True, calls=calls, rejected=error)

def device_case(case):
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        hashes = {p: 'a'*64 for p in m.PARTS}
        def fake_run(argv, **kwargs):
            if argv == ['adb', 'devices']:
                value = 'List of devices attached\nfixture-serial\tdevice\n'
                if case in ('multiple', 'mixed'): value += 'other\tdevice\n'
            elif argv[-1] == 'getprop ro.product.device': value = 'other' if case == 'product' or (case == 'mixed' and argv[2] == 'other') else 'nuwa'
            elif 'compatible' in argv[-1]: value = 'nuwa kalama'
            elif argv[-1] == 'getprop sys.boot_completed': value = '0' if case == 'incomplete' else '1'
            elif argv[-1] == 'getprop ro.boot.slot_suffix': value = '_b' if case == 'slot' else '_a'
            elif 'sha256sum' in argv[-1]: value = '\n'.join(('b'*64 if case == 'hash' else v)+'  '+p for p,v in hashes.items())
            else: raise AssertionError('Unexpected command '+str(argv))
            return subprocess.CompletedProcess(argv, 0, value, '')
        error = None
        expected = 'wrong' if case == 'identity' else None
        with patch.object(m.subprocess, 'run', side_effect=fake_run):
            try: m.Device(folder).android({'partition_hashes': hashes}, expected)
            except ValueError as e: error = str(e)
        assert (error is None) == (case in ('success', 'mixed')), (case,error)
        assert all('fixture-serial' not in p.read_text() for p in folder.glob('*.json')), 'Serial leaked'
        return dict(case='android-'+case, passed=True, rejected=error)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', required=True, type=Path)
    a=p.parse_args()
    cases=['success','transport-failure','wrong-device','writer-failed','stale','android-between',
           'power-loss','bad-nonce','bad-media','bad-writer-result','wrong-trial','no-media','closed','consumed']
    results=[run_case(c) for c in cases]
    results += [device_case(c) for c in ['success','mixed','multiple','product','incomplete','slot','hash','identity']]
    m.save_new(a.output, dict(device_accessed=False, cases=results, launcher_sha256=m.sha(m.__file__)))
    print('PASS', len(results), 'offline state/transport cases; consumed-before-send and no resend')

if __name__=='__main__': main()
