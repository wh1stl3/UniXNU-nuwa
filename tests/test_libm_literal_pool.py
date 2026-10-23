"""Fail-closed regressions for the exact Libm constant-pool fingerprint."""
import sys
from pathlib import Path
import struct
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from native_prelink_inputs import inputs,tools,components

class LiteralPoolTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.profile,_,donor,selection=inputs()
  with tools(True) as (parser,emitter):
   cls.emitter=emitter
   parent,_,_=components(parser,donor,selection)
   cls.start=int(cls.profile['literal_pool']['start'],0)
   at=parser.backed_offset(parent,cls.start,1224,len(donor));cls.pool=donor[at:at+1224]
 def inventory(self,data):
  segment=dict(name='__TEXT_EXEC',va=self.start,size=len(data),filesize=len(data),fileoff=0)
  return self.emitter.instruction_inventory(data,[segment],{'com.apple.kec.Libm':dict(segments=[segment])})
 def test_exact_complete_pool_is_recognized(self):
  result=self.inventory(self.pool)
  self.assertEqual([dict(module='com.apple.kec.Libm',va=self.start,size=1224,sha256=self.profile['literal_pool']['sha256'])],result['known_inline_data'])
 def test_changed_byte_with_unchanged_prefix_is_rejected(self):
  data=bytearray(self.pool);data[100]^=1
  self.assertEqual(data[:16],self.pool[:16])
  with self.assertRaisesRegex(ValueError,'External PC-relative encoding'):self.inventory(bytes(data))
 def test_instruction_after_the_pool_is_not_exempted(self):
  data=self.pool+struct.pack('<I',0x94040000)
  with self.assertRaisesRegex(ValueError,'External PC-relative encoding'):self.inventory(data)
 def test_unknown_external_code_without_pool_is_rejected(self):
  with self.assertRaisesRegex(ValueError,'External PC-relative encoding'):self.inventory(struct.pack('<I',0x94040000))

if __name__=='__main__':unittest.main()
