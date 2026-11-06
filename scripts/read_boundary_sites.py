'''Scope read boundaries to the native exec header call, thread and stack frame.'''
import struct
import exec_path_sites as V34
FIRST=0xfffffff00769bf90
CALLS=((0xfffffff0074669b0,'_vn_rdwr','_vn_rdwr_64'),
       (0xfffffff007466acc,'_vn_rdwr_64','_mac_vnode_check_read'),
       (0xfffffff007466b20,'_vn_rdwr_64','_VNOP_READ'),
       (0xfffffff00746c688,'_VNOP_READ','indirect_x8'),
       (0xfffffff007466b08,'_vn_rdwr_64','_vn_read_swapfile'))
# active, TPIDR, vnode, caller FP, rdwr64 FP, VNOP FP, last stage,
# dispatch target, five actual post-call x0 values.
STATE_BYTES=112

def add_sites(add,raw,m,backed):
    V34.add_sites(add,raw,m,backed)
    for pc,fn,target in CALLS:
        word=struct.unpack_from('<I',raw,backed(m,pc))[0]
        if target=='indirect_x8':
            if word!=0xd63f0100:raise ValueError('Read dispatch no longer BLR x8')
        else:
            imm=word&0x3ffffff
            if imm&(1<<25):imm-=1<<26
            if word&0xfc000000!=0x94000000 or pc+imm*4!=m['symbols'][target]:raise ValueError('Pinned read BL target changed')
        add(pc,fn,target,'call',pc);add(pc+4,fn,target,'continuation',pc)

def observe(site):
    source=V34.observe(site)
    if site==FIRST:
        source+='''    adr x9, probe_read_state
    str xzr, [x9]
    mrs x10, tpidr_el1
    str x10, [x9, #8]
    str x1, [x9, #16]
    stp xzr, xzr, [x9, #24]
    stp xzr, xzr, [x9, #40]
    str xzr, [x9, #56]
    str xzr, [x9, #104]
    mov x10, #-1
    stp x10, x10, [x9, #64]
    stp x10, x10, [x9, #80]
    str x10, [x9, #96]
    mov x10, #1
    str x10, [x9]
'''
        for i in range(266,276):
            source+=f'    adr x16, probe_flags\n    strb wzr, [x16, #{128+i}]\n    DENSE_ONCE {i}, 0\n    adr x16, probe_flags\n    strb wzr, [x16, #{128+i}]\n'
        return source+'    mov x23, #250\n    HEXROW_VAL 1664\n    mov x23, #-1\n    HEXROW_VAL 1696\n'
    if site==FIRST+4:return source+'    adr x9, probe_read_state\n    str xzr, [x9]\n'
    entry=next(((i,pc) for i,(pc,fn,target) in enumerate(CALLS) if site in (pc,pc+4)),None)
    if entry is None:return source
    i,pc=entry;stage=266+2*i+(site==pc+4);done=f'.Lread_done_{site:x}'
    source+=f'''    adr x9, probe_read_state
    ldr x10, [x9]
    cbz x10, {done}
    mrs x10, tpidr_el1
    ldr x11, [x9, #8]
    cmp x10, x11
    b.ne {done}
'''
    if i==0:
        # vn_rdwr saved incoming LR at FP+8. Guard before reading caller memory.
        source+=f'''    ldr x10, [x29, #8]
    LOADABS x11, read_header_return
    cmp x10, x11
    b.ne {done}
'''
        if site==pc:source+='    str x29, [x9, #24]\n    add x10, sp, #160\n    str x10, [x9, #32]\n'
        else:source+=f'    ldr x10, [x9, #24]\n    cmp x29, x10\n    b.ne {done}\n'
    else:
        offset=40 if i==3 else 32
        source+=f'    ldr x10, [x9, #{offset}]\n    cbz x10, {done}\n    cmp x29, x10\n    b.ne {done}\n'
        if i==2 and site==pc:source+='    add x10, sp, #160\n    str x10, [x9, #40]\n'
        if i==3 and site==pc:source+='    str x8, [x9, #56]\n'
    # VNOP_READ's continuation is a shared native error join (MAC denial also
    # branches there). Pair each return with an observed call in this frame.
    source+='    ldr x12, [x9, #104]\n'
    if site==pc:
        source+=f'    orr x12, x12, #{1<<i}\n'
    else:
        source+=f'    tst x12, #{1<<i}\n    b.eq {done}\n    bic x12, x12, #{1<<i}\n'
    source+='    str x12, [x9, #104]\n'
    source+=f'    mov x10, #{stage}\n    str x10, [x9, #48]\n'
    if site==pc+4:source+=f'    str x0, [x9, #{64+8*i}]\n'
    color='0xff40ff80' if site==pc+4 else '0xff40c0ff'
    source+=f'    DENSE_ONCE {stage}, {color}\n    mov x23, #{stage}\n    HEXROW_VAL 1664\n'
    source+=('    mov w23, w0\n' if site==pc+4 else '    mov x23, #-1\n')+'    HEXROW_VAL 1696\n'
    return source+done+':\n'
