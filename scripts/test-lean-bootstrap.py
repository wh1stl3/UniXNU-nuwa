"""Cold-path semantics with retired bands; native translation and args unchanged."""
import argparse,importlib.util,json,sys
from pathlib import Path
R=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('lean_entry',R/'scripts/test-kernel-entry-probe.py');E=importlib.util.module_from_spec(s);sys.modules[s.name]=E;s.loader.exec_module(E)
def main():
 a=argparse.ArgumentParser();a.add_argument('--build',type=Path,required=True);a.add_argument('--output',type=Path,required=True);a=a.parse_args();assert not a.output.exists()
 b=json.loads(a.build.read_bytes());old=json.loads((R/'reports/kernel-entry-probe/2026-10-29-probe55-provenance-r3/build.json').read_bytes());raw=(R/b['candidate']['path']).read_bytes();prior=(R/old['candidate']['path']).read_bytes();assert E.B.sha(raw)==b['candidate']['sha256'];checks=[]
 for occupied in (None,0x8c3000403):
  kwargs={} if occupied is None else dict(preoccupy=occupied)
  previous,regs0,pix0,tables0,_=E.run(prior,old,**kwargs);actual,regs1,pix1,tables1,_=E.run(raw,b,**kwargs)
  assert actual.get('stop')==previous.get('stop')=='before-sctlr' and not actual['bad_memory']
  assert regs0==regs1 and tables0==tables1 and actual['boot_args_unchanged']
  assert all(pix1[str(y)]==0 for y in (256,288,320))
  checks.append(dict(name='cold-native-and-no-old-bands:'+str(occupied),passed=True))
 for mode in ('aarch64','default'):
  previous=E.run_continuous(prior,old,mode);actual=E.run_continuous(raw,b,mode)
  for key in ('error','reached','bad_memory','tcr','ttbr0','ttbr1','mair','sctlr','native_vbar_snapshot'):
   assert actual.get(key)==previous.get(key),(mode,key,actual.get(key),previous.get(key))
  if mode=='aarch64':assert actual['reached'] and actual['error'] is None
  assert actual['pixels']['352']=='0x0' and actual['pixels']['384']=='0x0'
  checks.append(dict(name='continuous-translation:'+mode,passed=True))
 a.output.write_text(json.dumps(dict(candidate_sha256=E.B.sha(raw),checks=checks,device_accessed=False),indent=2)+'\n');print('lean bootstrap 4 passed')
if __name__=='__main__':main()
