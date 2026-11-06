"""Replay actual mdev/helper/memcpy code using PROBE65 corrected scalar inputs in mapped fixtures."""
import argparse,gc,importlib.util,json,struct,sys
from pathlib import Path
import unmap_trace_inputs as M
import lean_probe_inputs as V
s=importlib.util.spec_from_file_location('mdev_full_t',M.R/'scripts/test-probe-transparency.py');T=importlib.util.module_from_spec(s);sys.modules[s.name]=T;s.loader.exec_module(T)
a=argparse.ArgumentParser();a.add_argument('--build',type=Path,required=True);a=a.parse_args()
current=M.read(a.build);media=M.read(M.R/'reports/xnu-entry-probe-trial/2026-10-31-probe65-unmap/media-review.json');h=media['fields']
BP=int(h['B620'],16);DATA=int(h['B635'],16);OFFSET=int(h['B630'],16);BASE=(int(h['B631'],16)<<12)&((1<<64)-1);RAM=BASE+OFFSET
COUNT=int(h['B633'],16)&0xffffffff;FLAGS=int(h['B633'],16)>>32;MD=int(h['B632'],16);SPEC=T.STACK+0x7000
START=0xfffffff00741fcc8;END=0xfffffff00741ff38;checks=[]
assert COUNT==4096 and FLAGS&0x41==0x41 and MD>>32==1 and OFFSET+COUNT<=(MD&0xffffffff)<<12
assert BASE==0xfffffff0084f1000 and RAM==0xfffffff00a6d7000
def native_anchor(raw,b,pc):
 B=M.builder();off=B.backed(B.macho(raw),pc);word=raw[off:off+4].hex()
 return dict(va=hex(pc),before=word,after=word,reason='unmodified-native-entry-anchor')

def run(raw,b,read,video,native):
 patches={int(p['reason'].rsplit('_',1)[1]):p for p in b['patches'] if p['reason'].startswith('probe_backend_trace_')}
 state=int(b['backend_trace']['symbols']['trace_state'],16)
 src=bytes((i*17+3)&255 for i in range(COUNT));disk=bytes((i*23+5)&255 for i in range(COUNT))
 def setup(u):
  for addr,size in ((BP&~4095,8192),(DATA,4096),(RAM,4096)):u.mem_map(addr,size)
  u.mem_write(DATA,src);u.mem_write(RAM,disk)
  for off,fmt,value in ((0x4c,'I',(FLAGS&~1)|int(read)),(0x5c,'I',COUNT),(0x60,'I',99),(0x64,'I',int(h['B623'],16)),(0x68,'Q',DATA),(0x78,'Q',OFFSET//512)):
   u.mem_write(BP+off,struct.pack('<'+fmt,value))
  u.mem_write(BP+0xa8,struct.pack('<Q',T.STACK+0x6000));u.mem_write(T.STACK+0x6068,struct.pack('<Q',DATA))
  u.mem_write(0xfffffff007a7f5d8,struct.pack('<QIII',int(h['B631'],16),MD&0xffffffff,MD>>32,512))
  st=bytearray(280);struct.pack_into('<I',st,0,2);struct.pack_into('<Q',st,8,BP);struct.pack_into('<Q',st,24,START);struct.pack_into('<Q',st,104,SPEC);struct.pack_into('<I',st,68,2);u.mem_write(state,bytes(st))
  u.reg_write(T.UC_ARM64_REG_X0,BP);u.reg_write(T.UC_ARM64_REG_X29,SPEC);u.reg_write(T.UC_ARM64_REG_X30,0xfffffff007476f80)
 c=dict(flag=0,video=video,nzcv=0xa0000000,x0=BP,seed_simd=True,setup=setup)
 u,_,writes=T.machine(raw,b,patches.get(7) or native_anchor(raw,b,START),c,True);u.reg_write(T.UC_ARM64_REG_SP,T.STACK+0x8000)
 for p in patches.values():u.mem_write(int(p['va'],16),bytes.fromhex(p['before'] if native else p['after']))
 u.ctl_remove_cache(0xfffffff007000000,0xfffffff009000000)
 visited=[]
 def at(u,pc,size,data):
  if pc in (START,0xfffffff00742b404,0xfffffff0079dde70,0xfffffff00741ff2c,0xfffffff00742b50c,0xfffffff00742b514,END):visited.append(hex(pc))
  if pc==END:u.emu_stop()
 u.hook_add(T.U.UC_HOOK_CODE,at);u.emu_start(START,0,count=3000000)
 assert u.reg_read(T.UC_ARM64_REG_PC)==END,visited
 assert bytes(u.mem_read(DATA,COUNT))==(disk if read else src)
 assert bytes(u.mem_read(RAM,COUNT))==(disk if read else src)
 assert int.from_bytes(u.mem_read(BP+0x4c,4),'little')==(FLAGS&~1)|int(read)
 assert int.from_bytes(u.mem_read(BP+0x60,4),'little')==COUNT
 regs=[u.reg_read(x) for x in T.REGS]+[u.reg_read(T.UC_ARM64_REG_SP),u.reg_read(T.UC_ARM64_REG_NZCV)]
 simd=[u.reg_read(getattr(T,'UC_ARM64_REG_Q'+str(i))) for i in range(32)]
 # Native mdev leaves the first eight frame bytes as unused padding; compare its output slot, saved registers and caller stack.
 mem=bytes(u.mem_read(BP,0x110))+bytes(u.mem_read(T.STACK+0x7fa8,0x8058))
 st=bytes(u.mem_read(state,280));del u;gc.collect();return regs,simd,mem,st,visited
for path in (M.R/'reports/kernel-entry-probe/2026-10-31-probe64-completion-r1/build.json',a.build):
 b=M.read(path);raw=(M.R/b['candidate']['path']).read_bytes();V.verify_bytes(b,raw)
 for read in (False,True):
  for video in (False,True):
   expected=run(raw,b,read,video,True);got=run(raw,b,read,video,False);assert expected[:3]==got[:3],dict(registers=expected[0]==got[0],simd=expected[1]==got[1],memory_diff=[hex(i) for i,(x,y) in enumerate(zip(expected[2],got[2])) if x!=y][:24])
   for off in ([] if b['probe_revision'] in (68,69,70,71,72) else [144] if b['probe_revision']==67 else [128,140,144] if b['probe_revision']==66 else [128,132,136,140,144]):assert struct.unpack_from('<I',got[3],off)[0]==2
   checks.append(dict(name=f"rev{b['probe_revision']}:direction={'captured-read-flags' if read else 'write-counterfactual'}:video={video}",passed=True,visited=got[4]))
out=dict(candidate_sha256=current['candidate']['sha256'],checks=checks,field_scalars=media['fields'],ram_base=hex(BASE),transfer_address=hex(RAM),bytes=COUNT,limits='Corrected field flags and synthetic real_bp pre-mapped shortcut, data pages and 512-byte sector fixture; exact native helper and memcpy instructions, no host stubs. Scalar snapshot does not prove later flags or actual hardware mapping/cache/bus behavior. Data patterns are not real RAMDisk bytes.')
(a.build.parent/'mdev-native-chain.json').write_text(json.dumps(out,indent=2));print(len(checks),'full mdev chain checks passed')
