"""PROBE65: one scoped first-request backend trace in retired observer code and existing inert data."""
import copy,json,hashlib,struct,argparse,subprocess,importlib.util
from pathlib import Path
import init_bridge_inputs as P
R=P.R;read=P.read;sha=P.sha;ref=P.ref;P55=P.P55;P57=P.P57;MARKERS=P.MARKERS
BASE=R/'reports/kernel-entry-probe/2026-10-30-probe61-init-bridge-r2'
TESTS=P.TESTS|{'backend-trace','completion-layout','unmap-chain','mdev-native-chain','render-barrier'}
SITES=[(1,0xfffffff005194694,'x20'),(2,0xfffffff007476f78,'x19'),(3,0xfffffff005198638,'x0'),(4,0xfffffff0051987b0,'x19'),(5,0xfffffff00741ff48,'x19'),(6,0xfffffff00519469c,'x20'),(7,0xfffffff00741fcc8,'x0'),(8,0xfffffff00741fda4,'x19'),(9,0xfffffff00741fdac,'x19'),(10,0xfffffff00741ff2c,'x19'),(11,0xfffffff00741ff34,'x19'),(12,0xfffffff00742b8e4,'x0'),(13,0xfffffff00742ba84,'x19'),(14,0xfffffff00742b50c,'x0'),(15,0xfffffff00742b514,'x0')]
START=0xfffffff0084ba590
RETIRED_START=0xfffffff0084ba584
RETIRED_END=0xfffffff0084bbc7c
EXPECTED_CODE='15b04f041bc8359cf16745370f7182a9aa016169355ac9479eb10a532d1f5606'
EXPECTED_SYMBOLS={'return_1': '0xfffffff0084ba6dc', 'return_10': '0xfffffff0084bb124', 'return_11': '0xfffffff0084bb234', 'return_12': '0xfffffff0084bb348', 'return_13': '0xfffffff0084bb4a0', 'return_14': '0xfffffff0084bb5c4', 'return_15': '0xfffffff0084bb6d8', 'return_2': '0xfffffff0084ba7d8', 'return_3': '0xfffffff0084ba8b8', 'return_4': '0xfffffff0084baa00', 'return_5': '0xfffffff0084bab40', 'return_6': '0xfffffff0084bac90', 'return_7': '0xfffffff0084bada0', 'return_8': '0xfffffff0084baf08', 'return_9': '0xfffffff0084bb024', 'return_9_fallthrough': '0xfffffff0084bb028', 'trace_1': '0xfffffff0084ba590', 'trace_10': '0xfffffff0084bb02c', 'trace_11': '0xfffffff0084bb128', 'trace_12': '0xfffffff0084bb238', 'trace_13': '0xfffffff0084bb34c', 'trace_14': '0xfffffff0084bb4a4', 'trace_15': '0xfffffff0084bb5c8', 'trace_2': '0xfffffff0084ba6e0', 'trace_3': '0xfffffff0084ba7dc', 'trace_4': '0xfffffff0084ba8bc', 'trace_5': '0xfffffff0084baa04', 'trace_6': '0xfffffff0084bab44', 'trace_7': '0xfffffff0084bac94', 'trace_8': '0xfffffff0084bada4', 'trace_9': '0xfffffff0084baf0c', 'trace_hex': '0xfffffff0084bb790', 'trace_state': '0xfffffff0084e75b0', 'trace_tile': '0xfffffff0084bb6dc', 'trace_tile_postbarrier': '0xfffffff0084bb750'}

def builder():
 s=importlib.util.spec_from_file_location('trace_builder',R/'scripts/build-kernel-entry-probe.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def source(b,raw):
 B=builder();m=B.macho(raw);old=(R/'package/entry-probe/entry-probe.S').read_text();parts=['.text\n.p2align 4\n']
 for macro in ('PROBE_SAVE','PROBE_RESTORE','HEX_DIGITS'):
  at=old.index('.macro '+macro+'\n');parts.append(old[at:old.index('.endm',at)+5]+'\n')
 parts.append('.macro SAVE\nPROBE_SAVE\nstr x30,[sp,#168]\n.endm\n.macro RESTORE\nldr x30,[sp,#168]\nPROBE_RESTORE\n.endm\n')
 sy=b['probe']['symbols'];parts.append('.equ probe_scratch,'+sy['probe_scratch']+'\n.equ parent_state,'+sy['probe_resource_strategy_state']+'\n')
 for i,site,bpreg in SITES:
  parts.append(f'.global trace_{i}\ntrace_{i}:\nSAVE\nadr x9,trace_state\n')
  if i==1:
   parts.append("""adr x10,parent_state
ldr x11,[x10,#8]
cbz x11,done_1
ldr x11,[x10,#16]
tbz x11,#1,done_1
ldr x11,[x10]
ldr x12,[x29]
ldr x12,[x12]
cmp x11,x12
b.ne done_1
ldr x12,[x29,#8]
movz x13,#0xe574
movk x13,#0x0746,lsl #16
movk x13,#0xfff0,lsl #32
movk x13,#0xffff,lsl #48
cmp x12,x13
b.ne done_1
ldaxr w11,[x9]
cbnz w11,clear_1
mov w12,#1
stlxr w13,w12,[x9]
cbnz w13,done_1
str x20,[x9,#8]
str x0,[x9,#16]
str x29,[x9,#48]
mov w11,#2
stlr w11,[x9]
""")
  else:
   parts.append(f'ldar w10,[x9]\ncmp w10,#2\nb.ne done_{i}\nldr x10,[x9,#8]\ncmp x10,{bpreg}\nb.ne done_{i}\n')
  if i>=7:
   parts.append(f'ldr x10,[x9,#24]\nmovz x11,#0xfcc8\nmovk x11,#0x0741,lsl #16\nmovk x11,#0xfff0,lsl #32\nmovk x11,#0xffff,lsl #48\ncmp x10,x11\nb.ne done_{i}\nldr x10,[x9,#104]\n')
   if i==7:
    parts.append('cmp x10,x29\nb.ne done_7\nmovz x11,#0x6f80\nmovk x11,#0x0747,lsl #16\nmovk x11,#0xfff0,lsl #32\nmovk x11,#0xffff,lsl #48\ncmp x30,x11\nb.ne done_7\n')
   elif i==13:parts.append('ldr x11,[x29]\nldr x11,[x11]\ncmp x10,x11\nb.ne done_13\nldr x11,[x29,#8]\nmovz x12,#0xff48\nmovk x12,#0x0741,lsl #16\nmovk x12,#0xfff0,lsl #32\nmovk x12,#0xffff,lsl #48\ncmp x11,x12\nb.ne done_13\n')
   else:parts.append(f'ldr x11,[x29]\ncmp x10,x11\nb.ne done_{i}\n')
   if i in (14,15):parts.append(f'movz x11,#0xff34\nmovk x11,#0x0741,lsl #16\nmovk x11,#0xfff0,lsl #32\nmovk x11,#0xffff,lsl #48\ncmp x30,x11\nb.ne done_{i}\n')
   if i==12:parts.append('movz x11,#0xff48\nmovk x11,#0x0741,lsl #16\nmovk x11,#0xfff0,lsl #32\nmovk x11,#0xffff,lsl #48\ncmp x30,x11\nb.ne done_12\n')
  if i==4:parts.append('ldr x10,[x9,#96]\ncmp x10,x20\nb.ne done_4\nldr x10,[x9,#112]\ncmp x10,x29\nb.ne done_4\n')
  if i==5:parts.append('ldr x10,[x9,#104]\nldr x11,[x29]\ncmp x10,x11\nb.ne done_5\n')
  if i==6:parts.append('ldr x10,[x9,#48]\ncmp x10,x29\nb.ne done_6\n')
  parts.append(f'add x10,x9,#{64+(i-1)*4 if i<=6 else 128+(i-7)*4}\nldaxr w11,[x10]\ncbnz w11,clear_{i}\nmov w11,#1\nstlxr w12,w11,[x10]\ncbnz w12,done_{i}\n')
  if i==2:parts.append('str x8,[x9,#24]\nstr w20,[x9,#32]\nstr x29,[x9,#104]\n')
  if i==3:parts.append('str x1,[x9,#96]\nadd x10,sp,#160\nstr x10,[x9,#112]\nadd x10,x9,#72\n')
  if i==6:parts.append('str w0,[x9,#40]\n')
  parts.append(f'mov w11,#2\nstlr w11,[x10]\nmov x24,#{i}\nbl trace_tile\n')
  fields={1:[('x20',0xb620,200),('x0',0xb621,232)],2:[('x8',0xb622,264),('x20',0xb623,296)],6:[('x0',0xb624,328)]}.get(i,[])
  for reg,tag,y in fields:parts.append(f'mov x23,{reg}\nmov x24,#{tag}\nmov x25,#{y}\nbl trace_hex\n')
  if i==8:
   for expr,tag,y in [('mov x23,x20',0xb630,360),('ldr x23,[x21]',0xb631,392),('ldr x23,[x21,#8]',0xb632,424),('ldr w23,[x19,#0x4c]\nlsl x23,x23,#32\nldr w24,[x19,#0x5c]\norr x23,x23,x24',0xb633,456)]:
    # Renderer clobbers saved x19..x25: reload native operands from SAVE before each capture.
    parts.append('ldp x19,x20,[sp,#80]\nldr x21,[sp,#96]\n'+expr+f'\nmov x24,#{tag}\nmov x25,#{y}\nbl trace_hex\n')
  if i==9:
   for expr,tag,y in [('mov w23,w0',0xb634,488),('ldr x23,[sp,#184]',0xb635,520)]:
    parts.append(expr+f'\nmov x24,#{tag}\nmov x25,#{y}\nbl trace_hex\n')
  if i==14:parts.append('ldr w23,[x0,#0x4c]\nmov x24,#0xb650\nmov x25,#680\nbl trace_hex\n')
  if i in (11,13):
   captures={11:[('mov w23,w0',0xb640,552)],13:[('ldr w23,[x19,#0x4c]',0xb641,584),('ldr x23,[x19,#0x80]',0xb642,616),('ldr x23,[x19,#0xd0]',0xb643,648)]}[i]
   for expr,tag,y in captures:parts.append('ldr x19,[sp,#80]\n'+expr+f'\nmov x24,#{tag}\nmov x25,#{y}\nbl trace_hex\n')
  if i in (4,5,6):
   # Freeze only when the original APFS call has returned and the observed completion boundary is present.
   parts.append(f'adr x9,trace_state\nadd x10,x9,#84\nldar w11,[x10]\ncmp w11,#2\nb.ne done_{i}\nldr x10,[x9,#24]\nmovz x11,#0xfcc8\nmovk x11,#0x0741,lsl #16\nmovk x11,#0xfff0,lsl #32\nmovk x11,#0xffff,lsl #48\n')
   # Correct full canonical address is emitted explicitly, no guessed runtime symbol.
   assert 0xfffffff00741fcc8 == ((0xffff<<48)|(0xfff0<<32)|(0x0741<<16)|0xfcc8)
   parts.append(f'cmp x10,x11\nb.eq close_{i}\ncbz x10,close_{i}\nldr w10,[x9,#40]\ncbnz w10,close_{i}\nadd x10,x9,#76\nldar w11,[x10]\ncmp w11,#2\nb.ne done_{i}\nclose_{i}:\nmov w11,#3\nstlr w11,[x9]\n')
  parts.append(f'b done_{i}\nclear_{i}:\nclrex\ndone_{i}:\nRESTORE\n')
  if i==9:
   assert raw[B.backed(m,site):B.backed(m,site)+4]==bytes.fromhex('800e0035')
   parts.append('cbz w0,return_9_fallthrough\n.global return_9\nreturn_9: b .\n.global return_9_fallthrough\nreturn_9_fallthrough: b .\n')
  else:parts.append(f'.inst 0x{int.from_bytes(raw[B.backed(m,site):B.backed(m,site)+4],"little"):08x}\n.global return_{i}\nreturn_{i}:\nb .\n')
 parts.append("""
trace_tile:
mov x17,x24
adr x15,probe_scratch
ldp x9,x10,[x15]
cbz x9,tile_done
mov x16,#512
cmp x24,#11
b.lo tile_position
sub x24,x24,#4
mov x16,#704
tile_position:
mov x11,#32
madd x11,x24,x11,xzr
add x11,x11,#384
madd x9,x10,x11,x9
add x9,x9,x16
mov w12,#0xff80
movk w12,#0xff40,lsl #16
mov x13,#16
1: mov x14,#32
mov x15,x9
2: str w12,[x15],#4
subs x14,x14,#1
b.ne 2b
add x9,x9,x10
subs x13,x13,#1
b.ne 1b
dsb sy
.global trace_tile_postbarrier
trace_tile_postbarrier:
cmp x17,#10
b.ne tile_done
// Positive post-DSB witness only: cyan right half, no additional barrier.
sub x9,x9,x10,lsl #4
add x9,x9,#64
mov w12,#0xc0ff
movk w12,#0xff40,lsl #16
mov x13,#16
post_row:
mov x15,x9
mov x14,#16
post_pixel:
str w12,[x15],#4
subs x14,x14,#1
b.ne post_pixel
add x9,x9,x10
subs x13,x13,#1
b.ne post_row
tile_done: ret
trace_hex:
mov x19,x23
adr x15,probe_scratch
ldp x21,x22,[x15]
cbz x21,hex_done
madd x21,x22,x25,x21
add x21,x21,#1024
// Clear exactly this 480x20 row, including inter-glyph gaps, before drawing.
mov x9,x21
mov x10,#20
clear_row:
mov x11,x9
mov x12,#480
clear_pixel:
str wzr,[x11],#4
subs x12,x12,#1
b.ne clear_pixel
add x9,x9,x22
subs x10,x10,#1
b.ne clear_row
mov x23,x24
mov x24,#12
HEX_DIGITS
mov x23,x19
mov x24,#60
HEX_DIGITS
dsb sy
hex_done: ret
.p2align 3
.global trace_state
trace_state: .zero 128
hex_font:
""")
 font=(R/'out/kernel-entry-probe-55-provenance-r3/probe.S').read_text();at=font.index('\nhex_font:');font=font[at:].splitlines()[2:];rows=[]
 for line in font:
  if '.word' in line:rows.append(line)
  elif rows:break
 parts.append('\n'.join(rows)+'\n');result=''.join(parts)
 result='.equ trace_state,'+sy['probe_cluster_gate_state']+'\n'+result.replace('trace_state: .zero 128', '')
 for reg,sym in [('x10','parent_state'),('x15','probe_scratch'),('x9','trace_state')]:
  result=result.replace('adr '+reg+','+sym, '\n'.join(f'{op} {reg},#(({sym} >> {shift}) & 0xffff)'+(f',lsl #{shift}' if shift else '') for op,shift in [('movz',0),('movk',16),('movk',32),('movk',48)]))
 return result

def compile_code(text,work):
 work.mkdir(parents=True,exist_ok=True);(work/'trace.S').write_text(text);base='/mnt/'+str(work.resolve())[0].lower()+str(work.resolve())[2:].replace('\\','/')
 subprocess.run(['wsl','-d','Ubuntu-22.04','--','/usr/bin/clang','--target=aarch64-none-elf','-c',base+'/trace.S','-o',base+'/trace.o'],check=True,capture_output=True)
 subprocess.run(['wsl','-d','Ubuntu-22.04','--','/usr/bin/ld.lld','-Ttext='+hex(START),'-e','trace_1',base+'/trace.o','-o',base+'/trace.elf'],check=True,capture_output=True)
 subprocess.run(['wsl','-d','Ubuntu-22.04','--','/usr/bin/llvm-objcopy','-O','binary','--only-section=.text',base+'/trace.elf',base+'/trace.bin'],check=True,capture_output=True)
 nm=subprocess.check_output(['wsl','-d','Ubuntu-22.04','--','/usr/bin/llvm-nm','--defined-only',base+'/trace.elf'],text=True);sy={line.split()[2]:int(line.split()[0],16) for line in nm.splitlines() if len(line.split())==3};return (work/'trace.bin').read_bytes(),sy

def derive(code,sy):
 b=P.read(BASE/'build.json');raw=(R/b['candidate']['path']).read_bytes();P.verify_bytes(b,raw);B=builder();m=B.macho(raw);out=bytearray(raw);off=B.backed(m,START,len(code));assert START+len(code)<=RETIRED_END and not b['read_flow']['resource_cluster']['gate_diagnostics']['enabled'];assert not any(raw[B.backed(m,int(b['probe']['symbols']['probe_cluster_gate_state'],16)):B.backed(m,int(b['probe']['symbols']['probe_cluster_gate_state'],16))+176]);patches=[];code=bytearray(code)
 retired={c['reason'] for c in b['lean_observation']['changes'] if c['kind']=='restore-native'}
 syms=b['probe']['symbols'];ranges=sorted((int(syms[k],16),int(syms[k+'_replay'],16)+8,k) for k in retired if k in syms and k+'_replay' in syms and RETIRED_START<=int(syms[k],16)<RETIRED_END)
 assert ranges[0][0]==RETIRED_START and ranges[-1][1]==RETIRED_END and all(0<=z[0]-a[1]<=12 for a,z in zip(ranges,ranges[1:]))
 assert all(k in retired or k.endswith('_replay') for k,v in syms.items() if RETIRED_START<=int(v,16)<RETIRED_END)
 for i,site,reg in SITES:
  at=B.backed(m,site);assert not any(p.get('va')==hex(site) for p in b['patches']);target=sy['trace_'+str(i)];ret=sy['return_'+str(i)];code[ret-START:ret-START+4]=B.branch(ret,0xfffffff00741ff7c if i==9 else site+4);after=B.branch(site,target);out[at:at+4]=after;patches.append(dict(va=hex(site),file_offset=at,before=raw[at:at+4].hex(),after=after.hex(),reason='probe_backend_trace_'+str(i)))
 ret=sy['return_9_fallthrough'];code[ret-START:ret-START+4]=B.branch(ret,0xfffffff00741fdb0)
 out[off:off+len(code)]=code;return b,bytes(out),patches,bytes(code)

def verify_bytes(b,raw):
 cfg=b['backend_trace'];assert cfg['code_sha256']==EXPECTED_CODE and {k:cfg['symbols'][k] for k in EXPECTED_SYMBOLS}==EXPECTED_SYMBOLS;code=(R/cfg['code_path']).read_bytes();assert hashlib.sha256(code).hexdigest()==cfg['code_sha256'];old,expected,patches,_=derive(code,{k:int(v,16) for k,v in cfg['symbols'].items()});assert raw==expected and b['probe_revision']==65 and b['patches']==old['patches']+patches
 assert (R/cfg['source_path']).read_text()==source(old,(R/old['candidate']['path']).read_bytes())
 for key in ('read_flow','root_mount_diagnostic','pthread_startup','fscompression_startup','image4_compatibility','probe','lean_observation','target_observation','init_bridge_observation'):assert b[key]==old[key]
 return True

def metadata(build):return P.metadata(build)
def validate(meta,kernel_sha):
 b=P.P.bound(meta['build']);proof=P.P.bound(meta['milestone-proof']);raw=(R/b['candidate']['path']).read_bytes();assert hashlib.sha256(raw).hexdigest()==kernel_sha==proof['candidate_sha256'];verify_bytes(b,raw)
 for item in proof['sources']:assert sha(R/item['path'])==item['sha256']==sha(R/item['archive'])
 assert set(proof['tests'])==TESTS
 for name,item in proof['tests'].items():
  r=P.P.bound(item);checks=r.get('checks',r.get('cases'));assert r['candidate_sha256']==kernel_sha and checks and all(c['passed'] for c in checks) and len(checks)==proof['counts'][name]
 assert sha(R/P.P.bound(proof['reproduce_build'])['candidate']['path'])==kernel_sha
 from nuwa_exec_detail_launch_context import API
 root=P.P.bound(meta['root-launch']);API.validate_report(root);assert root['candidate_sha256']==kernel_sha and P.P.bound(meta['launch-context'])['components']['kernel']['sha256']==kernel_sha
 return b

if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--work',type=Path,required=True);a.add_argument('--output',type=Path,required=True);a=a.parse_args();assert not a.work.exists() and not a.output.exists();b=read(BASE/'build.json');raw=(R/b['candidate']['path']).read_bytes();text=source(b,raw);code,sy=compile_code(text,a.work);old,raw,patches,code=derive(code,sy);b=copy.deepcopy(old);(a.work/'trace.bin').write_bytes(code);(a.work/'kernel-entry-probe.macho').write_bytes(raw);(a.work/'probe.S').write_bytes((R/'out/kernel-entry-probe-55-provenance-r3/probe.S').read_bytes());b['candidate']=dict(path=(a.work/'kernel-entry-probe.macho').as_posix(),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw));b['probe_revision']=65;b['patches']+=patches;b['backend_trace']=dict(code_path=(a.work/'trace.bin').as_posix(),code_sha256=hashlib.sha256(code).hexdigest(),source_path=(a.work/'trace.S').as_posix(),symbols={k:hex(v) for k,v in sy.items()},scope='Nine mdev/completion/unmap boundaries added to six scoped backend stages; upper isolated HEX rows with background clearing; first scoped APFS device submission only; claim never reused; other backend completion is partial. No object reads after callback.');a.output.parent.mkdir(parents=True,exist_ok=True);verify_bytes(b,raw);a.output.write_text(json.dumps(b,indent=2));print(b['candidate'],len(code))
