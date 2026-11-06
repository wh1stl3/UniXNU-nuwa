"""Read cached call neighborhoods and concrete display callback initializers."""
import argparse,hashlib,importlib.util,json,struct,subprocess
from pathlib import Path
import capstone as CS
from desktop_cache import CacheSet
from payload_cache_slide import parse_v2,rebase_page
R=Path(__file__).resolve().parents[1]

def main():
 p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 assert not a.work.exists() and a.work.parent==Path('/var/tmp') and not a.output.exists()
 parent=R/'reports/desktop-readiness/2026-11-03-offline-desktop-r7/cached-contracts-final.json';d=json.loads(parent.read_bytes());assert d['passed']
 spec=importlib.util.spec_from_file_location('core',R/'scripts/audit-desktop-core-services.py');core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
 assert hashlib.sha256(core.C.TOOL.read_bytes()).hexdigest()==core.C.TOOL_SHA
 source=Path(d['source_image']['path']);assert source.stat().st_size==d['source_image']['after']['bytes']
 a.work.mkdir();cache=None;mounted=False;error=None;windows=[];stores=[];resolved=[]
 try:
  subprocess.run([str(core.C.TOOL),'-o','ro',str(source),str(a.work)],check=True,capture_output=True);mounted=True
  root=a.work/'root' if (a.work/'root').is_dir() else a.work;cache=CacheSet(root/'System/Library/Caches/com.apple.dyld/dyld_shared_cache_arm64')
  md=CS.Cs(CS.CS_ARCH_ARM64,CS.CS_MODE_ARM);md.detail=True
  def window(path,start,size,reason):
   raw=cache.vmread(start,size);ins=list(md.disasm(raw,start))
   return dict(path=path,address=hex(start),bytes=raw.hex(),sha256=hashlib.sha256(raw).hexdigest(),reason=reason,
    instructions=[dict(pc=hex(i.address),instruction=i.mnemonic+' '+i.op_str) for i in ins])
  def pointer(addr):
   mapping=next(m for m in cache.mappings if m['address']<=addr<m['address']+m['size']);reader=mapping['reader']
   header=reader.read(0,0x200);off,count=struct.unpack_from('<II',header,0x138);rows=reader.read(off,count*56)
   row=next(struct.unpack_from('<6Q2I',rows,i*56) for i in range(count) if struct.unpack_from('<Q',rows,i*56)[0]==mapping['address'])
   page=addr&~4095;raw=cache.vmread(page,4096)
   if row[4]:raw=rebase_page(raw,(page-mapping['address'])//4096,parse_v2(reader.read(row[3],row[4]),mapping['size']),0)[0]
   return struct.unpack_from('<Q',raw,addr-page)[0]
  for record in d['records']:
   if 'BoardServices' in record['path']:
    for call in record['calls']:
     if call['api'] in ('_bootstrap_look_up','_xpc_connection_create_mach_service'):
      windows.append(window(record['path'],int(call['pc'],16)-160,224,call))
   if 'IOMobileFramebuffer.framework' not in record['path']:continue
   for span in record['code_spans']:
    raw=cache.vmread(span['address'],span['size']);assert hashlib.sha256(raw).hexdigest()==span['sha256']
    ins=list(md.disasm(raw,span['address']))
    for ix,i in enumerate(ins):
     op=i.operands
     if i.mnemonic in ('str','stp') and op[-1].type==CS.arm64.ARM64_OP_MEM and op[-1].mem.disp in (0x720,0x728,0x748,0x750):
      stores.append(window(record['path'],max(span['address'],i.address-120),224,dict(store_pc=hex(i.address),offset=hex(op[-1].mem.disp))))
  windows.append(window('RunningBoardServices',0x1937bad00,32,'Objective-C selector trampoline'))
  obj=0x1d682a980;raw=cache.vmread(obj,32);chars=pointer(obj+16);length=struct.unpack_from('<Q',raw,24)[0];assert 0<length<256
  resolved.append(dict(object=hex(obj),raw=raw.hex(),character_pointer=hex(chars),length=length,value=cache.vmread(chars,length).decode(),evidence='constant string layout and slide-v2 character pointer; selector trampoline separately inspected'))
  selector=pointer(0x1d6837570);resolved.append(dict(selector_reference='0x1d6837570',pointer=hex(selector),value=cache.vmread(selector,128).split(b'\0')[0].decode()))
  for start,size in ((0x1af2267dc,0x3b0),(0x1af226a80,0x100),(0x1af226f5c,0x250),(0x1af2271f8,0x110),(0x1af223648,0x80)):
   windows.append(window('IOMobileFramebuffer',start,size,'open branch / callback implementation'))
  reads=cache.report()['reads']
 except BaseException as exc:error=dict(type=type(exc).__name__,message=str(exc));reads=[]
 finally:
  if cache:cache.close()
  if mounted:subprocess.run(['fusermount','-u',str(a.work)],check=True,capture_output=True)
 cleaned=subprocess.run(['mountpoint','-q',str(a.work)],capture_output=True).returncode!=0
 result=dict(passed=error is None and cleaned,error=error,windows=windows,callback_stores=stores,resolved_strings=resolved,reads=reads,mount_cleanup_complete=cleaned,
  parent_sha256=hashlib.sha256(parent.read_bytes()).hexdigest(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),device_accessed=False)
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');assert result['passed'],error
 print('PASS',len(windows),'service neighborhoods;',len(stores),'display callback stores')
if __name__=='__main__':main()
