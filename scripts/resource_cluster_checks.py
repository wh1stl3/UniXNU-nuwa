"""Scoped handler observers: native instruction differential and caller fixtures."""
import hashlib,struct
from pathlib import Path
import resource_cluster_sites as P
import resource_dispatch_checks as W
MODES=('normal','no-video','foreign-thread','inactive-read','inactive-wrapper','wrapper-frame','wrong-lr','inactive-handler','handler-frame','unpaired','parent-lr','parent-unpaired')
def source_sha256():return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
def required_names():return {f'cluster:{p["site"]:#x}:{mode}' for p in P.points() for mode in MODES}|{'cluster:reset','cluster:missing-thread-negative'}|{f'cluster-continuity:{case}:{mode}' for case in CONTINUITY_CASES for mode in ('normal','no-video')}|{'cluster:ubc-vm-native-outside-hooks'}

def setup(M,raw,b,p,mode):
    T=M.T;spec=P.spec_for(p)
    u,m,sy,state,resource,dispatch=W.setup(M,raw,b,P.H.H.W.points()[0],'normal')
    caller=T.STACK+0x8800;frame=T.STACK+0x7800;grand=T.STACK+0x9800
    outer=p['phase'] in ('entry','return');lr=P.BASE+spec['lr']
    u.mem_write(caller,struct.pack('<QQ',grand,spec['parent_lr']+(4 if mode=='parent-lr' else 0)))
    u.mem_write(frame,struct.pack('<QQ',caller,lr+(4 if mode=='wrong-lr' else 0)))
    u.reg_write(T.UC_ARM64_REG_X29,caller if outer else frame)
    u.reg_write(T.UC_ARM64_REG_SP,frame+16 if outer else frame-spec['frame'])
    u.reg_write(T.UC_ARM64_REG_LR,lr+(4 if mode=='wrong-lr' else 0))
    if p.get('value')=='x19':u.reg_write(T.UC_ARM64_REG_X19,12)
    u.reg_write(T.UC_ARM64_REG_X0,T.STACK+0xa000);u.reg_write(T.UC_ARM64_REG_X8,T.STOP)
    if mode=='no-video':u.mem_write(sy['probe_scratch'],struct.pack('<Q',0))
    if mode=='foreign-thread':u.reg_write(T.UC_ARM64_REG_TPIDR_EL1,T.STACK+0x4000)
    if mode=='inactive-read':u.mem_write(sy['probe_read_state'],bytes(8))
    parent=[grand+(16 if mode=='wrapper-frame' else 0),0 if mode=='inactive-wrapper' else 1,0 if mode=='parent-unpaired' else 1<<spec['parent_bit'],0]
    u.mem_write(sy[P.state_name(spec['parent'])],struct.pack('<4Q',*parent))
    own=[caller+(16 if mode=='handler-frame' else 0),0 if mode=='inactive-handler' else 1,0 if mode=='unpaired' else (1<<len(spec['calls']))-1,7]
    u.mem_write(sy[P.state_name(p['group'])],struct.pack('<4Q',*own))
    return u,m,sy,state,own

def execute(M,raw,b,p,mode,original,om):
    T=M.T;site=p['site'];ref,_,_,_,_=setup(M,raw,b,p,mode)
    value=p.get('value','x0')
    sampled=((ref.reg_read(T.UC_ARM64_REG_X20)&0xffffffff)<<32)|(ref.reg_read(T.UC_ARM64_REG_X8)&0xffffffff) if value=='request_residual' else ref.reg_read(getattr(T,'UC_ARM64_REG_'+value.upper()))
    provenance=[ref.reg_read(T.UC_ARM64_REG_X20),ref.reg_read(T.UC_ARM64_REG_X9),
                struct.unpack('<i',ref.mem_read(P.BASE+0x9feca8,4))[0]&((1<<64)-1)] if p['offset']==0x46e570 else None
    at=M.B.backed(om,site);ref.mem_write(site,original[at:at+4])
    try:ref.emu_start(site,0,count=1)
    except T.U.UcError as error:raise AssertionError((hex(site),mode,'native reference instruction failed',original[at:at+4].hex())) from error
    expected=M.D.snapshot(ref)
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
        state[4:6]=[site,sampled]
        if provenance is not None:state[1:4]=provenance
    assert list(struct.unpack('<8Q',u.mem_read(sy['probe_result_state'],64)))==state,(hex(site),mode,'record')
    assert list(struct.unpack('<4Q',u.mem_read(sy[P.state_name(p['group'])],32)))==own,(hex(site),mode,'pairing')
    extra=0
    if P.G.ENABLED and P.G.selected(p):
        flags=0;wide=0;strict=0
        if mode not in ('foreign-thread','inactive-read'):
            flags=1<<9
            if p['offset']==0x43cb90:flags|=1<<11;wide=T.STACK+0xa000
            if p['offset']==P.G.CALLER_ENTRY:
                wide=P.BASE+P.spec_for(p)['lr']+(4 if mode=='wrong-lr' else 0)
                flags|=1<<P.G.caller_bit(wide)
            def pixels(bits):return 24*(bits&255).bit_count()+32*((bits>>8)&1023).bit_count()
            extra+=pixels(flags)
            if hit:
                flags|=1<<8
                if p['offset']==0x43cb90:flags|=1<<13;strict=T.STACK+0xa000
            else:
                reason={'inactive-wrapper':0,'parent-unpaired':1,'wrong-lr':2,'wrapper-frame':3,'parent-lr':4,'inactive-handler':5,'handler-frame':6,'unpaired':7}[mode]
                flags|=1<<reason
            extra+=pixels(flags)
        slot=P.G.OFFSETS.index(p['offset'])*32
        assert struct.unpack('<4Q',u.mem_read(sy[P.G.SYMBOL]+slot,32))==(flags,wide,strict,flags if mode!='no-video' else 0),(hex(site),mode,'gate diagnostics')
    hex_bytes=192000 if provenance is not None else 76800
    assert sum(n for pos,n in writes)==((extra+((576 if P.live_tile(p) else 0)+(hex_bytes if P.show_hex(p) else 0) if hit else 0)) if mode!='no-video' else 0),(hex(site),mode,'pixels')
    tx,ty=P.geometry(p)
    for pos,n in writes:
        y,x=divmod(pos-T.FB,T.ROW)
        rows=(896,924,952,980,1008) if provenance is not None else (980,1008)
        assert (ty<=y<ty+6 and tx*4<=x and x+n<=(tx+24)*4) or (P.show_hex(p) and any(row<=y<row+20 for row in rows) and 1024<=x and x+n<=2944) or (P.G.selected(p) and any(ry<=y<ry+rh and rx*4<=x and x+n<=(rx+rw)*4 for rx,ry,rw,rh in P.G.rectangles(p,P.geometry)))
    return dict(name=f'cluster:{site:#x}:{mode}',passed=True)


# Explicit VM-boundary fixtures: exercise native helper, epilogue and caller
# together. They do not qualify actual VM cache contents or physical IO.
CONTINUITY_CASES={
    'null-object':(8,0,0,False),
    'zero-request':(0,0,0,True),
    'cache-miss':(8,0,0,True),
    'partial-copy':(8,3,0,True),
    'complete-copy':(8,8,0,True),
    'native-error':(8,0,5,True),
}

def continuity(M,raw,b,original,om,case,mode,native):
    T=M.T;requested,copied,error,object_present=CONTINUITY_CASES[case]
    p=next(p for p in P.points() if p['site']==P.BASE+0x438c34)
    u,m,sy,state,own=setup(M,raw,b,p,mode)
    fp=u.reg_read(T.UC_ARM64_REG_X29);uio=T.STACK+0xb000;obj=T.STACK+0xc000
    u.reg_write(T.UC_ARM64_REG_X1,uio);u.reg_write(T.UC_ARM64_REG_X2,fp-0x60)
    u.reg_write(T.UC_ARM64_REG_X3,0);u.reg_write(T.UC_ARM64_REG_X4,1)
    u.reg_write(T.UC_ARM64_REG_X20,requested)
    u.mem_write(fp-0x60,struct.pack('<I',requested))
    u.mem_write(uio+0x18,struct.pack('<Q',0))
    u.mem_write(uio+0x20,struct.pack('<I',2))
    u.mem_write(uio+0x28,struct.pack('<Q',requested))
    if native:
        for point in P.points():
            at=M.B.backed(om,point['site']);u.mem_write(point['site'],original[at:at+4])
    trace=[];moves=[]
    def hook(u,pc,n,d):
        if pc in (P.BASE+0x438c34,P.BASE+0x43cb58,P.BASE+0x43cc74,P.BASE+0x438c38,P.BASE+0x438c3c):trace.append(pc)
        if pc==P.BASE+0x6fa47c:
            u.reg_write(T.UC_ARM64_REG_X0,obj if object_present else 0)
            u.reg_write(T.UC_ARM64_REG_PC,u.reg_read(T.UC_ARM64_REG_LR))
        if pc==P.BASE+0x3005cc:
            assert u.reg_read(T.UC_ARM64_REG_X0)==obj and u.reg_read(T.UC_ARM64_REG_X2)==uio
            assert u.reg_read(T.UC_ARM64_REG_X4)==requested
            moves.append(requested)
            u.mem_write(uio+0x18,struct.pack('<Q',copied))
            u.mem_write(uio+0x28,struct.pack('<Q',requested-copied))
            u.reg_write(T.UC_ARM64_REG_X0,error)
            u.reg_write(T.UC_ARM64_REG_PC,u.reg_read(T.UC_ARM64_REG_LR))
        if pc==P.BASE+0x438c40:u.emu_stop()
    u.hook_add(T.U.UC_HOOK_CODE,hook)
    u.emu_start(p['site'],0,count=12000000)
    assert u.reg_read(T.UC_ARM64_REG_PC)==P.BASE+0x438c40
    assert trace==[P.BASE+x for x in (0x438c34,0x43cb58,0x43cc74,0x438c38,0x438c3c)]
    assert len(moves)==int(object_present and requested!=0)
    residual=struct.unpack('<I',u.mem_read(fp-0x60,4))[0]
    assert residual==requested-copied and u.reg_read(T.UC_ARM64_REG_X0)==error
    if not native:
        record=struct.unpack('<8Q',u.mem_read(sy['probe_result_state'],64))
        assert record[4:6]==(P.BASE+0x438c3c,(requested<<32)|residual)
        pair=struct.unpack('<4Q',u.mem_read(sy[P.state_name('clustercopy')],32))
        assert pair[2]&1==0
    return M.D.snapshot(u),bytes(u.mem_read(uio,48)),residual

def run(M,raw,b,original,om):
    checks=[execute(M,raw,b,p,mode,original,om) for p in P.points() for mode in MODES]
    T=M.T;p=P.points()[0];u,m,sy,_,_=setup(M,raw,b,p,'normal')
    first=M.P.D.PREVIOUS.DECOMP.PREVIOUS.FIRST
    for spec in P.SPECS:u.mem_write(sy[P.state_name(spec['name'])],b'\xff'*32)
    u.mem_write(sy['probe_scratch'],bytes(8));stop=sy['probe_dense_'+format(first&0xffffffff,'x')+'_replay']
    u.hook_add(T.U.UC_HOOK_CODE,lambda u,pc,n,d:u.emu_stop() if pc==stop else None)
    u.emu_start(first,0,count=3000000)
    for spec in P.SPECS:assert bytes(u.mem_read(sy[P.state_name(spec['name'])],32))==bytes(32)
    checks.append(dict(name='cluster:reset',passed=True))
    start=sy['probe_dense_'+format(p['site']&0xffffffff,'x')];end=sy['probe_dense_'+format(p['site']&0xffffffff,'x')+'_replay']
    ins=T.A.disasm(raw,m,start,end-start)
    index=next(i for i,v in enumerate(ins) if v.mnemonic=='mrs' and 'tpidr_el1' in v.op_str)
    branch=next(v for v in ins[index:] if v.mnemonic=='b.ne')
    bad=bytearray(raw);at=M.B.backed(m,branch.address);bad[at:at+4]=bytes.fromhex('1f2003d5')
    rejected=False
    try:execute(M,bytes(bad),b,p,'foreign-thread',original,om)
    except AssertionError:rejected=True
    assert rejected
    checks.append(dict(name='cluster:missing-thread-negative',passed=True))
    for case in CONTINUITY_CASES:
        for mode in ('normal','no-video'):
            actual=continuity(M,raw,b,original,om,case,mode,False)
            reference=continuity(M,raw,b,original,om,case,mode,True)
            assert actual==reference,(case,mode,'native helper and caller continuity')
            checks.append(dict(name=f'cluster-continuity:{case}:{mode}',passed=True))
    m=M.B.macho(raw)
    hooked={p['site'] for p in P.points()}
    for start,size in ((P.BASE+0x43cb58,0x124),(P.BASE+0x3005cc,0x6d0)):
        for pc in range(start,start+size,4):
            if pc not in hooked:
                assert raw[M.B.backed(m,pc):M.B.backed(m,pc)+4]==original[M.B.backed(om,pc):M.B.backed(om,pc)+4],hex(pc)

    checks.append(dict(name='cluster:ubc-vm-native-outside-hooks',passed=True))
    return checks
