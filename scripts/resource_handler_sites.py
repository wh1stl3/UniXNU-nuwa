"""Observe the PROBE42-resolved APFS handler; preserve all native calls."""
import hashlib, struct
from pathlib import Path
import resource_dispatch_sites as W
ENTRY=0xfffffff00519cb28
RET=ENTRY+0x11c
CALLS=(0x1c,0x20,0x30,0x5c,0x78,0xac,0xc0,0xe8,0x104)

def points():
    sites={ENTRY:dict(site=ENTRY,phase='entry',calls=[],returns=[]),RET:dict(site=RET,phase='return',calls=[],returns=[])}
    for pair,offset in enumerate(CALLS):
        for after in (False,True):
            pc=ENTRY+offset+4*after
            p=sites.setdefault(pc,dict(site=pc,phase='body',calls=[],returns=[]))
            p['returns' if after else 'calls'].append(pair)
    return [dict(p,id=613+i) for i,p in enumerate(sorted(sites.values(),key=lambda p:p['site']))]

def plan():
    return dict(source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),points=points(),state_bytes=32,
        fields={'A03D':'last scoped APFS handler checkpoint, not stopped PC','A03E':'native x0 at that checkpoint; argument or raw return, not necessarily errno'},
        scope='active read thread and paired native wrapper frame/LR, paired internal returns',new_grid_rectangles=0,native_policy_changed=False)

def add_sites(add,raw,m,backed):
    for p in points():
        word=struct.unpack_from('<I',raw,backed(m,p['site']))[0]
        if p['calls']:assert word&0xfc000000==0x94000000 or word&0xfffffc1f==0xd63f0000
        if p['phase']=='return':assert word==0xd65f03c0
        add(p['site'],'resource-handler',hex(p['site']),'context')

def observe(site):
    p=next((p for p in points() if p['site']==site),None)
    if p is None:return ''
    done=f'.Lresource_handler_done_{p["id"]}'
    s=f'''    adr x9, probe_read_state
    ldr x10, [x9]
    cbz x10, {done}
    mrs x10, tpidr_el1
    ldr x11, [x9, #8]
    cmp x10, x11
    b.ne {done}
    adr x9, probe_resource_dispatch_state
    ldr x10, [x9, #8]
    cbz x10, {done}
'''
    s+=('    mov x12, x29\n    mov x13, x30\n' if p['phase'] in ('entry','return') else '    ldr x12, [x29]\n    ldr x13, [x29, #8]\n')
    s+=f'''    ldr x10, [x9]
    cmp x10, x12
    b.ne {done}
    LOADABS x10, {W.AFTER:#x}
    cmp x13, x10
    b.ne {done}
    adr x14, probe_resource_handler_state
'''
    if p['phase']=='entry':
        s+='    str x12, [x14]\n    mov x10, #1\n    str x10, [x14, #8]\n    stp xzr, xzr, [x14, #16]\n'
    else:
        s+=f'    ldr x10, [x14, #8]\n    cbz x10, {done}\n    ldr x10, [x14]\n    cmp x10, x12\n    b.ne {done}\n'
    s+='    ldr x10, [x14, #16]\n'
    for pair in p['returns']:s+=f'    tbz x10, #{pair}, {done}\n    bic x10, x10, #{1<<pair}\n'
    for pair in p['calls']:s+=f'    orr x10, x10, #{1<<pair}\n'
    s+='    str x10, [x14, #16]\n    ldr x10, [x14, #24]\n    add x10, x10, #1\n    str x10, [x14, #24]\n'
    if p['phase']=='return':s+='    str xzr, [x14, #8]\n'
    s+=f'    adr x9, probe_result_state\n    LOADABS x10, {site:#x}\n    stp x10, x0, [x9, #32]\n'
    return s+W.R.R.draw((32,40))+done+':\n'

def reset():return '    adr x14, probe_resource_handler_state\n    stp xzr, xzr, [x14]\n    stp xzr, xzr, [x14, #16]\n'

def transform(template):
    needle='.balign 4096\n.global probe_zero';assert template.count(needle)==1
    return template.replace(needle,'.global probe_resource_handler_state\nprobe_resource_handler_state:\n    .zero 32\n'+needle)
