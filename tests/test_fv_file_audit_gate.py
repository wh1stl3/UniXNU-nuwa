"""An old FD cannot claim the new FV file-audit module."""
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]


class FvFileAuditGate(unittest.TestCase):
    def test_prior_fd_missing_fv_driver_is_refused(self):
        spec=importlib.util.spec_from_file_location('fv_inspector',ROOT/'scripts/ci/inspect-firmware-candidate.py')
        reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
        profile=json.loads((ROOT/'config/firmware-fv-file-audit-profile.json').read_text())
        decode=json.loads
        def spoof(text,*args,**kw):
            value=decode(text,*args,**kw)
            if isinstance(value,dict) and value.get('profile')=='upstream-merged':
                value.update(profile='fv-file-audit',recipe=profile['recipe'])
            return value
        with patch.object(reader.json,'loads',side_effect=spoof):
            with self.assertRaisesRegex(ValueError,'NuwaFileAuditDxe absent or duplicated'):
                reader.inspect(ROOT/'out/upstream-firmware-40014018074/nuwa-firmware-40014018074',
                               'NuwaBootMemoryDxe',True,True,True,'fv-file-audit')


if __name__=='__main__':unittest.main()
