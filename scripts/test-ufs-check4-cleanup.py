"""Actual carrier hook ABI and native instruction retirement; no hardware emulation."""
import argparse,hashlib,json,struct,sys,importlib.util
from pathlib import Path
import flush_trace_inputs as t
import legacy_observer_cleanup as clean
sys.path.insert(0,str(t.R/'out/python-tools'))
import unicorn as U
from unicorn.arm64_const import *
p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);w=p.parse_args().work
proof=json.loads((w/'kernel-proof.json').read_bytes());raw=(w/'kernel.macho').read_bytes();assert hashlib.sha256(raw).hexdigest()==proof['kernel_sha256']
B=t.builder();m=B.macho(raw);tar=proof['targets'];loc=proof['symbols'];tests=[]
regs=[getattr(U.arm64_const,'UC_ARM64_REG_X'+str(i)) for i in range(31)]
qregs=[getattr(U.arm64_const,'UC_ARM64_REG_Q'+str(i)) for i in range(32)]
def machine():
 u=U.Uc(U.UC_ARCH_ARM64,U.UC_MODE_ARM);u.mem_map(0x20000000,0x10000);pages=set()
 def fault(uc,access,a,size,value,data):
  page=a&~4095
  if page in pages:return False
  s=next(s for s in m['segments'] if s['va']<=page and page+4096<=s['va']+s['size']);n=max(0,min(4096,s['filesize']-page+s['va']));o=s['fileoff']+page-s['va'];u.mem_map(page,4096);u.mem_write(page,raw[o:o+n]+bytes(4096-n));pages.add(page);return True
 u.hook_add(U.UC_HOOK_MEM_UNMAPPED,fault)
 fault(u,0,tar['coarse_state'],0,0,None)
 return u
for ident,(name,low) in enumerate(clean.EVENTS,1):
 site=0xfffffff000000000+low;stop=tar['phase_'+name+'_resume'];result=not name.endswith('_before')
 for variant in ('zero','error','foreign','inactive'):
  u=machine();thread=0x20002000;u.reg_write(UC_ARM64_REG_TPIDR_EL1,thread+(16 if variant=='foreign' else 0));u.mem_write(tar['coarse_state']+104,struct.pack('<Q',0 if variant=='inactive' else thread))
  values=[0x10000+i*16 for i in range(31)];values[0]=14 if variant=='error' else 0;vectors=[(0x123456789abcdef0<<64)+i for i in range(32)];draws=[];hits=[]
  def hook(uc,pc,size,data):
   if pc==loc['draw']:
    draws.append((uc.reg_read(UC_ARM64_REG_X0),uc.reg_read(UC_ARM64_REG_X1)));lr=uc.reg_read(UC_ARM64_REG_LR)
    for reg in regs[:19]:uc.reg_write(reg,0xdeadbeef)
    uc.reg_write(UC_ARM64_REG_NZCV,0xf0000000);uc.reg_write(UC_ARM64_REG_PC,lr)
   elif pc==stop:hits.append(pc);uc.emu_stop()
  u.hook_add(U.UC_HOOK_CODE,hook)
  for visit in range(2):
   for r,v in zip(regs,values):u.reg_write(r,v)
   for r,v in zip(qregs,vectors):u.reg_write(r,v)
   u.reg_write(UC_ARM64_REG_SP,0x20008000);u.reg_write(UC_ARM64_REG_NZCV,0xa0000000);u.emu_start(site,0,count=5000)
   expected=values[:]
   if not result:expected[30]=site+4
   assert [u.reg_read(r) for r in regs]==expected,(name,variant,'GPR')
   assert [u.reg_read(r) for r in qregs]==vectors
   assert u.reg_read(UC_ARM64_REG_SP)==0x20008000 and u.reg_read(UC_ARM64_REG_NZCV)==0xa0000000
   assert len(hits)==visit+1
   wanted=[] if variant in ('foreign','inactive') else [(18,0xa0000000|ident)]+([(17,14),(20,0xe0000000|ident)] if result and variant=='error' else [])
   assert draws==wanted,(name,variant,draws,wanted)
  tests.append(dict(name=name,variant=variant,second_visit_silent=True))
# Exact restoration proof, including predecessor dense hook overrides.
a=json.loads((t.R/'reports/ufs-check-4-r1/legacy-source-audit.json').read_bytes());changes={int(x['address'],16):x for x in proof['changes']};restored=overridden=0
for row in a['rows']:
 x=row['patch'];addr=int(x['va'],16);low=addr&0xfffffff
 if not row['source_effects_only_diagnostic'] and low not in clean.MANUAL:continue
 now=raw[B.backed(m,addr,4):][:4].hex()
 if now==x['before']:restored+=1
 else:
  c=changes[addr];assert now==c['after'] and ('first-visit coarse milestone:' in c['reason'] or ('bounded PID1' in c['reason'] and low in {s for n,s in clean.EVENTS})),c
  overridden+=1
assert restored+overridden==501
assert 'coarse_exec_hold' not in loc and 'exec_confirmed_hold' not in loc
for key,site in [('exec_entry_old',0x769ce3c),('exec_namei_target',0x769bdd8)]:
 parent=json.loads((t.BASE/'build.json').read_bytes());assert tar[key]==int(parent['probe']['symbols']['probe_dense_'+format(site,'x')+'_replay'],16)
tests.append(dict(name='501 legacy dense bodies bypassed',native_restored=restored,compact_replacements=overridden))
# Five former hold conditions all reach real task_clear_return_wait with unchanged arguments.
for active,commit,flag,match in [(0,1,2,1),(1,0,2,1),(1,1,2,0),(1,1,1,1),(1,1,2,1)]:
 u=machine();task=0x20001000;state=0xfffffff0084e7088
 # map old state lazily by writing through the backing segment page
 try:u.mem_write(state,bytes(80))
 except U.UcError:
  page=state&~4095;u.mem_map(page,4096);u.mem_write(page,raw[B.backed(m,page):][:4096])
 u.mem_write(state,struct.pack('<10Q',active,commit,0,0,0,0,0,0,0,task if match else task+16));u.reg_write(UC_ARM64_REG_X0,task);u.reg_write(UC_ARM64_REG_X1,flag);u.reg_write(UC_ARM64_REG_SP,0x20008000)
 stop=tar['phase_release_before_resume'];u.emu_start(0xfffffff00769d230,stop,count=5000)
 assert u.reg_read(UC_ARM64_REG_PC)==stop and u.reg_read(UC_ARM64_REG_X0)==task and u.reg_read(UC_ARM64_REG_X1)==flag and u.reg_read(UC_ARM64_REG_LR)==0xfffffff00769d234
 tests.append(dict(name='native release continues',active=active,commit=commit,flag=flag,match=match))
# First error is sticky across later error and success stages; native return remains intact.
u=machine();u.reg_write(UC_ARM64_REG_TPIDR_EL1,0x20002000);u.mem_write(tar['coarse_state']+104,struct.pack('<Q',0x20002000));sticky_draws=[]
def sticky_hook(uc,pc,size,data):
 if pc==loc['draw']:
  sticky_draws.append((uc.reg_read(UC_ARM64_REG_X0),uc.reg_read(UC_ARM64_REG_X1)));uc.reg_write(UC_ARM64_REG_PC,uc.reg_read(UC_ARM64_REG_LR))
u.hook_add(U.UC_HOOK_CODE,sticky_hook)
for name,error in [('getattr_after',5),('authorize_after',13),('read_after',0)]:
 low=dict(clean.EVENTS)[name];u.reg_write(UC_ARM64_REG_X0,error);u.reg_write(UC_ARM64_REG_SP,0x20008000);u.emu_start(0xfffffff000000000+low,tar['phase_'+name+'_resume'],count=5000);assert u.reg_read(UC_ARM64_REG_X0)==error
assert [v for row,v in sticky_draws if row==17]==[5] and [v for row,v in sticky_draws if row==20]==[0xe0000002]
assert struct.unpack('<II',u.mem_read(tar['coarse_state']+264,8))==(5,2)
# Mixed FSCompression entry retains real helper call and native replay but no old exec-state write.
u=machine();values=[0x10000+i*16 for i in range(31)];helper_hits=[];old_state_writes=[]
def mixed_hook(uc,pc,size,data):
 if pc==0xfffffff0084e65dc:
  helper_hits.append(pc);lr=uc.reg_read(UC_ARM64_REG_LR)
  for r in regs[9:29]:uc.reg_write(r,0xdeadbeef)
  uc.reg_write(UC_ARM64_REG_NZCV,0xf0000000);uc.reg_write(UC_ARM64_REG_PC,lr)
def mixed_write(uc,access,addr,size,value,data):
 if 0xfffffff0084e7088<=addr<0xfffffff0084e70e8:old_state_writes.append(addr)
u.hook_add(U.UC_HOOK_CODE,mixed_hook);u.hook_add(U.UC_HOOK_MEM_WRITE,mixed_write)
for r,v in zip(regs,values):u.reg_write(r,v)
u.reg_write(UC_ARM64_REG_SP,0x20008000);u.reg_write(UC_ARM64_REG_NZCV,0xa0000000)
u.emu_start(0xfffffff00769d5f4,0xfffffff00769ce3c,count=5000)
values[30]=0xfffffff00769d5f8
assert helper_hits==[0xfffffff0084e65dc] and not old_state_writes
assert [u.reg_read(r) for r in regs]==values and u.reg_read(UC_ARM64_REG_SP)==0x20008000 and u.reg_read(UC_ARM64_REG_NZCV)==0xa0000000
# Conservative source classifier must reject effects outside diagnostic storage.
sp=importlib.util.spec_from_file_location('retirement_audit',t.R/'scripts/audit-legacy-observer-retirement.py');audit=importlib.util.module_from_spec(sp);sp.loader.exec_module(audit)
for bad in ('bl native_function','str x9, [x0]','movk x0, #1','b probe_test','msr tpidr_el1, x9'):
 assert not audit.audit('probe_test:\n PROBE_SAVE\n '+bad+'\n PROBE_RESTORE','probe_test')[0],bad
for low in (0x73c7378,0x729e804,0x5194248,0x5194278,0x5194290):
 x=next(x for x in parent['patches'] if x.get('va')==hex(0xfffffff000000000+low));assert raw[B.backed(m,int(x['va'],16),4):][:4].hex()==x['before']
(w/'cleanup-tests.json').write_text(json.dumps(dict(passed=True,kernel_sha256=proof['kernel_sha256'],tests=tests,scope='Actual ARM64 observer ABI and original native instructions. Draw helper explicitly substituted in ABI cases. No APFS, UFS or scheduler runtime acceptance.'),indent=2)+'\n');print('PASS',len(tests),restored,overridden)

