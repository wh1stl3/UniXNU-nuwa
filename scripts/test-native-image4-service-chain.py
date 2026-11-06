"""Execute original Image4 start -> AES match/wait -> nonce gate/persistence ordering."""
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
context=0xfffffff005caea20;logging=0xfffffff005cb14d8
for name in ('parent_refusal','provider_wait','provider_type_failure','provider_to_nonce','persistence_readonly','persistence_wait'):
 m=Machine(c);SELF=MEM+0x10000;VT=MEM+0x11000;DICT=MEM+0x12000;DVT=MEM+0x13000;AES=MEM+0x14000;STORE=MEM+0x15000;RELEASE=STORE+4;RETAIN=STORE+8
 m.put(SELF,VT);m.put(VT+0x20,RETAIN);m.put(DICT,DVT);m.put(DVT+0x28,RELEASE)
 m.put(0xfffffff006a116d0,0);m.put(0xfffffff006a116c8,MEM+0x16000)
 m.put(context,logging);m.put(context+0x63,0);m.put(context+0x228,STORE);m.put(context+0x230,MEM+0x17000);m.put(context+0x238,MEM+0x18000)
 m.put(0xfffffff005cab920,MEM+0x19000);m.put(MEM+0x19000,0x1234)
 for slot in (logging+0x28,logging+0x30):m.callbacks[m.get(slot)]=lambda:m.ret()
 parent=m.get(m.get(0xfffffff005cab908)+0x2c0)
 m.callbacks[parent]=lambda:(m.events.append('parent start fixture'),m.ret(0 if name=='parent_refusal' else 1))
 def matching():
  m.ensure(m.x(0));assert bytes(m.u.mem_read(m.x(0),17))==b'IOAESAccelerator\0\0'[:17]
  m.events.append('AES matching dictionary fixture');m.ret(DICT)
 def wait():
  assert m.x(0)==DICT and m.x(1)==0xffffffffffffffff;m.events.append('unbounded AES service wait requested')
  if name=='provider_wait':m.stop('AES provider wait boundary')
  else:m.ret(AES)
 m.callbacks[0xfffffff0046f9d4c]=matching;m.callbacks[0xfffffff0046f9d64]=wait
 m.callbacks[0xfffffff0046f9d04]=lambda:m.ret(0 if name=='provider_type_failure' else AES)
 m.callbacks[0xfffffff0046f98bc]=lambda:m.stop('native invalid AES provider panic')
 m.callbacks[RELEASE]=lambda:(m.events.append('matching dictionary release'),m.ret())
 m.callbacks[RETAIN]=lambda:(m.events.append('Image4 instance retain'),m.ret())
 for addr,label in [(0xfffffff0046f9fc8,'mutex lock'),(0xfffffff0046f9fd4,'mutex unlock'),(0xfffffff0046f9fa4,'nonce gate close'),(0xfffffff0046f9f98,'nonce gate open')]:m.callbacks[addr]=lambda label=label:(m.events.append(label),m.ret())
 def persist():
  assert m.x(2)==0x203;m.events.append('nonce persistence backend fixture')
  if name=='persistence_wait':m.stop('nonce persistence wait boundary')
  else:m.ret(30 if name=='persistence_readonly' else 0)
 m.callbacks[STORE]=persist
 m.callbacks[0xfffffff0046f0bb8]=lambda:m.stop('post-persistence success helper boundary')
 m.callbacks[0xfffffff0046f9c98]=lambda:m.stop('workloop allocation boundary')
 m.x(0,SELF);m.x(1,MEM+0x1a000)
 try:m.run(0xfffffff0046eeab8)
 except Exception:print(name,m.events,m.recent);raise
 expected={'parent_refusal':'return','provider_wait':'AES provider wait boundary','provider_type_failure':'native invalid AES provider panic','provider_to_nonce':'post-persistence success helper boundary','persistence_readonly':'workloop allocation boundary','persistence_wait':'nonce persistence wait boundary'}[name]
 assert m.stopped==expected,(name,m.stopped)
 if name=='parent_refusal':assert m.x(0)==0 and len(m.events)==1
 if name in ('provider_to_nonce','persistence_readonly','persistence_wait'):
  assert m.get(SELF+0x90)==AES and m.get(0xfffffff006a116d0)==SELF
  assert m.events.index('matching dictionary release')<m.events.index('Image4 instance retain')<m.events.index('nonce gate close')<m.events.index('nonce gate open')<m.events.index('nonce persistence backend fixture')
  assert 0xfffffff0046ed9ec in m.visits and 0xfffffff0046ed6bc in m.visits
 else:assert 'nonce gate open' not in m.events and m.get(0xfffffff006a116d0)==0
 rows.append(m.record(name))
write_report(a.output,c,rows,'Original Image4 service start and actual nonce producer/persistence functions, zero-domain context. Parent start, matching/wait/cast, OS virtual lifetime calls, locks/gate and persistence backend are explicit fixtures. Full service start, AES operations and scheduling not completed. Unbounded wait is an actual argument; no hardware deadlock claimed.')
r=json.loads(a.output.read_bytes());r['script_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();a.output.write_text(json.dumps(r,indent=2)+'\n');print('PASS',len(rows),'Image4 service ordering cases')
