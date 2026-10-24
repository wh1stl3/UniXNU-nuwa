"""An old FD cannot claim the new FV file-audit module."""
import importlib.util
import json
import struct
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import fv_file_audit_package as package


class FvFileAuditGate(unittest.TestCase):
    package_path=ROOT/'reports/fv-file-audit/40078257763/package.json'

    def module(self,name,path):
        spec=importlib.util.spec_from_file_location(name,ROOT/path)
        value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value

    def test_empty_capture_refused_for_new_scope(self):
        trial=self.module('fv_capture_trial','scripts/trial-v4-firmware.py')
        for value in (None,'',' ',False):
            self.assertFalse(trial.capture_confirmed({'human_capture_confirmation':value},package.APPROVAL))

    def test_new_scope_requires_fresh_preflight_before_device(self):
        trial=self.module('fv_trial','scripts/trial-v4-firmware.py')
        with patch.object(sys,'argv',['trial','launch','--package',str(self.package_path),'--evidence',str(ROOT/'reports/fv-file-audit/never-created.json')]), \
             patch.object(trial.subprocess,'run',side_effect=AssertionError('Device operation forbidden')):
            with self.assertRaisesRegex(ValueError,'fresh process-log/recovery preflight required'):
                trial.main()

    def test_new_scope_requires_capture_before_adb(self):
        record=self.module('fv_record','scripts/record-nuwa-trial-state.py')
        with patch.object(sys,'argv',['record','--package',str(self.package_path),'--output',str(ROOT/'reports/fv-file-audit/never-created.json')]), \
             patch.object(record.subprocess,'run',side_effect=AssertionError('Device operation forbidden')), \
             patch.object(record.subprocess,'check_output',side_effect=AssertionError('Device enumeration forbidden')):
            with self.assertRaisesRegex(ValueError,'capture confirmation required'):
                record.main()

    def test_package_cannot_add_external_application(self):
        original=Path.read_text
        def change(path,*args,**kwargs):
            text=original(path,*args,**kwargs)
            if path==self.package_path:
                value=json.loads(text);value['external_efi_application_in_payload']=True;return json.dumps(value)
            return text
        with patch.object(Path,'read_text',change):
            with self.assertRaisesRegex(ValueError,'package or data-only metadata changed'):
                package.validate(self.package_path)

    def reader(self):
        spec=importlib.util.spec_from_file_location('fv_crypto_inspector',ROOT/'scripts/ci/inspect-firmware-candidate.py')
        reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader);return reader

    def crypto_inputs(self):
        artifact=ROOT/'out/firmware-ci/40078257763/nuwa-firmware-40078257763'
        return next(artifact.rglob('NuwaFileAuditDxe.efi')).read_bytes(),next(artifact.rglob('NuwaFileAuditDxe.map')).read_text()

    def test_optimized_ready_calls_real_sha_compression(self):
        reader=self.reader();data,mapping=self.crypto_inputs()
        result=reader.fv_sha_linkage(data,mapping)
        self.assertEqual(len(result['direct_call_sites']),4)

    def test_removed_sha_calls_are_refused(self):
        reader=self.reader();data,mapping=self.crypto_inputs()
        result=reader.fv_sha_linkage(data,mapping);changed=bytearray(data)
        header,=struct.unpack_from('<I',data,60)
        count,=struct.unpack_from('<H',data,header+6)
        optsize,=struct.unpack_from('<H',data,header+20)
        sections=[struct.unpack_from('<4I',data,header+24+optsize+40*i+8) for i in range(count)]
        for site in result['direct_call_sites']:
            rva=int(site,16);s=next(s for s in sections if s[1]<=rva<s[1]+s[2]);at=s[3]+rva-s[1]
            struct.pack_into('<I',changed,at,0xd503201f)
        with self.assertRaisesRegex(ValueError,'does not call'):
            reader.fv_sha_linkage(bytes(changed),mapping)

    def test_stub_compression_body_is_refused(self):
        reader=self.reader();data,mapping=self.crypto_inputs()
        result=reader.fv_sha_linkage(data,mapping);end=int(result['sha_block_rva'],16)+4
        with self.assertRaisesRegex(ValueError,'nontrivial SHA'):
            reader.fv_sha_linkage(data,mapping+f'\n{end:08x} 00000000 0 injected_stub_end\n')

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
