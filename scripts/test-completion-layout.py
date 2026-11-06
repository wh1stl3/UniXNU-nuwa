"""Verify current-code marker footprints avoid the relocated HEX pane."""
import argparse,gc,importlib.util,json,sys
from pathlib import Path
import completion_trace_inputs as M
import lean_probe_inputs as V
s=importlib.util.spec_from_file_location('layout_t',M.R/'scripts/test-probe-transparency.py');T=importlib.util.module_from_spec(s);sys.modules[s.name]=T;s.loader.exec_module(T)
a=argparse.ArgumentParser();a.add_argument('--build',type=Path,required=True);a=a.parse_args()
b=M.read(a.build);raw=(M.R/b['candidate']['path']).read_bytes();V.verify_bytes(b,raw)
names=M.MARKERS-{'probe_entry','probe_mmu','probe_mmu_on'}
names|={c.get('function',c.get('reason')) for c in b['init_bridge_observation']['changes']}
rows=range(200,681,32);checks=[]
def intersects(pos,size):
 y,x=divmod(pos-T.FB,T.ROW)
 return any(v<=y<v+20 for v in rows) and x<736*4 and x+size>256*4
assert intersects(T.FB+200*T.ROW+256*4,4)
assert not intersects(T.FB+200*T.ROW+736*4,4)
for p in b['patches']:
 if p['reason'] not in names and not p['reason'].startswith('probe_target_'):continue
 c=dict(flag=0,video=True,nzcv=0xa0000000,x0=T.STACK+0x2000,seed_simd=True)
 ref,expected,_=T.machine(raw,b,p,c,True);c['native_pc']=expected['pc'];u,actual,writes=T.machine(raw,b,p,c)
 fb=[(pos,n) for pos,n in writes if T.FB<=pos<T.FB+0x1200000]
 assert fb and not any(intersects(pos,n) for pos,n in fb),p['reason']
 checks.append(dict(name=p['reason']+': no HEX overlap',passed=True))
 del ref,u;gc.collect()
assert len(checks)>=18
out=dict(candidate_sha256=b['candidate']['sha256'],checks=checks,limits='Executed current normal milestone/target/init marker footprints. Firmware background is handled by per-field clearing; arbitrary future console or panic writes are not prevented.')
(a.build.parent/'completion-layout.json').write_text(json.dumps(out,indent=2));print(len(checks),'layout checks passed')
