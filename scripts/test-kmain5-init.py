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
for idx,(name,site) in enumerate([('init_alloc',0x769d2f8),('init_path',0x769d4e0),('init_copy',0x769d53c),('init_exec',0x769d5f4),('init_hold',0x84db290)]):
 for value in (0,14):
  u=machine(site);values=[0x10000+i*16 for i in range(31)];values[0]=value;vectors=[(0x123456789abcdef0<<64)+i for i in range(32)]
  stop={'init_alloc':tar['init_alloc_target'],'init_path':tar['init_path_resume'],'init_copy':tar['init_copy_error' if value else 'init_copy_ok'],'init_exec':tar['init_exec_old'],'init_hold':loc['init_confirmed_hold']}[name]
  try:u.mem_map(stop&~4095,4096)
  except U.UcError:pass
  draws=[];hits=[]
  def hook(u,pc,size,_):
   if pc==loc['draw']:
    draws.append((u.reg_read(UC_ARM64_REG_X0),u.reg_read(UC_ARM64_REG_X1)));lr=u.reg_read(UC_ARM64_REG_LR)
    for r in regs[:19]:u.reg_write(r,0xdeadbeef)
    u.reg_write(UC_ARM64_REG_NZCV,0xf0000000);u.reg_write(UC_ARM64_REG_PC,lr)
   elif pc==stop:hits.append(pc);u.emu_stop()
  u.hook_add(U.UC_HOOK_CODE,hook)
  for visit in range(2):
   for r,v in zip(regs,values):u.reg_write(r,v)
   for r,v in zip(qregs,vectors):u.reg_write(r,v)
   u.reg_write(UC_ARM64_REG_SP,0x20008000);u.reg_write(UC_ARM64_REG_NZCV,0xa0000000);u.emu_start(site,0,count=3000)
   expect=values[:]
   if name=='init_alloc':expect[30]=proof['targets']['init_alloc_resume']
   assert [u.reg_read(r) for r in regs]==expect,(name,'registers')
   assert [u.reg_read(r) for r in qregs]==vectors
   assert u.reg_read(UC_ARM64_REG_NZCV)==0xa0000000
   assert u.reg_read(UC_ARM64_REG_SP)==0x20008000-(160 if name=='init_path' else 0)
   assert len(hits)==visit+1
   assert draws==[(16,1<<idx)]+([(17,value)] if name=='init_copy' else [])
  tests.append(dict(name=name,value=value,passed=True,second_visit_silent=True))
for name,active,commit,flag,match in [('inactive',0,1,2,True),('uncommitted',1,0,2,True),('foreign',1,1,2,False),('wrong-flag',1,1,1,True),('held',1,1,2,True)]:
 u=machine(0x84db088);state=0x84e7088;task=0x20001000
 u.mem_write(state,struct.pack('<10Q',active,commit,0,0,0,0,0,0,0,task if match else task+16));u.reg_write(UC_ARM64_REG_X0,task);u.reg_write(UC_ARM64_REG_X1,flag);u.reg_write(UC_ARM64_REG_SP,0x20008000)
 stop=loc['init_confirmed_hold'] if name=='held' else 0x72a1ab0
 try:u.mem_map(stop&~4095,4096)
 except U.UcError:pass
 draws=[];hit=[]
 def guard(u,pc,size,_):
  if pc==loc['draw']:
   draws.append((u.reg_read(UC_ARM64_REG_X0),u.reg_read(UC_ARM64_REG_X1)));u.reg_write(UC_ARM64_REG_PC,u.reg_read(UC_ARM64_REG_LR))
  elif pc==stop:hit.append(pc);u.emu_stop()
 u.hook_add(U.UC_HOOK_CODE,guard);u.emu_start(0x84db088,0,count=10000)
 assert hit==[stop] and draws==([(16,16)] if name=='held' else []),(name,draws,hex(u.reg_read(UC_ARM64_REG_PC)))
 assert u.reg_read(UC_ARM64_REG_X0)==task and u.reg_read(UC_ARM64_REG_X1)==flag
 tests.append(dict(name='native-guard-'+name,passed=True))
report=dict(passed=True,kernel_sha256=proof['kernel_sha256'],tests=tests,external_calls_modeled=True,device_execution=False)
(w/'init-tests.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS',len(tests),'init and native guard cases')
