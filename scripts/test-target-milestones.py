import json,sys,importlib.util,gc
from pathlib import Path
R=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('target_t',R/'scripts/test-probe-transparency.py');T=importlib.util.module_from_spec(s);sys.modules[s.name]=T;s.loader.exec_module(T)
f=R/'reports/kernel-entry-probe/2026-10-30-probe60-target-r1';b=json.loads((f/'build.json').read_bytes());raw=(R/b['candidate']['path']).read_bytes();checks=[]
for p in b['patches']:
 if not p['reason'].startswith('probe_target_'):continue
 for flag,video in [(0,True),(1,True),(0,False),(4,True)]:
  c=dict(flag=flag,video=video,nzcv=0xa0000000,x0=T.STACK+0x2000,seed_simd=True);ref,expected,nwrites=T.machine(raw,b,p,c,True);c['native_pc']=expected['pc'];got,actual,writes=T.machine(raw,b,p,c);assert actual==expected,(p,actual,expected)
  for pos,n in nwrites:assert bytes(ref.mem_read(pos,n))==bytes(got.mem_read(pos,n))
  assert bytes(ref.mem_read(T.STACK+0x8000,0x8000))==bytes(got.mem_read(T.STACK+0x8000,0x8000))
  fb=[(pos,n) for pos,n in writes if T.FB<=pos<T.FB+0x1200000];assert bool(fb)==(flag==0 and video)
  assert all(T.framebuffer_write_in_bounds(pos,n,60,55) for pos,n in fb)
  checks.append(dict(name=p['reason']+str((flag,video)),passed=True));del ref,got;gc.collect()
with (f/'target-milestones.json').open('x') as z:json.dump(dict(candidate_sha256=b['candidate']['sha256'],checks=checks,scope='Native GPR/SIMD/NZCV/SP and memory differential; once/no-video guards; no hardware proof'),z,indent=2)
print('12 target contexts passed')
