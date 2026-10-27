"""Scoped native fetch and fixed type4 callback observations, revision45."""
import hashlib
import struct
from pathlib import Path
import probe_shared_hex as PREVIOUS
import read_decmp_sites as DECOMP
FETCH=0xfffffff00747fd28
FETCH_RET=0xfffffff00747fe68
CALLBACK=0xfffffff005696600
CALLBACK_RET=0xfffffff005696888
INDIRECT=0xfffffff00747fdc0
CALLERS=(0xfffffff007480474,0xfffffff007480520)
FETCH_CALLS=(0x58,0x68,0x98,0xa8,0xb0,0xb4,0xc8,0xd8,0xdc,0xec,0xf8,0x120)
CALLBACK_CALLS=(0x84,0x120,0x140,0x15c,0x194,0x1b0,0x1fc,0x244,0x254,0x264,0x3d4,0x424,0x43c,0x450,0x474)


def points():
    out=[]
    for kind,entry,ret,calls in (('fetch',FETCH,FETCH_RET,FETCH_CALLS),('callback',CALLBACK,CALLBACK_RET,CALLBACK_CALLS)):
        out.append(dict(site=entry,kind=kind,phase='entry',pair=None))
        for n,off in enumerate(calls):
            for after in (0,1):out.append(dict(site=entry+off+after*4,kind=kind,phase='continuation' if after else 'call',pair=n))
        out.append(dict(site=ret,kind=kind,phase='return',pair=None))
    for i,p in enumerate(out):p['id']=441+i
    return out


def geometry(idx):return 736+((idx-441)%2)*48,232+((idx-441)//2)*24


def plan():
    return dict(source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),points=points(),state_bytes=64,
                rectangles=[dict(id=p['id'],x=geometry(p['id'])[0],y=geometry(p['id'])[1],width=32,height=2) for p in points()],
                native_policy_changed=False,scope='active header/thread/target, outer pairs, decmp-fetch-callback frame and LR chain, actual callback x8, own pairs')


def add_sites(add,raw,m,backed):
    DECOMP.add_sites(add,raw,m,backed)
    assert m['symbols']['_decmpfs_fetch_uncompressed_data']==FETCH
    for p in points():
        word=struct.unpack_from('<I',raw,backed(m,p['site']))[0]
        if p['phase']=='call':assert word&0xfc000000==0x94000000 or word&0xfffffc1f==0xd63f0000
        if p['phase']=='return':assert word==0xd65f03c0
        add(p['site'],p['kind'],hex(p['site']),'context' if p['pair'] is None else p['phase'])


def scope(p,done):
    outer=p['phase'] in ('entry','return');cb=p['kind']=='callback'
    s=f'''    adr x9, probe_read_state
    ldr x10, [x9]
    cbz x10, {done}
    mrs x10, tpidr_el1
    ldr x11, [x9, #8]
    cmp x10, x11
    b.ne {done}
    ldr x10, [x9, #56]
    LOADABS x11, {DECOMP.PREVIOUS.BODY.ENTRY:#x}
    cmp x10, x11
    b.ne {done}
    ldr x10, [x9, #104]
    tbz x10, #3, {done}
    adr x10, probe_read_body_state
    ldr x10, [x10]
    tbz x10, #8, {done}
    adr x14, probe_fetch_state
'''
    s+=('    mov x12, x29\n    mov x10, x30\n' if outer else '    ldr x12, [x29]\n    ldr x10, [x29, #8]\n')
    if cb:
        s+=f'''    LOADABS x11, {INDIRECT+4:#x}
    cmp x10, x11
    b.ne {done}
    ldr x10, [x14, #32]
    LOADABS x11, {CALLBACK:#x}
    cmp x10, x11
    b.ne {done}
    ldr x10, [x14, #8]
    tbz x10, #2, {done}
    ldr x13, [x12]
    ldr x10, [x12, #8]
'''
    else:s+='    mov x13, x12\n'
    s+=f'''    LOADABS x11, {CALLERS[0]+4:#x}
    cmp x10, x11
    b.eq .Lfetch_lr_ok_{p['id']}
    LOADABS x11, {CALLERS[1]+4:#x}
    cmp x10, x11
    b.ne {done}
.Lfetch_lr_ok_{p['id']}:
    adr x10, probe_decmp_state
    ldr x11, [x10, #8]
    mov x15, #0xa00000
    tst x11, x15
    b.eq {done}
    ldr x10, [x10]
    ldr x11, [x13]
    cmp x10, x11
    b.ne {done}
    ldr x10, [x13, #8]
    LOADABS x11, {DECOMP.CALLER+4:#x}
    cmp x10, x11
    b.ne {done}
'''
    if p['kind']=='fetch' and p['phase']=='entry':
        s+='    str x13, [x14]\n    str xzr, [x14, #8]\n    str xzr, [x14, #32]\n    str xzr, [x14, #40]\n    str xzr, [x14, #48]\n'
    else:
        s+=f'    ldr x10, [x14]\n    cmp x10, x13\n    b.ne {done}\n'
    if cb:
        if p['phase']=='entry':s+='    str x12, [x14, #40]\n    str xzr, [x14, #48]\n'
        else:s+=f'    ldr x10, [x14, #40]\n    cmp x10, x12\n    b.ne {done}\n'
    return s


def observe(site):
    s=PREVIOUS.observe(site)
    if site==DECOMP.PREVIOUS.FIRST:
        s+='    adr x14, probe_fetch_state\n'
        for n in range(0,64,16):s+=f'    stp xzr, xzr, [x14, #{n}]\n'
        for p in points():
            i=p['id'];s+=f'    adr x16, probe_flags\n    strb wzr, [x16, #{128+i}]\n    DENSE_ONCE {i}, 0\n    adr x16, probe_flags\n    strb wzr, [x16, #{128+i}]\n'
    for p in (q for q in points() if q['site']==site):
        done=f'.Lfetch_done_{p["id"]}';s+=scope(p,done)
        if p['pair'] is not None:
            off=48 if p['kind']=='callback' else 8
            s+=f'    ldr x10, [x14, #{off}]\n'
            if p['phase']=='call':s+=f'    orr x10, x10, #{1<<p["pair"]:#x}\n'
            else:s+=f'    tbz x10, #{p["pair"]}, {done}\n    bic x10, x10, #{1<<p["pair"]:#x}\n    str x0, [x14, #24]\n'
            s+=f'    str x10, [x14, #{off}]\n'
        if site==INDIRECT:s+='    str x8, [x14, #32]\n'
        s+=f'    LOADABS x10, {site:#x}\n    str x10, [x14, #16]\n'
        s+=f'    DENSE_ONCE {p["id"]}, '+('0xffffc040' if p['phase']=='call' else '0xffff40ff' if p['phase']=='entry' else '0xffffffff')+'\n'+done+':\n'
    return s


def transform(template):
    start=template.index('.macro DENSE_ONCE');end=template.index('.endm',start)
    dense=template[start:end];idx=chr(92)+'idx'
    for reg,old,new in (
        ('y','    .if '+idx+' >= 373\n    mov x11, #(224+', '    .if '+idx+' >= 441\n    mov x11, #(232+(('+idx+'-441)/2)*24)\n    .elseif '+idx+' >= 373\n    mov x11, #(224+'),
        ('x','    .if '+idx+' >= 373\n    mov x11, #((736+', '    .if '+idx+' >= 441\n    mov x11, #((736+(('+idx+'-441)%2)*48)*4)\n    .elseif '+idx+' >= 373\n    mov x11, #((736+')):
        assert dense.count(old)==1;dense=dense.replace(old,new)
    template=template[:start]+dense+template[end:]
    return template.replace('.balign 4096\n.global probe_zero','.global probe_fetch_state\nprobe_fetch_state:\n    .zero 64\n.balign 4096\n.global probe_zero')
