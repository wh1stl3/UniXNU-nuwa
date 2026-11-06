"""Actual carrier ignition_blob handler: privilege and nonce-gate boundaries.
No real process, locks, scheduler, nonce initialization or sysctl copyout is executed.
"""
import argparse,hashlib,json,struct,sys
from pathlib import Path
import flush_trace_inputs as trace
sys.path.insert(0,str(trace.R/'out/python-tools'))
import unicorn as U
from unicorn.arm64_const import *
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.output.exists()
R=trace.R;sha=lambda b:hashlib.sha256(b).hexdigest();raw=(R/'out/payload-s1-r1/kernel.macho').read_bytes();q=json.loads((R/'reports/payload-s1-r1/offline-package-r2.json').read_bytes());assert sha(raw)==q['kernel_sha256']
B=trace.builder();m=B.macho(raw);entry=0xfffffff0046e4330;oid=0xfffffff006a11330;context=0xfffffff005caea20;logging=0xfffffff005cb14d8
off=B.backed(m,oid,0x50);fields=struct.unpack_from('<10Q',raw,off);assert fields[6]==entry and fields[4]==0x84
off=B.backed(m,fields[5],32);assert raw[off:off+14]==b'ignition_blob\0'
binding=dict(oid=hex(oid),handler=hex(entry),blob_address=hex(fields[3]),blob_bytes=fields[4],handler_sha256=sha(raw[B.backed(m,entry,0x18c):][:0x18c]))
cases=[]
for case in ('pid1-immediate','pid1-wait-handoff','unprivileged'):
 u=U.Uc(U.UC_ARCH_ARM64,U.UC_MODE_ARM);pages=set();base=0x20000000;stop=base+0x1000;stack=base+0x1f000
 u.mem_map(base,0x20000)
 def mapping(addr,n):
  for page in range(addr&~4095,(addr+n+4095)&~4095,4096):
   if page in pages:continue
   s=next((s for s in m['segments'] if s['va']<=page<s['va']+s['size']),None);assert s,hex(page)
   u.mem_map(page,4096);pages.add(page)
   if page-s['va']<s['filesize']:
    n=min(4096,s['filesize']-(page-s['va']));o=s['fileoff']+page-s['va'];u.mem_write(page,raw[o:o+n])
 def fault(uc,access,addr,n,value,data):mapping(addr,n);return True
 def write(address,data):
  if address>=0xffff000000000000:mapping(address,len(data))
  u.mem_write(address,data)
 u.hook_add(U.UC_HOOK_MEM_UNMAPPED,fault)
 write(context+0x230,struct.pack('<QQ',base+0x4000,base+0x5000))
 write(logging+0x28,struct.pack('<QQ',base+0x2000,base+0x2010))
 req=base+0x3000;write(req,struct.pack('<Q',base+0x6000));events=[]
 targets={0xfffffff0046fa04c:'proc_task',0xfffffff0046f9c38:'entitlement',0xfffffff0046fa040:'is_initproc',0xfffffff0046f9fc8:'lock',0xfffffff0046f9fb0:'gate_try_close',0xfffffff0046f9fbc:'gate_wait',0xfffffff0046f9f98:'gate_open',0xfffffff0046f9fd4:'unlock',0xfffffff0046fa0b8:'sysctl_handle_opaque',base+0x2000:'log',base+0x2010:'log_context'}
 def hook(uc,pc,size,data):
  name=targets.get(pc)
  if not name:return
  xs=[uc.reg_read(x) for x in (UC_ARM64_REG_X0,UC_ARM64_REG_X1,UC_ARM64_REG_X2,UC_ARM64_REG_X3,UC_ARM64_REG_X4)];ret=0;event=dict(call=name)
  if name=='proc_task':ret=base+0x6100
  elif name=='entitlement':
   mapping(xs[1],64);assert bytes(uc.mem_read(xs[1],64)).split(b'\0')[0]==b'com.apple.private.img4.ignition-blob'
  elif name=='is_initproc':ret=int(case!='unprivileged')
  elif name in ('lock','unlock'):assert xs[0]==base+0x4000
  elif name=='gate_try_close':ret=int(case=='pid1-wait-handoff')
  elif name=='gate_wait':assert xs[:2]==[base+0x4000,base+0x5000];event['fixture_result']=0
  elif name=='sysctl_handle_opaque':assert xs==[oid,fields[3],0x84,req,xs[4]];event['bytes']=xs[2]
  events.append(event);uc.reg_write(UC_ARM64_REG_X0,ret);uc.reg_write(UC_ARM64_REG_PC,uc.reg_read(UC_ARM64_REG_LR))
 u.hook_add(U.UC_HOOK_CODE,hook)
 for reg,value in ((UC_ARM64_REG_X0,oid),(UC_ARM64_REG_X3,req),(UC_ARM64_REG_SP,stack),(UC_ARM64_REG_LR,stop)):u.reg_write(reg,value)
 u.emu_start(entry,stop,count=10000);assert u.reg_read(UC_ARM64_REG_PC)==stop and u.reg_read(UC_ARM64_REG_SP)==stack
 names=[v['call'] for v in events];assert u.reg_read(UC_ARM64_REG_W0)==(1 if case=='unprivileged' else 0)
 assert names.count('lock')==names.count('unlock')==int(case!='unprivileged')
 assert names.count('gate_wait')==int(case=='pid1-wait-handoff')
 assert names.count('sysctl_handle_opaque')==int(case!='unprivileged')
 cases.append(dict(name=case,events=events,errno=u.reg_read(UC_ARM64_REG_W0)))
report=dict(passed=True,kernel_sha256=sha(raw),script_sha256=sha(Path(__file__).read_bytes()),binding=binding,cases=cases,device_accessed=False,nonce_state_verified=False,blob_contents_authenticated=False,scope='Actual ignition_blob callback and context getter; explicit process privilege, initialized mutex/gate, log and sysctl sink fixtures. Demonstrates the wait-capable branch, not a device wait or nonce completion.')
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n');print('PASS 3 native ignition_blob reader boundary cases')
