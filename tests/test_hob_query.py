"""A previous MMU FD must not pass the HOB diagnostic identity checks."""
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('hob_inspector', ROOT / 'scripts/ci/inspect-firmware-candidate.py')
inspector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inspector)


class HobQueryGate(unittest.TestCase):
    def test_previous_mmu_binary_rejected(self):
        original = json.loads
        profile = original((ROOT / 'config/firmware-hob-query-profile.json').read_text())
        def decode(text, *args, **kwargs):
            value = original(text, *args, **kwargs)
            if isinstance(value, dict) and value.get('profile') == 'mmu-branches':
                value['profile'] = 'hob-query'
                value['recipe'] = profile['recipe']
            return value
        artifact = ROOT / 'out/firmware-ci/39958974666/nuwa-firmware-39958974666'
        with patch.object(inspector.json, 'loads', side_effect=decode):
            with self.assertRaisesRegex(ValueError, 'HOB query logs absent'):
                inspector.inspect(artifact, 'NuwaBootMemoryDxe', True, True, True, 'hob-query')


if __name__ == '__main__':
    unittest.main()
