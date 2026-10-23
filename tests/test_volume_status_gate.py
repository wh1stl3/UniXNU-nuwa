"""Offline volume-status artifact and capture-gate regressions."""
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT/path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value

class VolumeStatusGate(unittest.TestCase):
    def test_old_publisher_rejected_even_if_profile_metadata_is_spoofed(self):
        inspector = module('volume_inspector', 'scripts/ci/inspect-firmware-candidate.py')
        profile = json.loads((ROOT/'config/firmware-volume-status-profile.json').read_text())
        old = ROOT/'out/firmware-ci/39973030321/nuwa-firmware-39973030321'
        decode = json.loads
        def changed(text, *args, **kwargs):
            value = decode(text, *args, **kwargs)
            if isinstance(value, dict) and value.get('profile') == 'hob-integrity':
                value['profile'] = 'volume-status'
                value['recipe'] = profile['recipe']
            return value
        with patch.object(inspector.json, 'loads', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'Volume status publisher markers absent'):
                inspector.inspect(old, 'NuwaBootMemoryDxe', True, True, True, 'volume-status')

    def test_new_scope_requires_capture_confirmation(self):
        trial = module('volume_trial', 'scripts/trial-v4-firmware.py')
        for text in (None, '', ' ', False):
            self.assertFalse(trial.capture_confirmed({'human_capture_confirmation': text}, 'VOLUME-STATUS-OFFLINE'))
        self.assertTrue(trial.capture_confirmed({'human_capture_confirmation': 'Recording ready'}, 'VOLUME-STATUS-OFFLINE'))

if __name__ == '__main__':
    unittest.main()
