// SPDX-License-Identifier: BSD-2-Clause-Patent
// Stackless diagnostic hooks for the fixed Darwin22 start.s cold-boot path.
// x0 (entry) / x20 (later hooks) contains the unmodified physical boot_args.
// x9-x17 are dead at the three selected hook sites; x0-x8/x18-x30 survive.
//
// Layout is deliberate: the 16-entry exception vector table sits at the very start
// of this page so that "msr vbar_el1, <page base>" points at it. All entries branch
// to probe_exception, which reports ESR/ELR/FAR through the geometry snapshot and
// never relies on x20 (an exception can fire when x20 holds anything).

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

// Snapshot-based drawing: framebuffer base and line stride come from probe_scratch,
// so it stays valid after the MMU switch and inside an exception where x20 is dead.
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

// 16 hex digits of a system register, drawn from the snapshot. 4x4 squares,
// 24 bytes apart, one row of 5 pixels per hex bit row (same glyphs as hex_font).
.macro HEXROW_VAL y
    adr         x15, probe_scratch
    ldr         x21, [x15]
    ldr         x22, [x15, #8]
    cbz         x21, .Lhex_done\@
    mov         x24, #60
    mov         x25, #\y
    madd        x21, x22, x25, x21
.Lhex_digit\@:
    lsr         x25, x23, x24
    and         x25, x25, #15
    adr         x26, hex_font
    ldr         w27, [x26, x25, lsl #2]
    mov         x28, #0
.Lhex_row\@:
    mov         x17, #0
.Lhex_col\@:
    mov         x16, #19
    sub         x16, x16, x28, lsl #2
    sub         x16, x16, x17
    lsr         w15, w27, w16
    and         w15, w15, #1
    neg         w15, w15
    lsl         x14, x28, #2
    madd        x13, x14, x22, x21
    add         x13, x13, x17, lsl #4
    mov         x12, #4
.Lhex_pixel_row\@:
    stp         w15, w15, [x13]
    stp         w15, w15, [x13, #8]
    add         x13, x13, x22
    subs        x12, x12, #1
    b.ne        .Lhex_pixel_row\@
    add         x17, x17, #1
    cmp         x17, #4
    b.lo        .Lhex_col\@
    add         x28, x28, #1
    cmp         x28, #5
    b.lo        .Lhex_row\@
    add         x21, x21, #24*4
    subs        x24, x24, #4
    b.ge        .Lhex_digit\@
.Lhex_done\@:
.endm
// Same renderer, but the value comes from a system register.
.macro HEXROW_SNAP reg, y
    mrs         x23, \reg
    HEXROW_VAL \y
.endm

// Band layout: every band is 32 rows tall with a 48-row pitch (16 rows of gap),
// starting at row 256. Hex rows use the same pitch and are 20 rows of glyphs.
//   256 blue (__start)      304 yellow (page tables)  352 magenta (before SCTLR)
//   400 cyan (after SCTLR+isb)  448 white (_arm_init)  496 purple (_current_percpu_base)
//   544 brown (_arm_vm_init)  592 teal (_pmap_bootstrap)  640 orange (_kernel_bootstrap)
//   688 red (exception)      736 ESR_EL1  784 ELR_EL1  832 FAR_EL1
//   880 teal-gray (arm_vm_init+0x54)  928 olive (arm_vm_init+0xa4)
//   976 hot pink (panic)  1024 violet (panic_trap_to_debugger)
//   1072 first eight bytes of the panic format string, as hex
// The firmware logo is a background layer drawn before the kernel, so bands
// drawn over it stay visible; the firmware only redraws the menu below row
// ~1150, so no band may live there. Height check 1104; the screen is 3200 rows.
// Draw-once guard: the flag byte lives in the probe's own flag page, so a hook
// that is hit repeatedly costs one branch instead of a full band redraw.
.macro BAND_ONCE idx, y, color
    adr         x15, probe_scratch
    ldr         x9, [x15]
    cbz         x9, .Lno_device\@
    adr         x16, probe_flags
    ldrb        w17, [x16, #\idx]
    cbnz        w17, 9f
    mov         w17, #1
    strb        w17, [x16, #\idx]
    dsb         sy
    BAND_SNAPSHOT \y, \color
9:
.Lno_device\@:
.endm
// Counter hook: renders the call count as hex for the first four calls, then
// only counts. Cheap enough for hooks that run thousands of times.
.macro BAND_ONCE20 idx, y, color
    BAND x20, \y, \color
.endm
.macro COUNT16 idx, y
    adr         x15, probe_scratch
    ldr         x9, [x15]
    cbz         x9, .Lno_device\@
    adr         x16, probe_flags
    ldrb        w17, [x16, #\idx]
    cmp         w17, #4
    b.hs        9f
    add         w17, w17, #1
    strb        w17, [x16, #\idx]
    dsb         sy
    mov         x23, x17
    HEXROW_VAL \y
9:
.Lno_device\@:
.endm


.text
.balign 4096
.global probe_vectors
probe_vectors:
    .rept 16
    .space 124
    b probe_exception
    .endr
.balign 4
.global probe_exception
probe_exception:
    adr         x15, probe_scratch
    ldr         x9, [x15]
    cbz         x9, exception_stop
    BAND_ONCE 0, 1120, 0xffff0000
    HEXROW_SNAP esr_el1, 1152
    HEXROW_SNAP elr_el1, 1184
    HEXROW_SNAP far_el1, 1216
    dsb         sy
.global exception_stop
exception_stop:
    b exception_stop

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
    // Point the exception vectors at this page (its identity address), so an
    // exception taken while the MMU is on still lands on our reporter. The page
    // is reachable through the V=P identity mapping until pmap is rebuilt.
    adr         x13, probe_vectors
    msr         vbar_el1, x13
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
    cmp         x9, #1248                         // must cover the FAR row at 1216
    b.lo        .Lsnap_done\@
    ldr         x9, [x20, #0x50]
    and         x9, x9, #255
    cmp         x9, #32
    b.ne        .Lsnap_done\@
    adr         x9, probe_scratch
    stp         x13, x14, [x9]                    // framebuffer base, line stride
.Lsnap_done\@:
.endm
.global probe_entry
probe_entry:
    BAND x0, 256, 0xff0080ff
    b original_first_cpu
.global probe_tables
probe_tables:
    BAND x20, 288, 0xffffff00
    .inst original_tables_word
    b original_tables_resume
.global probe_mmu
probe_mmu:
    BAND x20, 320, 0xffff00ff
    MAP_FB
    SNAP_VIDEO
    .inst original_mmu_word
    b original_mmu_resume

// After "msr sctlr_el1" the PC is still a physical address, kept valid by the
// V=P mapping. The original isb is replayed FIRST so the SCTLR write is
// architecturally synchronised before anything is drawn; then the band is drawn
// and control returns to the instruction after the isb.
.global probe_mmu_on
probe_mmu_on:
    .inst original_mmu_on_word
    BAND_ONCE 1, 352, 0xff00ffff
.global probe_mmu_on_replay
probe_mmu_on_replay:
    b original_mmu_on_resume

// arm_init is entered at the KVA, so this hook also proves the TTBR1 mapping is
// live and usable for instruction fetch.
.global probe_arm_init
probe_arm_init:
    BAND_ONCE 2, 384, 0xffffffff
    // Mainline shim, not a measurement: the platform-expert path reads the per-CPU
    // base through TPIDR_EL1 before XNU has built cpu_data_t, and start.s clears
    // TPIDR_EL1 after enabling the MMU. Point it at a zeroed page: cpu_number at
    // +0xe8 then reads 0, which is the correct answer for the boot CPU. XNU
    // overwrites TPIDR_EL1 with the real per-CPU data later in cpu_bootstrap.
    adr         x15, probe_zero
    msr         TPIDR_EL1, x15
.global probe_arm_init_replay
probe_arm_init_replay:
    .inst original_arm_init_word
    b original_arm_init_resume
.balign 4
// C-entry markers past arm_init. They share the snapshot so they keep working
// after MMU is on, and they are the only signal available before pmap rebuilds
// the tables.
// Dense markers: one trial answers many questions at once. Every entry below is a
// function entry (or a pinned offset inside arm_vm_init) on the path from arm_init to
// pmap_bootstrap, plus the whole panic family.
.global probe_cpu_base
probe_cpu_base:
    BAND_ONCE 3, 416, 0xff8000ff
.global probe_cpu_base_replay
probe_cpu_base_replay:
    .inst original_cpu_base_word
    b original_cpu_base_resume
.global probe_arm_vm
probe_arm_vm:
    BAND_ONCE 4, 448, 0xff804000
.global probe_arm_vm_replay
probe_arm_vm_replay:
    .inst original_arm_vm_word
    b original_arm_vm_resume
.global probe_pmap
probe_pmap:
    BAND_ONCE 5, 480, 0xff00ff80
.global probe_pmap_replay
probe_pmap_replay:
    .inst original_pmap_word
    b original_pmap_resume
.global probe_kernel_bootstrap
probe_kernel_bootstrap:
    BAND_ONCE 6, 512, 0xffff8040
.global probe_kernel_bootstrap_replay
probe_kernel_bootstrap_replay:
    .inst original_kernel_bootstrap_word
    b original_kernel_bootstrap_resume
.global probe_avm_bases
probe_avm_bases:
    BAND_ONCE 7, 544, 0xff008080
.global probe_avm_bases_replay
probe_avm_bases_replay:
    .inst original_avm_bases_word
    b original_avm_bases_resume
.global probe_avm_memcheck
probe_avm_memcheck:
    BAND_ONCE 8, 576, 0xff808000
.global probe_avm_memcheck_replay
probe_avm_memcheck_replay:
    .inst original_avm_memcheck_word
    b original_avm_memcheck_resume
.global probe_avm_physmap
probe_avm_physmap:
    BAND_ONCE 9, 608, 0xff8080c0
.global probe_avm_physmap_replay
probe_avm_physmap_replay:
    .inst original_avm_physmap_word
    b original_avm_physmap_resume
.global probe_avm_slide
probe_avm_slide:
    BAND_ONCE 10, 640, 0xff808080
.global probe_avm_slide_replay
probe_avm_slide_replay:
    .inst original_avm_slide_word
    b original_avm_slide_resume
.global probe_early_random
probe_early_random:
    COUNT16 11, 784
.global probe_early_random_replay
probe_early_random_replay:
    .inst original_early_random_word
    b original_early_random_resume
.global probe_dt_lookup
probe_dt_lookup:
    BAND_ONCE 14, 672, 0xff9400d3
.global probe_dt_lookup_replay
probe_dt_lookup_replay:
    .inst original_dt_lookup_word
    b original_dt_lookup_resume
.global probe_soc_base
probe_soc_base:
    BAND_ONCE 15, 704, 0xff00c0c0
.global probe_soc_base_replay
probe_soc_base_replay:
    .inst original_soc_base_word
    b original_soc_base_resume
.global probe_timer_regs
probe_timer_regs:
       BAND_ONCE 16, 736, 0xffff80c0
.global probe_timer_regs_replay
probe_timer_regs_replay:
       .inst original_timer_regs_word
    b original_timer_regs_resume
.global probe_wfe_timeout
probe_wfe_timeout:
       BAND_ONCE 17, 768, 0xff9400d3
.global probe_wfe_timeout_replay
probe_wfe_timeout_replay:
       .inst original_wfe_timeout_word
    b original_wfe_timeout_resume
.global probe_wfe_init
probe_wfe_init:
       BAND_ONCE 18, 800, 0xff00c0c0
.global probe_wfe_init_replay
probe_wfe_init_replay:
       .inst original_wfe_init_word
    b original_wfe_init_resume
.global probe_misc_boot_args
probe_misc_boot_args:
       BAND_ONCE 19, 832, 0xff80c000
.global probe_misc_boot_args_replay
probe_misc_boot_args_replay:
       .inst original_misc_boot_args_word
    b original_misc_boot_args_resume
.global probe_misc_regs
probe_misc_regs:
       BAND_ONCE 20, 864, 0xffffc000
.global probe_misc_regs_replay
probe_misc_regs_replay:
       .inst original_misc_regs_word
    b original_misc_regs_resume
.global probe_cpu_topo
probe_cpu_topo:
    BAND_ONCE 14, 896, 0xff80c000
.global probe_cpu_topo_replay
probe_cpu_topo_replay:
    .inst original_cpu_topo_word
    b original_cpu_topo_resume
.global probe_cpu_bootstrap
probe_cpu_bootstrap:
    BAND_ONCE 15, 928, 0xffffc000
.global probe_cpu_bootstrap_replay
probe_cpu_bootstrap_replay:
    .inst original_cpu_bootstrap_word
    b original_cpu_bootstrap_resume
.global probe_machine_startup
probe_machine_startup:
    BAND_ONCE 16, 960, 0xffc000ff
.global probe_machine_startup_replay
probe_machine_startup_replay:
    .inst original_machine_startup_word
    b original_machine_startup_resume
.global probe_panic
probe_panic:
    BAND_ONCE 17, 992, 0xffff1493
.global probe_panic_replay
probe_panic_replay:
    .inst original_panic_word
    b original_panic_resume
.global probe_panic_options
probe_panic_options:
    BAND_ONCE 18, 1024, 0xffc000c0
.global probe_panic_options_replay
probe_panic_options_replay:
    .inst original_panic_options_word
    b original_panic_options_resume
.global probe_panic_trap
probe_panic_trap:
    BAND_ONCE 19, 1040, 0xff9400ff
    // x0 is the panic format string: render its first eight bytes as hex so the
    // message can be read off the screen, the only output channel we have.
    ldr         x23, [x0]
    rev         x23, x23
    HEXROW_VAL 1088
.global probe_panic_trap_replay
probe_panic_trap_replay:
    .inst original_panic_trap_word
    b original_panic_trap_resume
.balign 8
.global probe_scratch
probe_scratch:
    .quad 0, 0

// Early exception output for the kernel's own physical vectors: red band, then
// ESR/ELR/FAR in 16 hex digits each, read from boot_args through x20. This path
// is only live before the probe page takes over VBAR.
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
    cmp x10, #1248
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
    BAND_ONCE20 22, 1120, 0xffff0000
    HEXROW esr_el1, 1152
    HEXROW elr_el1, 1184
    HEXROW far_el1, 1216
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

.balign 4096
.global probe_zero
probe_zero:
    .space 4096
// The flag page is separate from the per-CPU shim page: the kernel writes into
// the shim page, which must not corrupt the flags.
.balign 4096
.global probe_flags
probe_flags:
    .space 4096
