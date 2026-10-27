"""Observe actual read target and one fixed candidate entry; never infer equality."""
import struct
import read_boundary_sites as PREVIOUS

ENTRY = 0xfffffff0051a5858
DISPATCH = PREVIOUS.CALLS[3][0]


def add_sites(add, raw, macho, backed):
    PREVIOUS.add_sites(add, raw, macho, backed)
    if struct.unpack_from('<I', raw, backed(macho, ENTRY))[0] != 0xd10403ff:
        raise ValueError('Fixed read candidate entry prologue changed')
    add(ENTRY, 'fixed_regular_read_candidate', 'fixed_regular_read_candidate', 'entry')


def scope(done):
    return f'''    adr x9, probe_read_state
    ldr x10, [x9]
    cbz x10, {done}
    mrs x10, tpidr_el1
    ldr x11, [x9, #8]
    cmp x10, x11
    b.ne {done}
    ldr x10, [x9, #40]
    cbz x10, {done}
    cmp x29, x10
    b.ne {done}
    ldr x10, [x9, #104]
    tbz x10, #3, {done}
'''


def observe(site):
    source = PREVIOUS.observe(site)
    if site == PREVIOUS.FIRST:
        return source + '''    adr x16, probe_flags
    strb wzr, [x16, #404]
    DENSE_ONCE 276, 0
    adr x16, probe_flags
    strb wzr, [x16, #404]
    mov x23, #0
    HEXROW_VAL 1728
    mov x23, #0
    HEXROW_VAL 1760
'''
    if site not in (DISPATCH, ENTRY):
        return source
    done = f'.Ldispatch_scope_done_{site:x}'
    source += scope(done)
    if site == DISPATCH:
        source += '    mov x23, x8\n    HEXROW_VAL 1728\n'
    else:
        source += f'''    LOADABS x11, {DISPATCH + 4:#x}
    cmp x30, x11
    b.ne {done}
    ldr x10, [x9, #56]
    LOADABS x11, {ENTRY:#x}
    cmp x10, x11
    b.ne {done}
    add x10, sp, #184
    cmp x0, x10
    b.ne {done}
    mov x23, x11
    HEXROW_VAL 1760
    DENSE_ONCE 276, 0xff40ff80
'''
    return source + done + ':\n'
