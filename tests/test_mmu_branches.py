"""Offline negative checks: an older FD cannot masquerade as MMU diagnostics."""
import importlib.util
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('inspector', ROOT / 'scripts/ci/inspect-firmware-candidate.py')
inspector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inspector)
OLD = ROOT / 'out/firmware-ci/39943865806/nuwa-firmware-39943865806'
PACKAGE = ROOT / 'reports/mmu-branches/39958974666/package.json'
sys.path.insert(0, str(ROOT / 'scripts'))


class MmuDiagnosticGate(unittest.TestCase):
    def test_old_fd_rejected_even_with_mocked_new_profile_identity(self):
        # Only mock decoded metadata, never rewrite historical evidence.
        original = json.loads
        profile = original((ROOT / 'config/firmware-mmu-branches-profile.json').read_text())
        def decode(text, *args, **kwargs):
            value = original(text, *args, **kwargs)
            if isinstance(value, dict) and value.get('profile') == 'constructor-trace':
                value['profile'] = 'mmu-branches'
                value['recipe'] = profile['recipe']
            return value
        with patch.object(inspector.json, 'loads', side_effect=decode):
            with self.assertRaisesRegex(ValueError, 'MMU branch logs absent'):
                inspector.inspect(OLD, 'NuwaBootMemoryDxe', True, True, True, 'mmu-branches')

    def test_fresh_capture_confirmation(self):
        spec = importlib.util.spec_from_file_location('trial', ROOT / 'scripts/trial-v4-firmware.py')
        trial = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(trial)
        for value in (None, '', '  ', False):
            self.assertFalse(trial.capture_confirmed({'human_capture_confirmation': value}, 'MMU-BRANCHES-OFFLINE'))
        self.assertTrue(trial.capture_confirmed({'human_capture_confirmation': '已准备录像'}, 'MMU-BRANCHES-OFFLINE'))
        self.assertFalse(trial.capture_confirmed({'human_capture_confirmation': '已准备录像'}, 'CONSTRUCTOR-TRACE-OFFLINE'))
        self.assertTrue(trial.capture_confirmed({'human_capture_confirmation': '可以，启动前通知我'}, 'CONSTRUCTOR-TRACE-OFFLINE'))

    def test_baseline_checks_cannot_be_omitted(self):
        with self.assertRaisesRegex(ValueError, 'requires all baseline diagnostic checks'):
            inspector.inspect(OLD, 'NuwaBootMemoryDxe')

    @unittest.skipUnless(PACKAGE.exists(), 'Requires downloaded MMU diagnostic artifact')
    def test_container_padding_rejected_even_with_updated_hash(self):
        from sec_handoff_package import validate
        metadata = json.loads(PACKAGE.read_text())
        image = (ROOT / metadata['image_path']).resolve()
        changed = image.read_bytes()[:-1] + b'\x01'
        metadata['image_sha256'] = hashlib.sha256(changed).hexdigest()
        read_bytes, read_text = Path.read_bytes, Path.read_text
        def bytes_read(path):
            return changed if path.resolve() == image else read_bytes(path)
        def text_read(path, *args, **kwargs):
            return json.dumps(metadata) if path.resolve() == PACKAGE.resolve() else read_text(path, *args, **kwargs)
        with patch.object(Path, 'read_bytes', bytes_read), patch.object(Path, 'read_text', text_read):
            with self.assertRaisesRegex(ValueError, 'header/padding differs'):
                validate(PACKAGE)

    @unittest.skipUnless(PACKAGE.exists(), 'Requires downloaded MMU diagnostic artifact')
    def test_device_gates_refuse_before_subprocess(self):
        for script, args, message in (
            ('trial-v4-firmware.py', ['launch', '--evidence', str(ROOT / 'reports/mmu-gate-not-created.json')], 'fresh process-log/recovery preflight'),
            ('record-nuwa-trial-state.py', ['--output', str(ROOT / 'reports/mmu-gate-not-created.json')], 'Fresh user capture confirmation'),
        ):
            spec = importlib.util.spec_from_file_location('gate', ROOT / 'scripts' / script)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            with patch.object(sys, 'argv', [script, *args, '--package', str(PACKAGE)]):
                with patch.object(module.subprocess, 'run', side_effect=AssertionError('Device subprocess reached')):
                    with patch.object(module.subprocess, 'check_output', side_effect=AssertionError('Device subprocess reached')):
                        with self.assertRaisesRegex(ValueError, message):
                            module.main()


if __name__ == '__main__':
    unittest.main()
