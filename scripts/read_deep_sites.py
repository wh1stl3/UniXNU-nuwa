"""Revision46: allocation, vector preparation and native decode helper trace."""
import hashlib,struct
from pathlib import Path
import read_fetch_sites as PREVIOUS
MALLOC_DATA=0xfffffff00784fa08
MALLOC=0xfffffff00784e604
MALLOC_RET=0xfffffff00784e6f0
DECODE=0xfffffff005696f98
DECODE_RET=0xfffffff0056970bc
POST_OFFSETS=(0x1b8,0x1c0,0x1c4,0x2f4,0x314,0x318,0x328,0x32c,0x354,0x3a4,0x3c4,0x3e4)
MALLOC_CALLS=(0x4c,0xa8,0xcc,0xd8)
DECODE_CALLS=(0x80,0xc4,0x100,0x148,0x164,0x180,0x1bc,0x1cc,0x1e8,0x22c,0x248,0x2bc,0x2f8,0x310,0x3a4,0x3b4,0x3e4,0x418,0x44c,0x460,0x494,0x4c8,0x4f4,0x518,0x550,0x580,0x59c,0x5cc,0x600)


def points():
    out=[dict(site=PREVIOUS.CALLBACK+off,kind='post',phase='checkpoint',pair=None) for off in POST_OFFSETS]
    out.append(dict(site=MALLOC_DATA,kind='malloc',phase='tail-entry',pair=None))
    for kind,entry,ret,calls in (('malloc',MALLOC,MALLOC_RET,MALLOC_CALLS),('decode',DECODE,DECODE_RET,DECODE_CALLS)):
        out.append(dict(site=entry,kind=kind,phase='entry',pair=None))
        for n,off in enumerate(calls):
            for after in (0,1):out.append(dict(site=entry+off+after*4,kind=kind,phase='continuation' if after else 'call',pair=n))
        out.append(dict(site=ret,kind=kind,phase='return',pair=None))
    for i,p in enumerate(out):p['id']=499+i
    return out


def geometry(idx):
    if idx<522:return 208,224+(idx-499)*24
    return 736+((idx-522)%2)*48,240+((idx-522)//2)*24


def plan():
    return dict(source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),points=points(),state_bytes=64,
                rectangles=[dict(id=p['id'],x=geometry(p['id'])[0],y=geometry(p['id'])[1],width=32,height=2) for p in points()],
                native_policy_changed=False,scope='retained fetch/callback context plus exact child LR, active parent call, saved child parent frame, own pairing')


def add_sites(add,raw,m,backed):
    PREVIOUS.add_sites(add,raw,m,backed)
    assert m['symbols']['_IOMallocData']==MALLOC_DATA and m['symbols']['_IOMalloc_internal']==MALLOC
    for p in points():
        word=struct.unpack_from('<I',raw,backed(m,p['site']))[0]
        if p['phase']=='call':assert word&0xfc000000==0x94000000 or word&0xfffffc1f==0xd63f0000,(p,hex(word))
        if p['phase']=='return':assert word==0xd65f03c0
        add(p['site'],p['kind'],hex(p['site']),'context' if p['pair'] is None else p['phase'])


def scope(p,done):
    child=p['kind']!='post';inner=child and p['phase'] not in ('entry','tail-entry','return')
    base=PREVIOUS.scope(dict(id=p['id'],kind='callback',phase='call'),done)
    if inner:
        old='    ldr x12, [x29]\n    ldr x10, [x29, #8]\n'
        assert base.count(old)==1
        base=base.replace(old,'    ldr x12, [x29]\n    ldr x10, [x12, #8]\n    ldr x12, [x12]\n')
    if not child:return base+'    adr x14, probe_deep_state\n'
    off=0 if p['kind']=='malloc' else 32
    callers=(PREVIOUS.CALLBACK+0x144,PREVIOUS.CALLBACK+0x1b4) if off==0 else (PREVIOUS.CALLBACK+0x3d8,PREVIOUS.CALLBACK+0x428)
    pairs=(2,5) if off==0 else (10,11)
    s=base+('    ldr x12, [x29]\n    ldr x10, [x29, #8]\n' if inner else '    mov x12, x29\n    mov x10, x30\n')
    s+=f'''    ldr x11, [x14, #48]
    LOADABS x13, {callers[0]:#x}
    cmp x10, x13
    b.ne .Ldeep_second_{p['id']}
    tbz x11, #{pairs[0]}, {done}
    b .Ldeep_parent_ok_{p['id']}
.Ldeep_second_{p['id']}:
    LOADABS x13, {callers[1]:#x}
    cmp x10, x13
    b.ne {done}
    tbz x11, #{pairs[1]}, {done}
.Ldeep_parent_ok_{p['id']}:
    adr x14, probe_deep_state
    add x14, x14, #{off}
'''
    if p['phase'] in ('entry','tail-entry'):s+='    str x12, [x14]\n    str xzr, [x14, #8]\n'
    else:s+=f'    ldr x10, [x14]\n    cmp x10, x12\n    b.ne {done}\n'
    return s


def observe(site):
    s=PREVIOUS.observe(site)
    if site==PREVIOUS.DECOMP.PREVIOUS.FIRST:
        s+='    adr x14, probe_deep_state\n'
        for off in range(0,64,16):s+=f'    stp xzr, xzr, [x14, #{off}]\n'
        for p in points():
            i=p['id'];s+=f'    adr x16, probe_flags\n    strb wzr, [x16, #{128+i}]\n    DENSE_ONCE {i}, 0\n    adr x16, probe_flags\n    strb wzr, [x16, #{128+i}]\n'
    for p in (q for q in points() if q['site']==site):
        done=f'.Ldeep_done_{p["id"]}';s+=scope(p,done)
        if p['pair'] is not None:
            s+='    ldr x10, [x14, #8]\n'
            if p['phase']=='call':s+=f'    orr x10, x10, #{1<<p["pair"]:#x}\n'
            else:s+=f'    tbz x10, #{p["pair"]}, {done}\n    bic x10, x10, #{1<<p["pair"]:#x}\n    str x0, [x14, #24]\n'
            s+='    str x10, [x14, #8]\n'
        s+=f'    LOADABS x10, {site:#x}\n    str x10, [x14, #16]\n'
        color='0xffffc040' if p['phase']=='call' else '0xffffffff' if p['phase'] in ('continuation','return') else '0xffff40ff'
        s+=f'    DENSE_ONCE {p["id"]}, {color}\n'+done+':\n'
    return s


def transform(template):
    start=template.index('.macro DENSE_ONCE');end=template.index('.endm',start)
    dense=template[start:end];idx=chr(92)+'idx'
    old='    .if '+idx+' >= 441\n    mov x11, #(232+'
    new='    .if '+idx+' >= 522\n    mov x11, #(240+(('+idx+'-522)/2)*24)\n    .elseif '+idx+' >= 499\n    mov x11, #(224+('+idx+'-499)*24)\n    .elseif '+idx+' >= 441\n    mov x11, #(232+'
    assert dense.count(old)==1;dense=dense.replace(old,new)
    old='    .if '+idx+' >= 441\n    mov x11, #((736+'
    new='    .if '+idx+' >= 522\n    mov x11, #((736+(('+idx+'-522)%2)*48)*4)\n    .elseif '+idx+' >= 499\n    mov x11, #(208*4)\n    .elseif '+idx+' >= 441\n    mov x11, #((736+'
    assert dense.count(old)==1;dense=dense.replace(old,new)
    template=template[:start]+dense+template[end:]
    return template.replace('.balign 4096\n.global probe_zero','.global probe_deep_state\nprobe_deep_state:\n    .zero 64\n.balign 4096\n.global probe_zero')
