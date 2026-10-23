"""Audit trial rejects an old FV and missing per-trial capture."""
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
 s=importlib.util.spec_from_file_location(name,ROOT/path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class BootAuditGate(unittest.TestCase):
 def test_old_fv_cannot_claim_audit_profile(self):
  reader=load('audit_reader','scripts/ci/inspect-firmware-candidate.py')
  profile=json.loads((ROOT/'config/firmware-boot-input-audit-profile.json').read_text());decode=json.loads
  def fake(text,*a,**kw):
   value=decode(text,*a,**kw)
   if isinstance(value,dict) and value.get('profile')=='embedded-probe':value.update(profile='boot-input-audit',recipe=profile['recipe'])
   return value
  with patch.object(reader.json,'loads',side_effect=fake):
   with self.assertRaisesRegex(ValueError,'NuwaBootAuditDxe absent'):
    reader.inspect(ROOT/'out/firmware-ci/39988591973/nuwa-firmware-39988591973','NuwaBootMemoryDxe',True,True,True,'boot-input-audit')
 def test_empty_capture_rejected(self):
  trial=load('audit_trial','scripts/trial-v4-firmware.py')
  for value in (None,'','  ',False):self.assertFalse(trial.capture_confirmed({'human_capture_confirmation':value},'BOOT-INPUT-AUDIT-OFFLINE'))
if __name__=='__main__':unittest.main()
