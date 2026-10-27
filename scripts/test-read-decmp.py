"""Execute compressed-read observations against displaced native instructions.

Full decompression, real locks, IRQs, timing and device execution are not modeled.
The native prefix test stops before the first IORWLockRead call body.
"""
import argparse
import importlib.util
import json
import struct
import sys
from pathlib import Path
import read_decmp_sites as P

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('decmp_model',ROOT/'scripts/test-read-dispatch-observer.py')
T=importlib.util.module_from_spec(spec);sys.modules[spec.name]=T;spec.loader.exec_module(T)
B=T.B
MODES=('normal','foreign-thread','foreign-frame','wrong-lr','outer-unpaired','unpaired','no-video','inactive','wrong-target')


def setup(raw,b,site,mode):
    m=B.macho(raw);u=T.machine(raw,m,b'',0,[],False)
    sy={k:int(v,16) for k,v in b['probe']['symbols'].items()}
    for i in range(31):u.reg_write(getattr(T,f'UC_ARM64_REG_X{i}'),T.STACK+0x4000+i*0x10)
    outer=site in (P.ENTRY,P.RET)
    apfs,caller,frame=T.STACK+0xc000,T.STACK+0xd000,T.STACK+0xb000
    u.reg_write(T.UC_ARM64_REG_X29,apfs if outer else frame)
    u.reg_write(T.UC_ARM64_REG_LR,P.CALLER+4)
    u.reg_write(T.UC_ARM64_REG_X8,T.STOP)
    u.reg_write(T.UC_ARM64_REG_SP,T.STACK+0xa000)
    u.mem_write(apfs,struct.pack('<QQ',caller,P.PREVIOUS.BODY.PREVIOUS.DISPATCH+4))
    u.mem_write(frame,struct.pack('<QQ',apfs,P.CALLER+4))
    u.mem_write(sy['probe_read_state'],struct.pack('<14Q',0 if mode=='inactive' else 1,0x1111,
                T.STACK+0x4000,0,0,caller+(16 if mode=='foreign-frame' else 0),272,
                0 if mode=='wrong-target' else P.PREVIOUS.BODY.ENTRY,0,0,0,0,0,8))
    u.reg_write(T.UC_ARM64_REG_TPIDR_EL1,0x2222 if mode=='foreign-thread' else 0x1111)
    u.mem_write(sy['probe_read_body_state'],struct.pack('<Q',0 if mode=='outer-unpaired' else 1<<8))
    u.mem_write(sy['probe_decmp_state'],struct.pack('<4Q',apfs,0 if mode=='unpaired' else (1<<33)-1,0,0))
    if mode=='wrong-lr':
        if outer:u.reg_write(T.UC_ARM64_REG_LR,T.STOP)
        else:u.mem_write(frame+8,struct.pack('<Q',T.STOP))
    u.mem_write(sy['probe_scratch'],struct.pack('<QQ',0 if mode=='no-video' else T.FB,T.ROW))
    return u,m,sy


def snapshot(u):
    return dict(registers=[u.reg_read(getattr(T,f'UC_ARM64_REG_X{i}')) for i in range(31)],
                simd=[u.reg_read(getattr(T,f'UC_ARM64_REG_Q{i}')) for i in range(32)],
                sp=u.reg_read(T.UC_ARM64_REG_SP),pc=u.reg_read(T.UC_ARM64_REG_PC),nzcv=u.reg_read(T.UC_ARM64_REG_NZCV))


def execute(raw,b,site,mode,native,original,om):
    u,m,sy=setup(raw,b,site,mode);writes=[]
    def write(u,a,p,n,v,d):
        if T.FB<=p<T.FB+0x1200000:
            y,off=divmod(p-T.FB,T.ROW)
            assert any(ry<=y<ry+16 and rx*4<=off and off+n<=(rx+32)*4 for rx,ry in [P.geometry(q['id']) for q in P.points()])
        else:writes.append((p,n))
    u.hook_add(T.U.UC_HOOK_MEM_WRITE,write)
    if native:
        at=B.backed(om,site);u.mem_write(site,original[at:at+4]);u.emu_start(site,0,count=1)
        return snapshot(u),[(p,n,bytes(u.mem_read(p,n)).hex()) for p,n in writes]
    expected,native_writes=execute(raw,b,site,mode,True,original,om)
    u.hook_add(T.U.UC_HOOK_CODE,lambda u,pc,n,d:u.emu_stop() if pc==expected['pc'] else None)
    u.emu_start(site,0,count=2000000)
    assert snapshot(u)==expected,(hex(site),mode,'native state differs')
    for p,n,value in native_writes:assert bytes(u.mem_read(p,n)).hex()==value
    active=mode in ('normal','unpaired','no-video')
    for q in (p for p in P.points() if p['site']==site):
        x,y=P.geometry(q['id']);value=struct.unpack('<I',u.mem_read(T.FB+y*T.ROW+x*4,4))[0]
        hit=active and not (mode=='unpaired' and q['phase']=='continuation')
        lit=hit and mode!='no-video'
        assert value==((0xff40c0ff if q['phase']=='call' else 0xff40ff80) if lit else 0),(q,mode,value)
        if hit:assert struct.unpack('<Q',u.mem_read(sy['probe_decmp_state']+16,8))[0]==site
    return dict(name=hex(site)+':'+mode,passed=True)


def reset(raw,b):
    u,m,sy=setup(raw,b,P.ENTRY,'normal')
    u.mem_write(sy['probe_decmp_state'],b'\xa5'*32)
    for q in P.points():
        x,y=P.geometry(q['id']);u.mem_write(T.FB+y*T.ROW+x*4,b'\xa5'*128)
        u.mem_write(sy['probe_flags']+128+q['id'],b'\x01')
    stop=m['symbols']['_vn_rdwr']
    u.hook_add(T.U.UC_HOOK_CODE,lambda u,pc,n,d:u.emu_stop() if pc==stop else None)
    u.emu_start(P.PREVIOUS.FIRST,0,count=2000000)
    assert u.reg_read(T.UC_ARM64_REG_PC)==stop and bytes(u.mem_read(sy['probe_decmp_state'],32))==bytes(32)
    for q in P.points():
        x,y=P.geometry(q['id']);assert bytes(u.mem_read(T.FB+y*T.ROW+x*4,128))==bytes(128)
        assert bytes(u.mem_read(sy['probe_flags']+128+q['id'],1))==bytes(1)


def prefix(raw,b,original,om,native=False):
    u,m,sy=setup(raw,b,P.ENTRY,'normal')
    # A real prologue/current_act path with mapped structures. Owner differs,
    # so stop at the actual first IORWLockRead boundary without faking its result.
    args,cp,uio=T.STACK+0x5000,T.STACK+0x6000,T.STACK+0x7000
    u.reg_write(T.UC_ARM64_REG_X0,args);u.reg_write(T.UC_ARM64_REG_X2,cp)
    u.mem_write(args,struct.pack('<5Q',0,T.STACK+0x4000,uio,8,0))
    u.mem_write(cp+16,struct.pack('<Q',0x3333))
    if native:
        for q in P.points():
            pc=q['site'];at=B.backed(om,pc);u.mem_write(pc,original[at:at+4])
    stop=m['symbols']['_IORWLockRead']
    u.hook_add(T.U.UC_HOOK_CODE,lambda u,pc,n,d:u.emu_stop() if pc==stop else None)
    u.emu_start(P.ENTRY,0,count=2000000)
    assert u.reg_read(T.UC_ARM64_REG_PC)==stop
    assert u.reg_read(T.UC_ARM64_REG_X0)==cp+0x38
    if not native:
        for idx in (373,374,375,376):
            x,y=P.geometry(idx);value=struct.unpack('<I',u.mem_read(T.FB+y*T.ROW+x*4,4))[0]
            assert value==(0xff40c0ff if idx in (374,376) else 0xff40ff80)
    # Compare the saved frame and initialized locals, not untouched allocation
    # bytes. A pre-prologue observer may leave scratch in those undefined slots.
    defined=((0x78,0x38),(0xb8,8),(0xc4,4),(0xd0,0x60))
    return snapshot(u),[bytes(u.mem_read(T.STACK+0xa000-0x130+off,n)).hex() for off,n in defined]


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    assert not a.output.exists()
    b=json.loads(a.build.read_bytes());raw=(ROOT/b['candidate']['path']).read_bytes()
    assert b['probe_revision'] in (42,43,44,45,46,47,48,49) and B.sha(raw)==b['candidate']['sha256'] and b['read_decmp']==P.plan()
    original=B.INPUT.read_bytes();assert B.sha(original)==B.EXPECTED;om=B.macho(original)
    def layout_ok(rects):
        reserved=((0,256,192,544),(256,224,480,664),(832,224,608,816))
        for x,y,w,h in rects:
            if x<0 or y<200 or x+w>1440 or y+h>1040:return False
            if any(x<rx+rw and rx<x+w and y<ry+rh and ry<y+h for rx,ry,rw,rh in reserved):return False
        return True
    rects=[(*P.geometry(p['id']),32,16) for p in P.points()]
    assert layout_ok(rects)
    edges={e['id']:e for e in b['dense_bootstrap']['edges']}
    assert all((edges[p['id']]['x'],edges[p['id']]['y'])==P.geometry(p['id']) for p in P.points())
    assert not layout_ok([(32+(i%4)*48,256+(i//4)*24,32,16) for i in range(68)])
    checks=[dict(name='layout-no-overlap',passed=True),dict(name='old-layout-negative',passed=True)]
    for site in sorted({p['site'] for p in P.points()}):
        for mode in MODES:checks.append(execute(raw,b,site,mode,False,original,om))
        if len(checks)%90==0:print(json.dumps(dict(progress=len(checks))),flush=True)
    reset(raw,b);checks.append(dict(name='header-reset',passed=True))
    assert prefix(raw,b,original,om)==prefix(raw,b,original,om,True)
    checks.append(dict(name='native-prefix',passed=True))
    m=B.macho(raw);sy=b['probe']['symbols'];site=P.ENTRY+P.CALL_OFFSETS[0]+4
    start=int(sy[f'probe_dense_{site&0xffffffff:x}'],16);end=int(sy[f'probe_dense_{site&0xffffffff:x}_replay'],16)
    branch=next(i for i in T.A.disasm(raw,m,start,end-start) if i.mnemonic=='tbz' and i.op_str.startswith('w13, #0,'))
    changed=bytearray(raw);at=B.backed(m,branch.address);changed[at:at+4]=bytes.fromhex('1f2003d5')
    rejected=False
    try:execute(bytes(changed),b,site,'unpaired',False,original,om)
    except AssertionError:rejected=True
    assert rejected;checks.append(dict(name='missing-pair-negative',passed=True))
    out=dict(candidate_sha256=B.sha(raw),source_sha256=P.plan()['source_sha256'],test_sha256=B.sha(Path(__file__).read_bytes()),checks=checks,
             device_accessed=False,complete_decompression_executed=False,
             limitations=['Single instruction comparisons and real prologue/current_act only','First lock body not executed; no native lock, cache, fetch, IRQ or hardware qualification'])
    a.output.write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(checks=len(checks),passed=True)))


if __name__=='__main__':main()
