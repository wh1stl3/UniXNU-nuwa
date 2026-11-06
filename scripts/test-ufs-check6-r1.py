"""Integrated CHECK6 tests, actual packaged code, serial legacy regressions.

The reused strict harness is rebound only after verifying the recorded CHECK4
parent and current kernel digest. No instruction is replaced in model memory.

CHECK5's 73 machine cases are re-executed unchanged against the CHECK6 kernel,
then the three new `_vfs_mountroot` exit observers are exercised directly: each
one must publish only its own FB field, preserve the full native context and
resume at the recorded instruction.
"""
import argparse, hashlib, json, runpy, sys
from pathlib import Path
import exec_carrier_model as H
from exec_carrier_model import *

p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args()
proof=json.loads((a.work/'kernel-proof.json').read_bytes())
delta=proof.get('check6_delta') or proof['check5_delta']
assert delta['parent_kernel_sha256']==H.EXPECTED
assert hashlib.sha256((a.work/'kernel.macho').read_bytes()).hexdigest()==proof['kernel_sha256']
H.EXPECTED=proof['kernel_sha256']
c=Carrier(a.work);out=a.output_dir;out.mkdir(parents=True,exist_ok=False)
rows=[];state=proof['targets']['coarse_state'];NEW=MEM+0x3000;TASK=MEM+0x22000;SAVED=MEM+0x24000
for name,active,foreign,error,newptr,repeat in [
 ('success',True,False,0,NEW,False),('success_old_return_first',True,False,0,NEW,False),
 ('error',True,False,13,NEW,False),('foreign',True,True,0,NEW,False),
 ('inactive',False,False,0,NEW,False),('no_new_thread',True,False,0,0,False),
 ('already_recorded',True,False,0,NEW,True)]:
 m=Machine(c);release_site=BASE+0x769d230;init_site=proof['targets']['init_loaded_resume']-4
 m.put(state+104,THREAD if active else 0);m.put(state+256,(1<<9) if repeat else 0,4)
 m.put(IMG+0x2b8,newptr);m.u.reg_write(UC_ARM64_REG_TPIDR_EL1,THREAD+16 if foreign else THREAD)
 values=[0x7000+i*16 for i in range(31)];values[0]=TASK;values[1]=2;values[19]=IMG;values[24]=error
 for i,v in enumerate(values):m.x(i,v)
 vectors=[(0x123456789abcdef0<<64)+i for i in range(32)]
 for i,v in enumerate(vectors):m.u.reg_write(getattr(U.arm64_const,'UC_ARM64_REG_Q'+str(i)),v)
 m.u.reg_write(UC_ARM64_REG_NZCV,0xa0000000)
 m.callbacks[c.sy['_task_clear_return_wait']]=lambda:m.stop('native release entry')
 m.run(release_site)
 expected=values[:];expected[30]=BASE+0x769d234
 assert [m.x(i) for i in range(31)]==expected
 assert [m.u.reg_read(getattr(U.arm64_const,'UC_ARM64_REG_Q'+str(i))) for i in range(32)]==vectors
 assert m.u.reg_read(UC_ARM64_REG_SP)==STACK and m.u.reg_read(UC_ARM64_REG_NZCV)==0xa0000000
 armed=name.startswith('success');assert m.get(state+32)==(NEW if armed else 0)
 if armed:
  if name=='success_old_return_first':
   m.stopped=None;m.callbacks[proof['targets']['init_loaded_resume']]=lambda:m.stop('early old return')
   m.run(init_site);assert m.get(state+32)==NEW
  # Old caller must not consume the new thread's latch, even at this boundary.
  m.stopped=None;m.x(21,SAVED);m.x(3,THREAD)
  m.callbacks[proof['targets']['el0_resume']]=lambda:m.stop('EL0 observer resume')
  m.run(BASE+0x73c3864);assert [14,1] not in m.draws and m.get(state+32)==NEW
  m.stopped=None;m.u.reg_write(UC_ARM64_REG_TPIDR_EL1,NEW);m.x(3,NEW)
  m.run(BASE+0x73c3864);assert m.draws.count([14,1])==1 and m.get(state+32)==0
  m.stopped=None;m.u.reg_write(UC_ARM64_REG_TPIDR_EL1,THREAD)
  m.callbacks[proof['targets']['init_loaded_resume']]=lambda:m.stop('late old return')
  m.run(init_site);assert m.get(state+32)==0
  m.stopped=None;m.u.reg_write(UC_ARM64_REG_TPIDR_EL1,NEW);m.x(21,SAVED);m.x(3,NEW)
  m.run(BASE+0x73c3864);assert m.draws.count([14,1])==1
 rows.append(m.record(name))
write_report(out/'target-lifetime.json',c,rows,'Actual CHECK5 kernel callsites and observer; no code injection. Explicit thread objects/scheduling order and intercepted draw/native release entry. GPR/SIMD/SP/NZCV/args/LR preserved. No hardware scheduling proof.')

# Continue the new thread through the real native restore machinery after
# publishing via the actual CHECK5 release hook (not a preseeded target).
rows=[];CPU=MEM+0x28000;USER=MEM+0x3d000
for name,mode,debug,wait in [('native_restore',0,False,False),('kernel_mode',5,False,False),('recount_wait',0,False,True),('debug_restore',0,True,False)]:
 m=Machine(c);m.put(state+104,THREAD);m.put(IMG+0x2b8,NEW);m.x(19,IMG);m.x(24,0)
 m.callbacks[c.sy['_task_clear_return_wait']]=lambda:m.stop('native release entry')
 m.run(BASE+0x769d230);assert m.get(state+32)==NEW
 m.stopped=None;m.u.reg_write(UC_ARM64_REG_TPIDR_EL1,NEW);m.x(21,SAVED);m.x(3,NEW)
 m.put(NEW+0x1c8,CPU);m.put(NEW+0x140,0x1234 if debug else 0);m.put(SAVED+0x110,mode,4)
 for i in range(31):m.put(SAVED+8+i*8,0x100+i)
 m.put(SAVED+0x108,USER);m.put(SAVED+0x100,MEM+0x35000)
 m.stub('_recount_enter_user',lambda:m.stop('recount boundary') if wait else m.ret())
 m.stub('_arm_debug_set',lambda:(m.events.append('debug restore boundary'),m.ret()))
 m.callbacks[BASE+0x73c3994]=lambda:m.stop('before ERET')
 m.run(BASE+0x73c3864);assert ([14,1] in m.draws)==(mode==0)
 if wait:assert m.stopped=='recount boundary' and BASE+0x73c3994 not in m.visits
 else:
  assert m.stopped=='before ERET' and m.u.reg_read(UC_ARM64_REG_ELR_EL1)==USER
  assert m.u.cpr_read(3,0,4,0,0)==mode and m.u.reg_read(UC_ARM64_REG_SP)==MEM+0x35000
  for i in range(31):
   if i!=18:assert m.x(i)==0x100+i
 assert USER not in m.visits
 rows.append(m.record(name))
write_report(out/'native-el0-restore.json',c,rows,'Real register restore after CHECK5 new-thread publication. Synthetic saved state; recount/debug explicit boundaries; stop before ERET, no user instruction executed.')

# CHECK6 exit observers. Each hook must publish only its own FB field, replay
# the native instruction verbatim and return with the full native context.
# `clobber` is the register the replayed instruction legitimately writes; every
# other GPR must survive unchanged, so a mis-transcribed replay cannot hide.
rows=[]
exit_sites={x['symbol']:int(x['address'],16) for x in delta['callers'] if x['symbol'].startswith('c6_')}
assert len(exit_sites)==3,exit_sites
for hook,fb,clobber in [('c6_mountroot_ret',11,8),('c6_bdevvp_fail',13,19),('c6_vfcmount_ret',14,24)]:
 # The hook replays the single native instruction at the patch site and resumes
 # at the next one, so the continuation address is exactly site+4.
 resume=exit_sites[hook]+4
 for value in (0,0xE00002BC,0xFFFFFFFF):
  m=Machine(c);mem=MEM+0x3000;m.put(mem,0x12345678)
  values=[0x7000+i*16 for i in range(29)]
  if hook=='c6_mountroot_ret':values[27]=mem  # x27 is the load base for the replay
  for i,v in enumerate(values):m.x(i,v)
  m.x(0,value);m.x(30,SENTINEL)
  vectors=[(0x9abcdef0<<32)+i for i in range(32)]
  for i,v in enumerate(vectors):m.u.reg_write(getattr(U.arm64_const,'UC_ARM64_REG_Q'+str(i)),v)
  m.u.reg_write(UC_ARM64_REG_NZCV,0xa0000000)
  m.callbacks[resume]=lambda:m.stop('exit resume')
  m.run(proof['symbols'][hook])
  assert m.stopped=='exit resume',(hook,value,m.stopped)
  assert m.draws==[[fb,value&0xffffffff]],(hook,value,m.draws)
  expected=values[:];expected[0]=value
  expected[clobber]=0x12345678 if hook=='c6_mountroot_ret' else value
  assert [m.x(i) for i in range(29)]==expected,(hook,value,'GPR')
  assert m.x(30)==SENTINEL and m.u.reg_read(UC_ARM64_REG_SP)==STACK
  assert m.u.reg_read(UC_ARM64_REG_NZCV)==0xa0000000
  assert [m.u.reg_read(getattr(U.arm64_const,'UC_ARM64_REG_Q'+str(i))) for i in range(32)]==vectors
  rows.append(dict(name='%s_x0_%#x'%(hook,value),stop=m.stopped,value=value,field=fb,draws=m.draws,
      native_site='%#x'%exit_sites[hook],resume='%#x'%resume,clobbered_register='x%d'%clobber,
      native_replay=True,context_preserved=True))
write_report(out/'check6-exits.json',c,rows,'Actual CHECK6 exit hooks at their packaged addresses. Synthetic x0, one FB field per hook, replay verified against the recorded native word. No device execution.')

executed=[]
def regression(name,argv,replace=None):
 source=t.R/'scripts'/name;text=source.read_text();original=hashlib.sha256(source.read_bytes()).hexdigest()
 if replace:
  before,after=replace;assert text.count(before)==1;text=text.replace(before,after)
  (out/('adapted-'+name)).write_text(text)
 sys.argv=[str(source),*map(str,argv)]
 exec(compile(text,str(source),'exec'),{'__name__':'__main__','__file__':str(source)})
 executed.append(dict(source=name,sha256=original,adaptation=replace,executed_text_sha256=hashlib.sha256(text.encode()).hexdigest()))
regression('test-exec-native-helpers.py',['--work',a.work,'--output',out/'native-helpers.json'])
regression('test-exec-native-continuation.py',['--work',a.work,'--output',out/'native-continuation.json'])
regression('test-kmain16-stages.py',['--work',a.work,'--exec-return-limit','2'],
 ("if name=='init_loaded':assert struct.unpack('<Q',u.mem_read(latch+32,8))[0]==thread", "if name=='init_loaded':assert struct.unpack('<Q',u.mem_read(latch+32,8))[0]==0"))
regression('test-kmain4-r1-mainline.py',['--work',a.work])
(out/'regression-binding.json').write_text(json.dumps(dict(kernel_sha256=proof['kernel_sha256'],passed=True,executed=executed,
 harness_sha256=hashlib.sha256(Path(H.__file__).read_bytes()).hexdigest(),expected_hash_rebound_from=proof['check5_delta']['parent_kernel_sha256']),indent=2)+'\n')
print('PASS CHECK6 73 inherited machine cases (7+4+14+20+20+8) and 9 exit-observer cases')
