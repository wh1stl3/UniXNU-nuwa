"""Scoped handler observers: native instruction differential and caller fixtures."""
import hashlib,struct
from pathlib import Path
import resource_handler_sites as P
import resource_dispatch_checks as W
MODES=('normal','no-video','foreign-thread','inactive-read','inactive-wrapper','wrapper-frame','wrong-lr','inactive-handler','handler-frame','unpaired')
def source_sha256():return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
def required_names():return {f'handler:{p["site"]:#x}:{mode}' for p in P.points() for mode in MODES}|{'handler:reset','handler:missing-thread-negative'}

def setup(M,raw,b,p,mode):
    T=M.T
    u,m,sy,state,resource,dispatch=W.setup(M,raw,b,P.W.points()[0],'normal')
    wrapper=T.STACK+0x8800;frame=T.STACK+0x7800
    outer=p['phase'] in ('entry','return')
    u.mem_write(frame,struct.pack('<QQ',wrapper,P.W.AFTER+(4 if mode=='wrong-lr' else 0)))
    u.reg_write(T.UC_ARM64_REG_X29,wrapper if outer else frame)
    u.reg_write(T.UC_ARM64_REG_SP,frame+16 if outer else frame-0x40)
    u.reg_write(T.UC_ARM64_REG_LR,P.W.AFTER+(4 if mode=='wrong-lr' else 0))
    u.reg_write(T.UC_ARM64_REG_X0,0x11223344);u.reg_write(T.UC_ARM64_REG_X8,T.STOP)
    if mode=='no-video':u.mem_write(sy['probe_scratch'],struct.pack('<Q',0))
    if mode=='foreign-thread':u.reg_write(T.UC_ARM64_REG_TPIDR_EL1,T.STACK+0x4000)
    if mode=='inactive-read':u.mem_write(sy['probe_read_state'],bytes(8))
    dispatch=[wrapper+(16 if mode=='wrapper-frame' else 0),0 if mode=='inactive-wrapper' else 1]
    u.mem_write(sy['probe_resource_dispatch_state'],struct.pack('<2Q',*dispatch))
    own=[wrapper+(16 if mode=='handler-frame' else 0),0 if mode=='inactive-handler' else 1,0 if mode=='unpaired' else 511,7]
    u.mem_write(sy['probe_resource_handler_state'],struct.pack('<4Q',*own))
    return u,m,sy,state,own

def execute(M,raw,b,p,mode,original,om):
    T=M.T;site=p['site'];ref,_,_,_,_=setup(M,raw,b,p,mode)
    at=M.B.backed(om,site);ref.mem_write(site,original[at:at+4]);ref.emu_start(site,0,count=1);expected=M.D.snapshot(ref)
    u,_,sy,state,own=setup(M,raw,b,p,mode);writes=[]
    u.hook_add(T.U.UC_HOOK_MEM_WRITE,lambda u,a,pos,n,v,d:writes.append((pos,n)) if T.FB<=pos<T.FB+0x1200000 else None)
    u.hook_add(T.U.UC_HOOK_CODE,lambda u,pc,n,d:u.emu_stop() if pc==expected['pc'] else None)
    u.emu_start(site,0,count=3000000);assert M.D.snapshot(u)==expected,(hex(site),mode,'native registers')
    hit=mode in ('normal','no-video','unpaired') or p['phase']=='entry' and mode in ('inactive-handler','handler-frame')
    if mode=='unpaired' and p['returns']:hit=False
    if hit:
        if p['phase']=='entry':own=[T.STACK+0x8800,1,0,0]
        for bit in p['returns']:own[2]&=~(1<<bit)
        for bit in p['calls']:own[2]|=1<<bit
        own[3]+=1
        if p['phase']=='return':own[1]=0
        state[4:6]=[site,0x11223344]
    assert list(struct.unpack('<8Q',u.mem_read(sy['probe_result_state'],64)))==state,(hex(site),mode,'record')
    assert list(struct.unpack('<4Q',u.mem_read(sy['probe_resource_handler_state'],32)))==own,(hex(site),mode,'pairing')
    assert sum(n for pos,n in writes)==(76800 if hit and mode!='no-video' else 0),(hex(site),mode,'pixels')
    for pos,n in writes:
        y,x=divmod(pos-T.FB,T.ROW);assert (980<=y<1000 or 1008<=y<1028) and 1024<=x and x+n<=2944
    return dict(name=f'handler:{site:#x}:{mode}',passed=True)

def run(M,raw,b,original,om):
    checks=[execute(M,raw,b,p,mode,original,om) for p in P.points() for mode in MODES]
    T=M.T;p=P.points()[0];u,m,sy,_,_=setup(M,raw,b,p,'normal')
    first=M.P.D.PREVIOUS.DECOMP.PREVIOUS.FIRST
    u.mem_write(sy['probe_scratch'],bytes(8));stop=sy['probe_dense_'+format(first&0xffffffff,'x')+'_replay']
    u.hook_add(T.U.UC_HOOK_CODE,lambda u,pc,n,d:u.emu_stop() if pc==stop else None)
    u.emu_start(first,0,count=3000000)
    assert bytes(u.mem_read(sy['probe_resource_handler_state'],32))==bytes(32)
    checks.append(dict(name='handler:reset',passed=True))
    start=sy['probe_dense_'+format(P.ENTRY&0xffffffff,'x')];end=sy['probe_dense_'+format(P.ENTRY&0xffffffff,'x')+'_replay']
    ins=T.A.disasm(raw,m,start,end-start)
    index=next(i for i,v in enumerate(ins) if v.mnemonic=='mrs' and 'tpidr_el1' in v.op_str)
    branch=next(v for v in ins[index:] if v.mnemonic=='b.ne')
    bad=bytearray(raw);at=M.B.backed(m,branch.address);bad[at:at+4]=bytes.fromhex('1f2003d5')
    rejected=False
    try:execute(M,bytes(bad),b,p,'foreign-thread',original,om)
    except AssertionError:rejected=True
    assert rejected
    checks.append(dict(name='handler:missing-thread-negative',passed=True))
    return checks
