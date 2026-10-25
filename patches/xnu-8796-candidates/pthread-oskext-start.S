// Called only inside the saved BSD-entry probe frame, after IOKit/MAC startup.
// Request the genuine OSKext lifecycle; never call the donor kmod entry here.
// Preserve every SIMD register and the original x0-x8, FPCR/FPSR. The caller's
// PROBE_SAVE frame preserves x9-x28/NZCV and its small wrapper saves x29/x30.
.text
.p2align 2
.global pthread_load_before_bsd
pthread_load_before_bsd:
    sub sp, sp, #640
    stp x0, x1, [sp, #0]
    stp x2, x3, [sp, #16]
    stp x4, x5, [sp, #32]
    stp x6, x7, [sp, #48]
    stp x8, x29, [sp, #64]
    str x30, [sp, #80]
    mrs x9, fpcr
    str x9, [sp, #88]
    mrs x9, fpsr
    str x9, [sp, #96]
    stp q0, q1, [sp, #112]
    stp q2, q3, [sp, #144]
    stp q4, q5, [sp, #176]
    stp q6, q7, [sp, #208]
    stp q8, q9, [sp, #240]
    stp q10, q11, [sp, #272]
    stp q12, q13, [sp, #304]
    stp q14, q15, [sp, #336]
    stp q16, q17, [sp, #368]
    stp q18, q19, [sp, #400]
    stp q20, q21, [sp, #432]
    stp q22, q23, [sp, #464]
    stp q24, q25, [sp, #496]
    stp q26, q27, [sp, #528]
    stp q28, q29, [sp, #560]
    stp q30, q31, [sp, #592]
    adr x19, probe_pthread_load_status
    LOADABS x9, native_pthread_functions
    ldr x20, [x9]
    cbnz x20, .Lpthread_already_registered
    DENSE_ONCE 178, 0xff40c0ff
    adr x0, .Lpthread_bundle
    LOADABS x9, native_kext_load
    blr x9
    str x0, [x19]
    mov x9, #1
    str x9, [x19, #16]
    DENSE_ONCE 179, 0xff40ff80
    LOADABS x9, native_pthread_functions
    ldr x20, [x9]
    b .Lpthread_record
.Lpthread_already_registered:
    str xzr, [x19]
    str xzr, [x19, #16]
    DENSE_ONCE 181, 0xffffff00
.Lpthread_record:
    str x20, [x19, #8]
    cbz x20, .Lpthread_restore
    DENSE_ONCE 180, 0xffff40ff
.Lpthread_restore:
    ldp q0, q1, [sp, #112]
    ldp q2, q3, [sp, #144]
    ldp q4, q5, [sp, #176]
    ldp q6, q7, [sp, #208]
    ldp q8, q9, [sp, #240]
    ldp q10, q11, [sp, #272]
    ldp q12, q13, [sp, #304]
    ldp q14, q15, [sp, #336]
    ldp q16, q17, [sp, #368]
    ldp q18, q19, [sp, #400]
    ldp q20, q21, [sp, #432]
    ldp q22, q23, [sp, #464]
    ldp q24, q25, [sp, #496]
    ldp q26, q27, [sp, #528]
    ldp q28, q29, [sp, #560]
    ldp q30, q31, [sp, #592]
    ldr x9, [sp, #88]
    msr fpcr, x9
    ldr x9, [sp, #96]
    msr fpsr, x9
    ldp x0, x1, [sp, #0]
    ldp x2, x3, [sp, #16]
    ldp x4, x5, [sp, #32]
    ldp x6, x7, [sp, #48]
    ldp x8, x29, [sp, #64]
    ldr x30, [sp, #80]
    add sp, sp, #640
    ret
.Lpthread_bundle:
    .asciz "com.apple.kec.pthread"
.p2align 2
