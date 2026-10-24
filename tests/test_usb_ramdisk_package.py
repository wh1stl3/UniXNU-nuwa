"""Container corruption and device-action gates for the fixed USB candidate."""
import importlib.util
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import usb_ramdisk_package as package


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Containers(unittest.TestCase):
    def setUp(self):
        self.header = bytearray(4096)
        self.header[:8] = b'ANDROID!'
        struct.pack_into('<I', self.header, 20, 1584)
        struct.pack_into('<I', self.header, 40, 4)
        self.header[44:51] = b'console'
        self.kernel = b'K' * 4113
        self.ramdisk = b'R' * 9001
        self.image = package.compose(self.header, self.kernel, self.ramdisk, 3)

    def check(self, data, version=3):
        return package.inspect_container(data, self.header, self.kernel, self.ramdisk, version)

    def test_canonical_pair_changes_only_two_header_bytes(self):
        control = package.compose(self.header, self.kernel, self.ramdisk, 4)
        self.assertEqual([i for i in range(len(control)) if self.image[i] != control[i]], [20, 40])
        self.assertTrue(self.check(self.image)['original_cmdline_preserved'])

    def test_corruptions_are_refused(self):
        for label, offset in [('kernel', 4101), ('ramdisk', 4096+8192+1),
                              ('kernel_padding', 4096+4113), ('tail_padding', len(self.image)-1),
                              ('cmdline', 44), ('signature_or_padding', 1580),
                              ('header_size', 20), ('ramdisk_size', 12), ('version', 40)]:
            with self.subTest(label=label):
                broken = bytearray(self.image)
                broken[offset] ^= 1
                with self.assertRaises(ValueError):
                    self.check(broken)
        for broken in (self.image[:-1], self.image + bytes(4096)):
            with self.assertRaises(ValueError):
                self.check(broken)

    def test_unsupported_header_or_signed_input_refused(self):
        for version in (0, 1, 2, 5):
            with self.assertRaises(ValueError):
                package.compose(self.header, self.kernel, self.ramdisk, version)
        broken = bytearray(self.header)
        broken[1580] = 1
        with self.assertRaises(ValueError):
            package.compose(broken, self.kernel, self.ramdisk, 3)


class DeviceGates(unittest.TestCase):
    def test_empty_capture_refused(self):
        trial = load('usb_trial_capture', 'scripts/trial-v4-firmware.py')
        for value in (None, '', ' ', False):
            self.assertFalse(trial.capture_confirmed({'human_capture_confirmation': value}, package.APPROVAL))

    def test_v4_control_cannot_launch(self):
        trial = load('usb_trial_control', 'scripts/trial-v4-firmware.py')
        with patch.object(sys, 'argv', ['trial', 'launch', '--package',
             str(ROOT / f'reports/usb-ramdisk/{package.RUN}/package-v4.json'),
             '--evidence', str(ROOT / 'reports/usb-ramdisk/test-never-created.json')]), \
             patch.object(trial.subprocess, 'run', side_effect=AssertionError('Device subprocess forbidden')):
            with self.assertRaisesRegex(ValueError, 'outside the approved trial scope'):
                trial.main()

    def test_v3_without_preflight_cannot_launch(self):
        trial = load('usb_trial_preflight', 'scripts/trial-v4-firmware.py')
        with patch.object(sys, 'argv', ['trial', 'launch', '--package',
             str(ROOT / f'reports/usb-ramdisk/{package.RUN}/package-v3.json'),
             '--evidence', str(ROOT / 'reports/usb-ramdisk/test-never-created.json')]), \
             patch.object(trial.subprocess, 'run', side_effect=AssertionError('Device subprocess forbidden')):
            with self.assertRaisesRegex(ValueError, 'fresh process-log/recovery preflight required'):
                trial.main()

    def test_preflight_without_capture_refuses_before_adb(self):
        record = load('usb_record', 'scripts/record-nuwa-trial-state.py')
        with patch.object(sys, 'argv', ['record', '--package',
             str(ROOT / f'reports/usb-ramdisk/{package.RUN}/package-v3.json'),
             '--output', str(ROOT / 'reports/usb-ramdisk/test-never-created.json')]), \
             patch.object(record.subprocess, 'run', side_effect=AssertionError('Device subprocess forbidden')), \
             patch.object(record.subprocess, 'check_output', side_effect=AssertionError('Device enumeration forbidden')):
            with self.assertRaisesRegex(ValueError, 'capture confirmation required'):
                record.main()


if __name__ == '__main__':
    unittest.main()
