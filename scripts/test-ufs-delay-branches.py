"""Actual donor IODelay branch selection, with runtime selector/clock fixtures."""
import sys,json,struct,hashlib
from pathlib import Path
import flush_trace_inputs as t
sys.path.insert(0,str(t.R/'out/python-tools'))
import unicorn as U
from unicorn.arm64_const import *
w=t.R/'out/ufs-check-1-r1-final';raw=(w/'kernel.macho').read_bytes();b=t.builder();m=b.macho(raw);results=[]
for spin,preempt,irq,expected in [(1,0,1,'machine-delay'),(0,1,1,'machine-delay'),(0,0,0,'machine-delay'),(0,0,1,'thread-deadline-wait')]:
 u=U.Uc(U.UC_ARCH_ARM64,U.UC_MODE_ARM);u.mem_map(0x20000000,0x10000);stops=[]
 def fault(uc,access,address,size,value,data):
  page=address&~4095;s=next(s for s in m['segments'] if s['va']<=page<s['va']+s['size']);n=max(0,min(4096,s['filesize']-page+s['va']));o=s['fileoff']+page-s['va'];uc.mem_map(page,4096);uc.mem_write(page,raw[o:o+n]+bytes(4096-n));return True
 def hook(uc,pc,size,data):
  selectors={0xfffffff0073ceb44:100,0xfffffff0073caef4:spin,0xfffffff0073c10e0:preempt,0xfffffff0073c8c4c:irq}
  if pc==0xfffffff0073cf034:
   assert uc.reg_read(UC_ARM64_REG_X0)==2 and uc.reg_read(UC_ARM64_REG_X1)==1000
   uc.mem_write(uc.reg_read(UC_ARM64_REG_X2),struct.pack('<Q',48));uc.reg_write(UC_ARM64_REG_PC,uc.reg_read(UC_ARM64_REG_LR))
  elif pc in selectors:uc.reg_write(UC_ARM64_REG_X0,selectors[pc]);uc.reg_write(UC_ARM64_REG_PC,uc.reg_read(UC_ARM64_REG_LR))
  elif pc==0xfffffff0073cf094:
   assert uc.reg_read(UC_ARM64_REG_X1)==148;stops.append('machine-delay');uc.emu_stop()
  elif pc==0xfffffff00728ffb0:
   assert uc.reg_read(UC_ARM64_REG_X2)==148;stops.append('thread-deadline-wait');uc.emu_stop()
 u.hook_add(U.UC_HOOK_MEM_UNMAPPED,fault);u.hook_add(U.UC_HOOK_CODE,hook);u.reg_write(UC_ARM64_REG_SP,0x20008000);u.reg_write(UC_ARM64_REG_X0,2);u.emu_start(0xfffffff00784fd38,0,count=1000);assert stops==[expected]
 results.append(dict(spin=spin,preemption_level=preempt,interrupts_enabled=irq,target=expected,passed=True))
(t.R/'reports/ufs-check-1-r1/trial/delay-branches.json').write_text(json.dumps(dict(passed=True,kernel_sha256=hashlib.sha256(raw).hexdigest(),cases=results,scope='Actual IODelay and clock_delay control flow; selector values, conversion and clock mocked. Hardware branch unknown.'),indent=2)+'\n');print('PASS four actual IODelay branch cases')
