"""Forward analysis with loader-derived placement and the existing 1GiB owned RAM window.
Native v22 mapping hooks execute; adversarial cases inject occupied or malformed descriptors before the hook. Normal case has no host page-table edits. No device commands. This is a model only.
"""
import argparse,importlib.util,json,struct,sys
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'out/python-tools'))
import unicorn as U
from unicorn.arm64_const import *
s=importlib.util.spec_from_file_location('b',R/'scripts/build-kernel-entry-probe.py');B=importlib.util.module_from_spec(s);s.loader.exec_module(B)
cli=argparse.ArgumentParser(description=__doc__)
cli.add_argument('--build',type=Path,required=True)
cli.add_argument('--adt',type=Path,required=True)
cli.add_argument('--output',type=Path,required=True)
cli.add_argument('--case',choices=['normal','occupied-probe','bad-topology','occupied-fb'],default='normal')
args=cli.parse_args()
build=json.loads(args.build.read_text());raw=(R/build['candidate']['path']).read_bytes();assert B.sha(raw)==build['candidate']['sha256']
m=B.macho(raw);base=min(s['va'] for s in m['segments'] if s['size']);end=max(s['va']+s['size'] for s in m['segments']);PA=0x8c01c8000;FB=0xb8000000;window=0x40000000
argsPA=B.align(PA+end-base,0x4000);treePA=argsPA+0x1000;adt=args.adt.read_bytes();used=B.align(treePA+len(adt),0x4000)-PA
u=U.Uc(U.UC_ARCH_ARM64,U.UC_MODE_ARM);u.mem_map(PA,window);u.mem_map(FB,0x1200000);u.mem_map(0x80000000,0x1000)
for seg in m['segments']:
 if seg['filesize']:u.mem_write(PA+seg['va']-base,raw[seg['fileoff']:seg['fileoff']+seg['filesize']])
a=bytearray(4096);struct.pack_into('<HH',a,0,2,2);struct.pack_into('<4Q',a,8,base,PA,window,PA+used);struct.pack_into('<6Q',a,0x28,FB,1,5760,1440,3200,32);struct.pack_into('<Q',a,0x60,base+treePA-PA);struct.pack_into('<I',a,0x68,len(adt));a[0x6c:0x6f]=b'-v\0';struct.pack_into('<Q',a,1144,window)
u.mem_write(argsPA,bytes(a));u.mem_write(treePA,adt);u.reg_write(UC_ARM64_REG_X0,argsPA);u.reg_write(UC_ARM64_REG_X20,argsPA);u.reg_write(UC_ARM64_REG_PSTATE,0x3c5);u.cpr_write(3,6,1,1,0,0x401);u.cpr_write(3,4,1,1,0,1<<31)
syms=m['symbols'];ps=build['probe']['symbols'];events=[];bad=[];checks=[];transition={};stop_reason=None
watch={syms[n]:n for n in ('_arm_vm_init','_pmap_bootstrap','_kernel_bootstrap','_panic','_set_tcr','_set_mmu_ttb_alternate','_set_mmu_ttb')}
watch.update({0xfffffff0073be1f0:'first-table-bzero',0xfffffff0073beb60:'before-TTBR0-switch',0xfffffff0073beb74:'before-TTBR1-switch',0xfffffff0073beb7c:'after-TTBR-switches'})
def walk(va):
 tcr=u.cpr_read(3,0,2,0,2);t1=bool(va>>63);size=64-((tcr>>(16 if t1 else 0))&63);level=4-(size-4)//9;root=u.cpr_read(3,0,2,0,1 if t1 else 0)&0x0000fffffffff000;rows=[]
 try:
  for lev in range(level,4):
   shift=12+9*(3-lev);index=(va>>shift)&((1<<(size-shift if lev==level else 9))-1);desc=struct.unpack('<Q',u.mem_read(root+index*8,8))[0];rows.append(hex(desc))
   if not desc&1:return dict(mapped=False,rows=rows)
   if lev==3 or not desc&2:return dict(mapped=True,pa=hex((desc&0x0000fffffffff000&~((1<<shift)-1))|(va&((1<<shift)-1))),rows=rows)
   root=desc&0x0000fffffffff000
 except Exception as e:return dict(error=str(e),rows=rows)
def hook(u,pc,size,_):
 global stop_reason
 if pc==0xfffffff0073beb60:
  root=u.reg_read(UC_ARM64_REG_X0)
  va=int(build['probe']['va'],16)
  path=[];table=root
  for shift in (30,21):
   at=table+((va>>shift)&(255 if shift==30 else 511))*8
   d=struct.unpack('<Q',u.mem_read(at,8))[0];path.append(at);table=d&0x0000fffffffff000
  leaves=[table+(((va+i)>>12)&511)*8 for i in range(0,int(ps['probe_end'],16)-va,4096)]
  transition['root1']=root;transition['leaves']=leaves
  if args.case=='occupied-probe':u.mem_write(leaves[-1],struct.pack('<Q',0x12345003))
  if args.case=='bad-topology':u.mem_write(path[-1],struct.pack('<Q',0x6000008000040d))
  transition['before']=[struct.unpack('<Q',u.mem_read(at,8))[0] for at in leaves]
  transition['registers']=[u.reg_read(getattr(U.arm64_const,'UC_ARM64_REG_X'+str(i))) for i in range(31)]
  transition['sp']=u.reg_read(UC_ARM64_REG_SP);transition['nzcv']=u.reg_read(UC_ARM64_REG_NZCV)
 if pc==syms['_set_mmu_ttb_alternate'] and 'registers' in transition:
  actual=[u.reg_read(getattr(U.arm64_const,'UC_ARM64_REG_X'+str(i))) for i in range(31)]
  expected=list(transition['registers']);expected[30]=0xfffffff0073beb64
  assert actual==expected
  assert u.reg_read(UC_ARM64_REG_SP)==transition['sp'] and u.reg_read(UC_ARM64_REG_NZCV)==transition['nzcv']
  checks.append(dict(name='TTBR1 call preserves GPR/SP/NZCV and native LR',passed=True))
  transition['after']=[struct.unpack('<Q',u.mem_read(at,8))[0] for at in transition['leaves']]
  if args.case in ('occupied-probe','bad-topology'):
   assert transition['before']==transition['after']
   checks.append(dict(name='Rejects occupied or malformed tables without partial page-table edits',passed=True))
   stop_reason='rejected-before-switch';u.emu_stop();return
 if pc==0xfffffff0073beb74:
  root=u.reg_read(UC_ARM64_REG_X0);transition['root0']=root
  transition['registers0']=[u.reg_read(getattr(U.arm64_const,'UC_ARM64_REG_X'+str(i))) for i in range(31)]
  transition['sp0']=u.reg_read(UC_ARM64_REG_SP);transition['nzcv0']=u.reg_read(UC_ARM64_REG_NZCV)
  if args.case=='occupied-fb':u.mem_write(root+16,struct.pack('<Q',0x6000004000040d))
 if pc==syms['_set_mmu_ttb'] and 'root0' in transition:
  actual=[u.reg_read(getattr(U.arm64_const,'UC_ARM64_REG_X'+str(i))) for i in range(31)]
  expected=list(transition['registers0']);expected[30]=0xfffffff0073beb78
  assert actual==expected and u.reg_read(UC_ARM64_REG_SP)==transition['sp0'] and u.reg_read(UC_ARM64_REG_NZCV)==transition['nzcv0']
  checks.append(dict(name='TTBR0 call preserves GPR/SP/NZCV and native LR',passed=True))
 if pc==syms['_set_mmu_ttb'] and 'root0' in transition and args.case=='occupied-fb':
  assert struct.unpack('<Q',u.mem_read(transition['root0']+16,8))[0]==0x6000004000040d
  assert struct.unpack('<Q',u.mem_read(int(ps['probe_scratch'],16)-base+PA,8))[0]==0
  checks.append(dict(name='Occupied framebuffer slot preserved and renderer disabled',passed=True))
  stop_reason='occupied-fb-before-switch';u.emu_stop();return

 if pc in watch:
  e=dict(site=watch[pc],pc=hex(pc),x0=hex(u.reg_read(UC_ARM64_REG_X0)),x1=hex(u.reg_read(UC_ARM64_REG_X1)),tcr=hex(u.cpr_read(3,0,2,0,2)),ttbr0=hex(u.cpr_read(3,0,2,0,0)),ttbr1=hex(u.cpr_read(3,0,2,0,1)),fb=walk(FB),probe=walk(int(build['probe']['va'],16)));events.append(e)
  if len(events)>100:u.emu_stop()
  if watch[pc]=='_kernel_bootstrap':u.emu_stop()
 if pc in (int(ps['exception_stop'],16),int(ps['fault_stop'],16),PA+int(ps['exception_stop'],16)-base,PA+int(ps['fault_stop'],16)-base):u.emu_stop()
def invalid(u,access,addr,size,value,_):bad.append(dict(access=access,address=hex(addr),pc=hex(u.reg_read(UC_ARM64_REG_PC))));return False
u.hook_add(U.UC_HOOK_CODE,hook);u.hook_add(U.UC_HOOK_MEM_INVALID,invalid)
error=None
try:u.emu_start(PA+m['entry']-base,0,count=20000000)
except U.UcError as e:error=str(e)
pc=u.reg_read(UC_ARM64_REG_PC);near=max((v,k) for k,v in syms.items() if v<=pc)
out=dict(scope=__doc__,candidate_sha256=B.sha(raw),input=dict(argsPA=hex(argsPA),treePA=hex(treePA),treeKVA=hex(base+treePA-PA),topOfKernelData=hex(PA+used),owned_window=hex(window),adt_sha256=B.sha(adt),loader_memSizeActual_offset=1144),events=events,error=error,pc=hex(pc),nearest=near[1]+'+'+hex(pc-near[0]),bad_memory=bad,final_fb=walk(FB),final_probe=walk(int(build['probe']['va'],16)))
if args.case=='normal':
 assert any(e['site']=='_pmap_bootstrap' for e in events),out
 assert error=='Invalid memory read (UC_ERR_READ_UNMAPPED)' and pc==syms['_PE_create_console']+0x48,out
 assert out['final_fb']['mapped'] and out['final_probe']['mapped'],out
 assert u.cpr_read(3,0,12,0,0)==int(ps['probe_vectors'],16)
 before=transition['before'];after=transition['after'];assert not any(before)
 start=int(build['probe']['va'],16);data=int(ps['probe_data'],16)
 for i,d in enumerate(after):
  va=start+i*4096;assert d&0x0000fffffffff000==PA+va-base
  if va<data: assert d&(1<<7) and not d&(1<<53) and d&(1<<54)
  else: assert not d&(1<<7) and d&(1<<53) and d&(1<<54)
 checks += [dict(name='Native cold path passes pmap probe after TTBR reconstruction',passed=True),dict(name='Code RO executable and data RW NX map exact probe physical pages',passed=True),dict(name='Next stop preserved as console platform read, not probe fetch',passed=True)]
else: assert stop_reason is not None and error is None,out
out.update(checks=checks,case=args.case,stop_reason=stop_reason,transition=transition)
args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(dict(case=args.case,checks=len(checks),passed=True,stop=out['nearest'])))
