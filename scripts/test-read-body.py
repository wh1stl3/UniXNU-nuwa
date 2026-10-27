"""Native instruction/observer equivalence at every scoped read-body site."""
import argparse,importlib.util,json,struct,sys
from pathlib import Path
import read_body_sites as P
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('body_model',ROOT/'scripts/test-read-dispatch-observer.py')
T=importlib.util.module_from_spec(spec);sys.modules[spec.name]=T;spec.loader.exec_module(T)
U=T.U;B=T.B

def execute(raw,m,b,site,mode,candidate):
 u=T.machine(raw,m,b'',0,[],False)
 for i in range(31):u.reg_write(getattr(T,f'UC_ARM64_REG_X{i}'),T.STACK+0x4000+i*0x10)
 sy={k:int(v,16) for k,v in b['probe']['symbols'].items()}
 outer=site in (P.ENTRY+4,0xfffffff0051a5978)
 caller=T.STACK+0xd000;fp=caller if outer else T.STACK+0xc000
 u.reg_write(T.UC_ARM64_REG_X29,fp);u.reg_write(T.UC_ARM64_REG_LR,P.PREVIOUS.DISPATCH+4)
 u.reg_write(T.UC_ARM64_REG_X8,T.STOP)
 u.reg_write(T.UC_ARM64_REG_SP,T.STACK+0xb000)
 u.mem_write(fp,struct.pack('<QQ',caller,P.PREVIOUS.DISPATCH+4))
 state=sy['probe_read_state'];pair=(1<<len(P.CALL_OFFSETS))-1
 u.mem_write(state,struct.pack('<14Q',0 if mode=='inactive' else 1,0x1111,T.STACK+0x4000,0,0,caller,0,P.ENTRY,0,0,0,0,0,8))
 if mode=='foreign-thread':u.reg_write(T.UC_ARM64_REG_TPIDR_EL1,0x2222)
 if mode=='foreign-frame':u.mem_write(state+40,struct.pack('<Q',caller+16))
 if mode=='wrong-lr':
  if outer:u.reg_write(T.UC_ARM64_REG_LR,T.STOP)
  else:u.mem_write(fp+8,struct.pack('<Q',T.STOP))
 if mode=='unpaired':pair=0
 u.mem_write(sy['probe_read_body_state'],struct.pack('<Q',pair))
 u.mem_write(sy['probe_scratch'],struct.pack('<QQ',0 if mode=='no-video' else T.FB,T.ROW))
 writes=[]
 def write(u,a,p,n,v,d):
  if T.FB<=p<T.FB+0x1200000:
   y,off=divmod(p-T.FB,T.ROW)
   rects=[(256,840,480,20),(256,868,480,20)]+[(832+((q['id']-276)%10)*48,808+((q['id']-276)//10)*24,32,16) for q in P.points()]
   assert any(ry<=y<ry+rh and rx*4<=off and off+n<=(rx+rw)*4 for rx,ry,rw,rh in rects),(hex(p),n)
  else:writes.append((p,n))
 u.hook_add(U.UC_HOOK_MEM_WRITE,write)
 if candidate:
  expected=execute(raw,m,b,site,mode,False)
  u.hook_add(U.UC_HOOK_CODE,lambda u,a,n,d:u.emu_stop() if a==expected['snapshot']['pc'] else None)
  u.emu_start(site,0,count=2000000)
 else:
  original=B.INPUT.read_bytes();om=B.macho(original);at=B.backed(om,site)
  u.mem_write(site,original[at:at+4]);u.emu_start(site,0,count=1)
 snapshot=dict(registers=[u.reg_read(getattr(T,f'UC_ARM64_REG_X{i}')) for i in range(31)],simd=[u.reg_read(getattr(T,f'UC_ARM64_REG_Q{i}')) for i in range(32)],sp=u.reg_read(T.UC_ARM64_REG_SP),pc=u.reg_read(T.UC_ARM64_REG_PC),nzcv=u.reg_read(T.UC_ARM64_REG_NZCV))
 if not candidate:return dict(snapshot=snapshot,writes=[(p,n,bytes(u.mem_read(p,n)).hex()) for p,n in writes])
 assert snapshot==expected['snapshot'],(hex(site),mode,'native state differs')
 for p,n,value in expected['writes']:assert bytes(u.mem_read(p,n)).hex()==value
 scoped=mode not in ('inactive','foreign-thread','foreign-frame','wrong-lr','no-video')
 for q in (p for p in P.points() if p['site']==site):
  x=832+((q['id']-276)%10)*48;y=808+((q['id']-276)//10)*24
  value=struct.unpack('<I',u.mem_read(T.FB+y*T.ROW+x*4,4))[0]
  lit=scoped and not (mode=='unpaired' and q['phase']=='continuation')
  assert value==((0xff40c0ff if q['phase']=='call' else 0xff40ff80) if lit else 0),(hex(site),mode,q,value)
 return dict(site=hex(site),mode=mode,passed=True)

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():raise ValueError('Fresh report required')
 b=json.loads(a.build.read_text());raw=(ROOT/b['candidate']['path']).read_bytes();assert B.sha(raw)==b['candidate']['sha256'] and b['probe_revision'] in (38,39,40,41,42,43,44,45,46,47,48,49)
 m=B.macho(raw);checks=[]
 for site in sorted({p['site'] for p in P.points()}):
  for mode in ('normal','foreign-thread','foreign-frame','unpaired','no-video'):
   checks.append(execute(raw,m,b,site,mode,True))
  if len(checks)%50==0:print(json.dumps(dict(progress=len(checks))),flush=True)
 for site in (P.ENTRY+4,P.ENTRY+0x30,0xfffffff0051a5978):
  for mode in ('inactive','wrong-lr'):checks.append(execute(raw,m,b,site,mode,True))
 report=dict(candidate_sha256=B.sha(raw),source_sha256=B.sha((ROOT/'scripts/read_body_sites.py').read_bytes()),checks=checks,points=P.points(),native_instructions_executed=True,complete_filesystem_body_executed=False,device_accessed=False)
 a.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(dict(checks=len(checks),passed=True)))
if __name__=='__main__':main()
