"""Reject unsafe relink inputs using the successful private build's real argv."""
import importlib.util,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
s=importlib.util.spec_from_file_location('ramlink',ROOT/'scripts/ci/build-ramblock-kernel.py')
M=importlib.util.module_from_spec(s);s.loader.exec_module(M)
CI=ROOT/'out/ci-ramblock-40870837215/nuwa-8796-merged-40870837215/nuwa-8796-source'

class LinkInputs(unittest.TestCase):
    def setUp(self):
        self.work=Path('/nuwa-test')
        self.original=json.loads((CI/'reports/kernel-make-command.json').read_bytes())
        self.original=[('OBJROOT='+str(self.work/'build/xnu/ios-obj')) if v.startswith('OBJROOT=') else v for v in self.original]
        self.archives=[self.work/'build'/n for n in ('cpu.a','platform.a','ramblock.a','bindings.a')]
    def test_only_reviewed_three_object_flags_change(self):
        result=M.link_command(self.original,self.work,self.archives)
        changes=[(a,b) for a,b in zip(self.original,result) if a!=b]
        self.assertEqual({a.split('=')[0] for a,b in changes},{'KernelConfigTables.cpo_CFLAGS_ADD','IOKitBSDInit.cpo_CFLAGS_ADD','bsd_init.o_CFLAGS_ADD'})
        for a,b in changes:self.assertTrue(b.startswith(a))
        self.assertEqual(next(v for v in self.original if v.startswith('kern_exec.o_')),next(v for v in result if v.startswith('kern_exec.o_')))
        self.assertFalse(any('undefined' in v for v in result))
        self.assertEqual(len(result),len(self.original)+2)
    def test_reject_existing_archive_override(self):
        with self.assertRaises(ValueError):M.link_command(self.original+['LD_KERNEL_ARCHIVES=bad'],self.work,self.archives)
    def test_reject_external_archive(self):
        with self.assertRaises(ValueError):M.link_command(self.original,self.work,self.archives[:3]+[Path('/unreviewed.a')])
    def test_reject_conflicting_feature_definition(self):
        original=[v+' -DXNU_NATIVE_RAM_BLOCK=0' if v.startswith('IOKitBSDInit.cpo_CFLAGS_ADD=') else v for v in self.original]
        with self.assertRaises(ValueError):M.link_command(original,self.work,self.archives)
    def test_reject_missing_personality_flags(self):
        with self.assertRaises(ValueError):M.link_command([v for v in self.original if not v.startswith('KernelConfigTables.cpo_CFLAGS_ADD=')],self.work,self.archives)
    def test_actual_kernel_parser(self):
        raw=(CI/'build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/mach.development.bcm2837.unstripped').read_bytes()
        sy,segments=M.symbols(raw)
        self.assertIn('_IOKitBSDInit',sy);self.assertIn('__ZN6OSKext22loadKextWithIdentifierEPKcbbhhP7OSArray',sy)
        self.assertNotIn('_native_ramblock_register_late',sy)
        self.assertFalse([n for n,v in sy.items() if v['kind']&14==0])
        with self.assertRaises(ValueError):M.symbols(b'BAD!'+raw[4:])

if __name__=='__main__':unittest.main(verbosity=2)
