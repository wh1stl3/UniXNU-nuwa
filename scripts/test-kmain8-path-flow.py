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
for value in (0,14):
 site=0x769bd78;u=machine(site);thread=0x20002000
 u.reg_write(UC_ARM64_REG_TPIDR_EL1,thread);u.mem_write(tar['coarse_state']+104,struct.pack('<Q',thread))
 values=[0x10000+i*16 for i in range(31)];values[0]=value
 for reg,val in zip(regs,values):u.reg_write(reg,val)
 u.reg_write(UC_ARM64_REG_SP,0x20008000);u.reg_write(UC_ARM64_REG_NZCV,0xa0000000)
 stop=0x769bd90 if value==0 else 0x769bd7c;hits=[];draws=[]
 def hook(u,pc,size,_):
  if pc==loc['draw']:
   draws.append((u.reg_read(UC_ARM64_REG_X0),u.reg_read(UC_ARM64_REG_X1)))
   lr=u.reg_read(UC_ARM64_REG_LR)
   for reg in regs[:19]:u.reg_write(reg,0xdeadbeef)
   u.reg_write(UC_ARM64_REG_NZCV,0xf0000000);u.reg_write(UC_ARM64_REG_PC,lr)
  elif pc==stop:hits.append(pc);u.emu_stop()
 u.hook_add(U.UC_HOOK_CODE,hook);u.emu_start(site,0,count=3000)
 assert hits==[stop] and [u.reg_read(reg) for reg in regs]==values
 assert u.reg_read(UC_ARM64_REG_SP)==0x20008000 and u.reg_read(UC_ARM64_REG_NZCV)==0xa0000000
 assert draws==[(16,32),(18,value)]
 old_error=struct.unpack('<Q',u.mem_read(0x84e7088+88,8))[0]
 assert old_error==(240 if value else 0)
 tests.append(dict(path_errno=value,native_continuation=hex(stop),old_first_error=old_error,passed=True))
(w/'path-flow-tests.json').write_text(json.dumps(dict(passed=True,kernel_sha256=proof['kernel_sha256'],tests=tests,scope='New observer plus actual inherited save-path return trampoline. No real allocation/namei/storage emulated.'),indent=2)+'\n')
print('PASS two integrated path-return/error continuations')
