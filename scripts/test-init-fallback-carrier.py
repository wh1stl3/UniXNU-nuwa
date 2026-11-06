"""Actual load_init_program fallback control flow; exec itself is an explicit stub."""
import sys,json,struct,hashlib,argparse
from pathlib import Path
import flush_trace_inputs as t
sys.path.insert(0,str(t.R/'out/python-tools'))
import unicorn as U
from unicorn.arm64_const import *
p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);w=p.parse_args().work
raw=(w/'kernel.macho').read_bytes();b=t.builder();m=b.macho(raw);results=[]
for name,returns,wanted in [('first-success',[0],1),('expected-enoent',[2,0],2),('other-error',[5,0],2),('second-block',[2,None],2),('both-absent',[2,2],2)]:
 u=U.Uc(U.UC_ARCH_ARM64,U.UC_MODE_ARM);u.mem_map(0x20000000,0x10000);mapped=set();calls=[];stops=[]
 def fault(uc,access,address,size,value,data):
  page=address&~4095;s=next(s for s in m['segments'] if s['va']<=page<s['va']+s['size']);n=max(0,min(4096,s['filesize']-page+s['va']));o=s['fileoff']+page-s['va'];uc.mem_map(page,4096);uc.mem_write(page,raw[o:o+n]+bytes(4096-n));return True
 u.hook_add(U.UC_HOOK_MEM_UNMAPPED,fault)
 def hook(uc,pc,size,data):
  if pc==0xfffffff007283e88:uc.reg_write(UC_ARM64_REG_PC,uc.reg_read(UC_ARM64_REG_LR))
  elif pc==0xfffffff00769d4e0:
   a=uc.reg_read(UC_ARM64_REG_X2);off=b.backed(m,a,1);path=raw[off:raw.index(b'\0',off)].decode();calls.append(path);result=returns[len(calls)-1]
   if result is None:stops.append('second-exec-in-progress');uc.emu_stop()
   else:uc.reg_write(UC_ARM64_REG_X0,result);uc.reg_write(UC_ARM64_REG_PC,uc.reg_read(UC_ARM64_REG_LR))
  elif pc in (0xfffffff00769d490,0xfffffff007938000):stops.append('return' if pc==0xfffffff00769d490 else 'panic');uc.emu_stop()
 u.hook_add(U.UC_HOOK_CODE,hook);u.reg_write(UC_ARM64_REG_SP,0x20008000);u.reg_write(UC_ARM64_REG_X19,0x20001000);u.emu_start(0xfffffff00769d3c0,0,count=1000)
 assert len(calls)==wanted and calls[0]=='/usr/appleinternal/sbin/launchd.development'
 if wanted==2:assert calls[1]=='/sbin/launchd'
 expected='panic' if name=='both-absent' else 'second-exec-in-progress' if name=='second-block' else 'return';assert stops==[expected]
 results.append(dict(case=name,paths=calls,stop=stops[0],passed=True))
(w/'init-fallback-tests.json').write_text(json.dumps(dict(passed=True,kernel_sha256=hashlib.sha256(raw).hexdigest(),tests=results,scope='Actual carrier fallback instructions and literal paths; printf and exec mocked; no runtime second-path completion claim.'),indent=2)+'\n');print('PASS five actual init fallback cases')
