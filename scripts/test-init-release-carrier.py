"""Execute native suffix selection and strcmp; explicit bootarg/exec boundaries."""
import sys,json,hashlib,argparse
from pathlib import Path
import flush_trace_inputs as t
sys.path.insert(0,str(t.R/'out/python-tools'))
import unicorn as U
from unicorn.arm64_const import *
p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
raw=(a.work/'kernel.macho').read_bytes();b=t.builder();m=b.macho(raw);results=[]
for suffix,values,expected in [(None,[2,0],'return'),('release',[0],'return'),('release',[2],'panic'),('release',[5],'panic'),('release',[None],'exec-in-progress'),('',[0],'return'),('release',['helper'],'scoped-exec-entry'),('release',['copyout-error'],'panic')]:
 proof=json.loads((a.work/'kernel-proof.json').read_bytes());helper=values[0] in ('helper','copyout-error');draws=[]
 u=U.Uc(U.UC_ARCH_ARM64,U.UC_MODE_ARM);u.mem_map(0x20000000,0x10000);calls=[];stops=[];recent=[]
 def fault(uc,access,address,size,value,data):
  page=address&~4095;s=next(s for s in m['segments'] if s['va']<=page<s['va']+s['size']);n=max(0,min(4096,s['filesize']-page+s['va']));o=s['fileoff']+page-s['va'];uc.mem_map(page,4096);uc.mem_write(page,raw[o:o+n]+bytes(4096-n));return True
 u.hook_add(U.UC_HOOK_MEM_UNMAPPED,fault)
 def string(addr):
  out=bytearray()
  while True:
   try:v=u.mem_read(addr+len(out),1)
   except U.UcError:
    fault(u,0,addr+len(out),1,0,None);v=u.mem_read(addr+len(out),1)
   if v==b'\0':return out.decode()
   out+=v
 def hook(uc,pc,size,data):
  recent.append(hex(pc));recent[:]=recent[-500:]
  if pc==0xfffffff007905fdc:
   assert string(uc.reg_read(UC_ARM64_REG_X0))=='launchdsuffix'
   if suffix is not None:uc.mem_write(uc.reg_read(UC_ARM64_REG_X1),suffix.encode()+b'\0')
   uc.reg_write(UC_ARM64_REG_X0,int(suffix is not None));uc.reg_write(UC_ARM64_REG_PC,uc.reg_read(UC_ARM64_REG_LR))
  elif pc==0xfffffff007283e88:uc.reg_write(UC_ARM64_REG_PC,uc.reg_read(UC_ARM64_REG_LR))
  elif helper and pc==0xfffffff0084e65dc:
   uc.reg_write(UC_ARM64_REG_PC,uc.reg_read(UC_ARM64_REG_LR)) # explicit FSCompression lifecycle boundary, preserves arguments
  elif pc==proof['symbols']['draw']:
   draws.append([uc.reg_read(UC_ARM64_REG_X0),uc.reg_read(UC_ARM64_REG_X1)]);uc.reg_write(UC_ARM64_REG_PC,uc.reg_read(UC_ARM64_REG_LR))
  elif helper and pc==proof['targets']['exec_entry_old']:
   assert uc.reg_read(UC_ARM64_REG_LR)==0xfffffff00769d5f8
   assert [16,1] in draws;stops.append('scoped-exec-entry');uc.emu_stop()
  elif helper and pc in (0xfffffff0073b9518,0xfffffff0076adb1c,0xfffffff0076b44c0,0xfffffff007367444):
   if pc==0xfffffff0073b9518:
    result=14 if values[0]=='copyout-error' else 0
    if not result:uc.mem_write(uc.reg_read(UC_ARM64_REG_X1),bytes(uc.mem_read(uc.reg_read(UC_ARM64_REG_X0),uc.reg_read(UC_ARM64_REG_X2))))
   else:result=int(pc==0xfffffff0076adb1c)
   uc.reg_write(UC_ARM64_REG_X0,result);uc.reg_write(UC_ARM64_REG_PC,uc.reg_read(UC_ARM64_REG_LR))
  elif pc==0xfffffff00769d4e0:
   calls.append(string(uc.reg_read(UC_ARM64_REG_X2)));value=values[len(calls)-1]
   if helper:return
   if value is None:stops.append('exec-in-progress');uc.emu_stop()
   else:uc.reg_write(UC_ARM64_REG_X0,value);uc.reg_write(UC_ARM64_REG_PC,uc.reg_read(UC_ARM64_REG_LR))
  elif pc in (0xfffffff00769d490,0xfffffff007938000):stops.append('return' if pc==0xfffffff00769d490 else 'panic');uc.emu_stop()
 u.mem_write(0x20008028,(0x20003000).to_bytes(8,'little'));u.reg_write(UC_ARM64_REG_TPIDR_EL1,0x20001000)
 u.hook_add(U.UC_HOOK_CODE,hook);u.reg_write(UC_ARM64_REG_SP,0x20008000);u.reg_write(UC_ARM64_REG_X29,0x20008120);u.reg_write(UC_ARM64_REG_X19,0x20001000);u.reg_write(UC_ARM64_REG_CPACR_EL1,3<<20);
 try:u.emu_start(0xfffffff00769d308,0,count=10000)
 except Exception:
  Path('reports/ufs-check-3-r1/helper-model-failure.json').write_text(json.dumps(recent,indent=2));print('FAILED',values,hex(u.reg_read(UC_ARM64_REG_PC)),[hex(u.reg_read(x)) for x in (UC_ARM64_REG_X0,UC_ARM64_REG_X1,UC_ARM64_REG_X2)]);raise
 assert stops==[expected] and len(calls)==len(values),(suffix,calls,stops)
 assert calls==(['/usr/appleinternal/sbin/launchd.development','/sbin/launchd'] if suffix is None else ['/sbin/launchd'])
 if values[0]=='copyout-error':assert [13,14] in draws and [16,1] not in draws
 results.append(dict(draws=draws,suffix=suffix,exec_results=values,paths=calls,stop=stops[0],passed=True))
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(dict(passed=True,kernel_sha256=hashlib.sha256(raw).hexdigest(),tests=results,scope='Unicorn native suffix branch and strcmp. PE bootargs, printf and exec result are mocked. Helper cases execute native strlen/copyout call flow and real entry/return hooks; copyout, process/token and FSCompression lifecycle are explicit fixtures. No hardware/full-XNU claim.'),indent=2)+'\n');print('PASS eight native release selection/helper cases')
