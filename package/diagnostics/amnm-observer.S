/* Bind _amnm_observer_log and _amnm_input_continue only in a checked link.
 * Patch the original CMP with B _amnm_input_hook. The continuation must be
 * the instruction immediately after that CMP. All addresses are relocatable.
 */
.text
.p2align 2
.globl _amnm_input_hook
_amnm_input_hook:
    sub sp, sp, #272
    stp x0, x1, [sp, #0]
    stp x2, x3, [sp, #16]
    stp x4, x5, [sp, #32]
    stp x6, x7, [sp, #48]
    stp x8, x9, [sp, #64]
    stp x10, x11, [sp, #80]
    stp x12, x13, [sp, #96]
    stp x14, x15, [sp, #112]
    stp x16, x17, [sp, #128]
    stp x18, x19, [sp, #144]
    stp x20, x21, [sp, #160]
    stp x22, x23, [sp, #176]
    stp x24, x25, [sp, #192]
    stp x26, x27, [sp, #208]
    stp x28, x29, [sp, #224]
    str x30, [sp, #240]
    mrs x9, nzcv
    str x9, [sp, #248]

    adrp x9, _amnm_observer_log@PAGE
    add x9, x9, _amnm_observer_log@PAGEOFF
    mov x10, #1
    ldaddal x10, x11, [x9]
    cmp x11, #16
    b.hs 1f
    mov x12, #96
    madd x12, x11, x12, x9
    add x12, x12, #128
    mov x13, #3
    str x13, [x12, #8]
    uxtw x13, w8
    str x13, [x12, #16]
    str x21, [x12, #24]
    str x19, [x12, #32]
    add x13, sp, #272
    str x13, [x12, #40]
    str x29, [x12, #48]
    ldp x14, x15, [x13, #48]
    stp x14, x15, [x12, #56]
    add x11, x11, #1
    stlr x11, [x12]
1:
    ldr x9, [sp, #248]
    msr nzcv, x9
    ldp x0, x1, [sp, #0]
    ldp x2, x3, [sp, #16]
    ldp x4, x5, [sp, #32]
    ldp x6, x7, [sp, #48]
    ldp x8, x9, [sp, #64]
    ldp x10, x11, [sp, #80]
    ldp x12, x13, [sp, #96]
    ldp x14, x15, [sp, #112]
    ldp x16, x17, [sp, #128]
    ldp x18, x19, [sp, #144]
    ldp x20, x21, [sp, #160]
    ldp x22, x23, [sp, #176]
    ldp x24, x25, [sp, #192]
    ldp x26, x27, [sp, #208]
    ldp x28, x29, [sp, #224]
    ldr x30, [sp, #240]
    add sp, sp, #272
    cmp w8, #0
    b _amnm_input_continue

/* Separate entry points; the original INPUT body above remains unchanged. */
.macro SAVE_CONTEXT
    sub sp, sp, #272
    stp x0, x1, [sp, #0]
    stp x2, x3, [sp, #16]
    stp x4, x5, [sp, #32]
    stp x6, x7, [sp, #48]
    stp x8, x9, [sp, #64]
    stp x10, x11, [sp, #80]
    stp x12, x13, [sp, #96]
    stp x14, x15, [sp, #112]
    stp x16, x17, [sp, #128]
    stp x18, x19, [sp, #144]
    stp x20, x21, [sp, #160]
    stp x22, x23, [sp, #176]
    stp x24, x25, [sp, #192]
    stp x26, x27, [sp, #208]
    stp x28, x29, [sp, #224]
    str x30, [sp, #240]
    mrs x9, nzcv
    str x9, [sp, #248]
.endmacro

.macro RESTORE_CONTEXT
    ldr x9, [sp, #248]
    msr nzcv, x9
    ldp x0, x1, [sp, #0]
    ldp x2, x3, [sp, #16]
    ldp x4, x5, [sp, #32]
    ldp x6, x7, [sp, #48]
    ldp x8, x9, [sp, #64]
    ldp x10, x11, [sp, #80]
    ldp x12, x13, [sp, #96]
    ldp x14, x15, [sp, #112]
    ldp x16, x17, [sp, #128]
    ldp x18, x19, [sp, #144]
    ldp x20, x21, [sp, #160]
    ldp x22, x23, [sp, #176]
    ldp x24, x25, [sp, #192]
    ldp x26, x27, [sp, #208]
    ldp x28, x29, [sp, #224]
    ldr x30, [sp, #240]
    add sp, sp, #272
.endmacro

.macro RESERVE_TICKET
    adrp x9, _amnm_observer_log@PAGE
    add x9, x9, _amnm_observer_log@PAGEOFF
    mov x10, #1
    ldaddal x10, x11, [x9]
.endmacro

.macro SLOT_ADDRESS
    mov x12, #96
    madd x12, x11, x12, x9
    add x12, x12, #128
.endmacro

.p2align 2
.globl _amnm_store_hook
_amnm_store_hook:
    SAVE_CONTEXT
    RESERVE_TICKET
    /* Execute the original exactly once, even when the log overflows. */
    strb w8, [x19]
    cmp x11, #16
    b.hs 2f
    SLOT_ADDRESS
    mov x13, #4
    str x13, [x12, #8]
    and x13, x8, #255
    str x13, [x12, #16]
    str x19, [x12, #24]
    str x21, [x12, #32]
    add x13, sp, #272
    str x13, [x12, #40]
    str x29, [x12, #48]
    ldp x14, x15, [x13, #48]
    stp x14, x15, [x12, #56]
    add x11, x11, #1
    stlr x11, [x12]
2:
    RESTORE_CONTEXT
    b _amnm_store_continue

.p2align 2
.globl _amnm_branch_hook
_amnm_branch_hook:
    SAVE_CONTEXT
    RESERVE_TICKET
    cmp x11, #16
    b.hs 3f
    SLOT_ADDRESS
    mov x13, #5
    str x13, [x12, #8]
    uxtw x13, w8
    str x13, [x12, #16]
    add x13, sp, #272
    str x13, [x12, #24]
    str x29, [x12, #32]
    add x11, x11, #1
    stlr x11, [x12]
3:
    RESTORE_CONTEXT
    cbz w8, 4f
    b _amnm_branch_nonzero
4:
    b _amnm_branch_zero

/* ENTRY patch replaces exactly SUB SP,SP,#0x190; continue at next insn. */
.p2align 2
.globl _amnm_entry_hook
_amnm_entry_hook:
    SAVE_CONTEXT
    RESERVE_TICKET
    cmp x11, #16
    b.hs 5f
    SLOT_ADDRESS
    mov x13, #1
    str x13, [x12, #8]
    add x13, sp, #272
    str x13, [x12, #16]
    str x29, [x12, #24]
    str x30, [x12, #32]
    add x11, x11, #1
    stlr x11, [x12]
5:
    RESTORE_CONTEXT
    sub sp, sp, #0x190
    b _amnm_entry_continue

/* Replace the MOV immediately before BLR, not the BLR. Continue at the
 * original untouched BLR so its LR and architectural branch type are native.
 * _amnm_precall_return is that original BLR site + 4. */
.p2align 2
.globl _amnm_precall_hook
_amnm_precall_hook:
    SAVE_CONTEXT
    RESERVE_TICKET
    cmp x11, #16
    b.hs 6f
    SLOT_ADDRESS
    mov x13, #2
    str x13, [x12, #8]
    str x8, [x12, #16]
    str x0, [x12, #24]
    str x2, [x12, #32]
    str x3, [x12, #40]
    add x13, sp, #272
    str x13, [x12, #48]
    str x29, [x12, #56]
    adrp x13, _amnm_precall_return@PAGE
    add x13, x13, _amnm_precall_return@PAGEOFF
    str x13, [x12, #64]
    add x11, x11, #1
    stlr x11, [x12]
6:
    RESTORE_CONTEXT
    mov x1, x21
    b _amnm_precall_continue
