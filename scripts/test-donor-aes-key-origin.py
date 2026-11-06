"""Native original-donor special-key creation and lookup; crypto explicitly mocked."""
import argparse,hashlib,json,sys
from pathlib import Path
import unicorn
try:import tomllib
except ModuleNotFoundError:
 import pip._vendor.tomli as tomllib
 sys.modules['tomllib']=tomllib
from exec_carrier_model import *
from aes_origin_inputs import carrier,read,DONOR
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.output.exists()
c=carrier(True);rows=[]
for name in ('derived_fixture','parent_rejected','parent_wait'):
 m=Machine(c);SELF=MEM+0x10000;VT=SELF+0x1000;TABLE=VT+0x1000;SRC=TABLE+0x1000;DST=SRC+0x1000;DVT=DST+0x1000;IN=DVT+0x1000;OUT=IN+0x1000;CALL=OUT+0x1000
 m.put(SELF,VT);m.put(SELF+0x98,0xfffffff007adc5c8);m.put(SELF+0xd0,TABLE);m.put(SELF+0xd8,12,4)
 m.put(0xfffffff006ca8940,CALL+0x100);m.put(CALL+0x100,0x1234)
 for obj in (SRC,DST):m.put(obj,DVT)
 allocations=[];calls=[]
 def alloc():
  obj=(SRC,DST)[len(allocations)];allocations.append(obj);m.ret(obj)
 m.callbacks[0xfffffff0056db938]=alloc
 def memset():m.u.mem_write(m.x(0),bytes([m.x(1)&255])*m.x(2));m.ret(m.x(0))
 m.callbacks[0xfffffff0056dba04]=memset
 def writebytes():
  m.ensure(m.x(2));m.u.mem_write(IN,bytes(m.u.mem_read(m.x(2),m.x(3))));m.ret(m.x(3))
 def readbytes():m.u.mem_write(m.x(2),bytes(m.u.mem_read(OUT,m.x(3))));m.ret(m.x(3))
 def crypto():
  index=m.x(22);key=m.x(6);sel=m.get(key+36,4);block=bytes(m.u.mem_read(IN,16)).hex()
  expected=read(c,0xfffffff007adc5c8+index*24,24)
  assert sel==int.from_bytes(expected[4:8],'little') and block==expected[8:].hex()
  assert m.x(3)==16 and m.x(5)==0 and bytes(m.u.mem_read(m.x(4),16))==bytes(16)
  calls.append(dict(index=index,parent_selector=sel,derivation_block=block,synthetic_output=True))
  if index==10 and name=='parent_wait':m.stop('parent AES wait boundary');return
  m.u.mem_write(OUT,bytes([0xa0+index])*16)
  m.ret(0xe00002c7 if index==10 and name=='parent_rejected' else 0)
 for table,off,fn in ((DVT,0xd0,writebytes),(DVT,0xc8,readbytes),(VT,0x550,crypto),(VT,0x580,lambda:(m.events.append('disable hardware selector '+str(m.x(1))),m.ret()))):
  m.put(table+off,CALL);m.callbacks[CALL]=fn;CALL+=4
 m.callbacks[0xfffffff0056da71c]=lambda:m.stop('derived-key loop completed; post-loop extras excluded')
 m.x(0,SELF)
 try:m.run(0xfffffff0056da420)
 except Exception:print(name,m.recent);raise
 target=TABLE+10*0x34
 if name=='parent_wait':assert m.stopped=='parent AES wait boundary'
 else:assert m.stopped.startswith('derived-key loop completed')
 assert m.get(target,1)==(1 if name=='derived_fixture' else 0)
 if name=='derived_fixture':assert m.get(target+4,4)==2212 and m.get(target+8,4)==128 and m.get(target+0x2c,4)==0
 row=m.record(name);row['parent_calls']=calls;row['target_valid']=m.get(target,1);rows.append(row)
 if name!='parent_wait':
  m.x(0,SELF);m.x(1,2212);m.x(2,OUT+0x200);m.u.reg_write(UC_ARM64_REG_LR,SENTINEL);m.stopped=None;m.run(0xfffffff0056d9ffc)
  assert m.stopped=='return';assert m.x(0)==(0 if name=='derived_fixture' else 0xe00002c1)
  if name=='derived_fixture':assert m.get(OUT+0x200)==target+8
  rows.append(m.record(name+'_lookup'))
write_report(a.output,c,rows,'Original iOS16 donor createSpecialKeys loops and special-key lookup execute native code with actual immutable 12-row derivation table. Descriptor allocation/read/write, locks not involved here, disable-key virtual and AES operation are explicit fixtures. Derived bytes are marked synthetic and prove no UID or nuwa crypto. Stops before post-loop extra operations. Not CHECK5 linked-provider execution.')
r=json.loads(a.output.read_bytes());r['script_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();a.output.write_text(json.dumps(r,indent=2)+'\n');print('PASS',len(rows),'donor native key creation/lookup cases')