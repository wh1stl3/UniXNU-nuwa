"""Read actual renderer footprints from exact-candidate Unicorn execution."""
import argparse,gc,importlib.util,json,sys
from pathlib import Path
import lean_probe_inputs as V
import backend_trace_inputs as M
s=importlib.util.spec_from_file_location('bridge_map_t',M.R/'scripts/test-probe-transparency.py');T=importlib.util.module_from_spec(s);sys.modules[s.name]=T;s.loader.exec_module(T)
a=argparse.ArgumentParser();a.add_argument('--build',type=Path,required=True);a=a.parse_args();b=M.read(a.build);raw=(M.R/b['candidate']['path']).read_bytes();V.verify_bytes(b,raw)
names={c.get('function',c.get('reason')) for c in b['init_bridge_observation']['changes']};checks=[]
for p in b['patches']:
 if p['reason'] not in names and not p['reason'].startswith('probe_target_'):continue
 c=dict(flag=0,video=True,nzcv=0xa0000000,x0=T.STACK+0x2000,seed_simd=True);ref,state,_=T.machine(raw,b,p,c,True);c['native_pc']=state['pc'];u,got,writes=T.machine(raw,b,p,c);assert got==state
 coords=[((pos-T.FB)%T.ROW//4,(pos-T.FB)//T.ROW) for pos,n in writes if T.FB<=pos<T.FB+0x1200000];assert coords
 x=min(q[0] for q in coords);y=min(q[1] for q in coords);pixel=int.from_bytes(u.mem_read(T.FB+y*T.ROW+x*4,4),'little')
 checks.append(dict(name=p['reason'],pc=p['va'],passed=True,x=x,y=y,pixel=hex(pixel),scope='Actual first pixel; native framebuffer coordinates, not camera coordinates'))
 del ref,u;gc.collect()
assert len(checks)==9
with (a.build.parent/'marker-map.json').open('x') as f:json.dump(dict(candidate_sha256=b['candidate']['sha256'],checks=checks,hardware_proof=False),f,indent=2)
print(json.dumps(checks))
