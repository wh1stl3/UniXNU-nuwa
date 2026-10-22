"""Protect existing kernel outputs when reusing a real compiler argv for drivers."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('driver_audit', ROOT / 'scripts/ci/audit-driver-archives.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class DriverCommands(unittest.TestCase):
    def record(self):
        return {'directory': str(ROOT / 'out/argv-check'), 'file': 'IOPlatformExpert.cpp',
                'arguments': ['clang++', '-c', '-x', 'c++', 'IOPlatformExpert.cpp',
                              '-target', 'arm64-apple-ios16.0', '-DVALUE=two words',
                              '-o', 'IOPlatformExpert.cpo', '-MD', '-MF', 'original.d',
                              '-MT', 'original-target', '-MJ', 'original.cpo.json', '-MP']}

    def test_keeps_abi_and_does_not_overwrite_kernel_side_outputs(self):
        record = self.record()
        before = list(record['arguments'])
        source, obj = ROOT / 'out/driver source.cpp', ROOT / 'out/driver.o'
        result = audit.driver_command(record, source, obj, ROOT / 'out')
        for original in ('original.d', 'original.cpo.json', 'original-target', 'IOPlatformExpert.cpo'):
            self.assertNotIn(original, result)
        self.assertEqual(result[result.index('-o') + 1], str(obj))
        self.assertIn(str(source), result)
        self.assertIn('arm64-apple-ios16.0', result)
        self.assertIn('-DVALUE=two words', result)
        self.assertEqual(record['arguments'], before)

    def test_rejects_missing_or_duplicate_source(self):
        for count in (0, 2):
            record = self.record()
            record['arguments'].remove('IOPlatformExpert.cpp')
            record['arguments'] += ['IOPlatformExpert.cpp'] * count
            with self.assertRaises(ValueError):
                audit.driver_command(record, ROOT / 'out/driver.cpp', ROOT / 'out/driver.o', ROOT / 'out')

    def test_rejects_truncated_side_output_option(self):
        record = self.record()
        record['arguments'].append('-MJ')
        with self.assertRaises(ValueError):
            audit.driver_command(record, ROOT / 'out/driver.cpp', ROOT / 'out/driver.o', ROOT / 'out')


if __name__ == '__main__':
    unittest.main()
