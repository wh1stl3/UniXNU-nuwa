"""Pinned native exec observations; only unreviewed restore task release is held."""
import struct
FIRST=0xfffffff00769d5f4
RETURN=FIRST+4
RELEASE=0xfffffff00769d230
CALLS=((0xfffffff00769cf10,'_mac_execve_enter'),
       (0xfffffff00769cf50,'_cloneproc'),
       (0xfffffff00769cfa8,'_exec_activate_image'),
       (0xfffffff00769d0d8,'_proc_exec_switch_task'),
       (0xfffffff00769d0f4,'_ipc_task_enable'),
       (0xfffffff00769d10c,'_process_signature'),
       (0xfffffff00769d1f4,'_task_clear_return_wait'),
       (RELEASE,'_task_clear_return_wait'),
       (0xfffffff00769d21c,'_task_terminate_internal'))
def add_sites(add,raw,m,backed):
    add(RETURN,'_load_init_program_at_path','___mac_execve','continuation',FIRST)
    fn='___mac_execve';add(m['symbols'][fn],fn,fn,'entry')
    for pc,target in CALLS:
        word=struct.unpack_from('<I',raw,backed(m,pc))[0]
        imm=word&0x3ffffff
        if imm&(1<<25):imm-=1<<26
        if word&0xfc000000!=0x94000000 or pc+imm*4!=m['symbols'][target]:raise ValueError('Pinned exec call changed')
        add(pc,fn,target,'call',pc);add(pc+4,fn,target,'continuation',pc)
def observe(site):
    done=f'.Lexec_observe_done_{site:x}'
    s=['    adr x9, probe_exec_state']
    if site==FIRST:
        initial=s+['    mov x10, #1','    str x10, [x9]','    str xzr, [x9, #8]',
            '    mov x10, #-1','    stp x10, x10, [x9, #16]','    str x10, [x9, #32]',
            '    str x10, [x9, #40]','    str xzr, [x9, #72]']
        for row in (1440,1472,1536,1600):initial+=['    mov x23, #-1',f'    HEXROW_VAL {row}']
        initial+=['    mov x23, #0','    HEXROW_VAL 1504']
        return '\n'.join(initial)+'\n'
    relevant={RETURN,0xfffffff00769cf14,0xfffffff00769cf54,0xfffffff00769cfac,
              0xfffffff00769d0d8,0xfffffff00769d0dc,0xfffffff00769d110,RELEASE}
    if site not in relevant:return ''
    s+=['    ldr x10, [x9]',f'    cbz x10, {done}']
    result={RETURN:(32,1536),0xfffffff00769cf14:(40,1600),
            0xfffffff00769cfac:(16,1440),0xfffffff00769d110:(24,1472)}
    if site in result:
        off,row=result[site];s += [f'    str x0, [x9, #{off}]','    mov w23, w0']
        if site==RETURN:s+=['    str xzr, [x9]','    str xzr, [x9, #8]']
        s += [f'    HEXROW_VAL {row}']
    if site==0xfffffff00769cf54:s+=['    str x0, [x9, #48]']
    if site==0xfffffff00769d0d8:s+=['    str x3, [x9, #72]']
    if site==0xfffffff00769d0dc:s+=['    mov x10, #1','    str x10, [x9, #8]','    str x0, [x9, #56]','    mov x23, #1','    HEXROW_VAL 1504']
    if site==RELEASE:
        s += ['    ldr x10, [x9, #8]',f'    cbz x10, {done}',
              '    cmp w1, #2',f'    b.ne {done}',
              '    ldr x10, [x9, #72]','    cmp x0, x10',f'    b.ne {done}',
              '    str x0, [x9, #64]','    DISPLAY_CHECK 239','    DENSE_ONCE 239, 0xffff40ff',
              '.global probe_restore_release_hold','probe_restore_release_hold:',
              '    b probe_restore_release_hold']
    return '\n'.join(s+[done+':'])+'\n'
