"""Execute real strategy wrapper and buf_vnode with explicit indirect-target fixture."""
import importlib.util,json,struct,sys,argparse
from pathlib import Path
R=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('entry',R/'scripts/test-cluster-io-entry.py');E=importlib.util.module_from_spec(s);s.loader.exec_module(E)
M,C,T,P=E.M,E.C,E.T,E.P
def run(raw,b,original,om,mode,native,result):
 p=next(p for p in P.points() if p['offset']==0x46e538)
 u,m,sy,_,_=C.setup(M,raw,b,p,mode)
 bp,vp,ops,target=(T.STACK+x for x in (0xb000,0xc000,0xd000,0xe000))
 u.reg_write(T.UC_ARM64_REG_X0,bp);u.mem_write(bp+0x88,struct.pack('<Q',vp));u.mem_write(vp+0xd0,struct.pack('<Q',ops))
 index=struct.unpack('<i',u.mem_read(P.BASE+0x9feca8,4))[0];assert 0<=index<256
 u.mem_write(ops+index*8,struct.pack('<Q',target));u.mem_write(target,bytes.fromhex('c0035fd6'))
 if native:
  for q in P.points():
   at=M.B.backed(om,q['site']);u.mem_write(q['site'],original[at:at+4])
 calls=[]
 def hook(u,pc,n,d):
  if pc==target:
   args=u.reg_read(T.UC_ARM64_REG_X0);assert struct.unpack('<QQ',u.mem_read(args,16))==(P.BASE+0x9feca8,bp)
   if not native:assert struct.unpack('<QQ',u.mem_read(sy['probe_result_state']+32,16))==(P.BASE+0x46e570,target)
   if not native:assert struct.unpack('<QQQ',u.mem_read(sy['probe_result_state']+8,24))==(vp,ops,index)
   calls.append(pc);u.reg_write(T.UC_ARM64_REG_X0,result)
  if pc==P.BASE+0x435310:u.emu_stop()
 u.hook_add(T.U.UC_HOOK_CODE,hook);u.emu_start(p['site'],0,count=6000000)
 assert calls==[target] and u.reg_read(T.UC_ARM64_REG_PC)==P.BASE+0x435310 and u.reg_read(T.UC_ARM64_REG_X0)==result
 return M.D.snapshot(u)
def main():
 c=argparse.ArgumentParser();c.add_argument('--build',type=Path,required=True);c.add_argument('--output',type=Path,required=True);a=c.parse_args();assert not a.output.exists()
 b=json.loads(a.build.read_bytes());raw=(R/b['candidate']['path']).read_bytes();original=M.B.INPUT.read_bytes();om=M.B.macho(original)
 assert M.B.sha(raw)==b['candidate']['sha256'];checks=[]
 for mode in ('normal','no-video'):
  for result in (0,5):
   assert run(raw,b,original,om,mode,False,result)==run(raw,b,original,om,mode,True,result)
   checks.append(dict(name=f'{mode}:{result}',passed=True))
 a.output.write_text(json.dumps(dict(candidate_sha256=M.B.sha(raw),checks=checks,device_accessed=False,limitations=['Indirect target is an explicit fixture; no real filesystem or device completion']),indent=2)+'\n');print('strategy continuity 4 passed')
if __name__=='__main__':main()
