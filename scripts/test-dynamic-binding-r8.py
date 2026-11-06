"""Execute actual callback initialization and dynamic service argument paths."""
import argparse,hashlib,json,struct
from pathlib import Path
import unicorn as U
from unicorn import arm64_const as A
R=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.output.exists()
 source=R/'reports/desktop-readiness/2026-11-03-offline-desktop-r8/dynamic-code-final.json';d=json.loads(source.read_bytes());assert d['passed'];cases=[]
 def machine(w):
  u=U.Uc(U.UC_ARCH_ARM64,U.UC_MODE_ARM);addr=int(w['address'],16);raw=bytes.fromhex(w['bytes']);assert hashlib.sha256(raw).hexdigest()==w['sha256'];base=addr&~4095
  u.mem_map(base,((addr+len(raw)+4095)&~4095)-base);u.mem_write(addr,raw);u.mem_map(0x100000,0x10000);u.reg_write(A.UC_ARM64_REG_SP,0x108000);return u
 for mode,begin,wait in ((0,0x1af223708,0x1af223648),(1,0x1af2271f8,0x1af2272f0)):
  w=next(w for w in d['windows'] if w['address']=='0x1af2267dc');u=machine(w);u.mem_write(0x100b38,bytes([mode]));u.mem_write(0x101000,struct.pack('<Q',0x100000));u.reg_write(A.UC_ARM64_REG_X0,0x100000);u.reg_write(A.UC_ARM64_REG_X19,0x101000);hit=[]
  def hook(uc,pc,size,data):
   if pc==0x1af226b84:hit.append(pc);uc.emu_stop()
  u.hook_add(U.UC_HOOK_CODE,hook);u.emu_start(0x1af2268b0,0,count=500);assert hit
  assert struct.unpack('<Q',u.mem_read(0x100728,8))[0]==begin and struct.unpack('<Q',u.mem_read(0x100750,8))[0]==wait
  cases.append(dict(name='actual display initialization branch',mode=mode,begin=hex(begin),wait=hex(wait)))
 assert d['resolved_strings'][0]['value']=='com.apple.runningboard' and d['resolved_strings'][1]['value']=='UTF8String'
 for pc,start in ((0x1937745f8,0x1937745e4),(0x193780030,0x19378001c)):
  w=next(w for w in d['windows'] if isinstance(w['reason'],dict) and w['reason']['pc']==hex(pc));u=machine(w);u.reg_write(A.UC_ARM64_REG_X19,0x100000);u.mem_write(0x100038,struct.pack('<Q',0x1234));hit=[]
  def hook2(uc,addr,size,data):
   if addr==start+8:
    assert uc.reg_read(A.UC_ARM64_REG_X0)==0x1d682a980
    # The actual selector reference is bound above; Objective-C runtime is a fixture.
    uc.reg_write(A.UC_ARM64_REG_X0,int(d['resolved_strings'][0]['character_pointer'],16));uc.reg_write(A.UC_ARM64_REG_PC,addr+4)
   if addr==pc:hit.append(addr);uc.emu_stop()
  u.hook_add(U.UC_HOOK_CODE,hook2);u.emu_start(start,0,count=30);assert hit
  assert u.reg_read(A.UC_ARM64_REG_X0)==int(d['resolved_strings'][0]['character_pointer'],16) and u.reg_read(A.UC_ARM64_REG_X2)==2
  assert u.reg_read(A.UC_ARM64_REG_X1)==(0 if pc==0x1937745f8 else 0x1234)
  cases.append(dict(name='RBS dynamic connection name',pc=hex(pc),name_value='com.apple.runningboard',flags=2))
 result=dict(passed=True,cases=cases,parent_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
  limitations=['Explicit object/stack state; no successful IOServiceOpen assumed','Objective-C UTF8String execution is substituted after binding selector/constant bytes','Both display initialization modes tested; runtime mode selection and display backend not proven'],device_accessed=False)
 a.output.write_text(json.dumps(result,indent=2)+'\n');print('PASS',len(cases),'actual initialization/dynamic argument cases')
if __name__=='__main__':main()
