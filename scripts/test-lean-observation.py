"""Compare lean scopes to sealed PROBE55 and to displaced native instructions."""
import argparse,gc,importlib.util,json,sys
from pathlib import Path
R=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('lean_flow',R/'scripts/test-read-flow.py');M=importlib.util.module_from_spec(s);sys.modules[s.name]=M;s.loader.exec_module(M)
T=M.T;B=M.B
BASE=R/'reports/kernel-entry-probe/2026-10-29-probe55-provenance-r3/build.json'

def main():
 a=argparse.ArgumentParser();a.add_argument('--build',type=Path,required=True);a.add_argument('--output',type=Path,required=True);a=a.parse_args();assert not a.output.exists()
 b=json.loads(a.build.read_bytes());old=json.loads(BASE.read_bytes());raw=(R/b['candidate']['path']).read_bytes();prior=(R/old['candidate']['path']).read_bytes();original=B.INPUT.read_bytes();om=B.macho(original)
 assert B.sha(raw)==b['candidate']['sha256'] and B.sha(prior)==old['candidate']['sha256'];checks=[]
 jobs=[]
 for module in (M.DISPATCH_CHECKS,M.HANDLER_CHECKS,M.CHAIN_CHECKS,M.CLUSTER_CHECKS):
  for p in module.P.points():
   for mode in module.MODES:jobs.append((module.__name__,p,mode,lambda data,report,p=p,mode=mode,module=module:module.setup(M,data,report,p,mode)))
 for p in M.P.RESOURCE.points():
  for mode in M.RMODES:jobs.append(('resource',p,mode,lambda data,report,p=p,mode=mode:M.resource_setup(data,report,p,mode)))
 for p in M.P.points():
  for mode in M.D.MODES+M.EXTRA:jobs.append(('flow',p,mode,lambda data,report,p=p,mode=mode:M.setup(data,report,p['site'],mode)))
 state_sizes={'probe_read_state':64,'probe_resource_state':32,'probe_resource_dispatch_state':16,'probe_resource_handler_state':32,'probe_result_state':64,'probe_deep_state':64,'probe_fetch_state':64}
 state_sizes.update({M.CLUSTER_CHECKS.P.state_name(s['name']):32 for s in M.CLUSTER_CHECKS.P.SPECS})
 state_sizes.update({M.CHAIN_CHECKS.P.state_name(s['name']):32 for s in M.CHAIN_CHECKS.P.SPECS})
 for group,p,mode,setup in jobs:
  site=p['site'];ref=setup(prior,old)[0];at=B.backed(om,site);ref.mem_write(site,original[at:at+4]);native_writes=[]
  ref.hook_add(T.U.UC_HOOK_MEM_WRITE,lambda u,a,pos,n,v,d:native_writes.append((pos,n)))
  ref.emu_start(site,0,count=1);expected=M.D.snapshot(ref)
  states=[]
  for data,report in ((prior,old),(raw,b)):
   row=setup(data,report);u,sy=row[0],row[2];writes=[]
   u.hook_add(T.U.UC_HOOK_MEM_WRITE,lambda u,a,pos,n,v,d:writes.append((pos,n)) if T.FB<=pos<T.FB+0x1200000 else None)
   u.hook_add(T.U.UC_HOOK_CODE,lambda u,pc,n,d:u.emu_stop() if pc==expected['pc'] else None)
   u.emu_start(site,0,count=3000000);assert M.D.snapshot(u)==expected,(group,hex(site),mode,'native context')
   for pos,n in native_writes:assert bytes(u.mem_read(pos,n))==bytes(ref.mem_read(pos,n))
   states.append({k:bytes(u.mem_read(sy[k],size)) for k,size in state_sizes.items() if k in sy})
   if data is raw and group!=M.CLUSTER_CHECKS.__name__:assert not writes,(group,hex(site),mode,'unexpected retired framebuffer write')
   del u
  assert states[0]==states[1],(group,hex(site),mode,'scope or record drift')
  checks.append(dict(name=group+':'+hex(site)+':'+mode,passed=True));del ref;gc.collect()
  if len(checks)%100==0:print('scope checks '+str(len(checks)),flush=True)
 a.output.write_text(json.dumps(dict(candidate_sha256=B.sha(raw),baseline_sha256=B.sha(prior),checks=checks,device_accessed=False,limits=['Synthetic scope and native instruction differential; no hardware timing or concurrency qualification']),indent=2)+'\n')
 print('PASS '+str(len(checks)))
if __name__=='__main__':main()
