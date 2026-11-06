"""PROBE61: expose six existing init/exec milestones, no new HEX or policy changes."""
import json,hashlib,struct,copy,argparse
from pathlib import Path
import root_progress_inputs as P
R=P.R
MARKERS=P.MARKERS
P55=P.P55
P57=P.P57
read=P.read
sha=P.sha
ref=P.ref
TESTS=P.TESTS|{'target-milestones','init-bridge','marker-map'}
BASE=R/'reports/kernel-entry-probe/2026-10-30-probe60-target-r1'
IDS={216,218,219,220,225,226}
def derive():
 import strategy_target_inputs as parent
 b=P.read(BASE/'build.json');raw=(R/b['candidate']['path']).read_bytes();assert hashlib.sha256(raw).hexdigest()==b['candidate']['sha256'];parent.verify_bytes(b,raw)
 out=bytearray(raw);selected=[];patches=[]
 for c in b['lean_observation']['changes']:
  use=(c['kind']=='skip-render' and c.get('invocation','').split(',')[0] in {'DENSE_ONCE '+str(i) for i in IDS}) or (c['kind']=='restore-native' and c.get('reason') in {'probe_dense_769d4e0','probe_dense_769ce3c','probe_dense_769cfa8'})
  if not use:continue
  at=c['file_offset'];assert out[at:at+4]==bytes.fromhex(c['after']);out[at:at+4]=bytes.fromhex(c['before']);selected.append(c)
  if c['kind']=='restore-native':patches.append(dict(va=c['va'],file_offset=at,before=c['after'],after=c['before'],reason=c['reason']))
 assert len(selected)==9 and len(patches)==3
 return b,bytes(out),patches,selected

def verify_bytes(b,raw):
 old,expected,patches,changes=derive();assert raw==expected and b['probe_revision']==61
 assert {c['function'] for c in changes if c['kind']=='skip-render'} <= {p['reason'] for p in b['patches']}
 assert b['init_bridge_observation']['changes']==changes and b['patches']==old['patches']+patches
 for key in ('read_flow','root_mount_diagnostic','pthread_startup','fscompression_startup','image4_compatibility','probe','target_observation'):assert b[key]==old[key]
 assert b['lean_observation']['changes']==[c for c in old['lean_observation']['changes'] if c not in changes]
 return True
def metadata(build):return P.metadata(build)
def validate(meta,kernel_sha):
 b=P.bound(meta['build']);proof=P.bound(meta['milestone-proof']);raw=(R/b['candidate']['path']).read_bytes();assert hashlib.sha256(raw).hexdigest()==kernel_sha==proof['candidate_sha256'];verify_bytes(b,raw)
 for item in proof['sources']:assert P.sha(R/item['path'])==item['sha256']==P.sha(R/item['archive'])
 assert set(proof['tests'])==TESTS
 assert proof['counts']['marker-map']==9 and proof['counts']['init-bridge']==24 and proof['counts']['target-milestones']==12 and proof['counts']['milestones']==48 and proof['counts']['bootstrap']==4 and proof['counts']['negative-controls']==4
 for name,item in proof['tests'].items():
  report=P.bound(item);assert report['candidate_sha256']==kernel_sha;checks=report.get('checks',report.get('cases'));assert checks and all(c['passed'] for c in checks);assert len(checks)==proof['counts'][name]
 assert P.sha(R/P.bound(proof['reproduce_build'])['candidate']['path'])==kernel_sha
 from nuwa_exec_detail_launch_context import API
 root=P.bound(meta['root-launch']);API.validate_report(root);assert root['candidate_sha256']==kernel_sha
 assert P.bound(meta['launch-context'])['components']['kernel']['sha256']==kernel_sha
 return b
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.work.exists() and not a.output.exists();a.work.mkdir(parents=True);a.output.parent.mkdir(parents=True,exist_ok=True)
 b,raw,patches,changes=derive();b=copy.deepcopy(b);path=a.work/'kernel-entry-probe.macho';path.write_bytes(raw);(a.work/'probe.S').write_bytes((R/'out/kernel-entry-probe-55-provenance-r3/probe.S').read_bytes());b['candidate']=dict(path=path.as_posix(),sha256=P.sha(path),bytes=len(raw));b['probe_revision']=61;b['patches']+=patches;b['init_bridge_observation']=dict(changes=changes,ids=sorted(IDS),scope='Init path to exec activation; cumulative unscoped marks, no request pairing or EL0 claim');b['lean_observation']['changes']=[c for c in b['lean_observation']['changes'] if c not in changes];verify_bytes(b,raw);a.output.write_text(json.dumps(b,indent=2));print(b['candidate'])
