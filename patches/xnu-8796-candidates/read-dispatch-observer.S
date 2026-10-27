// SPDX-License-Identifier: BSD-2-Clause-Patent
// OFFLINE PROTOTYPE ONLY: no Mach-O or boot image is emitted by its test.
// A036 = actual dispatch x8; A037 = observed pinned regular-read entry PC.
// Caller/native code always runs, including when the observer scope rejects.
.macro READ_SCOPE done
    LOADABS x9, probe_read_state
    ldr x10, [x9]
    cbz x10, \done
    mrs x10, tpidr_el1
    ldr x11, [x9, #8]
    cmp x10, x11
    b.ne \done
    ldr x10, [x9, #40]
    cbz x10, \done
    cmp x29, x10
    b.ne \done
    ldr x10, [x9, #104]
    tbz x10, #3, \done
.endm
.text
.global read_header_reset
read_header_reset:
    PROBE_SAVE
    mov x23, #0
    HEXROW_VAL 1728
    mov x23, #0
    HEXROW_VAL 1760
    PROBE_RESTORE
    LOADABS x30, read_header_return
    b native_vn_rdwr
.global read_dispatch_target
read_dispatch_target:
    PROBE_SAVE
    READ_SCOPE .Ldispatch_done
    mov x23, x8
    HEXROW_VAL 1728
.Ldispatch_done:
    PROBE_RESTORE
    LOADABS x30, read_dispatch_return
    br x8
.global read_apfs_entry
read_apfs_entry:
    PROBE_SAVE
    READ_SCOPE .Lentry_done
    LOADABS x11, read_dispatch_return
    cmp x30, x11
    b.ne .Lentry_done
    ldr x10, [x9, #56]
    LOADABS x11, read_apfs_address
    cmp x10, x11
    b.ne .Lentry_done
    // The real VNOP_READ argument structure is at caller SP+8.
    add x10, sp, #184
    cmp x0, x10
    b.ne .Lentry_done
    mov x23, x11
    HEXROW_VAL 1760
.Lentry_done:
    PROBE_RESTORE
    .inst 0xd10403ff  // exact displaced sub sp,sp,#0x100
    b read_apfs_resume
.balign 4
hex_font:
    .word 0xf999f, 0x26227, 0xf1f8f, 0xf1f1f
    .word 0x99f11, 0xf8f1f, 0xf8f9f, 0xf1244
    .word 0xf9f9f, 0xf9f1f, 0xf9f99, 0xe9e9e
    .word 0xf888f, 0xe999e, 0xf8f8f, 0xf8f88
