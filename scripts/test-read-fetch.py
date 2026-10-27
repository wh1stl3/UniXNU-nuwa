"""Native-state, complete pixel, scoped pairing and real fetch-prefix checks."""
import argparse,importlib.util,json,struct,sys
from pathlib import Path
import read_fetch_sites as P
ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('fetch_model',ROOT/'scripts/test-read-decmp.py');D=importlib.util.module_from_spec(s);sys.modules[s.name]=D;s.loader.exec_module(D)
T=D.T;B=D.B
MODES=D.MODES


def setup(raw,b,site,mode):
    u,m,sy=D.setup(raw,b,D.P.ENTRY,mode)
    apfs,decmp,fetch,cb=(T.STACK+i for i in (0xc000,0xb000,0xe000,0xf000))
    u.mem_write(decmp,struct.pack('<QQ',apfs,D.P.CALLER+4))
    u.mem_write(fetch,struct.pack('<QQ',decmp,P.CALLERS[0]+4))
    u.mem_write(cb,struct.pack('<QQ',fetch,P.INDIRECT+4))
    p=next(q for q in P.points() if q['site']==site);outer=p['phase'] in ('entry','return')
    parent=fetch if p['kind']=='callback' else decmp
    frame=cb if p['kind']=='callback' else fetch
    lr=P.INDIRECT+4 if p['kind']=='callback' else P.CALLERS[0]+4
    u.reg_write(T.UC_ARM64_REG_X29,parent if outer else frame);u.reg_write(T.UC_ARM64_REG_LR,lr)
    if mode=='wrong-lr':
        if outer:u.reg_write(T.UC_ARM64_REG_LR,T.STOP)
        else:u.mem_write(frame+8,struct.pack('<Q',T.STOP))
    if mode=='foreign-frame':u.mem_write(decmp,struct.pack('<Q',apfs+16))
    u.mem_write(sy['probe_decmp_state'],struct.pack('<4Q',apfs,1<<21,0,0))
    u.mem_write(sy['probe_fetch_state'],struct.pack('<8Q',decmp,0 if mode=='unpaired' and p['kind']=='fetch' else 0xffff,0,0,P.CALLBACK,fetch,0 if mode=='unpaired' else 0xffff,0))
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
        color=0xffffc040 if q['phase']=='call' else 0xffff40ff if q['phase']=='entry' else 0xffffffff
        expected_bytes+=256 if lit else 0
        for row in range(16):assert bytes(u.mem_read(base+row*T.ROW,128))==(struct.pack('<I',color)*32 if lit and row<2 else b'\xa5'*128),(q['id'],mode,row)
    assert sum(n for p,n in writes)==expected_bytes
    return dict(name=hex(site)+':'+mode,passed=True)


def reset(raw,b):
    u,m,sy=setup(raw,b,P.FETCH,'normal');u.mem_write(sy['probe_fetch_state'],b'\xa5'*64)
    for q in P.points():
        x,y=P.geometry(q['id']);u.mem_write(T.FB+y*T.ROW+x*4,b'\xa5'*128);u.mem_write(sy['probe_flags']+128+q['id'],b'\x01')
    stop=m['symbols']['_vn_rdwr'];u.hook_add(T.U.UC_HOOK_CODE,lambda u,pc,n,d:u.emu_stop() if pc==stop else None)
    u.emu_start(D.P.PREVIOUS.FIRST,0,count=3000000)
    assert u.reg_read(T.UC_ARM64_REG_PC)==stop and bytes(u.mem_read(sy['probe_fetch_state'],64))==bytes(64)
    for q in P.points():
        x,y=P.geometry(q['id']);assert bytes(u.mem_read(T.FB+y*T.ROW+x*4,128))==bytes(128)
        assert bytes(u.mem_read(sy['probe_flags']+128+q['id'],1))==bytes(1)


def prefix(raw,b,original,om,native=False):
    u,m,sy=setup(raw,b,P.FETCH,'normal');hdr,vec,got=(T.STACK+i for i in (0x6000,0x7000,0x8000))
    u.mem_write(hdr,struct.pack('<IIIQ',0x636d7066,20,4,8192))
    for reg,v in ((2,hdr),(3,0),(4,4096),(5,vec),(6,got)):u.reg_write(getattr(T,f'UC_ARM64_REG_X{reg}'),v)
    if native:
        for pc in {q['site'] for q in P.points()}:
            at=B.backed(om,pc);u.mem_write(pc,original[at:at+4])
    stop=m['symbols']['_IORWLockRead'];sp=u.reg_read(T.UC_ARM64_REG_SP)
    u.hook_add(T.U.UC_HOOK_CODE,lambda u,pc,n,d:u.emu_stop() if pc==stop else None);u.emu_start(P.FETCH,0,count=2000000)
    assert u.reg_read(T.UC_ARM64_REG_PC)==stop
    return snapshot(u),bytes(u.mem_read(sp-80,80)),bytes(u.mem_read(got,8))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.output.exists()
    b=json.loads(a.build.read_bytes());raw=(ROOT/b['candidate']['path']).read_bytes();assert b['probe_revision'] in (45,46,47,48,49) and B.sha(raw)==b['candidate']['sha256'] and b['read_fetch']==P.plan()
    original=B.INPUT.read_bytes();assert B.sha(original)==B.EXPECTED;om=B.macho(original)
    checks=[]
    for site in sorted({q['site'] for q in P.points()}):
        for mode in MODES:checks.append(execute(raw,b,site,mode,original,om))
    reset(raw,b);checks.append(dict(name='header-reset',passed=True))
    old=[(*D.P.geometry(q['id']),32,2) for q in D.P.points()]
    new=[(*P.geometry(q['id']),32,2) for q in P.points()]
    for i,(x,y,w,h) in enumerate(new):
        assert 736<=x and x+w<=816 and 224<=y and y+h<=1040
        assert not any(x<rx+rw and rx<x+w and y<ry+rh and ry<y+h for rx,ry,rw,rh in old+new[:i])
    checks.append(dict(name='layout',passed=True))
    sy={k:int(v,16) for k,v in b['probe']['symbols'].items()};site=P.FETCH+0x5c
    start=sy[f'probe_dense_{site&0xffffffff:x}'];end=sy[f'probe_dense_{site&0xffffffff:x}_replay'];m=B.macho(raw)
    ins=next(i for i in T.A.disasm(raw,m,start,end-start) if i.mnemonic=='tbz' and i.op_str.startswith('w10, #0,'))
    bad=bytearray(raw);at=B.backed(m,ins.address);bad[at:at+4]=bytes.fromhex('1f2003d5');rejected=False
    try:execute(bytes(bad),b,site,'unpaired',original,om)
    except AssertionError:rejected=True
    assert rejected;checks.append(dict(name='missing-pair-negative',passed=True))
    u,m,sy=setup(raw,b,P.CALLBACK,'normal');u.mem_write(sy['probe_fetch_state']+32,bytes(8))
    expected,_=execute(raw,b,P.CALLBACK,'normal',original,om,True)
    u.hook_add(T.U.UC_HOOK_CODE,lambda u,pc,n,d:u.emu_stop() if pc==expected['pc'] else None);u.emu_start(P.CALLBACK,0,count=2000000)
    assert snapshot(u)==expected and bytes(u.mem_read(sy['probe_fetch_state']+16,8))==bytes(8)
    checks.append(dict(name='wrong-callback-target',passed=True))
    assert prefix(raw,b,original,om)==prefix(raw,b,original,om,True);checks.append(dict(name='native-fetch-prefix',passed=True))
    out=dict(candidate_sha256=B.sha(raw),source_sha256=P.plan()['source_sha256'],test_sha256=B.sha(Path(__file__).read_bytes()),checks=checks,device_accessed=False,complete_decompression_executed=False,limitations=['Only native fetch prefix executes until lock body; isolated instructions elsewhere','No live lock, decompression, cache or IRQ qualification'])
    a.output.write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(dict(checks=len(checks),passed=True)))


if __name__=='__main__':main()
