"""Read-only pinned original iOS16 AES input and CHECK5 carrier helpers."""
import hashlib,struct,xml.etree.ElementTree as ET
from pathlib import Path
import exec_carrier_model as H
CHECK5='c38fe9d4428467f9f3767408159f4d8327984fcaad2fbde175eca6ece93d313e'
DONOR='2ec297bac95bcba01046fd0148e97e7e5885c05a6c18827f39f534ba375c1221'
DONOR_PATH=Path('/mnt/d/Code/PortingiOSLegacy/nuwa/artifacts/ios16-donor-inspection/20261020T115253317035Z/original-iphone-kernelcache.macho')
def carrier(donor=False):
 H.EXPECTED=CHECK5;c=H.Carrier(H.t.R/'out/ufs-check-5-r1-qualified')
 if donor:
  c.raw=DONOR_PATH.read_bytes();assert hashlib.sha256(c.raw).hexdigest()==DONOR
  c.m=c.b.macho(c.raw);c.sy=c.m['symbols'];H.EXPECTED=DONOR
 return c
def read(c,va,size):return c.raw[c.b.backed(c.m,va,size):][:size]
def metadata(c):
 seg=next(s for s in c.m['segments'] if s['name']=='__PRELINK_INFO');root=ET.fromstring(read(c,seg['va'],seg['filesize']).rstrip(b'\0'));ids={x.attrib['ID']:x for x in root.iter() if 'ID' in x.attrib}
 def dec(x):
  if 'IDREF' in x.attrib:return dec(ids[x.attrib['IDREF']])
  a=list(x)
  if x.tag=='dict':return {dec(a[i]):dec(a[i+1]) for i in range(0,len(a),2)}
  if x.tag in ('array','plist'):return [dec(y) for y in a]
  if x.tag=='integer':return int(x.text or '0',0)
  return x.text or ''
 v=dec(root);return (v[0] if isinstance(v,list) else v)['_PrelinkInfoDictionary']