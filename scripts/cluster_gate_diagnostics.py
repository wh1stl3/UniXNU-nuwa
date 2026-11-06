"""PROBE52: slot formerly at 43CB8C now diagnoses the 438C3C return gap.

Bounded, thread-scoped diagnostics; never widen strict gates.

Bits are cumulative within a header attempt, not invocation counts or order.
No state or pixels are written before the active-read and thread checks pass.
"""
ENABLED = False  # PROBE55 retires reason/control logging; strict gates remain.
OFFSETS = (0x438c34, 0x438c38, 0x43cb58, 0x438c3c, 0x43cb90,
           0x43cc1c, 0x43cc20, 0x43cc74, 0x3005cc)
REASONS = ('parent-inactive', 'parent-unpaired', 'lr-mismatch', 'parent-frame',
           'parent-lr', 'self-inactive', 'self-frame', 'unpaired-return')
REACHED = 1 << 9
PASSED = 1 << 8
CONTROL = 0x43cb90
CALLER_ENTRY = 0x43cb58
CALLER_LRS = (0xfffffff007438c38, 0xfffffff0074364a4, 0xfffffff00743a080)


def caller_bit(lr):
    return 14 + (CALLER_LRS.index(lr) if lr in CALLER_LRS else 3)
SYMBOL = 'probe_cluster_gate_state'
SLOT_BYTES = 32  # flags, wide last x0, strict last x0, completed-render flags


def selected(p):
    return p['offset'] in OFFSETS


def rectangles(p, geometry):
    x, y = geometry(p)
    return [(x + 26, y, 8, 6), (x, y + 7, 24, 2)]


def render(p, geometry, tag, clear=False):
    """Independent reason bits at right; reached/pass/control bits below.

    Only one stripe per bit; no reason can erase another. No HEX calls.
    """
    x, y = geometry(p)
    label = f'.Lgate_pixels_{p["id"]}_{tag}'
    s = f'    adr x9, probe_scratch\n    ldp x10, x11, [x9]\n    cbz x10, {label}_done\n'
    if not clear:
        s += f'    adr x9, {SYMBOL}\n    ldr x17, [x9, #{OFFSETS.index(p["offset"])*SLOT_BYTES}]\n'
    cells = [(bit, x+26+bit, y, 1, 6, 0xffffa040) for bit in range(8)]
    # Left to right: arrived, strict pass, wide NULL/non-NULL, strict NULL/non-NULL.
    status_bits = (9, 8, 14, 15, 16, 17) if p['offset']==CALLER_ENTRY else (9, 8, 10, 11, 12, 13)
    for i, bit in enumerate(status_bits):
        cells.append((bit, x+i*4, y+7, 4, 2,
                      0xffffffff if bit in (8, 9) else 0xffff0000 if bit in (10, 12) else 0xff00ffff))
    for bit, xx, yy, width, height, color in cells:
        cell = label + '_' + str(bit)
        if not clear:
            s += f'    tbz x17, #{bit}, {cell}_done\n'
        s += f'    mov x12, #{yy}\n    madd x12, x11, x12, x10\n    add x12, x12, #{xx*4}\n    LOADABS x13, {0 if clear else color:#x}\n'
        for row in range(height):
            for col in range(width):
                s += f'    str w13, [x12, #{col*4}]\n'
            if row != height-1:
                s += '    add x12, x12, x11\n'
        s += cell + '_done:\n'
    if not clear:
        s += f'    adr x9, {SYMBOL}\n    str x17, [x9, #{OFFSETS.index(p["offset"])*SLOT_BYTES+24}]\n'
    return s + label + '_done:\n'


def update(p, geometry, tag, mask, control=False):
    slot = OFFSETS.index(p['offset'])*SLOT_BYTES
    label = f'.Lgate_update_{p["id"]}_{tag}'
    s = f'    adr x9, {SYMBOL}\n    ldr x16, [x9, #{slot}]\n    orr x17, x16, #{mask}\n'
    if p['offset']==CALLER_ENTRY and tag=='arrival':
        s += '    str x30, [x9, #'+str(slot+8)+']\n'
        for index, lr in enumerate(CALLER_LRS):
            s += f'    LOADABS x16, {lr:#x}\n    cmp x30, x16\n    b.eq {label}_caller{index}\n'
        s += f'    orr x17, x17, #{1<<17}\n    b {label}_caller_done\n'
        for index in range(3):
            s += f'{label}_caller{index}:\n    orr x17, x17, #{1<<(14+index)}\n    b {label}_caller_done\n'
        s += label+'_caller_done:\n'
    if control:
        strict = tag == 'pass'
        nullbit, nonnullbit = (12, 13) if strict else (10, 11)
        s += f'    str x0, [x9, #{slot+(16 if strict else 8)}]\n    cbnz x0, {label}_nonnull\n    orr x17, x17, #{1<<nullbit}\n    b {label}_store\n{label}_nonnull:\n    orr x17, x17, #{1<<nonnullbit}\n{label}_store:\n'
    s += f'    str x17, [x9, #{slot}]\n    ldr x16, [x9, #{slot+24}]\n    cmp x16, x17\n    b.eq {label}_done\n'
    s += render(p, geometry, tag)
    return s + label + '_done:\n'


def instrument(p, geometry, assembly):
    if not ENABLED or not selected(p):
        return assembly
    done = f'.Lresource_cluster_done_{p["id"]}'
    # Match existing gate branches without altering any condition or its order.
    lines = assembly.splitlines(keepends=True)
    branches = [i for i, line in enumerate(lines) if line.strip().startswith(('cbz ', 'b.ne ', 'tbz ')) and line.rstrip().endswith(done)]
    expected = 7 + (0 if p['phase']=='entry' else 2) + len(p['returns'])
    assert len(branches) == expected
    labels = []
    for n, index in enumerate(branches[2:]):
        bit = min(n, 7)
        label = f'.Lgate_reject_{p["id"]}_{bit}'
        lines[index] = lines[index].replace(done, label)
        labels.append((label, bit))
    # Wide arrival/control observation happens only after R1/R2, before parent checks.
    lines[branches[1]] += update(p, geometry, 'arrival', REACHED, p['offset']==CONTROL)
    # All native samples are already stored before scratch registers are reused.
    record = next(i for i, line in enumerate(lines) if 'stp x10,' in line and '[x9, #32]' in line)
    lines[record] += update(p, geometry, 'pass', PASSED, p['offset']==CONTROL)
    tail = f'    b {done}\n'
    for label, bit in dict(labels).items():
        tail += label + ':\n' + update(p, geometry, 'reject'+str(bit), 1<<bit) + f'    b {done}\n'
    return ''.join(lines).replace(done+':\n', tail+done+':\n')


def reset(points, geometry):
    if not ENABLED:
        return ''
    s = f'    adr x9, {SYMBOL}\n'
    for index in range(len(OFFSETS)*SLOT_BYTES//16):
        s += f'    stp xzr, xzr, [x9, #{index*16}]\n'
    return s + ''.join(render(p, geometry, 'reset', True) for p in points if selected(p))


def data():
    return f'.balign 8\n.global {SYMBOL}\n{SYMBOL}:\n    .zero {len(OFFSETS)*SLOT_BYTES}\n'
