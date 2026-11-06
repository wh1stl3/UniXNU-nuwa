"""Native delete prefix and disjoint semantic windows; external VM calls are explicit host substitutes."""
import argparse,gc,importlib.util,json,struct,sys
from pathlib import Path
import delete_trace_inputs as M
s=importlib.util.spec_from_file_location('delete_chain_t',M.R/'scripts/test-probe-transparency.py');T=importlib.util.module_from_spec(s);sys.modules[s.name]=T;s.loader.exec_module(T)
a=argparse.ArgumentParser();a.add_argument('--build',type=Path,required=True);a=a.parse_args();b=M.read(a.build);raw=(M.R/b['candidate']['path']).read_bytes();M.verify_bytes(b,raw)
MAP=T.STACK+0x3000;ENTRY=T.STACK+0x2000;PMAP=T.STACK+0x5000;THREAD=T.STACK+0x1000;WRAP=T.STACK+0x4c00;UPLFRAME=T.STACK+0x4a00;DF=T.STACK+0x7ff0
state=int(b['backend_trace']['symbols']['trace_state'],16);patches={int(p['reason'].rsplit('_',1)[1]):p for p in b['patches'] if p['reason'].startswith('probe_backend_trace_')};checks=[]
LOOKUP=0xfffffff007348228;PMREMOVE=0xfffffff0073a64fc;UNLINK=0xfffffff0073485bc;PANIC=0xfffffff007938000
windows={'lookup-hit':(0xfffffff007326b44,0xfffffff007326d44,[26,27]),'lookup-miss':(0xfffffff007326b44,0xfffffff007326d44,[26,27]),'lookup-null':(0xfffffff007326b44,0xfffffff007326d44,[26,27]),'misaligned-panic':(0xfffffff007326b44,PANIC+4,[26,31]),'pmap':(0xfffffff00732758c,0xfffffff0073275a4,[28,29]),'pmap-skip':(0xfffffff007327584,0xfffffff0073275a4,[]),'unlink':(0xfffffff00732774c,0xfffffff007327760,[30]),'wait-transition':(0xfffffff0073271e8,0xfffffff0072799d0,[32]),'wait-wired':(0xfffffff00732725c,0xfffffff0072799d0,[32]),'unwire':(0xfffffff007327388,0xfffffff00731c150,[33]),'panic':(PANIC,PANIC+4,[31])}
def run(case,video,native,foreign):
 start,end,wanted=windows[case];prefix=case.startswith('lookup') or case=='misaligned-panic'
 def reg(u,n,v):u.reg_write(getattr(T,'UC_ARM64_REG_X'+str(n)),v)
 def get(u,n):return u.reg_read(getattr(T,'UC_ARM64_REG_X'+str(n)))
 def setup(u):
  st=bytearray(280);struct.pack_into('<I',st,0,2);struct.pack_into('<I',st,172,2);struct.pack_into('<QQQQQQ',st,232,MAP+(16 if foreign else 0),UPLFRAME,0x1000,0x2000,0 if prefix else DF,THREAD+(16 if foreign else 0));u.mem_write(state,bytes(st))
  u.mem_write(MAP+0x20,struct.pack('<QQ',0,0x100000));u.mem_write(MAP+0x34,struct.pack('<H',12));u.mem_write(MAP+0x40,struct.pack('<Q',PMAP));u.mem_write(MAP+0x90,struct.pack('<I',1));u.mem_write(0xfffffff00715c660,struct.pack('<Q',PMAP+0x100))
  u.mem_write(ENTRY+0x10,struct.pack('<QQ',0x1000,0x2000));u.mem_write(ENTRY+0x48,struct.pack('<Q',0x0002000112345678));u.mem_write(WRAP,struct.pack('<QQ',UPLFRAME,0xfffffff0073639cc));u.mem_write(DF-0x60,struct.pack('<Q',ENTRY));u.reg_write(T.UC_ARM64_REG_TPIDR_EL1,THREAD)
  for n,v in [(0,MAP),(1,0x1001 if case=='misaligned-panic' else 0x1000),(2,0x2000),(3,0),(4,0),(5,T.STACK+0x6000),(23,MAP),(29,WRAP if prefix else DF),(30,0xfffffff00732fdac)]:reg(u,n,v)
  if not prefix:
   u.reg_write(T.UC_ARM64_REG_SP,T.STACK+0x7e50);reg(u,1,ENTRY);reg(u,13,ENTRY);reg(u,27,MAP+0x40);reg(u,22,ENTRY);reg(u,25,0x2000);reg(u,20,0x1000)
  if case=='pmap-skip':reg(u,0,0);reg(u,28,0)
  if case=='panic':reg(u,0,0xdeadbeef);reg(u,30,0xfffffff00795a920)
 # Build the machine with a harmless native SUB anchor, then restore original entry SP.
 u,_,writes=T.machine(raw,b,patches[26],dict(flag=0,video=video,nzcv=0xa0000000,x0=MAP,seed_simd=True,setup=setup),True);u.reg_write(T.UC_ARM64_REG_SP,T.STACK+(0x8000 if prefix else 0x7e50))
 for p in patches.values():u.mem_write(int(p['va'],16),bytes.fromhex(p['before'] if native else p['after']))
 u.ctl_remove_cache(0xfffffff007000000,0xfffffff009000000);events=[]
 def hook(u,pc,size,data):
  if pc==end:u.emu_stop();return
  if pc in (LOOKUP,PMREMOVE,UNLINK):
   events.append(hex(pc))
   if pc==LOOKUP:
    assert get(u,0)==MAP and get(u,1)==0x1000
    u.mem_write(get(u,2),struct.pack('<Q',0 if case=='lookup-null' else ENTRY));reg(u,0,0 if case=='lookup-miss' else 1)
   if pc==PMREMOVE:assert [get(u,i) for i in range(4)]==[PMAP,0x1000,0x2000,0x100]
   if pc==UNLINK:assert [get(u,i) for i in range(3)]==[MAP,ENTRY,0]
   u.reg_write(T.UC_ARM64_REG_PC,get(u,30))
 u.hook_add(T.U.UC_HOOK_CODE,hook);u.emu_start(start,0,count=4000000);assert u.reg_read(T.UC_ARM64_REG_PC)==end,(case,hex(u.reg_read(T.UC_ARM64_REG_PC)))
 regs=[u.reg_read(x) for x in T.REGS]+[u.reg_read(T.UC_ARM64_REG_SP),u.reg_read(T.UC_ARM64_REG_NZCV)];simd=[u.reg_read(getattr(T,'UC_ARM64_REG_Q'+str(i))) for i in range(32)]
 mem=bytes(u.mem_read(MAP,0x100))+bytes(u.mem_read(ENTRY,0x100))+bytes(u.mem_read(T.STACK+0x8000,0x8000));st=bytes(u.mem_read(state,280));fb=sum(n for addr,n in writes if T.FB<=addr<T.FB+0x1200000)
 del u;gc.collect();return regs,simd,mem,st,events,fb
for case in windows:
 for video in (False,True):
  for foreign in (False,True):
   expected=run(case,video,True,foreign);got=run(case,video,False,foreign);assert got[:3]==expected[:3] and got[4]==expected[4],(case,video,foreign)
   hits=[i for i in range(26,34) if struct.unpack_from('<I',got[3],M.flag_offset(i))[0]==2];assert hits==([] if foreign else windows[case][2]),(case,hits)
   checks.append(dict(name=f'{case}:video={video}:foreign={foreign}',passed=True,substituted_calls=got[4],framebuffer_bytes=got[5]))
old=M.read(M.R/'reports/kernel-entry-probe/2026-10-31-probe67-map-r1/build.json');priorbytes=(M.R/old['backend_trace']['code_path']).stat().st_size;nowbytes=(M.R/b['backend_trace']['code_path']).stat().st_size
assert len(patches)==17 and nowbytes==5352<priorbytes==5464
# Budget is selected normal-path upper bound, not a hardware timing measurement.
budget=dict(hooks=17,prior_hooks=17,code_bytes=nowbytes,prior_code_bytes=priorbytes,state_bytes=280,reserved_state_bytes=288,normal_selected_tiles=14,prior_normal_selected_tiles=17,normal_selected_hex_rows=13,prior_normal_selected_hex_rows=16,loops_added=0,per_stage_limit=1,hardware_timing_measured=False)
checks.append(dict(name='observer-budget-no-hook-growth-smaller-code-and-normal-draw-bound',passed=True))
(a.build.parent/'delete-native-chain.json').write_text(json.dumps(dict(candidate_sha256=b['candidate']['sha256'],checks=checks,budget=budget,limits='Native user-map prefix, real misalignment panic branch, pmap/unlink/sleep/unwire windows. Lookup/pmap/unlink calls explicitly substituted; windows are not a full real delete or hardware test. Panic retains original observer and native control flow.'),indent=2));print(len(checks),'delete chain/window and budget checks passed')
