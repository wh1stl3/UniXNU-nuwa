"""Pin shipped loader stores and execute native page/header argument blocks.

Unicorn block and wrapper tests with explicit API models. No EFI allocation,
full arm_init, real MAC/filesystem, MMU execution or hardware qualification.
"""
import argparse,hashlib,importlib.util,json,struct,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('read_fixture',ROOT/'scripts/test-read-boundaries.py');F=importlib.util.module_from_spec(spec);sys.modules[spec.name]=F;spec.loader.exec_module(F)
from unicorn.arm64_const import *
from capstone import Cs,CS_ARCH_ARM64,CS_MODE_ARM
U=F.U;B=F.B
FW=ROOT/'out/upstream-firmware-40014018074/nuwa-firmware-40014018074'
def sha(x):return hashlib.sha256(x).hexdigest()
def instructions(raw,at,pc,size):
 return [dict(pc=hex(x.address),bytes=x.bytes.hex(),instruction=x.mnemonic+' '+x.op_str) for x in Cs(CS_ARCH_ARM64,CS_MODE_ARM).disasm(raw[at:at+size],pc)]
def adt_nodes(raw):
 nodes={}
 def node(at,parent):
  count,children=struct.unpack_from('<II',raw,at);at+=8;props={}
  for _ in range(count):
   key=raw[at:at+32].split(b'\0')[0].decode('ascii');n=struct.unpack_from('<I',raw,at+32)[0]&0x7fffffff;at+=36
   assert at+n<=len(raw) and key not in props;props[key]=raw[at:at+n];at+=(n+3)&~3
  name=props.get('name',b'').split(b'\0')[0].decode('ascii');path=parent.rstrip('/')+'/'+name if parent else '/';assert path not in nodes;nodes[path]=props
  for _ in range(children):at=node(at,path)
  return at
 end=node(0,'');assert not any(raw[end:]);return nodes

def native_machine(raw,m):
 base=min(s['va'] for s in m['segments'] if s['size']);end=max(s['va']+s['size'] for s in m['segments'])
 u=U.Uc(U.UC_ARCH_ARM64,U.UC_MODE_ARM);u.mem_map(base,B.align(end-base));u.mem_map(F.STACK,0x10000)
 for s in m['segments']:
  if s['filesize']:u.mem_write(s['va'],raw[s['fileoff']:s['fileoff']+s['filesize']])
 return u

def header_args(raw,m,shift):
 u=native_machine(raw,m);sy=m['symbols'];page=sy['_PAGE_SHIFT_CONST'];img=F.STACK+0x7000;sp=F.STACK+0x8000
 u.mem_write(page,struct.pack('<I',shift));u.mem_write(img+0x20,struct.pack('<Q',F.STACK+0x4000));u.mem_write(img+0x40,struct.pack('<Q',F.STACK+0x6000))
 u.reg_write(UC_ARM64_REG_X19,img);u.reg_write(UC_ARM64_REG_X26,page);u.reg_write(UC_ARM64_REG_SP,sp)
 calls=[]
 def hook(u,pc,size,data):
  if pc==F.R.FIRST:u.emu_stop();return
  if pc in (0xfffffff00746aacc,0xfffffff00746a6d8):
   calls.append(hex(pc));u.reg_write(UC_ARM64_REG_X0,F.STACK+(0x2800 if pc==0xfffffff00746aacc else 0x2900));u.reg_write(UC_ARM64_REG_PC,u.reg_read(UC_ARM64_REG_LR))
 u.hook_add(U.UC_HOOK_CODE,hook);u.emu_start(0xfffffff00769bf40,0,count=100)
 assert u.reg_read(UC_ARM64_REG_PC)==F.R.FIRST and len(calls)==2
 args=[u.reg_read(getattr(sys.modules[__name__],f'UC_ARM64_REG_X{i}')) for i in range(8)]
 assert args==[0,F.STACK+0x4000,F.STACK+0x6000,1<<shift,0,2,8,F.STACK+0x2800]
 assert struct.unpack('<QQ',u.mem_read(sp,16))==(sp+0x1c,F.STACK+0x2900)
 return dict(shift=shift,args=args,stack_arguments=[hex(sp+0x1c),hex(F.STACK+0x2900)],modelled_calls=calls)

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists() or not a.output.resolve().is_relative_to(ROOT/'reports'):raise ValueError('Fresh reports destination required')
 b=json.loads(a.build.read_text());candidate=(ROOT/b['candidate']['path']).read_bytes();assert sha(candidate)==b['candidate']['sha256'];raw=B.INPUT.read_bytes();assert sha(raw)==B.EXPECTED;m=B.macho(raw)
 adt=(ROOT/'out/exec-mainline-v36/launch/kernel.macho.adt').read_bytes();assert sha(adt)=='458232d6270643a88b465814535eead13eb88771c869e3cf6edfbe1741aa12f0'
 value=adt_nodes(adt)['/chosen']['darwinboot-memory-size'];assert len(value)==8;window=struct.unpack('<Q',value)[0];assert window==0x40000000
 # Use shipped Darwin22 EFI, not the unpatched upstream Darwin23 header.
 pe=(FW/'build/AARCH64/DarwinBoot.efi').read_bytes();assert sha(pe)=='3313e8568b97432675c33e76dc3b8a7240cfff66a1cd0559ba33e2f512440145';e=struct.unpack_from('<I',pe,60)[0];n=struct.unpack_from('<H',pe,e+6)[0];o=struct.unpack_from('<H',pe,e+20)[0];sections=[struct.unpack_from('<4I',pe,e+24+o+40*i+8) for i in range(n)]
 def pe_at(pc):
  s=next(s for s in sections if s[1]<=pc<s[1]+s[0]);return s[3]+pc-s[1]
 start=0x233c;end=0x2368;block=pe[pe_at(start):pe_at(end)]
 assert block.hex()=='f62740f9e8830f32e1a30291f52747a902068052c80200b9c0a20091e8bf46f9c96e01f9c8d600a9c9d201a9'
 loader=[]
 for w in (0x10000000,window,window+0x200000,0x200000000):
  u=U.Uc(U.UC_ARCH_ARM64,U.UC_MODE_ARM);u.mem_map(0x2000,0x1000);u.mem_write(start,block);u.mem_map(F.STACK,0x10000);sp=F.STACK+0x4000;args=F.STACK+0x7000;u.reg_write(UC_ARM64_REG_SP,sp);u.reg_write(UC_ARM64_REG_X20,0x8c4000000)
  u.mem_write(sp+0x48,struct.pack('<Q',args));u.mem_write(sp+0x70,struct.pack('<QQ',0x8c01c8000,w));u.mem_write(sp+0xd78,struct.pack('<Q',0xfffffff007004000));u.emu_start(start,end,count=30)
  actual=[struct.unpack('<Q',u.mem_read(args+x,8))[0] for x in (0x18,0x2d8,0x478)];assert actual==[w,w,0];loader.append(dict(window=w,memSize=actual[0],memSizeActual=actual[1],upstream_Darwin23_offset_untouched=actual[2]))
 # Execute fixed native PAGE_SHIFT stores; initial disk zero is not the result.
 page_pc=0xfffffff007972e74;page_end=0xfffffff007972e8c;page_bytes=raw[B.backed(m,page_pc):B.backed(m,page_end)]
 assert page_bytes.hex()=='48bffff01f2003d589018052091901b9680800b0092900b9'
 u=native_machine(raw,m);u.mem_write(m['symbols']['_PAGE_SHIFT_CONST'],struct.pack('<I',0xdeadbeef));u.emu_start(page_pc,page_end,count=10);shift=struct.unpack('<I',u.mem_read(m['symbols']['_PAGE_SHIFT_CONST'],4))[0];assert shift==12
 args=header_args(raw,m,shift);negative=header_args(raw,m,14);assert args['args'][3]==4096 and negative['args'][3]==16384
 changed=bytearray(raw);off=B.backed(m,0xfffffff00769bf88);assert changed[off:off+4].hex()=='06018052';changed[off:off+4]=bytes.fromhex('06008052')
 flags_rejected=False
 try:header_args(bytes(changed),m,shift)
 except AssertionError:flags_rejected=True
 assert flags_rejected
 sites={F.R.FIRST,F.R.FIRST+4}|{pc+off for pc,_,_ in F.R.CALLS for off in (0,4)}
 for pc in sites:
  item=next(x for x in b['patches'] if x.get('va')==hex(pc));assert bytes.fromhex(item['before'])==raw[B.backed(m,pc):B.backed(m,pc)+4]
 # Both native and candidate use the same real flags/request contract. API
 # models expose errno/residual branches but do not implement MAC or APFS.
 checks=[]
 for mode,remain,aresid,flags in [('success',0,True,8),('mac-denied',0,True,8),('read-error',0,True,8),('swap',0,True,8),('mac-pending',0,True,8),('dispatch-pending',0,True,8),('success',128,True,8),('success',128,False,8),('noauth',0,True,0x8008)]:
  actual=[];expected=[];events=[];reference_events=[];kw=dict(request=args['args'][3],ioflags=flags,remaining=remain,aresid=aresid)
  F.run(candidate,b,mode,capture=actual,events=events,**kw);F.run(candidate,b,mode,reference=True,capture=expected,events=reference_events,**kw);assert actual==expected and events==reference_events
  addiov=next(x for x in events if x['function']=='_uio_addiov');assert addiov['args'][1:3]==[F.STACK+0x6000,4096]
  if 'filesystem-callback' in actual[0]['calls']:
   v=next(x for x in events if x['function']=='filesystem-callback');vargs=bytes.fromhex(v['vnop_args']);assert struct.unpack_from('<I',vargs,24)[0]==flags
  if remain and aresid:assert int.from_bytes(bytes.fromhex(actual[0]['residual']),'little')==remain
  if mode=='noauth':assert '_mac_vnode_check_read' not in actual[0]['calls']
  else:assert '_mac_vnode_check_read' in actual[0]['calls']
  checks.append(dict(mode=mode,remaining=remain,aresid=aresid,flags=flags,passed=True,snapshot=actual[0],events=events))
 mapping=json.loads((ROOT/'reports/kernel-entry-probe/2026-10-26-v36/mapping.json').read_text());tcrs=sorted({int(x['tcr'],16) for x in mapping['snapshots']});granules=[dict(tcr=hex(t),tg0=(t>>14)&3,tg1=(t>>30)&3,ttbr0_bytes={0:4096,1:65536,2:16384}.get((t>>14)&3),ttbr1_bytes={2:4096,1:16384,3:65536}.get((t>>30)&3)) for t in tcrs]
 # Loader source normalization pins exactly to the shipped recipe inputs;
 # ABI modification is separately pinned to device patch and native EFI.
 recipe=json.loads((FW/'inputs.json').read_text());sources={}
 for item in recipe['recipe']['inputs']:
  if item['root']=='unixnu' and item['path'].endswith(('DarwinBoot.c','BootArgs.h')):
   source=Path('D:/Code/UniXNU-integration')/item['path'];blob=source.read_bytes().replace(b'\r\n',b'\n');assert sha(blob)==item['lf_sha256'];sources[item['path']]=item['lf_sha256']
 out=dict(scope=__doc__,level='Unicorn block/wrapper execution and static evidence only',native_input_sha256=sha(raw),candidate_sha256=sha(candidate),build_report_sha256=sha(a.build.read_bytes()),fixture_sha256=sha(Path(F.__file__).read_bytes()),test_sha256=sha(Path(__file__).read_bytes()),adt_sha256=sha(adt),owned_window=window,loader=dict(efi_sha256=sha(pe),fd_sha256=sha((FW/'build/FV/SILICIUM_UEFI.fd').read_bytes()),recipe_sha256=sha((FW/'inputs.json').read_bytes()),upstream_sources=sources,abi_patch_sha256=sha((ROOT/'patches/loader-candidates/0005-darwin22-boot-args.patch').read_bytes()),native_stores=instructions(pe,pe_at(start),start,end-start),checks=loader),page_init=dict(block=instructions(raw,B.backed(m,page_pc),page_pc,page_end-page_pc),shift=shift,full_arm_init_executed=False),header=dict(instructions=instructions(raw,B.backed(m,0xfffffff00769bf40),0xfffffff00769bf40,0x54),actual=args),flags_negative_control=dict(name='native header flags8 to flags0 mutation rejected',passed=flags_rejected,scope='in-memory instruction mutation only'),negative_control=dict(name='16KiB alternate shift rejected as current-image contract',injected_shift=14,observed_length=negative['args'][3],required_length=args['args'][3],passed=negative['args'][3]!=args['args'][3],scope='Synthetic changed global only, not a viable current-image configuration'),mapping_report_sha256=sha((ROOT/'reports/kernel-entry-probe/2026-10-26-v36/mapping.json').read_bytes()),restored_sites=[hex(pc) for pc in sorted(sites)],bootstrap_tcr_granules=granules,checks=checks,limitations=['Native blocks start at explicitly seeded boundaries, not complete EFI Boot or arm_init entry','API calls are models; no real MAC, APFS, decmpfs or allocation tested','Compiled constant12 does not establish observed live runtime value; no hardware page-size qualification','Historical transition fixture used memSizeActual offset0x478; do not use it as Darwin22 ABI proof','Bootstrap table granule and advertised runtime page size are separate values'],device_accessed=False)
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(dict(checks=len(checks),loader_store_cases=len(loader),shift=shift,header_length=args['args'][3],flags=args['args'][6],passed=True)))
if __name__=='__main__':main()
