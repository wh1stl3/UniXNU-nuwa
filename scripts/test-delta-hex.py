"""Compare every pixel against PROBE39's renderer, including spacing/borders.

Flat execution proves output and write-volume changes, not hardware timing.
"""
import argparse,importlib.util,json,struct,sys
from pathlib import Path
import probe_delta_hex as P
ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('delta_shared_model',ROOT/'scripts/test-shared-hex.py')
S=importlib.util.module_from_spec(s);sys.modules[s.name]=S;s.loader.exec_module(S)
T=S.T;B=S.B;MASK=(1<<64)-1
ROWS=tuple(range(1088,1985,32))
EXTRA=('legacy-counter','unaligned-legacy','no-video-state-unchanged','header-result-reset','invalid-validity-redraw','commit-after-drawing','missing-glyph-negative','native-scratch-registers')
def required_names():return {f'pixels-and-delta-{row}' for row in ROWS}|set(EXTRA)

def load(path):
    b=json.loads(path.read_bytes());raw=(ROOT/b['candidate']['path']).read_bytes();assert B.sha(raw)==b['candidate']['sha256']
    return b,raw,B.macho(raw),{k:int(v,16) for k,v in b['probe']['symbols'].items()}

def machine(data,row):
    b,raw,m,sy=data;u=T.machine(raw,m,b'',0,[],False)
    y=224+((row-1088)//32)*28 if row>=1088 else 756
    base=T.FB+(y-1)*T.ROW;u.mem_write(base,b'\xa5'*(22*T.ROW))
    u.hook_add(T.U.UC_HOOK_CODE,lambda u,pc,n,d:u.emu_stop() if pc==T.STOP else None)
    return u,sy,y,base

def step(u,sy,row,value,y,base):
    for reg,val in ((T.UC_ARM64_REG_X21,T.FB),(T.UC_ARM64_REG_X22,T.ROW),(T.UC_ARM64_REG_X23,value),(T.UC_ARM64_REG_X24,row),(T.UC_ARM64_REG_LR,T.STOP)):
        u.reg_write(reg,val)
    preserved={reg:u.reg_read(reg) for reg in [*[getattr(T,f'UC_ARM64_REG_X{i}') for i in range(9)],T.UC_ARM64_REG_X18,T.UC_ARM64_REG_X29,T.UC_ARM64_REG_LR,T.UC_ARM64_REG_SP]}
    writes=[]
    def store(u,a,p,n,v,d):
        if T.FB<=p<T.FB+0x1200000:
            yy,off=divmod(p-T.FB,T.ROW)
            assert y<=yy<y+20 and 1024<=off and off+n<=2944 and n in (4,8) and p%4==0,(row,hex(p),n,yy,off)
            writes.append((p,n))
    hook=u.hook_add(T.U.UC_HOOK_MEM_WRITE,store)
    u.emu_start(sy['probe_hex_shared'],0,count=200000)
    u.hook_del(hook);assert u.reg_read(T.UC_ARM64_REG_PC)==T.STOP
    assert all(u.reg_read(reg)==v for reg,v in preserved.items())
    return bytes(u.mem_read(base,22*T.ROW)),sum(n for _,n in writes)

def sequence(candidate,reference,row):
    actual=machine(candidate,row);native=machine(reference,row)
    values=[0,0,MASK,0x0123456789abcdef,0xfedcba9876543210,0x8000000000000001]
    # Every nibble position changes independently, then returns to zero.
    values += [0]+[1<<(4*i) for i in range(16)]+[0,MASK]
    total_new=total_old=0;previous=None
    for value in values:
        a=step(*actual[:2],row,value,*actual[2:]);r=step(*native[:2],row,value,*native[2:])
        assert a[0]==r[0],(row,hex(value),'pixels or border')
        expected=38400 if previous is None else 1920*sum(((previous^value)>>(4*i))&15!=0 for i in range(16))
        assert a[1]==expected,(row,hex(value),a[1],expected)
        total_new+=a[1];total_old+=r[1];previous=value
    assert total_new<total_old
    return dict(name=f'pixels-and-delta-{row}',passed=True,candidate_bytes=total_new,reference_bytes=total_old,updates=len(values))

def main():
    cli=argparse.ArgumentParser();cli.add_argument('--build',type=Path,required=True);cli.add_argument('--output',type=Path,required=True);a=cli.parse_args();assert not a.output.exists()
    d=load(a.build);b,raw,m,sy=d;assert b['probe_revision'] in (48,49) and b['delta_hex']==P.plan()
    old=load(ROOT/'reports/kernel-entry-probe/2026-10-27-v47-r2/build.json')
    checks=[sequence(d,old,row) for row in ROWS]
    for name,row in (('legacy-counter',784),('unaligned-legacy',1089)):
        u=machine(d,row);v=machine(old,row)
        for value in (0,MASK,0x0123456789abcdef):assert step(*u[:2],row,value,*u[2:])==step(*v[:2],row,value,*v[2:])
        checks.append(dict(name=name,passed=True))
    sd=S.data(a.build);u=T.machine(raw,m,b'',0,[],False);before=b'\xa5'*464;u.mem_write(sy['probe_hex_delta_cache'],before)
    u.mem_write(sy['probe_scratch'],struct.pack('<QQ',0,T.ROW));stop=sd[5]
    u.hook_add(T.U.UC_HOOK_CODE,lambda u,pc,n,d:u.emu_stop() if pc==stop else None);u.emu_start(sd[4],0,count=100000)
    assert bytes(u.mem_read(sy['probe_hex_delta_cache'],464))==before;checks.append(dict(name='no-video-state-unchanged',passed=True))
    S.reset(sd);checks.append(dict(name='header-result-reset',passed=True))
    row=1728;u=machine(d,row);v=machine(old,row);slot=sy['probe_hex_delta_cache']+(row-1088)//32*16
    u[0].mem_write(slot,struct.pack('<QQ',MASK,2))
    assert step(*u[:2],row,MASK,*u[2:])==step(*v[:2],row,MASK,*v[2:]);checks.append(dict(name='invalid-validity-redraw',passed=True))
    u,us,y,base=machine(d,row)
    u.reg_write(T.UC_ARM64_REG_X21,T.FB);u.reg_write(T.UC_ARM64_REG_X22,T.ROW);u.reg_write(T.UC_ARM64_REG_X23,MASK);u.reg_write(T.UC_ARM64_REG_X24,row)
    seen=[]
    def interrupt(u,a,p,n,value,data):
        if T.FB<=p<T.FB+0x1200000:
            seen.append(bytes(u.mem_read(slot,16)));u.emu_stop()
    u.hook_add(T.U.UC_HOOK_MEM_WRITE,interrupt);u.emu_start(sy['probe_hex_shared'],0,count=200000)
    assert seen and all(v==bytes(16) for v in seen);checks.append(dict(name='commit-after-drawing',passed=True))
    ins=next(i for i in T.A.disasm(raw,m,sy['probe_hex_shared'],sy['probe_hex_shared_end']-sy['probe_hex_shared']) if i.mnemonic=='lsr' and i.op_str=='x23, x19, x20')
    bad=bytearray(raw);at=B.backed(m,ins.address);bad[at:at+4]=bytes.fromhex('f7031faa') # mov x23,xzr
    rejected=False
    try:sequence((b,bytes(bad),m,sy),old,row)
    except AssertionError:rejected=True
    assert rejected;checks.append(dict(name='missing-glyph-negative',passed=True))
    checks.append(dict(name='native-scratch-registers',passed=True,scope='X0-X8,X18,X29,LR,SP preserved in every direct helper call; full hooks checked separately'))
    assert {c['name'] for c in checks}==required_names()
    total=sum(c.get('candidate_bytes',0) for c in checks);ref=sum(c.get('reference_bytes',0) for c in checks)
    a.output.write_text(json.dumps(dict(candidate_sha256=B.sha(raw),source_sha256=P.plan()['source_sha256'],test_sha256=B.sha(Path(__file__).read_bytes()),reference_candidate_sha256=old[0]['candidate']['sha256'],checks=checks,sequence_bytes=dict(candidate=total,reference=ref),device_accessed=False,limitations=['Software pixels/write volume only; no hardware timing, cache, IRQ or scanout proof','No native filesystem or userspace execution claim']),indent=2)+'\n')
    print(json.dumps(dict(checks=len(checks),passed=True,sequence_bytes=total,reference_bytes=ref)))

if __name__=='__main__':main()
