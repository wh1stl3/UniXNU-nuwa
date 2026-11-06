"""Extend the unconsumed r1 with root identity and scoped init/EL0 boundaries."""
from pathlib import Path
R=Path(__file__).resolve().parents[1]
s=(R/'package/kernel-mainline/CoarseStages.S').read_text()
save=s[s.index('    sub sp,sp,#256'):s.index('    mov w0,#8')]
restore=s[s.index('    ldr x9,[sp,#248]',s.index('resume:')):s.index('    sub sp,sp,#0xb0',s.index('resume:'))]
s=s.replace('    mov w1,#1\n    mov w0,#0\n', ''.join(f'    mov w0,#{i}\n    mov w1,#0xffffffff\n    bl draw\n' for i in (12,13,14))+'    mov w1,#1\n    mov w0,#0\n',1)
s=s.replace('coarse_root_return_done:\n', '''    ldr w10,[sp,#0]
    cbnz w10,coarse_root_return_done
    ldr x10,[sp,#160]
    ldr w1,[x10]
    mov w0,#12
    bl draw
coarse_root_return_done:
''',1)
s+='\n.global coarse_init_loaded\ncoarse_init_loaded:\n'+save+'''    .addr x9,coarse_state
    ldr w10,[x9,#16]
    cbnz w10,coarse_init_loaded_done
    mov w10,#1
    str w10,[x9,#16]
    mrs x10,tpidr_el1
    add x9,x9,#32
    stlr x10,[x9]
    mov w0,#13
    mov w1,#0
    bl draw
coarse_init_loaded_done:
'''+restore+'''    movz x8,#0xa000
    movk x8,#0x07a9,lsl #16
    movk x8,#0xfff0,lsl #32
    movk x8,#0xffff,lsl #48
    .jump init_loaded_resume
'''
# Common exception-return path: no calls and no framebuffer access until the
# successfully loaded init thread is armed, matched, and its saved CPSR is EL0t.
s+='\n.global coarse_el0\ncoarse_el0:\n'+'''    sub sp,sp,#32
    stp x9,x10,[sp]
    mrs x9,nzcv
    str x9,[sp,#16]
    .addr x9,coarse_state
    add x9,x9,#32
    ldar x10,[x9]
    cbz x10,el0_fast_done
    mrs x9,tpidr_el1
    cmp x9,x10
    b.ne el0_fast_done
    ldr w10,[x21,#0x110]
    tst w10,#0x1f
    b.ne el0_fast_done
    .addr x9,coarse_state
    add x9,x9,#32
    stlr xzr,[x9]
    ldr x9,[sp,#16]
    msr nzcv,x9
    ldp x9,x10,[sp]
    add sp,sp,#32
'''+save+'''    mov w0,#14
    mov w1,#1
    bl draw
'''+restore+'''    mov x19,x3
    .jump el0_resume
el0_fast_done:
    ldr x9,[sp,#16]
    msr nzcv,x9
    ldp x9,x10,[sp]
    add sp,sp,#32
    mov x19,x3
    .jump el0_resume
'''
s+='\n.global coarse_exec_result\ncoarse_exec_result:\n'+save+'''    .addr x9,coarse_state
    ldr w10,[x9,#20]
    cbnz w10,coarse_exec_result_done
    mov w10,#1
    str w10,[x9,#20]
    ldr w1,[sp]
    mov w0,#13
    bl draw
coarse_exec_result_done:
'''+restore+'    ret\n'
(R/'package/kernel-mainline/CoarseStages-r2.S').write_text(s,newline='\n')
b=(R/'scripts/build-ufs-kmain2.py').read_text().replace('CoarseStages.S','CoarseStages-r2.S').replace('KMAIN-2 r1','KMAIN-2 r2').replace('boot-kmain-2-r1.img','boot-kmain-2-r2.img')
b=b.replace('init_entry_resume=0xfffffff00769d2a8)', 'init_entry_resume=0xfffffff00769d2a8, init_loaded_resume=0xfffffff007673570, el0_resume=0xfffffff0073c3868)')
b=b.replace("(0xfffffff00769d2a4, '44f83814', 'init_entry')):","(0xfffffff00769d2a4, '44f83814', 'init_entry'),\n        (0xfffffff00767356c, '282100f0', 'init_loaded'),\n        (0xfffffff0073c3864, 'f30303aa', 'el0'),\n        (0xfffffff00769d624, 'c0035fd6', 'exec_result')):")
(R/'scripts/build-ufs-kmain2-r2.py').write_text(b,newline='\n')
print('Generated six-stage r2 source and builder')
