"""Native bootobjectspath and dyld Preboot error boundaries, without device access.
IORegistry/sysctl sinks and OS services are fixtures; not a complete ignition boot.
"""
import argparse,hashlib,json,struct,sys
from pathlib import Path
import flush_trace_inputs as trace
import nuwa_launch_context as context
sys.path.insert(0,str(trace.R/'out/python-tools'))
import unicorn as U
from unicorn.arm64_const import *
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.output.exists()
R=trace.R;sha=lambda x:hashlib.sha256(x).hexdigest()
def load(p):return json.loads((R/p).read_bytes())
q=load('reports/payload-s1-r1/offline-package-r2.json');raw=(R/'out/payload-s1-r1/kernel.macho').read_bytes();assert sha(raw)==q['kernel_sha256']
adt=(R/'out/payload-s1-r1/launch/kernel.macho.adt').read_bytes();assert sha(adt)==q['files']['kernel.macho.adt']
chosen=context.properties(context.find(context.parse(adt),'/chosen'));digest=chosen['boot-manifest-hash']
assert digest==hashlib.sha384(chosen['nuwa-launch-manifest']).digest() and len(digest)==48
B=trace.builder();m=B.macho(raw);sym=m['symbols'];kernel_cases=[]
for case in ('shipped-diagnostic-hash','properties-absent','objects-path-precedence'):
 u=U.Uc(U.UC_ARCH_ARM64,U.UC_MODE_ARM);pages=set();arena=0x20000000;stop=arena+0x1000;stack=arena+0x1f000
 u.mem_map(arena,0x20000)
 def mapping(addr,n):
  for page in range(addr&~4095,(addr+n+4095)&~4095,4096):
   if page in pages:continue
   s=next((s for s in m['segments'] if s['va']<=page<s['va']+s['size']),None);assert s,hex(page)
   u.mem_map(page,4096);pages.add(page)
   if page-s['va']<s['filesize']:
    count=min(4096,s['filesize']-(page-s['va']));off=s['fileoff']+page-s['va'];u.mem_write(page,raw[off:off+count])
 def fault(uc,access,addr,n,value,data):mapping(addr,n);return True
 u.hook_add(U.UC_HOOK_MEM_UNMAPPED,fault);strings=[];calls=[]
 targets={sym[n]:n for n in ('_bzero','_IOGetBootObjectsPath','_IOGetBootManifestHash','_sysctl_io_string')}
 def hook(uc,pc,size,data):
  name=targets.get(pc)
  if not name:return
  calls.append(name);x0=uc.reg_read(UC_ARM64_REG_X0);x1=uc.reg_read(UC_ARM64_REG_X1);ret=0
  if name=='_bzero':uc.mem_write(x0,bytes(x1))
  elif name=='_IOGetBootObjectsPath':
   if case=='objects-path-precedence':uc.mem_write(x0,b'fixture-existing-path\0');ret=1
  elif name=='_IOGetBootManifestHash':
   if case!='properties-absent':uc.mem_write(x0,digest);uc.mem_write(x1,struct.pack('<Q',len(digest)));ret=1
  elif name=='_sysctl_io_string':strings.append(bytes(uc.mem_read(x1,128)).split(b'\0')[0].decode())
  uc.reg_write(UC_ARM64_REG_X0,ret);uc.reg_write(UC_ARM64_REG_PC,uc.reg_read(UC_ARM64_REG_LR))
 u.hook_add(U.UC_HOOK_CODE,hook);u.reg_write(UC_ARM64_REG_X3,arena+0x2000);u.reg_write(UC_ARM64_REG_SP,stack);u.reg_write(UC_ARM64_REG_LR,stop)
 u.emu_start(sym['_sysctl_bootobjectspath'],stop,count=10000)
 assert u.reg_read(UC_ARM64_REG_PC)==stop and u.reg_read(UC_ARM64_REG_SP)==stack
 expected=[] if case=='properties-absent' else [digest.hex().upper() if case=='shipped-diagnostic-hash' else 'fixture-existing-path']
 assert strings==expected and u.reg_read(UC_ARM64_REG_W0)==(2 if case=='properties-absent' else 0)
 if case=='objects-path-precedence':assert '_IOGetBootManifestHash' not in calls
 kernel_cases.append(dict(case=case,output=strings,errno=u.reg_read(UC_ARM64_REG_W0),calls=calls))

da=load('reports/desktop-readiness/2026-11-02-payload-dyld-startup-r2/audit.json');assert da['passed']
d=(R/'out/payload-dyld-startup-r2/dyld').read_bytes();assert sha(d)==da['records'][0]['sha256']
symbols=load('out/payload-dyld-startup-r2/dyld.symbols.json');ds={k:int(v['address'],16) for k,v in symbols.items()}
assert ds['__stage_preboot']==0x80a18 and ds['__preboot_fire']==0x5ec78 and ds['_stage_fire']==0x5d540
stage=bytearray(d[0x80a18:0x80a58]);stage_pointers=[]
# Zero-slide fixture for these five encoded descriptor pointers only. Not a dyld self-rebase test.
for off,target in ((0,0x7ad43),(8,0x7a588),(16,0x7a599),(48,ds['__preboot_fire']),(56,ds['__preboot_payload_check'])):
 encoded=struct.unpack_from('<Q',stage,off)[0];assert encoded&((1<<36)-1)==target and not (encoded>>63)
 struct.pack_into('<Q',stage,off,target);stage_pointers.append(dict(offset=off,encoded=hex(encoded),zero_slide_target=hex(target)))
dyld_cases=[]
for error in (2,6):
 u=U.Uc(U.UC_ARCH_ARM64,U.UC_MODE_ARM);u.mem_map(0,0x100000);u.mem_write(0,d);u.mem_write(ds['__stage_preboot'],bytes(stage));u.mem_map(0x20000000,0x20000)
 base=0x20000000;stop=base+0x1000;stack=base+0x1f000;args=base+0x2000;cfg=base+0x3000;boot=base+0x6000;errptr=base+0x7000
 u.mem_write(args,struct.pack('<Q',2));events=[];phase='stage';stage_error=None
 names=['_arguments','_configuration','___bzero','___getpid','_dlog','_fsctl','___error','_dyld_halt','_ignition_halt','__simple_getenv','_ignite','__ZN5dyld47consoleEPKcz','__ZNK5dyld415SyscallDelegate4openEPKcii']
 targets={ds[n]:n for n in names}
 def string(ptr):return bytes(u.mem_read(ptr,256)).split(b'\0')[0].decode()
 def hook(uc,pc,size,data):
  name=targets.get(pc)
  if not name:return
  x0=uc.reg_read(UC_ARM64_REG_X0);x1=uc.reg_read(UC_ARM64_REG_X1);x2=uc.reg_read(UC_ARM64_REG_X2);ret=0
  if name=='_arguments':ret=args
  elif name=='_configuration':ret=cfg
  elif name=='___bzero':uc.mem_write(x0,bytes(x1))
  elif name=='___getpid':ret=1
  elif name=='_fsctl':
   role=struct.unpack('<H',uc.mem_read(x2+2,2))[0]
   assert phase=='stage' and x1==0xc1044a50 and role==0x10 and string(x0)=='/'
   events.append(dict(call='actual-role-query',command=hex(x1),role=role,path='/',fixture_errno=error))
   uc.mem_write(errptr,struct.pack('<I',error));ret=0xffffffff
  elif name=='___error':ret=errptr
  elif name in ('_dyld_halt','_ignition_halt'):raise AssertionError('Unexpected halt at '+hex(pc))
  elif name=='_ignite':assert phase=='finder';ret=stage_error;events.append(dict(call='ignite-boundary-fixture',errno=ret))
  elif name.endswith('SyscallDelegate4openEPKcii'):
   assert phase=='finder' and string(x1).rstrip('/')=='/System/Library/Caches/com.apple.dyld'
   events.append(dict(call='default-cache-open',path=string(x1),filesystem_fixture=True));ret=88
  uc.reg_write(UC_ARM64_REG_X0,ret);uc.reg_write(UC_ARM64_REG_PC,uc.reg_read(UC_ARM64_REG_LR))
 u.hook_add(U.UC_HOOK_CODE,hook)
 for reg,value in ((UC_ARM64_REG_X0,ds['__stage_preboot']),(UC_ARM64_REG_X1,boot),(UC_ARM64_REG_SP,stack),(UC_ARM64_REG_LR,stop)):u.reg_write(reg,value)
 u.emu_start(ds['_stage_fire'],stop,count=100000);assert u.reg_read(UC_ARM64_REG_PC)==stop and u.reg_read(UC_ARM64_REG_SP)==stack
 stage_error=u.reg_read(UC_ARM64_REG_W0);assert stage_error==error
 phase='finder';obj=base+0x8000;proc=base+0x9000
 u.mem_write(proc+0x3c,struct.pack('<I',2));u.mem_write(proc+0x90,struct.pack('<I',1))
 entry=next(v for k,v in ds.items() if 'CacheFinderC2' in k)
 for reg,value in ((UC_ARM64_REG_X0,obj),(UC_ARM64_REG_X1,proc),(UC_ARM64_REG_X2,base+0xa000),(UC_ARM64_REG_X3,base+0xb000),(UC_ARM64_REG_SP,stack),(UC_ARM64_REG_LR,stop)):u.reg_write(reg,value)
 u.emu_start(entry,stop,count=10000);assert u.reg_read(UC_ARM64_REG_PC)==stop and u.reg_read(UC_ARM64_REG_SP)==stack
 assert struct.unpack('<i',u.mem_read(obj,4))[0]==88 and events[-1]['call']=='default-cache-open'
 dyld_cases.append(dict(fsctl_fixture_errno=error,actual_preboot_stage_errno=stage_error,events=events,commpage_flags=0,pid=1))
report=dict(passed=True,kernel_sha256=sha(raw),adt_sha256=sha(adt),dyld_sha256=sha(d),script_sha256=sha(Path(__file__).read_bytes()),kernel_cases=kernel_cases,dyld_cases=dyld_cases,stage_pointer_fixtures=stage_pointers,
 direct_dyld_string_presence={s:s.encode() in d for s in ('kern.bootobjectspath','kern.apfsprebootuuid','boot-manifest-hash')},
 device_accessed=False,full_ignition_executed=False,actual_apfs_role_query_executed=False,authentication_verified=False,
 scope='Actual kernel path conversion and dyld stage_fire/preboot_fire/role-helper instructions. IO getters, sysctl sink and OS calls are fixtures. CacheFinder composes the resulting errno through an explicit ignite fixture; no boot-spec selection, full ignition, APFS ioctl implementation or real open.')
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n');print('PASS',len(kernel_cases),'kernel path cases;',len(dyld_cases),'Preboot error boundaries')
