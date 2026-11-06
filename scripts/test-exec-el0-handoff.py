"""Frozen CHECK4 target-thread counterexample and native restore-to-ERET audit."""
import argparse
from pathlib import Path
from exec_carrier_model import *
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
c=Carrier(a.work);rows=[];SAVED=MEM+0x20000;CPU=MEM+0x25000;NEW=MEM+0x3000;USER=MEM+0x3d000

for name,thread,mode,debug,recount_wait in [
 ('old_target_new_thread_missed',NEW,0,False,False),
 ('old_thread_matches',THREAD,0,False,False),
 ('kernel_mode_rejected',THREAD,5,False,False),
 ('after_marker_recount_wait',THREAD,0,False,True),
 ('after_marker_debug_restore',THREAD,0,True,False)]:
 m=Machine(c);state=c.proof['targets']['coarse_state']
 # Execute actual init-return observer, rather than pre-seeding its target.
 resume=c.proof['targets']['init_loaded_resume'];m.callbacks[resume]=lambda:m.stop('init observer return')
 m.run(c.proof['symbols']['coarse_init_loaded']);assert m.get(state+32)==THREAD
 del m.callbacks[resume];m.stopped=None
 m.u.reg_write(UC_ARM64_REG_TPIDR_EL1,thread);m.x(21,SAVED);m.x(3,thread)
 m.put(thread+0x1c8,CPU);m.put(thread+0x140,0x1234 if debug else 0);m.put(SAVED+0x110,mode,4)
 m.put(SAVED+0x108,USER);m.put(SAVED+0x100,MEM+0x35000)
 for i in range(31):m.put(SAVED+8+i*8,0x100+i)
 m.put(SAVED+0x108,USER);m.put(SAVED+0x100,MEM+0x35000)
 m.stub('_recount_enter_user',lambda:m.stop('recount boundary') if recount_wait else m.ret())
 m.stub('_arm_debug_set',lambda:(m.events.append('debug restore boundary'),m.ret()))
 m.callbacks[BASE+0x73c3994]=lambda:m.stop('before ERET')
 m.run(BASE+0x73c3864)
 seen=[14,1] in m.draws
 assert seen==(thread==THREAD and mode==0),(name,m.draws)
 if recount_wait:assert m.stopped=='recount boundary' and BASE+0x73c3994 not in m.visits
 else:
  assert m.stopped=='before ERET'
  assert m.u.reg_read(UC_ARM64_REG_ELR_EL1)==USER and m.u.cpr_read(3,0,4,0,0)==mode
  assert m.u.reg_read(UC_ARM64_REG_SP)==MEM+0x35000
  for i in range(31):
   if i!=18:assert m.x(i)==0x100+i,(name,i,hex(m.x(i)))
  assert USER not in m.visits
 row=m.record(name);row.update(el0_marker=seen,target_latch=m.get(state+32),current_thread=thread,
     user_instruction_executed=False);rows.append(row)
write_report(a.output,c,rows,'Actual old init-return latch and scoped EL0 observer, then native register restore up to ERET. Distinct old/new thread counterexample. Recount/debug are explicit boundaries; saved user state is synthetic. ERET and user instruction intentionally not executed, no hardware claim.')
print('PASS',len(rows),'EL0 handoff cases; frozen observer misses distinct exec thread')
