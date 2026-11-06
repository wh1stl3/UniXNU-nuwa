"""Locate actual Image4 AES name references and linked provider symbols; no provider-ready claim."""
import argparse,hashlib,json,struct,sys,xml.etree.ElementTree as ET
from pathlib import Path
import unicorn,capstone
try:import tomllib
except ModuleNotFoundError:
 import pip._vendor.tomli as tomllib
 sys.modules['tomllib']=tomllib
import exec_carrier_model as H
from exec_carrier_model import Carrier,t
H.EXPECTED='c38fe9d4428467f9f3767408159f4d8327984fcaad2fbde175eca6ece93d313e';c=Carrier(t.R/'out/ufs-check-5-r1-qualified')
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.output.exists()
def read(va,n):return c.raw[c.b.backed(c.m,va,n):][:n]
strings=[]
for seg in c.m['segments']:
 data=c.raw[seg['fileoff']:seg['fileoff']+seg['filesize']];at=0
 while True:
  at=data.find(b'IOAESAccelerator\0',at)
  if at<0:break
  strings.append(seg['va']+at);at+=1
md=capstone.Cs(capstone.CS_ARCH_ARM64,capstone.CS_MODE_ARM);start=0xfffffff0046e4000
instructions=list(md.disasm(read(start,0x16000),start));refs=[]
for i,x in enumerate(instructions[:-1]):
 if x.mnemonic!='adrp':continue
 reg,page=x.op_str.split(', ');page=int(page.lstrip('#'),0)
 for y in instructions[i+1:i+3]:
  parts=y.op_str.split(', ')
  if y.mnemonic=='add' and len(parts)==3 and parts[0]==reg and parts[1]==reg and parts[2].startswith('#'):
   target=page+int(parts[2][1:],0)
   if target in strings:refs.append(dict(site=hex(x.address),string=hex(target),instructions=[f'{z.address:#x} {z.mnemonic} {z.op_str}' for z in instructions[max(0,i-5):i+23]]))
info=next(s for s in c.m['segments'] if s['name']=='__PRELINK_INFO');xml=read(info['va'],info['filesize']).rstrip(b'\0');root=ET.fromstring(xml);ids={x.attrib['ID']:x for x in root.iter() if 'ID' in x.attrib}
def decode(x):
 if 'IDREF' in x.attrib:return decode(ids[x.attrib['IDREF']])
 children=list(x)
 if x.tag=='dict':return {decode(children[i]):decode(children[i+1]) for i in range(0,len(children),2)}
 if x.tag in ('array','plist'):return [decode(y) for y in children]
 if x.tag=='integer':return int(x.text or '0',0)
 if x.tag in ('true','false'):return x.tag=='true'
 return x.text or ''
metadata=decode(root);metadata=metadata[0] if isinstance(metadata,list) else metadata
entries=metadata['_PrelinkInfoDictionary'];providers=[]
for entry in entries:
 serialized=json.dumps(entry)
 if any(token in serialized for token in ('AES','AppleImage4')):providers.append(dict(bundle=entry.get('CFBundleIdentifier'),personalities=entry.get('IOKitPersonalities',{})))
result=dict(passed=True,kernel_sha256=H.EXPECTED,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),strings=list(map(hex,strings)),image4_refs=refs,prelink_entries=len(entries),aes_image4_entries=providers,
 linked_native_aes_symbols={k:hex(v) for k,v in c.sy.items() if 'NativeAES' in k or 'native_aes_' in k},
 scope='Bounded Image4 ADRP+ADD references and kernel symbol table. Symbol/name presence is not driver selection, publication, matching or service readiness; unmatched instruction forms not exhaustively covered.')
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
