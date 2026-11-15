#!/usr/bin/env python3
"""Bind AMNM outer evidence to the actual final image, map and r4 layout."""
import importlib.util
import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace

def load(name, filename):
    spec=importlib.util.spec_from_file_location(name,Path(__file__).with_name(filename))
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

M=load('amnm_package','build-owner-amnm-observe.py')
MANIFEST_SHA='640d5d9602b1aa5a5c438e4b190b829e8b6fe8494fb1e8ca2c879ce35028f53a'
VERIFIER_SHA='b316df8ab1a17c48a6b948aac8e4e5f2b4986b818959e96aedd0c5f9035d4109'
BUILD_SHA='04f1db2246b5ebe03a826c7751816bf3963f1ea8c097c4aaf2a21fa4bb2d8fca'
MAP_SHA='237499b08b36b4f0cb16465dbabd18cf0d949ce1243e6927d3561091996d00f9'
FAT_SHA='7074311dc2e2d3e0e71432b150a4bbef557625e27412a98b1464a7736f11c1fa'
OUTER_SHA='c5784135e3bb03e371808510dc0031fe3641782fd5fedf852fd7401783c0ddef'
TRUST_SHA='367e051548f9f0407fa9fe9d40007fa4e7c5ff27c45f5a7a30cedf344e24d98e'
CONFIG_SHA='7b2ac4be356c5b6070b887057aa734219e45b70767a6d6faf1307b712576e931'

def check_parent_members(trust, config):
    M.O.require(M.O.sha(trust)==TRUST_SHA and M.O.sha(config)==CONFIG_SHA,
                'AMNM parent trust/config hash mismatch')

def check_evidence(manifest_raw, audit_raw, build_raw, map_raw):
    for name, raw, expected in [('manifest',manifest_raw,MANIFEST_SHA),('verifier audit',audit_raw,VERIFIER_SHA),
                                ('build result',build_raw,BUILD_SHA),('native map',map_raw,MAP_SHA)]:
        M.O.require(M.O.sha(raw)==expected, 'AMNM frozen '+name+' hash mismatch')
    return json.loads(manifest_raw),json.loads(audit_raw),json.loads(build_raw)

def check_outer(stock, outer, payload, report, capacity):
    M.O.require(M.O.sha(payload)==FAT_SHA==report['fat_sha256'] and
                M.O.sha(outer)==OUTER_SHA==report['outer_sha256'], 'AMNM frozen output hash mismatch')
    extracted=M.V.parse(outer)['ramdisk']
    M.O.require(extracted==payload, 'AMNM outer ramdisk differs from FAT')
    return M.V.compare(stock,outer,payload,capacity)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args=parser.parse_args()
    o=M.OUTPUT
    report=M.O.read_json(o/'report.json')
    record=M.O.read_json(o/'derived-record.json')
    kernel=M.KERNEL.read_bytes(); adt=(M.PARENT/'adt-generation/final.adt').read_bytes()
    trust=(M.PARENT/'inputs/kernel.macho.trustcache').read_bytes()
    parent=(M.PARENT/'adt-generation/record.json').read_bytes()
    M.validate_record(record,kernel,adt,trust,parent)
    manifest_path=Path('/root/nuwa-amnm-final-candidate-stage3-20261111/manifest.json')
    build_path=Path('/root/nuwa-amnm-stage3-native-20261111/build-result.json')
    map_path=Path('/root/nuwa-amnm-stage3-native-20261111/nuwa/ios-16.7.16-20H392/nuwa_amnm/tree/build/nuwa-amnm-observer/native-link.map')
    map_raw=map_path.read_bytes()
    manifest,final_audit,build=check_evidence(manifest_path.read_bytes(),M.AUDIT.read_bytes(),build_path.read_bytes(),map_raw)
    M.O.require(manifest['candidate']['sha256']==final_audit['candidate']['sha256']==M.KERNEL_SHA and
                manifest['candidate']['bytes']==len(kernel), 'AMNM manifest/audit kernel mismatch')
    M.O.require(Path(build['link_map']['path'])==map_path and M.O.sha(map_raw)==build['link_map']['sha256'] and
                b'amnm-stage1-bindings.o' not in map_raw and b'amnm-stage2-bindings.o' in map_raw,
                'AMNM final map binding mismatch')
    M.O.require(M.O.sha((M.O.ROOT/'scripts/audit-amnm-final.py').read_bytes())==M.AUDIT_SHA,
                'AMNM audit source hash mismatch')
    source=M.O.git(M.BASE/'drivers/DarwinBoot','show', M.L.R4_COMMIT+':DarwinBootPkg/Driver/DarwinBoot.c')
    M.O.require(M.O.sha(source.replace(b'\r',b''))==M.L.R4_SOURCE_SHA, 'r4 source binding mismatch')
    base,end,segments=M.L.vm_layout(kernel)
    parent_record,token=M.O.load_record(M.PARENT/'adt-generation/record.json')
    tree=M.O.inspect_adt(adt,token)
    chosen=dict(M.O.find(tree,'/chosen')[1])
    layout=M.L.relative_layout(base,end,len(adt),len(trust),int.from_bytes(chosen['darwinboot-memory-size'],'little'))
    M.O.require(layout==report['relative_layout'] and base==report['kernel_vm_base'] and end==report['kernel_vm_end'],
                'AMNM layout mismatch')
    objects=[]
    for key in ('log','panic_text','winner'):
        item=final_audit[key]; lo=int(item['va'],16); hi=int(item['end'],16)
        M.O.require(base<=lo<hi<=end and hi-lo==item['bytes'] and
                    any(s['name']=='__DATA' and s['vmaddr']<=lo<hi<=s['vmaddr']+s['vmsize'] for s in segments),
                    'AMNM object outside root VM span')
        objects.append({'name':key,'va':hex(lo),'end':hex(hi),'relative_start':lo-base,'relative_end':hi-base})
    for item in manifest['changes']:
        for field in ('site','target'):
            va=int(item[field],16)
            M.O.require(any(s['vmaddr']<=va and va+4<=s['vmaddr']+s['filesize'] for s in segments),
                        'AMNM code outside file-backed load range')
    payload=(o/'payload.img').read_bytes(); outer=(o/'vendor_boot.img').read_bytes()
    ctx=M.C.validate_inputs(M.PARENT, M.O.ROOT/'.cache/stock/vendor_boot_b.img',
                            M.O.ROOT/'.cache/boot-stage12-v4-r4.img', M.LAYOUT)
    outer_comparison=check_outer(ctx.stock,outer,payload,report,ctx.partitions['vendor_boot_b']['bytes'])
    config_bytes=(M.PARENT/'extracted/EFI/UniXNU/unixnu.toml').read_bytes()
    check_parent_members(trust,config_bytes)
    expected={'Payloads/kernel.macho':kernel,'Payloads/kernel.macho.adt':adt,
              'Payloads/kernel.macho.trustcache':trust,'unixnu.toml':config_bytes}
    with tempfile.TemporaryDirectory(prefix='amnm-audit-r2-') as temporary:
        tmp=Path(temporary); fat_path=tmp/'outer-ramdisk.img'
        fat_path.write_bytes(M.V.parse(outer)['ramdisk'])
        extracted=tmp/'extract'; extracted.mkdir()
        command=['mcopy','-s','-i',str(fat_path),'::/EFI',str(extracted)]
        result=subprocess.run(command,capture_output=True,env=dict(os.environ,MTOOLS_SKIP_CHECK='1',TZ='UTC'))
        M.O.require(result.returncode==0, 'AMNM audit mcopy failed')
        fat_hashes=M.P.verify_extracted(extracted,expected,adt,ctx.record_path,
                    SimpleNamespace(board=ctx.board),'-v serial=3')
        M.O.require(fat_hashes==report['fat_hashes'], 'AMNM report FAT member hashes mismatch')
    evidence={'status':'self-checked','profile':M.PROFILE,'kernel_sha256':M.KERNEL_SHA,
              'parent_record_sha256':M.PARENT_SHA,'adt_sha256':M.ADT_SHA,
              'audit_script_sha256':M.AUDIT_SHA,'verifier_audit_sha256':M.O.sha(M.AUDIT.read_bytes()),
              'manifest_sha256':M.O.sha(manifest_path.read_bytes()),'native_map_sha256':M.O.sha(map_raw),
              'native_build_result_sha256':M.O.sha(build_path.read_bytes()),
              'fixed_r4_sha256':M.C.R4_SHA,'r4_source_commit':M.L.R4_COMMIT,
              'r4_source_sha256':M.L.R4_SOURCE_SHA,'kernel_vm_base':base,'kernel_vm_end':end,
              'relative_layout':layout,'objects':objects,'fat_sha256':report['fat_sha256'],
              'outer_sha256':report['outer_sha256'],'outer_comparison':outer_comparison,
              'fat_hashes':fat_hashes, 'extraction_command':command,
              'extraction_exit':result.returncode, 'device_release':False,
              'limitations':['VM relative layout only; actual window address not observed',
                             'No runtime mapping, screen, authentication or device result']}
    path=args.output or o/'amnm-provenance.json'
    M.O.require(not path.exists(),'AMNM provenance already exists')
    M.O.write_json(path,evidence)
    print(json.dumps(evidence,indent=2))

if __name__=='__main__': main()
