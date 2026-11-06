"""Execute Image4's actual MAC registration wrapper and the linked XNU registrar."""
import argparse,hashlib,json,sys
from pathlib import Path
import unicorn
try:import tomllib
except ModuleNotFoundError:
 import pip._vendor.tomli as tomllib
 sys.modules['tomllib']=tomllib
import exec_carrier_model as H
from exec_carrier_model import *
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.output.exists()
H.EXPECTED='c38fe9d4428467f9f3767408159f4d8327984fcaad2fbde175eca6ece93d313e';c=Carrier(t.R/'out/ufs-check-5-r1-qualified')
CONF=0xfffffff005caf458;OPS=0xfffffff005caf4a8;LIST=BASE+0x71eb238;LATE=BASE+0x7ac05a8;TABLE=MEM+0x10000;HANDLE=MEM+0x11000;rows=[]
for name in ('early_success','late_success','duplicate','full','late_not_allowed','late_lock_wait'):
 m=Machine(c);late=name.startswith('late');m.put(LATE,int(late),4)
 m.put(LIST,0,4);m.put(LIST+4,4,4);m.put(LIST+8,0,4);m.put(LIST+12,0,4);m.put(LIST+20,0,4);m.put(LIST+24,TABLE)
 m.put(CONF+0x38,0,4);m.put(HANDLE,0xffffffff,4)
 assert m.get(CONF+0x20)==OPS and m.get(OPS+0x398)==m.get(OPS+0x3a0)==0
 assert m.get(0xfffffff005cabaf0)==c.sy['_mac_policy_register']
 if name=='duplicate':m.put(TABLE,CONF);m.put(LIST,1,4)
 if name=='full':m.put(LIST,4,4)
 if name=='late_not_allowed':m.put(CONF+0x28,1,4)
 m.stub('_printf',lambda:m.ret())
 def lock():
  m.events.append('MAC list lock boundary')
  if name=='late_lock_wait':m.stop('MAC list lock wait boundary')
  else:m.ret()
 for sym in ('_lck_mtx_lock','_lck_mtx_unlock','_thread_wakeup_prim'):
  m.stub(sym,lock if sym=='_lck_mtx_lock' else lambda s=sym:(m.events.append(s),m.ret()))
 m.put(BASE+0x7af7710,0,4)
 m.callbacks[0xfffffff0046fa028]=lambda:m.stop('Image4 registration failure panic')
 m.x(0,HANDLE)
 try:m.run(0xfffffff0046ee518)
 except Exception:
  print(name,m.events,m.recent,m.record(name)['visited_symbols']);raise
 assert c.sy['_mac_policy_register'] in m.visits
 if name.endswith('success'):
  assert m.stopped=='return' and m.x(0)==0 and m.get(HANDLE,4)==0
  assert m.get(TABLE)==CONF and m.get(LIST,4)==1 and m.get(CONF+0x38,4)&1
 elif name=='late_lock_wait':assert m.stopped=='MAC list lock wait boundary' and m.get(HANDLE,4)==0xffffffff
 else:
  assert m.stopped=='Image4 registration failure panic'
  # Wrapper stores the real registrar errno at SP before calling panic.
  expected={'duplicate':17,'full':12,'late_not_allowed':1}[name]
  assert m.get(m.u.reg_read(UC_ARM64_REG_SP))==expected
  assert m.get(HANDLE,4)==0xffffffff and m.get(CONF+0x38,4)==0
 rows.append(m.record(name))
write_report(a.output,c,rows,'Real Image4 wrapper, import thunk and XNU MAC registrar including native list insertion, duplicate/capacity/late-policy checks and updateflags/label-list path. MAC list contents, printf, late mutex/wakeup are explicit fixtures; no policy callback was injected. Both original init callback slots are NULL. No provider or authenticated context construction is certified.')
r=json.loads(a.output.read_bytes());r.update(script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),policy_init_slots=[hex(OPS+0x398),hex(OPS+0x3a0)],policy_init_values=[0,0]);a.output.write_text(json.dumps(r,indent=2)+'\n');print('PASS',len(rows),'native Image4 MAC registration cases')
