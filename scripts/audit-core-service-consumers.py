"""Read fixed OS binaries/plists; trace constant call arguments, not just providers.

Only file inputs, read-only APFS mount. Does not execute donor programs or enable jobs.
"""
import argparse,hashlib,importlib.util,json,plistlib,re,struct,subprocess
from pathlib import Path
import capstone as CS
import desktop_root_contract as D
from desktop_namespace import Namespace
R=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('core',R/'scripts/audit-desktop-core-services.py');core=importlib.util.module_from_spec(s);s.loader.exec_module(core)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def inspect(raw):
 assert struct.unpack_from('<I',raw)[0]==0xfeedfacf
 n,cmdbytes=struct.unpack_from('<II',raw,16);at=32;sections=[];segments=[];symbols=[];indirect=[];st=None;dy=None;loadcommands=[]
 for _ in range(n):
  cmd,size=struct.unpack_from('<II',raw,at);assert size>=8 and at+size<=32+cmdbytes
  loadcommands.append(dict(command=hex(cmd),bytes=size,file_offset=at))
  if cmd==0x19:
   va,vs,off,fs=struct.unpack_from('<QQQQ',raw,at+24);segments.append((va,vs,off,fs))
   for i in range(struct.unpack_from('<I',raw,at+64)[0]):
    pos=at+72+i*80;name=raw[pos:pos+16].split(b'\0')[0].decode();sv,sz,so=struct.unpack_from('<QQI',raw,pos+32);flags,r1,r2=struct.unpack_from('<III',raw,pos+64)
    sections.append(dict(name=name,va=sv,size=sz,offset=so,flags=flags,r1=r1,r2=r2))
  elif cmd==2:st=struct.unpack_from('<IIII',raw,at+8)
  elif cmd==0xb:dy=struct.unpack_from('<18I',raw,at+8)
  at+=size
 assert at==32+cmdbytes
 if st:
  so,count,stro,strlen=st
  for i in range(count):
   ix,typ,sec,desc,value=struct.unpack_from('<IBBHQ',raw,so+16*i)
   assert ix<strlen;end=raw.index(b'\0',stro+ix,stro+strlen);symbols.append(dict(name=raw[stro+ix:end].decode(errors='replace'),type=typ,value=value))
 if dy:
  offset,count=dy[12:14];indirect=list(struct.unpack_from('<'+'I'*count,raw,offset))
 stubs={}
 for sec in sections:
  if sec['flags']&255==8:
   assert sec['r2']>0
   for i in range(sec['size']//sec['r2']):
    index=indirect[sec['r1']+i]
    if index&0xc0000000:continue
    stubs[sec['va']+i*sec['r2']]=symbols[index]['name']
 def string(address):
  if address is None:return None
  for va,vs,off,fs in segments:
   if va<=address<va+fs:
    start=off+address-va;end=raw.find(b'\0',start,min(off+fs,start+1024))
    if end<0:return None
    data=raw[start:end]
    if not data or any(x<32 or x>126 for x in data):return None
    return data.decode()
 refs=[];calls=[];unresolved={};md=CS.Cs(CS.CS_ARCH_ARM64,CS.CS_MODE_ARM);md.detail=True
 apis={'_xpc_connection_create_mach_service':0,'_xpc_connection_create':0,'_bootstrap_look_up':1,'_bootstrap_look_up2':1,
       '_open':0,'_openat':1,'_stat':0,'_lstat':0,'_access':0,'_mkdir':0,'_unlink':0,'_rename':0,'_fopen':0,'_opendir':0}
 for sec in sections:
  if sec['name']!='__text':continue
  code=raw[sec['offset']:sec['offset']+sec['size']]
  targets={i.operands[-1].imm for i in md.disasm(code,sec['va']) if i.operands and i.operands[-1].type==CS.arm64.ARM64_OP_IMM and (i.group(CS.CS_GRP_JUMP) or i.group(CS.CS_GRP_CALL))}
  constants={}
  for ins in md.disasm(code,sec['va']):
   if ins.address in targets:constants.clear()
   op=ins.operands;pending={}
   def reg(o):return ins.reg_name(o.reg).replace('w','x',1)
   if ins.mnemonic in ('adrp','adr') and len(op)==2:pending[reg(op[0])]=(op[1].imm,hex(ins.address))
   elif ins.mnemonic=='add' and len(op)==3 and op[2].type==CS.arm64.ARM64_OP_IMM and reg(op[1]) in constants:
    value,origin=constants[reg(op[1])];pending[reg(op[0])]=(value+(op[2].imm<<op[2].shift.value),origin)
   elif ins.mnemonic=='mov' and len(op)==2:
    if op[1].type==CS.arm64.ARM64_OP_REG and reg(op[1]) in constants:pending[reg(op[0])]=constants[reg(op[1])]
    elif op[1].type==CS.arm64.ARM64_OP_IMM:pending[reg(op[0])]=(op[1].imm,hex(ins.address))
   if ins.mnemonic in ('bl','b') and op and op[0].type==CS.arm64.ARM64_OP_IMM:
    api=stubs.get(op[0].imm)
    if api in apis:
     arg='x'+str(apis[api]);value,origin=constants.get(arg,(None,None));literal=string(value)
     if literal:
      call=dict(pc=hex(ins.address),api=api,arg=arg,literal=literal,literal_va=hex(value),producer_pc=origin,proof='constant argument within straight-line instruction block to imported stub')
      if api=='_xpc_connection_create_mach_service':
       flags=constants.get('x2',(None,None))[0];call['flags']=flags;call['endpoint_role']='unknown' if flags is None else 'listener' if flags&1 else 'client'
      calls.append(call)
     else:unresolved[api]=unresolved.get(api,0)+1
   for r in ins.regs_access()[1]:constants.pop(ins.reg_name(r).replace('w','x',1),None)
   constants.update(pending)
   # No constant propagation through branches, calls, returns or jump tables.
   if ins.group(CS.CS_GRP_JUMP) or ins.group(CS.CS_GRP_CALL) or ins.group(CS.CS_GRP_RET):constants.clear()
 for sec in sections:
  if sec['name']!='__cstring':continue
  area=raw[sec['offset']:sec['offset']+sec['size']]
  for match in re.finditer(rb'[^\x00]+',area):
   try:value=match.group().decode('ascii')
   except UnicodeDecodeError:continue
   if value.startswith(('/var/','/private/var/','com.apple.')):refs.append(dict(va=hex(sec['va']+match.start()),value=value,evidence='literal only; not proven consumer or required path'))
 return dict(commands=loadcommands,imports=sorted(set(x['name'] for x in symbols if x['type']&0xe==0)),constant_calls=calls,unresolved_call_counts=unresolved,literals=refs,
  limitation='Standalone __text straight-line constants only; no interprocedural, Objective-C, dynamic strings, framework/shared-cache implementation or runtime path proof')

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 work=a.work.resolve();out=a.out.resolve();assert work.parent==Path('/var/tmp') and not work.exists() and out.is_relative_to(R/'out') and not out.exists() and not a.output.exists()
 auditpath=R/'reports/desktop-readiness/2026-10-30-core-services-r1/audit.json';audit=json.loads(auditpath.read_bytes());assert audit['error'] is None and audit['mount_cleanup_complete']
 sourcepath=R/'reports/desktop-readiness/2026-10-27-contract-r1/data-source-r2.json';source=json.loads(sourcepath.read_bytes())
 item=next(x for x in audit['inputs'] if x['component']=='OS');image=Path(item['path']);assert image.stat().st_size==item['before']['bytes']
 assert sha(core.C.TOOL.read_bytes())==core.C.TOOL_SHA
 work.mkdir();out.mkdir();mounted=False;error=None;records=[];datafiles=[];result={};commands=[]
 def run(args):
  child=subprocess.run(list(map(str,args)),capture_output=True,text=True,timeout=120);commands.append(dict(argv=list(map(str,args)),returncode=child.returncode,stderr=child.stderr));child.check_returncode()
 try:
  run([core.C.TOOL,'-o','ro',image,work]);mounted=True;run(['mountpoint','-q',work]);root=work/'root' if (work/'root').is_dir() else work
  ns=Namespace([dict(prefix='/',component='OS',root=root)])
  launch=Path(ns.resolve('/System/Library/xpc/launchd.plist')['physical']).read_bytes()
  contract=json.loads((R/audit['launch_contract']['path']).read_bytes());assert sha(launch)==contract['main_launch_config']['sha256']
  decoded=plistlib.loads(launch);services=D.contract(decoded);providers=services['providers']
  for entry in audit['namespace']['selected_paths']:
   if entry['component']!='OS':continue
   raw=Path(ns.resolve(entry['path'])['physical']).read_bytes();assert sha(raw)==entry['sha256']
   dest=out/entry['path'].lstrip('/');dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
   info=inspect(raw)
   for call in info['constant_calls']:
    if call['api'].startswith(('_xpc_connection','_bootstrap_')):call['declared_providers']=providers.get(call['literal'],[])
   record=dict(path=entry['path'],sha256=sha(raw),extracted=str(dest.relative_to(R)),**info);records.append(record)
   print('inspected',entry['path'],len(info['constant_calls']),'constant calls',flush=True)
  selected={j['label'] for j in audit['launch_contract']['jobs']}
  jobs=[dict(job=j,actual_plist=D.plist_value(raw)) for trail,raw in D.jobs(decoded) for j in services['jobs'] if j['id']=='/'.join(trail) and j['label'] in selected]
  for entry in source['data_source']['entries']:
   if entry['type']!='file':continue
   raw=Path(ns.resolve('/'+entry['path'])['physical']).read_bytes();assert sha(raw)==entry['sha256']
   info=dict(entry)
   if entry['path'].endswith('.plist'):
    try:obj=plistlib.loads(raw);info['plist_top_keys']=list(obj) if isinstance(obj,dict) else None
    except plistlib.InvalidFileException:info['plist_parse']='not plist'
   datafiles.append(info)
  result=dict(jobs=jobs,providers=providers,path_references=[x for x in services['path_references'] if x['label'] in selected],
   explicit_conditions=[x for x in services['explicit_job_conditions'] if any(x['job']==j['job']['id'] for j in jobs)],data_files=datafiles)
 except BaseException as exc:error=dict(type=type(exc).__name__,message=str(exc))
 finally:
  if mounted:run(['fusermount','-u',work])
  cleaned=subprocess.run(['mountpoint','-q',str(work)],capture_output=True).returncode!=0
  result.update(passed=error is None and cleaned,error=error,mount_cleanup_complete=cleaned,binaries=records,commands=commands,
   parent_bindings={str(x.relative_to(R)):sha(x.read_bytes()) for x in (auditpath,sourcepath)},image_digest_reused=item['before'],
   input_binding='Existing component digest reused; every selected executable, launch plist and Data file compared to fixed prior SHA256. Whole image not rehashed.',
   script_sha256=sha(Path(__file__).read_bytes()),device_accessed=False,jobs_enabled=False,root_changed=False)
  a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n')
 assert result['passed'],error
 print('PASS',len(records),'fixed binaries,',len(jobs),'jobs,',len(datafiles),'Data files')
if __name__=='__main__':main()
