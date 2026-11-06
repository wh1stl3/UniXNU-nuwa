"""Exact VM removal wrapper; host substitutes for lock/delete/unlock/zap boundaries.
Checks ABI, call ordering, bookkeeping and observer transparency; not real VM/pmap completion.
"""
import argparse,gc,importlib.util,json,struct,sys
from pathlib import Path
import map_trace_inputs as M
import lean_probe_inputs as V
s=importlib.util.spec_from_file_location('map_chain_t',M.R/'scripts/test-probe-transparency.py');T=importlib.util.module_from_spec(s);sys.modules[s.name]=T;s.loader.exec_module(T)
a=argparse.ArgumentParser();a.add_argument('--build',type=Path,required=True);a=a.parse_args();b=M.read(a.build);raw=(M.R/b['candidate']['path']).read_bytes();V.verify_bytes(b,raw)
MAP=T.STACK+0x3000;UPLFRAME=T.STACK+0x4000;THREAD=T.STACK+0x1000
START=0xfffffff00732fd54;END=0xfffffff0073639cc
LOCK=0xfffffff007277cbc;DELETE=0xfffffff007326b44;UNLOCK=0xfffffff007279328;ZAP=0xfffffff007327c8c
state=int(b['backend_trace']['symbols']['trace_state'],16);patches={int(p['reason'].rsplit('_',1)[1]):p for p in b['patches'] if p['reason'].startswith('probe_backend_trace_')};checks=[]
def native_anchor(raw,pc):
 B=M.builder();off=B.backed(B.macho(raw),pc);word=raw[off:off+4].hex();return dict(va=hex(pc),before=word,after=word,reason='native-anchor')

def run(stop,result,video,native,foreign):
 def reg(u,n,v):u.reg_write(getattr(T,'UC_ARM64_REG_X'+str(n)),v)
 def get(u,n):return u.reg_read(getattr(T,'UC_ARM64_REG_X'+str(n)))
 def setup(u):
  st=bytearray(280);struct.pack_into('<I',st,0,2);struct.pack_into('<I',st,172,2);struct.pack_into('<QQQQ',st,232,MAP,UPLFRAME+(16 if foreign else 0),0xfffffff84b2b1000,0xfffffff84b2b2000);u.mem_write(state,bytes(st))
  u.mem_write(MAP+8,struct.pack('<Q',0x420000));u.mem_write(MAP+0x98,struct.pack('<I',10));u.mem_write(THREAD+0x4d8,struct.pack('<I',0x1234));u.reg_write(T.UC_ARM64_REG_TPIDR_EL1,THREAD)
  for n,v in [(0,MAP),(1,0xfffffff84b2b1000),(2,0xfffffff84b2b2000),(3,0),(4,0),(29,UPLFRAME),(30,END)]:reg(u,n,v)
 u,_,_=T.machine(raw,b,patches.get(21) or native_anchor(raw,START),dict(flag=0,video=video,nzcv=0xa0000000,x0=MAP,seed_simd=True,setup=setup),True);u.reg_write(T.UC_ARM64_REG_SP,T.STACK+0x8000)
 for p in patches.values():u.mem_write(int(p['va'],16),bytes.fromhex(p['before'] if native else p['after']))
 u.ctl_remove_cache(0xfffffff007000000,0xfffffff009000000);events=[]
 target=dict(lock=LOCK,delete=DELETE,unlock=UNLOCK,zap=ZAP,returned=END)[stop]
 def hook(u,pc,size,data):
  if pc in (LOCK,DELETE,UNLOCK,ZAP,END):events.append(hex(pc))
  if pc==target:u.emu_stop();return
  if pc==LOCK:
   assert get(u,0)==MAP;u.mem_write(MAP+8,struct.pack('<Q',0x1234004a0000))
  elif pc==DELETE:
   assert [get(u,i) for i in range(5)]==[MAP,0xfffffff84b2b1000,0xfffffff84b2b2000,0,0]
   zap=get(u,5);assert zap==T.STACK+0x7fb0 and bytes(u.mem_read(zap,16))==struct.pack('<QQ',0,zap)
   reg(u,0,result);reg(u,1,4096 if result==0 else 0)
  elif pc==UNLOCK:
   assert get(u,0)==MAP and int.from_bytes(u.mem_read(MAP+0x98,4),'little')==11
   u.mem_write(MAP+8,struct.pack('<Q',0x420000));reg(u,0,123);reg(u,1,456)
  elif pc==ZAP:
   assert get(u,0)==T.STACK+0x7fb0;reg(u,0,789);reg(u,1,987)
  else:return
  u.reg_write(T.UC_ARM64_REG_PC,get(u,30))
 u.hook_add(T.U.UC_HOOK_CODE,hook);u.emu_start(START,0,count=4000000);assert u.reg_read(T.UC_ARM64_REG_PC)==target
 regs=[u.reg_read(x) for x in T.REGS]+[u.reg_read(T.UC_ARM64_REG_SP),u.reg_read(T.UC_ARM64_REG_NZCV)];simd=[u.reg_read(getattr(T,'UC_ARM64_REG_Q'+str(i))) for i in range(32)]
 mem=bytes(u.mem_read(MAP,0x100))+bytes(u.mem_read(T.STACK+0x8000,0x8000));st=bytes(u.mem_read(state,280))
 if stop=='returned':assert get(u,0)==result and get(u,1)==(4096 if result==0 else 0) and get(u,29)==UPLFRAME and u.reg_read(T.UC_ARM64_REG_SP)==T.STACK+0x8000
 del u;gc.collect();return regs,simd,mem,st,events
for stop,count in [('lock',1),('delete',2),('unlock',3),('zap',4),('returned',5)]:
 for video in (False,True):
  for foreign in (False,True):
   for result in ((0,5) if stop in ('unlock','zap','returned') else (0,)):
    expected=run(stop,result,video,True,foreign);got=run(stop,result,video,False,foreign);assert got[:3]==expected[:3] and got[4]==expected[4],(stop,result,video,foreign)
    flags=[struct.unpack_from('<I',got[3],208+4*i)[0] for i in range(5)];assert flags==([0]*5 if foreign else [2 if j<count and 21+j in patches else 0 for j in range(5)]),flags
    checks.append(dict(name=f'{stop}:result={result}:video={video}:foreign={foreign}',passed=True,substituted_call_events=got[4]))
(a.build.parent/'map-native-chain.json').write_text(json.dumps(dict(candidate_sha256=b['candidate']['sha256'],checks=checks,limits='Exact vm_map_remove_guard wrapper instructions, including native map timestamp and two-register return. lck_rw_lock_exclusive/vm_map_delete/lck_rw_done/vm_map_zap_dispose are host substitutes; no real map lock, delete, pmap, scheduler or device qualification.'),indent=2));print(len(checks),'map wrapper chain checks passed')
