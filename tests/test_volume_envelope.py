"""A previous HOB FD must not pass the volume transport identity checks."""
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('hob_inspector', ROOT / 'scripts/ci/inspect-firmware-candidate.py')
inspector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inspector)


class VolumeEnvelopeGate(unittest.TestCase):
    def test_previous_hob_binary_rejected(self):
        original = json.loads
        profile = original((ROOT / 'config/firmware-volume-envelope-profile.json').read_text())
        def decode(text, *args, **kwargs):
            value = original(text, *args, **kwargs)
            if isinstance(value, dict) and value.get('profile') == 'hob-query':
                value['profile'] = 'volume-envelope'
                value['recipe'] = profile['recipe']
            return value
        artifact = ROOT / 'out/firmware-ci/39962464061/nuwa-firmware-39962464061'
        with patch.object(inspector.json, 'loads', side_effect=decode):
            with self.assertRaisesRegex(ValueError, 'Volume envelope publisher markers absent'):
                inspector.inspect(artifact, 'NuwaBootMemoryDxe', True, True, True, 'volume-envelope')


if __name__ == '__main__':
    unittest.main()
