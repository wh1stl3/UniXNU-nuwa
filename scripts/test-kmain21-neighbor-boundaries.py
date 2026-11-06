"""Execute shipped init boundary hooks and native release-guard negative controls."""
import argparse,hashlib,json,struct,sys
from pathlib import Path
import flush_trace_inputs as trace
sys.path.insert(0,str(trace.R/'out/python-tools'))
import unicorn as U
from unicorn.arm64_const import *
p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);w=p.parse_args().work
proof=json.loads((w/'kernel-proof.json').read_bytes());raw=(w/'kernel.macho').read_bytes()
assert hashlib.sha256(raw).hexdigest()==proof['kernel_sha256']
b=trace.builder();m=b.macho(raw);seg=m['segments'][-1];bias=0xfffffff000000000
loc={k:v-bias for k,v in proof['symbols'].items()};tar={k:v-bias for k,v in proof['targets'].items()};tests=[]
regs=[getattr(U.arm64_const,'UC_ARM64_REG_X'+str(i)) for i in range(31)]
qregs=[getattr(U.arm64_const,'UC_ARM64_REG_Q'+str(i)) for i in range(32)]
def machine(site):
 u=U.Uc(U.UC_ARCH_ARM64,U.UC_MODE_ARM);u.mem_map(seg['va']-bias,proof['mapped_end']-seg['va']);u.mem_write(seg['va']-bias,raw[seg['fileoff']:]);u.mem_map(0x20000000,0x10000)
 if not seg['va']-bias<=site<proof['mapped_end']-bias:
  u.mem_map(site&~4095,4096);off=b.backed(m,(site&~4095)+bias);u.mem_write(site&~4095,raw[off:off+4096])
 return u

sites=[('query_before',0x51f7268,0x523561c),('neighbor_before',0x5234d5c,0x525ec64),('neighbor_after',0x5234d60,0x5234d64),('release_before',0x5234d70,0x5240cb4),('release_after',0x5234d74,0x5234d78),('query_after',0x51f726c,0x51f7270)]
for step,(name,site,stop) in enumerate(sites,1):
 default_stop=stop
 for variant in ('zero','value','alias','alias-parent','foreign','inactive','other-frame','completed')+(('unpaired',) if step==3 else ()):
  stop=0x51f75b0 if step==6 and variant!='value' else default_stop
  if step==3 and variant=='value':stop=0x5234ec8
  u=machine(site);stack=0x20008000;thread=0x20002000;state=tar['coarse_state'];values=[0x10000+i*16 for i in range(31)];values[0]=14 if variant=='value' else 0;values[30]=0x20006000;values[22]=0x20004000;values[29]=0x20005000;values[28]=14 if variant=='value' else 0
  try:u.mem_map(stop&~4095,4096)
  except U.UcError:pass
  if variant!='inactive':u.mem_write(state+104,struct.pack('<Q',thread))
  u.mem_write(state+136,struct.pack('<Q',stack+(0x590 if step in (1,6) else 0x710)+(16 if variant=='other-frame' else 0)))
  if step==3 and variant!='unpaired':u.mem_write(state+152,struct.pack('<I',1<<2))
  neighbor=0x20004100;target=0x20004200
  if variant=='alias':neighbor=target
  if variant=='alias-parent':neighbor=values[27]
  u.mem_write(stack+0x48,struct.pack('<QQ',neighbor,target))
  if variant=='completed':u.mem_write(state+148,struct.pack('<I',0x1000))
  u.mem_write(stack,bytes(range(32)));u.reg_write(UC_ARM64_REG_TPIDR_EL1,thread+(16 if variant=='foreign' else 0));draws=[];hits=[];minimum=[stack]
  def hook(uc,pc,size,data):
   minimum[0]=min(minimum[0],uc.reg_read(UC_ARM64_REG_SP))
   if pc==loc['draw']:
    draws.append((uc.reg_read(UC_ARM64_REG_X0),uc.reg_read(UC_ARM64_REG_X1)));lr=uc.reg_read(UC_ARM64_REG_LR)
    for reg in regs[:19]:uc.reg_write(reg,0xdeadbeef)
    uc.reg_write(UC_ARM64_REG_NZCV,0xf0000000);uc.reg_write(UC_ARM64_REG_PC,lr)
   elif pc==stop:hits.append(pc);uc.emu_stop()
  u.hook_add(U.UC_HOOK_CODE,hook)
  vectors=[(0x123456789abcdef0<<64)+i for i in range(32)]
  for visit in range(2):
   minimum[0]=stack
   for reg,value in zip(regs,values):u.reg_write(reg,value)
   for reg,value in zip(qregs,vectors):u.reg_write(reg,value)
   u.reg_write(UC_ARM64_REG_SP,stack);u.reg_write(UC_ARM64_REG_NZCV,0xa0000000);u.emu_start(site,0,count=4000)
   expected=values[:]
   if step in (1,2,4):expected[30]=site+4+bias
   if step==5:expected[27]=target
   assert [u.reg_read(reg) for reg in regs]==expected,(name,variant,'GPR')
   assert [u.reg_read(reg) for reg in qregs]==vectors and u.reg_read(UC_ARM64_REG_SP)==stack and u.reg_read(UC_ARM64_REG_NZCV)==0xa0000000
   assert bytes(u.mem_read(stack,32))==bytes(range(32)), 'Caller stack args changed'
   payload=values[0] if step==6 else (1 if variant=='alias' else 2 if variant=='alias-parent' else 0) if step==2 else 0
   wanted=[(18,0xf0000000|(step<<24)|payload)] if variant in ('zero','value','alias','alias-parent') else []
   assert draws==wanted and len(hits)==visit+1,(name,variant,draws,wanted)
   assert stack-minimum[0]==(288 if variant=='unpaired' else 64 if visit==1 or variant in ('foreign','inactive','other-frame','completed') else 288)
  tests.append(dict(name=name,variant=variant,passed=True,once_only=True,stack_arguments_preserved=True))
(w/'neighbor-boundary-tests.json').write_text(json.dumps(dict(passed=True,kernel_sha256=proof['kernel_sha256'],tests=tests,external_calls_modeled=True),indent=2)+'\n');print('PASS',len(tests),'B boundary ABI and scope cases')
