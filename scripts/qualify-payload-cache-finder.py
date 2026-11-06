"""Exercise original iOS16 dyld CacheFinder instructions with explicit OS/ignite fixtures."""
import argparse,hashlib,json,struct,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'out/python-tools'))
import unicorn as U
from unicorn.arm64_const import *
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,required=True);p.add_argument('--audit',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
sha=lambda x:hashlib.sha256(x).hexdigest()
assert not a.output.exists();audit=json.loads(a.audit.read_bytes());assert audit['passed'] and audit['mount_cleanup_complete']
record=next(v for v in audit['records'] if v['path']=='/usr/lib/dyld');raw=(a.input/'dyld').read_bytes();assert sha(raw)==record['sha256']
sy=json.loads((a.input/'dyld.symbols.json').read_bytes())
def address(part):
 hits=[int(v['address'],16) for k,v in sy.items() if part in k];assert len(hits)==1,(part,hits);return hits[0]
entry=address('CacheFinderC2');assert entry==0x17ad4
assert raw[0x17b60:0x17b64]==bytes.fromhex('280a1837') # tbnz w8,#3: actual skipIgnition bit
targets={address(k):v for k,v in [('__simple_getenv','env'),('SyscallDelegate4open','open'),('SyscallDelegate5close','close'),('_ignite','ignite'),('dyld47console','log'),('dyld44halt','halt')]}
checks=[]
def run(name,flags,error,fd=-1,pid=1,halt=None,expected_open=True,expected_ignite=True):
 u=U.Uc(U.UC_ARCH_ARM64,U.UC_MODE_ARM);u.mem_map(0,0x100000);u.mem_write(0,raw);u.mem_map(0x1000000,0x20000)
 obj=0x1001000;process=0x1002000;logging=0x1003000;delegate=0x1004000;sp=0x101f000;stop=0x101e000
 def put(address,value,fmt='<Q'):u.mem_write(address,struct.pack(fmt,value))
 put(process+0x3c,2,'<I');put(process+0x58,1,'<I');put(process+0x80,flags);put(process+0x90,pid,'<I')
 events=[]
 def string(ptr):return bytes(u.mem_read(ptr,160)).split(b'\0',1)[0].decode()
 def hook(uc,pc,size,data):
  if pc not in targets:return
  op=targets[pc];event=dict(operation=op)
  if op in ('log','halt'):event['message']=string(uc.reg_read(UC_ARM64_REG_X0))
  if op=='halt':events.append(event);uc.emu_stop();return
  result=0
  if op=='open':
   event['path']=string(uc.reg_read(UC_ARM64_REG_X1));event['flags']=uc.reg_read(UC_ARM64_REG_X2);result=88
  elif op=='close':event['fd']=uc.reg_read(UC_ARM64_REG_X1)
  elif op=='ignite':
   args=uc.reg_read(UC_ARM64_REG_X0);assert struct.unpack('<I',uc.mem_read(args,4))[0]==1
   event['fixture_errno']=error;result=error;put(uc.reg_read(UC_ARM64_REG_X1)+8,fd,'<i')
  events.append(event);uc.reg_write(UC_ARM64_REG_X0,result);uc.reg_write(UC_ARM64_REG_PC,uc.reg_read(UC_ARM64_REG_LR))
 u.hook_add(U.UC_HOOK_CODE,hook)
 for reg,value in ((UC_ARM64_REG_X0,obj),(UC_ARM64_REG_X1,process),(UC_ARM64_REG_X2,logging),(UC_ARM64_REG_X3,delegate),(UC_ARM64_REG_SP,sp),(UC_ARM64_REG_LR,stop)):u.reg_write(reg,value)
 u.emu_start(entry,stop,count=10000)
 opened=[e for e in events if e['operation']=='open'];ignited=any(e['operation']=='ignite' for e in events);halts=[e['message'] for e in events if e['operation']=='halt']
 assert ignited==expected_ignite and bool(opened)==expected_open and halts==([] if halt is None else [halt]),(name,events)
 if halt is None:
  assert u.reg_read(UC_ARM64_REG_PC)==stop and u.reg_read(UC_ARM64_REG_SP)==sp
  assert struct.unpack('<i',u.mem_read(obj,4))[0]==(88 if expected_open else fd)
 for event in opened:assert event['path'].rstrip('/')=='/System/Library/Caches/com.apple.dyld' and event['flags']==0
 checks.append(dict(name=name,commpage_flags=flags,pid=pid,events=events,returned=halt is None))
run('disabled-falls-back',0,8)
run('no-device-falls-back',0,19)
run('partial-disabled-falls-back',0,89)
run('removed-is-fatal-for-pid1',0,90,halt='ignition failed',expected_open=False)
run('bad-exec-is-fatal-for-pid1',0,85,halt='no shared cache in cryptex',expected_open=False)
run('successful-ignition-fd',0,0,37,expected_open=False)
run('successful-without-cache-fd',0,0)
run('skip-bit-bypasses-ignite',8,90,expected_ignite=False)
run('prefer-system-is-not-skip',16,90,halt='ignition failed',expected_open=False)
run('prefer-system-closes-ignition-fd',16,0,37)
run('non-pid1-removed-falls-back',0,90,pid=2)
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(dict(passed=True,dyld_sha256=sha(raw),audit_sha256=sha(a.audit.read_bytes()),symbols_sha256=sha((a.input/'dyld.symbols.json').read_bytes()),script_sha256=sha(Path(__file__).read_bytes()),unicorn_version=U.__version__,cases=checks,device_accessed=False,actual_ignite_executed=False,actual_open_executed=False,scope='Actual CacheFinder instructions; env/open/close/ignite/log/halt are explicit fixtures. Flags are model inputs, not kernel changes or runtime evidence.'),indent=2)+'\n')
print('PASS',len(checks),'original dyld CacheFinder cases')
