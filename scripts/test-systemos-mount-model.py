"""Execute genuine linked SystemOS mount code with explicit VFS/IOKit fixtures.
Does not execute a filesystem mount, UFS, trust-cache acceptance or userland.
"""
import argparse,hashlib,json,struct,sys
from pathlib import Path
import flush_trace_inputs as trace
sys.path.insert(0,str(trace.R/'out/python-tools'))
import unicorn as U
from unicorn.arm64_const import *
p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);a=p.parse_args();w=a.work
proof=json.loads((w/'kernel-proof.json').read_bytes());raw=(w/'kernel.macho').read_bytes()
assert hashlib.sha256(raw).hexdigest()==proof['kernel_sha256']
B=trace.builder();m=B.macho(raw);sym=m['symbols']|proof['targets'];local=proof['symbols'];seg=m['segments'][-1]
imports={n:int(v,16) for n,v in json.loads((w/'linked/imports.json').read_bytes()).items()}
regs=[getattr(U.arm64_const,'UC_ARM64_REG_X'+str(i)) for i in range(31)]
old,new,proc,oldmp,newmp,olddev,newdev,stat1,stat2,result,sp=(0x20002000,0x20002100,0x20003000,0x20004000,0x20004100,0x20005000,0x20005100,0x20007000,0x20008000,0x20009000,0x20018000)
user=0x40000000;sentinel=0x50000000;device=0x06000002;tests=[]
def run(case='success',wrapper=False,repeat=False):
 u=U.Uc(U.UC_ARCH_ARM64,U.UC_MODE_ARM);pages=set()
 def mapping(addr,size):
  for page in range(addr&~4095,(addr+size+4095)&~4095,4096):
   if page not in pages:u.mem_map(page,4096);pages.add(page)
 def code(addr,size):
  mapping(addr,size);off=B.backed(m,addr,size);u.mem_write(addr,raw[off:off+size])
 code(seg['va'],proof['mapped_end']-seg['va']);mapping(0x20000000,0x20000);mapping(user,0x10000);mapping(sentinel,4096)
 # XNU8796 mount.h packs vfsstatfs at 4 bytes; f_fstypename is offset 80.
 u.mem_write(stat1+80,b'hfs\0' if case=='lower-fstype' else b'apfs\0');u.mem_write(stat2+80,b'apfs\0')
 stubs=dict(imports)
 stubs['_systemos_failure_draw']=local['draw']
 for n in ('_nuwa_ufs_root_authorize','_nuwa_ufs_select_systemos','_nuwa_ufs_systemos_device_authorized','_vm_map_page_size','_memorystatus_init_at_boot_snapshot','_panic'):stubs[n]=sym[n]
 for addr in set(stubs.values()):
  try:code(addr,8)
  except StopIteration:
   assert any(s['va']<=addr and addr+8<=s['va']+s['size'] for s in m['segments']),hex(addr)
   mapping(addr,8)
 byaddr={v:k for k,v in stubs.items()};refs={};calls=[];lookups=0;mounted=False;finished=False;panic=False;snapshots=0;failure_displays=0
 def owned(v):refs[v]=refs.get(v,0)+1;return v
 def string(addr):return bytes(u.mem_read(addr,80)).split(b'\0')[0]
 def ret(value=0):u.reg_write(UC_ARM64_REG_X0,value&((1<<64)-1));u.reg_write(UC_ARM64_REG_PC,u.reg_read(UC_ARM64_REG_LR))
 def hook(uc,pc,size,data):
  nonlocal lookups,mounted,finished,panic,snapshots,failure_displays
  if pc==sentinel or (wrapper and pc==sym['systemos_resume']):finished=True;uc.emu_stop();return
  if pc not in byaddr:return
  name=byaddr[pc];x=[uc.reg_read(r) for r in regs[:5]];calls.append(name)
  if name=='_current_proc':ret(proc)
  elif name=='_proc_pid':assert x[0]==proc;ret(2 if case=='pid' else 1)
  elif name=='_vfs_context_current':ret(0x20006000)
  elif name=='_vnode_lookup':
   assert string(x[0])==b'/' and x[1]==0;lookups+=1
   error=(case=='lower-lookup' and lookups==1) or (case=='upper-lookup' and lookups==2)
   if not error:uc.mem_write(x[2],struct.pack('<Q',owned(old if lookups==1 else new)))
   ret(2 if error else 0)
  elif name=='_vnode_put':assert refs.get(x[0],0)>0,(case,'unowned put',hex(x[0]));refs[x[0]]-=1;ret()
  elif name=='_vnode_mount':ret(oldmp if x[0]==old else newmp)
  elif name=='_vfs_statfs':ret(stat1 if x[0]==oldmp else stat2)
  elif name=='_vfs_flags':ret((0x21 if case=='lower-union' else 1) if x[0]==oldmp else (1 if case=='upper-flags' else 0x21))
  elif name=='_vnode_isvroot':ret(1)
  elif name=='_vfs_devvp':ret(owned(olddev if x[0]==oldmp else newdev))
  elif name=='_vnode_specrdev':ret(0x06000001 if x[0]==olddev else device+(1 if case=='wrong-device' else 0))
  elif name=='_vfs_vnodecovered':ret(owned(new if case=='wrong-cover' else old))
  elif name=='_nuwa_ufs_root_authorize':assert x[:2]==[old,0x06000001];ret(0 if case=='lower-auth' else 1)
  elif name=='_nuwa_ufs_select_systemos':
   if case!='selection':uc.mem_write(x[0],struct.pack('<I',device)+b'/dev/disk0s2\0'+bytes(52))
   ret(0 if case=='selection' else 1)
  elif name=='_nuwa_ufs_systemos_device_authorized':assert x[0]==device;ret(0 if case=='upper-auth' else 1)
  elif name in ('_copyout','___copyout_chk'):
   assert user<=x[1] and x[1]+x[2]<=user+0x350
   if case!='copyout':uc.mem_write(x[1],bytes(uc.mem_read(x[0],x[2])))
   ret(14 if case=='copyout' else 0)
  elif name=='_mount':
   assert x[0]==proc;tp,path,flags,pad,arg=struct.unpack('<QQIIQ',uc.mem_read(x[1],32))
   assert (tp,path,flags,arg)==(user+0x100,user+0x120,0x21,user+0x200)
   assert string(tp)==b'apfs' and string(path)==b'/' and string(user+0x160)==b'/dev/disk0s2'
   data=bytes(uc.mem_read(arg,0x150));assert struct.unpack_from('<QQH',data)==(user+0x160,1,1)
   assert struct.unpack_from('<II',data,0x144)==(99,99)
   mounted=case!='mount';ret(13 if case=='mount' else 0)
  elif name in ('_strcmp','_strncmp'):ret(0 if string(x[0])==string(x[1]) else 1)
  elif name in ('_bzero','___bzero'):uc.mem_write(x[0],bytes(x[1]));ret()
  elif name in ('_memset','___memset_chk'):uc.mem_write(x[0],bytes([x[1]&255])*x[2]);ret(x[0])
  elif name in ('_memcpy','_memmove','___memcpy_chk'):uc.mem_write(x[0],bytes(uc.mem_read(x[1],x[2])));ret(x[0])
  elif name=='_OSCompareAndSwap':
   value=struct.unpack('<I',uc.mem_read(x[2],4))[0];ok=value==x[0]
   if ok:uc.mem_write(x[2],struct.pack('<I',x[1]))
   ret(int(ok))
  elif name=='_vm_map_page_size':assert x[0]==0x2000a000;ret(16384)
  elif name=='_memorystatus_init_at_boot_snapshot':snapshots+=1;ret()
  elif name=='_systemos_failure_draw':
   ph,er,mo=struct.unpack('<IiI',uc.mem_read(sym['_nuwa_systemos_mount_result'],12))
   assert x[0]==16 and x[1]==(0xe0000000|((mo&1)<<24)|((ph&255)<<16)|(er&65535))
   failure_displays+=1;ret()
  elif name=='_panic':panic=True;assert string(x[0]).startswith(b'SystemOS mount rejected:');assert struct.unpack('<QQQ',uc.mem_read(uc.reg_read(UC_ARM64_REG_SP),24))==struct.unpack('<IiI',uc.mem_read(sym['_nuwa_systemos_mount_result'],12));uc.emu_stop()
  else:raise AssertionError(('unmodelled external',name,hex(pc)))
 u.hook_add(U.UC_HOOK_CODE,hook)
 if wrapper:code(0xfffffff00769d2f8,8)
 def execute():
  for i,r in enumerate(regs):u.reg_write(r,0x30000000+i*16)
  u.reg_write(UC_ARM64_REG_X0,proc);u.reg_write(UC_ARM64_REG_X1,0 if case=='scratch' else user);u.reg_write(UC_ARM64_REG_X2,16384);u.reg_write(UC_ARM64_REG_X3,result)
  u.reg_write(UC_ARM64_REG_X19,proc);u.reg_write(UC_ARM64_REG_X20,0x2000a000);u.reg_write(UC_ARM64_REG_SP,sp);u.reg_write(UC_ARM64_REG_LR,sentinel)
  u.mem_write(sp+0x28,struct.pack('<Q',user))
  u.emu_start(0xfffffff00769d2f8 if wrapper else sym['_nuwa_systemos_mount_initial'],0,count=30000)
 execute()
 errno,phase,mountbit={'success':(0,7,1),'pid':(22,0,0),'scratch':(22,0,0),'lower-lookup':(2,1,0),'lower-fstype':(80,2,0),'lower-union':(80,2,0),'lower-auth':(80,2,0),'selection':(6,3,0),'copyout':(14,4,0),'mount':(13,5,0),'upper-lookup':(2,6,1),'upper-flags':(80,6,1),'wrong-cover':(80,6,1),'wrong-device':(80,6,1),'upper-auth':(80,6,1)}[case]
 result_at=sym['_nuwa_systemos_mount_result'] if wrapper else result
 assert struct.unpack('<IiI',u.mem_read(result_at,12))==(phase,errno,mountbit),(case,'result',bytes(u.mem_read(result_at,12)).hex())
 assert all(v==0 for v in refs.values()),(case,refs)
 assert mounted==bool(mountbit)
 assert failure_displays==int(wrapper and bool(errno))
 if wrapper:
  assert (finished,panic,snapshots)==(not bool(errno),bool(errno),0 if errno else 1)
  if not errno:assert u.reg_read(UC_ARM64_REG_SP)==sp and u.reg_read(UC_ARM64_REG_X19)==proc and u.reg_read(UC_ARM64_REG_X20)==0x2000a000
 else:assert finished and not panic and u.reg_read(UC_ARM64_REG_W0)==errno
 if repeat:
  calls_before=len(calls);execute();assert u.reg_read(UC_ARM64_REG_W0)==37
  assert '_mount' not in calls[calls_before:] and struct.unpack('<IiI',u.mem_read(result,12))==(0,37,0)
 tests.append(dict(case=case,wrapper=wrapper,repeat=repeat,phase=phase,error=errno,mounted=mountbit,references_balanced=True,external_calls=calls))
for case in ('success','pid','scratch','lower-lookup','lower-fstype','lower-union','lower-auth','selection','copyout','mount','upper-lookup','upper-flags','wrong-cover','wrong-device','upper-auth'):run(case,repeat=case=='success')
for case in ('success','mount','upper-auth'):run(case,wrapper=True)
out=dict(passed=True,kernel_sha256=proof['kernel_sha256'],tests=tests,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),actual_mount=False,device_accessed=False,scope='Actual linked caller/C bridge/functional trampoline; explicit synthetic VFS, selector, auth and syscall fixtures. No UFS, filesystem or EL0 execution.')
(w/'systemos-mount-tests.json').write_text(json.dumps(out,indent=2)+'\n');print('PASS',len(tests),'SystemOS caller and trampoline cases')
