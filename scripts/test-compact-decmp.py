"""Check complete strip pixels, untouched surroundings and reset behavior."""
import argparse
import importlib.util
import json
import struct
import sys
from pathlib import Path
import probe_compact_decmp as P
ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('compact_model',ROOT/'scripts/test-read-decmp.py')
D=importlib.util.module_from_spec(s);sys.modules[s.name]=D;s.loader.exec_module(D)
T=D.T;B=D.B


def run(raw,b,q,mode='normal',repeat=False):
    u,m,sy=D.setup(raw,b,q['site'],mode)
    x,y=D.P.geometry(q['id']);base=T.FB+y*T.ROW+x*4
    for row in range(16):u.mem_write(base+row*T.ROW,b'\xa5'*128)
    if repeat:u.mem_write(sy['probe_flags']+128+q['id'],b'\x01')
    original=B.INPUT.read_bytes();om=B.macho(original)
    expected,_=D.execute(raw,b,q['site'],mode,True,original,om)
    writes=[]
    u.hook_add(T.U.UC_HOOK_MEM_WRITE,lambda u,a,p,n,v,d:writes.append((p,n)) if T.FB<=p<T.FB+0x1200000 else None)
    u.hook_add(T.U.UC_HOOK_CODE,lambda u,pc,n,d:u.emu_stop() if pc==expected['pc'] else None)
    u.emu_start(q['site'],0,count=2000000)
    assert D.snapshot(u)==expected
    color=0xff40c0ff if q['phase']=='call' else 0xff40ff80
    painted=mode!='no-video' and not repeat
    assert sum(n for p,n in writes)==(256 if painted else 0)
    for row in range(16):
        want=struct.pack('<I',color)*32 if painted and row<2 else b'\xa5'*128
        assert bytes(u.mem_read(base+row*T.ROW,128))==want,(q['id'],row)
    assert all(base<=p and (p-base)//T.ROW<2 and (p-base)%T.ROW+n<=128 for p,n in writes)


def reset(raw,b):
    u,m,sy=D.setup(raw,b,D.P.ENTRY,'normal')
    for q in D.P.points():
        x,y=D.P.geometry(q['id'])
        for row in range(16):u.mem_write(T.FB+(y+row)*T.ROW+x*4,b'\xa5'*128)
        u.mem_write(sy['probe_flags']+128+q['id'],b'\x01')
    stop=m['symbols']['_vn_rdwr']
    u.hook_add(T.U.UC_HOOK_CODE,lambda u,pc,n,d:u.emu_stop() if pc==stop else None)
    u.emu_start(D.P.PREVIOUS.FIRST,0,count=2000000)
    assert u.reg_read(T.UC_ARM64_REG_PC)==stop
    for q in D.P.points():
        x,y=D.P.geometry(q['id'])
        for row in range(16):
            nested=False
            if b['probe_revision']>=45:
                import read_fetch_sites as F
                nested=any((x,y+row) in ((F.geometry(p['id'])[0],F.geometry(p['id'])[1]),(F.geometry(p['id'])[0],F.geometry(p['id'])[1]+1)) for p in F.points())
            assert bytes(u.mem_read(T.FB+(y+row)*T.ROW+x*4,128))==(bytes(128) if row<2 or nested else b'\xa5'*128)
        assert bytes(u.mem_read(sy['probe_flags']+128+q['id'],1))==bytes(1)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.output.exists()
    b=json.loads(a.build.read_bytes());raw=(ROOT/b['candidate']['path']).read_bytes()
    assert b['probe_revision'] in (44,45,46,47,48,49) and b['compact_decmp']==P.plan() and B.sha(raw)==b['candidate']['sha256']
    checks=[]
    for q in D.P.points():
        run(raw,b,q);checks.append(dict(name='pixels-'+str(q['id']),passed=True))
    reset(raw,b);checks.append(dict(name='header-reset',passed=True))
    q=D.P.points()[0]
    run(raw,b,q,'no-video');checks.append(dict(name='no-video',passed=True))
    run(raw,b,q,repeat=True);checks.append(dict(name='repeat-no-write',passed=True))
    old=json.loads((ROOT/'reports/kernel-entry-probe/2026-10-26-v43-r2/build.json').read_bytes())
    oldraw=(ROOT/old['candidate']['path']).read_bytes();assert B.sha(oldraw)==old['candidate']['sha256']
    rejected=False
    try:run(oldraw,old,q)
    except AssertionError:rejected=True
    assert rejected;checks.append(dict(name='old-height-negative',passed=True))
    out=dict(candidate_sha256=B.sha(raw),source_sha256=P.plan()['source_sha256'],test_sha256=B.sha(Path(__file__).read_bytes()),checks=checks,device_accessed=False,
             bytes_per_marker=256,previous_bytes_per_marker=2048,limitations=['Flat execution model; cache, IRQ timing and scanout not modeled','No claim that reduced observer traffic fixes the runtime stall'])
    a.output.write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(dict(checks=len(checks),passed=True)))


if __name__=='__main__':main()
