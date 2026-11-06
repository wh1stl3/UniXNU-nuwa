"""Bind native TEXT lifecycle and post-init Image4 provider evidence."""
import argparse,hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parents[1];sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.output.exists()
base=R/'reports/desktop-readiness/2026-11-03-offline-mainline-r4';evidence=[];total=0
for report,script,count in [('mach-object-chain','test-native-mach-object-chain',4),('image4-service-chain','test-native-image4-service-chain',6),('image4-aes-callsite-final','audit-image4-aes-callsite',0),('image4-coverage-reuse-final','audit-image4-coverage-reuse',0)]:
 path=base/(report+'.json');r=json.loads(path.read_bytes());assert r['passed'] and r['kernel_sha256']=='c38fe9d4428467f9f3767408159f4d8327984fcaad2fbde175eca6ece93d313e'
 assert r['script_sha256']==sha(R/'scripts'/(script+'.py'))
 if count:assert len(r['cases'])==count
 total+=count;evidence.append(dict(path=str(path.relative_to(R)),sha256=sha(path),cases=count))
frozen=[]
for path,expected in [('out/ufs-check-5-r1-qualified/boot-ufs-check-5-r1.img','876d4b783fca141053479e44ee72f6d80a237611cf6d671353f1389b16a0d540'),('reports/ufs-check-5-r1/offline-qualification-final.json','27755b0de2082c258e5a14454b652d794de85f070f39a410d36c212a0db00fdb')]:
 assert sha(R/path)==expected;frozen.append(dict(path=path,sha256=expected))
source=Path('/mnt/d/Code/PortingiOSLegacy/common/sources/xnu-ios16-full');sources=[dict(path=str(source/f),sha256=sha(source/f)) for f in ('iokit/IOKit/IOService.h','iokit/Kernel/IOService.cpp','osfmk/vm/vm_map.c','osfmk/vm/vm_object.c','bsd/kern/mach_loader.c')]
result=dict(passed=True,native_cases=total,evidence=evidence,frozen=frozen,source_bindings=sources,
 findings=['TEXT control conversion, reference increment and native release on copy error executed','NULL pager selects anonymous mapping, not automatic invalid-object failure','Image4 service requests IOAESAccelerator with UINT64_MAX timeout before nonce gate release','nonce initializer statically closes the gate before persisted-seed lookup','no NativeAES implementation symbols or AES-named concrete personality identified in checked candidate tables; runtime presence remains unobserved','early Image4 init code/data unchanged from prior full-init model; reuse instead of repeating'],
 remaining=['native object copy/pager and successful map insertion','actual provider discovery/initialization and iOS16 AES ABI/key requirements','shared-cache framework dynamic IPC and Data metadata import'],
 scope='Offline instructions/static evidence only, explicit IO/UBC/locks/OS object/service/persistence fixtures. No device root cause, full VM success, new candidate, deployment or security-policy change.',script_sha256=sha(Path(__file__)))
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print('PASS',total,'native scenarios; historical early init reused; CHECK5 frozen')
