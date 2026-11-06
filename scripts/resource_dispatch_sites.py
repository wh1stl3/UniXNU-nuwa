"""Observe the naturally resolved ResourceFork getxattr target, without dereferencing it."""
import hashlib, struct
from pathlib import Path
import read_resource_sites as R

CALL = 0xfffffff00746e1a4
AFTER = CALL + 4
HELPER_RETURN = R.ENTRY + 0x74


def points():
    return [dict(site=CALL, id=611, phase='call'), dict(site=AFTER, id=612, phase='continuation')]


def plan():
    return dict(source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                points=points(), state_bytes=16, target_source='native x8 before BLR; no observer target/table dereference',
                fields={'A03D': 'getxattr dispatch call/continuation checkpoint',
                        'A03E': 'call: actual x8 target; continuation: raw x0'},
                scope='existing header/thread/callback/decode/resource gates, exact wrapper caller, active VNOP pair and paired wrapper FP',
                native_policy_changed=False)


def add_sites(add, raw, m, backed):
    assert struct.unpack_from('<I', raw, backed(m, CALL))[0] == 0xd63f0100
    assert struct.unpack_from('<I', raw, backed(m, AFTER))[0] == 0xaa0003e1
    for p in points():
        add(p['site'], 'resource-dispatch', hex(p['site']), 'context')


def observe(site):
    p = next((p for p in points() if p['site'] == site), None)
    if p is None:
        return ''
    done = f'.Lresource_dispatch_done_{p["id"]}'
    matched = f'.Lresource_dispatch_parent_{p["id"]}'
    # Native wrapper FP/LR are restored even when a scope check rejects the hit.
    s = f'''    stp x29, x30, [sp, #-16]!
    ldr x10, [x29, #8]
    LOADABS x11, {HELPER_RETURN:#x}
    cmp x10, x11
    b.ne {done}
    ldr x16, [x29]
    ldr x17, [x16]
    ldr x18, [x16, #8]
    mov x29, x17
'''
    s += R.D.scope(dict(id=p['id']+3000, kind='decode', phase='call'), done)
    for n, (pc, bit) in enumerate(R.PARENTS):
        label = f'.Lresource_dispatch_next_{p["id"]}_{n}'
        s += f'''    LOADABS x10, {pc:#x}
    cmp x18, x10
    b.ne {label}
    ldr x10, [x14, #8]
    tbz x10, #{bit}, {done}
    b {matched}
{label}:
'''
    s += f'''    b {done}
{matched}:
    adr x9, probe_result_state
    ldr x10, [x9, #56]
    cbz x10, {done}
    ldr x10, [x9, #24]
    cbz x10, {done}
    cmn x10, #1
    b.eq {done}
    ldr x10, [x9]
    ldr x11, [x17]
    cmp x10, x11
    b.ne {done}
    adr x14, probe_resource_state
    ldr x10, [x14, #24]
    cbz x10, {done}
    ldr x10, [x14]
    cmp x10, x17
    b.ne {done}
    ldr x10, [x14, #16]
    cmp x10, x18
    b.ne {done}
    ldr x10, [x14, #8]
    tbz x10, #2, {done}
    adr x14, probe_resource_dispatch_state
    ldr x12, [sp]
'''
    if site == CALL:
        s += '    str x12, [x14]\n    mov x10, #1\n    str x10, [x14, #8]\n'
    else:
        s += f'''    ldr x10, [x14, #8]
    cbz x10, {done}
    ldr x10, [x14]
    cmp x10, x12
    b.ne {done}
    str xzr, [x14, #8]
'''
    s += f'    LOADABS x10, {site:#x}\n    str x10, [x9, #32]\n'
    s += '    str x8, [x9, #40]\n' if site == CALL else '    str x0, [x9, #40]\n'
    return s + R.R.draw((32, 40)) + done + ':\n    ldp x29, x30, [sp], #16\n'


def reset():
    return '    adr x14, probe_resource_dispatch_state\n    stp xzr, xzr, [x14]\n'


def transform(template):
    needle = '.balign 4096\n.global probe_zero'
    assert template.count(needle) == 1
    return template.replace(needle, '.global probe_resource_dispatch_state\nprobe_resource_dispatch_state:\n    .zero 16\n' + needle)
