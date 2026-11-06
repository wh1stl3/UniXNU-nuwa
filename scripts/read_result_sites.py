"""Revision47: distinguish second-allocation return from callback error paths."""
import hashlib,struct
from pathlib import Path
import read_deep_sites as PREVIOUS
F=PREVIOUS.PREVIOUS
REQUEST=F.CALLBACK+0x1ac
CONTINUATION=F.CALLBACK+0x1b4
OFFSETS=(0x1ac,0x1f0,0x1f4,0x208,0x224,0x228,0x268)
FIELDS=((8,1856),(16,1888),(24,1920),(32,1952),(40,1984))

def points():
    return [dict(id=582+i,site=F.CALLBACK+off,phase='call' if off in (0x1f0,0x224) else 'continuation' if off in (0x1f4,0x228) else 'checkpoint',pair=0 if off in (0x1f0,0x1f4) else 1 if off in (0x224,0x228) else None) for i,off in enumerate(OFFSETS)]

def geometry(idx):return 736+((idx-582)%2)*48,244+((idx-582)//2)*24

def plan():
    return dict(source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),points=points(),state_bytes=64,
                rectangles=[dict(id=p['id'],x=geometry(p['id'])[0],y=geometry(p['id'])[1],width=32,height=2) for p in points()],
                fields={'A03A':'second allocation requested bytes','A03B':'second IOMalloc_internal RET x0; F until observed','A03C':'second callback call continuation x0; F until observed','A03D':'last scoped result/error checkpoint PC','A03E':'callback metadata subtype at native SP+0x58'},
                native_policy_changed=False,scope='active header/thread/actual callback and parent frames, second-call request pins callback FP, exact allocator LR, independently paired printf edges')

def add_sites(add,raw,m,backed):
    PREVIOUS.add_sites(add,raw,m,backed)
    for p in points():
        word=struct.unpack_from('<I',raw,backed(m,p['site']))[0]
        if p['phase']=='call':assert word&0xfc000000==0x94000000
        add(p['site'],'result',hex(p['site']),'context')

def scope(site,done):
    if site==PREVIOUS.MALLOC_RET:
        s=PREVIOUS.scope(dict(id=589,kind='malloc',phase='return'),done)
        s+=f'    LOADABS x11, {CONTINUATION:#x}\n    cmp x30, x11\n    b.ne {done}\n'
    else:s=F.scope(dict(id=590+(site-F.CALLBACK)//4,kind='callback',phase='call'),done)
    s+='    adr x9, probe_result_state\n'
    if site!=REQUEST:
        s+=f'    ldr x10, [x9, #56]\n    cbz x10, {done}\n    ldr x10, [x9]\n    cmp x10, x29\n    b.ne {done}\n'
    return s

def draw(offsets):
    return ''.join(f'    adr x9, probe_result_state\n    ldr x23, [x9, #{off}]\n    HEXROW_VAL {row}\n' for off,row in FIELDS if off in offsets)

def observe(site):
    s=PREVIOUS.observe(site)
    if site==F.DECOMP.PREVIOUS.FIRST:
        s+='    adr x9, probe_result_state\n'
        for off in range(0,64,16):s+=f'    stp xzr, xzr, [x9, #{off}]\n'
        s+='    mov x10, #-1\n    stp x10, x10, [x9, #16]\n'+draw((8,16,24,32,40))
        for p in points():
            i=p['id'];s+=f'    adr x16, probe_flags\n    strb wzr, [x16, #{128+i}]\n    DENSE_ONCE {i}, 0\n    adr x16, probe_flags\n    strb wzr, [x16, #{128+i}]\n'
    p=next((p for p in points() if p['site']==site),None)
    if not p and site not in (CONTINUATION,PREVIOUS.MALLOC_RET):return s
    done=f'.Lresult_done_{site:x}';s+=scope(site,done)
    if site==REQUEST:
        s+='    str x29, [x9]\n    str x24, [x9, #8]\n    mov x10, #-1\n    stp x10, x10, [x9, #16]\n    ldur w10, [x29, #-0x98]\n    str x10, [x9, #40]\n    str xzr, [x9, #48]\n    mov x10, #1\n    str x10, [x9, #56]\n'
    if p and p['pair'] is not None:
        s+='    ldr x10, [x9, #48]\n'
        if p['phase']=='call':s+=f'    orr x10, x10, #{1<<p["pair"]}\n'
        else:s+=f'    tbz x10, #{p["pair"]}, {done}\n    bic x10, x10, #{1<<p["pair"]}\n'
        s+='    str x10, [x9, #48]\n'
    if site==CONTINUATION:s+='    str x0, [x9, #24]\n'
    if site==PREVIOUS.MALLOC_RET:s+='    str x0, [x9, #16]\n'
    s+=f'    LOADABS x10, {site:#x}\n    str x10, [x9, #32]\n'
    if p:
        color='0xffffc040' if p['phase']=='call' else '0xffffffff' if p['phase']=='continuation' else '0xffff40ff'
        s+=f'    DENSE_ONCE {p["id"]}, {color}\n'
    s+=draw((8,16,24,32,40) if site==REQUEST else (24,32) if site==CONTINUATION else (16,32) if site==PREVIOUS.MALLOC_RET else (32,))
    return s+done+':\n'

def transform(template):
    start=template.index('.macro DENSE_ONCE');end=template.index('.endm',start);dense=template[start:end];idx=chr(92)+'idx'
    old='    .if '+idx+' >= 522\n    mov x11, #(240+'
    new='    .if '+idx+' >= 582\n    mov x11, #(244+(('+idx+'-582)/2)*24)\n    .elseif '+idx+' >= 522\n    mov x11, #(240+'
    assert dense.count(old)==1;dense=dense.replace(old,new)
    old='    .if '+idx+' >= 522\n    mov x11, #((736+'
    new='    .if '+idx+' >= 582\n    mov x11, #((736+(('+idx+'-582)%2)*48)*4)\n    .elseif '+idx+' >= 522\n    mov x11, #((736+'
    assert dense.count(old)==1;dense=dense.replace(old,new)
    template=template[:start]+dense+template[end:]
    return template.replace('.balign 4096\n.global probe_zero','.global probe_result_state\nprobe_result_state:\n    .zero 64\n.balign 4096\n.global probe_zero')
