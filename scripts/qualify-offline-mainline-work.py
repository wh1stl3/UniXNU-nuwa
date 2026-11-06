"""Bind the ordered offline loader/SystemOS/services/Data deliverables."""
import argparse,hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_bytes())
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report-dir',type=Path,required=True);a=p.parse_args();d=a.report_dir.resolve();output=d/'summary.json';assert not output.exists()
candidate=read(R/'reports/ufs-check-5-r1/candidate.json');q=read(R/candidate['qualification'])
assert sha(R/candidate['image_path'])==candidate['image_sha256']=='876d4b783fca141053479e44ee72f6d80a237611cf6d671353f1389b16a0d540'
for path,digest in q['sources'].items():assert sha(R/path)==digest,path
for path,digest in q['reused']['sources'].items():assert sha(R/path)==digest,path
reports={};counts={}
for name,count in [('native-loader-launchd-final.json',21),('native-loader-dyld-final.json',21),('nonce-handoff.json',6),('systemos-readiness.json',6),('service-failure-boundaries.json',4)]:
 r=read(d/name);assert r['passed'] and len(r['cases'])==count
 if 'kernel_sha256' in r:assert r['kernel_sha256']==candidate['kernel_sha256']
 reports[name]=sha(d/name);counts[name]=count
for name in ('core-consumers-final.json','data-readiness-qualified.json'):
 r=read(d/name);assert r['passed'];reports[name]=sha(d/name)
services=read(d/'core-consumers-final.json');data=read(d/'data-readiness-qualified.json')
assert services['mount_cleanup_complete'] and len(services['binaries'])==12 and len(services['jobs'])==10
assert len(services['client_edges'])==3 and len(services['listener_endpoints'])==4 and not services['unknown_endpoint_roles']
assert len(services['summary_omissions_corrected'])==5
assert data['directory_count']==161 and data['classification_counts']=={'conditional':25,'unknown':11}
assert not data['deployment_ready'] and not data['data_image_built']
for binary in services['binaries']:assert sha(R/binary['extracted'])==binary['sha256']
scripts=['test-native-loader-contracts.py','test-ignition-nonce-handoff.py','audit-systemos-integration-readiness.py','audit-core-service-consumers.py','refine-core-service-contracts.py','plan-data-service-readiness.py','inspect-service-code.py','test-service-failure-boundaries.py','qualify-offline-mainline-work.py']
sources={str(Path('scripts')/name):sha(R/'scripts'/name) for name in scripts}
source=Path('/mnt/d/Code/PortingiOSLegacy/common/sources/xnu-ios16-full/bsd/kern/mach_loader.c')
summary=dict(passed=True,stage='P2/S06 with S05 Data preparation',ordered_deliverables=['native Mach loader acceptance/error branches','SystemOS integration and nonce/Preboot contract','actual service callers and full launch conditions','Data provenance/metadata and consumer preparation'],
 reports=reports,machine_cases=sum(counts.values()),case_counts=counts,sources=sources,source_reference=dict(path=str(source),sha256=sha(source),role='mechanism reference; exact target instructions authoritative'),
 preserved_candidate=dict(path=candidate['image_path'],sha256=candidate['image_sha256'],kernel_sha256=candidate['kernel_sha256'],qualification_sha256=sha(R/candidate['qualification']),source_bindings_checked=len(q['sources'])+len(q['reused']['sources'])),
 explicit_fix='Offline service summaries now preserve hardware/variant/private launch conditions omitted by previous selected-field summary. No target code or configuration fix claimed.',
 scope='58 actual machine-code scenarios with explicit VM/AMFI/IO/scheduling/API boundaries; static standalone service callers, not complete dynamic/framework dependency graph. No full XNU/APFS, userland or desktop execution.',
 remaining=['VM mapping, authentic AMFI acceptance and scheduling require live evidence','nonce producer arrival and valid blob/boot-spec not proved','framework/Objective-C/dynamic IPC and path creation remain outside standalone analysis','APFS ACL/protection/keybag/importer and Data persistence not qualified'],
 public_references=['https://unixnu.com/porting/bring-up','https://github.com/apple-oss-distributions/xnu/blob/xnu-8796.141.3/bsd/kern/mach_loader.c','https://developer.apple.com/documentation/xpc/xpc_connection_mach_service_listener?language=objc'],
 device_accessed=False,candidate_changed=False,partition_writes=False,committed=False,pushed=False)
output.write_text(json.dumps(summary,indent=2)+'\n');print('PASS ordered offline work,',summary['machine_cases'],'machine scenarios; CHECK5 and qualification unchanged')
