"""Compile and execute an in-memory-only dispatch/entry observer prototype.

No kernel file, boot package, hardware command, native policy or APFS body is
replaced on disk. Real VNOP_READ and callback first instruction execute; APIs
and callback remainder are explicit models, not filesystem qualification.
"""
import argparse,hashlib,json,re,struct,subprocess,sys
from pathlib import Path
import read_dispatch_audit as A
R=A.ROOT;B=A.B;sys.path.insert(0,str(R/'out/python-tools'))
import unicorn as U
from unicorn.arm64_const import *
STACK=0xf00000;FB=0xb8000000;ROW=5760;SP=STACK+0xe000;STOP=STACK+0xf800
FONT=[0xf999f,0x26227,0xf1f8f,0xf1f1f,0x99f11,0xf8f1f,0xf8f9f,0xf1244,0xf9f9f,0xf9f1f,0xf9f99,0xe9e9e,0xf888f,0xe999e,0xf8f8f,0xf8f88]
def compile_probe(work,constants,va):
 work.mkdir(parents=True,exist_ok=False);template=(R/'package/entry-probe/entry-probe.S').read_text(encoding='utf-8-sig');macros=[]
 for name in ('PROBE_SAVE','PROBE_RESTORE','HEX_DIGITS','HEX_RENDER','HEXROW_VAL','LOADABS'):
  match=re.search(r'^\.macro '+name+r'(?:\s[^\n]*)?\n.*?^\.endm',template,re.M|re.S);assert match,name;macros.append(match[0].replace('adr x15, probe_scratch','LOADABS x15, probe_scratch'))
 source='\n'.join('.equ '+k+', '+hex(v) for k,v in constants.items() if k not in ('native_vn_rdwr','read_apfs_resume'))+'\n'+'\n'.join(macros)+'\n'+(R/'patches/xnu-8796-candidates/read-dispatch-observer.S').read_text(encoding='utf-8-sig');(work/'observer.S').write_text(source,encoding='utf-8',newline='\n');commands=[]
 for argv in (['clang','--target=aarch64-none-elf','-c',B.linux(work/'observer.S'),'-o',B.linux(work/'observer.o')],['ld.lld','-Ttext='+hex(va),'--entry=read_dispatch_target',*[f'--defsym={k}={v:#x}' for k,v in constants.items() if k in ('native_vn_rdwr','read_apfs_resume')],B.linux(work/'observer.o'),'-o',B.linux(work/'observer.elf')],['llvm-objcopy','-O','binary','--only-section=.text',B.linux(work/'observer.elf'),B.linux(work/'observer.bin')]):
  cmd=['wsl','-d','Ubuntu-22.04','--',*argv];p=subprocess.run(cmd,capture_output=True,text=True);commands.append(dict(argv=cmd,exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr));(work/'commands.json').write_text(json.dumps(commands,indent=2)+'\n',encoding='utf-8',newline='\n');p.check_returncode()
 nm=subprocess.check_output(['wsl','-d','Ubuntu-22.04','--','llvm-nm','--defined-only',B.linux(work/'observer.elf')],text=True);sy={name:int(v,16) for v,kind,name in re.findall(r'^([0-9a-f]+)\s+(\S)\s+(\S+)$',nm,re.M)}
 return (work/'observer.bin').read_bytes(),sy,commands

def field(u,tag):
 y=224+(tag-0xa022)*28;pixels=[]
 for n in range(20):
  bits=0
  for row in range(5):
   for col in range(4):
    pixel=struct.unpack('<I',u.mem_read(FB+(y+row*4)*ROW+(256+n*24+col*4)*4,4))[0];assert pixel in (0,0xffffffff);bits=(bits<<1)|bool(pixel)
  pixels.append(bits)
 if not any(pixels):return None
 digits=[FONT.index(x) for x in pixels];identifier=int(''.join(f'{x:x}' for x in digits[:4]),16);assert identifier==tag,(identifier,tag)
 return int(''.join(f'{x:x}' for x in digits[4:]),16)

def machine(raw,m,proto,va,patches,candidate):
 base=min(s['va'] for s in m['segments'] if s['size']);end=max(s['va']+s['size'] for s in m['segments']);u=U.Uc(U.UC_ARCH_ARM64,U.UC_MODE_ARM);u.mem_map(base,B.align(end-base));u.mem_map(STACK,0x10000);u.mem_map(FB,0x1200000)
 if proto:u.mem_map(va,B.align(len(proto)));u.mem_write(va,proto)
 for s in m['segments']:
  if s['filesize']:u.mem_write(s['va'],raw[s['fileoff']:s['fileoff']+s['filesize']])
 if candidate:
  for pc,target in patches:u.mem_write(pc,B.branch(pc,target))
 for i in range(31):u.reg_write(getattr(sys.modules[__name__],f'UC_ARM64_REG_X{i}'),0x101000+i*0x100)
 for i in range(32):u.reg_write(getattr(sys.modules[__name__],f'UC_ARM64_REG_Q{i}'),0x12345678123456781234567800000000+i)
 u.reg_write(UC_ARM64_REG_SP,SP);u.reg_write(UC_ARM64_REG_X29,STACK+0xf000);u.reg_write(UC_ARM64_REG_LR,STOP);u.reg_write(UC_ARM64_REG_TPIDR_EL1,0x1111);u.reg_write(UC_ARM64_REG_CPACR_EL1,3<<20)
 return u

def execute(raw,m,b,proto,va,patches,case,candidate,extra_rectangles=()):
 u=machine(raw,m,proto,va,patches,candidate);sy=m['symbols'];ps={k:int(v,16) for k,v in b['probe']['symbols'].items()};state=ps['probe_read_state'];vp=STACK+0x4000;ops=STACK+0x5000;uio=STACK+0x3000;ctx=STACK+0x2000
 u.mem_write(ps['probe_scratch'],struct.pack('<QQ',0 if case.get('no_video') else FB,ROW));u.mem_write(state,struct.pack('<14Q',1,0x1111,vp,0,0,SP-16,0,0,0,0,0,0,0,0))
 if case.get('foreign_frame'):u.mem_write(state+40,struct.pack('<Q',SP-32))
 if case.get('foreign_thread'):u.reg_write(UC_ARM64_REG_TPIDR_EL1,0x2222)
 index=case.get('index',17);target=case.get('target',A.ENTRY);u.mem_write(sy['_vnop_read_desc'],struct.pack('<i',index));u.mem_write(vp+0xd0,struct.pack('<Q',ops));u.mem_write(ops+index*8,struct.pack('<Q',target))
 u.reg_write(UC_ARM64_REG_X0,vp);u.reg_write(UC_ARM64_REG_X1,uio);u.reg_write(UC_ARM64_REG_X2,8);u.reg_write(UC_ARM64_REG_X3,0 if case.get('null_context') else ctx)
 visited=[];writes=set();bad=[];renderer=[];api=[];body_seen=False
 def watch(u,pc,size,data):
  nonlocal body_seen
  if pc==STOP:u.emu_stop();return
  if pc in (A.DISPATCH,A.DISPATCH+4,A.ENTRY,A.ENTRY+4):visited.append(hex(pc))
  if pc==sy['_uio_resid']:
   api.append('uio_resid');u.reg_write(UC_ARM64_REG_X0,4096 if len(api)==1 else 0);u.reg_write(UC_ARM64_REG_PC,u.reg_read(UC_ARM64_REG_LR));return
  if pc==(A.ENTRY+4 if target==A.ENTRY else target):
   body_seen=True
   if case.get('pending'):u.emu_stop();return
   if target==A.ENTRY:u.reg_write(UC_ARM64_REG_SP,u.reg_read(UC_ARM64_REG_SP)+256)
   u.reg_write(UC_ARM64_REG_X0,case.get('errno',0));u.reg_write(UC_ARM64_REG_PC,u.reg_read(UC_ARM64_REG_LR))
 def write(u,a,p,n,v,data):
  pc=u.reg_read(UC_ARM64_REG_PC)
  if FB<=p<FB+0x1200000:
   y,offset=divmod(p-FB,ROW);x=offset//4
   rectangles=((256,784,480,20),(256,812,480,20))+tuple(extra_rectangles)
   assert n>0 and any(rx*4<=offset and offset+n<=(rx+rw)*4 and ry<=y<ry+rh for rx,ry,rw,rh in rectangles),(x,y,n)
   renderer.append((x,y,n))
  elif va<=pc<va+len(proto):
   assert STACK<=p and p+n<=STACK+0x10000,hex(p)
  elif not ps['probe_entry']<=pc<max(s['va']+s['size'] for s in m['segments']):writes.add((p,n))
 u.hook_add(U.UC_HOOK_CODE,watch);u.hook_add(U.UC_HOOK_MEM_WRITE,write);u.hook_add(U.UC_HOOK_MEM_INVALID,lambda u,a,p,n,v,d:bad.append(dict(access=a,address=hex(p),pc=hex(u.reg_read(UC_ARM64_REG_PC)))) or False)
 error=None
 try:u.emu_start(sy['_VNOP_READ'],0,count=2000000)
 except U.UcError as e:error=str(e)
 assert bool(error)==bool(case.get('invalid_target')),(case,error,bad)
 snapshot=dict(registers=[hex(u.reg_read(getattr(sys.modules[__name__],f'UC_ARM64_REG_X{i}'))) for i in range(31)],simd=[hex(u.reg_read(getattr(sys.modules[__name__],f'UC_ARM64_REG_Q{i}'))) for i in range(32)],sp=hex(u.reg_read(UC_ARM64_REG_SP)),pc=hex(u.reg_read(UC_ARM64_REG_PC)),nzcv=hex(u.reg_read(UC_ARM64_REG_NZCV)),fpcr=hex(u.reg_read(UC_ARM64_REG_FPCR)),fpsr=hex(u.reg_read(UC_ARM64_REG_FPSR)),thread=hex(u.reg_read(UC_ARM64_REG_TPIDR_EL1)),native_initialized_memory={hex(p)+':'+str(n):bytes(u.mem_read(p,n)).hex() for p,n in sorted(writes)},caller_stack_sha256=B.sha(u.mem_read(SP,0x2000)),read_state=bytes(u.mem_read(state,112)).hex(),api=api,body_boundary_seen=body_seen,visited=visited,error=error,bad=bad)
 fields=dict(A036=field(u,0xa036),A037=field(u,0xa037))
 scoped=not any(case.get(k) for k in ('no_video','foreign_frame','foreign_thread','null_context'))
 if candidate:assert fields==dict(A036=target if scoped else None,A037=A.ENTRY if scoped and target==A.ENTRY else None),(case,fields)
 else:assert fields==dict(A036=None,A037=None)
 if case.get('null_context'):assert u.reg_read(UC_ARM64_REG_X0)==22 and not body_seen
 elif not case.get('pending') and not case.get('invalid_target'):assert u.reg_read(UC_ARM64_REG_X0)==case.get('errno',0) and u.reg_read(UC_ARM64_REG_SP)==SP
 return snapshot,fields,dict(writes=len(renderer),max_row=max((y for x,y,n in renderer),default=None))

def header_reset(raw,m,b,proto,va,patches,candidate,extra_rectangles=()):
 u=machine(raw,m,proto,va,patches,candidate);ps={k:int(v,16) for k,v in b['probe']['symbols'].items()};u.mem_write(ps['probe_scratch'],struct.pack('<QQ',FB,ROW))
 for y in (784,812):
  for row in range(20):u.mem_write(FB+(y+row)*ROW+1024,b'\xff'*(480*4))
 for rx,ry,rw,rh in extra_rectangles:
  for y in range(ry,ry+rh):u.mem_write(FB+y*ROW+rx*4,b'\xff'*(rw*4))
 u.hook_add(U.UC_HOOK_CODE,lambda u,pc,size,d:u.emu_stop() if pc==m['symbols']['_vn_rdwr'] else None);u.emu_start(0xfffffff00769bf90,0,count=1000000);assert u.reg_read(UC_ARM64_REG_PC)==m['symbols']['_vn_rdwr']
 if candidate:assert field(u,0xa036)==field(u,0xa037)==0
 if candidate:
  for rx,ry,rw,rh in extra_rectangles:
   assert all(bytes(u.mem_read(FB+y*ROW+rx*4,rw*4))==bytes(rw*4) for y in range(ry,ry+rh)), 'Stale candidate-entry tile survived a new header attempt'
 return dict(registers=[hex(u.reg_read(getattr(sys.modules[__name__],f'UC_ARM64_REG_X{i}'))) for i in range(31)],sp=hex(u.reg_read(UC_ARM64_REG_SP)),nzcv=hex(u.reg_read(UC_ARM64_REG_NZCV)))

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.output.exists() and a.output.resolve().is_relative_to(R/'reports');assert not a.work.exists() and a.work.resolve().is_relative_to(R/'out');native,nm,audit=A.audit();b=json.loads(a.build.read_text());raw=(R/b['candidate']['path']).read_bytes();assert B.sha(raw)==b['candidate']['sha256']=='54179a8775ee4d723bb0493a66679932f986d39231e9ef371d856afb07b3ea07';m=B.macho(raw);ps={k:int(v,16) for k,v in b['probe']['symbols'].items()};va=B.align(max(s['va']+s['size'] for s in m['segments']))+4096
 constants=dict(probe_scratch=ps['probe_scratch'],probe_read_state=ps['probe_read_state'],read_header_return=0xfffffff00769bf94,native_vn_rdwr=m['symbols']['_vn_rdwr'],read_dispatch_return=A.DISPATCH+4,read_apfs_address=A.ENTRY,read_apfs_resume=A.ENTRY+4)
 proto,sy,commands=compile_probe(a.work,constants,va);repro,_,repro_commands=compile_probe(a.work.with_name(a.work.name+'-reproduce'),constants,va);assert proto==repro
 assert raw[B.backed(m,A.ENTRY):B.backed(m,A.ENTRY)+4].hex()=='ff0304d1'
 patches=[(ps['probe_dense_769bf90_replay'],sy['read_header_reset']),(ps['probe_dense_746c688_replay'],sy['read_dispatch_target']),(A.ENTRY,sy['read_apfs_entry'])]
 for pc,_ in patches[:2]:
  ins=A.disasm(raw,m,pc,12);assert [i.mnemonic for i in ins[:2]]==['adrp','add'];assert ins[2].mnemonic==('b' if pc==patches[0][0] else 'br')
 cases=[dict(name='matched regular candidate',index=17),dict(name='assigned index1',index=1),dict(name='assigned index73',index=73),dict(name='signed negative index control',index=-1),dict(name='callback errno5 retained',errno=5),dict(name='callback entry pending',pending=True),dict(name='other APFS operation target',target=0xfffffff00519041c),dict(name='unmapped target call-site without entry',target=0x500000,invalid_target=True),dict(name='foreign thread',foreign_thread=True),dict(name='foreign native frame',foreign_frame=True),dict(name='no video',no_video=True),dict(name='null context native EINVAL',null_context=True)]
 checks=[]
 for case in cases:
  actual,fields,bounds=execute(raw,m,b,proto,va,patches,case,True);expected,_,_=execute(raw,m,b,proto,va,patches,case,False);assert actual==expected,(case,{k:dict(actual=actual[k],expected=expected[k]) for k in actual if actual[k]!=expected[k]});checks.append(dict(case=case,passed=True,snapshot=actual,fields=fields,renderer=bounds))
 assert header_reset(raw,m,b,proto,va,patches,True)==header_reset(raw,m,b,proto,va,patches,False)
 # A wrong source register still preserves the native call, but must fail the
 # displayed runtime-target contract. In-memory mutation only.
 mutated=bytearray(proto);ins=A.CS.disasm(proto[sy['read_dispatch_target']-va:sy['read_apfs_entry']-va],sy['read_dispatch_target']);at=next(i.address-va for i in ins if i.mnemonic=='mov' and i.op_str=='x23, x8');assert struct.unpack_from('<I',proto,at)[0]==0xaa0803f7;struct.pack_into('<I',mutated,at,0xaa0703f7);rejected=False
 try:execute(raw,m,b,bytes(mutated),va,patches,cases[0],True)
 except AssertionError:rejected=True
 assert rejected
 assert B.sha((R/b['candidate']['path']).read_bytes())==b['candidate']['sha256']
 out=dict(scope=__doc__,candidate_sha256=b['candidate']['sha256'],prototype_code_sha256=B.sha(proto),prototype_code_va=hex(va),prototype_bytes=len(proto),prototype_binary_reproduced=True,commands=commands,reproduce_commands=repro_commands,patches=[dict(site=hex(pc),before=raw[B.backed(m,pc):B.backed(m,pc)+4].hex(),after=B.branch(pc,target).hex(),target=hex(target),scope='in memory only') for pc,target in patches],checks=checks,header_reset_transparency_and_stale_clear=True,wrong_display_register_negative_rejected=True,max_renderer_row=831,field_layout=dict(A036=dict(x=256,y=784,value='actual dispatch x8'),A037=dict(x=256,y=812,value='pinned regular-read entry PC, zero until observed')),sources=[dict(path=str(p.relative_to(R)).replace('\\','/'),sha256=B.sha(p.read_bytes())) for p in (Path(__file__),R/'scripts/read_dispatch_audit.py',R/'patches/xnu-8796-candidates/read-dispatch-observer.S',R/'package/entry-probe/entry-probe.S')],device_accessed=False,boot_package_emitted=False,kernel_file_modified=False,runtime_target_known=False,limitations=['Only pinned regular-read entry is observed; a different A036 target does not imply that target failed to enter','Native VNOP wrapper and first callback instruction execute; callback remainder and uio API are modeled','Extra framebuffer rows through831 require full integration/mapping/exception/package qualification before any device use','Signed negative index is a synthetic corruption control, not a valid runtime configuration'])
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(dict(cases=len(cases),attempt_pairs=len(cases)+1,negative_rejected=rejected,prototype_reproduced=True,boot_package_emitted=False,passed=True)))
if __name__=='__main__':main()
