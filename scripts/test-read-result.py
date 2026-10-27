"""Actual result hooks, native return/CBZ paths, stale-state and scope negatives.

Allocator output is a supplied fixture, never a claim that heap allocation ran.
"""
import argparse,importlib.util,json,struct,sys
from pathlib import Path
import read_result_sites as P
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('result_deep_model',ROOT/'scripts/test-read-deep.py')
M=importlib.util.module_from_spec(spec);sys.modules[spec.name]=M;spec.loader.exec_module(M)
F=M.F;T=M.T;B=M.B;MASK=(1<<64)-1
MODES=(*M.MODES,'unarmed','wrong-owner')
SITES=tuple(p['site'] for p in P.points())+(P.CONTINUATION,P.PREVIOUS.MALLOC_RET)
EXTRA=('header-reset','layout','first-allocation-excluded','native-null-return','native-nonnull-return','missing-pair-negative')

def required_names():return {hex(site)+':'+mode for site in SITES for mode in MODES}|set(EXTRA)

def setup(raw,b,site,mode):
    inner_mode='normal' if mode in ('unarmed','wrong-owner') else mode
    if site==P.PREVIOUS.MALLOC_RET:u,m,sy=M.setup(raw,b,site,inner_mode)
    else:u,m,sy=F.setup(raw,b,P.CONTINUATION,inner_mode)
    cb=T.STACK+0xf000
    u.reg_write(T.UC_ARM64_REG_X0,T.STACK+0x6000);u.reg_write(T.UC_ARM64_REG_X24,40)
    u.mem_write(cb-0x98,struct.pack('<I',0x1cc))
    state=[cb+(16 if mode=='wrong-owner' else 0),40,MASK,MASK,0,0x1cc,0 if mode=='unpaired' else 3,0 if mode=='unarmed' else 1]
    u.mem_write(sy['probe_result_state'],struct.pack('<8Q',*state))
    return u,m,sy,state

def execute(raw,b,site,mode,original,om):
    ref,_,_,_=setup(raw,b,site,mode);at=B.backed(om,site);ref.mem_write(site,original[at:at+4]);stores=[]
    ref.hook_add(T.U.UC_HOOK_MEM_WRITE,lambda u,a,p,n,v,d:stores.append((p,n)))
    ref.emu_start(site,0,count=1);expected=M.snapshot(ref)
    u,m,sy,state=setup(raw,b,site,mode);before=state[:];writes=[]
    u.hook_add(T.U.UC_HOOK_MEM_WRITE,lambda u,a,p,n,v,d:writes.append((p,n)) if T.FB<=p<T.FB+0x1200000 else None)
    u.hook_add(T.U.UC_HOOK_CODE,lambda u,pc,n,d:u.emu_stop() if pc==expected['pc'] else None)
    u.emu_start(site,0,count=3000000);assert M.snapshot(u)==expected,(hex(site),mode,'native state')
    for p,n in stores:assert bytes(u.mem_read(p,n))==bytes(ref.mem_read(p,n))
    p=next((p for p in P.points() if p['site']==site),None)
    hit=mode in ('normal','unpaired','no-video') or site==P.REQUEST and mode in ('unarmed','wrong-owner')
    if p and p['phase']=='continuation' and mode=='unpaired':hit=False
    if hit:
        if site==P.REQUEST:state=[T.STACK+0xf000,40,MASK,MASK,site,0x1cc,0,1]
        else:
            state[4]=site
            if site==P.CONTINUATION:state[3]=T.STACK+0x6000
            if site==P.PREVIOUS.MALLOC_RET:state[2]=T.STACK+0x6000
            if p and p['pair'] is not None:
                if p['phase']=='call':state[6]|=1<<p['pair']
                else:state[6]&=~(1<<p['pair'])
    assert list(struct.unpack('<8Q',bytes(u.mem_read(sy['probe_result_state'],64))))==state,(hex(site),mode,'recorded values',before,state)
    fields=(8,16,24,32,40) if site==P.REQUEST else (24,32) if site==P.CONTINUATION else (16,32) if site==P.PREVIOUS.MALLOC_RET else (32,)
    lit=hit and mode!='no-video';field_writes=[]
    for address,n in writes:
        y,offset=divmod(address-T.FB,T.ROW)
        if y>=896 and 1024<=offset<2944:
            assert any(896+i*28<=y<916+i*28 and off in fields for i,(off,_) in enumerate(P.FIELDS))
            assert offset+n<=2944;field_writes.append((address,n))
    assert sum(n for _,n in field_writes)==38400*len(fields)*(1 if lit else 0),(hex(site),mode,'field writes')
    if lit:
        for i,(off,_) in enumerate(P.FIELDS):
            if off in fields:assert T.field(u,0xa03a+i)==state[off//8]
    if p:
        x,y=P.geometry(p['id']);color=0xffffc040 if p['phase']=='call' else 0xffffffff if p['phase']=='continuation' else 0xffff40ff
        for row in range(2):assert bytes(u.mem_read(T.FB+(y+row)*T.ROW+x*4,128))==(struct.pack('<I',color)*32 if lit else bytes(128))
    return dict(name=hex(site)+':'+mode,passed=True)

def reset(raw,b):
    u,m,sy,_=setup(raw,b,P.REQUEST,'normal');u.mem_write(sy['probe_result_state'],b'\xa5'*64)
    for p in P.points():u.mem_write(sy['probe_flags']+128+p['id'],b'\x01')
    stop=m['symbols']['_vn_rdwr'];u.hook_add(T.U.UC_HOOK_CODE,lambda u,pc,n,d:u.emu_stop() if pc==stop else None)
    u.emu_start(P.F.DECOMP.PREVIOUS.FIRST,0,count=4000000);assert u.reg_read(T.UC_ARM64_REG_PC)==stop
    assert struct.unpack('<8Q',bytes(u.mem_read(sy['probe_result_state'],64)))==(0,0,MASK,MASK,0,0,0,0)
    for tag,value in zip(range(0xa03a,0xa03f),(0,MASK,MASK,0,0)):assert T.field(u,tag)==value
    for p in P.points():
        x,y=P.geometry(p['id']);assert bytes(u.mem_read(sy['probe_flags']+128+p['id'],1))==b'\0'
        assert bytes(u.mem_read(T.FB+y*T.ROW+x*4,128))==bytes(128)

def suffix(raw,b,original,om,value,native=False):
    u,m,sy,_=setup(raw,b,P.PREVIOUS.MALLOC_RET,'normal');cb=T.STACK+0xf000;sp=cb-0xf0-0x30
    u.reg_write(T.UC_ARM64_REG_SP,sp);u.reg_write(T.UC_ARM64_REG_X29,sp+0x20);u.reg_write(T.UC_ARM64_REG_X20,value)
    u.mem_write(sp,struct.pack('<6Q',0x22,0x21,0x20,0x19,cb,P.CONTINUATION))
    u.reg_write(T.UC_ARM64_REG_X24,40)
    if native:
        for patch in b['patches']:
            if patch['va'] is None:continue
            site=int(patch['va'],16) if isinstance(patch['va'],str) else patch['va']
            if P.F.CALLBACK<=site<P.F.CALLBACK+0x480 or P.PREVIOUS.MALLOC<=site<=P.PREVIOUS.MALLOC_RET:
                at=B.backed(om,site);u.mem_write(site,original[at:at+4])
    stop=P.F.CALLBACK+(0x208 if value==0 else 0x1c4)
    u.hook_add(T.U.UC_HOOK_CODE,lambda u,pc,n,d:u.emu_stop() if pc==stop else None)
    u.emu_start(P.PREVIOUS.MALLOC+0xdc,0,count=3000000)
    assert u.reg_read(T.UC_ARM64_REG_PC)==stop
    if not native:
        assert T.field(u,0xa03b)==value and T.field(u,0xa03c)==value
    return M.snapshot(u),bytes(u.mem_read(T.STACK+0x6000,16))

def main():
    cli=argparse.ArgumentParser();cli.add_argument('--build',type=Path,required=True);cli.add_argument('--output',type=Path,required=True);a=cli.parse_args();assert not a.output.exists()
    b=json.loads(a.build.read_bytes());raw=(ROOT/b['candidate']['path']).read_bytes();assert b['probe_revision'] in (47,48,49) and b['read_result']==P.plan() and B.sha(raw)==b['candidate']['sha256']
    original=B.INPUT.read_bytes();assert B.sha(original)==B.EXPECTED;om=B.macho(original)
    checks=[execute(raw,b,site,mode,original,om) for site in SITES for mode in MODES]
    reset(raw,b);checks.append(dict(name='header-reset',passed=True))
    old=[(*P.PREVIOUS.geometry(q['id']),32,2) for q in P.PREVIOUS.points()]+[(*P.F.geometry(q['id']),32,2) for q in P.F.points()]+[(*P.F.DECOMP.geometry(q['id']),32,2) for q in P.F.DECOMP.points()]+[(0,256,192,544),(256,224,480,664),(832,224,608,816)]
    new=[(*P.geometry(q['id']),32,2) for q in P.points()]+[(256,y,480,20) for y in (896,924,952,980,1008)]
    for i,(x,y,w,h) in enumerate(new):
        assert 0<=x and x+w<=1440 and 0<=y and y+h<=1040
        assert not any(x<rx+rw and rx<x+w and y<ry+rh and ry<y+h for rx,ry,rw,rh in old+new[:i])
    checks.append(dict(name='layout',passed=True))
    u,m,sy,state=setup(raw,b,P.PREVIOUS.MALLOC_RET,'normal');u.reg_write(T.UC_ARM64_REG_LR,P.F.CALLBACK+0x144)
    stop=P.F.CALLBACK+0x144;u.hook_add(T.U.UC_HOOK_CODE,lambda u,pc,n,d:u.emu_stop() if pc==stop else None);u.emu_start(P.PREVIOUS.MALLOC_RET,0,count=2000000)
    assert bytes(u.mem_read(sy['probe_result_state'],64))==struct.pack('<8Q',*state);checks.append(dict(name='first-allocation-excluded',passed=True))
    for name,value in (('native-null-return',0),('native-nonnull-return',T.STACK+0x6000)):
        assert suffix(raw,b,original,om,value)==suffix(raw,b,original,om,value,True);checks.append(dict(name=name,passed=True))
    site=P.F.CALLBACK+0x228;start=int(b['probe']['symbols'][f'probe_dense_{site&0xffffffff:x}'],16);end=int(b['probe']['symbols'][f'probe_dense_{site&0xffffffff:x}_replay'],16)
    ins=next(i for i in T.A.disasm(raw,B.macho(raw),start,end-start) if i.mnemonic=='tbz' and i.op_str.startswith('w10, #1,'))
    bad=bytearray(raw);at=B.backed(B.macho(raw),ins.address);bad[at:at+4]=bytes.fromhex('1f2003d5');rejected=False
    try:execute(bytes(bad),b,site,'unpaired',original,om)
    except AssertionError:rejected=True
    assert rejected;checks.append(dict(name='missing-pair-negative',passed=True))
    assert {c['name'] for c in checks}==required_names()
    a.output.write_text(json.dumps(dict(candidate_sha256=B.sha(raw),source_sha256=P.plan()['source_sha256'],test_sha256=B.sha(Path(__file__).read_bytes()),checks=checks,device_accessed=False,limitations=['Allocator result supplied to actual native epilogue; allocation and printf bodies not executed','No hardware timing, IRQ or user-mode claim']),indent=2)+'\n')
    print(json.dumps(dict(checks=len(checks),passed=True)))

if __name__=='__main__':main()
