"""Real parse_machfile command walk into native signature/segment helpers."""
import argparse,hashlib,json,struct,sys
import unicorn
try:
 import tomllib
except ModuleNotFoundError:
 import pip._vendor.tomli as tomllib
 sys.modules['tomllib']=tomllib
from pathlib import Path
import exec_carrier_model as H
from exec_carrier_model import *
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.output.exists()
H.EXPECTED='c38fe9d4428467f9f3767408159f4d8327984fcaad2fbde175eca6ece93d313e';c=Carrier(t.R/'out/ufs-check-5-r1-qualified')
raw=(t.R/'out/core-consumers-20261103-r1/sbin/launchd').read_bytes();assert hashlib.sha256(raw).hexdigest()=='12370e5ee35bf28ae479b6c4b4455f4f4693ab803e37c5eb3032537c18cac61c'
EXTRA=0x30000000;RESULT=MEM+0x6000;rows=[]
cases=[('depth',4),('cpu',1),('filetype',4),('commands_past_file',2),('allocation',5),('command_io',9),('command_short_read',2),('zero_cmdsize',2),('command_extent',2),('signature_io',9),('signature_wait',None),('signature_reject',4),('segment_mapping',None)]
for name,expected in cases:
 m=Machine(c);m.u.mem_map(EXTRA,0x40000);data=bytearray(raw);depth=3 if name=='depth' else 0
 if name=='cpu':struct.pack_into('<I',data,4,0x1000007)
 if name=='filetype':struct.pack_into('<I',data,12,6)
 if name=='zero_cmdsize':struct.pack_into('<I',data,36,0)
 if name=='command_extent':struct.pack_into('<I',data,36,len(raw))
 m.u.mem_write(HEADER,bytes(data[:4096]));m.put(IMG+0x2a8,CTX);m.put(BASE+0x715d118,14,4);m.put(RESULT+0x44,0x180,2)
 m.put(BASE+0x7abce30,0,4)
 for symbol,value in [('_vfs_context_proc',PROC),('_vfs_context_ucred',CTX),('_cpu_type',0x100000c),('_grade_binary',1),('_ubc_getobject',MEM+0x21000),('_vm_map_page_mask',0x3fff),('_vm_map_page_size',0x4000),('_vm_map_page_shift',14)]:m.stub(symbol,lambda v=value:m.ret(v))
 m.stub('_kalloc_ext',lambda:(m.events.append('command allocation'),m.ret(0 if name=='allocation' else EXTRA)))
 for sym in ('_kfree_ext','_kfree_data_external'):
  if sym in c.sy:m.stub(sym,lambda:(m.events.append('command free'),m.ret()))
 def reading():
  address,length,offset=m.x(2),m.x(3),m.x(4);command=address==EXTRA
  assert m.x(0)==0 and m.x(1)==VNODE
  m.events.append('command read' if command else 'signature read')
  if not command and name=='signature_wait':m.stop('signature IO boundary');return
  assert length<=0x20000
  m.u.mem_write(address,bytes(data[offset:offset+length]).ljust(length,b'\0'))
  m.put(m.get(m.u.reg_read(UC_ARM64_REG_SP)),1 if command and name=='command_short_read' else 0,4)
  m.ret(5 if (command and name=='command_io') or (not command and name=='signature_io') else 0)
 m.stub('_vn_rdwr',reading);m.stub('_ubc_cs_blob_get',lambda:m.ret(0))
 def allocate():m.put(m.x(0),EXTRA+0x20000);m.events.append('signature allocation');m.ret()
 m.stub('_ubc_cs_blob_allocate',allocate);m.stub('_kauth_cred_get',lambda:m.ret(CTX));m.stub('_current_proc',lambda:m.ret(PROC))
 m.stub('_ubc_cs_blob_deallocate',lambda:(m.events.append('signature free'),m.ret()))
 def add():m.events.append('AMFI add boundary');m.ret(13)
 m.stub('_ubc_cs_blob_add',add);m.stub('_printf',lambda:m.ret())
 m.stub('_thread_state_initialize',lambda:(m.events.append('thread state initialization fixture'),m.ret(0)))
 m.stub('_proc_getpid',lambda:m.ret(1))
 m.stub('_cs_process_global_enforcement',lambda:m.ret(1))
 def validate():m.put(m.x(5),0,4);m.events.append('page signature validation fixture');m.ret(1)
 m.stub('_cs_validate_range',validate)
 # For the segment case, stop at the native helper's VM interface, rather
 # than synthesizing successful mappings or calling the helper directly.
 if name=='segment_mapping':
  def cached():
   blob=EXTRA+0x30000;m.u.mem_write(blob,bytes(0x100));m.u.mem_write(blob+0x18,struct.pack('<II',0x100000c,0));m.u.mem_write(blob+0x20,struct.pack('<I',1));m.ret(blob)
  m.stub('_ubc_cs_blob_get',cached);m.stub('_ubc_cs_generation_check',lambda:m.ret(0))
  for symbol in ('_vm_map_enter_mem_object_control','_vm_map_enter','_vm_map_enter_mem_object','_vm_map_raise_min_offset'):
   if symbol in c.sy:m.stub(symbol,lambda s=symbol:(m.events.append(s),m.stop('VM mapping boundary')))
  m.stub('_ubc_getsize',lambda:m.ret(len(raw)))
 for i,v in enumerate((VNODE,MEM+0x20000,THREAD,HEADER,0,1 if name=='commands_past_file' else len(raw),depth,0)):m.x(i,v)
 for off,value in [(0,0),(8,RESULT),(16,RESULT),(24,IMG)]:m.put(STACK+off,value)
 try:m.run('_parse_machfile')
 except Exception:
  print(name,m.events,m.recent,m.record(name)['visited_symbols']);raise
 if expected is not None:
  assert m.stopped=='return' and m.x(0)&0xffffffff==expected,(name,m.x(0),m.events,m.recent,m.record(name)['visited_symbols'])
  assert m.u.reg_read(UC_ARM64_REG_SP)==STACK
 else:assert m.stopped==('VM mapping boundary' if name=='segment_mapping' else 'signature IO boundary'),(name,m.stopped)
 if name.startswith('signature'):assert c.sy['_load_code_signature'] in m.visits
 if name=='segment_mapping':assert c.sy['_load_segment'] in m.visits
 rows.append(m.record(name))
write_report(a.output,c,rows,'Actual parse_machfile entry/command traversal into real load_code_signature/load_segment. Real launchd header/load commands. CPU grade, allocation, IO and UBC/AMFI APIs are explicit fixtures; VM mapping stops before execution. No full process/VM creation or userland.')
r=json.loads(a.output.read_bytes());r.update(script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),input_sha256=hashlib.sha256(raw).hexdigest());a.output.write_text(json.dumps(r,indent=2)+'\n');print('PASS',len(rows),'native Mach command-chain cases')
