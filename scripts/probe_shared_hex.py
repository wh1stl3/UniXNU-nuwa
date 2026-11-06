"""Revision43: one unchanged-pixel HEX renderer; avoid unchanged A035 redraws.

Only the result field is cached, reset before every header attempt. Display
stores stay 32-bit pairs; no new MMIO width, native policy or IRQ behavior.
"""
import hashlib
from pathlib import Path
import read_decmp_sites as PREVIOUS


def plan():
    return dict(source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                cached_logical_row=1696,cache_bytes=16,reset='before every header attempt',
                native_policy_changed=False,pixel_store_width_changed=False,
                all_previous_observations_retained=True,shared_call_stack_bytes=16,
                stackless_exception_renderer=True)


def observe(site):
    source=PREVIOUS.observe(site)
    if site==PREVIOUS.PREVIOUS.FIRST:
        source='    adr x12, probe_hex_result_cache\n    str xzr, [x12, #8]\n'+source
    return source


def transform(template):
    start=template.index('.macro HEXROW_VAL y');end=template.index('.endm',start)+len('.endm')
    stackless=template[start:end].replace('.macro HEXROW_VAL y','.macro HEXROW_STACKLESS y')
    template=template[:start]+r'''.macro HEXROW_VAL y
    adr x15, probe_scratch
    ldr x21, [x15]
    ldr x22, [x15, #8]
    cbz x21, .Lshared_no_video\@
    stp x20, x30, [sp, #-16]!
    mov x24, #\y
    bl probe_hex_shared
    ldp x20, x30, [sp], #16
.Lshared_no_video\@:
.endm'''+ '\n'+stackless+template[end:]
    snap_start=template.index('.macro HEXROW_SNAP');snap_end=template.index('.endm',snap_start)
    snap=template[snap_start:snap_end].replace('HEXROW_VAL','HEXROW_STACKLESS')
    template=template[:snap_start]+snap+template[snap_end:]
    helper='''
.global probe_hex_shared
probe_hex_shared:
    mov x19, x23
    mov x20, x24
    cmp x20, #1696
    b.ne .Lshared_draw
    adr x12, probe_hex_result_cache
    ldr x13, [x12, #8]
    cbz x13, .Lshared_draw
    ldr x13, [x12]
    cmp x13, x19
    b.eq .Lshared_return
.Lshared_draw:
    cmp x20, #1088
    b.lo .Lshared_counter
    sub x25, x20, #1088
    lsr x25, x25, #5
    mov x26, #28
    mul x25, x25, x26
    add x25, x25, #224
    b .Lshared_position
.Lshared_counter:
    mov x25, #756
.Lshared_position:
    madd x21, x22, x25, x21
    add x21, x21, #1024
    lsr x25, x20, #5
    mov x23, #0xa000
    add x23, x23, x25
    mov x24, #12
    HEX_DIGITS
    mov x23, x19
    mov x24, #60
    HEX_DIGITS
    cmp x20, #1696
    b.ne .Lshared_return
    adr x12, probe_hex_result_cache
    str x19, [x12]
    mov x13, #1
    str x13, [x12, #8]
.Lshared_return:
    ret
.global probe_hex_shared_end
probe_hex_shared_end:
'''
    marker='.balign 4096\n.global probe_data'
    assert template.count(marker)==1
    template=template.replace(marker,helper+marker)
    marker='.balign 4096\n.global probe_zero'
    assert template.count(marker)==1
    return template.replace(marker,'.global probe_hex_result_cache\nprobe_hex_result_cache:\n    .quad 0,0\n'+marker)
