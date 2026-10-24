// SPDX-License-Identifier: BSD-2-Clause-Patent
// Stackless diagnostic hooks for the fixed Darwin22 start.s cold-boot path.
// x0 (entry) / x20 (later hooks) contains the unmodified physical boot_args.
// x9-x17 are dead at the three selected hook sites; x0-x8/x18-x30 survive.
.text
.balign 4
.macro BAND args, y, color
    ldr x9, [\args, #0x28]
    cbz x9, 9f
    ldr x10, [\args, #0x38]
    ldr x11, [\args, #0x48]
    cmp x11, #(\y+32)
    b.lo 9f
    cbz x10, 9f
    cmp x10, #0x10, lsl #12
    b.hi 9f
    ldr x11, [\args, #0x50]
    and x11, x11, #255
    cmp x11, #32
    b.ne 9f
    tst x10, #7
    b.ne 9f
    mov x11, #\y
    madd x9, x10, x11, x9
    lsl x10, x10, #5
    mov w12, #(\color & 0xffff)
    movk w12, #((\color >> 16) & 0xffff), lsl #16
1:
    stp w12, w12, [x9], #8
    subs x10, x10, #8
    b.hi 1b
    dsb sy
9:
.endm
.global probe_entry
probe_entry:
    BAND x0, 256, 0xff0080ff
    b original_first_cpu
.global probe_tables
probe_tables:
    BAND x20, 352, 0xffffff00
    .inst original_tables_word
    b original_tables_resume
.global probe_mmu
probe_mmu:
    BAND x20, 448, 0xffff00ff
    .inst original_mmu_word
    b original_mmu_resume

// Early exception output: red band, then ESR/ELR/FAR in 16 hex digits each.
// These hooks replace only the original physical LowExceptionVector self loops.
// Once the kernel switches to its normal virtual VBAR these hooks are inactive.
.macro HEXROW reg, y
    mrs x23, \reg
    mov x24, #60
    ldr x21, [x20, #0x28]
    ldr x22, [x20, #0x38]
    mov x25, #\y
    madd x21, x22, x25, x21
hex_digit_\@:
    lsr x25, x23, x24
    and x25, x25, #15
    adr x26, hex_font
    ldr w27, [x26, x25, lsl #2]
    mov x28, #0
hex_row_\@:
    // 4 columns, each a 4x4 square; high glyph bit first.
    mov x17, #0
hex_col_\@:
    mov x16, #19
    sub x16, x16, x28, lsl #2
    sub x16, x16, x17
    lsr w15, w27, w16
    and w15, w15, #1
    neg w15, w15
    lsl x14, x28, #2
    madd x13, x14, x22, x21
    add x13, x13, x17, lsl #4
    mov x12, #4
hex_pixel_row_\@:
    stp w15, w15, [x13]
    stp w15, w15, [x13, #8]
    add x13, x13, x22
    subs x12, x12, #1
    b.ne hex_pixel_row_\@
    add x17, x17, #1
    cmp x17, #4
    b.lo hex_col_\@
    add x28, x28, #1
    cmp x28, #5
    b.lo hex_row_\@
    add x21, x21, #24*4
    subs x24, x24, #4
    b.ge hex_digit_\@
.endm
.global probe_fault
probe_fault:
    ldr x9, [x20, #0x28]
    cbz x9, fault_stop
    ldr x10, [x20, #0x48]
    cmp x10, #704
    b.lo fault_stop
    ldr x10, [x20, #0x38]
    cmp x10, #1536
    b.lo fault_stop
    cmp x10, #0x10, lsl #12
    b.hi fault_stop
    tst x10, #7
    b.ne fault_stop
    ldr x10, [x20, #0x50]
    and x10, x10, #255
    cmp x10, #32
    b.ne fault_stop
    BAND x20, 544, 0xffff0000
    HEXROW esr_el1, 608
    HEXROW elr_el1, 640
    HEXROW far_el1, 672
    dsb sy
.global fault_stop
fault_stop:
    b fault_stop
.balign 4
hex_font:
    .word 0xf999f, 0x26227, 0xf1f8f, 0xf1f1f
    .word 0x99f11, 0xf8f1f, 0xf8f9f, 0xf1244
    .word 0xf9f9f, 0xf9f1f, 0xf9f99, 0xe9e9e
    .word 0xf888f, 0xe999e, 0xf8f8f, 0xf8f88
