"""Execute nonce-lock producer loop then actual ignition reader; scheduler is explicit."""
import argparse,hashlib,json,struct
from pathlib import Path
import exec_carrier_model as H
from exec_carrier_model import *
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.output.exists()
H.EXPECTED='c38fe9d4428467f9f3767408159f4d8327984fcaad2fbde175eca6ece93d313e';c=Carrier(t.R/'out/ufs-check-5-r1-qualified')
context=0xfffffff005caea20
producer=0xfffffff0046ed9ec;reader=0xfffffff0046e4330;rows=[]
for name,count,block in [('empty_registry',0,False),('two_nonce_domains',2,False),('domain_callback_wait',2,True)]:
 m=Machine(c);m.events=[];LOG=MEM+0x10000;GETLOG=MEM+0x11000;LOGFN=MEM+0x12000;DOMAIN=MEM+0x14000
 m.put(context,LOG);m.put(LOG+0x28,LOGFN);m.put(LOG+0x30,GETLOG)
 m.put(context+0x230,MEM+0x16000);m.put(context+0x238,MEM+0x17000);m.put(context+0x63,count)
 m.callbacks[GETLOG]=lambda:m.ret(0);m.callbacks[LOGFN]=lambda:m.ret(0)
 def event(label):m.events.append(label);m.ret()
 for addr,label in [(0xfffffff0046f9fc8,'mutex lock'),(0xfffffff0046f9fa4,'gate close'),(0xfffffff0046f9f98,'gate open'),(0xfffffff0046f9fd4,'mutex unlock')]:
  m.callbacks[addr]=lambda s=label:event(s)
 def domain():m.put(DOMAIN+0x28,m.x(0));m.ret(DOMAIN)
 def digest():
  assert m.x(0)==context and m.x(1)==DOMAIN
  m.events.append('domain digest callback')
  if block:m.stop('domain digest boundary')
  else:m.ret()
 m.callbacks[0xfffffff0046ee47c]=domain;m.callbacks[0xfffffff0046edaf8]=digest
 m.callbacks[0xfffffff0046f9f14]=lambda:event('publish nonce digest boundary')
 m.x(0,context);m.run(producer)
 assert m.events[:2]==['mutex lock','gate close']
 if block:assert m.stopped=='domain digest boundary' and 'gate open' not in m.events
 else:
  assert m.stopped=='return' and m.events[-2:]==['gate open','mutex unlock']
  assert m.events.count('domain digest callback')==m.events.count('publish nonce digest boundary')==count
 rows.append(m.record(name))
 # Observe reader after producer completes or stalls. Gate return is a
 # scheduler contract derived from this model order, not emulated lock internals.
 m.stopped=None;m.u.reg_write(UC_ARM64_REG_SP,STACK);m.x(30,SENTINEL)
 logbase=0xfffffff005cb14d8;m.put(logbase+0x28,LOGFN);m.put(logbase+0x30,GETLOG)
 for addr,value in [(0xfffffff0046fa04c,MEM+0x18000),(0xfffffff0046f9c38,0),(0xfffffff0046fa040,1),(0xfffffff0046f9fb0,int(block))]:m.callbacks[addr]=lambda v=value:m.ret(v)
 m.callbacks[0xfffffff0046f9fbc]=lambda:m.stop('reader waits for nonce gate')
 def copy():assert m.x(2)==0x84;m.events.append('copy opaque blob boundary');m.ret()
 m.callbacks[0xfffffff0046fa0b8]=copy
 m.put(MEM+0x20000,PROC);m.x(0,0xfffffff006a11330);m.x(1,0xfffffff005cac328);m.x(2,0x84);m.x(3,MEM+0x20000)
 m.run(reader)
 assert m.stopped==('reader waits for nonce gate' if block else 'return')
 assert ('copy opaque blob boundary' in m.events)==(not block)
 rows.append(m.record(name+'_reader'))
# Bind static direct callers and data pointers without claiming runtime arrival.
callers=[];pointers=[]
for seg in c.m['segments']:
 for at in range(seg['fileoff'],seg['fileoff']+seg['filesize']-7,4):
  pc=seg['va']+at-seg['fileoff'];word=struct.unpack_from('<I',c.raw,at)[0]
  if word&0xfc000000==0x94000000:
   imm=word&0x3ffffff;imm=imm-(1<<26) if imm&(1<<25) else imm
   if pc+4*imm==producer:callers.append(hex(pc))
  if struct.unpack_from('<Q',c.raw,at)[0]==producer:pointers.append(hex(pc))
write_report(a.output,c,rows,'Real nonce-lock producer loop, ordering and ignition_blob reader. Domain digest/publication, log, mutex/gate internals and scheduling are explicit boundaries. Zero-domain gate-open does not authenticate or populate blob. No device nonce initialization proof.')
r=json.loads(a.output.read_bytes());r.update(producer=hex(producer),direct_callers=callers,absolute_pointer_locations=pointers,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest());a.output.write_text(json.dumps(r,indent=2)+'\n')
print('PASS',len(rows),'nonce producer/reader cases',callers,pointers)
