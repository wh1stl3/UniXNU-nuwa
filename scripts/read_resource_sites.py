"""Scoped ResourceFork helper progress; no native IO or error-policy changes."""
import hashlib,struct
from pathlib import Path
import read_result_sites as R
D=R.PREVIOUS
ENTRY=0xfffffff005696d2c
RET=0xfffffff005696e80
CALLS=(0x40,0x50,0x70,0x7c,0x90,0xbc,0xcc,0xf4,0x120,0x130)
PARENTS=((D.DECODE+0x148+4,3),(D.DECODE+0x180+4,5),(D.DECODE+0x1bc+4,6),(D.DECODE+0x1e8+4,8))

def points():
    out=[dict(site=ENTRY,phase='entry',pair=None)]
    for n,off in enumerate(CALLS):
        for after in (0,1):out.append(dict(site=ENTRY+off+after*4,phase='continuation' if after else 'call',pair=n))
    out.append(dict(site=RET,phase='return',pair=None))
    return [dict(p,id=589+i,kind='resource') for i,p in enumerate(out)]

def plan():
    return dict(source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),points=points(),state_bytes=32,
                parents=[dict(return_pc=hex(pc),pair=pair) for pc,pair in PARENTS],native_policy_changed=False,
                display='Existing A03D/E only; no added grid rectangles',scope='Header/thread/actual callback/decode frame, exact paired resource caller, resource parent frame/LR and per-call pairing')

def add_sites(add,raw,m,backed):
    for p in points():
        word=struct.unpack_from('<I',raw,backed(m,p['site']))[0]
        if p['phase']=='call':assert word&0xfc000000==0x94000000
        if p['phase']=='return':assert word==0xd65f03c0
        add(p['site'],'resource',hex(p['site']),'context')

def observe(site):
    p=next((v for v in points() if v['site']==site),None)
    if p is None:return ''
    done=f'.Lresource_done_{p["id"]}';matched=f'.Lresource_parent_{p["id"]}'
    if p['phase'] in ('entry','return'):s='    mov x17, x29\n    mov x18, x30\n'
    else:s='    ldr x17, [x29]\n    ldr x18, [x29, #8]\n'
    s='    stp x29, x30, [sp, #-16]!\n'+s+'    mov x29, x17\n'
    s+=D.scope(dict(id=p['id']+2000,kind='decode',phase='call'),done)
    for n,(pc,bit) in enumerate(PARENTS):
        nextlabel=f'.Lresource_next_{p["id"]}_{n}'
        s+=f'    LOADABS x10, {pc:#x}\n    cmp x18, x10\n    b.ne {nextlabel}\n    ldr x10, [x14, #8]\n    tbz x10, #{bit}, {done}\n    b {matched}\n{nextlabel}:\n'
    s+=f'    b {done}\n{matched}:\n    adr x9, probe_result_state\n    ldr x10, [x9, #56]\n    cbz x10, {done}\n    ldr x10, [x9, #24]\n    cbz x10, {done}\n    cmn x10, #1\n    b.eq {done}\n    ldr x10, [x9]\n    ldr x11, [x17]\n    cmp x10, x11\n    b.ne {done}\n    adr x14, probe_resource_state\n'
    if p['phase']=='entry':s+='    str x17, [x14]\n    str xzr, [x14, #8]\n    str x18, [x14, #16]\n    mov x10, #1\n    str x10, [x14, #24]\n'
    else:
        s+=f'    ldr x10, [x14, #24]\n    cbz x10, {done}\n    ldr x10, [x14]\n    cmp x10, x17\n    b.ne {done}\n    ldr x10, [x14, #16]\n    cmp x10, x18\n    b.ne {done}\n'
    if p['pair'] is not None:
        s+='    ldr x10, [x14, #8]\n'
        if p['phase']=='call':s+=f'    orr x10, x10, #{1<<p["pair"]}\n'
        else:s+=f'    tbz x10, #{p["pair"]}, {done}\n    bic x10, x10, #{1<<p["pair"]}\n'
        s+='    str x10, [x14, #8]\n'
    if p['phase']=='return':s+='    str xzr, [x14, #24]\n'
    s+=f'    LOADABS x10, {site:#x}\n    str x10, [x9, #32]\n'
    s+=('    str x0, [x9, #40]\n' if p['phase'] in ('continuation','return') else '    mov x10, #-1\n    str x10, [x9, #40]\n')
    return s+R.draw((32,40))+done+':\n    ldp x29, x30, [sp], #16\n'

def reset():return '    adr x14, probe_resource_state\n    stp xzr, xzr, [x14]\n    stp xzr, xzr, [x14, #16]\n'

def transform(template):
    needle='.balign 4096\n.global probe_zero';assert template.count(needle)==1
    return template.replace(needle,'.global probe_resource_state\nprobe_resource_state:\n    .zero 32\n'+needle)
