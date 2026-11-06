"""PROBE60 three unscoped strategy target milestones, reusing retired slots."""
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
TESTS=P.TESTS|{'target-milestones'}
BASE=R/'reports/kernel-entry-probe/2026-10-30-probe59-root-progress-r1'
SITES=[('probe_cpu_base',0xfffffff005194248),('probe_arm_vm',0xfffffff005194278),('probe_pmap',0xfffffff005194290)]
def branch(a,b):
 d=b-a;assert d%4==0 and -(1<<27)<=d<(1<<27);return struct.pack('<I',0x14000000|((d//4)&0x3ffffff))
def derive():
 b=P.read(BASE/'build.json');raw=(R/b['candidate']['path']).read_bytes();assert hashlib.sha256(raw).hexdigest()==b['candidate']['sha256'];P.verify_bytes(b,raw)
 import importlib.util
 spec=importlib.util.spec_from_file_location('target_builder',R/'scripts/build-kernel-entry-probe.py');B=importlib.util.module_from_spec(spec);spec.loader.exec_module(B);m=B.macho(raw);out=bytearray(raw);patches=[];changes=[]
 old=P.read(P.P55/'build.json');sy=b['probe']['symbols']
 for label,site in SITES:
  assert not any(p.get('va')==hex(site) for p in b['patches'])
  assert any(c.get('reason')==label and c['kind']=='restore-native' for c in b['lean_observation']['changes'])
  start=int(sy[label],16);replay=int(sy[label+'_replay'],16);at=B.backed(m,site);word=raw[at:at+4]
  render=next(c for c in b['lean_observation']['changes'] if c.get('function')==label and c['kind']=='skip-render')
  edits=[(at,branch(site,start)),(render['file_offset'],bytes.fromhex(render['before'])),(B.backed(m,replay),word),(B.backed(m,replay+4),branch(replay+4,site+4))]
  for off,data in edits:
   changes.append(dict(file_offset=off,before=raw[off:off+4].hex(),after=data.hex()));out[off:off+4]=data
  patches.append(dict(va=hex(site),file_offset=at,before=word.hex(),after=branch(site,start).hex(),reason='probe_target_'+label))
 return b,bytes(out),patches,changes
def verify_bytes(b,raw):
 old,expected,patches,changes=derive();assert raw==expected and b['probe_revision']==60
 assert b['target_observation']['changes']==changes and b['patches']==old['patches']+patches
 for key in ('read_flow','root_mount_diagnostic','pthread_startup','fscompression_startup','image4_compatibility','probe','lean_observation'):assert b[key]==old[key]
 return True
def metadata(build):return P.metadata(build)
def validate(meta,kernel_sha):
 b=P.bound(meta['build']);proof=P.bound(meta['milestone-proof']);raw=(R/b['candidate']['path']).read_bytes();assert hashlib.sha256(raw).hexdigest()==kernel_sha==proof['candidate_sha256'];verify_bytes(b,raw)
 for item in proof['sources']:assert P.sha(R/item['path'])==item['sha256']==P.sha(R/item['archive'])
 assert set(proof['tests'])==P.TESTS|{'target-milestones'}
 assert proof['counts']['target-milestones']==12 and proof['counts']['milestones']==48 and proof['counts']['bootstrap']==4 and proof['counts']['negative-controls']==4
 for name,item in proof['tests'].items():
  report=P.bound(item);assert report['candidate_sha256']==kernel_sha;checks=report.get('checks',report.get('cases'));assert checks and all(c['passed'] for c in checks);assert len(checks)==proof['counts'][name]
 assert P.sha(R/P.bound(proof['reproduce_build'])['candidate']['path'])==kernel_sha
 from nuwa_exec_detail_launch_context import API
 root=P.bound(meta['root-launch']);API.validate_report(root);assert root['candidate_sha256']==kernel_sha
 assert P.bound(meta['launch-context'])['components']['kernel']['sha256']==kernel_sha
 return b
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.work.exists() and not a.output.exists();a.work.mkdir(parents=True);a.output.parent.mkdir(parents=True,exist_ok=True)
 b,raw,patches,changes=derive();b=copy.deepcopy(b);path=a.work/'kernel-entry-probe.macho';path.write_bytes(raw);b['candidate']=dict(path=path.as_posix(),sha256=P.sha(path),bytes=len(raw));b['probe_revision']=60;b['patches']+=patches;b['target_observation']=dict(changes=changes,scope='Unscoped once-only marks; not caller-specific paired invocation proof');(a.work/'probe.S').write_bytes((R/'out/kernel-entry-probe-55-provenance-r3/probe.S').read_bytes());verify_bytes(b,raw);a.output.write_text(json.dumps(b,indent=2));print(b['candidate'])
