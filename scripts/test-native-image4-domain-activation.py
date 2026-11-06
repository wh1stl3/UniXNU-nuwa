"""Execute native nonce initializer through count publication from real prologue."""
import argparse,hashlib,json,sys
from pathlib import Path
import unicorn
try:import tomllib
except ModuleNotFoundError:
 import pip._vendor.tomli as tomllib
 sys.modules['tomllib']=tomllib
from exec_carrier_model import *
from aes_origin_inputs import carrier
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.output.exists()
c=carrier();rows=[];CONTEXT=0xfffffff005caea20;LOG=0xfffffff005cb14d8
for errno in (2,84,96,5):
 m=Machine(c);POLICY=MEM+0x10000;GUARD=POLICY+0x1000
 m.put(0xfffffff005cab920,GUARD);m.put(GUARD,0x1234)
 m.callbacks[0xfffffff0046f0e10]=lambda:m.ret(POLICY)
 m.callbacks[0xfffffff0046f0f30]=lambda:m.ret(0xfffffff005cae660)
 m.callbacks[0xfffffff0046f9f68]=lambda:m.ret(POLICY+0x100)
 m.callbacks[0xfffffff0046f9f80]=lambda:m.ret(POLICY+0x200)
 for addr,label in ((0xfffffff0046f9fc8,'lock'),(0xfffffff0046f9fd4,'unlock'),(0xfffffff0046f9f8c,'gate close')):m.callbacks[addr]=lambda label=label:(m.events.append(label),m.ret())
 for off in (0x28,0x30):m.callbacks[m.get(LOG+off)]=lambda:m.ret()
 m.callbacks[0xfffffff0046f06c0]=lambda:(m.events.append('persisted seed errno '+str(errno)),m.ret(errno))
 def digest():
  assert m.x(2)==11;m.u.mem_write(m.x(3),bytes(64));m.events.append('boot digest explicit fixture');m.ret()
 m.callbacks[m.get(LOG+0x50)]=digest
 # Stop only after the actual instruction published count 11, before per-domain seed initialization.
 m.callbacks[0xfffffff0046ed328]=lambda:m.stop('fresh-domain initialization boundary')
 m.callbacks[0xfffffff0046ed040]=lambda:m.stop('existing-domain initialization boundary')
 m.callbacks[0xfffffff0046fa028]=lambda:m.stop('native initializer panic')
 try:m.run(0xfffffff0046ecc14)
 except Exception:print(errno,m.recent);raise
 if errno==5:assert m.stopped=='native initializer panic' and m.get(CONTEXT+0x63)==0
 else:assert m.stopped=='fresh-domain initialization boundary' and m.get(CONTEXT+0x63)==11
 row=m.record('persisted_errno_'+str(errno));row['domain_count']=m.get(CONTEXT+0x63);rows.append(row)
write_report(a.output,c,rows,'Actual CHECK5 nonce initializer prologue through persistent-read decision and native count publication. IORegistry persisted-read errno, logging/digest, lock allocation/gate are explicit fixtures; native copying and branch code execute. Stops before per-domain seed creation. Shows missing seed does not imply zero domains; does not certify active hardware domains or entire init.')
r=json.loads(a.output.read_bytes());r['script_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();a.output.write_text(json.dumps(r,indent=2)+'\n');print('PASS',len(rows),'native domain count cases')