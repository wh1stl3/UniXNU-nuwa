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

// Pre-MMU preparation for the post-MMU hooks. The bootstrap tables map only the
// kernel's own physical range, so the framebuffer that is reachable while the
// MMU is off is unmapped afterwards. Install one 1 GiB identity block for
// 0x80000000-0xBFFFFFFF as Device-nGnRnE (MAIR index 3, the index start.s sets
// from MAIR_DISABLE), never overwriting an existing descriptor, then snapshot
// the geometry from boot_args into this page so the post-MMU hooks no longer
// depend on the boot_args physical address.
.macro MAP_FB
    mrs         x13, ttbr0_el1
    movz        x14, #0xf000
    movk        x14, #0xffff, lsl #16
    movk        x14, #0xffff, lsl #32
    and         x13, x13, x14                    // V=P L1 table physical address
    ldr         x15, [x13, #16]                  // L1 slot 2 covers 0x80000000
    cbnz        x15, .Lmap_skip\@                 // occupied: leave mappings alone
    movz        x15, #0x040d                      // valid block, AF, AttrIndx 3
    movk        x15, #0x8000, lsl #16             // 0x80000000
    movk        x15, #0x0060, lsl #48             // PXN | UXN
    str         x15, [x13, #16]
    dsb         ish
    b           .Lmap_done\@
.Lmap_skip\@:
    // The slot already maps something we did not audit: report "no framebuffer"
    // so SNAP_VIDEO stores nothing and the post-MMU hooks draw nothing.
    mov         x15, #0
.Lmap_done\@:
.endm
.macro SNAP_VIDEO
    cbz         x15, .Lsnap_done\@                  // no mapping, no snapshot
    ldr         x13, [x20, #0x28]
    cbz         x13, .Lsnap_done\@
    ldr         x14, [x20, #0x38]
    cmp         x14, #0x10, lsl #12
    b.hi        .Lsnap_done\@
    tst         x14, #7
    b.ne        .Lsnap_done\@
    ldr         x9, [x20, #0x48]
    cmp         x9, #864                          // must cover the white band at 832
    b.lo        .Lsnap_done\@
    ldr         x9, [x20, #0x50]
    and         x9, x9, #255
    cmp         x9, #32
    b.ne        .Lsnap_done\@
    adr         x9, probe_scratch
    stp         x13, x14, [x9]                    // framebuffer base, line stride
.Lsnap_done\@:
.endm
.global probe_mmu
probe_mmu:
    BAND x20, 448, 0xffff00ff
    MAP_FB
    SNAP_VIDEO
    .inst original_mmu_word
    b original_mmu_resume

// After "msr sctlr_el1" the PC is still a physical address, kept valid by the
// V=P mapping. The original isb is replayed FIRST so the SCTLR write is
// architecturally synchronised before anything is drawn; then the band is drawn
// and control returns to the instruction after the isb.
.macro BAND_SNAPSHOT y, color
    adr         x15, probe_scratch
    ldr         x9, [x15]
    cbz         x9, .Ldraw_done\@
    ldr         x10, [x15, #8]
    mov         x11, #\y
    madd        x9, x10, x11, x9
    lsl         x10, x10, #5
    mov         w12, #(\color & 0xffff)
    movk        w12, #((\color >> 16) & 0xffff), lsl #16
1:
    stp         w12, w12, [x9], #8
    subs        x10, x10, #8
    b.hi        1b
    dsb         sy
.Ldraw_done\@:
.endm
.global probe_mmu_on
probe_mmu_on:
    .inst original_mmu_on_word
    BAND_SNAPSHOT 736, 0xff00ffff
.global probe_mmu_on_replay
probe_mmu_on_replay:
    b original_mmu_on_resume

// arm_init is entered at the KVA, so this hook also proves the TTBR1 mapping is
// live and usable for instruction fetch.
.global probe_arm_init
probe_arm_init:
    BAND_SNAPSHOT 832, 0xffffffff
.global probe_arm_init_replay
probe_arm_init_replay:
    .inst original_arm_init_word
    b original_arm_init_resume
.balign 4
// C-entry markers past arm_init. They share the snapshot so they keep working
// after MMU is on, and they are the only signal available before pmap rebuilds
// the tables.
.global probe_cpu_base
probe_cpu_base:
    BAND_SNAPSHOT 896, 0xff8000ff
.global probe_cpu_base_replay
probe_cpu_base_replay:
    .inst original_cpu_base_word
    b original_cpu_base_resume
.global probe_arm_vm
probe_arm_vm:
    BAND_SNAPSHOT 960, 0xff804000
.global probe_arm_vm_replay
probe_arm_vm_replay:
    .inst original_arm_vm_word
    b original_arm_vm_resume
.global probe_pmap
probe_pmap:
    BAND_SNAPSHOT 1024, 0xff00ff80
.global probe_pmap_replay
probe_pmap_replay:
    .inst original_pmap_word
    b original_pmap_resume
.global probe_kernel_bootstrap
probe_kernel_bootstrap:
    BAND_SNAPSHOT 1088, 0xffff8040
.global probe_kernel_bootstrap_replay
probe_kernel_bootstrap_replay:
    .inst original_kernel_bootstrap_word
    b original_kernel_bootstrap_resume
.balign 8
.global probe_scratch
probe_scratch:
    .quad 0, 0

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
