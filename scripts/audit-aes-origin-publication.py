"""Pin donor derivation/publication and current-package static provider coverage."""
import argparse,hashlib,importlib.util,json,struct,sys
from pathlib import Path
import unicorn,capstone
try:import tomllib
except ModuleNotFoundError:
 import pip._vendor.tomli as tomllib
 sys.modules['tomllib']=tomllib
from aes_origin_inputs import *
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.output.exists()
d=carrier(True);c=carrier();md=capstone.Cs(capstone.CS_ARCH_ARM64,capstone.CS_MODE_ARM)
def ins(obj,addr,size):return [f'{x.address:#x} {x.mnemonic} {x.op_str}' for x in md.disasm(read(obj,addr,size),addr)]
def ptr(obj,addr):return struct.unpack('<Q',read(obj,addr,8))[0]
def cstr(obj,addr):return read(obj,addr,80).split(b'\0')[0].decode()
table=[]
for i in range(12):
 row=read(d,0xfffffff007adc5c8+i*24,24);selector,parent=struct.unpack_from('<II',row);table.append(dict(index=i,selector=selector,parent_selector=parent,derivation_block=row[8:].hex()))
assert table[10]==dict(index=10,selector=2212,parent_selector=2000,derivation_block='0c31f7df81924d038cb437fa0360f7c9')
spec=importlib.util.spec_from_file_location('adt',H.t.R/'scripts/check-nuwa-adt.py');adt=importlib.util.module_from_spec(spec);spec.loader.exec_module(adt)
adtpath=H.t.R/'out/ufs-check-5-r1-qualified/qualified-readback/kernel.macho.adt';adtraw=adtpath.read_bytes();nodes=adt.decode(adtraw)
selected=lambda obj:[dict(bundle=e['CFBundleIdentifier'],personalities=e.get('IOKitPersonalities',{})) for e in metadata(obj) if any(s in e['CFBundleIdentifier'] for s in ('AES','CryptoAccelerator','Image4'))]
vt=ptr(c,0xfffffff005cab908);targets=[]
for off in (0x2a0,0x2b0):
 value=ptr(c,vt+16+off);targets.append(dict(offset=hex(off),target=hex(value),symbols=[k for k,v in c.sy.items() if v==value]))
result=dict(passed=True,check5_sha256=CHECK5,donor_sha256=DONOR,donor_derivation_table=table,check5_selected_metadata=selected(c),donor_selected_metadata=selected(d),
 adt_sha256=hashlib.sha256(adtraw).hexdigest(),adt_aes_matches=[path for path,node in nodes.items() if 'aes' in path.lower() or any(b'aes,s8000' in v for v in node['properties'].values())],
 current_ioservice_import_vtable=hex(vt),current_ioservice_instance_vtable=hex(vt+16),current_ioservice_slots=targets,
 donor_aes_vtable_slots={hex(off):hex(ptr(d,0xfffffff006eb9aa8+off)) for off in (0x2b0,0x550,0x588)},
 donor_parent_start_import=hex(ptr(d,ptr(d,0xfffffff006eb9a28)+0x2c0)),
 donor_wait_resource=cstr(d,0xfffffff004e14fcc),donor_platform_function=cstr(d,0xfffffff004e14fd2),
 code=dict(donor_table_setup=ins(d,0xfffffff0062638ec,24),donor_parent_start=ins(d,0xfffffff006263a18,32),family_wait_secureroot=ins(d,0xfffffff0056d95f0,0xb0),family_publish=ins(d,0xfffffff0056d9830,28),parent2000_hardware_selection=ins(d,0xfffffff006264124,0x2c),special_lookup=ins(d,0xfffffff0056d9ffc,0x60),native_domain_count_publish=ins(c,0xfffffff0046ed2f4,0x34)),
 scope='Static exact donor and CHECK5 bindings. Donor MMIO/UID and publication are not executed or transplanted. Metadata and ADT absence do not prove all runtime provider absence; no nuwa crypto readiness.',script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
def execspan(obj,bundle):
 e=next(e for e in metadata(obj) if e['CFBundleIdentifier']==bundle);va=e['_PrelinkExecutableLoadAddr'];hdr=read(obj,va,32);at=va+32
 for _ in range(struct.unpack_from('<I',hdr,16)[0]):
  cmd,size=struct.unpack('<II',read(obj,at,8))
  if cmd==0x19 and read(obj,at+8,16).split(b'\0')[0]==b'__TEXT_EXEC':return struct.unpack('<QQ',read(obj,at+24,16))
  at+=size
 raise AssertionError(bundle)
import re
cb,cs=execspan(c,'com.apple.iokit.IOCryptoAcceleratorFamily');db,ds=execspan(d,'com.apple.iokit.IOCryptoAcceleratorFamily')
normal=lambda lines:[re.sub(r'0x[0-9a-f]{16}', 'ADDRESS',line.split(' ',1)[1]) for line in lines]
family=[]
for offset,size,label in ((0xffc,0x60,'special-key lookup'),(0x1420,0x2fc,'special-key creation loops'),(0xc8c,0x1e8,'descriptor AES request')):
 old=ins(d,db+offset,size);new=ins(c,cb+offset,size)
 family.append(dict(label=label,donor_entry=hex(db+offset),check5_entry=hex(cb+offset),size=size,normalized_instructions_identical=normal(old)==normal(new),donor_code_sha256=hashlib.sha256(read(d,db+offset,size)).hexdigest(),check5_code_sha256=hashlib.sha256(read(c,cb+offset,size)).hexdigest()))
result['family_code_binding']=family
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(family,indent=2))