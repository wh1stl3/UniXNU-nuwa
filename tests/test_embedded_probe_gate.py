"""The embedded diagnostic scope must reject old artifacts and empty capture."""
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]

def load(name,path):
 s=importlib.util.spec_from_file_location(name,ROOT/path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

class EmbeddedGate(unittest.TestCase):
 def test_old_fd_cannot_claim_embedded_profile(self):
  reader=load('embedded_reader','scripts/ci/inspect-firmware-candidate.py')
  profile=json.loads((ROOT/'config/firmware-embedded-probe-profile.json').read_text());decode=json.loads
  def fake(text,*a,**kw):
   value=decode(text,*a,**kw)
   if isinstance(value,dict) and value.get('profile')=='volume-status':value.update(profile='embedded-probe',recipe=profile['recipe'])
   return value
  with patch.object(reader.json,'loads',side_effect=fake):
   with self.assertRaisesRegex(ValueError,'NuwaEmbeddedVolumeDxe absent'):
    reader.inspect(ROOT/'out/firmware-ci/39985245383/nuwa-firmware-39985245383','NuwaBootMemoryDxe',True,True,True,'embedded-probe')
 def test_empty_capture_rejected(self):
  trial=load('embedded_trial','scripts/trial-v4-firmware.py')
  for value in (None,'','  ',False):self.assertFalse(trial.capture_confirmed({'human_capture_confirmation':value},'EMBEDDED-PROBE-OFFLINE'))

if __name__=='__main__':unittest.main()
