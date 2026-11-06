"""Execute final PMGR bridge bytes with modeled IOKit calls, including ownership failures."""
import argparse,hashlib,json,struct,sys
from pathlib import Path
import flush_trace_inputs as trace
sys.path.insert(0,str(trace.R/'out/python-tools'))
import unicorn as U
from unicorn.arm64_const import *
p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);w=p.parse_args().work
proof=json.loads((w/'kernel-proof.json').read_bytes());raw=(w/'kernel.macho').read_bytes();bias=0xfffffff000000000
B=trace.builder();m=B.macho(raw);seg=m['segments'][-1];loc={k:v-bias for k,v in proof['symbols'].items()};t={k:v-bias for k,v in proof['targets'].items()}
def machine():
 u=U.Uc(U.UC_ARCH_ARM64,U.UC_MODE_ARM);u.mem_map(seg['va']-bias,proof['mapped_end']-seg['va']);u.mem_write(seg['va']-bias,raw[seg['fileoff']:]);u.mem_map(0x20000000,0x10000)
 pages=set()
 for key,va in t.items():
  if (not key.startswith('pmgr_') and key!='storage_load') or key=='pmgr_vtable':continue
  page=va&~4095
  if page not in pages:u.mem_map(page,4096);pages.add(page)
  if key in ('pmgr_read','pmgr_write'):
   off=B.backed(m,va+bias,32);u.mem_write(va,raw[off:off+32])
 return u
results=[]
for case,want in [('success',16),('load',1),('alloc',2),('identity',3),('provider',3),('init',3),('platform',4),('attach',4),('start',5),('matching',6),('not_found',6),('wrong_found',6)]:
 u=machine();nub=0x20002000;platform=0x20003000;dictionary=0x20004000;other=0x20005000;stack=0x2000f000
 u.mem_write(nub,struct.pack('<Q',proof['targets']['pmgr_vtable']+(8 if case=='identity' else 0)))
 if case=='provider':u.mem_write(nub+0x88,struct.pack('<Q',platform))
 regs=[getattr(U.arm64_const,'UC_ARM64_REG_X'+str(i)) for i in range(19,30)];vals=[0x123000+i for i in range(len(regs))]
 for reg,val in zip(regs,vals):u.reg_write(reg,val)
 u.reg_write(UC_ARM64_REG_SP,stack);u.reg_write(UC_ARM64_REG_LR,loc['halt']);calls=[];released=[]
 names={v:k for k,v in t.items() if k.startswith('pmgr_') and k not in ('pmgr_read','pmgr_write','pmgr_vtable','pmgr_amfi_resume')};names[t['storage_load']]='load'
 def hook(u,pc,size,data):
  if pc not in names:return
  name=names[pc];x0=u.reg_read(UC_ARM64_REG_X0);x1=u.reg_read(UC_ARM64_REG_X1);calls.append(name);ret=0
  if name=='load':ret=1 if case=='load' else 0
  elif name=='pmgr_alloc':ret=0 if case=='alloc' else nub
  elif name=='pmgr_init':assert (x0,x1)==(nub,0);ret=case!='init'
  elif name=='pmgr_platform':ret=0 if case=='platform' else platform
  elif name in ('pmgr_attach','pmgr_start'):assert (x0,x1)==(nub,platform);ret=case!=name[5:]
  elif name=='pmgr_register':assert (x0,x1)==(nub,2)
  elif name=='pmgr_matching':ret=0 if case=='matching' else dictionary
  elif name=='pmgr_wait':assert (x0,x1)==(dictionary,1000000);ret=0 if case=='not_found' else other if case=='wrong_found' else nub
  elif name=='pmgr_release_object':released.append(x0)
  elif name in ('pmgr_stop_service','pmgr_detach_service'):assert (x0,x1)==(nub,platform)
  u.reg_write(UC_ARM64_REG_X0,int(ret));u.reg_write(UC_ARM64_REG_PC,u.reg_read(UC_ARM64_REG_LR))
 u.hook_add(U.UC_HOOK_CODE,hook);u.emu_start(loc['pmgr_install'],loc['halt'],count=10000)
 assert u.reg_read(UC_ARM64_REG_PC)==loc['halt'] and u.reg_read(UC_ARM64_REG_X1)==want,(case,calls)
 assert u.reg_read(UC_ARM64_REG_SP)==stack and [u.reg_read(reg) for reg in regs]==vals
 published='pmgr_register' in calls
 if published:
  assert int.from_bytes(u.mem_read(t['coarse_state']+48,8),'little')==nub
  assert released==([] if case=='matching' else [dictionary] if case=='not_found' else [other,dictionary] if case=='wrong_found' else [nub,dictionary])
  assert 'pmgr_detach_service' not in calls
 elif case not in ('load','alloc'):assert released==[nub]
 if case=='start':assert 'pmgr_detach_service' in calls and 'pmgr_stop_service' not in calls
 previous_calls=list(calls);u.reg_write(UC_ARM64_REG_LR,loc['halt']);u.emu_start(loc['pmgr_install'],loc['halt'],count=10000)
 assert calls==previous_calls and u.reg_read(UC_ARM64_REG_X1)==want
 results.append(dict(case=case,status=want,calls=calls,released= released,published=published))
# Actual AMFI hook replay, all general/SIMD registers, flags and DAIF, repeat draw suppression.
u=machine();site=0x46fe7a4;u.mem_write(site,raw[B.backed(m,site+bias,4):][:4]);stack=0x2000f000
regs=[getattr(U.arm64_const,'UC_ARM64_REG_X'+str(i)) for i in range(31)];vals=[0x10000+i*16 for i in range(31)]
for reg,val in zip(regs,vals):u.reg_write(reg,val)
qregs=[getattr(U.arm64_const,'UC_ARM64_REG_Q'+str(i)) for i in range(32)]
for index,reg in enumerate(qregs):u.reg_write(reg,(0x12345678<<64)+index)
u.reg_write(UC_ARM64_REG_SP,stack);u.reg_write(UC_ARM64_REG_PSTATE,0xa00003c5);draws=[]
def boundary(u,pc,size,data):
 if pc==loc['draw']:
  draws.append((u.reg_read(UC_ARM64_REG_X0),u.reg_read(UC_ARM64_REG_X1)));u.reg_write(UC_ARM64_REG_PC,u.reg_read(UC_ARM64_REG_LR))
u.hook_add(U.UC_HOOK_CODE,boundary)
for _ in range(2):
 u.emu_start(site,site+4,count=10000)
 assert [u.reg_read(reg) for reg in regs]==vals and u.reg_read(UC_ARM64_REG_SP)==stack
 assert int.from_bytes(u.mem_read(stack,8),'little')==vals[21]
 assert [u.reg_read(reg) for reg in qregs]==[(0x12345678<<64)+i for i in range(32)]
 assert u.reg_read(UC_ARM64_REG_PSTATE)&0xf00003c0==0xa00003c0
assert draws==[(16,1)]
# Existing panic once-latch fragment, actual stores only inside red banner.
u=machine();fb=0x30000000;stride=5760;u.mem_map(fb,0x200000)
u.mem_write(t['scratch'],struct.pack('<QQ',fb,stride));writes=[]
def pixels(u,access,address,size,value,data):
 if fb<=address<fb+0x200000:
  y,x=divmod(address-fb,stride);assert 128<=y<192 and 0<=x and x+size<=4096,(y,x,size)
  assert value==0xffff0000;writes.append(address)
u.hook_add(U.UC_HOOK_MEM_WRITE,pixels)
u.emu_start(0x84e5198,0x84e5208,count=150000);assert len(writes)==1024*64
before=len(writes);u.emu_start(0x84e5198,0x84e5208,count=150000);assert len(writes)==before
(w/'pmgr-tests.json').write_text(json.dumps(dict(passed=True,kernel_sha256=hashlib.sha256(raw).hexdigest(),cases=results,panic_banner_once=True,amfi_hook_replay=True,repeat_suppressed=True,scope='Final assembly executed; IOKit calls modeled. Original null-provider helper instructions executed. Not real service publication.'),indent=2)+'\n')
print('PASS PMGR',len(results),'lifecycle cases and AMFI replay')
