"""Model reserved x18 clearing during HEX rendering, preserving old evidence."""
import argparse, importlib.util, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
s=importlib.util.spec_from_file_location('delta_model',ROOT/'scripts/test-delta-hex.py')
D=importlib.util.module_from_spec(s);s.loader.exec_module(D)
T=D.T

def run(build,row,inject):
 data=D.load(build);u,sy,y,base=D.machine(data,row);hits=[];faults=[];u.reg_write(T.UC_ARM64_REG_X18,0)
 def tick(u,pc,n,arg):
  if inject and sy['probe_hex_shared']<=pc<sy['probe_hex_shared_end']:
   u.reg_write(T.UC_ARM64_REG_X18,0)
 def invalid(u,access,address,size,value,arg):
  faults.append(dict(pc=hex(u.reg_read(T.UC_ARM64_REG_PC)),address=hex(address)));return False
 u.hook_add(T.U.UC_HOOK_CODE,tick);u.hook_add(T.U.UC_HOOK_MEM_INVALID,invalid)
 try:
  pixels,count=D.step(u,sy,row,D.MASK,y,base)
  return dict(completed=True,writes=count),pixels
 except T.U.UcError as e:
  return dict(completed=False,error=str(e),faults=faults),None

def main():
 p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.output.exists()
 checks=[]
 for row in D.ROWS:
  clean,pixels=run(a.build,row,False);interrupted,actual=run(a.build,row,True)
  assert clean['completed'] and interrupted['completed'] and actual==pixels
  checks.append(dict(row=row,passed=True,synthetic_x18_clear_every_instruction=True))
 old,_=run(ROOT/'reports/kernel-entry-probe/2026-10-27-v49-r5/build.json',1984,True)
 assert not old['completed'] and old['faults'][0]['address']=='0x8'
 b=json.loads(a.build.read_text());a.output.write_text(json.dumps(dict(candidate_sha256=b['candidate']['sha256'],checks=checks,old_candidate_negative=old,scope='Unicorn register-clobber injection, not physical IRQ qualification'),indent=2)+'\n')
 print(json.dumps(dict(checks=len(checks),old_candidate_rejected=True)))
if __name__=='__main__':main()

