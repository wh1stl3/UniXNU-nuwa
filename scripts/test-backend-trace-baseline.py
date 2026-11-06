"""Test all re-enabled post-MMU marks against native and archived55 contexts."""
import argparse,importlib.util,json,sys,gc
from pathlib import Path
import lean_probe_inputs as V
import backend_trace_inputs as M
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
T=load('milestone_transparency',M.R/'scripts/test-probe-transparency.py')
E=load('milestone_cold',M.R/'scripts/test-kernel-entry-probe.py')
def save(p,v):
 with p.open('x',encoding='utf-8') as f:json.dump(v,f,indent=2);f.write('\n')
def main():
 a=argparse.ArgumentParser();a.add_argument('--build',type=Path,required=True);a.add_argument('--output',type=Path,required=True);a=a.parse_args()
 b=M.read(a.build);old=M.read(M.P55/'build.json');raw=(M.R/b['candidate']['path']).read_bytes();prior=(M.R/old['candidate']['path']).read_bytes();V.verify_bytes(b,raw);checks=[];cold=[]
 for occupied in (None,0x8c3000403):
  kwargs={} if occupied is None else dict(preoccupy=occupied)
  previous,r0,p0,t0,_=E.run(prior,old,**kwargs);actual,r1,p1,t1,_=E.run(raw,b,**kwargs)
  assert actual.get('stop')==previous.get('stop')=='before-sctlr' and not actual['bad_memory']
  assert r0==r1 and t0==t1 and actual['boot_args_unchanged']
  assert p1['256']==p0['256'] and p1['320']==p0['320'] and p1['288']==0
  cold.append(dict(name='cold-markers-native-and-geometry:'+str(occupied),passed=True))
 for mode in ('aarch64','default'):
  previous=E.run_continuous(prior,old,mode);actual=E.run_continuous(raw,b,mode)
  for key in ('error','reached','bad_memory','tcr','ttbr0','ttbr1','mair','sctlr','native_vbar_snapshot'):assert actual.get(key)==previous.get(key),(mode,key)
  if mode=='aarch64':assert actual['reached'] and actual['error'] is None
  for y in ('352','384'):assert actual['pixels'][y]==previous['pixels'][y]
  cold.append(dict(name='continuous-mmu-and-arm-init:'+mode,passed=True))
 for patch in b['patches']:
  if patch['reason'] not in M.MARKERS-{'probe_entry','probe_mmu','probe_mmu_on'}:continue
  for kind,flag,video,nzcv,x0 in [('first',0,True,0xa0000000,1),('repeat',1,True,0x50000000,0),('no-video',0,False,0xf0000000,1),('saturated',4,True,0,0)]:
   case=dict(flag=flag,video=video,nzcv=nzcv,x0=x0,seed_simd=True)
   ref,expected,nwrites=T.machine(raw,b,patch,case,True);case['native_pc']=expected['pc']
   got,actual,writes=T.machine(raw,b,patch,case)
   if patch['reason']=='probe_arm_init':expected['tpidr_el1']=actual['tpidr_el1']
   assert actual==expected,(patch['reason'],kind)
   for p,n in nwrites:assert bytes(ref.mem_read(p,n))==bytes(got.mem_read(p,n))
   assert bytes(ref.mem_read(T.STACK+0x8000,0x8000))==bytes(got.mem_read(T.STACK+0x8000,0x8000))
   fbwrites=[(p,n) for p,n in writes if T.FB<=p<T.FB+0x1200000]
   assert all(T.framebuffer_write_in_bounds(p,n,59,55) for p,n in fbwrites)
   if kind=='first':assert fbwrites,'Missing re-enabled marker'
   else:assert not fbwrites,'Once guard or no-video gate failed'
   checks.append(dict(name=patch['reason']+':'+kind,passed=True,framebuffer_writes=len(fbwrites)))
   del ref,got;gc.collect()
 assert len(checks)==48
 save(a.output,dict(candidate_sha256=b['candidate']['sha256'],checks=checks,limits='Unicorn single-thread contexts; not hardware timing/cache qualification'))
 save(a.output.parent/'bootstrap.json',dict(candidate_sha256=b['candidate']['sha256'],checks=cold,device_accessed=False))
 print('48 milestone and 4 continuous bootstrap checks passed')
if __name__=='__main__':main()
