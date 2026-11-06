"""Stop exact renderer before DSB, then resume to verify post-barrier witness order."""
import argparse,gc,importlib.util,json,struct,sys
from pathlib import Path
import unmap_trace_inputs as M
import lean_probe_inputs as V
s=importlib.util.spec_from_file_location('barrier_t',M.R/'scripts/test-probe-transparency.py');T=importlib.util.module_from_spec(s);sys.modules[s.name]=T;s.loader.exec_module(T)
a=argparse.ArgumentParser();a.add_argument('--build',type=Path,required=True);a=a.parse_args();b=M.read(a.build);raw=(M.R/b['candidate']['path']).read_bytes();V.verify_bytes(b,raw)
state=int(b['backend_trace']['symbols']['trace_state'],16);post=int(b['backend_trace']['symbols']['trace_tile_postbarrier'],16);B=M.builder();m=B.macho(raw)
assert raw[B.backed(m,post-4):B.backed(m,post)]==bytes.fromhex('9f3f03d5')
patch=next(p for p in b['patches'] if p['reason']=='probe_backend_trace_10');BP=T.STACK+0x2000;FRAME=T.STACK+0x4000;SPEC=T.STACK+0x7000;checks=[]
def setup(u):
 st=bytearray(176);struct.pack_into('<I',st,0,2);struct.pack_into('<Q',st,8,BP);struct.pack_into('<Q',st,24,0xfffffff00741fcc8);struct.pack_into('<Q',st,104,SPEC);u.mem_write(state,bytes(st));u.mem_write(FRAME,struct.pack('<Q',SPEC));u.reg_write(T.UC_ARM64_REG_X19,BP);u.reg_write(T.UC_ARM64_REG_X29,FRAME)
c=dict(flag=0,video=True,nzcv=0xa0000000,x0=BP,seed_simd=True,setup=setup)
u,expected,_=T.machine(raw,b,patch,c,True);site=int(patch['va'],16);u.mem_write(site,bytes.fromhex(patch['after']));u.ctl_remove_cache(site,site+4)
h=u.hook_add(T.U.UC_HOOK_CODE,lambda u,pc,size,data:u.emu_stop() if pc==post-4 else None)
u.emu_start(site,0,count=1000000);assert u.reg_read(T.UC_ARM64_REG_PC)==post-4
pixel=lambda x:int.from_bytes(u.mem_read(T.FB+704*T.ROW+x*4,4),'little')
assert pixel(128)==pixel(144)==0xff40ff80;checks.append(dict(name='before-DSB-full-green-no-post-witness',passed=True))
u.hook_del(h);u.hook_add(T.U.UC_HOOK_CODE,lambda u,pc,size,data:u.emu_stop() if pc==site+4 else None)
u.emu_start(post-4,0,count=1000000);assert u.reg_read(T.UC_ARM64_REG_PC)==site+4
assert pixel(128)==0xff40ff80 and pixel(144)==0xff40c0ff;checks.append(dict(name='after-DSB-cyan-right-half-native-continuation',passed=True))
assert [u.reg_read(x) for x in T.REGS]==expected['registers'] and u.reg_read(T.UC_ARM64_REG_SP)==expected['sp'] and u.reg_read(T.UC_ARM64_REG_NZCV)==expected['nzcv'];checks.append(dict(name='witness-preserves-native-state',passed=True))
out=dict(candidate_sha256=b['candidate']['sha256'],checks=checks,dsb_pc=hex(post-4),post_witness_pc=hex(post),limits='Instruction order and renderer colors in Unicorn only. Does not model physical DSB completion; absent cyan cannot prove a DSB hang.')
(a.build.parent/'render-barrier.json').write_text(json.dumps(out,indent=2));print(len(checks),'barrier-order checks passed')
