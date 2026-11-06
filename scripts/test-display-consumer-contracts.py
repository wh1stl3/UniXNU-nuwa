"""Run original 20H392 display dispatch and request setup instructions."""
import argparse,hashlib,json,struct
from pathlib import Path
import unicorn as U
from unicorn import arm64_const as A
R=Path(__file__).resolve().parents[1]

def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.output.exists()
 source=R/'reports/desktop-readiness/2026-11-03-offline-desktop-r7/display-code.json';d=json.loads(source.read_bytes());assert d['passed'];r=next(r for r in d['records'] if 'Framebuffer' in r['path']);cases=[]
 def machine(record):
  u=U.Uc(U.UC_ARCH_ARM64,U.UC_MODE_ARM);addr=int(record['address'],16);raw=bytes.fromhex(record['bytes']);assert hashlib.sha256(raw).hexdigest()==record['sha256']
  base=addr&~4095;u.mem_map(base,((addr+len(raw)+4095)&~4095)-base);u.mem_write(addr,raw);u.mem_map(0x100000,0x10000)
  u.reg_write(A.UC_ARM64_REG_SP,0x108000);u.reg_write(A.UC_ARM64_REG_LR,0x10f000);return u
 def run(u,start,stops):
  hit=[]
  def hook(uc,pc,size,data):
   if pc in stops:hit.append(pc);uc.emu_stop()
  u.hook_add(U.UC_HOOK_CODE,hook);u.emu_start(start,0,count=100);assert len(hit)==1;return hit[0]
 for name,offset in (('_IOMobileFramebufferSwapBegin',0x728),('_IOMobileFramebufferSwapWait',0x750)):
  f=next(f for f in r['functions'] if f['name']==name)
  for object_present,callback in ((False,0),(True,0),(True,0x10e000)):
   u=machine(f);u.reg_write(A.UC_ARM64_REG_X0,0x100000 if object_present else 0);u.mem_write(0x100000+offset,struct.pack('<Q',callback))
   stop=run(u,int(f['address'],16),{0x10f000,0x10e000});assert stop==(0x10e000 if callback else 0x10f000)
   if not callback:assert u.reg_read(A.UC_ARM64_REG_W0)==0xe00002c2
   cases.append(dict(name=name,object_present=object_present,callback=callback,stop=hex(stop)))
 for pc,selector,count in ((0x1af22355c,5,0x46c),(0x1af22368c,6,3),(0x1af223758,4,0)):
  w=next(w for w in r['windows'] if int(w['call']['pc'],16)==pc);u=machine(w)
  u.reg_write(A.UC_ARM64_REG_X0,0x100000);u.reg_write(A.UC_ARM64_REG_X1,7);u.reg_write(A.UC_ARM64_REG_X2,9);u.mem_write(0x100014,struct.pack('<I',0x123))
  assert run(u,int(w['address'],16),{pc})==pc
  assert u.reg_read(A.UC_ARM64_REG_W0)==0x123 and u.reg_read(A.UC_ARM64_REG_W1)==selector and u.reg_read(A.UC_ARM64_REG_W3)==count
  if selector==5:assert u.reg_read(A.UC_ARM64_REG_X2)==0x100018
  if selector==6:assert struct.unpack('<3Q',u.mem_read(u.reg_read(A.UC_ARM64_REG_X2),24))==(7,9,0)
  if selector==4:assert struct.unpack('<I',u.mem_read(u.reg_read(A.UC_ARM64_REG_X5),4))[0]==1
  cases.append(dict(name='native request setup',pc=hex(pc),selector=selector,count=count))
 result=dict(passed=True,cases=cases,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
  limitations=['Actual userland bytes with explicit local object/stack/port state','No kernel user-client call executed, no surface mapping, swap completion or display output verified','Exported wrappers dispatch through object callbacks; nearby selector helpers are not assumed wired without tracing initialization'],device_accessed=False)
 a.output.write_text(json.dumps(result,indent=2)+'\n');print('PASS',len(cases),'native display cases')
if __name__=='__main__':main()
