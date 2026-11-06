"""Bind actual Image4 runtime initializer records and MAC registration ABI."""
import argparse,hashlib,json,struct,sys
from pathlib import Path
import unicorn
try:import tomllib
except ModuleNotFoundError:
 import pip._vendor.tomli as tomllib
 sys.modules['tomllib']=tomllib
import exec_carrier_model as H
from exec_carrier_model import Carrier,t
H.EXPECTED='c38fe9d4428467f9f3767408159f4d8327984fcaad2fbde175eca6ece93d313e';c=Carrier(t.R/'out/ufs-check-5-r1-qualified')
def read(va,n):return c.raw[c.b.backed(c.m,va,n):][:n]
def q(va):return struct.unpack('<Q',read(va,8))[0]
def string(va):return read(va,128).split(b'\0')[0].decode()
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.output.exists()
header=0xfffffff003e16dc0;segment=string(0xfffffff003e1ecf3);section=string(0xfffffff003e1ea05)
ncmds,cmdbytes=struct.unpack_from('<II',read(header,32),16);commands=read(header+32,cmdbytes);at=0;match=[]
for _ in range(ncmds):
 cmd,size=struct.unpack_from('<II',commands,at)
 if cmd==0x19:
  for i in range(struct.unpack_from('<I',commands,at+64)[0]):
   off=at+72+80*i;sect=commands[off:off+16].split(b'\0')[0].decode();seg=commands[off+16:off+32].split(b'\0')[0].decode()
   if (seg,sect)==(segment,section):match.append(struct.unpack_from('<QQ',commands,off+32))
 at+=size
assert len(match)==1;address,size=match[0];assert size%8==0
records=[]
for offset in range(0,size,8):
 obj=q(address+offset);records.append(dict(table_slot=hex(address+offset),object=hex(obj),name=string(q(obj+8)),initializer=hex(q(obj+0x10))))
result=dict(passed=True,kernel_sha256=H.EXPECTED,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),header=hex(header),segment=segment,section=section,table=hex(address),bytes=size,records=records,
 registration=dict(wrapper='0xfffffff0046ee518',import_slot='0xfffffff005cabaf0',target=hex(q(0xfffffff005cabaf0)),symbol='_mac_policy_register',init_slot='0xfffffff005caf840',init=q(0xfffffff005caf840),initbsd_slot='0xfffffff005caf848',initbsd=q(0xfffffff005caf848)),
 root_context_selection=dict(mode_import='_code_signing_configuration',native_root='0xfffffff005caceb0',monitor_import='_kernel_image4_get_monitor_exports',published_pointer='0xfffffff005cb14d0',getter='0xfffffff0046f0e20'),scope='Fixed iOS16 native header/section table and linked pointers; callbacks are statically enumerated, not assumed completed.')
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
