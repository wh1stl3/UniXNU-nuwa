"""Execute PROBE49 gate paths and verify bounded sticky state and visible bits.

Synthetic CPU/framebuffer fixtures only; no hardware scanout or VM qualification.
"""
import argparse
import importlib.util
import json
import struct
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('gate_model',ROOT/'scripts/test-read-flow.py')
M=importlib.util.module_from_spec(spec);sys.modules[spec.name]=M;spec.loader.exec_module(M)
C,T,P=M.CLUSTER_CHECKS,M.T,M.CLUSTER_CHECKS.P


def exercise(raw,b,p,mode,x0,prior=None,caller_lr=None):
    u,m,sy,state,own=C.setup(M,raw,b,p,mode)
    u.reg_write(T.UC_ARM64_REG_X0,x0)
    if caller_lr is not None:u.reg_write(T.UC_ARM64_REG_LR,caller_lr)
    base=sy[P.G.SYMBOL];size=9*32;slot=P.G.OFFSETS.index(p['offset'])*32 if P.G.selected(p) else None
    if prior is not None:u.mem_write(base,prior)
    writes=[]
    u.hook_add(T.U.UC_HOOK_MEM_WRITE,lambda u,a,pos,n,v,d:writes.append((pos,n)))
    end=sy['probe_dense_'+format(p['site']&0xffffffff,'x')+'_replay']
    before=M.D.snapshot(u)
    u.hook_add(T.U.UC_HOOK_CODE,lambda u,pc,n,d:u.emu_stop() if pc==end else None)
    u.emu_start(p['site'],0,count=3000000)
    after=M.D.snapshot(u);before['pc']=end
    assert after==before,('observer register preservation',mode)
    # Native hook has not replayed: writes may only hit scratch stack, observer
    # storage, framebuffer. Specifically reject writes escaping the diag array
    # into adjacent probe_zero/code (the incoming id*4 bug).
    for pos,n in writes:
        if base<=pos<base+4096:
            seen=sy['probe_cluster_tile_seen']
            assert pos+n<=base+size or seen<=pos and pos+n<=seen+16,('diagnostic overflow',hex(pos))
    data=bytes(u.mem_read(base,size));flags,wide,strict,painted=struct.unpack_from('<4Q',data,slot) if slot is not None else (0,0,0,0)
    if slot is None:assert data==(prior if prior is not None else bytes(size))
    fb=[(pos,n) for pos,n in writes if T.FB<=pos<T.FB+0x1200000]
    if mode in ('inactive-read','foreign-thread'):
        assert data==(prior if prior is not None else bytes(size)) and not fb
        assert list(struct.unpack('<8Q',u.mem_read(sy['probe_result_state'],64)))==state
    if mode=='no-video':assert not fb and painted==0
    if fb:
        assert painted==flags
        x,y=P.geometry(p)
        for bit in range(8):
            if flags&(1<<bit):assert bytes(u.mem_read(T.FB+y*T.ROW+(x+26+bit)*4,4))==struct.pack('<I',0xffffa040)
        for i,bit in enumerate((9,8,14,15,16,17) if p['offset']==P.G.CALLER_ENTRY else (9,8,10,11,12,13)):
            if flags&(1<<bit):
                color=0xffffffff if bit in (8,9) else 0xffff0000 if bit in (10,12) else 0xff00ffff
                assert bytes(u.mem_read(T.FB+(y+7)*T.ROW+(x+i*4)*4,16))==struct.pack('<I',color)*4
    return data,(flags,wide,strict,painted),u,sy


def main():
    cli=argparse.ArgumentParser();cli.add_argument('--build',type=Path,required=True);cli.add_argument('--output',type=Path,required=True)
    a=cli.parse_args();assert not a.output.exists()
    b=json.loads(a.build.read_bytes());raw=(ROOT/b['candidate']['path']).read_bytes()
    assert M.B.sha(raw)==b['candidate']['sha256'] and b['read_flow']==M.P.plan()
    original=M.B.INPUT.read_bytes();om=M.B.macho(original);checks=[]
    for p in P.points():
        if not P.G.selected(p):continue
        for mode in C.MODES:
            C.execute(M,raw,b,p,mode,original,om)
            checks.append(dict(name=hex(p['site'])+':'+mode,passed=True))
    entry=next(p for p in P.points() if p['offset']==P.G.CALLER_ENTRY)
    prior=None;expected=1<<9|1
    for lr in (*P.G.CALLER_LRS,0xfffffff005123458):
        prior,record,_,_=exercise(raw,b,entry,'inactive-wrapper',0,prior,caller_lr=lr)
        expected|=1<<P.G.caller_bit(lr)
        assert record==(expected,lr,0,expected)
        checks.append(dict(name='caller-attribution:'+hex(lr),passed=True))
    for mode in ('foreign-thread','inactive-read'):
        exercise(raw,b,entry,mode,0,prior,caller_lr=0)
        checks.append(dict(name='caller-scope-negative:'+mode,passed=True))
    # Repeat a selected caller tile; diagnostic slots need not have base tiles.
    repaint=next(p for p in P.points() if p['offset']==0x43914c)
    _,_,u,sy=exercise(raw,b,repaint,'normal',0)
    writes=[]
    u.hook_add(T.U.UC_HOOK_MEM_WRITE,lambda u,a,pos,n,v,d:writes.append((pos,n)) if T.FB<=pos<T.FB+0x1200000 else None)
    u.emu_start(repaint['site'],0,count=3000000)
    assert not writes
    checks.append(dict(name='repeat-entry-zero-framebuffer-writes',passed=True))
    # No-video must not mark the base tile as painted; later hit can display it.
    _,_,u,sy=exercise(raw,b,repaint,'no-video',0)
    index=P.TILE_OFFSETS.index(repaint['offset'])
    assert bytes(u.mem_read(sy['probe_cluster_tile_seen']+index,1))==bytes(1)
    u.mem_write(sy['probe_scratch'],struct.pack('<QQ',T.FB,T.ROW))
    u.emu_start(repaint['site'],0,count=3000000)
    assert bytes(u.mem_read(sy['probe_cluster_tile_seen']+index,1))==b'\x01'
    checks.append(dict(name='no-video-then-base-tile-repaint',passed=True))
    p=next(p for p in P.points() if p['offset']==0x43cb90)
    # Rejections accumulate, including both control outcomes. No strict result
    # is created until the original complete gate succeeds.
    prior=None;expected=1<<9
    for mode,bit in [('inactive-wrapper',0),('parent-unpaired',1),('wrong-lr',2),('wrapper-frame',3),('parent-lr',4),('inactive-handler',5),('handler-frame',6),('unpaired',7)]:
        value=0 if bit%2==0 else 0x12345678
        prior,record,u,sy=exercise(raw,b,p,mode,value,prior)
        expected|=(1<<bit)|(1<<(10 if value==0 else 11))
        assert record==(expected,value,0,expected)
        checks.append(dict(name='cumulative:'+mode,passed=True))
    for value in (0,0x87654321):
        prior,record,u,sy=exercise(raw,b,p,'normal',value,prior)
        expected|=(1<<8)|(1<<(12 if value==0 else 13))
        assert record==(expected,value,value,expected)
        checks.append(dict(name='strict-control:'+str(value),passed=True))
    for mode in ('foreign-thread','inactive-read'):
        exercise(raw,b,p,mode,0,prior)
        checks.append(dict(name='prior-observations-do-not-leak:'+mode,passed=True))
    saved,record,_,_=exercise(raw,b,p,'no-video',0)
    assert record==((1<<9)|(1<<8)|(1<<10)|(1<<12),0,0,0)
    _,record,_,_=exercise(raw,b,p,'normal',0,saved)
    assert record[3]==record[0]
    checks.append(dict(name='no-video-record-then-visible-repaint',passed=True))
    # Reset actual header code with every state byte dirty.
    u.mem_write(sy[P.G.SYMBOL],b'\xff'*(9*32))
    first=M.P.D.PREVIOUS.DECOMP.PREVIOUS.FIRST
    end=sy['probe_dense_'+format(first&0xffffffff,'x')+'_replay']
    u.hook_add(T.U.UC_HOOK_CODE,lambda u,pc,n,d:u.emu_stop() if pc==end else None)
    u.emu_start(first,0,count=3000000)
    assert bytes(u.mem_read(sy[P.G.SYMBOL],9*32))==bytes(9*32)
    for point in P.points():
        if P.G.selected(point):
            for x,y,w,h in P.G.rectangles(point,P.geometry):
                for yy in range(y,y+h):assert bytes(u.mem_read(T.FB+yy*T.ROW+x*4,w*4))==bytes(w*4)
    checks.append(dict(name='header-clears-all-diagnostics-and-pixels',passed=True))
    # Preserve request/residual sample, catching scratch register reuse.
    sample=next(p for p in P.points() if p['offset']==0x438c3c)
    C.execute(M,raw,b,sample,'normal',original,om)
    checks.append(dict(name='requested-residual-sample-preserved',passed=True))
    a.output.write_bytes(json.dumps(dict(candidate_sha256=M.B.sha(raw),source_sha256=M.B.sha(Path(__file__).read_bytes()),checks=checks,device_accessed=False,scope=__doc__),indent=2).encode()+b'\n')
    print(json.dumps(dict(checks=len(checks),passed=True)))


if __name__=='__main__':main()
