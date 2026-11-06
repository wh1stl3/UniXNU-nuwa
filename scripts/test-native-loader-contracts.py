"""CHECK5 actual Mach loader helpers with fixed dyld commands; no image mutation."""
import argparse,hashlib,json,struct
from pathlib import Path
import exec_carrier_model as H
from exec_carrier_model import *
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--image',choices=('dyld','launchd'),default='dyld');a=p.parse_args();assert not a.output.exists()
H.EXPECTED='c38fe9d4428467f9f3767408159f4d8327984fcaad2fbde175eca6ece93d313e'
c=Carrier(t.R/'out/ufs-check-5-r1-qualified');rows=[];CMD=MEM+0x5000;RESULT=MEM+0x7000;BLOB=MEM+0x9000;BUFFER=MEM+0x10000
input_report=t.R/'reports/desktop-readiness/2026-11-03-offline-mainline-r1/core-consumers-r2.json'
input_record=next(x for x in json.loads(input_report.read_bytes())['binaries'] if x['path']==('/sbin/launchd' if a.image=='launchd' else '/usr/lib/dyld'))
dyldpath=t.R/input_record['extracted'];dyld=dyldpath.read_bytes();commands=[];at=32
assert hashlib.sha256(dyld).hexdigest()==input_record['sha256']
filetype=struct.unpack_from('<I',dyld,12)[0]
assert struct.unpack_from('<I',dyld)[0]==0xfeedfacf
for _ in range(struct.unpack_from('<I',dyld,16)[0]):
 cmd,size=struct.unpack_from('<II',dyld,at);assert size>=8 and at+size<=len(dyld);commands.append((cmd,dyld[at:at+size]));at+=size
signature=next(raw for cmd,raw in commands if cmd==0x1d)
textseg=next(raw for cmd,raw in commands if cmd==0x19 and raw[8:24].rstrip(b'\0')==b'__TEXT')
main=next((raw for cmd,raw in commands if cmd==0x80000028),None)
def finish(m,name,want):
 assert m.stopped=='return' and m.x(0)&0xffffffff==want,(name,m.stopped,m.x(0),m.events)
 assert m.u.reg_read(UC_ARM64_REG_SP)==STACK
 rows.append(m.record(name))
for name,size,threads,stacksize,init_error,want in [('main_default_stack',24,0,0,0,0),('main_custom_stack',24,0,0x80000,0,0),('main_short',16,0,0,0,2),('main_duplicate',24,1,0,0,4),('main_state_failure',24,0,0,5,4)]:
 m=Machine(c);command=struct.pack('<IIQQ',0x80000028,size,struct.unpack_from('<Q',main,8)[0] if main else 0x4000,stacksize)
 if main and name=='main_default_stack':assert command==main
 m.u.mem_write(CMD,command);m.put(RESULT+0x40,threads,4);m.put(RESULT+0x44,0x180,2)
 m.put(BASE+0x715d118,14,4);m.stub('_thread_state_initialize',lambda:(m.events.append('thread_state_initialize boundary'),m.ret(init_error)))
 for i,v in enumerate((CMD,THREAD,0x4000,RESULT)):m.x(i,v)
 m.run('_load_main');finish(m,name,want)
 if want==0:
  assert m.get(RESULT+0x10)==0x16fdfc000 and m.get(RESULT+0x40,4)==1
  assert m.get(RESULT+0x28)==(stacksize+0x4000 if stacksize else 0x100000)
  assert c.sy['_thread_userstackdefault'] in m.visits

for name,cache,generation,revalidate,readerr,residual,add_error,allocate_error,want in [
 ('signature_cached_current',True,0,0,0,0,0,0,0),('signature_cached_revalidate',True,1,0,0,0,0,0,0),
 ('signature_revalidate_reject',True,1,13,0,0,0,0,4),('signature_eagain_reread',True,1,35,0,0,0,0,0),
 ('signature_fresh',False,0,0,0,0,0,0,0),('signature_read_error',False,0,0,5,0,0,0,9),
 ('signature_short_read',False,0,0,0,1,0,0,9),('signature_read_wait',False,0,0,None,0,0,0,None),
 ('signature_rejected',False,0,0,0,0,13,0,4),('signature_nomem',False,0,0,0,0,0,12,5),
 ('signature_out_of_file',False,0,0,0,0,0,0,2)]:
 m=Machine(c);m.u.mem_write(CMD,signature);m.put(BLOB+0x18,0x100000c,4);m.put(BLOB+0x1c,0,4);m.put(BLOB+0x20,1,4);m.put(BLOB+0x38,0x4000);m.put(BLOB+0xac,1,1)
 m.stub('_ubc_cs_blob_get',lambda:m.ret(BLOB if cache else 0));m.stub('_ubc_cs_generation_check',lambda:m.ret(generation))
 m.stub('_ubc_cs_blob_revalidate',lambda:(m.events.append('AMFI revalidate boundary'),m.ret(revalidate)))
 m.stub('_printf',lambda:m.ret())
 def alloc():
  m.events.append('allocate');
  if not allocate_error:m.put(m.x(0),BUFFER)
  m.ret(allocate_error)
 def read():
  offset,length=struct.unpack_from('<II',signature,8)
  assert (m.x(0),m.x(1),m.x(2),m.x(3),m.x(4))==(0,VNODE,BUFFER,length,offset)
  m.events.append('signature file read')
  if readerr is None:m.stop('signature IO boundary');return
  m.put(m.get(m.u.reg_read(UC_ARM64_REG_SP)),residual,4);m.ret(readerr)
 def add():
  assert m.x(0)==VNODE and m.x(2)==0x100000c
  m.events.append('AMFI blob add boundary')
  if not add_error:m.put(m.get(m.u.reg_read(UC_ARM64_REG_SP)+8),BLOB)
  m.ret(add_error)
 m.stub('_ubc_cs_blob_allocate',alloc);m.stub('_vn_rdwr',read);m.stub('_ubc_cs_blob_add',add)
 m.stub('_kauth_cred_get',lambda:m.ret(CTX));m.stub('_current_proc',lambda:m.ret(PROC))
 m.stub('_ubc_cs_blob_deallocate',lambda:(m.events.append('deallocate'),m.ret()))
 m.stub('_ubc_cs_validation_bitmap_allocate',lambda:(m.events.append('validation bitmap boundary'),m.ret()))
 for i,v in enumerate((CMD,VNODE,0,1 if name=='signature_out_of_file' else len(dyld),0x100000c,0,RESULT,IMG)):m.x(i,v)
 m.run('_load_code_signature')
 if want is None:assert m.stopped=='signature IO boundary';rows.append(m.record(name));continue
 finish(m,name,want)
 if want==0:assert m.get(RESULT+0x48,4)&1 and m.get(RESULT+0x70,4)==1 and m.get(RESULT+0x78)==0x4000
 if name in ('signature_read_error','signature_short_read','signature_rejected'):assert m.events.count('deallocate')==1
 if cache and revalidate!=35:assert 'allocate' not in m.events

for name in ('segment_real_text','segment_short','segment_file_overflow','segment_truncated_file','segment_bad_sections'):
 m=Machine(c);command=bytearray(textseg)
 if name=='segment_short':struct.pack_into('<I',command,4,40)
 if name=='segment_file_overflow':struct.pack_into('<QQ',command,40,(1<<64)-0x100,0x200)
 if name=='segment_bad_sections':struct.pack_into('<I',command,64,0xffffffff)
 m.u.mem_write(CMD,bytes(command));m.put(BASE+0x715d118,14,4)
 for symbol,value in (('_vm_map_page_size',0x4000),('_vm_map_page_mask',0x3fff),('_vm_map_page_shift',14)):
  m.stub(symbol,lambda v=value:m.ret(v))
 # Stop at the real VM mapping call; do not simulate successful VM allocation.
 for symbol in ('_vm_map_enter_mem_object_control','_vm_map_enter','_vm_map_enter_mem_object'):
  if symbol in c.sy:m.stub(symbol,lambda s=symbol:(m.events.append(s),m.stop('VM mapping boundary')))
 m.stub('_printf',lambda:m.ret());m.stub('_ubc_getsize',lambda:m.ret(len(dyld)))
 m.put(BASE+0x7abcE30,0,4)
 for i,v in enumerate((CMD,filetype,MEM+0x19000,0,1 if name=='segment_truncated_file' else len(dyld),VNODE,MEM+0x1a000,0)):m.x(i,v)
 m.put(STACK,RESULT);m.put(STACK+8,IMG);m.put(RESULT+0x44,0x180,2)
 m.run('_load_segment')
 if name=='segment_real_text':assert m.stopped=='VM mapping boundary';rows.append(m.record(name))
 else:finish(m,name,2)
write_report(a.output,c,rows,'Actual CHECK5 load_main, native stack-default helper, load_code_signature and load_segment. Fixed '+a.image+' LC_SEGMENT_64/LC_CODE_SIGNATURE and LC_MAIN when present. VM mapping stops at actual call boundary; thread initialization, UBC/AMFI/IO operations explicit fixtures. No full image load, signature acceptance or user execution.')
report=json.loads(a.output.read_bytes());report.update(input_image=input_record['path'],input_sha256=hashlib.sha256(dyld).hexdigest(),input_report_sha256=hashlib.sha256(input_report.read_bytes()).hexdigest(),actual_LC_MAIN=main.hex() if main else None,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),commands={'signature':signature.hex(),'text_segment':textseg.hex()});a.output.write_text(json.dumps(report,indent=2)+'\n')
print('PASS',len(rows),'native loader contracts')
