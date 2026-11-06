"""Execute shipped namei->lookup->cache call with real renderer and native prologue.
Synthetic nameidata/root vnode; stop at cache entry, not an APFS/device simulation.
"""
import argparse,json,hashlib,struct,sys
from pathlib import Path
import flush_trace_inputs as t
sys.path.insert(0,str(t.R/'out/python-tools'))
import unicorn as U
from unicorn.arm64_const import *
p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);w=p.parse_args().work
proof=json.loads((w/'kernel-proof.json').read_bytes());raw=(w/'kernel.macho').read_bytes();assert hashlib.sha256(raw).hexdigest()==proof['kernel_sha256']
b=t.builder();m=b.macho(raw);bias=0xfffffff000000000;seg=m['segments'][-1];u=U.Uc(U.UC_ARCH_ARM64,U.UC_MODE_ARM)
u.mem_map(seg['va']-bias,proof['mapped_end']-seg['va']);u.mem_write(seg['va']-bias,raw[seg['fileoff']:])
for page in [0x7440000,0x7441000,0x7431000,0x7abd000]:
 u.mem_map(page,4096)
 if page!=0x7abd000:u.mem_write(page,raw[b.backed(m,page+bias):][:4096])
u.mem_map(0x20000000,0x10000);u.mem_map(0x80000000,0x800000)
state=proof['targets']['coarse_state']-bias;ndp=0x20000000;ctx=0x20001000;dp=0x20003000;thread=0x20002000
u.mem_write(ndp+0x10,struct.pack('<Q',dp));u.mem_write(ndp+0x158,struct.pack('<Q',ctx));u.mem_write(ndp+0x178,struct.pack('<Q',ndp+0x400));u.mem_write(ndp+0x400,b'/sbin/launchd\0')
u.mem_write(state+104,struct.pack('<QQ',thread,ndp));u.mem_write(proof['targets']['scratch']-bias,struct.pack('<QQ',0x80000000,5760))
u.reg_write(UC_ARM64_REG_X0,ndp);u.reg_write(UC_ARM64_REG_X19,ndp);u.reg_write(UC_ARM64_REG_SP,0x20008000);u.reg_write(UC_ARM64_REG_TPIDR_EL1,thread)
hits=[]
def hook(u,pc,size,_):
 if pc==0x7431cd0:
  assert u.reg_read(UC_ARM64_REG_X0)==ndp and u.reg_read(UC_ARM64_REG_X1)==ndp+0x150
  assert u.reg_read(UC_ARM64_REG_X2)==dp and u.reg_read(UC_ARM64_REG_X3)==ctx and u.reg_read(UC_ARM64_REG_X5)==0
  assert u.reg_read(UC_ARM64_REG_LR)==0x74411b8
  assert struct.unpack('<Q',u.mem_read(0x20007ff8,8))[0]==0xfffffff0074404d0 if 'exec_cache_zero' not in proof['targets'] else struct.unpack('<Q',u.mem_read(0x20007ff8,8))[0]==0x74404d0
  hits.append(pc);u.emu_stop()
u.hook_add(U.UC_HOOK_CODE,hook);u.emu_start(0x74404cc,0,count=300000);assert hits==[0x7431cd0]
report=dict(passed=True,kernel_sha256=proof['kernel_sha256'],native_lookup_prologue_and_cache_arguments=True,renderer_executed=('exec_cache_zero' not in proof['targets']),synthetic_nameidata=True,stopped_before_cache_execution=True,hardware_execution=False)
(w/'lookup-entry-model.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS native lookup handoff to cache entry',w)
