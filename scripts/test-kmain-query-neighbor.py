"""Native query worker/lock-call/child wrapper model. Native search/key extraction execute; locks and lower IO remain fixtures; neighbor/target identities and locking flags are distinct."""
import argparse,hashlib,json,struct,sys
from pathlib import Path
import flush_trace_inputs as t
sys.path.insert(0,str(t.R/'out/python-tools'))
import unicorn as U
from unicorn.arm64_const import *
p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);w=p.parse_args().work
proof=json.loads((w/'kernel-proof.json').read_bytes());raw=(w/'kernel.macho').read_bytes();assert hashlib.sha256(raw).hexdigest()==proof['kernel_sha256']
B=t.builder();m=B.macho(raw);base=0xfffffff000000000;tests=[]
for mode in ['native-neighbor-success','native-neighbor-lock-block','native-neighbor-alias','native-neighbor-release-block','native-neighbor-fetch-error','native-neighbor-value-error','native-neighbor-alias-parent','native-neighbor-unlock-block']:
 u=U.Uc(U.UC_ARCH_ARM64,U.UC_MODE_ARM);u.mem_map(0x20000000,0x20000);mapped=set();draws=[];stopped=[];calls=[];held=set();refs={};stack=0x20018000;fetches=[0];compares=[0];fetch_trace=[];lock_trace=[]
 def put(a,v,n=8):u.mem_write(a,v.to_bytes(n,'little'))
 def reg(i):return u.reg_read(getattr(U.arm64_const,'UC_ARM64_REG_X'+str(i)))
 def map_page(a):
  page=a&~4095
  if page in mapped:return
  s=next(s for s in m['segments'] if s['va']<=page and page+4096<=s['va']+s['size']);n=max(0,min(4096,s['filesize']-page+s['va']));o=s['fileoff']+page-s['va'];u.mem_map(page,4096);u.mem_write(page,raw[o:o+n]+bytes(4096-n));mapped.add(page)
 def fault(uc,access,a,size,v,data):map_page(a);return True
 u.hook_add(U.UC_HOOK_MEM_UNMAPPED,fault)
 state=proof['targets']['coarse_state'];map_page(state)
 tree,hdr,key,hint,child,chdr,fs,thread=[0x20001000+i*0x1000 for i in range(8)]
 deep=mode.startswith('second-child') or mode in ('two-level-success','native-two-level');internal=mode.startswith(('child','internal')) or deep or mode in ('compare-block-after-fetch','native-child');internal=True;put(tree+0xc0,hdr);put(tree+8,fs);put(tree+0x70,42);put(tree+0x108,fs);put(hdr+0x20,0 if internal else 2,2);put(hdr+0x22,1 if internal else 0,2);put(hdr+0x24,1,4);put(child+0xc0,chdr);put(chdr+0x20,2,2);put(chdr+0x24,1,4);put(key,42);put(hint,42);put(hint+8,tree)
 put(state+104,thread);put(state+136,stack+0x590);refs[tree]=0;refs[child]=0
 grandchild=0x2000b000;ghdr=0x2000c000;put(grandchild+0xc0,ghdr);refs[grandchild]=0
 for index,(node,header,isleaf) in enumerate([(tree,hdr,not internal),(child,chdr,not deep),(grandchild,ghdr,True)]):
  table=0x2000d000+index*0x100;data=0x2000e000+index*0x100
  put(node,fs);put(node+8,fs);put(node+0x100,base+0x51f9ac8 if mode.startswith('native') else 0x2000f000);put(node+0xc8,table);put(node+0xd0,data);put(node+0xe8,8,4)
  put(header+0x20,6 if isleaf else 4,2);put(header+0x22,0 if isleaf else 1,2);put(header+0x24,1,4);put(header+0x2c,128,2);put(data,(3<<60)|42 if mode.startswith('native') else 42)
 put(key,(3<<60)|42)
 # Root keys 41/42/43: mode-3 query for 42 takes right neighbor 43 before target 42.
 put(hdr+0x24,3,4)
 for j,oid in enumerate((41,42,43)):
  put(0x2000d000+4*j,8*j,2);put(0x2000d002+4*j,8*(j+1),2);put(0x2000e000+8*j,(3<<60)|oid)
  put(0x2000e080-8*(j+1),100+j)
 put(tree+0xd8,0x2000e080);put(tree+0x30,4096,4)
 put(0x2000e100,(3<<60)|43);put(0x2000e200,(3<<60)|42)
 if mode=='native-neighbor-value-error':put(0x2000d00a,5000,2)
 put(fs+0x180,fs);put(fs+0x24,13,2)
 for i,v in enumerate([tree,0,key,8,0,hint if mode.startswith('hint') else 0,0x2000a000,0x2000a008]):u.reg_write(getattr(U.arm64_const,'UC_ARM64_REG_X'+str(i)),v)
 u.reg_write(UC_ARM64_REG_SP,stack);u.reg_write(UC_ARM64_REG_TPIDR_EL1,thread);u.reg_write(UC_ARM64_REG_CPACR_EL1,3<<20)
 def ret(v=0):u.reg_write(UC_ARM64_REG_X0,v);u.reg_write(UC_ARM64_REG_PC,u.reg_read(UC_ARM64_REG_LR))
 def hook(uc,pc,size,data):
  low=pc-base
  if pc==proof['symbols']['draw']:draws.append(reg(1));ret();return
  if low in (0x525ec64,0x525eca0,0x524308c,0x5240cb4,0x522d6cc,0x522d89c,0x522ae84,0x522bb4c):calls.append(hex(pc))
  if low==0x525ec64:
   lock_trace.append(dict(address=hex(reg(0)),caller=hex(reg(30))))
   if reg(30)==base+0x5234d60 and mode=='native-neighbor-lock-block':stopped.append('neighbor-read-lock-not-returning');uc.emu_stop();return
   if reg(0) in held and mode in ('native-neighbor-alias','native-neighbor-alias-parent'):stopped.append('alias-recursive-read-lock');uc.emu_stop();return
   assert reg(0) not in held;held.add(reg(0));ret()
  elif low==0x525eca0:
   if mode=='native-neighbor-unlock-block' and reg(30)==base+0x5234d6c:stopped.append('parent-unlock-not-returning');uc.emu_stop();return
   assert reg(0) in held;held.remove(reg(0));ret()
  elif low==0x524308c:refs[reg(0)]+=1;ret()
  elif low==0x5240cb4:
   if mode=='native-neighbor-release-block' and reg(30)==base+0x5234d74:stopped.append('parent-release-not-returning');uc.emu_stop();return
   refs[reg(0)]-=1;assert refs[reg(0)]>=0;ret()
  elif low in (0x522d6cc,0x522d89c):
   assert reg(0)+0xb0 in held,(mode,hex(reg(0)),held,fetch_trace,lock_trace)
  elif low==0x516b1cc:ret() # diagnostic sink only; bounds/error path stays native
  elif low==0x51f9ac8:compares[0]+=1
  elif pc==0x2000f000:
   compares[0]+=1
   if mode=='compare-block-after-fetch' and fetches[0]>0:stopped.append('comparison-not-returning');uc.emu_stop();return
   left=struct.unpack('<Q',uc.mem_read(reg(1),8))[0];right=struct.unpack('<Q',uc.mem_read(reg(3),8))[0]
   put(reg(5),((left>right)-(left<right))&0xffffffff,4)
   ret(5 if mode in ('leaf-error','internal-search-error') or (mode=='hint-relock-block' and compares[0]==1) else 0)
  # 522ae84, value extraction and value bounds execute real carrier instructions.
  elif low==0x522bb4c:
   fetches[0]+=1
   if mode=='child-block' or (mode=='second-child-block' and fetches[0]==2):stopped.append('child-fetch-not-returning');uc.emu_stop();return
   sp=uc.reg_read(UC_ARM64_REG_SP);flags=int.from_bytes(uc.mem_read(sp+8,4),'little');oid=reg(7)
   fetch_trace.append(dict(flags=flags,oid=oid))
   fail=mode=='native-neighbor-fetch-error' and fetches[0]==2
   if not fail:
    assert oid in (101,102),(mode,oid)
    node=child if oid==102 else grandchild
    if mode=='native-neighbor-alias':node=grandchild
    if mode=='native-neighbor-alias-parent' and oid==102:node=tree
    output=struct.unpack('<Q',uc.mem_read(sp+0x20,8))[0];put(output,node)
    if flags&2:assert node+0xb0 not in held;held.add(node+0xb0)
    refs[node]+=1
   ret(5 if fail else 0)
  elif low in (0x51f75b0,0x51f7270):stopped.append('query-return');uc.emu_stop()
 u.hook_add(U.UC_HOOK_CODE,hook);u.emu_start(base+0x51f7268,0,count=40000)
 assert stopped,(mode,hex(u.reg_read(UC_ARM64_REG_PC)),calls)
 error=mode.endswith('error');returned=stopped[0]=='query-return'
 if returned:
  assert reg(0)==(92 if mode=='native-neighbor-value-error' else 5 if error else 0),(mode,reg(0))
  assert len(held)==(0 if error else 1) and sum(refs.values())==(0 if error else 1),(mode,held,refs)
 assert fetch_trace==([] if mode=='native-neighbor-value-error' else [dict(flags=0,oid=102),dict(flags=2,oid=101)]),(mode,fetch_trace)
 if 'nscope_fast' in proof['symbols']:
  expected={'native-neighbor-success':[1,2,3,4,5,6],'native-neighbor-lock-block':[1,2],'native-neighbor-alias':[1,2],'native-neighbor-alias-parent':[1,2],'native-neighbor-release-block':[1,2,3,4],'native-neighbor-unlock-block':[1,2,3],'native-neighbor-fetch-error':[1,2,3,6],'native-neighbor-value-error':[1,6]}[mode]
  expected=[0xf0000000|(x<<24)|((1 if mode=='native-neighbor-alias' else 2 if mode=='native-neighbor-alias-parent' else 0) if x==2 else (92 if mode.endswith('value-error') else 5 if mode.endswith('fetch-error') else 0) if x==6 else 0) for x in expected]
  assert draws==expected,(mode,draws,expected)
 else:
  expected=[0xe1000000,0xe2000000,0xe3000000]
  if mode=='native-neighbor-success':expected += [0xe4000000,0xe5000000,0xe6000000]
  if mode=='native-neighbor-fetch-error':expected=[0xe1000000,0xe2000000,0xe3000005,0xe6000005]
  if mode=='native-neighbor-value-error':expected=[0xe1000000,0xe600005c]
  assert draws==expected,(mode,draws,expected)
 tests.append(dict(mode=mode,events=[hex(x) for x in draws],calls=calls,fetch_trace=fetch_trace,lock_trace=lock_trace,fetches=fetches[0],comparisons=compares[0],stop=stopped[0],locks_remaining=len(held),references_remaining=sum(refs.values()),passed=True))
(w/'query-neighbor-model.json').write_text(json.dumps(dict(passed=True,kernel_sha256=proof['kernel_sha256'],tests=tests,scope='Native query worker, neighbor-prefetch branch, child-value extraction and bounds, key search, native inode comparator and cleanup. Lock primitive and lower fetch are modeled; comparison is native in native-* cases and modeled otherwise; real binary search/key extraction/bounds are executed; synthetic node headers, no hardware or full APFS proof.'),indent=2)+'\n',encoding='utf-8');print('PASS',len(tests),'query worker branch/lifetime cases')
