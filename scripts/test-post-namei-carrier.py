"""Execute native namei-success to header-read branches; explicit kernel helper boundaries."""
import argparse,hashlib,json,sys,struct
from pathlib import Path
import flush_trace_inputs as t
sys.path.insert(0,str(t.R/'out/python-tools'))
import unicorn as U
from unicorn.arm64_const import *
p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);a=p.parse_args();raw=(a.work/'kernel.macho').read_bytes();proof=json.loads((a.work/'kernel-proof.json').read_bytes());b=t.builder();m=b.macho(raw);base=0xfffffff000000000;results=[]
helpers={0x76a8698:'proc_lock',0x76b16b0:'proc_transstart',0x76a86c8:'proc_unlock',0x746a6d8:'context_proc',0x746ae68:'vnode_isreg',0x746ac54:'vnode_mount',0x7469a6c:'mount_noexec',0x7915718:'mac_exec',0x744cafc:'authorize',0x79dde70:'copy_attributes',0x746aacc:'context_cred',0x7466988:'header_read',0x76b1808:'proc_transend'}
helpers[proof['targets']['phase_getattr_before_resume']-base]='getattr'
cases=[('normal',None,0,6),('proc_wait','proc_transstart',None,None),('getattr_wait','getattr',None,1),('getattr_error','getattr',5,2),('mac_error','mac_exec',13,3),('authorize_error','authorize',13,4),('read_wait','header_read',None,5),('read_error','header_read',5,6)]
for name,changed,error,last in cases:
 u=U.Uc(U.UC_ARCH_ARM64,U.UC_MODE_ARM);u.mem_map(0x20000000,0x10000);draws=[];calls=[];stops=[];recent=[]
 def fault(uc,access,addr,size,value,data):
  page=addr&~4095;s=next(s for s in m['segments'] if s['va']<=page<s['va']+s['size']);n=max(0,min(4096,s['filesize']-page+s['va']));o=s['fileoff']+page-s['va'];uc.mem_map(page,4096);uc.mem_write(page,raw[o:o+n]+bytes(4096-n));return True
 u.hook_add(U.UC_HOOK_MEM_UNMAPPED,fault)
 def put(addr,value,n=8):u.mem_write(addr,value.to_bytes(n,'little'))
 img=0x20003000;proc=0x20004000;ndp=0x20005000;attr=0x20006000;vnode=0x20009000;mount=0x2000c000
 put(img+0x28,attr);put(img+0x30,0x2000b000);put(img+0x40,0x2000a000);put(img+0x2a8,proc);put(ndp+0x28,vnode);put(vnode+0xd8,mount);put(0x20007000,12,4)
 state=proof['targets']['coarse_state'];fault(u,0,state,0,0,None);put(state+104,0x20001000);u.reg_write(UC_ARM64_REG_TPIDR_EL1,0x20001000)
 for r,v in [(UC_ARM64_REG_X0,0),(UC_ARM64_REG_X19,img),(UC_ARM64_REG_X20,proc),(UC_ARM64_REG_X21,ndp),(UC_ARM64_REG_X26,0x20007000),(UC_ARM64_REG_SP,0x20008000)]:u.reg_write(r,v)
 u.reg_write(UC_ARM64_REG_CPACR_EL1,3<<20)
 def hook(uc,pc,size,data):
  recent.append(hex(pc));recent[:]=recent[-30:]
  if pc==proof['symbols']['draw']:
   draws.append((uc.reg_read(UC_ARM64_REG_X0),uc.reg_read(UC_ARM64_REG_X1)));uc.reg_write(UC_ARM64_REG_PC,uc.reg_read(UC_ARM64_REG_LR))
  elif pc-base in helpers:
   helper=helpers[pc-base];calls.append(helper)
   if helper==changed and error is None:stops.append('nonreturn boundary');uc.emu_stop();return
   value=error if helper==changed else {'context_proc':proc,'vnode_isreg':1,'vnode_mount':mount,'context_cred':0x2000d000}.get(helper,0)
   if helper=='getattr' and not value:put(attr+0x30,4096);put(attr+0x4c,0x49,2)
   if helper=='header_read' and not value:put(0x2000801c,0,4)
   uc.reg_write(UC_ARM64_REG_X0,value);uc.reg_write(UC_ARM64_REG_PC,uc.reg_read(UC_ARM64_REG_LR))
  elif pc in (base+0x769bfd4,base+0x769c164):stops.append('header read success' if pc==base+0x769bfd4 else 'native error cleanup');uc.emu_stop()
 u.hook_add(U.UC_HOOK_CODE,hook)
 try:u.emu_start(base+0x769bdd8,0,count=30000)
 except Exception:print(name,recent,calls,draws);raise
 assert stops==[('header read success' if name=='normal' else 'nonreturn boundary' if error is None else 'native error cleanup')],(name,stops,recent)
 phases=[v for r,v in draws if r==18];assert phases==([0xa0000000+i for i in range(1,last+1)] if last else []),(name,draws)
 assert [v for r,v in draws if r==17]==([error] if error else [])
 assert [v for r,v in draws if r==20]==([0xe0000000+last] if error else [])
 if error:assert u.reg_read(UC_ARM64_REG_X22)==error
 results.append(dict(name=name,draws=draws,helpers=calls,stop=stops[0]))
(a.work/'post-namei-model.json').write_text(json.dumps(dict(passed=True,kernel_sha256=hashlib.sha256(raw).hexdigest(),tests=results,scope='Actual native post-namei instructions and current hooks through permissions/header read. Kernel helpers, vnode attributes and draw are explicit fixtures. Nonreturn cases stop at the selected helper boundary; no hardware lock/UFS conclusion.'),indent=2)+'\n');print('PASS',len(results),'native post-namei paths')
