"""Exercise exact new hooks, differential native replay and first-request lifecycle."""
import argparse,importlib.util,json,sys,struct,gc
from pathlib import Path
import backend_trace_inputs as M
s=importlib.util.spec_from_file_location('trace_test',M.R/'scripts/test-probe-transparency.py');T=importlib.util.module_from_spec(s);sys.modules[s.name]=T;s.loader.exec_module(T)
a=argparse.ArgumentParser();a.add_argument('--build',type=Path,required=True);a.add_argument('--output',type=Path,required=True);a=a.parse_args();b=M.read(a.build);raw=(M.R/b['candidate']['path']).read_bytes();M.verify_bytes(b,raw)
STATE=int(b['backend_trace']['symbols']['trace_state'],16);PARENT=int(b['probe']['symbols']['probe_resource_strategy_state'],16)
BP=T.STACK+0x2000;CTX=T.STACK+0x3000;APFS=T.STACK+0x5000;CALLER=T.STACK+0x6000;SPEC=T.STACK+0x7000;MEMDEV=T.STACK+0x4000;MD=0xfffffff00741fcc8;checks=[]
patch={int(p['reason'].rsplit('_',1)[1]):p for p in b['patches'] if p['reason'].startswith('probe_backend_trace_')}
def q(data,off,value):struct.pack_into('<Q',data,off,value)
def w(data,off,value):struct.pack_into('<I',data,off,value)
def reg(u,n,value):u.reg_write(getattr(T,'UC_ARM64_REG_X'+str(n)),value)
def one(i,state,*,active=True,pending=True,parent=True,caller=True,foreign=False,frame=True,context=True,video=True,result=0,target=MD,freed=False):
 def setup(u):
  u.mem_write(STATE,bytes(state));u.mem_write(PARENT,struct.pack('<QQQQ',CALLER,int(active),2 if pending else 0,1))
  reg(u,29,APFS);u.mem_write(APFS,struct.pack('<QQ',T.STACK+0x5800,0xfffffff00746e574 if caller else 0xfffffff00746e578));u.mem_write(T.STACK+0x5800,struct.pack('<Q',CALLER if parent else CALLER+16));reg(u,20,BP+(16 if foreign else 0));reg(u,19,BP+(16 if foreign else 0));reg(u,0,BP+(16 if foreign else 0));reg(u,1,CTX)
  if i==1:reg(u,0,CTX)
  if i==2:reg(u,8,target);reg(u,20,0x07001234);reg(u,29,SPEC)
  if i==4:reg(u,20,CTX if context else CTX+16);reg(u,29,T.STACK+0x7ff0 if frame else T.STACK+0x7fe0)
  if i==5:reg(u,29,MEMDEV);u.mem_write(MEMDEV,struct.pack('<Q',SPEC if frame else SPEC+16))
  if i==6:reg(u,0,result);reg(u,29,APFS if frame else APFS+16)
  if freed:
   u.mem_unmap(BP,4096);u.mem_unmap(CTX,4096)
 c=dict(flag=0,video=video,nzcv=0xa0000000,x0=BP,seed_simd=True,setup=setup)
 ref,expected,nativewrites=T.machine(raw,b,patch[i],c,True);c['native_pc']=expected['pc'];u,actual,writes=T.machine(raw,b,patch[i],c);assert actual==expected,(i,actual,expected)
 for addr,n in nativewrites:assert bytes(ref.mem_read(addr,n))==bytes(u.mem_read(addr,n))
 assert bytes(ref.mem_read(T.STACK+0x8000,0x8000))==bytes(u.mem_read(T.STACK+0x8000,0x8000))
 fb=[(addr,n) for addr,n in writes if T.FB<=addr<T.FB+0x1200000]
 for addr,n in fb:
  y,x=divmod(addr-T.FB,T.ROW);x//=4;assert (128<=x and x+n//4<=160 and 416<=y<592) or (256<=x and x+n//4<=736 and any(v<=y<v+20 for v in (1200,1232,1264,1296,1328)))
 allowed=lambda addr,n:STATE<=addr and addr+n<=STATE+128 or T.STACK+0x8000-176<=addr and addr+n<=T.STACK+0x8000 or (addr,n) in nativewrites or T.FB<=addr and addr+n<=T.FB+0x1200000
 assert all(allowed(addr,n) for addr,n in writes),'Unexpected writes'
 if fb:
  fields={1:[(0xb620,BP,1200),(0xb621,CTX,1232)],2:[(0xb622,target,1264),(0xb623,0x07001234,1296)],6:[(0xb624,result,1328)]}.get(i,[])
  font=int(b['backend_trace']['symbols']['hex_font'],16)
  for tag,value,y in fields:
   for pos,ch in enumerate(f'{tag:04x}{value:016x}'):
    glyph=struct.unpack('<I',u.mem_read(font+int(ch,16)*4,4))[0]
    for row in range(5):
     for col in range(4):
      pixel=struct.unpack('<I',u.mem_read(T.FB+(y+row*4)*T.ROW+(256+pos*24+col*4)*4,4))[0]
      assert pixel==(0xffffffff if (glyph>>(19-row*4-col))&1 else 0),(i,tag,ch,row,col,pixel)
 out=bytes(u.mem_read(STATE,128));del ref,u;gc.collect();return out,len(fb)
def done(name):checks.append(dict(name=name,passed=True))
for name,kw in [('inactive',dict(active=False)),('parent-call-inactive',dict(pending=False)),('foreign-frame',dict(parent=False)),('foreign-callsite',dict(caller=False))]:
 st,n=one(1,bytes(128),**kw);assert st==bytes(128) and n==0;done(name)
for claim in (1,2,3):
 st=bytearray(128);w(st,0,claim);out,n=one(1,st);assert out==st and n==0;done('claim-not-reused:'+str(claim))
for i in range(2,7):
 st,n=one(i,bytes(128));assert st==bytes(128) and not n;done('unselected-stage:'+str(i))
for video in (False,True):
 for result in (0,5,2):
  st=bytes(128)
  for i in (1,2,3,4,5,6):
   st,n=one(i,st,video=video,result=result,freed=i in (4,5,6));assert bool(n)==video
  assert struct.unpack_from('<I',st)[0]==3 and struct.unpack_from('<Q',st,8)[0]==BP
  assert struct.unpack_from('<Q',st,16)[0]==CTX and struct.unpack_from('<Q',st,24)[0]==MD and struct.unpack_from('<I',st,32)[0]==0x07001234
  assert struct.unpack_from('<I',st,40)[0]==result and [struct.unpack_from('<I',st,64+4*i)[0] for i in range(6)]==[2]*6
  out,n=one(1,st);assert out==st and not n;done('native-memory-backend-chain:'+str((video,result)))
selected,_=one(1,bytes(128));selected,_=one(2,selected);selected,_=one(3,selected)
for i in (2,3,4,5,6):
 st,n=one(i,selected,foreign=True);assert st==selected and not n;done('foreign-bp:'+str(i))
for i,kw in ((4,dict(context=False)),(4,dict(frame=False)),(5,dict(frame=False)),(6,dict(frame=False))):
 st,n=one(i,selected,**kw);assert st==selected and not n;done('wrong-owner:'+str(i))
for order in ((1,2,6,3,4),(1,2,3,4,6)):
 st=bytes(128)
 for i in order:st,_=one(i,st,target=0xfffffff007000000)
 assert struct.unpack_from('<I',st)[0]==3 and struct.unpack_from('<I',st,80)[0]==0;done('other-backend-partial:'+str(order))
# A missed frame or incomplete completion remains open, never silently counted complete.
st=bytes(128)
for i in (1,2,6):st,_=one(i,st)
assert struct.unpack_from('<I',st)[0]==3 and struct.unpack_from('<I',st,80)[0]==0
for i in (3,4,5):
 out,n=one(i,st);assert out==st and not n
done('missing-sync-completion-freezes-partial-no-pointer-reuse')
# Native request object/context pages are unmapped in all callback-return tests above.
# A repeated stage does not repaint or overwrite recorded fields.
st,n=one(2,selected,target=0xfffffff007000000);assert st==selected and n==0;done('first-target-frozen')
# Verify no incoming direct branch from live code reaches the recycled observer area.
old=M.read(M.BASE/'build.json');original=(M.R/old['candidate']['path']).read_bytes();B=M.builder();parsed=B.macho(original);incoming=[]
for segment in parsed['segments']:
 if not struct.unpack_from('<I',original,segment['command_offset']+60)[0]&4:continue
 data=original[segment['fileoff']:segment['fileoff']+segment['filesize']];data=data[:len(data)//4*4]
 for j,(word,) in enumerate(struct.iter_unpack('<I',data)):
  if word&0x7c000000 != 0x14000000:continue
  pc=segment['va']+4*j;imm=word&0x3ffffff;imm=imm-(1<<26) if imm&(1<<25) else imm;target=pc+4*imm
  if M.START<=target<M.START+2256 and not M.RETIRED_START<=pc<M.RETIRED_END:incoming.append(hex(pc))
assert not incoming,incoming
done('recycled-code-has-no-live-direct-entry')
a.output.write_text(json.dumps(dict(candidate_sha256=b['candidate']['sha256'],checks=checks,limits='Exact hook replay and synthetic event schedules. No real APFS, backend IO or hardware timing proof. Generic backend completion remains partial.'),indent=2));print(len(checks),'passed')
