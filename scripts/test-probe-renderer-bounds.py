"""Execute renderers and independently constrain every write to its exact rectangles."""
import argparse,importlib.util,json,sys
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'scripts'))
s=importlib.util.spec_from_file_location('transparency',R/'scripts/test-probe-transparency.py');T=importlib.util.module_from_spec(s);sys.modules[s.name]=T;s.loader.exec_module(T)
CASES={'probe_soc_base':(704,(1344,1376,1408,1440,1472)),'probe_wfe_timeout':(768,(1504,1536)),'probe_panic_trap':(1040,(1088,1248,1280,1312,1568,1664))}
def run(build,site):
 b=json.loads(build.read_text());raw=(R/b['candidate']['path']).read_bytes();patch=next(p for p in b['patches'] if p['reason']==site)
 case=dict(flag=0,video=True,nzcv=0xa0000000,x0=1,native_pc=int(patch['va'],16)+4)
 u,state,writes=T.machine(raw,b,patch,case)
 tile,rows=CASES[site];rects=[(((tile-256)//512)*96,256+(tile-256)%512,96,32)]
 rects += [(256,224+28*((y-1088)//32),480,20) for y in rows]
 bad=[];fbwrites=0
 for p,n in writes:
  if not T.FB<=p<T.FB+0x1200000:continue
  fbwrites+=1;y,off=divmod(p-T.FB,T.ROW);x=off//4
  if not any(rx<=x and x*4+n<=(rx+rw)*4 and ry<=y<ry+rh for rx,ry,rw,rh in rects):bad.append(dict(address=hex(p),x=x,y=y,bytes=n))
 assert state['pc']==case['native_pc'] and not state['bad'] and fbwrites>0
 return dict(outside_count=len(bad),outside_first=bad[:12],writes=fbwrites,rectangles=rects)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--negative-build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();checks=[];cases={}
 for site in CASES:
  good=run(a.build,site);old=run(a.negative_build,site);cases[site]=dict(candidate=good,old_probe17=old)
  assert good['outside_count']==0,(site,good)
  assert old['outside_count']>0,(site,old)
  checks += [dict(name=site+' confines every framebuffer write to exact rectangles',passed=True),dict(name=site+' rejects old PROBE17 row drift',passed=True)]
 a.output.write_text(json.dumps(dict(candidate_sha256=json.loads(a.build.read_text())['candidate']['sha256'],negative_candidate_sha256=json.loads(a.negative_build.read_text())['candidate']['sha256'],checks=checks,cases=cases),indent=2)+'\n');print(json.dumps(dict(checks=len(checks),passed=True)))
if __name__=='__main__':main()
