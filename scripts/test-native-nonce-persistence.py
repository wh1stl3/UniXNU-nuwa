"""Execute the actual callback after nonce gate release; never equate it with blob publication."""
import argparse,hashlib,json,sys
from pathlib import Path
import unicorn
try:import tomllib
except ModuleNotFoundError:
 import pip._vendor.tomli as tomllib
 sys.modules['tomllib']=tomllib
import exec_carrier_model as H
from exec_carrier_model import *
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.output.exists()
H.EXPECTED='c38fe9d4428467f9f3767408159f4d8327984fcaad2fbde175eca6ece93d313e';c=Carrier(t.R/'out/ufs-check-5-r1-qualified');rows=[]
context=0xfffffff005caea20;entry=0xfffffff0046ed6bc;blob=0xfffffff005cac328
for name,errno in [('persist_success',0),('persist_nospace',28),('persist_readonly',30),('persist_not_supported',83),('persist_unexpected',5),('persist_wait',None)]:
 m=Machine(c);LOG=MEM+0x10000;GETLOG=MEM+0x11000;LOGFN=MEM+0x12000;STORE=MEM+0x13000
 m.put(context,LOG);m.put(LOG+0x28,LOGFN);m.put(LOG+0x30,GETLOG);m.put(context+0x228,STORE);m.put(context+0x63,0)
 m.callbacks[GETLOG]=lambda:m.ret();m.callbacks[LOGFN]=lambda:m.ret()
 m.put(0xfffffff005cab920,MEM+0x16000);m.put(MEM+0x16000,0x1234)
 for off in range(0x20,0x62):m.put(context+off,off&255,1)
 m.ensure(blob);before=bytes(m.u.mem_read(blob,0x84))
 def persist():
  assert m.x(2)==0x203
  m.ensure(m.x(0));key=bytes(m.u.mem_read(m.x(0),64)).split(b'\0')[0].decode()
  data=bytes(m.u.mem_read(m.x(1),m.x(2)))
  assert data[:0x42]==bytes(range(0x20,0x62)) and data[0x42]==1 and data[0x43:0x4b]==bytes(8)
  m.events.append(dict(call='context persistence callback',key=key,bytes=len(data),data_sha256=hashlib.sha256(data).hexdigest()))
  if errno is None:m.stop('persistence callback wait boundary')
  else:m.ret(errno)
 m.callbacks[STORE]=persist
 m.callbacks[0xfffffff0046fa028]=lambda:m.stop('native panic boundary')
 m.x(0,context);m.run(entry)
 assert bytes(m.u.mem_read(blob,0x84))==before
 if errno is None:assert m.stopped=='persistence callback wait boundary'
 elif errno==5:assert m.stopped=='native panic boundary'
 else:assert m.stopped=='return' and m.x(0)==errno and m.u.reg_read(UC_ARM64_REG_SP)==STACK
 rows.append(m.record(name))
write_report(a.output,c,rows,'Actual post-gate nonce persistence serializer, zero-domain context, real return/error/panic branches. Log and persistence backend are fixtures. No nonce domains, NVRAM write, blob publication, AES provider or scheduler implementation is certified.')
r=json.loads(a.output.read_bytes());r.update(script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),entry=hex(entry),blob_unchanged_in_all_cases=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print('PASS',len(rows),'native nonce persistence cases')
