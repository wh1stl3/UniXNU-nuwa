"""Verify standalone cluster glyphs, exact colors, reset and no HEX calls.

Fixed-image software evidence only; no scanout or hardware IRQ qualification.
"""
import argparse,importlib.util,json,struct,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('tile_model',ROOT/'scripts/test-read-flow.py')
M=importlib.util.module_from_spec(spec);sys.modules[spec.name]=M;spec.loader.exec_module(M)
C=M.CLUSTER_CHECKS;P=C.P;T=M.T

def main():
 cli=argparse.ArgumentParser();cli.add_argument('--build',type=Path,required=True);cli.add_argument('--output',type=Path,required=True);a=cli.parse_args();assert not a.output.exists()
 b=json.loads(a.build.read_bytes());raw=(ROOT/b['candidate']['path']).read_bytes();assert M.B.sha(raw)==b['candidate']['sha256']
 checks=[];occupied=set()
 for p in P.points():
  x,y=P.geometry(p);rect={(xx,yy) for xx in range(x,x+24) for yy in range(y,y+6)}
  assert not occupied&rect and 0<=x and x+24<=224 and 800<=y and y+6<=1040
  if P.tile_selected(p):occupied|=rect
  u,m,sy,_,_=C.setup(M,raw,b,p,'normal')
  start=sy['probe_dense_'+format(p['site']&0xffffffff,'x')];end=sy['probe_dense_'+format(p['site']&0xffffffff,'x')+'_replay']
  if not P.show_hex(p):
   assert not any(i.mnemonic in ('bl','blr') for i in T.A.disasm(raw,m,start,end-start)),hex(p['site'])
  u.hook_add(T.U.UC_HOOK_CODE,lambda u,pc,n,d:u.emu_stop() if pc==end else None)
  u.emu_start(p['site'],0,count=3000000)
  color=0xffff40ff if p['phase']=='entry' else 0xffffffff if p['phase']=='return' or p['returns'] else 0xffffc040 if p['calls'] else 0xff00ffff
  if not P.live_tile(p):color=0
  for yy in range(y,y+6):assert bytes(u.mem_read(T.FB+yy*T.ROW+x*4,96))==struct.pack('<I',color)*24
  checks.append(dict(name='tile:'+hex(p['site']),passed=True,hex_published=P.show_hex(p)))
  if P.tile_selected(p):
   ref,_,_,_,_=C.setup(M,raw,b,p,'normal')
   for spec in P.SPECS:
    address=sy[P.state_name(spec['name'])]
    u.mem_write(address,bytes(ref.mem_read(address,32)))
   writes=[]
   u.hook_add(T.U.UC_HOOK_MEM_WRITE,lambda u,a,pos,n,v,d:writes.append((pos,n)) if T.FB<=pos<T.FB+0x1200000 else None)
   u.emu_start(p['site'],0,count=3000000)
   assert not writes,('repeated selected site wrote framebuffer',hex(p['site']))
   checks.append(dict(name='repeat-zero-write:'+hex(p['site']),passed=True))
   v,_,vs,_,_=C.setup(M,raw,b,p,'no-video')
   v.hook_add(T.U.UC_HOOK_CODE,lambda u,pc,n,d:u.emu_stop() if pc==end else None)
   v.emu_start(p['site'],0,count=3000000)
   index=P.TILE_OFFSETS.index(p['offset'])
   assert bytes(v.mem_read(vs['probe_cluster_tile_seen']+index,1))==bytes(1)
   # Recreate native gate inputs after the first invocation consumed return bits.
   v2,_,_,_,_=C.setup(M,raw,b,p,'normal')
   for spec in P.SPECS:
    address=vs[P.state_name(spec['name'])]
    v.mem_write(address,bytes(v2.mem_read(address,32)))
   v.mem_write(vs['probe_scratch'],struct.pack('<QQ',T.FB,T.ROW))
   v.emu_start(p['site'],0,count=3000000)
   assert bytes(v.mem_read(vs['probe_cluster_tile_seen']+index,1))==(b'\x01' if P.live_tile(p) else b'\x00')
   checks.append(dict(name='no-video-retry:'+hex(p['site']),passed=True))

 # Dirty every tile, execute the actual header reset, check all slots cleared.
 u,m,sy,_,_=C.setup(M,raw,b,P.points()[0],'normal')
 for x,y in occupied:u.mem_write(T.FB+y*T.ROW+x*4,b'\xa5'*4)
 u.mem_write(sy['probe_cluster_tile_seen'],b'\xff'*16)
 first=M.P.D.PREVIOUS.DECOMP.PREVIOUS.FIRST;stop=sy['probe_dense_'+format(first&0xffffffff,'x')+'_replay']
 u.hook_add(T.U.UC_HOOK_CODE,lambda u,pc,n,d:u.emu_stop() if pc==stop else None)
 u.emu_start(first,0,count=3000000)
 assert u.reg_read(T.UC_ARM64_REG_PC)==stop
 assert bytes(u.mem_read(sy['probe_cluster_tile_seen'],16))==bytes(16)
 for x,y in occupied:assert bytes(u.mem_read(T.FB+y*T.ROW+x*4,4))==bytes(4)
 checks.append(dict(name='dirty-header-reset',passed=True))
 out=dict(candidate_sha256=b['candidate']['sha256'],source_sha256=M.B.sha(Path(__file__).read_bytes()),checks=checks,scope=__doc__,device_accessed=False)
 a.output.write_bytes(json.dumps(out,indent=2).encode()+b'\n');print(json.dumps(dict(checks=len(checks),passed=True)))
if __name__=='__main__':main()
