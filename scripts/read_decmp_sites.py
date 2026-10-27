"""Revision42: scoped compressed-read entry, native calls and continuations.

The center gutter (x736..815/y224..1031) is separate from HEX and older grids.
Every observation returns to the displaced native instruction. No lock, error,
authentication, scheduling or restore-userland-release policy is changed.
"""
import hashlib
import struct
from pathlib import Path
import read_grid_sites as PREVIOUS

ENTRY = 0xfffffff007480028
END = 0xfffffff007480904
RET = 0xfffffff007480330
CALLER = 0xfffffff0051a59b8
CALL_OFFSETS = (80,104,136,152,216,232,244,304,352,364,376,400,412,452,468,
                532,640,660,1016,1040,1052,1100,1200,1272,1496,1548,1612,
                1648,1760,1896,2064,2124,2248)


def points():
    out = [dict(site=ENTRY,id=373,phase='entry',pair=None)]
    for n,off in enumerate(CALL_OFFSETS):
        for after in (0,1):
            out.append(dict(site=ENTRY+off+after*4,id=374+2*n+after,
                            phase='continuation' if after else 'call',pair=n))
    out.append(dict(site=RET,id=440,phase='return',pair=None))
    return out


def geometry(idx):
    return 736+((idx-373)%2)*48,224+((idx-373)//2)*24


def plan():
    return dict(source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                entry=hex(ENTRY),caller=hex(CALLER),points=points(),state_bytes=32,
                rectangles=[dict(id=p['id'],x=geometry(p['id'])[0],y=geometry(p['id'])[1],width=32,height=16) for p in points()],
                native_policy_changed=False,hex_policy='No additional hot-path HEX',
                scope='active header, thread, VNOP/APFS frame chain, native LR, outer pair8, own call pairing')


def add_sites(add,raw,m,backed):
    PREVIOUS.BODY.add_sites(add,raw,m,backed)
    assert m['symbols']['_decmpfs_read_compressed']==ENTRY
    assert struct.unpack_from('<I',raw,backed(m,ENTRY))[0]==0xd104c3ff
    assert struct.unpack_from('<I',raw,backed(m,RET))[0]==0xd65f03c0
    for off in CALL_OFFSETS:
        word=struct.unpack_from('<I',raw,backed(m,ENTRY+off))[0]
        assert word&0xfc000000==0x94000000 or word&0xfffffc1f==0xd63f0000
    for p in points():
        add(p['site'],'_decmpfs_read_compressed',hex(p['site']),
            'context' if p['pair'] is None else p['phase'])


def scope(site,done):
    outer=site in (ENTRY,RET)
    s=f'''    adr x9, probe_read_state
    ldr x10, [x9]
    cbz x10, {done}
    mrs x10, tpidr_el1
    ldr x11, [x9, #8]
    cmp x10, x11
    b.ne {done}
    ldr x10, [x9, #56]
    LOADABS x11, {PREVIOUS.BODY.ENTRY:#x}
    cmp x10, x11
    b.ne {done}
    ldr x10, [x9, #104]
    tbz x10, #3, {done}
    adr x10, probe_read_body_state
    ldr x10, [x10]
    tbz x10, #8, {done}
'''
    s+=('    mov x12, x29\n    mov x10, x30\n' if outer else
        '    ldr x12, [x29]\n    ldr x10, [x29, #8]\n')
    s+=f'''    LOADABS x11, {CALLER+4:#x}
    cmp x10, x11
    b.ne {done}
    ldr x10, [x9, #40]
    cbz x10, {done}
    ldr x11, [x12]
    cmp x10, x11
    b.ne {done}
    ldr x10, [x12, #8]
    LOADABS x11, {PREVIOUS.BODY.PREVIOUS.DISPATCH+4:#x}
    cmp x10, x11
    b.ne {done}
    adr x14, probe_decmp_state
'''
    if site==ENTRY:
        s+='    str x12, [x14]\n    str xzr, [x14, #8]\n'
    else:
        s+=f'''    ldr x10, [x14]
    cmp x10, x12
    b.ne {done}
'''
    return s


def observe(site):
    source=PREVIOUS.observe(site)
    if site==PREVIOUS.FIRST:
        source+='    adr x14, probe_decmp_state\n    stp xzr, xzr, [x14]\n    stp xzr, xzr, [x14, #16]\n'
        for p in points():
            i=p['id']
            source+=f'    adr x16, probe_flags\n    strb wzr, [x16, #{128+i}]\n    DENSE_ONCE {i}, 0\n    adr x16, probe_flags\n    strb wzr, [x16, #{128+i}]\n'
        return source
    selected=[p for p in points() if p['site']==site]
    if not selected:return source
    done=f'.Ldecmp_done_{site:x}'
    source+=scope(site,done)
    for p in selected:
        skip=f'.Ldecmp_skip_{p["id"]}'
        if p['pair'] is not None:
            source+='    ldr x13, [x14, #8]\n'
            if p['phase']=='call':
                source+=f'    orr x13, x13, #{1<<p["pair"]:#x}\n    str x13, [x14, #8]\n'
            else:
                source+=f'    tbz x13, #{p["pair"]}, {skip}\n    bic x13, x13, #{1<<p["pair"]:#x}\n    str x13, [x14, #8]\n    str x0, [x14, #24]\n'
        source+=f'    LOADABS x13, {site:#x}\n    str x13, [x14, #16]\n'
        source+=f'    DENSE_ONCE {p["id"]}, '+('0xff40c0ff' if p['phase']=='call' else '0xff40ff80')+'\n'+skip+':\n'
    return source+done+':\n'
