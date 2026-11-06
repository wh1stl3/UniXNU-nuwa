"""CHECK9 zero-draw control: 73 inherited cases + 8 zero-draw cases.

The inherited harness intercepts `draw` at its symbol address, so those 73
cases cannot prove the zero-draw property by themselves. The new cases verify
it at the packaged-byte level AND by really executing the packaged draw body
with the interception removed, asserting zero memory writes.
"""
import argparse, hashlib, json, runpy, sys
from pathlib import Path
import exec_carrier_model as H
from exec_carrier_model import *

p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args()
proof=json.loads((a.work/'kernel-proof.json').read_bytes())
delta=proof.get('check6_delta') or proof['check5_delta']
d9=proof['check9_delta']
assert delta['parent_kernel_sha256']==H.EXPECTED
assert hashlib.sha256((a.work/'kernel.macho').read_bytes()).hexdigest()==proof['kernel_sha256']
H.EXPECTED=proof['kernel_sha256']
c=Carrier(a.work);out=a.output_dir;out.mkdir(parents=True,exist_ok=False)
ROOT=t.R
CHECK5=ROOT/'out/ufs-check-5-r1-qualified'
RET=bytes.fromhex('c0035fd6');NOP=bytes.fromhex('1f2003d5')

# ---------------- 73 inherited machine cases, unchanged ----------------
rows=[];state=proof['targets']['coarse_state'];NEW=MEM+0x3000;TASK=MEM+0x22000;SAVED=MEM+0x24000
for name,active,foreign,error,newptr,repeat in [
 ('success',True,False,0,NEW,False),('success_old_return_first',True,False,0,NEW,False),
 ('error',True,False,13,NEW,False),('foreign',True,True,0,NEW,False),
 ('inactive',False,False,0,NEW,False),('no_new_thread',True,False,0,0,False),
 ('already_recorded',True,False,0,NEW,True)]:
 m=Machine(c);release_site=BASE+0x769d230;init_site=proof['targets']['init_loaded_resume']-4
 m.put(state+104,THREAD if active else 0);m.put(state+256,(1<<9) if repeat else 0,4)
 m.put(IMG+0x2b8,newptr);m.u.reg_write(UC_ARM64_REG_TPIDR_EL1,THREAD+16 if foreign else THREAD)
 values=[0x7000+i*16 for i in range(31)];values[0]=TASK;values[1]=2;values[19]=IMG;values[24]=error
 for i,v in enumerate(values):m.x(i,v)
 vectors=[(0x123456789abcdef0<<64)+i for i in range(32)]
 for i,v in enumerate(vectors):m.u.reg_write(getattr(U.arm64_const,'UC_ARM64_REG_Q'+str(i)),v)
 m.u.reg_write(UC_ARM64_REG_NZCV,0xa0000000)
 m.callbacks[c.sy['_task_clear_return_wait']]=lambda:m.stop('native release entry')
 m.run(release_site)
 expected=values[:];expected[30]=BASE+0x769d234
 assert [m.x(i) for i in range(31)]==expected
 assert [m.u.reg_read(getattr(U.arm64_const,'UC_ARM64_REG_Q'+str(i))) for i in range(32)]==vectors
 assert m.u.reg_read(UC_ARM64_REG_SP)==STACK and m.u.reg_read(UC_ARM64_REG_NZCV)==0xa0000000
 armed=name.startswith('success');assert m.get(state+32)==(NEW if armed else 0)
 if armed:
  if name=='success_old_return_first':
   m.stopped=None;m.callbacks[proof['targets']['init_loaded_resume']]=lambda:m.stop('early old return')
   m.run(init_site);assert m.get(state+32)==NEW
  m.stopped=None;m.x(21,SAVED);m.x(3,THREAD)
  m.callbacks[proof['targets']['el0_resume']]=lambda:m.stop('EL0 observer resume')
  m.run(BASE+0x73c3864);assert [14,1] not in m.draws and m.get(state+32)==NEW
  m.stopped=None;m.u.reg_write(UC_ARM64_REG_TPIDR_EL1,NEW);m.x(3,NEW)
  m.run(BASE+0x73c3864);assert m.draws.count([14,1])==1 and m.get(state+32)==0
  m.stopped=None;m.u.reg_write(UC_ARM64_REG_TPIDR_EL1,THREAD)
  m.callbacks[proof['targets']['init_loaded_resume']]=lambda:m.stop('late old return')
  m.run(init_site);assert m.get(state+32)==0
  m.stopped=None;m.u.reg_write(UC_ARM64_REG_TPIDR_EL1,NEW);m.x(21,SAVED);m.x(3,NEW)
  m.run(BASE+0x73c3864);assert m.draws.count([14,1])==1
 rows.append(m.record(name))
write_report(out/'target-lifetime.json',c,rows,'Actual CHECK9 packaged kernel; inherited CHECK5 release-hook cases unchanged. Model intercepts draw, so zero-draw property is proven separately below.')

rows=[];CPU=MEM+0x28000;USER=MEM+0x3d000
for name,mode,debug,wait in [('native_restore',0,False,False),('kernel_mode',5,False,False),('recount_wait',0,False,True),('debug_restore',0,True,False)]:
 m=Machine(c);m.put(state+104,THREAD);m.put(IMG+0x2b8,NEW);m.x(19,IMG);m.x(24,0)
 m.callbacks[c.sy['_task_clear_return_wait']]=lambda:m.stop('native release entry')
 m.run(BASE+0x769d230);assert m.get(state+32)==NEW
 m.stopped=None;m.u.reg_write(UC_ARM64_REG_TPIDR_EL1,NEW);m.x(21,SAVED);m.x(3,NEW)
 m.put(NEW+0x1c8,CPU);m.put(NEW+0x140,0x1234 if debug else 0);m.put(SAVED+0x110,mode,4)
 for i in range(31):m.put(SAVED+8+i*8,0x100+i)
 m.put(SAVED+0x108,USER);m.put(SAVED+0x100,MEM+0x35000)
 m.stub('_recount_enter_user',lambda:m.stop('recount boundary') if wait else m.ret())
 m.stub('_arm_debug_set',lambda:(m.events.append('debug restore boundary'),m.ret()))
 m.callbacks[BASE+0x73c3994]=lambda:m.stop('before ERET')
 m.run(BASE+0x73c3864);assert ([14,1] in m.draws)==(mode==0)
 if wait:assert m.stopped=='recount boundary' and BASE+0x73c3994 not in m.visits
 else:
  assert m.stopped=='before ERET' and m.u.reg_read(UC_ARM64_REG_ELR_EL1)==USER
  assert m.u.cpr_read(3,0,4,0,0)==mode and m.u.reg_read(UC_ARM64_REG_SP)==MEM+0x35000
  for i in range(31):
   if i!=18:assert m.x(i)==0x100+i
 assert USER not in m.visits
 rows.append(m.record(name))
write_report(out/'native-el0-restore.json',c,rows,'Real register restore after CHECK9 new-thread publication; inherited CHECK5 cases unchanged.')

# ---------------- 8 new zero-draw cases ----------------
raw=(a.work/'kernel.macho').read_bytes()
check5=(CHECK5/'kernel.macho').read_bytes()
c5=json.loads((CHECK5/'kernel-proof.json').read_bytes())
lo,hi=d9['whole_kernel_diff_vs_check5']['file_range']
body=raw[lo:hi]
rows=[]

# 1. Packaged draw body is exactly ret + NOP padding.
assert body[:4]==RET and body[4:]==NOP*((len(body)//4)-1)
assert len(body)==d9['draw_body_bytes']==220
assert d9['draw_body_hex']==body.hex()
rows.append(dict(name='draw_body_is_ret_plus_nops',first_word=RET.hex(),nops=len(body)//4-1,
                 body_bytes=len(body),passed=True))

# 2. Whole-kernel single-variable property.
diff=[i for i,(x,y) in enumerate(zip(raw,check5)) if x!=y]
assert len(raw)==len(check5) and diff and all(lo<=i<hi for i in diff)
assert raw[:lo]==check5[:lo] and raw[hi:]==check5[hi:]
rows.append(dict(name='whole_kernel_diff_only_inside_draw',differing_bytes=len(diff),
                 draw_body_file_range=[lo,hi],all_within=True,passed=True))

# 3. Symbols, repair patches, source and inherited defect all retained.
assert proof['symbols']['draw']==c5['symbols']['draw']==0xfffffff0084bb680
assert proof['symbols']['font']==c5['symbols']['font']==0xfffffff0084bb75c
assert proof['symbols']['coarse_release_before']==c5['symbols']['coarse_release_before']
assert proof['symbols']['phase_record']==c5['symbols']['phase_record']
assert any(x['symbol']=='coarse_release_before' for x in delta['callers'])
assert (ROOT/'package/kernel-mainline/CoarseStages-ufs-check9-r1.S').read_bytes()==(ROOT/'package/kernel-mainline/CoarseStages-ufs-check5-r1.S').read_bytes()
assert proof['repair_patches']['inherited_read_return_chain_defect']['x30_installed_by_coarse_read_before']=='0xfffffff00769bfa4'
rows.append(dict(name='symbol_addresses_and_repair_patches_preserved',
                 draw=hex(proof['symbols']['draw']),font=hex(proof['symbols']['font']),
                 source_equal_check5=True,repair_patches=list(proof['repair_patches']),passed=True))

# 4/5/6. Really execute the packaged draw body with interception REMOVED:
#        zero memory writes, one instruction, full context preserved.
draw_addr=proof['symbols']['draw']
for w0,w1 in ((0,0),(3,0xc8a5),(0xffffffff,0x5a5a5a5a)):
 m=Machine(c)
 del m.callbacks[draw_addr]
 writes=[]
 m.u.hook_add(U.UC_HOOK_MEM_WRITE,lambda u,access,addr,size,value,data:writes.append((hex(addr),size,value)))
 m.x(30,SENTINEL);m.x(0,w0);m.x(1,w1)
 m.u.reg_write(UC_ARM64_REG_NZCV,0xa0000000)
 before=[m.x(i) for i in range(31)]
 m.run(draw_addr)
 assert m.stopped=='return' and writes==[],(w0,w1,m.stopped,writes)
 assert m.visits[draw_addr]==1 and (draw_addr+4) not in m.visits
 assert [m.x(i) for i in range(31)]==before
 assert m.u.reg_read(UC_ARM64_REG_SP)==STACK and m.u.reg_read(UC_ARM64_REG_NZCV)==0xa0000000
 rows.append(dict(name='real_draw_zero_writes_%#x'%w0,w0=w0,w1=w1,memory_writes=len(writes),
                  executed_instructions=sum(m.visits.values()),first_instruction_only=True,
                  context_preserved=True,passed=True))

# 7. Every `bl draw` callsite is still present (byte identical to CHECK5).
def bl_to(code,base,target):
 n=0
 for i in range(0,len(code)-3,4):
  w=int.from_bytes(code[i:i+4],'little')
  if w&0xfc000000!=0x94000000:continue
  imm=w&0x3ffffff;imm=imm-(1<<26) if imm&(1<<25) else imm
  if base+i+4*imm==target:n+=1
 return n
cave_start=delta['observer_file_offset']
# BL immediates are PC-relative in VIRTUAL address space, not file offsets.
cave=raw[cave_start:cave_start+proof['code_bytes']]
cave5=check5[cave_start:cave_start+proof['code_bytes']]
n9=bl_to(cave,t.START,draw_addr)
n5=bl_to(cave5,t.START,c5['symbols']['draw'])
assert n9==n5 and n9>0,(n9,n5)
rows.append(dict(name='bl_draw_callsites_preserved',check9=n9,check5=n5,passed=True))

# 8. CHECK8's extra hooks and any other new observer bodies are absent.
assert not any(k.startswith(('c8_','c7_','c6_')) for k in proof['symbols'])
assert proof['code_bytes']==c5['code_bytes']==4620
rows.append(dict(name='no_extra_observer_bodies',code_bytes=proof['code_bytes'],
                 check5_code_bytes=c5['code_bytes'],passed=True))

write_report(out/'check9-zero-draw.json',c,rows,
 'Packaged-byte and real-execution verification of the zero-draw control: draw body is ret+nops, no memory write, no dsb, all other kernel bytes and symbols identical to qualified CHECK5, all bl draw callsites and repair patches retained. Unicorn only; no device.')

executed=[]
def regression(name,argv,replace=None):
 source=t.R/'scripts'/name;text=source.read_text();original=hashlib.sha256(source.read_bytes()).hexdigest()
 if replace:
  pairs=replace if isinstance(replace,list) else [replace]
  for before,after in pairs:
   assert text.count(before)==1,(name,'adaptation anchor not unique',before[:60])
   text=text.replace(before,after)
  (out/('adapted-'+name)).write_text(text)
 sys.argv=[str(source),*map(str,argv)]
 exec(compile(text,str(source),'exec'),{'__name__':'__main__','__file__':str(source)})
 executed.append(dict(source=name,sha256=original,adaptation=replace,executed_text_sha256=hashlib.sha256(text.encode()).hexdigest()))
regression('test-exec-native-helpers.py',['--work',a.work,'--output',out/'native-helpers.json'])
regression('test-exec-native-continuation.py',['--work',a.work,'--output',out/'native-continuation.json'])
regression('test-kmain16-stages.py',['--work',a.work,'--exec-return-limit','2'],
 [("if name=='init_loaded':assert struct.unpack('<Q',u.mem_read(latch+32,8))[0]==thread",
   "if name=='init_loaded':assert struct.unpack('<Q',u.mem_read(latch+32,8))[0]==0"),
  ("assert list(pixels)==[0xffffffff if font[int(digit,16)]&(1<<(19-(y//4)*4-x//4)) else 0 for x in range(16)]",
   "assert list(pixels)==[0]*16"),
  ("extra_field_pixels=True,scope='Unicorn machine-code replay and rendering; no physical stage claim'",
   "extra_field_pixels=False,zero_draw_framebuffer_untouched=True,scope='CHECK9 zero-draw adaptation: real packaged draw body executed; framebuffer must stay untouched. Unicorn only, no device.'"),
  ("assert writes\nfor row in range(1236)",
   "assert not writes\nfor row in range(1236)"),
  ("legacy_a_rectangle_untouched=True,short_stride_rejected=True,all_21_rows_checked=True",
   "legacy_a_rectangle_untouched=True,short_stride_rejected=None,all_21_rows_checked=True,zero_draw_no_pixel_writes=True,note='CHECK9 zero-draw: draw is a single ret; no pixel write at any stride, so short-stride rejection is not exercised'")])
regression('test-kmain4-r1-mainline.py',['--work',a.work],
 [("assert list(pixels) == expected, (row, column, y)",
   "assert list(pixels) == [0]*16, (row, column, y)"),
  ("tests.append('actual FB00-FB07 pixels')",
   "tests.append('actual draw body: framebuffer untouched (zero-draw control)')")])
(out/'regression-binding.json').write_text(json.dumps(dict(kernel_sha256=proof['kernel_sha256'],passed=True,executed=executed,
 harness_sha256=hashlib.sha256(Path(H.__file__).read_bytes()).hexdigest(),expected_hash_rebound_from=proof['check5_delta']['parent_kernel_sha256']),indent=2)+'\n')
print('PASS CHECK9 73 inherited cases + 8 zero-draw cases (81 total)')
