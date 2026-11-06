"""Run native VNOP wrapper and real renderer around a modeled filesystem callback.
Synthetic initialized vnode/v_op and callback; no APFS/UFS hardware claim.
"""
import argparse,json,hashlib,struct,sys
from pathlib import Path
import flush_trace_inputs as t
sys.path.insert(0,str(t.R/'out/python-tools'))
import unicorn as U
from unicorn.arm64_const import *
p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);w=p.parse_args().work
proof=json.loads((w/'kernel-proof.json').read_bytes());raw=(w/'kernel.macho').read_bytes();assert hashlib.sha256(raw).hexdigest()==proof['kernel_sha256']
b=t.builder();m=b.macho(raw);bias=0xfffffff000000000;seg=m['segments'][-1];tests=[];new='exec_callback_resume' in proof['targets'];scoped='vnop_lookup_desc' in proof['targets']
for callback in (0x30000000,0xfffffff030000000):
 for errno,found in [(0,False),(0,True),(2,False),(14,False)]:
  u=U.Uc(U.UC_ARCH_ARM64,U.UC_MODE_ARM);u.mem_map(seg['va'],proof['mapped_end']-seg['va']);u.mem_write(seg['va'],raw[seg['fileoff']:])
  for page in [0xfffffff007441000,0xfffffff00746c000,0xfffffff0079fd000]:
   u.mem_map(page,4096);u.mem_write(page,raw[b.backed(m,page):][:4096])
  u.mem_map(callback,4096);u.mem_map(0x20000000,0x10000);u.mem_map(0x80000000,0x800000)
  state=proof['targets']['coarse_state'];ndp=0x20000100;ctx=0x20001000;dp=0x20003000;thread=0x20002000;vpp=ndp+0x28;cnp=ndp+0x150;table=0x20005000;desc=0xfffffff0079fdbb0
  u.mem_write(dp+0xd0,struct.pack('<Q',table));u.mem_write(table+5*8,struct.pack('<Q',callback));u.mem_write(desc,struct.pack('<I',5))
  u.mem_write(state+104,struct.pack('<QQ',thread,ndp));u.mem_write(proof['targets']['scratch'],struct.pack('<QQ',0x80000000,5760))
  for reg,val in [(UC_ARM64_REG_X0,dp),(UC_ARM64_REG_X1,vpp),(UC_ARM64_REG_X2,cnp),(UC_ARM64_REG_X3,ctx),(UC_ARM64_REG_X19,ndp),(UC_ARM64_REG_SP,0x20008000),(UC_ARM64_REG_TPIDR_EL1,thread)]:u.reg_write(reg,val)
  calls=[];draws=[];hits=[];stop=0xfffffff0074414a8 if errno==0 else 0xfffffff007441330
  def hook(u,pc,size,_):
   if pc==proof['symbols']['draw']:draws.append((u.reg_read(UC_ARM64_REG_X0),u.reg_read(UC_ARM64_REG_X1)))
   elif pc==callback:
    args=struct.unpack('<5Q',u.mem_read(u.reg_read(UC_ARM64_REG_X0),40));assert args==(desc,dp,vpp,cnp,ctx),args
    assert u.reg_read(UC_ARM64_REG_LR)==0xfffffff00746c264
    u.mem_write(vpp,struct.pack('<Q',0x20004000 if found else 0));u.reg_write(UC_ARM64_REG_X0,errno);u.reg_write(UC_ARM64_REG_X8,0xdeadbeef);u.reg_write(UC_ARM64_REG_PC,u.reg_read(UC_ARM64_REG_LR));calls.append(args)
   elif pc==stop:hits.append(pc);u.emu_stop()
  u.hook_add(U.UC_HOOK_CODE,hook);u.emu_start(0xfffffff007441328,0,count=1000000)
  assert hits==[stop] and len(calls)==1
  assert u.reg_read(UC_ARM64_REG_X0)==errno and u.reg_read(UC_ARM64_REG_X19)==ndp and u.reg_read(UC_ARM64_REG_SP)==0x20008000
  expected=[(16,4),(16,12),(17,callback&0xffffffff),(18,callback>>32),(16,44),(20,errno),(16,172)] if new else [(16,4),(16,132),(20,errno)]
  if scoped:expected=[(16,4),(18,callback&0xffffffff),(20,callback>>32),(16,132),(17,errno)]
  if 'exec_apfs_locked_old' in proof['targets']:expected=[(16,132),(17,errno)]
  assert draws==expected,(draws,expected)
  if new:assert bytes(u.mem_read(state+120,16))==bytes(16)
  tests.append(dict(callback=hex(callback),errno=errno,found=found,passed=True,native_vnop_args=True,native_return=True,real_renderer=True))
report=dict(passed=True,kernel_sha256=proof['kernel_sha256'],tests=tests,filesystem_callback_modeled=True,hardware_execution=False)
(w/'vnop-dispatch-model.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS 8 native VNOP dispatch/return cases with real renderer',w)
