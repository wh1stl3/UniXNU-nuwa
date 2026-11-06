"""Extract authenticated donor dyld startup evidence from a readonly OS mount."""
import argparse,importlib.util,io,json,os,re,struct,subprocess
from pathlib import Path
from payload_code_integrity import inspect,trust_entries
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('core',ROOT/'scripts/audit-desktop-core-services.py')
core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
work=a.work.resolve();out=a.out.resolve();report=a.report.resolve()
core.need(os.name!='nt' and work.parent==Path('/var/tmp') and not work.exists(),'Fresh WSL workspace')
core.need(out.is_relative_to(ROOT/'out') and not out.exists() and report.is_relative_to(ROOT/'reports') and not report.exists(),'Fresh outputs')
parent=ROOT/'reports/desktop-readiness/2026-11-02-payload-code-integrity-r1/audit.json';prior=json.loads(parent.read_bytes())
core.need(prior['passed'] and prior['all_selected_original_trust_covered'] and not prior['missing_original_trust_entries'],'Parent integrity')
item=next(x for x in prior['inputs'] if x['component']=='OS');image=Path(item['path'])
before=core.A.digests(image);core.need(before==item['after'],'Donor drift')
core.need(core.C.sha(core.C.TOOL.read_bytes())==core.C.TOOL_SHA,'Reader drift')
bundle=(ROOT/'out/payload-s1-r1/kernel.macho.trustcache').read_bytes();core.need(core.C.sha(bundle)==prior['trust_bundle_sha256'],'Trust bundle drift');trust=trust_entries(bundle)
work.mkdir();out.mkdir(parents=True);mount=work/'mount';mount.mkdir();mounted=False;error=None;records=[]
def run(argv):subprocess.run(list(map(str,argv)),check=True,capture_output=True,timeout=120)
try:
 run([core.C.TOOL,'-o','ro',image,mount]);mounted=True;run(['mountpoint','-q',mount]);root=mount/'root' if (mount/'root').is_dir() else mount
 for name in ('/usr/lib/dyld','/usr/lib/libignition.dylib'):
  try:path=core.C.rooted(root,name)
  except FileNotFoundError:
   records.append(dict(path=name,present=False));continue
  if not path.exists():records.append(dict(path=name,present=False));continue
  raw=path.read_bytes();signature=inspect(io.BytesIO(raw),len(raw),trust);core.need(signature['original_trust_covered'],'Original trust mismatch')
  previous=next((x for x in prior['records'] if x['path']==name),None)
  if previous:core.need(core.C.sha(raw)==previous['sha256'],'Binary drift')
  dest=out/path.name;dest.write_bytes(raw)
  core.need(struct.unpack_from('<I',raw)[0]==0xfeedfacf,'Thin arm64 Mach-O required')
  pos=32;symbols={};segments=[]
  for _ in range(struct.unpack_from('<I',raw,16)[0]):
   cmd,size=struct.unpack_from('<II',raw,pos)
   if cmd==2:
    sy,ns,st,ss=struct.unpack_from('<4I',raw,pos+8)
    for i in range(ns):
     sx,typ,sect,desc,value=struct.unpack_from('<IBBHQ',raw,sy+i*16)
     if sx and sx<ss:
      s=raw[st+sx:raw.index(b'\0',st+sx,st+ss)].decode('utf8','replace');symbols[s]=dict(address=hex(value),type=typ,section=sect)
   if cmd==0x19:
    seg=raw[pos+8:pos+24].rstrip(b'\0').decode();addr,length,off,sz=struct.unpack_from('<4Q',raw,pos+24);segments.append(dict(name=seg,address=hex(addr),size=length,offset=off,file_size=sz))
   pos+=size
  strings=[dict(offset=hex(m.start()),text=m.group().decode()) for m in re.finditer(rb'[ -~]{7,}',raw) if any(k in m.group().lower() for k in (b'ignit',b'cryptex',b'preboot',b'dyld-'))]
  (out/(path.name+'.symbols.json')).write_text(json.dumps(symbols,indent=2)+'\n')
  records.append(dict(path=name,present=True,sha256=core.C.sha(raw),bytes=len(raw),signature=signature,segments=segments,startup_strings=strings,startup_symbols={k:v for k,v in symbols.items() if any(s in k.lower() for s in ('ignit','cachefinder','commpage'))}))
  print(name,len(raw),'bytes;',len(symbols),'symbols;',len(strings),'startup strings',flush=True)
except BaseException as exc:error=dict(type=type(exc).__name__,message=str(exc))
finally:
 if mounted:
  try:run(['fusermount','-u',mount])
  except BaseException as exc:error=error or dict(type=type(exc).__name__,message=str(exc))
 cleanup=subprocess.run(['mountpoint','-q',str(mount)],capture_output=True).returncode!=0;after=core.A.digests(image)
 if before!=after:error=error or dict(type='InputChanged',message=str(image))
 report.parent.mkdir(parents=True,exist_ok=True);report.write_text(json.dumps(dict(passed=error is None and cleanup,error=error,mount_cleanup_complete=cleanup,input=dict(path=str(image),before=before,after=after),parent_sha256=core.C.sha(parent.read_bytes()),script_sha256=core.C.sha(Path(__file__).read_bytes()),records=records,device_accessed=False,scope='Original trusted donor bytes and symbols; no execution or AMFI policy claim'),indent=2)+'\n')
core.need(error is None and cleanup,'Inspection failed: '+str(error))
