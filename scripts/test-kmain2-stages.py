"""Execute the actual four coarse hooks, including native replay and second visits."""
import argparse, hashlib, json, struct, sys
from pathlib import Path
import flush_trace_inputs as trace
sys.path.insert(0, str(trace.R/'out/python-tools'))
import unicorn as U
from unicorn.arm64_const import *

p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);a=p.parse_args()
w=a.work;proof=json.loads((w/'kernel-proof.json').read_bytes());raw=(w/'kernel.macho').read_bytes()
assert hashlib.sha256(raw).hexdigest()==proof['kernel_sha256']
B=trace.builder();m=B.macho(raw);seg=m['segments'][-1];bias=0xfffffff000000000
local={k:v-bias for k,v in proof['symbols'].items()};targets=proof['targets'];tests=[]
sites=[('root_wait',0x78e37a8),('root_return',0x7673098),('mount_return',0x76730e8),('init_entry',0x769d2a4)]
for index,(name,site) in enumerate(sites):
 for value in (0,0xe00002bc):
  u=U.Uc(U.UC_ARCH_ARM64,U.UC_MODE_ARM)
  u.mem_map(seg['va']-bias,proof['mapped_end']-seg['va']);u.mem_write(seg['va']-bias,raw[seg['fileoff']:])
  u.mem_map(site&~4095,4096);u.mem_write(site,raw[B.backed(m,site+bias):][:4])
  stack=0x20001000;u.mem_map(stack-4096,8192)
  regs=[getattr(U.arm64_const,'UC_ARM64_REG_X'+str(i)) for i in range(31)]
  qregs=[getattr(U.arm64_const,'UC_ARM64_REG_Q'+str(i)) for i in range(32)]
  values=[0x10000+i*16 for i in range(31)];values[0]=value
  vectors=[(0x123456789abcdef0<<64)+i for i in range(32)]
  if name=='root_wait': stop=targets['root_wait_target']-bias
  elif name=='init_entry':stop=targets['init_entry_resume']-bias
  else:stop=targets[name+('_zero' if value==0 else '_resume')]-bias
  if stop&~4095 != site&~4095:u.mem_map(stop&~4095,4096)
  draws=[];stopped=[]
  def hook(u,pc,size,_):
   if pc==local['draw']:
    draws.append((u.reg_read(UC_ARM64_REG_X0),u.reg_read(UC_ARM64_REG_X1)))
    lr=u.reg_read(UC_ARM64_REG_LR)
    for reg in regs[:19]:u.reg_write(reg,0xdeadbeef)
    u.reg_write(UC_ARM64_REG_NZCV,0xf0000000);u.reg_write(UC_ARM64_REG_PC,lr)
   elif pc==stop:stopped.append(pc);u.emu_stop()
  u.hook_add(U.UC_HOOK_CODE,hook)
  for visit in range(2):
   for reg,val in zip(regs,values):u.reg_write(reg,val)
   for reg,val in zip(qregs,vectors):u.reg_write(reg,val)
   u.reg_write(UC_ARM64_REG_SP,stack);u.reg_write(UC_ARM64_REG_NZCV,0xa0000000)
   u.emu_start(site,0,count=2000)
   expected=values[:]
   if name=='root_wait':expected[30]=targets['root_wait_resume']
   assert [u.reg_read(r) for r in regs]==expected,(name,'GPR')
   assert [u.reg_read(r) for r in qregs]==vectors,(name,'SIMD')
   assert u.reg_read(UC_ARM64_REG_NZCV)==0xa0000000
   assert u.reg_read(UC_ARM64_REG_SP)==stack-(0x130 if name=='init_entry' else 0)
   assert len(stopped)==visit+1
   assert draws==[(index+8,1 if index in (0,3) else value)],(name,draws)
  tests.append(dict(site=name,input=hex(value),visits=2,draws=1,registers_flags_simd_preserved=True,native_replay=True))
# Render the extra fields using actual machine code; enforce no overlap with
# FB00-FB07 and no drawing beyond the expected twelve-row footprint.
u=U.Uc(U.UC_ARCH_ARM64,U.UC_MODE_ARM);u.mem_map(seg['va']-bias,proof['mapped_end']-seg['va']);u.mem_write(seg['va']-bias,raw[seg['fileoff']:])
fb=0x60000000;stride=5760;u.mem_map(fb,0x600000);u.mem_write(targets['scratch']-bias,struct.pack('<QQ',fb,stride))
font=struct.unpack('<16I',u.mem_read(local['font'],64))
for row,value in enumerate((1,0,0xe00002bc,1),8):
 u.reg_write(UC_ARM64_REG_X0,row);u.reg_write(UC_ARM64_REG_X1,value);u.reg_write(UC_ARM64_REG_LR,local['halt'])
 u.emu_start(local['draw'],local['halt'],count=100000)
 for col,digit in enumerate(f'{0xfb00+row:04x}{value:08x}'):
  for y in range(20):
   pixels=struct.unpack('<16I',u.mem_read(fb+(576+row*32+y)*stride+384+col*96,64))
   assert list(pixels)==[0xffffffff if font[int(digit,16)]&(1<<(19-(y//4)*4-x//4)) else 0 for x in range(16)]
assert bytes(u.mem_read(fb,832*stride))==bytes(832*stride)
assert bytes(u.mem_read(fb+948*stride,0x600000-948*stride))==bytes(0x600000-948*stride)
report=dict(passed=True,kernel_sha256=proof['kernel_sha256'],tests=tests,extra_field_pixels=True,scope='Unicorn machine-code replay and rendering; no physical stage claim')
(w/'coarse-tests.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS 8 replay/first-visit cases and FB08-FB0B pixels')
