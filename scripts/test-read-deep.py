"""Native allocation/vector/decode observations and real allocation prefix."""
import argparse,importlib.util,json,struct,sys
from pathlib import Path
import read_deep_sites as P
ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('deep_model',ROOT/'scripts/test-read-fetch.py');F=importlib.util.module_from_spec(s);sys.modules[s.name]=F;s.loader.exec_module(F)
D=F.D;T=F.T;B=F.B
MODES=D.MODES


def setup(raw,b,site,mode):
    u,m,sy=F.setup(raw,b,P.PREVIOUS.CALLBACK,mode)
    cb,child=T.STACK+0xf000,T.STACK+0xa800
    p=next(q for q in P.points() if q['site']==site)
    outer=p['phase'] in ('entry','tail-entry','return')
    lr=P.PREVIOUS.CALLBACK+(0x1b4 if p['kind']=='malloc' else 0x3d8)
    u.mem_write(child,struct.pack('<QQ',cb,lr))
    u.reg_write(T.UC_ARM64_REG_X29,cb if outer or p['kind']=='post' else child)
    u.reg_write(T.UC_ARM64_REG_LR,lr)
    if mode=='wrong-lr':
        if p['kind']=='post':u.mem_write(cb+8,struct.pack('<Q',T.STOP))
        elif outer:u.reg_write(T.UC_ARM64_REG_LR,T.STOP)
        else:u.mem_write(child+8,struct.pack('<Q',T.STOP))
    u.mem_write(sy['probe_fetch_state']+48,struct.pack('<Q',(1<<2)|(1<<5)|(1<<10)|(1<<11)))
    bits=0 if mode=='unpaired' else (1<<32)-1
    u.mem_write(sy['probe_deep_state'],struct.pack('<8Q',cb,bits,0,0,cb,bits,0,0))
    return u,m,sy


def snapshot(u):return D.snapshot(u)


def execute(raw,b,site,mode,original,om,native=False):
    u,m,sy=setup(raw,b,site,mode);writes=[]
    if native:
        at=B.backed(om,site);u.mem_write(site,original[at:at+4]);u.hook_add(T.U.UC_HOOK_MEM_WRITE,lambda u,a,p,n,v,d:writes.append((p,n)))
        u.emu_start(site,0,count=1)
        return snapshot(u),[(p,n,bytes(u.mem_read(p,n))) for p,n in writes]
    expected,stores=execute(raw,b,site,mode,original,om,True)
    selected=[q for q in P.points() if q['site']==site]
    for q in selected:
        x,y=P.geometry(q['id'])
        for row in range(16):u.mem_write(T.FB+(y+row)*T.ROW+x*4,b'\xa5'*128)
    u.hook_add(T.U.UC_HOOK_MEM_WRITE,lambda u,a,p,n,v,d:writes.append((p,n)) if T.FB<=p<T.FB+0x1200000 else None)
    u.hook_add(T.U.UC_HOOK_CODE,lambda u,pc,n,d:u.emu_stop() if pc==expected['pc'] else None)
    u.emu_start(site,0,count=2000000);assert snapshot(u)==expected,(hex(site),mode)
    for p,n,value in stores:assert bytes(u.mem_read(p,n))==value
    expected_bytes=0
    for q in selected:
        hit=mode in ('normal','unpaired','no-video') and not(mode=='unpaired' and q['phase']=='continuation')
        lit=hit and mode!='no-video';x,y=P.geometry(q['id']);base=T.FB+y*T.ROW+x*4
        color=0xffffc040 if q['phase']=='call' else 0xffffffff if q['phase'] in ('continuation','return') else 0xffff40ff
        expected_bytes+=256 if lit else 0
        for row in range(16):assert bytes(u.mem_read(base+row*T.ROW,128))==(struct.pack('<I',color)*32 if lit and row<2 else b'\xa5'*128),(q['id'],mode,row)
    assert sum(n for p,n in writes)==expected_bytes
    return dict(name=hex(site)+':'+mode,passed=True)


def reset(raw,b):
    u,m,sy=setup(raw,b,P.MALLOC_DATA,'normal');u.mem_write(sy['probe_deep_state'],b'\xa5'*64)
    for q in P.points():
        x,y=P.geometry(q['id']);u.mem_write(T.FB+y*T.ROW+x*4,b'\xa5'*128);u.mem_write(sy['probe_flags']+128+q['id'],b'\x01')
    stop=m['symbols']['_vn_rdwr'];u.hook_add(T.U.UC_HOOK_CODE,lambda u,pc,n,d:u.emu_stop() if pc==stop else None)
    u.emu_start(D.P.PREVIOUS.FIRST,0,count=3000000)
    assert u.reg_read(T.UC_ARM64_REG_PC)==stop and bytes(u.mem_read(sy['probe_deep_state'],64))==bytes(64)
    for q in P.points():
        x,y=P.geometry(q['id']);assert bytes(u.mem_read(T.FB+y*T.ROW+x*4,128))==bytes(128)
        assert bytes(u.mem_read(sy['probe_flags']+128+q['id'],1))==bytes(1)


def prefix(raw,b,original,om,native=False):
    u,m,sy=setup(raw,b,P.MALLOC_DATA,'normal')
    u.reg_write(T.UC_ARM64_REG_X0,40)
    u.mem_write(0xfffffff007a0ff80,bytes(8))
    if native:
        for pc in {q['site'] for q in P.points()}:
            at=B.backed(om,pc);u.mem_write(pc,original[at:at+4])
    stop=m['symbols']['_kalloc_ext'];sp=u.reg_read(T.UC_ARM64_REG_SP)
    u.hook_add(T.U.UC_HOOK_CODE,lambda u,pc,n,d:u.emu_stop() if pc==stop else None);u.emu_start(P.MALLOC_DATA,0,count=2000000)
    assert u.reg_read(T.UC_ARM64_REG_PC)==stop and u.reg_read(T.UC_ARM64_REG_X1)==40
    return snapshot(u),bytes(u.mem_read(sp-48,48))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.output.exists()
    b=json.loads(a.build.read_bytes());raw=(ROOT/b['candidate']['path']).read_bytes();assert b['probe_revision'] in (46,47,48,49) and B.sha(raw)==b['candidate']['sha256'] and b['read_deep']==P.plan()
    original=B.INPUT.read_bytes();assert B.sha(original)==B.EXPECTED;om=B.macho(original)
    checks=[]
    for site in sorted({q['site'] for q in P.points()}):
        for mode in MODES:checks.append(execute(raw,b,site,mode,original,om))
    reset(raw,b);checks.append(dict(name='header-reset',passed=True))
    old=[(*D.P.geometry(q['id']),32,2) for q in D.P.points()]+[(*P.PREVIOUS.geometry(q['id']),32,2) for q in P.PREVIOUS.points()]+[(0,256,192,544),(256,224,480,664),(832,224,608,816)]
    new=[(*P.geometry(q['id']),32,2) for q in P.points()]
    for i,(x,y,w,h) in enumerate(new):
        assert 0<=x and x+w<=1440 and 224<=y and y+h<=1040
        assert not any(x<rx+rw and rx<x+w and y<ry+rh and ry<y+h for rx,ry,rw,rh in old+new[:i])
    checks.append(dict(name='layout',passed=True))
    sy={k:int(v,16) for k,v in b['probe']['symbols'].items()};site=P.MALLOC+0x50
    start=sy[f'probe_dense_{site&0xffffffff:x}'];end=sy[f'probe_dense_{site&0xffffffff:x}_replay'];m=B.macho(raw)
    ins=next(i for i in T.A.disasm(raw,m,start,end-start) if i.mnemonic=='tbz' and i.op_str.startswith('w10, #0,'))
    bad=bytearray(raw);at=B.backed(m,ins.address);bad[at:at+4]=bytes.fromhex('1f2003d5');rejected=False
    try:execute(bytes(bad),b,site,'unpaired',original,om)
    except AssertionError:rejected=True
    assert rejected;checks.append(dict(name='missing-pair-negative',passed=True))
    u,m,sy=setup(raw,b,P.MALLOC,'normal');u.mem_write(sy['probe_fetch_state']+48,bytes(8))
    expected,_=execute(raw,b,P.MALLOC,'normal',original,om,True)
    u.hook_add(T.U.UC_HOOK_CODE,lambda u,pc,n,d:u.emu_stop() if pc==expected['pc'] else None);u.emu_start(P.MALLOC,0,count=2000000)
    assert snapshot(u)==expected and bytes(u.mem_read(sy['probe_deep_state']+16,8))==bytes(8)
    checks.append(dict(name='missing-parent-pair',passed=True))
    assert prefix(raw,b,original,om)==prefix(raw,b,original,om,True);checks.append(dict(name='native-allocation-prefix',passed=True))
    out=dict(candidate_sha256=B.sha(raw),source_sha256=P.plan()['source_sha256'],test_sha256=B.sha(Path(__file__).read_bytes()),checks=checks,device_accessed=False,complete_decompression_executed=False,limitations=['Only native allocation prefix executes until kalloc_ext; isolated instructions elsewhere','No live lock, decompression, cache or IRQ qualification'])
    a.output.write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(dict(checks=len(checks),passed=True)))


if __name__=='__main__':main()
