"""No device subprocess is permitted when file-audit inputs or gates are invalid."""
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import file_audit_package as package


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


class FileAuditGate(unittest.TestCase):
    def test_package_preserves_data_only_identity(self):
        report=package.validate(package.REPORT)
        self.assertTrue(report['xnu_included'])
        self.assertTrue(report['analytical_macho_data_only'])
        self.assertFalse(report['xnu_boot_entry'])
        self.assertFalse(report['kernel_execution_enabled'])

    def test_metadata_cannot_enable_kernel_entry(self):
        read=Path.read_text
        for key in ('kernel_execution_enabled','xnu_boot_entry'):
            def changed(path,*a,**kw):
                text=read(path,*a,**kw)
                if path==package.REPORT:
                    value=json.loads(text);value[key]=True;return json.dumps(value)
                return text
            with self.subTest(key=key),patch.object(Path,'read_text',changed):
                with self.assertRaisesRegex(ValueError,'metadata or complete container changed'):
                    package.validate(package.REPORT)

    def test_missing_preflight_blocks_launch_before_device(self):
        trial=module('file_trial','scripts/trial-v4-firmware.py')
        with patch.object(sys,'argv',['trial','launch','--package',str(package.REPORT),'--evidence',str(ROOT/'reports/file-read-audit/never-created.json')]), \
             patch.object(trial.subprocess,'run',side_effect=AssertionError('Device operation forbidden')):
            with self.assertRaisesRegex(ValueError,'fresh process-log/recovery preflight required'):
                trial.main()

    def test_missing_capture_blocks_preflight_before_enumeration(self):
        record=module('file_record','scripts/record-nuwa-trial-state.py')
        with patch.object(sys,'argv',['record','--package',str(package.REPORT),'--output',str(ROOT/'reports/file-read-audit/never-created.json')]), \
             patch.object(record.subprocess,'run',side_effect=AssertionError('Device operation forbidden')), \
             patch.object(record.subprocess,'check_output',side_effect=AssertionError('Device enumeration forbidden')):
            with self.assertRaisesRegex(ValueError,'capture confirmation required'):
                record.main()

    def test_empty_capture_rejected(self):
        trial=module('file_capture','scripts/trial-v4-firmware.py')
        for value in (None,'',' ',False):
            self.assertFalse(trial.capture_confirmed({'human_capture_confirmation':value},package.APPROVAL))


if __name__=='__main__':unittest.main()
