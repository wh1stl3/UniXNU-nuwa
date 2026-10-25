// SPDX-License-Identifier: BSD-2-Clause-Patent
// Stackless diagnostic hooks for the fixed Darwin22 start.s cold-boot path.
// x0 (entry) / x20 (later hooks) contains the unmodified physical boot_args.
// x9-x17 are dead at the three selected hook sites; x0-x8/x18-x30 survive.
//
// Layout is deliberate: the 16-entry exception vector table sits at the very start
// of this page so that "msr vbar_el1, <page base>" points at it. All entries branch
// to probe_exception, which reports ESR/ELR/FAR through the geometry snapshot and
// never relies on x20 (an exception can fire when x20 holds anything).

// Post-MMU hooks can interrupt live temporaries, not just ABI call boundaries.
// Preserve every renderer scratch GPR and NZCV before replaying native code.
.macro PROBE_SAVE
    sub sp, sp, #176
    stp x9, x10, [sp, #0]
    stp x11, x12, [sp, #16]
    stp x13, x14, [sp, #32]
    stp x15, x16, [sp, #48]
    stp x17, x18, [sp, #64]
    stp x19, x20, [sp, #80]
    stp x21, x22, [sp, #96]
    stp x23, x24, [sp, #112]
    stp x25, x26, [sp, #128]
    stp x27, x28, [sp, #144]
    mrs x9, nzcv
    str x9, [sp, #160]
.endm
.macro PROBE_RESTORE
    ldr x9, [sp, #160]
    msr nzcv, x9
    ldp x9, x10, [sp, #0]
    ldp x11, x12, [sp, #16]
    ldp x13, x14, [sp, #32]
    ldp x15, x16, [sp, #48]
    ldp x17, x18, [sp, #64]
    ldp x19, x20, [sp, #80]
    ldp x21, x22, [sp, #96]
    ldp x23, x24, [sp, #112]
    ldp x25, x26, [sp, #128]
    ldp x27, x28, [sp, #144]
    add sp, sp, #176
.endm

.macro BAND args, y, color
    ldr x9, [\args, #0x28]
    cbz x9, 9f
    ldr x10, [\args, #0x38]
    cmp x10, #384
    b.lo 9f
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
    mov x11, #(256 + ((\y - 256) % 512))
    madd x9, x10, x11, x9
    add x9, x9, #(((\y - 256) / 512) * 384)
    mov w12, #(\color & 0xffff)
    movk w12, #((\color >> 16) & 0xffff), lsl #16
    mov x13, #32
.Ltile_row\@:
    mov x14, #48
.Ltile_col\@:
    stp w12, w12, [x9], #8
    subs x14, x14, #1
    b.ne .Ltile_col\@
    add x9, x9, x10
    sub x9, x9, #384
    subs x13, x13, #1
    b.ne .Ltile_row\@
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
    mov x11, #(256 + ((\y - 256) % 512))
    madd x9, x10, x11, x9
    add x9, x9, #(((\y - 256) / 512) * 384)
    mov w12, #(\color & 0xffff)
    movk w12, #((\color >> 16) & 0xffff), lsl #16
    mov x13, #32
.Ltile_row\@:
    mov x14, #48
.Ltile_col\@:
    stp w12, w12, [x9], #8
    subs x14, x14, #1
    b.ne .Ltile_col\@
    add x9, x9, x10
    sub x9, x9, #384
    subs x13, x13, #1
    b.ne .Ltile_row\@
    dsb sy
.Ldraw_done\@:
.endm

// 16 hex digits of a system register, drawn from the snapshot. 4x4 squares,
// 24 bytes apart, one row of 5 pixels per hex bit row (same glyphs as hex_font).
.macro HEX_DIGITS
.Ldigits_digit\@:
    lsr         x25, x23, x24
    and         x25, x25, #15
    adr         x26, hex_font
    ldr         w27, [x26, x25, lsl #2]
    mov         x28, #0
.Ldigits_row\@:
    mov         x17, #0
.Ldigits_col\@:
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
.Ldigits_pixel_row\@:
    stp         w15, w15, [x13]
    stp         w15, w15, [x13, #8]
    add         x13, x13, x22
    subs        x12, x12, #1
    b.ne        .Ldigits_pixel_row\@
    add         x17, x17, #1
    cmp         x17, #4
    b.lo        .Ldigits_col\@
    add         x28, x28, #1
    cmp         x28, #5
    b.lo        .Ldigits_row\@
    add         x21, x21, #24*4
    subs        x24, x24, #4
    b.ge        .Ldigits_digit\@
.endm
.macro HEX_RENDER y
    // Four-nibble field ID followed by sixteen value nibbles. 4x4 glyph pixels.
    mov x19, x23
    .if \y >= 1088
    mov x25, #(224 + ((\y - 1088) / 32) * 28)
    .else
    mov x25, #756
    .endif
    madd x21, x22, x25, x21
    add x21, x21, #1024
    // Clear the entire 480x20 data rectangle, including inter-digit gaps.
    mov x9, x21
    mov x10, #20
.Lclear_row\@:
    mov x12, #240
.Lclear_col\@:
    stp wzr, wzr, [x9], #8
    subs x12, x12, #1
    b.ne .Lclear_col\@
    add x9, x9, x22
    sub x9, x9, #1280
    subs x10, x10, #1
    b.ne .Lclear_row\@
    mov x23, #(0xa000 + (\y / 32))
    mov x24, #12
    HEX_DIGITS
    mov x23, x19
    mov x24, #60
    HEX_DIGITS
.endm
.macro HEXROW_VAL y
    adr x15, probe_scratch
    ldr x21, [x15]
    ldr x22, [x15, #8]
    cbz x21, .Lhex_done\@
    HEX_RENDER \y
.Lhex_done\@:
.endm
// Same renderer, but the value comes from a system register.
.macro HEXROW_SNAP reg, y
    mrs         x23, \reg
    HEXROW_VAL \y
.endm
// Read an absolute 64-bit kernel address into x23 and render it. The address
// comes from the linker as an absolute symbol, so it must be materialised
// with movz/movk: the probe runs at the kernel's KVA, but the linker only
// knows the numeric value.
.macro LOADABS reg, sym
    movz        \reg, #((\sym) & 0xffff)
    movk        \reg, #(((\sym) >> 16) & 0xffff), lsl #16
    movk        \reg, #(((\sym) >> 32) & 0xffff), lsl #32
    movk        \reg, #(((\sym) >> 48) & 0xffff), lsl #48
.endm
// Render the 64-bit value at (absolute address + offset).
.macro HEXROW_AT sym, off, y
    LOADABS     x23, \sym
    ldr         x23, [x23, #\off]
    HEXROW_VAL  \y
.endm

// v21 screen: 96x32 stage tiles in x=0..191,y=256..767.
// Logical stage rows >=800 wrap into the second tile column. Hex records
// occupy x=256..735 with a four-nibble ID and sixteen value nibbles.
// Logical hex rows >=1088 map to y=224+28*((row-1088)/32); IDs are
// A000+(logical_row/32). Counter 784 uses y756. Nothing writes y>=800.
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
// Dense panel at x832..1295/y256..759, outside both earlier panels.
// Flags 128..287 are reserved for these independently numbered call/return edges.
.macro DENSE_ONCE idx, color
    adr x15, probe_scratch
    ldr x9, [x15]
    cbz x9, .Ldense_done\@
    ldr x10, [x15, #8]
    mov x11, #5376
    cmp x10, x11
    b.lo .Ldense_done\@
    adr x16, probe_flags
    ldrb w17, [x16, #(128+\idx)]
    cbnz w17, .Ldense_done\@
    mov w17, #1
    strb w17, [x16, #(128+\idx)]
    mov x11, #(256+(\idx/10)*32)
    madd x9, x10, x11, x9
    mov x11, #((832+(\idx%10)*48)*4)
    add x9, x9, x11
    mov w12, #(\color & 0xffff)
    movk w12, #((\color >> 16) & 0xffff), lsl #16
    mov x13, #24
.Ldense_row\@:
    mov x14, #16
.Ldense_col\@:
    stp w12, w12, [x9], #8
    subs x14, x14, #1
    b.ne .Ldense_col\@
    add x9, x9, x10
    sub x9, x9, #128
    subs x13, x13, #1
    b.ne .Ldense_row\@
    dsb sy
.Ldense_done\@:
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
    cmp x14, #2944
    b.lo .Lsnap_done\@
    cmp         x14, #0x10, lsl #12
    b.hi        .Lsnap_done\@
    tst         x14, #7
    b.ne        .Lsnap_done\@
    ldr         x9, [x20, #0x48]
    cmp         x9, #800                          // all diagnostic output is above row 800
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
    PROBE_SAVE
    BAND_ONCE 2, 384, 0xffffffff
    // Mainline shim, not a measurement: the platform-expert path reads the per-CPU
    // base through TPIDR_EL1 before XNU has built cpu_data_t, and start.s clears
    // TPIDR_EL1 after enabling the MMU. Point it at a zeroed page: cpu_number at
    // +0xe8 then reads 0, which is the correct answer for the boot CPU. XNU
    // overwrites TPIDR_EL1 with the real per-CPU data later in cpu_bootstrap.
    adr         x15, probe_zero
    msr         TPIDR_EL1, x15
    PROBE_RESTORE
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
    PROBE_SAVE
    BAND_ONCE 3, 416, 0xff8000ff
    PROBE_RESTORE
.global probe_cpu_base_replay
probe_cpu_base_replay:
    .inst original_cpu_base_word
    b original_cpu_base_resume
.global probe_arm_vm
probe_arm_vm:
    PROBE_SAVE
    BAND_ONCE 4, 448, 0xff804000
    PROBE_RESTORE
.global probe_arm_vm_replay
probe_arm_vm_replay:
    .inst original_arm_vm_word
    b original_arm_vm_resume
.global probe_pmap
probe_pmap:
    PROBE_SAVE
    BAND_ONCE 5, 480, 0xff00ff80
    PROBE_RESTORE
.global probe_pmap_replay
probe_pmap_replay:
    .inst original_pmap_word
    b original_pmap_resume
// DENSE_BOOTSTRAP_STUBS

.global probe_kernel_bootstrap
probe_kernel_bootstrap:
    PROBE_SAVE
    BAND_ONCE 6, 512, 0xffff8040
    PROBE_RESTORE
.global probe_kernel_bootstrap_replay
probe_kernel_bootstrap_replay:
    .inst original_kernel_bootstrap_word
    b original_kernel_bootstrap_resume
.global probe_avm_bases
probe_avm_bases:
    PROBE_SAVE
    BAND_ONCE 7, 544, 0xff008080
    PROBE_RESTORE
.global probe_avm_bases_replay
probe_avm_bases_replay:
    .inst original_avm_bases_word
    b original_avm_bases_resume
.global probe_avm_memcheck
probe_avm_memcheck:
    PROBE_SAVE
    BAND_ONCE 8, 576, 0xff808000
    PROBE_RESTORE
.global probe_avm_memcheck_replay
probe_avm_memcheck_replay:
    cbnz x0, .Lavm_memcheck_fallthrough
    b original_avm_memcheck_target
.Lavm_memcheck_fallthrough:
    b original_avm_memcheck_resume
.global probe_avm_physmap
probe_avm_physmap:
    PROBE_SAVE
    BAND_ONCE 9, 608, 0xff8080c0
    PROBE_RESTORE
.global probe_avm_physmap_replay
probe_avm_physmap_replay:
    .inst original_avm_physmap_word
    b original_avm_physmap_resume
.global probe_avm_slide
probe_avm_slide:
    PROBE_SAVE
    BAND_ONCE 10, 640, 0xff808080
    PROBE_RESTORE
.global probe_avm_slide_replay
probe_avm_slide_replay:
    .inst original_avm_slide_word
    b original_avm_slide_resume
.global probe_early_random
probe_early_random:
    PROBE_SAVE
    COUNT16 11, 784
    PROBE_RESTORE
.global probe_early_random_replay
probe_early_random_replay:
    .inst original_early_random_word
    b original_early_random_resume
.global probe_dt_lookup
probe_dt_lookup:
    PROBE_SAVE
    BAND_ONCE 12, 672, 0xff9400d3
    PROBE_RESTORE
.global probe_dt_lookup_replay
probe_dt_lookup_replay:
    .inst original_dt_lookup_word
    b original_dt_lookup_resume
.global probe_soc_base
probe_soc_base:
    PROBE_SAVE
    BAND_ONCE 13, 704, 0xff00c0c0
    // v20: decide the timebase question on hardware, not by inference.
    // This hook runs at the entry of pe_arm_get_soc_base_phys(), which is the
    // exact guard in pe_identify_machine():
    //     if (pe_arm_get_soc_base_phys() == 0) return;
    // At this point SecureDTInit() has already run (PE_init_platform() calls it
    // before pe_identify_machine()), so DTInitialized and DTRootNode hold their
    // final values, while gPESoCBasePhys is still zero: it is assigned inside
    // this very function. Reading both separates "the DT was never found" from
    // "the DT was found but ranges[1] was zero".
    //   row 1344: DTInitialized (0 = the tree was never initialised)
    //   row 1376: DTRootNode (the pointer the kernel actually holds)
    //   row 1408: gPESoCBasePhys (still zero at function entry)
    //   row 1440: PE_state_raw_90 (what SecureDTInit was given)
    //   row 1472: PE_state.bootArgs (the tree length the kernel took)
    stp         x19, x20, [sp, #-80]!
    stp         x21, x22, [sp, #16]
    stp         x23, x24, [sp, #32]
    stp         x25, x26, [sp, #48]
    stp         x27, x28, [sp, #64]
    LOADABS     x23, g_dt_initialized
    ldr         w23, [x23]
    HEXROW_VAL  1344
    LOADABS     x23, g_dt_root_node
    ldr         x23, [x23]
    HEXROW_VAL  1376
    LOADABS     x23, g_soc_base_phys
    ldr         x23, [x23]
    HEXROW_VAL  1408
    LOADABS     x23, g_pe_state
    ldr         x23, [x23, #0x90]              // PE_state_raw_90
    HEXROW_VAL  1440
    LOADABS     x23, g_pe_state
    ldr         x23, [x23, #0xa0]              // PE_state.bootArgs
    HEXROW_VAL  1472
    ldp         x27, x28, [sp, #64]
    ldp         x25, x26, [sp, #48]
    ldp         x23, x24, [sp, #32]
    ldp         x21, x22, [sp, #16]
    ldp         x19, x20, [sp], #80
    PROBE_RESTORE
.global probe_soc_base_replay
probe_soc_base_replay:
    .inst original_soc_base_word
    b original_soc_base_resume
.global probe_timer_regs
probe_timer_regs:
    PROBE_SAVE
       BAND_ONCE 14, 736, 0xffff80c0
    PROBE_RESTORE
.global probe_timer_regs_replay
probe_timer_regs_replay:
       .inst original_timer_regs_word
    b original_timer_regs_resume
.global probe_wfe_timeout
probe_wfe_timeout:
    PROBE_SAVE
       BAND_ONCE 15, 768, 0xff9400d3
    // v20: read the clock values the panic is computed from.
    // wfe_timeout_configure() runs after pe_identify_machine(), so
    // gPEClockFrequencyInfo already holds the final values here.
    //   row 1504: gPEClockFrequencyInfo.timebase_frequency_hz (offset 0x48)
    //   row 1536: arm64_eventi before configuration (initial value, not the rejected index)
    // A zero timebase means pe_identify_machine() returned early, which is
    // only possible when pe_arm_get_soc_base_phys() returned zero.
    stp         x19, x20, [sp, #-80]!
    stp         x21, x22, [sp, #16]
    stp         x23, x24, [sp, #32]
    stp         x25, x26, [sp, #48]
    stp         x27, x28, [sp, #64]
    LOADABS     x23, g_pe_clock_freq_info
    ldr         x23, [x23, #0x48]               // timebase_frequency_hz
    HEXROW_VAL  1504
    LOADABS     x23, g_arm64_eventi
    ldr         w23, [x23]
    HEXROW_VAL  1536
    ldp         x27, x28, [sp, #64]
    ldp         x25, x26, [sp, #48]
    ldp         x23, x24, [sp, #32]
    ldp         x21, x22, [sp, #16]
    ldp         x19, x20, [sp], #80
    PROBE_RESTORE
.global probe_wfe_timeout_replay
probe_wfe_timeout_replay:
       .inst original_wfe_timeout_word
    b original_wfe_timeout_resume
.global probe_wfe_init
probe_wfe_init:
    PROBE_SAVE
       BAND_ONCE 16, 800, 0xff00c0c0
    LOADABS x23, g_arm64_eventi
    ldr w23, [x23]
    HEXROW_VAL 1600
    LOADABS x23, g_arm64_eventi
    HEXROW_VAL 1632
    PROBE_RESTORE
.global probe_wfe_init_replay
probe_wfe_init_replay:
       adrp x8, original_wfe_init_page
    b original_wfe_init_resume
.global probe_misc_boot_args
probe_misc_boot_args:
    PROBE_SAVE
       BAND_ONCE 17, 832, 0xff80c000
    PROBE_RESTORE
.global probe_misc_boot_args_replay
probe_misc_boot_args_replay:
       .inst original_misc_boot_args_word
    b original_misc_boot_args_resume
.global probe_misc_regs
probe_misc_regs:
    PROBE_SAVE
       BAND_ONCE 18, 864, 0xffffc000
    PROBE_RESTORE
.global probe_misc_regs_replay
probe_misc_regs_replay:
       .inst original_misc_regs_word
    b original_misc_regs_resume
.global probe_cpu_topo
probe_cpu_topo:
    PROBE_SAVE
    BAND_ONCE 19, 896, 0xff80c000
    PROBE_RESTORE
.global probe_cpu_topo_replay
probe_cpu_topo_replay:
    .inst original_cpu_topo_word
    b original_cpu_topo_resume
.global probe_cpu_bootstrap
probe_cpu_bootstrap:
    PROBE_SAVE
    BAND_ONCE 20, 928, 0xffffc000
    PROBE_RESTORE
.global probe_cpu_bootstrap_replay
probe_cpu_bootstrap_replay:
    .inst original_cpu_bootstrap_word
    b original_cpu_bootstrap_resume
.global probe_machine_startup
probe_machine_startup:
    PROBE_SAVE
    BAND_ONCE 21, 960, 0xffc000ff
    PROBE_RESTORE
.global probe_machine_startup_replay
probe_machine_startup_replay:
    .inst original_machine_startup_word
    b original_machine_startup_resume
.global probe_panic
probe_panic:
    PROBE_SAVE
    BAND_ONCE 22, 992, 0xffff1493
    PROBE_RESTORE
.global probe_panic_replay
probe_panic_replay:
    .inst original_panic_word
    b original_panic_resume
.global probe_panic_options
probe_panic_options:
    PROBE_SAVE
    BAND_ONCE 23, 1024, 0xffc000c0
    PROBE_RESTORE
.global probe_panic_options_replay
probe_panic_options_replay:
    .inst original_panic_options_word
    b original_panic_options_resume
.global probe_panic_trap
probe_panic_trap:
    PROBE_SAVE
    BAND_ONCE 24, 1040, 0xff9400ff
    // HEXROW_VAL uses x21..x28, which are callee-saved; this hook runs at a
    // function entry, so save and restore them around the rendering.
    stp         x19, x20, [sp, #-80]!
    stp         x21, x22, [sp, #16]
    stp         x23, x24, [sp, #32]
    stp         x25, x26, [sp, #48]
    stp         x27, x28, [sp, #64]
    // x1 is the va_list: on Darwin it points at a struct whose first word is the
    // stack slot of the first variadic argument, which for panic("%s: invalid
    // ...", __func__, ...) is the name of the function that panicked.
    // x1 is the va_list pointer: its first word is the stack slot of the first
    // variadic argument. For panic("%s: invalid ...", __func__, ...) that is the
    // name of the function that panicked - but other panics pass a number there,
    // so only dereference it when it really looks like a page aligned kernel
    // pointer, otherwise fall back to the format string alone.
    // The first variadic argument is checked as a pointer: for
    // panic("%s: invalid bit index (%u)", __FUNCTION__, bit_index) it is the
    // function name, a kernel text address. The earlier page-alignment test
    // was wrong - a string literal in __TEXT is not page aligned, so the two
    // argument rows stayed empty on hardware. What is actually required is
    // that the value looks like a kernel pointer: in the KVA range and
    // within the bounded kernel text segment. An integer argument fails
    // both tests and the format string alone is rendered instead.
    ldr         x11, [x1]
    cbz         x11, .Lpanic_no_argument
    ldr x23, [x11]
    HEXROW_VAL 1568
    ldr x23, [x11, #8]
    HEXROW_VAL 1664
    ldr         x12, [x11]
    movz        x13, #0
    movk        x13, #0xffff, lsl #48
    cmp         x12, x13
    b.lo        .Lpanic_no_argument
    LOADABS x13, g_text_min
    cmp x12, x13
    b.lo .Lpanic_no_argument
    LOADABS x13, g_text_end_minus_16
    cmp x12, x13
    b.hi .Lpanic_no_argument
    // The argument is a pointer to the function name: read its first eight
    // bytes and render them as text, then the next eight.
    // x11 holds the variadic slot and x12 the pointer, but HEXROW_VAL uses
    // x12 internally, so x12 is reloaded from x11 before every use. x11 is
    // not touched by the renderer.
    ldr         x23, [x12]
    rev         x23, x23
    HEXROW_VAL 1088
    ldr         x12, [x11]
    ldr         x23, [x12, #8]
    rev         x23, x23
    HEXROW_VAL 1248
    // The argument pointer itself, so a zero or a non-text address is visible.
    // It is a value, not a loaded word, so it is not byte reversed.
    ldr         x12, [x11]
    mov         x23, x12
    HEXROW_VAL 1568
.Lpanic_no_argument:
    ldr         x23, [x0]
    rev         x23, x23
    HEXROW_VAL 1280
    ldr         x23, [x0, #8]
    rev         x23, x23
    HEXROW_VAL 1312
    ldp         x27, x28, [sp, #64]
    ldp         x25, x26, [sp, #48]
    ldp         x23, x24, [sp, #32]
    ldp         x21, x22, [sp, #16]
    ldp         x19, x20, [sp], #80
    PROBE_RESTORE
.global probe_panic_trap_replay
probe_panic_trap_replay:
    .inst original_panic_trap_word
    b original_panic_trap_resume

// v23 diagnostic lowering of the upstream DT-panic policy for the no-pram
// case only. The native binary constant-folded panic_text_len to one byte;
// a real DT region requires rebuilding source, not assigning a dynamic size.
.global probe_console_policy
probe_console_policy:
    PROBE_SAVE
    sub sp, sp, #96
    stp x0, x1, [sp]
    stp x2, x3, [sp, #16]
    stp x4, x5, [sp, #32]
    stp x6, x7, [sp, #48]
    stp x8, x30, [sp, #64]
    mov x0, #0
    adr x1, .Lpram_name
    add x2, sp, #80
    bl native_dt_lookup
    cmp w0, #1
    b.eq .Lconsole_region_present
    // Source check_for_panic_log returns without importing any old log.
    mov x9, #1
    adr x10, probe_console_status
    str x9, [x10]
    ldp x0, x1, [sp]
    ldp x2, x3, [sp, #16]
    ldp x4, x5, [sp, #32]
    ldp x6, x7, [sp, #48]
    ldp x8, x30, [sp, #64]
    add sp, sp, #96
    // Render only after restoring native arguments and the hook save frame.
    BAND_ONCE 26, 768, 0xff80ffff
    PROBE_RESTORE
    // Native tail uses w20=1 to select graphics/text mode; native prologue
    // already saved incoming x20. Do not bypass PE_initialize_console.
    mov w20, #1
    b native_console_tail
.Lconsole_region_present:
    adr x9, probe_console_status
    mov x10, #2
    str x10, [x9]
    // Explicit unsupported-policy stop; never access BCM panic memory.
    BAND_SNAPSHOT 1120, 0xffff0000
    mov x23, #2
    HEXROW_VAL 1696
.global probe_console_policy_stop
probe_console_policy_stop:
    b probe_console_policy_stop
.Lpram_name:
    .asciz "pram"
.balign 4
// Marker remains a separate transparent entry hook after the policy's tail.
.global probe_console_init
probe_console_init:
    PROBE_SAVE
    BAND_ONCE 27, 800, 0xffc08040
    PROBE_RESTORE
.global probe_console_init_replay
probe_console_init_replay:
    .inst original_console_init_word
    b original_console_init_resume

// v22: diagnostic mapping transition. No allocations or replacement of live
// descriptors. x0 is the new physical root; old V=P still maps these tables.
.global probe_ttbr1
probe_ttbr1:
    PROBE_SAVE
    adr x19, probe_vectors
    adr x20, probe_end
    LOADABS x9, g_phys_base
    ldr x21, [x9]
    LOADABS x9, g_virt_base
    ldr x22, [x9]
    sub x21, x21, x22
    // Validate every leaf first: no partial changes on occupied/bad topology.
    mov x23, x19
.Lvalidate_probe:
    ubfx x9, x23, #30, #8
    ldr x10, [x0, x9, lsl #3]
    and x11, x10, #3
    cmp x11, #3
    b.ne .Lmap_abort
    and x10, x10, #0x0000fffffffff000
    ubfx x9, x23, #21, #9
    ldr x10, [x10, x9, lsl #3]
    and x11, x10, #3
    cmp x11, #3
    b.ne .Lmap_abort
    and x10, x10, #0x0000fffffffff000
    ubfx x9, x23, #12, #9
    ldr x11, [x10, x9, lsl #3]
    cbnz x11, .Lmap_abort
    add x23, x23, #4096
    cmp x23, x20
    b.lo .Lvalidate_probe
    mov x23, x19
.Linstall_probe:
    ubfx x9, x23, #30, #8
    ldr x10, [x0, x9, lsl #3]
    and x10, x10, #0x0000fffffffff000
    ubfx x9, x23, #21, #9
    ldr x10, [x10, x9, lsl #3]
    and x10, x10, #0x0000fffffffff000
    ubfx x9, x23, #12, #9
    add x11, x23, x21
    adr x12, probe_data
    cmp x23, x12
    b.hs .Lprobe_rw
    // Normal WB idx0, AF, inner-shareable, EL1 RO executable, EL0 XN.
    mov x12, #0x783
    movk x12, #0x0040, lsl #48
    b .Lprobe_attr
.Lprobe_rw:
    // Mutable snapshot/flags/per-CPU page: privileged RW, PXN and UXN.
    mov x12, #0x703
    movk x12, #0x0060, lsl #48
.Lprobe_attr:
    orr x11, x11, x12
    str x11, [x10, x9, lsl #3]
    add x23, x23, #4096
    cmp x23, x20
    b.lo .Linstall_probe
    dsb ishst
    // Use KVA vectors: both old and new TTBR1 now map this code.
    msr vbar_el1, x19
    isb
    adr x9, probe_map_status
    mov x10, #1
    str x10, [x9]
    b .Lmap_exit
.Lmap_abort:
    adr x9, probe_map_status
    mov x10, #2
    str x10, [x9]
.Lmap_exit:
    PROBE_RESTORE
.global probe_ttbr1_replay
probe_ttbr1_replay:
    adrp x30, original_ttbr1_resume
    add x30, x30, :lo12:original_ttbr1_resume
    b original_ttbr1_entry

.global probe_ttbr0
probe_ttbr0:
    PROBE_SAVE
    adr x9, probe_map_status
    ldr x10, [x9]
    cmp x10, #1
    b.ne .Lfb_exit
    ldr x10, [x0, #16]
    cbnz x10, .Lfb_occupied
    mov x10, #0x040d
    movk x10, #0x8000, lsl #16
    movk x10, #0x0060, lsl #48
    str x10, [x0, #16]
    dsb ishst
    mov x10, #1
    str x10, [x9, #8]
    b .Lfb_exit
.Lfb_occupied:
    // Keep slot intact and disable rendering; code remains reachable.
    adr x11, probe_scratch
    str xzr, [x11]
    mov x10, #2
    str x10, [x9, #8]
.Lfb_exit:
    PROBE_RESTORE
.global probe_ttbr0_replay
probe_ttbr0_replay:
    adrp x30, original_ttbr0_resume
    add x30, x30, :lo12:original_ttbr0_resume
    b original_ttbr0_entry

// Early exception output for the kernel's own physical vectors: red band, then
// ESR/ELR/FAR in 16 hex digits each, read from boot_args through x20. This path
// is only live before the probe page takes over VBAR.
.macro HEXROW reg, y
    mrs x23, \reg
    ldr x21, [x20, #0x28]
    ldr x22, [x20, #0x38]
    HEX_RENDER \y
.endm
.global probe_fault
probe_fault:
    ldr x9, [x20, #0x28]
    cbz x9, fault_stop
    ldr x10, [x20, #0x48]
    cmp x10, #800
    b.lo fault_stop
    ldr x10, [x20, #0x38]
    cmp x10, #2944
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
.global probe_data
probe_data:
.global probe_scratch
probe_scratch:
    .quad 0, 0
.global probe_map_status
probe_map_status:
    .quad 0, 0
.global probe_console_status
probe_console_status:
    .quad 0
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

.global probe_end
probe_end:
