"""Execute the actual linked UFS ledger/renderer; no UFS hardware is simulated."""
import argparse,hashlib,json,struct,sys
from pathlib import Path
import flush_trace_inputs as t
sys.path.insert(0,str(t.R/'out/python-tools'))
import unicorn as U
from unicorn.arm64_const import *

p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);w=p.parse_args().work
proof=json.loads((w/'kernel-proof.json').read_bytes());raw=(w/'kernel.macho').read_bytes()
assert hashlib.sha256(raw).hexdigest()==proof['kernel_sha256']
B=t.builder();m=B.macho(raw);targets=proof['targets'];tests=[]
u=U.Uc(U.UC_ARCH_ARM64,U.UC_MODE_ARM)
u.mem_map(0x20000000,0x1400000);fb=0x20100000;stack=0x20080000;stop=0x20010000;mapped=set();writes=[]
def map_page(a):
 page=a&~4095
 if page in mapped:return
 s=next(s for s in m['segments'] if s['va']<=page and page+4096<=s['va']+s['size'])
 n=max(0,min(4096,s['filesize']-page+s['va']));o=s['fileoff']+page-s['va']
 u.mem_map(page,4096);u.mem_write(page,raw[o:o+n]+bytes(4096-n));mapped.add(page)
def fault(uc,access,a,size,value,data):map_page(a);return True
u.hook_add(U.UC_HOOK_MEM_UNMAPPED,fault)
def written(uc,access,a,size,value,data):
 if fb<=a<fb+3200*5760:
  for q in range(a,a+size,4):
   y,x=divmod(q-fb,5760);x//=4
   assert (1280<=y<1288 and 1088<=x<1344 and (x-1088)%24<16) or (((1296<=y<1302) or (1312<=y<1318)) and 1088<=x<1344 and (x-1088)%8<6),(hex(a),size,x,y)
  writes.append(a)
u.hook_add(U.UC_HOOK_MEM_WRITE,written)
def call(name,*args):
 saved={getattr(U.arm64_const,'UC_ARM64_REG_X'+str(i)):0x123400+i for i in range(19,30)}
 for reg,value in saved.items():u.reg_write(reg,value)
 for i,value in enumerate(args):u.reg_write(getattr(U.arm64_const,'UC_ARM64_REG_X'+str(i)),value)
 u.reg_write(UC_ARM64_REG_SP,stack);u.reg_write(UC_ARM64_REG_LR,stop)
 u.emu_start(targets[name],stop,count=500000)
 assert u.reg_read(UC_ARM64_REG_PC)==stop,(name,hex(u.reg_read(UC_ARM64_REG_PC)))
 assert u.reg_read(UC_ARM64_REG_SP)==stack
 assert all(u.reg_read(r)==v for r,v in saved.items()),name
def read(name,n=8):
 map_page(targets[name]);return int.from_bytes(u.mem_read(targets[name],n),'little')
def pixel(i):return int.from_bytes(u.mem_read(fb+1280*5760+(1088+24*i)*4,4),'little')
call('_nuwa_ufs_probe_bind',fb,5759);assert not writes
call('_nuwa_ufs_probe_bind',fb,5760);assert pixel(0)==0xffffff
tests.append('bound framebuffer; invalid stride rejected; actual ARM64 callee ABI')
previous=0
for phase in range(1,11):
 call('_nuwa_ufs_probe_move',previous,phase);previous=phase
 assert read('_nuwa_ufs_probe_state')&((1<<40)-1)==1<<(4*(phase-1))
 assert pixel(0)==0xffb000 and pixel(phase)==0xffb000
 tests.append('linked stage '+str(phase))
call('_nuwa_ufs_probe_move',0,10);assert pixel(10)==0x00ffff
call('_nuwa_ufs_probe_move',10,0);assert pixel(10)==0xffb000
call('_nuwa_ufs_probe_move',10,0);assert pixel(0)==0x00ff00
assert not read('_nuwa_ufs_probe_state')&((1<<40)-1)
tests.append('nested completion count and idle only after final request exits')
for seq in (1,2,3,1024,0xffffffff,0):
 call('_nuwa_ufs_probe_move',0,4)
 call('_nuwa_ufs_probe_command',seq,0);call('_nuwa_ufs_probe_move',4,5)
 assert read('_nuwa_ufs_probe_command_started',4)==seq
 gray=seq^(seq>>1)
 for bit in range(32):
  actual=int.from_bytes(u.mem_read(fb+1296*5760+(1088+8*bit)*4,4),'little')
  assert actual==(0xffffff if gray&(1<<(31-bit)) else 0x202020)
 call('_nuwa_ufs_probe_command',seq,1);call('_nuwa_ufs_probe_move',5,6)
 assert read('_nuwa_ufs_probe_command_returned',4)==seq
 for bit in range(32):assert u.mem_read(fb+1312*5760+(1088+8*bit)*4,4)==u.mem_read(fb+1296*5760+(1088+8*bit)*4,4)
 call('_nuwa_ufs_probe_move',6,0)
tests.append('issued and returned command identities; Gray pixels and wrap')
call('_nuwa_ufs_probe_result',92,17);assert pixel(0)==0xff0000
call('_nuwa_ufs_probe_result',5,88)
assert read('_nuwa_ufs_probe_first_error',4)==92 and read('_nuwa_ufs_probe_first_done')==17
tests.append('first error record remains paired; sticky error is not idle success')
call('_nuwa_ufs_probe_move',2,0);assert read('_nuwa_ufs_probe_state')>>63 and pixel(0)==0xff00ff
tests.append('unpaired exit explicitly invalid')
u.mem_write(targets['_nuwa_ufs_probe_state'],bytes(8))
for i in range(16):call('_nuwa_ufs_probe_move',0,1)
assert read('_nuwa_ufs_probe_state')>>63 and pixel(0)==0xff00ff
tests.append('phase capacity overflow explicitly invalid')
# Observer reduction is checked against the actual shipped instructions.
for address,original in [(0xfffffff00522bac8,'ff0301d1'),(0xfffffff00522bb48,'c0035fd6'),
 (0xfffffff00522d6cc,'ff0302d1'),(0xfffffff00522d898,'c0035fd6')]:
 off=B.backed(m,address,4);assert raw[off:off+4].hex()==original
tests.append('four former shared APFS detail hooks absent')
# Existing init helper return hook now reports both native default attempts.
exec_draws=[]
def exec_draw(uc,pc,size,data):
 if pc==proof["symbols"]["draw"]:
  exec_draws.append((uc.reg_read(UC_ARM64_REG_X0),uc.reg_read(UC_ARM64_REG_X1)))
  uc.reg_write(UC_ARM64_REG_PC,uc.reg_read(UC_ARM64_REG_LR))
u.hook_add(U.UC_HOOK_CODE,exec_draw)
for result,wanted,count in ((2,2,1),(8,8,2),(5,8,2)):
 u.reg_write(UC_ARM64_REG_X0,result);u.reg_write(UC_ARM64_REG_SP,stack);u.reg_write(UC_ARM64_REG_LR,stop)
 u.emu_start(0xfffffff00769d624,stop,count=500000)
 assert u.reg_read(UC_ARM64_REG_PC)==stop and u.reg_read(UC_ARM64_REG_X0)==result and u.reg_read(UC_ARM64_REG_SP)==stack
 assert int.from_bytes(u.mem_read(targets['coarse_state']+20,4),'little')==count
 assert exec_draws==([(13,2)] if count==1 else [(13,2),(13,8)])
 # Renderer is separately tested; here capture exact row/value and bounded calls.
tests.append('existing exec return hook records two attempts and then stops')
(w/'ufs-read-probe-tests.json').write_text(json.dumps(dict(passed=True,kernel_sha256=proof['kernel_sha256'],tests=tests,
 framebuffer_writes=len(writes),rect=[1088,1280,1344,1288],scope='Actual linked ARM64 ledger and renderer. Real driver integration additionally requires source/CI binding and host production-path tests. No hardware IO or scheduling qualification.'),indent=2)+'\n')
print('PASS',len(tests),'actual carrier UFS-ledger ABI/state/display cases')
