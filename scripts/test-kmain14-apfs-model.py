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
for bypass in (True,False):
 u=U.Uc(U.UC_ARCH_ARM64,U.UC_MODE_ARM);u.mem_map(seg['va'],proof['mapped_end']-seg['va']);u.mem_write(seg['va'],raw[seg['fileoff']:])
 for page in [0xfffffff007441000,0xfffffff00746c000,0xfffffff0079fd000,0xfffffff0051a1000,0xfffffff0051a2000,0xfffffff00525e000,0xfffffff00525f000,0xfffffff0051ae000]:
  u.mem_map(page,4096);u.mem_write(page,raw[b.backed(m,page):][:4096])
 u.mem_map(0x20000000,0x40000);u.mem_map(0x80000000,0x800000)
 state=proof['targets']['coarse_state'];ndp=0x20000100;ctx=0x20001000;dp=0x20003000;thread=0x20002000;vpp=ndp+0x28;cnp=ndp+0x150;table=0x20005000;desc=0xfffffff0079fdbb0;fs=0x20010000;node=0x20020000
 u.mem_write(dp+0xd0,struct.pack('<Q',table));u.mem_write(table+40,struct.pack('<Q',0xfffffff0051a1f68));u.mem_write(desc,struct.pack('<I',5));u.mem_write(cnp+4,struct.pack('<I',0x80008000 if bypass else 0));u.mem_write(cnp+40,struct.pack('<Q',0x20004000));u.mem_write(cnp+48,struct.pack('<I',3));u.mem_write(0x20004000,b'usr\0')
 u.mem_write(state+104,struct.pack('<QQ',thread,ndp));u.mem_write(proof['targets']['scratch'],struct.pack('<QQ',0x80000000,5760))
 for reg,val in [(UC_ARM64_REG_X0,dp),(UC_ARM64_REG_X1,vpp),(UC_ARM64_REG_X2,cnp),(UC_ARM64_REG_X3,ctx),(UC_ARM64_REG_X19,ndp),(UC_ARM64_REG_SP,0x20030000),(UC_ARM64_REG_TPIDR_EL1,thread)]:u.reg_write(reg,val)
 calls=[];draws=[];hits=[];frames=[]
 services={0xfffffff00525f5a0:0x20008000,0xfffffff00525f210:fs,0xfffffff00525f444:node,0xfffffff00525f1b0:0x20009000,0xfffffff00525edd8:0,0xfffffff00525e61c:0,0xfffffff0051aeffc:0}
 def hook(u,pc,size,_):
  if pc==proof['symbols']['draw']:draws.append((u.reg_read(UC_ARM64_REG_X0),u.reg_read(UC_ARM64_REG_X1)))
  elif pc==0xfffffff0051a1f68:
   assert tuple(struct.unpack('<5Q',u.mem_read(u.reg_read(UC_ARM64_REG_X0),40)))==(desc,dp,vpp,cnp,ctx)
   assert u.reg_read(UC_ARM64_REG_LR)==0xfffffff00746c264;frames.append(u.reg_read(UC_ARM64_REG_SP)-0x140)
  elif pc in services:
   calls.append(hex(pc));u.reg_write(UC_ARM64_REG_X0,services[pc]);u.reg_write(UC_ARM64_REG_PC,u.reg_read(UC_ARM64_REG_LR))
  elif pc==0xfffffff00525ec64:
   assert u.reg_read(UC_ARM64_REG_X0)==node+0xa0 and u.reg_read(UC_ARM64_REG_SP)==frames[0] and u.reg_read(UC_ARM64_REG_LR)==0xfffffff0051a227c
   hits.append(pc);u.reg_write(UC_ARM64_REG_PC,u.reg_read(UC_ARM64_REG_LR))
  elif pc==0xfffffff0051a2280:
   assert u.reg_read(UC_ARM64_REG_X8)==0;u.emu_stop()
 u.hook_add(U.UC_HOOK_CODE,hook);u.emu_start(0xfffffff007441328,0,count=2000000)
 assert hits==[0xfffffff00525ec64],hex(u.reg_read(UC_ARM64_REG_PC))
 assert draws==[(16,4),(16,12),(16,44),(16,300)],draws
 assert ('0xfffffff00525e61c' in calls)==(not bypass)
 tests.append(dict(passed=True,cache_bypassed=bypass,actual_apfs_prologue_and_branches=True,scoped_entry_and_prelock=True,calls=calls,stop='after modeled IORWLockRead return',services_modeled=True))
(w/'apfs-entry-model.json').write_text(json.dumps(dict(passed=True,kernel_sha256=proof['kernel_sha256'],tests=tests,full_filesystem_emulation=False),indent=2)+'\n');print('PASS 2 APFS paths through modeled lock return')

