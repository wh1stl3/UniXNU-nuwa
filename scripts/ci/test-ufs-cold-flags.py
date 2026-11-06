"""Regression against the real Apple objects from failed CI 41019713342."""
from pathlib import Path
import runpy, struct, unittest
ROOT=Path(__file__).resolve().parents[2]
M=runpy.run_path(str(ROOT/'scripts/build-ramblock-late-analysis.py'))
ART=ROOT/'out/ci-ramblock-link-41019713342/nuwa-8796-merged-41019713342/nuwa-8796-source/build/ramblock-archive'

class ColdFlags(unittest.TestCase):
    def setUp(self):
        self.before=(ART/'ufs-baseline.o').read_bytes()
        self.after=(ART/'NativeUfs.late.o').read_bytes()
        self.kw=dict(removed=set(M['inspect'](self.before)[0])&M['REMOVED'],init='__GLOBAL__sub_I_NativeUfs.cpp')
    def test_actual_loss_and_exact_metadata_restoration(self):
        with self.assertRaises(ValueError):M['verify'](self.before,self.after,**self.kw)
        fixed,names=M['restore_cold_flags'](self.before,self.after,**self.kw)
        self.assertEqual(len(names),20)
        changed=[i for i,(a,b) in enumerate(zip(self.after,fixed)) if a!=b]
        self.assertEqual(len(changed),20)
        self.assertTrue(all(self.after[i]==0 and fixed[i]==4 for i in changed))
        self.assertEqual(M['verify'](self.before,fixed,**self.kw),(10,2255))
    def test_no_second_change(self):
        fixed,_=M['restore_cold_flags'](self.before,self.after,**self.kw)
        again,names=M['restore_cold_flags'](self.before,fixed,**self.kw)
        self.assertEqual(again,fixed);self.assertEqual(names,[])
    def test_unreviewed_descriptor_rejected(self):
        fixed,_=M['restore_cold_flags'](self.before,self.after,**self.kw)
        index=next(i for i,(a,b) in enumerate(zip(self.after,fixed)) if a!=b)
        bad=self.after[:index]+b'\x01'+self.after[index+1:]
        with self.assertRaises(ValueError):M['restore_cold_flags'](self.before,bad,**self.kw)
    def test_actual_text_mutation_rejected(self):
        at=32;offset=None
        for _ in range(struct.unpack_from('<I',self.after,16)[0]):
            cmd,n=struct.unpack_from('<II',self.after,at)
            if cmd==0x19:
                for i in range(struct.unpack_from('<I',self.after,at+64)[0]):
                    sec=at+72+80*i
                    if self.after[sec:sec+16].split(b'\0')[0]==b'__text':offset=struct.unpack_from('<I',self.after,sec+48)[0]
            at+=n
        self.assertIsNotNone(offset)
        bad=self.after[:offset]+bytes([self.after[offset]^1])+self.after[offset+1:]
        with self.assertRaises(ValueError):M['restore_cold_flags'](self.before,bad,**self.kw)

if __name__=='__main__':unittest.main(verbosity=2)
