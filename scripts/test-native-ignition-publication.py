"""Run actual iOS16 sysctl registration and ignition-blob field population."""
import argparse,hashlib,json,struct,sys
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
entry=0xfffffff0046e467c;blob=0xfffffff005cac328
for name,identity_len,kind,optional,special in [('base',16,0,False,False),('optional_digest',16,3,True,False),('special_identity',16,0,False,True),('identity_overflow',17,0,False,False),('kind_overflow',16,4,False,False)]:
 m=Machine(c);ROOT=MEM+0x10000;IDENT=MEM+0x11000;KIND=MEM+0x12000;DIGEST=MEM+0x13000
 m.put(ROOT+8,IDENT);m.put(ROOT+0x10,KIND);m.put(ROOT+0x30,DIGEST if optional else 0)
 m.put(IDENT+8,0xfffffff005cb1090 if special else 0);m.put(IDENT+0x48,identity_len);m.put(KIND+8,kind)
 m.u.mem_write(IDENT+0x18,bytes(range(0x20)));m.u.mem_write(IDENT+0x50,b'I'*16);m.u.mem_write(DIGEST+8,b'D'*64)
 m.ensure(blob);before=bytes(m.u.mem_read(blob,0x84))
 m.callbacks[0xfffffff0046f0e20]=lambda:m.ret(ROOT)
 m.callbacks[0xfffffff0046f0cf4]=lambda:m.ret(0x12345678)
 m.callbacks[0xfffffff0046fa0d0]=lambda:(m.events.append(dict(register_oid=hex(m.x(0)))),m.ret())
 def copy():
  assert m.x(2)<=m.x(3);m.u.mem_write(m.x(0),bytes(m.u.mem_read(m.x(1),m.x(2))));m.ret()
 m.callbacks[0xfffffff0046f9d94]=copy;m.callbacks[0xfffffff0046f9dac]=copy
 m.callbacks[0xfffffff0046fa028]=lambda:m.stop('native panic boundary')
 m.run(entry)
 assert [e['register_oid'] for e in m.events]==['0xfffffff006a112e0','0xfffffff006a11330','0xfffffff006a113d0']
 if identity_len>16 or kind>3:assert m.stopped=='native panic boundary'
 else:
  assert m.stopped=='return' and m.u.reg_read(UC_ARM64_REG_SP)==STACK
  after=bytes(m.u.mem_read(blob,0x84));expected=bytearray(before)
  expected[2:26]=bytes(range(24));expected[26:42]=struct.pack('<4I',24,25,26,27);expected[42:46]=bytes(4)
  expected[0x72:0x82]=b'I'*16;expected[0x2e:0x32]=struct.pack('<I',kind)
  if optional:expected[0x32:0x72]=b'D'*64
  if special:expected[0x12:0x1a]=struct.pack('<Q',0x12345678)
  assert after==expected,(name,after.hex(),expected.hex())
 rows.append(m.record(name))
callers=[]
for seg in c.m['segments']:
 for off in range(seg['fileoff'],seg['fileoff']+seg['filesize']-3,4):
  word=struct.unpack_from('<I',c.raw,off)[0]
  if word&0xfc000000!=0x94000000:continue
  imm=word&0x3ffffff;imm=imm-(1<<26) if imm&(1<<25) else imm
  pc=seg['va']+off-seg['fileoff']
  if pc+imm*4==entry:callers.append(hex(pc))
write_report(a.output,c,rows,'Actual sysctl registration/blob serializer and overflow panic branches. Root context, sysctl registration API, checked copy and special identity derivation are explicit fixtures. No authenticated input, provider start, gate scheduling, dyld consumption or device arrival proved. Direct BL candidates are static encodings, not executed caller evidence.')
r=json.loads(a.output.read_bytes());r.update(script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),entry=hex(entry),direct_bl_candidates=callers);a.output.write_text(json.dumps(r,indent=2)+'\n');print('PASS',len(rows),'native ignition publication cases',callers)
