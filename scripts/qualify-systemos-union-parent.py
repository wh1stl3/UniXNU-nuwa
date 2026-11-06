"""Execute the current kernel's non-root union fallback, with explicit vnode/namei fixtures.
Checks path reconstruction, errors and owned resources, not an actual filesystem.
"""
import argparse, hashlib, json, struct, sys
from pathlib import Path
import flush_trace_inputs as trace
sys.path.insert(0, str(trace.R/'out/python-tools'))
import unicorn as U
from unicorn.arm64_const import *

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
a=p.parse_args();assert not a.output.exists()
raw=(a.work/'kernel.macho').read_bytes();proof=json.loads((a.work/'kernel-proof.json').read_bytes())
assert hashlib.sha256(raw).hexdigest()==proof['kernel_sha256']
B=trace.builder();m=B.macho(raw);bias=0xfffffff000000000
entry=m['symbols']['_lookup_traverse_union']-bias;assert entry==0x7441784
cases=[]
for name in ('nested','vector-copy','namei-error','not-directory','missing-name','too-long','namei-buffer'):
 u=U.Uc(U.UC_ARCH_ARM64,U.UC_MODE_ARM)
 callbacks={0x72ce5f4:'alloc',0x74311b8:'getname',0x7431220:'putname',0x73cbc00:'strlen',0x74401c8:'namei',0x72ccc3c:'free',0x74430e0:'put',0x7283e88:'printf'}
 for page in sorted({entry&~4095,0x700a000,0x7abd000}|{v&~4095 for v in callbacks}):
  u.mem_map(page,4096)
  if page!=0x7abd000:
   off=B.backed(m,page+bias,4096);u.mem_write(page,raw[off:off+4096])
 u.mem_map(0x1000000,0x20000);sp=0x101f000;root=0x1002000;lower=0x1002800;mount=0x1003000;result=0x1004000;heap=0x1008000;extra=0x1009000
 names=['Caches','Library','System']
 if name=='vector-copy':names=['a'*64,'Library','System']
 if name=='too-long':names=['a'*1023]
 nodes=[0x1001000+i*0x200 for i in range(len(names))];pointers={}
 for i,(node,text) in enumerate(zip(nodes,names)):
  at=0x1005000+i*0x500;pointers[node]=at
  u.mem_write(at,text.encode()+b'\0');u.mem_write(node+0xc0,struct.pack('<Q',nodes[i+1] if i+1<len(nodes) else root))
 u.mem_write(root+0x54,b'\1');u.mem_write(nodes[0]+0xd8,struct.pack('<Q',mount));u.mem_write(mount+0x38,struct.pack('<Q',root))
 u.mem_write(lower+0x70,struct.pack('<H',1 if name=='not-directory' else 2));u.mem_write(0x7abd760,struct.pack('<Q',0x12345678))
 allocated=set();borrowed=set();owned=[0];seen=[];observed_path=[]
 def string(at):return bytes(u.mem_read(at,1500)).split(b'\0')[0]
 def ret(value=0):u.reg_write(UC_ARM64_REG_X0,value);u.reg_write(UC_ARM64_REG_PC,u.reg_read(UC_ARM64_REG_LR))
 def hook(uc,pc,size,data):
  if pc not in callbacks:return
  fn=callbacks[pc];x0=uc.reg_read(UC_ARM64_REG_X0);x1=uc.reg_read(UC_ARM64_REG_X1);seen.append(fn)
  if fn=='alloc':assert not allocated;allocated.add(heap);ret(heap)
  elif fn=='getname':
   at=0 if name=='missing-name' else pointers[x0]
   if at:assert at not in borrowed;borrowed.add(at)
   ret(at)
  elif fn=='putname':assert x0 in borrowed;borrowed.remove(x0);ret()
  elif fn=='strlen':ret(len(string(x0)))
  elif fn=='namei':
   at=struct.unpack('<Q',uc.mem_read(x0,8))[0];observed_path.append(string(at).decode())
   assert observed_path[-1]=='/'.join(reversed(names))
   assert struct.unpack('<Q',uc.mem_read(x0+0x30,8))[0]==root
   if name=='namei-buffer':
    flags=struct.unpack('<I',uc.mem_read(x0+0x154,4))[0]
    uc.mem_write(x0+0x154,struct.pack('<I',flags|0x400));uc.mem_write(x0+0x168,struct.pack('<Q',extra));allocated.add(extra)
   if name!='namei-error':uc.mem_write(x0+0x28,struct.pack('<Q',lower));owned[0]+=1
   ret(5 if name=='namei-error' else 0)
  elif fn=='free':assert x1 in allocated;allocated.remove(x1);ret()
  elif fn=='put':assert x0==lower and owned[0]==1;owned[0]-=1;ret()
  elif fn=='printf':ret()
 u.hook_add(U.UC_HOOK_CODE,hook)
 u.reg_write(UC_ARM64_REG_SP,sp);u.reg_write(UC_ARM64_REG_X0,nodes[0]);u.reg_write(UC_ARM64_REG_X1,result);u.reg_write(UC_ARM64_REG_X2,0x1234);u.reg_write(UC_ARM64_REG_LR,0x101e000)
 u.emu_start(entry,0x101e000,count=30000)
 errno={'namei-error':5,'not-directory':2,'missing-name':2,'too-long':63}.get(name,0)
 assert u.reg_read(UC_ARM64_REG_PC)==0x101e000 and u.reg_read(UC_ARM64_REG_W0)==errno
 assert u.reg_read(UC_ARM64_REG_SP)==sp and not allocated and not borrowed
 assert struct.unpack('<Q',u.mem_read(result,8))[0]==(0 if errno else lower)
 assert owned[0]==int(not errno)
 cases.append(dict(name=name,errno=errno,path=observed_path,owned_vnode_returned=not bool(errno),all_temporary_resources_released=True,calls=seen))
a.output.parent.mkdir(parents=True,exist_ok=True)
a.output.write_text(json.dumps(dict(passed=True,kernel_sha256=proof['kernel_sha256'],cases=cases,
 function_sha256=hashlib.sha256(raw[B.backed(m,entry+bias,1):B.backed(m,entry+bias,1)+0x2bc]).hexdigest(),
 script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),actual_mount=False,device_accessed=False,
 scope='Real non-root union code; vnode names, allocation and lower namei are fixtures. No APFS execution.'),indent=2)+'\n')
print('PASS',len(cases),'non-root union path and ownership cases')
