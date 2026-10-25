// Model-tested compatibility candidate for the pinned AppleImage4 5.0.0.
// Not included in a boot package. The installer must pin the displaced ADRP.
// Entry is 0xfffffff0046ea000, after the original reader's saved-register frame.
// Never invent an AMNM value: use the original Darwin IOKit reader for this
// identifier when the selected dtless instance cannot represent it. All native
// lookup/type/length/conversion failures remain failures.
.text
.p2align 2
.global image4_amnm_provider
image4_amnm_provider:
    ldr x8, =0xfffffff005cacea8
    ldr x0, [x8]
    cbz x0, original_secure_dt
    cmp x20, #12
    b.eq direct_amnm
    ldr x8, =0xfffffff0046ea00c
    br x8
original_secure_dt:
    ldr x8, =0xfffffff0046ea034
    br x8
direct_amnm:
    mov x2, x20
    mov x3, x19
    ldr x8, =0xfffffff0046efe7c
    blr x8
    ldr x8, =0xfffffff0046ea138
    br x8
.ltorg
