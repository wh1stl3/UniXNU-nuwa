"""Regression checks for CI input provenance, using recorded real build inputs."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
def load(name):
    s=importlib.util.spec_from_file_location(name,ROOT/'scripts/ci'/name)
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

class Inputs(unittest.TestCase):
    def test_unselected_shadow_does_not_replace_reviewed_base(self):
        m=load('build-8796-source.py')
        item=dict(patch='same.patch',chosen='old/common/sources/UniXNU/patches/xnu/same.patch')
        self.assertEqual(m.selected_patch(Path('device'),Path('base'),item),Path('base/patches/xnu/same.patch'))

    def test_selected_device_candidate_remains_mandatory(self):
        m=load('build-8796-source.py')
        item=dict(patch='same.patch',chosen=r'old\device\patches\xnu-8796-candidates\same.patch')
        self.assertEqual(m.selected_patch(Path('device'),Path('base'),item),Path('device/patches/xnu-8796-candidates/same.patch'))

    def test_real_selected_sequence_matches_successful_ci(self):
        m=load('build-8796-source.py')
        patches,_,_=m.inputs(Path('D:/Code/UniXNU-integration'),'merged')
        ci=json.loads((ROOT/'out/upstream-kernel-40015845083-final/nuwa-8796-merged-40015845083/nuwa-8796-source/reports/build.json').read_bytes())
        self.assertEqual([dict(name=p.name,sha256=m.sha(p)) for p in patches],ci['patches'])

    def test_real_compile_record_keeps_private_and_abi_flags(self):
        h=load('audit-driver-archives.py')
        record=json.loads((ROOT/'out/kernel-ci/39793231214/nuwa-8796-source/reports/compile-records/iokit/DEVELOPMENT/IOPlatformExpert.cpo.json').read_text().strip().rstrip(','))
        command=h.driver_command(record,Path('/new/NativeRamBlock.cpp'),Path('/new/NativeRamBlock.o'),Path('/new/build'))
        original=record['arguments']
        for i,arg in enumerate(original):
            if arg.startswith(('-D','-target','-arch','-std=','-isysroot','-mkernel')):
                self.assertIn(arg,command)
                if arg in ('-D','-target','-arch','-isysroot'):
                    self.assertTrue(any(command[j:j+2]==original[i:i+2] for j in range(len(command)-1)))
        self.assertIn(str(Path('/new/NativeRamBlock.cpp')),command)
        self.assertNotIn('-fsyntax-only',command)
        self.assertNotIn('-S',command)

if __name__=='__main__':unittest.main(verbosity=2)
