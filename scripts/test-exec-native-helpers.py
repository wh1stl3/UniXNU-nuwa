"""Execute real proc transition and vnode attribute machinery in frozen CHECK4."""
import argparse
from pathlib import Path
from exec_carrier_model import *
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
c=Carrier(a.work);rows=[]
for name,flags,sleep,locked,nonblocking,expected in [
 ('idle',0,'stop',0,0,0),('already_locked',0,'stop',1,0,0),
 ('committed',0x60,'stop',0,0,11),('nonblocking',0x40,'stop',0,1,11),
 ('wait_boundary',0x40,'stop',1,0,None),('wait_wake_retry',0x40,'wake',1,0,0)]:
 m=environment(c,flags,sleep);m.locked=bool(locked);m.x(0,PROC);m.x(1,locked);m.x(2,nonblocking)
 m.run('_proc_transstart')
 if expected is None:assert m.stopped=='scheduler boundary'
 else:
  assert m.x(0)==expected and m.locked==bool(locked)
  assert m.get(PROC+0x648)==(THREAD if expected==0 else 0)
  assert m.get(PROC+0x458,4)==(0x40 if expected==0 else flags)
 rows.append(m.record(name))
for flags in (0x40,0xe0,0x1000|0xe0):
 m=environment(c,flags);m.put(PROC+0x648,THREAD);m.x(0,PROC);m.x(1,0);m.run('_proc_transend')
 assert m.get(PROC+0x458,4)==flags&~0xe0 and m.get(PROC+0x648)==0 and not m.locked
 assert ('wakeup after clear' in m.events)==bool(flags&0x80)
 rows.append(m.record('transend_'+hex(flags)))
for name,active,err,supported in [('requested',0x20000120390,0,True),('unsupported',1<<63,0,True),('vnop_error',0x390,5,True),('vnop_wait',0x390,None,True),('synthesized',0x390,0,False)]:
 m=environment(c,getattr_error=err,supported=supported);m.put(ATTR+8,active);m.put(ATTR+0x10,1<<22,4)
 m.x(0,VNODE);m.x(1,ATTR);m.x(2,CTX);m.run('_vnode_getattr')
 if err is None:assert m.stopped=='filesystem getattr boundary'
 else:
  assert m.x(0)==(22 if name=='unsupported' else err)
  if name!='unsupported':assert not m.get(ATTR+0x10,4)&(1<<22)
  if not err and name!='unsupported':assert m.get(ATTR+0xe0,4)==1 and m.get(ATTR)&0x180==0x180
 assert ('VNOP_GETATTR descriptor dispatch' in m.events)==(name!='unsupported')
 rows.append(m.record(name))
write_report(a.output,c,rows,'Actual proc_lock/unlock wrappers, proc_transstart/end, current_thread, vnode_getattr and uid/gid normalization. Mutex primitives, scheduler wake, credentials and VNOP_GETATTR are explicit boundaries; no real scheduler, APFS or device proof.')
print('PASS',len(rows),'native helper cases')
