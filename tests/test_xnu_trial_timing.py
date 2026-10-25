"""Timing policy only; these tests issue no device commands."""
import importlib.util,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('trial',Path(__file__).resolve().parents[1]/'scripts/trial-v4-firmware.py')
T=importlib.util.module_from_spec(spec);spec.loader.exec_module(T)
class Timing(unittest.TestCase):
    def test_xnu_menu_is_manual_no_fixed_wait(self):
        self.assertEqual(T.observation_window(None,'XNU-FIRST-ENTRY-ANALYSIS'),0)
        self.assertEqual(T.observation_window(0,'XNU-FIRST-ENTRY-ANALYSIS'),0)
    def test_other_scopes_keep_prior_timing(self):
        for scope in (None,'FV-FILE-SHA-OFFLINE','SEC-HANDOFF-OFFLINE'):
            self.assertEqual(T.observation_window(None,scope),120)
            with self.assertRaises(ValueError):T.observation_window(0,scope)
    def test_bounds_and_explicit_window(self):
        self.assertEqual(T.observation_window(180,'XNU-FIRST-ENTRY-ANALYSIS'),180)
        for n in (-1,601):
            with self.assertRaises(ValueError):T.observation_window(n,'XNU-FIRST-ENTRY-ANALYSIS')
if __name__=='__main__':unittest.main()
