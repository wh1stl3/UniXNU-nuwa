"""Execute real parser -> segment -> PAGEZERO map bounds update and error unwind."""
import argparse,hashlib,json,struct,sys
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
raw=(t.R/'out/core-consumers-20261103-r1/sbin/launchd').read_bytes();assert hashlib.sha256(raw).hexdigest()=='12370e5ee35bf28ae479b6c4b4455f4f4693ab803e37c5eb3032537c18cac61c'
at=32;zero=None
for _ in range(struct.unpack_from('<I',raw,16)[0]):
 cmd,size=struct.unpack_from('<II',raw,at)
 if cmd==0x19 and raw[at+8:at+24].split(b'\0')[0]==b'__PAGEZERO':zero=sum(struct.unpack_from('<QQ',raw,at+24))
 at+=size
assert zero and zero%0x4000==0
EXTRA=0x30000000;MAP=MEM+0x20000;RESULT=MEM+0x6000;rows=[]
for name in ('advance_to_text','backwards','beyond_max','existing_entry','map_lock_wait'):
 m=Machine(c);m.u.mem_map(EXTRA,0x40000);m.u.mem_write(HEADER,raw[:4096]);m.put(IMG+0x2a8,CTX);m.put(BASE+0x715d118,14,4);m.put(RESULT+0x44,0x180,2);m.put(BASE+0x7abce30,0,4)
 minimum=zero+0x4000 if name=='backwards' else 0
 m.put(MAP+0x20,minimum);m.put(MAP+0x28,zero if name=='beyond_max' else 0x8000000000);m.put(MAP+0x34,14,2);m.put(MAP+0x18,MAP+0x10)
 if name=='existing_entry':m.put(MAP+0x18,MEM+0x24000);m.put(MEM+0x24010,zero-0x4000)
 for symbol,value in [('_vfs_context_proc',PROC),('_vfs_context_ucred',CTX),('_cpu_type',0x100000c),('_grade_binary',1),('_ubc_getobject',MEM+0x21000),('_kalloc_ext',EXTRA),('_thread_state_initialize',0),('_proc_getpid',1),('_cs_process_global_enforcement',1),('_ubc_getsize',len(raw)),('_ubc_cs_generation_check',0),('_printf',0)]:m.stub(symbol,lambda v=value:m.ret(v))
 m.stub('_kfree_ext',lambda:(m.events.append('command buffer freed'),m.ret()))
 def read():
  assert m.x(2)==EXTRA and m.x(1)==VNODE
  m.u.mem_write(EXTRA,raw[m.x(4):m.x(4)+m.x(3)].ljust(m.x(3),b'\0'));m.put(m.get(m.u.reg_read(UC_ARM64_REG_SP)),0,4);m.ret()
 m.stub('_vn_rdwr',read)
 # EXTRA is separately mapped: direct writes avoid Machine.ensure's carrier-only mapping.
 def cached():
  blob=EXTRA+0x30000;m.u.mem_write(blob,bytes(0x100));m.u.mem_write(blob+0x18,struct.pack('<III',0x100000c,0,1));m.ret(blob)
 m.stub('_ubc_cs_blob_get',cached)
 m.stub('_cs_validate_range',lambda:(m.put(m.x(5),0,4),m.ret(1)))
 def lock():
  assert m.x(0)==MAP;m.events.append('map lock fixture')
  if name=='map_lock_wait':m.stop('map lock wait boundary')
  else:m.ret()
 m.stub('_lck_rw_lock_exclusive',lock);m.stub('_lck_rw_done',lambda:(m.events.append('map unlock fixture'),m.ret()))
 for symbol in ('_vm_map_enter_mem_object_control','_vm_map_enter','_vm_map_enter_mem_object'):
  if symbol in c.sy:m.stub(symbol,lambda s=symbol:(m.events.append(s),m.stop('TEXT mapping interface')))
 for i,v in enumerate((VNODE,MAP,THREAD,HEADER,0,len(raw),0,0)):m.x(i,v)
 for off,value in [(0,0),(8,RESULT),(16,RESULT),(24,IMG)]:m.put(STACK+off,value)
 try:m.run('_parse_machfile')
 except Exception:print(name,m.events,m.recent,m.record(name)['visited_symbols']);raise
 assert c.sy['_vm_map_raise_min_offset'] in m.visits and c.sy['_load_code_signature'] in m.visits
 if name=='advance_to_text':assert m.stopped=='TEXT mapping interface' and m.get(MAP+0x20)==zero
 elif name=='map_lock_wait':assert m.stopped=='map lock wait boundary' and m.get(MAP+0x20)==minimum and 'map unlock fixture' not in m.events
 else:assert m.stopped=='return' and m.x(0)==4 and m.get(MAP+0x20)==minimum and m.events.count('command buffer freed')==1
 if name!='map_lock_wait':assert m.events.count('map lock fixture')==m.events.count('map unlock fixture')==1 and m.get(MAP+0x98,4)==1
 rows.append(m.record(name))
write_report(a.output,c,rows,'Actual launchd command traversal, signature helper, segment helper, native VM page-size helpers and PAGEZERO bounds update/error return. Simulated map/list inputs and lock APIs; IO/UBC/page validation remain fixtures. Success stops before TEXT mapping, not a complete VM or process. No target changes.')
r=json.loads(a.output.read_bytes());r.update(script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),launchd_sha256=hashlib.sha256(raw).hexdigest(),pagezero_end=hex(zero));a.output.write_text(json.dumps(r,indent=2)+'\n');print('PASS',len(rows),'native Mach VM chain cases')
