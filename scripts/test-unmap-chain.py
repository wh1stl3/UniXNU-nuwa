"""Continuous native/observed replay from mdev pre-unmap through its return."""
import argparse,gc,importlib.util,json,struct,sys
from pathlib import Path
import unmap_trace_inputs as M
import lean_probe_inputs as V
s=importlib.util.spec_from_file_location('unmap_chain_t',M.R/'scripts/test-probe-transparency.py');T=importlib.util.module_from_spec(s);sys.modules[s.name]=T;s.loader.exec_module(T)
a=argparse.ArgumentParser();a.add_argument('--build',type=Path,required=True);a=a.parse_args()
current=M.read(a.build);checks=[]
BP=T.STACK+0x2000;REAL=T.STACK+0x3000;FRAME=T.STACK+0x4000;SPEC=T.STACK+0x7000
START=0xfffffff00741ff2c;END=0xfffffff00741ff38
def native_anchor(raw,b,pc):
 B=M.builder();off=B.backed(B.macho(raw),pc);word=raw[off:off+4].hex()
 return dict(va=hex(pc),before=word,after=word,reason='unmodified-native-entry-anchor')

def run(raw,b,flags,video,native,foreign):
 patches={int(p['reason'].rsplit('_',1)[1]):p for p in b['patches'] if p['reason'].startswith('probe_backend_trace_')}
 state=int(b['backend_trace']['symbols']['trace_state'],16)
 def setup(u):
  st=bytearray(280);struct.pack_into('<I',st,0,2);struct.pack_into('<Q',st,8,BP)
  struct.pack_into('<Q',st,24,0xfffffff00741fcc8);struct.pack_into('<Q',st,104,SPEC+(16 if foreign else 0));struct.pack_into('<I',st,68,2)
  u.mem_write(state,bytes(st));u.mem_write(FRAME,struct.pack('<Q',SPEC))
  u.mem_write(BP+0x4c,struct.pack('<I',flags));u.mem_write(BP+0xa8,struct.pack('<Q',REAL));u.mem_write(REAL+0x68,struct.pack('<Q',0xfffffff8682fe000))
  u.reg_write(T.UC_ARM64_REG_X19,BP);u.reg_write(T.UC_ARM64_REG_X29,FRAME)
 c=dict(flag=0,video=video,nzcv=0xa0000000,x0=BP,seed_simd=True,setup=setup)
 # Fixture helper executes just the displaced MOV. Then restore current code and
 # execute the entire chain in one emulation run, including BL/RET and both hooks.
 u,_,writes=T.machine(raw,b,patches.get(10) or native_anchor(raw,b,START),c,True)
 for p in patches.values():u.mem_write(int(p['va'],16),bytes.fromhex(p['before'] if native else p['after']))
 u.ctl_remove_cache(0xfffffff007000000,0xfffffff009000000)
 visited=[]
 def at(u,pc,size,data):
  if pc in (START,0xfffffff00742b50c,0xfffffff00742b514,0xfffffff00742b52c,0xfffffff00741ff34,END):visited.append(hex(pc))
  if pc==END:u.emu_stop()
 u.hook_add(T.U.UC_HOOK_CODE,at);u.emu_start(START,0,count=2000000)
 assert u.reg_read(T.UC_ARM64_REG_PC)==END,visited
 regs=[u.reg_read(x) for x in T.REGS]+[u.reg_read(T.UC_ARM64_REG_SP),u.reg_read(T.UC_ARM64_REG_NZCV)]
 simd=[u.reg_read(getattr(T,'UC_ARM64_REG_Q'+str(i))) for i in range(32)]
 memory=bytes(u.mem_read(BP,0x3000))+bytes(u.mem_read(T.STACK+0x8000,0x8000))
 st=bytes(u.mem_read(state,280));fbwrites=sum(T.FB<=pos<T.FB+0x1200000 for pos,n in writes)
 del u;gc.collect();return regs,simd,memory,st,visited,fbwrites
for build in (M.R/'reports/kernel-entry-probe/2026-10-31-probe64-completion-r1/build.json',a.build):
 b=M.read(build);raw=(M.R/b['candidate']['path']).read_bytes();V.verify_bytes(b,raw)
 for flags in (0x01c00043,0x01c00042,0x01c00003):
  for video in (False,True):
   for foreign in (False,True):
    expected=run(raw,b,flags,video,True,foreign);got=run(raw,b,flags,video,False,foreign)
    assert got[:3]==expected[:3]
    assert (0xfffffff00742b514 in [int(pc,16) for pc in got[4]]) == (not bool(flags&64))
    offsets=([] if b['probe_revision'] in (68,69,70,71,72) else [144] if b['probe_revision']==67 else [140,144])+([156] if b['probe_revision'] in (65,66) else [])
    for off in offsets:assert struct.unpack_from('<I',got[3],off)[0]==(0 if foreign else 2)
    if b['probe_revision']==65:assert struct.unpack_from('<I',got[3],160)[0]==(2 if not foreign and not flags&64 else 0)
    assert bool(got[5])==(video and not foreign and bool(offsets))
    checks.append(dict(name=f"rev{b['probe_revision']}:flags={flags:08x}:video={video}:wrong-owner={foreign}",passed=True,visited=got[4]))
out=dict(candidate_sha256=current['candidate']['sha256'],checks=checks,limits='Synthetic mapped objects, observed earlier flags and real-bp fast path; runs actual BL/RET and observers continuously. Does not model hardware stalls, concurrent flag changes, UPL unmapping, or prove the field request is a read.')
(a.build.parent/'unmap-chain.json').write_text(json.dumps(out,indent=2));print(len(checks),'continuous chain checks passed')
