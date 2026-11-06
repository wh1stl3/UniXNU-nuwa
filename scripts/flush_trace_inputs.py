"""PROBE71: one scoped first-request backend trace in retired observer code and existing inert data."""
import copy,json,hashlib,struct,argparse,subprocess,importlib.util
from pathlib import Path
import init_bridge_inputs as P
R=P.R;read=P.read;sha=P.sha;ref=P.ref;P55=P.P55;P57=P.P57;MARKERS=P.MARKERS
BASE=R/'reports/kernel-entry-probe/2026-10-30-probe61-init-bridge-r2'
TESTS=P.TESTS|{'backend-trace','completion-layout','unmap-chain','mdev-native-chain','upl-native-chain','map-native-chain','delete-native-chain'}
SITES=[(1, 18446744005075617428, 'x20'), (2, 18446744005112196984, 'x19'), (3, 18446744005075633720, 'x0'), (4, 18446744005075634096, 'x19'), (5, 18446744005111840584, 'x19'), (6, 18446744005075617436, 'x20'), (16, 18446744005111887200, 'x0'), (18, 18446744005111069120, 'x20'), (23, 18446744005110857132, 'x23'), (26, 18446744005110819652, 'x0'), (28, 18446744005110822296, 'x23'), (29, 18446744005110822304, 'x23'), (31, 18446744005129425020, 'x0'), (42, 18446744005111342936, 'x19'), (43, 18446744005111342984, 'x19'), (44, 18446744005111343056, 'x19'), (45, 18446744005111343064, 'x19')]
START=0xfffffff0084ba590
RETIRED_START=0xfffffff0084ba584
RETIRED_END=0xfffffff0084bbc7c
EXPECTED_CODE='3b1d7179c50caa7b521c8f17597bac4035842796b866492b17ab76762b017cb7'
EXPECTED_SYMBOLS={'return_1': '0xfffffff0084ba6dc', 'return_16': '0xfffffff0084badac', 'return_18': '0xfffffff0084baed8', 'return_2': '0xfffffff0084ba7d8', 'return_23': '0xfffffff0084baff8', 'return_26': '0xfffffff0084bb114', 'return_28': '0xfffffff0084bb1f8', 'return_29': '0xfffffff0084bb2fc', 'return_3': '0xfffffff0084ba8b8', 'return_31': '0xfffffff0084bb3fc', 'return_4': '0xfffffff0084baa00', 'return_42': '0xfffffff0084bb4f8', 'return_43': '0xfffffff0084bb5f4', 'return_44': '0xfffffff0084bb6f0', 'return_45': '0xfffffff0084bb7ec', 'return_5': '0xfffffff0084bab40', 'return_6': '0xfffffff0084bac90', 'trace_1': '0xfffffff0084ba590', 'trace_16': '0xfffffff0084bac94', 'trace_18': '0xfffffff0084badb0', 'trace_2': '0xfffffff0084ba6e0', 'trace_23': '0xfffffff0084baedc', 'trace_26': '0xfffffff0084baffc', 'trace_28': '0xfffffff0084bb118', 'trace_29': '0xfffffff0084bb1fc', 'trace_3': '0xfffffff0084ba7dc', 'trace_31': '0xfffffff0084bb300', 'trace_4': '0xfffffff0084ba8bc', 'trace_42': '0xfffffff0084bb400', 'trace_43': '0xfffffff0084bb4fc', 'trace_44': '0xfffffff0084bb5f8', 'trace_45': '0xfffffff0084bb6f4', 'trace_5': '0xfffffff0084baa04', 'trace_6': '0xfffffff0084bab44', 'trace_hex': '0xfffffff0084bb948', 'trace_small': '0xfffffff0084bb7f0', 'trace_state': '0xfffffff0084e75b0', 'trace_tile': '0xfffffff0084bb8a8'}
def flag_offset(i):return {42:132,43:144,44:152,45:156}[i] if i>=42 else 128+(i-26)*4 if i>=26 else 64+(i-1)*4 if i<=6 else 208+(i-21)*4 if i>=21 else 128+(i-7)*4


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
  elif i==31:
   parts.append('ldar w10,[x9]\ncmp w10,#2\nb.ne done_31\nldr x10,[x9,#264]\ncbz x10,done_31\nldr x10,[x9,#272]\ncbz x10,done_31\nmrs x11,tpidr_el1\ncmp x10,x11\nb.ne done_31\n')
  else:
   parts.append(f'ldar w10,[x9]\ncmp w10,#2\nb.ne done_{i}\nldr x10,[x9,#{280 if i>=42 else 232 if i>=21 else 192 if i>=17 else 8}]\ncmp x10,{bpreg}\nb.ne done_{i}\n')
  if i>=7 and i<=14:
   parts.append(f'ldr x10,[x9,#24]\nmovz x11,#0xfcc8\nmovk x11,#0x0741,lsl #16\nmovk x11,#0xfff0,lsl #32\nmovk x11,#0xffff,lsl #48\ncmp x10,x11\nb.ne done_{i}\nldr x10,[x9,#104]\n')
   if i==7:
    parts.append('cmp x10,x29\nb.ne done_7\nmovz x11,#0x6f80\nmovk x11,#0x0747,lsl #16\nmovk x11,#0xfff0,lsl #32\nmovk x11,#0xffff,lsl #48\ncmp x30,x11\nb.ne done_7\n')
   elif i==13:parts.append('ldr x11,[x29]\nldr x11,[x11]\ncmp x10,x11\nb.ne done_13\nldr x11,[x29,#8]\nmovz x12,#0xff48\nmovk x12,#0x0741,lsl #16\nmovk x12,#0xfff0,lsl #32\nmovk x12,#0xffff,lsl #48\ncmp x11,x12\nb.ne done_13\n')
   else:parts.append(f'ldr x11,[x29]\ncmp x10,x11\nb.ne done_{i}\n')
   if i in (14,15):parts.append(f'movz x11,#0xff34\nmovk x11,#0x0741,lsl #16\nmovk x11,#0xfff0,lsl #32\nmovk x11,#0xffff,lsl #48\ncmp x30,x11\nb.ne done_{i}\n')
   if i==12:parts.append('movz x11,#0xff48\nmovk x11,#0x0741,lsl #16\nmovk x11,#0xfff0,lsl #32\nmovk x11,#0xffff,lsl #48\ncmp x30,x11\nb.ne done_12\n')
  if i==16:
   parts.append('ldr x10,[x9,#104]\nldr x11,[x29]\nldr x11,[x11]\ncmp x10,x11\nb.ne done_16\nldr x11,[x29,#8]\nmovz x12,#0xff34\nmovk x12,#0x0741,lsl #16\nmovk x12,#0xfff0,lsl #32\nmovk x12,#0xffff,lsl #48\ncmp x11,x12\nb.ne done_16\n')
  if 17<=i<=20:
   parts.append('ldr x10,[x9,#200]\n')
   if i==20:parts.append('cmp x10,x29\nb.ne done_20\nmov x11,x30\n')
   else:parts.append(f'ldr x11,[x29]\ncmp x10,x11\nb.ne done_{i}\nldr x11,[x29,#8]\n')
   parts.append(f'movz x12,#0xb568\nmovk x12,#0x0742,lsl #16\nmovk x12,#0xfff0,lsl #32\nmovk x12,#0xffff,lsl #48\ncmp x11,x12\nb.ne done_{i}\n')
   if i==19:parts.append('movz x11,#0x39cc\nmovk x11,#0x0736,lsl #16\nmovk x11,#0xfff0,lsl #32\nmovk x11,#0xffff,lsl #48\ncmp x30,x11\nb.ne done_19\nadd x10,x9,#172\nldar w11,[x10]\ncmp w11,#2\nb.ne done_19\n')
  if 21<=i<=25:
   parts.append('ldr x10,[x9,#240]\n')
   if i==21:parts.append('cmp x10,x29\nb.ne done_21\nmov x11,x30\nldr x10,[x9,#248]\ncmp x1,x10\nb.ne done_21\nldr x10,[x9,#256]\ncmp x2,x10\nb.ne done_21\n')
   else:parts.append(f'ldr x11,[x29]\ncmp x10,x11\nb.ne done_{i}\nldr x11,[x29,#8]\n')
   parts.append(f'movz x12,#0x39cc\nmovk x12,#0x0736,lsl #16\nmovk x12,#0xfff0,lsl #32\nmovk x12,#0xffff,lsl #48\ncmp x11,x12\nb.ne done_{i}\n')
  if i==26:
   parts.append('ldr x10,[x9,#240]\nldr x11,[x29]\ncmp x10,x11\nb.ne done_26\nldr x11,[x29,#8]\nmovz x12,#0x39cc\nmovk x12,#0x0736,lsl #16\nmovk x12,#0xfff0,lsl #32\nmovk x12,#0xffff,lsl #48\ncmp x11,x12\nb.ne done_26\nmovk x12,#0xfdac\nmovk x12,#0x0732,lsl #16\ncmp x30,x12\nb.ne done_26\n')
  if i in (27,28,29,30,32,33):
   parts.append(f'ldr x10,[x9,#264]\ncbz x10,done_{i}\ncmp x10,x29\nb.ne done_{i}\n')
   lr={27:0x6d40,29:0x75a0,30:0x775c,33:0x7394}.get(i)
   if lr is not None:parts.append(f'movz x11,#{lr}\nmovk x11,#0x0732,lsl #16\nmovk x11,#0xfff0,lsl #32\nmovk x11,#0xffff,lsl #48\ncmp x30,x11\nb.ne done_{i}\n')
   if i==29:parts.append('ldr w11,[x9,#136]\ncmp w11,#2\nb.ne done_29\n')
   if i==32:parts.append('movz x11,#0x7200\nmovk x11,#0x0732,lsl #16\nmovk x11,#0xfff0,lsl #32\nmovk x11,#0xffff,lsl #48\ncmp x30,x11\nb.eq sleep_owner_ok\nmovz x11,#0x7274\nmovk x11,#0x0732,lsl #16\nmovk x11,#0xfff0,lsl #32\nmovk x11,#0xffff,lsl #48\ncmp x30,x11\nb.ne done_32\nsleep_owner_ok:\n')
  if i>=42:
   parts.append(f'ldr x10,[x9,#264]\nadd x11,x29,#0x220\ncmp x10,x11\nb.ne done_{i}\nldr x10,[x9,#272]\nmrs x11,tpidr_el1\ncmp x10,x11\nb.ne done_{i}\nldr w10,[x9,#136]\ncmp w10,#2\nb.ne done_{i}\n')
  if i==4:parts.append('ldr x10,[x9,#96]\ncmp x10,x20\nb.ne done_4\nldr x10,[x9,#112]\ncmp x10,x29\nb.ne done_4\n')
  if i==5:parts.append('ldr x10,[x9,#104]\nldr x11,[x29]\ncmp x10,x11\nb.ne done_5\n')
  if i==6:parts.append('ldr x10,[x9,#48]\ncmp x10,x29\nb.ne done_6\n')
  parts.append(f'add x10,x9,#{flag_offset(i)}\nldaxr w11,[x10]\ncbnz w11,clear_{i}\nmov w11,#1\nstlxr w12,w11,[x10]\ncbnz w12,done_{i}\n')
  if i==28:parts.append('str x0,[x9,#280]\n')
  if i==26:parts.append('add x11,sp,#160\nstr x11,[x9,#264]\nmrs x11,tpidr_el1\nstr x11,[x9,#272]\n')
  if i==23:parts.append('str xzr,[x9,#264]\n')
  if i==18:parts.append('str x0,[x9,#232]\nstr x29,[x9,#240]\nstr x1,[x9,#248]\nstr x2,[x9,#256]\n')
  if i==16:parts.append('ldr x11,[x0,#0xa0]\nstr x11,[x9,#192]\nstr x29,[x9,#200]\n')
  if i==2:parts.append('str x8,[x9,#24]\nstr w20,[x9,#32]\nstr x29,[x9,#104]\n')
  if i==3:parts.append('str x1,[x9,#96]\nadd x10,sp,#160\nstr x10,[x9,#112]\nadd x10,x9,#72\n')
  if i==6:parts.append('str w0,[x9,#40]\n')
  parts.append(f'mov w11,#2\nstlr w11,[x10]\nmov x24,#{i}\nbl {"trace_small" if i>=42 else "trace_tile"}\n')
  fields={1:[('x20',0xb620,200),('x0',0xb621,232)],2:[('x8',0xb622,264),('x20',0xb623,296)],6:[('x0',0xb624,328)]}.get(i,[])
  for reg,tag,y in fields:parts.append(f'mov x23,{reg}\nmov x24,#{tag}\nmov x25,#{y}\nbl trace_hex\n')
  if i==8:
   for expr,tag,y in [('mov x23,x20',0xb630,360),('ldr x23,[x21]',0xb631,392),('ldr x23,[x21,#8]',0xb632,424),('ldr w23,[x19,#0x4c]\nlsl x23,x23,#32\nldr w24,[x19,#0x5c]\norr x23,x23,x24',0xb633,456)]:
    # Renderer clobbers saved x19..x25: reload native operands from SAVE before each capture.
    parts.append('ldp x19,x20,[sp,#80]\nldr x21,[sp,#96]\n'+expr+f'\nmov x24,#{tag}\nmov x25,#{y}\nbl trace_hex\n')
  if i==9:
   for expr,tag,y in [('mov w23,w0',0xb634,488),('ldr x23,[sp,#184]',0xb635,520)]:
    parts.append(expr+f'\nmov x24,#{tag}\nmov x25,#{y}\nbl trace_hex\n')
  if i in (16,18,20):
   captures={16:[('ldr x23,[x0,#0xa0]',0xb660,360)],18:[('mov x23,x1',0xb663,456),('mov x23,x2',0xb664,488)],20:[('mov x23,x0',0xb661,392),('ldr w23,[x1,#0x10]\nlsl x23,x23,#32\nldr w24,[x1,#0x18]\norr x23,x23,x24',0xb662,424)]}[i]
   for expr,tag,y in captures:
    if i==20 and tag==0xb662:parts.append('cbz x1,fields_done_20\n')
    parts.append(expr+f'\nmov x24,#{tag}\nmov x25,#{y}\nbl trace_hex\n')
   if i==20:parts.append('fields_done_20:\n')
  if i==21:
   parts.append('cbz x0,map_fields_done\nldr x23,[x0,#8]\nmov x24,#0xb670\nmov x25,#392\nbl trace_hex\nmap_fields_done:\nmrs x23,tpidr_el1\ncbz x23,thread_field_done\nldr w23,[x23,#0x4d8]\nmov x24,#0xb671\nmov x25,#424\nbl trace_hex\nthread_field_done:\n')
  if i==23:
   for expr,tag,y in [('mov w23,w0',0xb672,520),('mov x23,x1',0xb673,680)]:parts.append(expr+f'\nmov x24,#{tag}\nmov x25,#{y}\nbl trace_hex\n')
  if i==27:
   parts.append('ldur x23,[x29,#-0x60]\nmov x24,#0xb680\nmov x25,#392\nbl trace_hex\nmov w23,w0\nmov x24,#0xb682\nmov x25,#552\nbl trace_hex\ncbz w0,lookup_fields_done\nldur x23,[x29,#-0x60]\ncbz x23,lookup_fields_done\nldr x23,[x23,#0x48]\nmov x24,#0xb681\nmov x25,#424\nbl trace_hex\nlookup_fields_done:\n')
  if i==31:
   for expr,tag,y in [('ldr x23,[sp,#168]',0xb683,584),('mov x23,x0',0xb684,616)]:parts.append(expr+f'\nmov x24,#{tag}\nmov x25,#{y}\nbl trace_hex\n')
  if i==32:parts.append('ldr x23,[sp,#168]\nmov x24,#0xb685\nmov x25,#648\nbl trace_hex\n')
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
trace_small:
adr x15,probe_scratch
ldp x9,x10,[x15]
cbz x9,small_done
sub x11,x24,#42
lsl x11,x11,#5
add x11,x11,#544
madd x9,x11,x10,x9
add x9,x9,#704
mov w12,#0xff80
movk w12,#0xff40,lsl #16
cmp x24,#42
b.ne maybe_type
ldr w13,[sp,#8]
cbz w13,flush_red
cmp w13,#1
b.eq flush_color_done
cmp w13,#257
b.lo flush_amber
mov w12,#0x40ff
movk w12,#0xffb0,lsl #16
b flush_color_done
maybe_type:
cmp x24,#43
b.ne flush_color_done
ldp x13,x14,[sp]
cmp x13,x14
b.ls flush_red
ldr w13,[sp,#16]
cmp w13,#3
b.ne flush_color_done
flush_amber:
mov w12,#0xc040
movk w12,#0xffff,lsl #16
b flush_color_done
flush_red:
mov w12,#0x4040
movk w12,#0xffff,lsl #16
flush_color_done:
mov w13,#8
1: stp w12,w12,[x9]
stp w12,w12,[x9,#8]
stp w12,w12,[x9,#16]
stp w12,w12,[x9,#24]
add x9,x9,x10
subs w13,w13,#1
b.ne 1b
small_done: ret
trace_tile:
mov x17,x24
adr x15,probe_scratch
ldp x9,x10,[x15]
cbz x9,tile_done
mov x16,#512
cmp x24,#26
b.lo tile_pre_delete
sub x24,x24,#26
mov x16,#704
b tile_position
tile_pre_delete:
cmp x24,#16
b.lo tile_old_position
sub x24,x24,#16
mov x16,#896
b tile_position
tile_old_position:
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
 b=P.read(BASE/'build.json');raw=(R/b['candidate']['path']).read_bytes();P.verify_bytes(b,raw);B=builder();m=B.macho(raw);out=bytearray(raw);off=B.backed(m,START,len(code));assert START+len(code)<=RETIRED_END and not b['read_flow']['resource_cluster']['gate_diagnostics']['enabled'];assert not any(raw[B.backed(m,int(b['probe']['symbols']['probe_cluster_gate_state'],16)):B.backed(m,int(b['probe']['symbols']['probe_cluster_gate_state'],16))+288]);patches=[];code=bytearray(code)
 retired={c['reason'] for c in b['lean_observation']['changes'] if c['kind']=='restore-native'}
 syms=b['probe']['symbols'];ranges=sorted((int(syms[k],16),int(syms[k+'_replay'],16)+8,k) for k in retired if k in syms and k+'_replay' in syms and RETIRED_START<=int(syms[k],16)<RETIRED_END)
 assert ranges[0][0]==RETIRED_START and ranges[-1][1]==RETIRED_END and all(0<=z[0]-a[1]<=12 for a,z in zip(ranges,ranges[1:]))
 assert all(k in retired or k.endswith('_replay') for k,v in syms.items() if RETIRED_START<=int(v,16)<RETIRED_END)
 for i,site,reg in SITES:
  at=B.backed(m,site);assert not any(p.get('va')==hex(site) for p in b['patches']);target=sy['trace_'+str(i)];ret=sy['return_'+str(i)];code[ret-START:ret-START+4]=B.branch(ret,0xfffffff00741ff7c if i==9 else site+4);after=B.branch(site,target);out[at:at+4]=after;patches.append(dict(va=hex(site),file_offset=at,before=raw[at:at+4].hex(),after=after.hex(),reason='probe_backend_trace_'+str(i)))

 out[off:off+len(code)]=code;return b,bytes(out),patches,bytes(code)

def verify_bytes(b,raw):
 cfg=b['backend_trace'];assert cfg['code_sha256']==EXPECTED_CODE and {k:cfg['symbols'][k] for k in EXPECTED_SYMBOLS}==EXPECTED_SYMBOLS;code=(R/cfg['code_path']).read_bytes();assert hashlib.sha256(code).hexdigest()==cfg['code_sha256'];old,expected,patches,_=derive(code,{k:int(v,16) for k,v in cfg['symbols'].items()});assert raw==expected and b['probe_revision']==71 and b['patches']==old['patches']+patches
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
 a=argparse.ArgumentParser();a.add_argument('--work',type=Path,required=True);a.add_argument('--output',type=Path,required=True);a=a.parse_args();assert not a.work.exists() and not a.output.exists();b=read(BASE/'build.json');raw=(R/b['candidate']['path']).read_bytes();text=source(b,raw);code,sy=compile_code(text,a.work);old,raw,patches,code=derive(code,sy);b=copy.deepcopy(old);(a.work/'trace.bin').write_bytes(code);(a.work/'kernel-entry-probe.macho').write_bytes(raw);(a.work/'probe.S').write_bytes((R/'out/kernel-entry-probe-55-provenance-r3/probe.S').read_bytes());b['candidate']=dict(path=(a.work/'kernel-entry-probe.macho').as_posix(),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw));b['probe_revision']=71;b['patches']+=patches;b['backend_trace']=dict(code_path=(a.work/'trace.bin').as_posix(),code_sha256=hashlib.sha256(code).hexdigest(),source_path=(a.work/'trace.S').as_posix(),symbols={k:hex(v) for k,v in sy.items()},scope='Scoped page-count class, VA-loop selection, pre-DSB and common return; four one-shot 8x8 tiles, no extra barrier; upper isolated HEX rows with background clearing; first scoped APFS device submission only; claim never reused; other backend completion is partial. No object reads after callback.');a.output.parent.mkdir(parents=True,exist_ok=True);verify_bytes(b,raw);a.output.write_text(json.dumps(b,indent=2));print(b['candidate'],len(code))
