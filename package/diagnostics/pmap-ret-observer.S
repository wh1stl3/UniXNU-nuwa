/* Single normal-RET observer. No caller continuation and no SP adjustment.
 * Final-layout binding must replace ONLY the exported slot with B renderer.
 * Until then B . fails closed on this path; it cannot print or resume boot.
 */
.section __TEXT,__text,regular,pure_instructions
.p2align 2
.globl _nuwa_pmap_ret_observer
_nuwa_pmap_ret_observer:
    adrp x0, _nuwa_pmap_ret_observer_message@PAGE
    add x0, x0, _nuwa_pmap_ret_observer_message@PAGEOFF
.globl _nuwa_pmap_ret_observer_renderer_branch
_nuwa_pmap_ret_observer_renderer_branch:
L_unbound_renderer:
    b L_unbound_renderer

.section __TEXT,__cstring,cstring_literals
.globl _nuwa_pmap_ret_observer_message
_nuwa_pmap_ret_observer_message:
    .asciz "DIAG: PMAP initializer normal epilogue reached; STOP"
