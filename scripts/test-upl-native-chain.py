"""Exact buf/UPL control flow; explicit host substitutes for lock and VM removal.

This checks observer transparency and UPL bookkeeping, NOT real lock or pmap behavior.
"""
import argparse,gc,importlib.util,json,struct,sys
from pathlib import Path
import upl_trace_inputs as M
import lean_probe_inputs as V
s=importlib.util.spec_from_file_location('upl_chain_t',M.R/'scripts/test-probe-transparency.py');T=importlib.util.module_from_spec(s);sys.modules[s.name]=T;s.loader.exec_module(T)
a=argparse.ArgumentParser();a.add_argument('--build',type=Path,required=True);a=a.parse_args();b=M.read(a.build);raw=(M.R/b['candidate']['path']).read_bytes();V.verify_bytes(b,raw)
BP=T.STACK+0x2000;UPL=T.STACK+0x1000;MAP=T.STACK+0x3000;FRAME=T.STACK+0x4000;SPEC=T.STACK+0x7000;REAL=T.STACK+0x6000
START=0xfffffff00741ff2c;END=0xfffffff00741ff38;LOCK=0xfffffff0072755c8;UNLOCK=0xfffffff00727585c;REMOVE=0xfffffff00732fd54;PANIC=0xfffffff007964fb8
state=int(b['backend_trace']['symbols']['trace_state'],16);patches={int(p['reason'].rsplit('_',1)[1]):p for p in b['patches'] if p['reason'].startswith('probe_backend_trace_')};checks=[]
def native_anchor(raw,b,pc):
 B=M.builder();off=B.backed(B.macho(raw),pc);word=raw[off:off+4].hex()
 return dict(va=hex(pc),before=word,after=word,reason='unmodified-native-entry-anchor')

def run(case,video,native,foreign):
 def setup(u):
  st=bytearray(280);struct.pack_into('<I',st,0,2);struct.pack_into('<Q',st,8,BP);struct.pack_into('<Q',st,24,0xfffffff00741fcc8);struct.pack_into('<Q',st,104,SPEC+(16 if foreign else 0));u.mem_write(state,bytes(st))
  u.mem_write(FRAME,struct.pack('<Q',SPEC));u.mem_write(BP+0x4c,struct.pack('<I',0x01c00043));u.mem_write(BP+0xa0,struct.pack('<Q',0 if case=='null-upl' else UPL))
  if case=='real-bp':u.mem_write(BP+0xa8,struct.pack('<Q',REAL));u.mem_write(REAL+0x68,struct.pack('<Q',0xfffffff10edb2000))
  u.mem_write(UPL+0x10,struct.pack('<I',1 if case=='bad-ref' else 2));u.mem_write(UPL+0x18,struct.pack('<I',0 if case=='unmapped' else 1));u.mem_write(UPL+0x2c,struct.pack('<IQ',4096,0xfffffff10edb2000))
  u.mem_write(MAP+0x34,struct.pack('<H',12));u.mem_write(0xfffffff00715b0a8,struct.pack('<Q',MAP))
  u.reg_write(T.UC_ARM64_REG_X19,BP);u.reg_write(T.UC_ARM64_REG_X29,FRAME)
 u,_,_=T.machine(raw,b,patches.get(10) or native_anchor(raw,b,START),dict(flag=0,video=video,nzcv=0xa0000000,x0=BP,seed_simd=True,setup=setup),True)
 for p in patches.values():u.mem_write(int(p['va'],16),bytes.fromhex(p['before'] if native else p['after']))
 u.ctl_remove_cache(0xfffffff007000000,0xfffffff009000000);events=[]
 def hook(u,pc,size,data):
  if pc==END or pc==PANIC or (pc==LOCK and case=='lock-stop') or (pc==REMOVE and case=='remove-stop'):
   events.append(hex(pc));u.emu_stop();return
  if pc in (LOCK,UNLOCK,REMOVE):
   events.append(hex(pc))
   if pc==REMOVE:
    assert [u.reg_read(x) for x in (T.UC_ARM64_REG_X0,T.UC_ARM64_REG_X1,T.UC_ARM64_REG_X2)]==[MAP,0xfffffff10edb2000,0xfffffff10edb3000]
    u.reg_write(T.UC_ARM64_REG_X0,0)
   u.reg_write(T.UC_ARM64_REG_PC,u.reg_read(T.UC_ARM64_REG_X30))
 u.hook_add(T.U.UC_HOOK_CODE,hook);u.emu_start(START,0,count=4000000)
 expected_pc={'lock-stop':LOCK,'remove-stop':REMOVE,'bad-ref':PANIC}.get(case,END);assert u.reg_read(T.UC_ARM64_REG_PC)==expected_pc
 regs=[u.reg_read(x) for x in T.REGS]+[u.reg_read(T.UC_ARM64_REG_SP),u.reg_read(T.UC_ARM64_REG_NZCV)];simd=[u.reg_read(getattr(T,'UC_ARM64_REG_Q'+str(i))) for i in range(32)]
 # Compare caller state and native owned objects. Dead/unused callee stack padding is not a native output.
 mem=bytes(u.mem_read(BP,0x110))+bytes(u.mem_read(UPL,0x48))+bytes(u.mem_read(T.STACK+0x8000,0x8000));st=bytes(u.mem_read(state,280))
 if case in ('mapped','remove-stop'):
  assert int.from_bytes(u.mem_read(UPL+0x10,4),'little')==1 and int.from_bytes(u.mem_read(UPL+0x18,4),'little')==0
  assert bytes(u.mem_read(UPL+0x2c,12))==bytes(12)
 if case=='unmapped' and expected_pc==END and 11 in patches:assert int.from_bytes(u.mem_read(state+144,4),'little')==(0 if native or foreign else 2)
 del u;gc.collect();return regs,simd,mem,st,events
for case in ('mapped','unmapped','real-bp','lock-stop','remove-stop','bad-ref','null-upl'):
 for video in (False,True):
  for foreign in (False,True):
   expected=run(case,video,True,foreign);got=run(case,video,False,foreign);assert got[:3]==expected[:3],(case,video,foreign)
   hit=lambda i:struct.unpack_from('<I',got[3],128+(i-7)*4)[0]==2
   if foreign:assert not any(hit(i) for i in (10,11,14,16,17,18,19,20))
   else:
    assert all(hit(i) for i in (10,14) if i in patches)
    assert hit(16)==(case!='real-bp')
    if 20 in patches:assert hit(20)==(case!='real-bp')
    if 17 in patches:assert hit(17)==(case not in ('real-bp','lock-stop','null-upl'))
    assert hit(18)==(case in ('mapped','remove-stop'))
    if 19 in patches:assert hit(19)==(case=='mapped')
    if 11 in patches:assert hit(11)==(case in ('mapped','unmapped','real-bp','null-upl'))
   checks.append(dict(name=f'{case}:video={video}:foreign={foreign}',passed=True,substituted_call_events=got[4]))
# Negative control: withdrawn r1 must demonstrate the observed missing-NULL guard.
current_b,current_raw,current_patches=b,raw,patches
old=M.read(M.R/'reports/kernel-entry-probe/2026-10-31-probe66-upl-r1/build.json');oldpath=M.R/old['candidate']['path'];assert M.sha(oldpath)=='4fdc8b41b474491fb061d6b2b7d406e8db4e6c3126fffd2e23a9a99f7a1375b0'
b,raw=old,oldpath.read_bytes();patches={int(p['reason'].rsplit('_',1)[1]):p for p in b['patches'] if p['reason'].startswith('probe_backend_trace_')}
try:run('null-upl',True,False,False)
except T.U.UcError as error:
 assert error.errno==T.U.UC_ERR_READ_UNMAPPED;checks.append(dict(name='withdrawn-r1-NULL-dereference-negative-control',passed=True))
else:raise AssertionError('Withdrawn NULL bug did not reproduce')
b,raw,patches=current_b,current_raw,current_patches
(a.build.parent/'upl-native-chain.json').write_text(json.dumps(dict(candidate_sha256=b['candidate']['sha256'],checks=checks,limits='Exact native buf_unmap and vm_map_remove_upl_range instructions; lock/unlock/VM removal are explicit host substitutes. No real mutex, scheduler, page table, vector-UPL or hardware qualification.'),indent=2));print(len(checks),'UPL chain checks passed')
