#!/usr/bin/env python3
"""Narrow host-only negative checks for the derived AMNM profile."""
import copy
import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location('amnm_pack', Path(__file__).with_name('build-owner-amnm-observe.py'))
M = importlib.util.module_from_spec(spec); spec.loader.exec_module(M)
spec2 = importlib.util.spec_from_file_location('amnm_audit', Path(__file__).with_name('audit-owner-amnm-observe.py'))
A = importlib.util.module_from_spec(spec2); spec2.loader.exec_module(A)

def rejected(name, fn):
    try: fn()
    except (ValueError, AssertionError): print(name + ': rejected')
    else: raise AssertionError(name + ': accepted')

def main():
    kernel = M.KERNEL.read_bytes()
    adt = (M.PARENT/'adt-generation/final.adt').read_bytes()
    trust = (M.PARENT/'inputs/kernel.macho.trustcache').read_bytes()
    parent = (M.PARENT/'adt-generation/record.json').read_bytes()
    config = (M.PARENT/'extracted/EFI/UniXNU/unixnu.toml').read_bytes()
    A.check_parent_members(trust,config)
    rejected('changed parent trust',lambda:A.check_parent_members(trust[:-1]+bytes([trust[-1]^1]),config))
    rejected('changed parent config',lambda:A.check_parent_members(trust,config+b'\n'))
    rec = M.O.read_json(M.OUTPUT/'derived-record.json')
    M.validate_record(rec,kernel,adt,trust,parent)
    for field,value in [('profile','pmap-ret-continue-20261111-r1'),('type','schema2'),
                        ('parent_record_sha256','0'*64),('kernel_sha256','0'*64),
                        ('args',['-v','serial=3','extra'])]:
        bad=copy.deepcopy(rec); bad[field]=value
        rejected(field,lambda bad=bad:M.validate_record(bad,kernel,adt,trust,parent))
    rejected('changed ADT',lambda:M.validate_record(rec,kernel,adt[:-1]+bytes([adt[-1]^1]),trust,parent))
    stock=(M.O.ROOT/'.cache/stock/vendor_boot_b.img').read_bytes()
    outer=(M.OUTPUT/'vendor_boot.img').read_bytes(); fat=(M.OUTPUT/'payload.img').read_bytes()
    for name,offset in [('outer header',16),('outer ramdisk',4096)]:
        changed=bytearray(outer); changed[offset]^=1
        rejected(name,lambda changed=changed:M.V.compare(stock,bytes(changed),fat,len(stock)))
    report=M.O.read_json(M.OUTPUT/'report.json')
    for name, which in [('payload + report','fat'),('outer + report','outer')]:
        bad=copy.deepcopy(report)
        if which=='fat':
            changed=bytearray(fat); changed[4096]^=1; altered=bytes(changed)
            bad['fat_sha256']=M.O.sha(altered)
            rejected(name,lambda:A.check_outer(stock,outer,altered,bad,len(stock)))
        else:
            changed=bytearray(outer); changed[4096]^=1; altered=bytes(changed)
            bad['outer_sha256']=M.O.sha(altered)
            rejected(name,lambda:A.check_outer(stock,altered,fat,bad,len(stock)))
    root=Path('/root/nuwa-amnm-final-candidate-stage3-20261111')
    manifest=(root/'manifest.json').read_bytes(); audit=M.AUDIT.read_bytes()
    build_path=Path('/root/nuwa-amnm-stage3-native-20261111/build-result.json')
    build=build_path.read_bytes(); b=json.loads(build)
    map_bytes=Path(b['link_map']['path']).read_bytes()
    A.check_evidence(manifest,audit,build,map_bytes)
    altered_map=map_bytes+b'\n'; b['link_map']['sha256']=M.O.sha(altered_map)
    altered_build=json.dumps(b).encode()
    rejected('map + build result',lambda:A.check_evidence(manifest,audit,altered_build,altered_map))
    aud=json.loads(audit); aud['winner']['va']=hex(int(aud['winner']['va'],16)-8)
    aud['winner']['end']=hex(int(aud['winner']['end'],16)-8)
    altered_audit=json.dumps(aud).encode()
    rejected('audit in-DATA address',lambda:A.check_evidence(manifest,altered_audit,build,map_bytes))
    print('PASS original 8, 4 synchronized-mutation and 2 parent-member negatives (host only)')

if __name__ == '__main__': main()
