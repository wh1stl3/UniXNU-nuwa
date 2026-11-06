"""Run the original Image4 runtime table traversal down to real registry dependency."""
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
H.EXPECTED='c38fe9d4428467f9f3767408159f4d8327984fcaad2fbde175eca6ece93d313e';c=Carrier(t.R/'out/ufs-check-5-r1-qualified');rows=[]
for name in ('registry_boundary','lock_allocation_wait'):
 m=Machine(c);allocations=[];logging=0xfffffff005cb14d8;state=0xfffffff006a11420
 m.put(0xfffffff005cb14b8,0,4);m.put(0xfffffff005cb14d0,0xfffffff005caceb0)
 m.put(0xfffffff005cab920,MEM+0x15000);m.put(MEM+0x15000,0x12345678)
 def alloc():
  if name=='lock_allocation_wait':m.stop('lock allocation wait boundary');return
  address=MEM+0x18000+len(allocations)*0x100;allocations.append(address);m.events.append('lock allocation fixture');m.ret(address)
 m.stub('_lck_grp_alloc_init',alloc);m.stub('_lck_mtx_alloc_init',alloc)
 for slot in (logging+0x28,logging+0x30):m.callbacks[m.get(slot)]=lambda:m.ret()
 def registry():
  m.ensure(m.x(0));path=bytes(m.u.mem_read(m.x(0),128)).split(b'\0')[0].decode()
  m.events.append(dict(registry_path=path));m.stop('IORegistry lookup boundary')
 m.callbacks[0xfffffff0046f9cf8]=registry
 try:m.run(0xfffffff0046e4a28)
 except Exception:
  print(name,m.events,m.recent,m.record(name)['visited_symbols']);raise
 if name=='registry_boundary':
  assert m.stopped=='IORegistry lookup boundary'
  assert c.sy['_getsectdatafromheader'] in m.visits and 0xfffffff0046e98cc in m.visits
  assert 0xfffffff0046efda4 in m.visits and len(allocations)==3
  assert [m.get(state+off) for off in (0,8,16)]==allocations
 else:assert m.stopped=='lock allocation wait boundary' and 0xfffffff0046e98cc not in m.visits
 assert 0xfffffff0046ee518 not in m.visits and 0xfffffff0046e467c not in m.visits
 rows.append(m.record(name))
write_report(a.output,c,rows,'Actual runtime dispatcher, original Mach-O __img4_rt table via native getsectdatafromheader, original darwin initializer and pmap cs prefix. Explicit allocator/logging fixtures, selected native mode and initialized context pointer. Stops before IORegistry API; no provider matching, hardware query or authentication completed. Wait is injected at allocation API, not a reproduced deadlock.')
r=json.loads(a.output.read_bytes());r['script_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();a.output.write_text(json.dumps(r,indent=2)+'\n');print('PASS',len(rows),'native runtime dispatch cases')
