"""Execute native Image4 property copy and hash-method selection with shipped ADT bytes."""
import argparse,hashlib,importlib.util,json,sys
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
s=importlib.util.spec_from_file_location('adt',t.R/'scripts/check-nuwa-adt.py');adt=importlib.util.module_from_spec(s);s.loader.exec_module(adt)
path=t.R/'out/ufs-check-5-r1-qualified/qualified-readback/kernel.macho.adt';raw=path.read_bytes();assert hashlib.sha256(raw).hexdigest()=='42d3074d39960b09636169d62d5c16bf0ed1115d3e88875192bdea9e6529fd56'
chosen=adt.decode(raw)['/device-tree/chosen']['properties'];print('shipped crypto-hash-method',chosen.get('crypto-hash-method'));rows=[]
for name in ('shipped','missing_hash','oversize_hash','wrong_object_type','unknown_hash'):
 props=dict(chosen)
 if name=='missing_hash':props.pop('crypto-hash-method',None)
 if name=='oversize_hash':props['crypto-hash-method']=b'x'*25
 if name=='unknown_hash':props['crypto-hash-method']=b'unknown\0'
 m=Machine(c);ENTRY=MEM+0x10000;VT=MEM+0x11000;OBJ=MEM+0x12000;OVT=MEM+0x13000;DATA=MEM+0x14000;GET=MEM+0x18000;LEN=GET+4;BYTES=GET+8
 m.put(ENTRY,VT);m.put(VT+0x118,GET);m.put(OBJ,OVT);m.put(OVT+0xa0,LEN);m.put(OVT+0xd8,BYTES)
 m.put(0xfffffff005cab920,MEM+0x15000);m.put(MEM+0x15000,0x1234);active=[b'',None]
 def get():
  assert m.x(0)==ENTRY;m.ensure(m.x(1));key=bytes(m.u.mem_read(m.x(1),64)).split(b'\0')[0].decode();value=props.get(key)
  m.events.append(dict(property=key,present=value is not None,bytes=len(value) if value is not None else 0));active[:]=[value or b'',key]
  if value is None:m.ret(0)
  else:m.u.mem_write(DATA,value or b'\0');m.ret(OBJ)
 m.callbacks[GET]=get;m.callbacks[LEN]=lambda:m.ret(len(active[0]));m.callbacks[BYTES]=lambda:m.ret(DATA)
 m.callbacks[0xfffffff0046f9d04]=lambda:m.ret(0 if name=='wrong_object_type' and active[1]=='crypto-hash-method' else OBJ)
 m.callbacks[0xfffffff0046fa028]=lambda:m.stop('native Image4 property panic')
 m.x(0,ENTRY);m.x(1,0)
 try:m.run(0xfffffff0046f0fd0)
 except Exception:print(name,m.events,m.recent);raise
 assert 0xfffffff0046f07e8 in m.visits
 if name=='shipped':
  assert props.get('crypto-hash-method',b'').rstrip(b'\0')==b'sha2-384'
  assert m.stopped=='return' and m.x(0)==0xfffffff005cae660
 else:assert m.stopped=='native Image4 property panic',(name,m.stopped,m.x(0))
 rows.append(m.record(name))
write_report(a.output,c,rows,'Native iOS16 Image4 selector and property helper use exact shipped ADT values; execute original zero/copy/string comparison code. IORegistry/OSData virtual methods and dynamic cast are model boundaries. Negative inputs exist only in emulated memory. Proves selector contract, not real registry publication or authenticated provider startup.')
r=json.loads(a.output.read_bytes());r.update(script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),adt_sha256=hashlib.sha256(raw).hexdigest(),shipped_hash_method=chosen['crypto-hash-method'].decode().rstrip('\0'));a.output.write_text(json.dumps(r,indent=2)+'\n');print('PASS',len(rows),'native chosen contract cases')
