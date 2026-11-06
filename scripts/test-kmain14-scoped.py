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
sites=[('exec_entry',0x769ce3c,'exec_entry_old'),('exec_namei',0x769bdd8,'exec_namei_target'),('exec_lookup',0x7441328,'exec_lookup_old'),('exec_apfs_entry',0x51a1f68,'exec_apfs_entry_old'),('exec_namei_enter',0x769bdd4,'exec_namei_enter_old'),('exec_apfs_lock',0x51a2278,'exec_apfs_lock_old'),('exec_hold',0x84db290,None),('exec_vnop_return',0x744132c,'exec_vnop_return_old'),('exec_apfs_locked',0x51a227c,'exec_apfs_locked_old')]
for idx,(name,site,target) in enumerate(sites):
 for variant in (('zero','error','foreign','inactive','other-ndp') if idx in (2,3,5,7,8) else ('zero','error','foreign','inactive')):
  value=14 if variant=='error' else 0
  u=machine(site);values=[0x10000+i*16 for i in range(31)];values[0]=value;values[30]=0xfffffff00769d5f8
  if idx==2:
   values[0]=0x20003000;u.mem_write(values[0]+0xd0,struct.pack('<Q',0x20004000));u.mem_write(0x20004028,struct.pack('<Q',0xfffffff0051a1f68));u.mem_map(tar['vnop_lookup_desc']&~4095,4096);u.mem_write(tar['vnop_lookup_desc'],struct.pack('<I',5))
  if idx==3:
   values[0]=0x20003100;u.mem_write(values[0]+16,struct.pack('<Q',0x20003200));u.mem_write(tar['coarse_state']+128,struct.pack('<Q',0x20003200+(16 if variant=='other-ndp' else 0)))
  if idx in (5,8):u.mem_write(tar['coarse_state']+136,struct.pack('<Q',0x20008000+(16 if variant=='other-ndp' else 0)))
  if idx==8:
   values[25]=0x20004000;u.mem_write(values[25]+0x98,struct.pack('<Q',0xc00000000008))
  if idx==0 and variant in ('foreign','inactive'):values[30]+=4
  u.mem_write(0x20008000+28,struct.pack('<I',4096 if value else 0))
  thread=0x20002000;u.reg_write(UC_ARM64_REG_TPIDR_EL1,thread if variant!='foreign' or idx==0 else thread+16)
  if idx and variant!='inactive':u.mem_write(tar['coarse_state']+104,struct.pack('<Q',thread))
  u.mem_write(tar['coarse_state']+112,struct.pack('<Q',values[19]+(16 if variant=='other-ndp' else 0)))
  vectors=[(0x123456789abcdef0<<64)+i for i in range(32)]
  stop=(tar[{5:'exec_lookup_zero',7:'exec_vnop_zero'}[idx]] if idx==7 and value==0 else tar[target]) if target else loc['exec_confirmed_hold']
  try:u.mem_map(stop&~4095,4096)
  except U.UcError:pass
  draws=[];hits=[]
  def hook(u,pc,size,_):
   if pc==loc['draw']:
    draws.append((u.reg_read(UC_ARM64_REG_X0),u.reg_read(UC_ARM64_REG_X1)));lr=u.reg_read(UC_ARM64_REG_LR)
    for reg in regs[:19]:u.reg_write(reg,0xdeadbeef)
    u.reg_write(UC_ARM64_REG_NZCV,0xf0000000);u.reg_write(UC_ARM64_REG_PC,lr)
   elif pc==stop:hits.append(pc);u.emu_stop()
  u.hook_add(U.UC_HOOK_CODE,hook)
  for visit in range(2):
   for reg,val in zip(regs,values):u.reg_write(reg,val)
   for reg,val in zip(qregs,vectors):u.reg_write(reg,val)
   u.reg_write(UC_ARM64_REG_SP,0x20008000);u.reg_write(UC_ARM64_REG_NZCV,0xa0000000);u.emu_start(site,0,count=3000)
   expected=values[:]
   if idx in (2,4):expected[30]=0xfffffff00744132c if idx==2 else 0xfffffff00769bdd8
   if idx==5:expected[30]=0xfffffff0051a227c
   if idx==8:expected[8]=0xc00000000008
   assert [u.reg_read(reg) for reg in regs]==expected,(name,variant,'GPR')
   assert [u.reg_read(reg) for reg in qregs]==vectors
   assert u.reg_read(UC_ARM64_REG_NZCV)==0xa0000000 and u.reg_read(UC_ARM64_REG_SP)==0x20008000-(0x140 if idx==3 else 0)
   assert len(hits)==visit+1
   if idx==1 and variant not in ('foreign','inactive'):assert struct.unpack('<Q',u.mem_read(tar['coarse_state']+112,8))[0]==0
   want=[] if variant in ('foreign','inactive','other-ndp') else [(16,1<<idx)]+([(19,value)] if idx==1 else [(17,value)] if idx==7 else [])
   assert draws==want,(name,variant,draws)
  tests.append(dict(name=name,variant=variant,passed=True,second_visit_silent=True))
for name,active,commit,flag,match in [('inactive',0,1,2,True),('uncommitted',1,0,2,True),('foreign',1,1,2,False),('wrong-flag',1,1,1,True),('held',1,1,2,True)]:
 u=machine(0x84db088);u.reg_write(UC_ARM64_REG_TPIDR_EL1,0x20002000);u.mem_write(tar['coarse_state']+104,struct.pack('<Q',0x20002000));state=0x84e7088;task=0x20001000
 u.mem_write(state,struct.pack('<10Q',active,commit,0,0,0,0,0,0,0,task if match else task+16));u.reg_write(UC_ARM64_REG_X0,task);u.reg_write(UC_ARM64_REG_X1,flag);u.reg_write(UC_ARM64_REG_SP,0x20008000)
 stop=loc['exec_confirmed_hold'] if name=='held' else 0x72a1ab0
 try:u.mem_map(stop&~4095,4096)
 except U.UcError:pass
 draws=[];hit=[]
 def guard(u,pc,size,_):
  if pc==loc['draw']:
   draws.append((u.reg_read(UC_ARM64_REG_X0),u.reg_read(UC_ARM64_REG_X1)));u.reg_write(UC_ARM64_REG_PC,u.reg_read(UC_ARM64_REG_LR))
  elif pc==stop:hit.append(pc);u.emu_stop()
 u.hook_add(U.UC_HOOK_CODE,guard);u.emu_start(0x84db088,0,count=10000)
 assert hit==[stop] and draws==([(16,64)] if name=='held' else []),(name,draws,hex(u.reg_read(UC_ARM64_REG_PC)))
 assert u.reg_read(UC_ARM64_REG_X0)==task and u.reg_read(UC_ARM64_REG_X1)==flag
 tests.append(dict(name='native-guard-'+name,passed=True))
report=dict(passed=True,kernel_sha256=proof['kernel_sha256'],tests=tests,external_calls_modeled=True,device_execution=False)
(w/'exec-tests.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS',len(tests),'init and native guard cases')
