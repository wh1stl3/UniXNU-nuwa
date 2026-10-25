// Pinned Image4 5.0.0 CHMH provider compatibility, after its original frame.
// The dtless chip-instance table has no CHMH entry. Query the original Darwin
// OSData reader; never manufacture a digest or convert a lookup error to success.
.text
.p2align 2
.global image4_chmh_provider
image4_chmh_provider:
    ldr x8, =0xfffffff005cacea8
    ldr x0, [x8]
    cbz x0, chmh_original_secure_dt
    cmp x22, #11
    b.eq direct_chmh
    ldr x8, =0xfffffff0046ea3c0
    br x8
chmh_original_secure_dt:
    ldr x8, =0xfffffff0046ea40c
    br x8
direct_chmh:
    mov x1, x21
    mov x2, x22
    mov x3, x19
    ldr x8, =0xfffffff0046f021c
    blr x8
    ldr x8, =0xfffffff0046ea3d4
    br x8
.ltorg
