"""Bind the deeper iOS16 VM/Image4 results without requalifying a boot candidate."""
import argparse,hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parents[1]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.output.exists()
base=R/'reports/desktop-readiness/2026-11-03-offline-mainline-r3';evidence=[];total=0
for report,script,count in [('image4-policy-registration','test-native-image4-policy-registration',6),('image4-runtime-dispatch','test-native-image4-runtime-dispatch',2),('mach-vm-chain-final','test-native-mach-vm-chain',5),('image4-chosen-contract','test-native-image4-chosen-contract',5),('image4-initializer-table','audit-image4-initializer-table',0)]:
 path=base/(report+'.json');r=json.loads(path.read_bytes());assert r['passed']
 assert r['kernel_sha256']=='c38fe9d4428467f9f3767408159f4d8327984fcaad2fbde175eca6ece93d313e'
 assert r['script_sha256']==sha(R/'scripts'/(script+'.py'))
 if count:assert len(r['cases'])==count
 total+=count;evidence.append(dict(path=str(path.relative_to(R)),sha256=sha(path),cases=count))
frozen=[]
for path,expected in [('out/ufs-check-5-r1-qualified/boot-ufs-check-5-r1.img','876d4b783fca141053479e44ee72f6d80a237611cf6d671353f1389b16a0d540'),('reports/ufs-check-5-r1/offline-qualification-final.json','27755b0de2082c258e5a14454b652d794de85f070f39a410d36c212a0db00fdb')]:
 assert sha(R/path)==expected;frozen.append(dict(path=path,sha256=expected))
root=Path('/mnt/d/Code/PortingiOSLegacy/common/sources/xnu-ios16-full');sources=[]
for path in ('security/mac_base.c','security/mac_policy.h','osfmk/vm/vm_map.c','bsd/kern/mach_loader.c'):sources.append(dict(path=str(root/path),sha256=sha(root/path)))
result=dict(passed=True,native_cases=total,evidence=evidence,source_bindings=sources,frozen=frozen,
 corrected_claim='0xfffffff0046ee518 registers a MAC policy; both policy init callbacks are NULL. It is not evidence of context initialization.',
 established=['actual MAC list insertion/error propagation into Image4 panic','actual runtime section enumeration reaches pmap cs and /chosen lookup','shipped sha2-384 selector accepted, four mutated property cases panic','native PAGEZERO map-bound update and failure unwind executed before TEXT mapping'],
 remaining=['real IORegistry publication/provider initialization and authenticated context contents','TEXT/VM object mapping and complete load_machfile lifecycle','framework dynamic IPC and relative dirfd consumers','Data production metadata import and persistence'],
 scope='Unicorn native instructions plus static source/pointer binding, with explicit IORegistry/OSData/locks/IO/UBC fixtures. No QEMU boot, device execution, new target fix or new candidate.',script_sha256=sha(Path(__file__)))
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print('PASS',total,'new native scenarios and source bindings; frozen CHECK5 unchanged')
