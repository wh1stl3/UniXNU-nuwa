"""Exercise exact new hooks, differential native replay and first-request lifecycle."""
import argparse,importlib.util,json,sys,struct,gc
from pathlib import Path
import flush_trace_inputs as M
s=importlib.util.spec_from_file_location('trace_test',M.R/'scripts/test-probe-transparency.py');T=importlib.util.module_from_spec(s);sys.modules[s.name]=T;s.loader.exec_module(T)
a=argparse.ArgumentParser();a.add_argument('--build',type=Path,required=True);a.add_argument('--output',type=Path,required=True);a=a.parse_args();b=M.read(a.build);raw=(M.R/b['candidate']['path']).read_bytes();M.verify_bytes(b,raw)
STATE=int(b['backend_trace']['symbols']['trace_state'],16);PARENT=int(b['probe']['symbols']['probe_resource_strategy_state'],16)
BP=T.STACK+0x2000;CTX=T.STACK+0x3000;APFS=T.STACK+0x5000;CALLER=T.STACK+0x6000;SPEC=T.STACK+0x7000;MEMDEV=T.STACK+0x4000;MD=0xfffffff00741fcc8;checks=[]
patch={int(p['reason'].rsplit('_',1)[1]):p for p in b['patches'] if p['reason'].startswith('probe_backend_trace_')}
def q(data,off,value):struct.pack_into('<Q',data,off,value)
def w(data,off,value):struct.pack_into('<I',data,off,value)
def reg(u,n,value):u.reg_write(getattr(T,'UC_ARM64_REG_X'+str(n)),value)
def one(i,state,*,active=True,pending=True,parent=True,caller=True,foreign=False,frame=True,context=True,video=True,result=0,target=MD,freed=False,lr=True,dirty=False,mapnull=False,thread=True,range_ok=True,entrynull=False,sleeplr=0xfffffff007327200):
 def setup(u):
  u.mem_write(STATE,bytes(state));u.mem_write(PARENT,struct.pack('<QQQQ',CALLER,int(active),2 if pending else 0,1))
  reg(u,29,APFS);u.mem_write(APFS,struct.pack('<QQ',T.STACK+0x5800,0xfffffff00746e574 if caller else 0xfffffff00746e578));u.mem_write(T.STACK+0x5800,struct.pack('<Q',CALLER if parent else CALLER+16));reg(u,20,BP+(16 if foreign else 0));reg(u,19,BP+(16 if foreign else 0));reg(u,0,BP+(16 if foreign else 0));reg(u,1,CTX)
  if i==1:reg(u,0,CTX)
  if i==2:reg(u,8,target);reg(u,20,0x07001234);reg(u,29,SPEC)
  if i==4:reg(u,20,CTX if context else CTX+16);reg(u,29,T.STACK+0x7ff0 if frame else T.STACK+0x7fe0)
  if i==5:reg(u,29,MEMDEV);u.mem_write(MEMDEV,struct.pack('<Q',SPEC if frame else SPEC+16))
  if i==6:reg(u,0,result);reg(u,29,APFS if frame else APFS+16)
  if i>=7:
   reg(u,29,SPEC if i==7 else MEMDEV);reg(u,30,0xfffffff007476f80 if lr else 0xfffffff007476f84)
   if i==7 and not frame:reg(u,29,SPEC+16)
   u.mem_write(MEMDEV,struct.pack('<Q',SPEC if frame else SPEC+16))
   reg(u,20,0x12345000);reg(u,21,CTX)
   u.mem_write(CTX,struct.pack('<QII',0x8c5000,0x12345,5))
   u.mem_write(BP+0x4c,struct.pack('<I',0x401));u.mem_write(BP+0x5c,struct.pack('<I',0x4000))
   if i==9:reg(u,0,result)
   u.mem_write(T.STACK+0x8008,struct.pack('<Q',0xfffffff061234000))
  if i in (11,12,13):
   reg(u,29,MEMDEV if i!=13 else T.STACK+0x4800)
   u.mem_write(MEMDEV,struct.pack('<Q',SPEC if frame else SPEC+16))
   reg(u,30,0xfffffff00741ff48 if lr else 0xfffffff00741ff4c)
   if i==11:reg(u,0,result)
   if i==13:
    u.mem_write(T.STACK+0x4800,struct.pack('<QQ',MEMDEV,0xfffffff00741ff48 if lr else 0xfffffff00741ff4c))
    u.mem_write(BP+0x80,struct.pack('<Q',0xfffffff005198638));u.mem_write(BP+0xd0,struct.pack('<Q',CTX))
  if i in (14,15):reg(u,30,0xfffffff00741ff34 if lr else 0xfffffff00741ff38)
  if i>=16:
   uf=T.STACK+0x4800;vf=T.STACK+0x4a00
   u.mem_write(uf,struct.pack('<QQ',MEMDEV,0xfffffff00741ff34 if lr else 0xfffffff00741ff38));u.mem_write(vf,struct.pack('<QQ',uf if frame else uf+16,0xfffffff00742b568 if lr else 0xfffffff00742b56c))
   u.mem_write(BP+0xa0,struct.pack('<Q',CTX));u.mem_write(CTX+0x10,struct.pack('<I',2));u.mem_write(CTX+0x18,struct.pack('<I',1))
   reg(u,29,uf if i in (16,20) else vf)
   if i==16:reg(u,0,BP+(16 if foreign else 0))
   elif i==20:
    reg(u,0,CALLER);reg(u,1,CTX+(16 if foreign else 0));reg(u,29,uf if frame else uf+16);reg(u,30,0xfffffff00742b568 if lr else 0xfffffff00742b56c)
   else:
    reg(u,20,CTX+(16 if foreign else 0));reg(u,1,0xfffffff10edb2000);reg(u,2,0xfffffff10edb3000)
    if i==18:reg(u,0,CALLER)
    if i==19:reg(u,30,0xfffffff0073639cc if lr else 0xfffffff0073639d0)
  if i>=21:
   mf=T.STACK+0x4c00;vf=T.STACK+0x4a00;mp=0 if mapnull else CALLER
   u.mem_write(mf,struct.pack('<QQ',vf if frame else vf+16,0xfffffff0073639cc if lr else 0xfffffff0073639d0))
   reg(u,29,(vf if frame else vf+16) if i==21 else mf);reg(u,30,0xfffffff0073639cc if lr else 0xfffffff0073639d0)
   reg(u,0,result if i==23 else mp+(16 if foreign else 0));reg(u,23,mp+(16 if foreign else 0))
   reg(u,1,0x123456789a if i==23 else 0xfffffff10edb2000+(4096 if not range_ok else 0));reg(u,2,0xfffffff10edb3000)
   u.mem_write(CALLER+8,struct.pack('<Q',0x1234004a0000));u.mem_write(T.STACK+0x14d8,struct.pack('<I',0x1234))
   u.reg_write(T.UC_ARM64_REG_TPIDR_EL1,T.STACK+0x1000 if thread else 0)
  if i>=26:
   df=T.STACK+0x7ff0;mf=T.STACK+0x4c00;vf=T.STACK+0x4a00;ep=0 if entrynull else T.STACK+0x1800
   u.mem_write(mf,struct.pack('<QQ',vf if frame else vf+16,0xfffffff0073639cc))
   u.mem_write(df-0x60,struct.pack('<Q',ep));u.mem_write(T.STACK+0x1848,struct.pack('<Q',0x0002000112345678))
   reg(u,29,mf if i==26 else df if frame else df+16);reg(u,23,CALLER+(16 if foreign else 0));reg(u,0,CALLER+(16 if foreign else 0))
   reg(u,30,{26:0xfffffff00732fdac,27:0xfffffff007326d40,28:0x1234,29:0xfffffff0073275a0,30:0xfffffff00732775c,31:0xfffffff00795a920,32:sleeplr,33:0xfffffff007327394}.get(i,0)+(0 if lr else 4))
   if i>=27:u.reg_write(T.UC_ARM64_REG_SP,T.STACK+0x7e50)
   if i==27:reg(u,0,result)
   if i==31:reg(u,0,0xdeadbeef);u.reg_write(T.UC_ARM64_REG_TPIDR_EL1,T.STACK+0x1000+(16 if foreign else 0) if thread else 0)
  if i>=42:
   reg(u,19,CALLER+(16 if foreign else 0));reg(u,29,df-0x220+(16 if not frame else 0));u.reg_write(T.UC_ARM64_REG_TPIDR_EL1,T.STACK+0x1000 if thread else 0)
  if i==42:reg(u,10,result)
  if i==43:reg(u,9,1 if result==0 else 2);reg(u,10,1);reg(u,11,result)
  if dirty:
   for y in range(200,681,32):u.mem_write(T.FB+y*T.ROW+256*4,bytes([0xa5])*(T.ROW*20))
  if freed:
   u.mem_unmap(BP,4096);u.mem_unmap(CTX,4096)
 c=dict(flag=0,video=video,nzcv=0xa0000000,x0=BP,seed_simd=True,setup=setup)
 ref,expected,nativewrites=T.machine(raw,b,patch[i],c,True);c['native_pc']=expected['pc'];u,actual,writes=T.machine(raw,b,patch[i],c);assert actual==expected,(i,actual,expected)
 for addr,n in nativewrites:assert bytes(ref.mem_read(addr,n))==bytes(u.mem_read(addr,n))
 assert bytes(ref.mem_read(T.STACK+0x8000,0x8000))==bytes(u.mem_read(T.STACK+0x8000,0x8000))
 fb=[(addr,n) for addr,n in writes if T.FB<=addr<T.FB+0x1200000]
 for addr,n in fb:
  y,x=divmod(addr-T.FB,T.ROW);x//=4;assert ((128<=x and x+n//4<=160 and 416<=y<720) or (176<=x and x+n//4<=208 and 384<=y<752)) or (224<=x and x+n//4<=256 and 384<=y<688) or (256<=x and x+n//4<=736 and any(v<=y<v+20 for v in (200,232,264,296,328,360,392,424,456,488,520,552,584,616,648,680)))
 allowed=lambda addr,n:STATE<=addr and addr+n<=STATE+288 or T.STACK+(0x7e50 if i>=27 else 0x8000)-176<=addr and addr+n<=T.STACK+(0x7e50 if i>=27 else 0x8000) or (addr,n) in nativewrites or T.FB<=addr and addr+n<=T.FB+0x1200000
 assert all(allowed(addr,n) for addr,n in writes),'Unexpected writes'
 if fb and i>=42:
  assert sum(n for _,n in fb)==256
  if i in (42,43):
   if i==42:color=0xffff4040 if result==0 else 0xff40ff80 if result==1 else 0xffffc040 if result<257 else 0xffb040ff
   else:color=0xffff4040 if result==0 else 0xffffc040 if result==3 else 0xff40ff80
   assert int.from_bytes(u.mem_read(T.FB+(544+(i-42)*32)*T.ROW+704,4),'little')==color
  for addr,n in fb:
   y,x=divmod(addr-T.FB,T.ROW);assert 544+32*(i-42)<=y<552+32*(i-42) and 704<=x and x+n<=736
 if fb:
  fields={1:[(0xb620,BP,200),(0xb621,CTX,232)],2:[(0xb622,target,264),(0xb623,0x07001234,296)],6:[(0xb624,result,328)],8:[(0xb630,0x12345000,360),(0xb631,0x8c5000,392),(0xb632,0x500012345,424),(0xb633,0x40100004000,456)],9:[(0xb634,result & 0xffffffff,488),(0xb635,0xfffffff061234000,520)],11:[(0xb640,result & 0xffffffff,552)],13:[(0xb641,0x401,584),(0xb642,0xfffffff005198638,616),(0xb643,CTX,648)],14:[(0xb650,0x401,680)]}.get(i,[])
  fields += {16:[(0xb660,CTX,360)],18:[(0xb663,0xfffffff10edb2000,456),(0xb664,0xfffffff10edb3000,488)],20:[(0xb661,CALLER,392),(0xb662,0x200000001,424)]}.get(i,[])
  fields += {21:([(0xb670,0x1234004a0000,392)] if not mapnull else [])+([(0xb671,0x1234,424)] if thread else []),23:[(0xb672,result&0xffffffff,520),(0xb673,0x123456789a,680)]}.get(i,[])
  fields += {27:[(0xb680,0 if entrynull else T.STACK+0x1800,392),(0xb682,result&0xffffffff,552)]+([(0xb681,0x0002000112345678,424)] if result&0xffffffff and not entrynull else []),31:[(0xb683,0xfffffff00795a920,584),(0xb684,0xdeadbeef,616)],32:[(0xb685,sleeplr,648)]}.get(i,[])
  font=int(b['backend_trace']['symbols']['hex_font'],16)
  for tag,value,y in fields:
   for pos,ch in enumerate(f'{tag:04x}{value:016x}'):
    glyph=struct.unpack('<I',u.mem_read(font+int(ch,16)*4,4))[0]
    for row in range(5):
     for col in range(4):
      pixel=struct.unpack('<I',u.mem_read(T.FB+(y+row*4)*T.ROW+(256+pos*24+col*4)*4,4))[0]
      assert pixel==(0xffffffff if (glyph>>(19-row*4-col))&1 else 0),(i,tag,ch,row,col,pixel)
  for tag,value,y in fields:
   # Every inter-glyph gap must be cleared even on a pre-populated firmware background.
   for pos in range(20):
    assert bytes(u.mem_read(T.FB+y*T.ROW+(256+pos*24+16)*4,8*4))==bytes(8*4)
 if fb and i==10:
  assert int.from_bytes(u.mem_read(T.FB+704*T.ROW+128*4,4),'little')==0xff40ff80
  assert int.from_bytes(u.mem_read(T.FB+704*T.ROW+144*4,4),'little')==0xff40c0ff
 if fb and i==14:assert int.from_bytes(u.mem_read(T.FB+704*T.ROW+192*4,4),'little')==0xff40ff80
 out=bytes(u.mem_read(STATE,288));del ref,u;gc.collect();return out,len(fb)
def done(name):checks.append(dict(name=name,passed=True))
for name,kw in [('inactive',dict(active=False)),('parent-call-inactive',dict(pending=False)),('foreign-frame',dict(parent=False)),('foreign-callsite',dict(caller=False))]:
 st,n=one(1,bytes(288),**kw);assert st==bytes(288) and n==0;done(name)
for claim in (1,2,3):
 st=bytearray(288);w(st,0,claim);out,n=one(1,st);assert out==st and n==0;done('claim-not-reused:'+str(claim))
for i in range(2,7):
 st,n=one(i,bytes(288));assert st==bytes(288) and not n;done('unselected-stage:'+str(i))
for video in (False,True):
 for result in (0,5,2):
  st=bytes(288)
  for i in (1,2,3,4,5,6):
   st,n=one(i,st,video=video,result=result,freed=i in (4,5,6));assert bool(n)==video
  assert struct.unpack_from('<I',st)[0]==3 and struct.unpack_from('<Q',st,8)[0]==BP
  assert struct.unpack_from('<Q',st,16)[0]==CTX and struct.unpack_from('<Q',st,24)[0]==MD and struct.unpack_from('<I',st,32)[0]==0x07001234
  assert struct.unpack_from('<I',st,40)[0]==result and [struct.unpack_from('<I',st,64+4*i)[0] for i in range(6)]==[2]*6
  out,n=one(1,st);assert out==st and not n;done('native-memory-backend-chain:'+str((video,result)))
selected,_=one(1,bytes(288));selected,_=one(2,selected);selected,_=one(3,selected)
for i in (2,3,4,5,6):
 st,n=one(i,selected,foreign=True);assert st==selected and not n;done('foreign-bp:'+str(i))
for i,kw in ((4,dict(context=False)),(4,dict(frame=False)),(5,dict(frame=False)),(6,dict(frame=False))):
 st,n=one(i,selected,**kw);assert st==selected and not n;done('wrong-owner:'+str(i))
for order in ((1,2,6,3,4),(1,2,3,4,6)):
 st=bytes(288)
 for i in order:st,_=one(i,st,target=0xfffffff007000000)
 assert struct.unpack_from('<I',st)[0]==3 and struct.unpack_from('<I',st,80)[0]==0;done('other-backend-partial:'+str(order))
# A missed frame or incomplete completion remains open, never silently counted complete.
st=bytes(288)
for i in (1,2,6):st,_=one(i,st)
assert struct.unpack_from('<I',st)[0]==3 and struct.unpack_from('<I',st,80)[0]==0
for i in (3,4,5):
 out,n=one(i,st);assert out==st and not n
done('missing-sync-completion-freezes-partial-no-pointer-reuse')
# Native request object/context pages are unmapped in all callback-return tests above.
# A repeated stage does not repaint or overwrite recorded fields.
st,n=one(2,selected,target=0xfffffff007000000);assert st==selected and n==0;done('first-target-frozen')
# New UPL stages use pointer values only after unlock; ownership and call frame gates are exercised separately.
base,_=one(1,bytes(288));base,_=one(2,base)
base16,_=one(16,base)
for i in (16,18):
 st0=bytearray(base if i==16 else base16)
 if i==19:w(st0,172,2)
 for video in (False,True):
  st,n=one(i,st0,video=video,dirty=True);assert bool(n)==video and struct.unpack_from('<I',st,128+(i-7)*4)[0]==2;done('upl-native-and-fields:'+str((i,video)))
 for kw in (dict(foreign=True),dict(frame=False),dict(lr=False)):
  st,n=one(i,st0,**kw);assert st==st0 and not n;done('upl-owner:'+str((i,kw)))
 st,n=one(i,bytes(288));assert st==bytes(288) and not n;done('upl-unselected:'+str(i))
 st,_=one(i,st0);out,n=one(i,st);assert out==st and not n;done('upl-first-only:'+str(i))
base18,_=one(18,base16)
# Preserve outer delete return and disarm the panic scope there.
for video in (False,True):
 for result in (0,5,0x100000000):
  st=bytearray(base18);q(st,264,0x1234);out,n=one(23,st,video=video,result=result,dirty=True);assert bool(n)==video and struct.unpack_from('<Q',out,264)[0]==0;done('delete-return-disarms:'+str((video,result)))
base26,_=one(26,base18)
for i in (26,28,29,31,42,43,44,45):
 st0=bytearray(base18 if i==26 else base26)
 if i>=42:st0=bytearray(one(28,base26)[0])
 if i==29:w(st0,136,2)
 for video in (False,True):
  for result in ((0,1,2,256,257) if i==42 else (0,1,3) if i==43 else (0,)):
   st,n=one(i,st0,video=video,result=result,dirty=True);assert bool(n)==video and struct.unpack_from('<I',st,M.flag_offset(i))[0]==2;done('delete-native-and-fields:'+str((i,video,result)))
 for kw in ([dict(foreign=True),dict(frame=False),dict(thread=False)] if i>=42 else [dict(foreign=True)] if i==31 else [dict(foreign=True),dict(frame=False)]+([] if i==28 else [dict(lr=False)])):
  st,n=one(i,st0,**kw);assert st==st0 and not n;done('delete-owner:'+str((i,kw)))
 st,n=one(i,bytes(288));assert st==bytes(288) and not n;done('delete-unselected:'+str(i))
 st=bytearray(st0);w(st,0,3);out,n=one(i,st);assert out==st and not n;done('delete-frozen:'+str(i))
 st,_=one(i,st0);out,n=one(i,st);assert out==st and not n;done('delete-first-only:'+str(i))
for field in (264,272):
 st=bytearray(base26);q(st,field,0);out,n=one(31,st);assert out==st and not n;done('panic-no-active-owner:'+str(field))
st,n=one(29,base26);assert st==base26 and not n;done('pmap-join-without-call-not-return')
# Every changed native site over67 is either retired or newly added; common stubs retain semantics.
import tlb_trace_inputs as OLD
prior=M.read(M.R/'reports/kernel-entry-probe/2026-10-31-probe70-tlb-r1/build.json');previous=(M.R/prior['candidate']['path']).read_bytes();OLD.verify_bytes(prior,previous)
B=M.builder();parsed=B.macho(raw);allowed=[(B.backed(parsed,M.START),B.backed(parsed,M.RETIRED_END-1)+1)]
for site in {x[1] for x in M.SITES}|{x[1] for x in OLD.SITES}:allowed.append((B.backed(parsed,site),B.backed(parsed,site)+4))
for lo,hi in sorted(allowed):
 assert raw[:lo]==previous[:lo];raw=raw[:lo]+previous[lo:hi]+raw[hi:]
assert raw==previous;raw=(M.R/b['candidate']['path']).read_bytes();done('delta-over70-retire-four-add-four-only')
# Verify no incoming direct branch from live code reaches the recycled observer area.
old=M.read(M.BASE/'build.json');original=(M.R/old['candidate']['path']).read_bytes();B=M.builder();parsed=B.macho(original);incoming=[]
for segment in parsed['segments']:
 if not struct.unpack_from('<I',original,segment['command_offset']+60)[0]&4:continue
 data=original[segment['fileoff']:segment['fileoff']+segment['filesize']];data=data[:len(data)//4*4]
 for j,(word,) in enumerate(struct.iter_unpack('<I',data)):
  if word&0x7c000000 != 0x14000000:continue
  pc=segment['va']+4*j;imm=word&0x3ffffff;imm=imm-(1<<26) if imm&(1<<25) else imm;target=pc+4*imm
  if M.START<=target<M.START+len((M.R/b['backend_trace']['code_path']).read_bytes()) and not M.RETIRED_START<=pc<M.RETIRED_END:incoming.append(hex(pc))
assert not incoming,incoming
done('recycled-code-has-no-live-direct-entry')
a.output.write_text(json.dumps(dict(candidate_sha256=b['candidate']['sha256'],checks=checks,limits='Exact hook replay and synthetic event schedules. No real APFS, backend IO or hardware timing proof. Generic backend completion remains partial.'),indent=2));print(len(checks),'passed')
