"""Revision48: retain full-size HEX pixels; redraw only changed value glyphs.

Software display-value records only: no CPU cache, MMU, IRQ or store-width change.
"""
import hashlib
from pathlib import Path

def plan():
    return dict(source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                first_logical_row=1088,last_logical_row=1984,slots=29,state_bytes=464,
                first_field_bytes=38400,changed_digit_bytes=1920,
                ordinary_call_stack_bytes=32,exception_stackless=True,
                full_result_redraw_after_header_reset=True,
                native_policy_changed=False,pixel_store_width_changed=False,
                cache_pointer_register="x0",reserved_x18_live_state=False,
                scope='Ordinary shared HEX only; first use full image, subsequent changed nibbles; valid committed after drawing')

def transform(template):
    start=template.index('probe_hex_shared:\n')+len('probe_hex_shared:\n')
    end=template.index('.global probe_hex_shared_end',start)
    legacy=template[start:end]
    body=r'''    cmp x24, #1088
    b.lo .Ldelta_legacy
    cmp x24, #1984
    b.hi .Ldelta_legacy
    tst x24, #31
    b.ne .Ldelta_legacy
    stp x0, x30, [sp, #-16]!
    mov x19, x23
    mov x20, x24
    sub x9, x20, #1088
    lsr x9, x9, #5
    adr x0, probe_hex_delta_cache
    add x0, x0, x9, lsl #4
    cmp x20, #1696
    b.ne .Ldelta_position
    adr x10, probe_hex_result_cache
    ldr x11, [x10, #8]
    cbnz x11, .Ldelta_position
    str xzr, [x0, #8]
.Ldelta_position:
    mov x26, #28
    mul x25, x9, x26
    add x25, x25, #224
    madd x21, x22, x25, x21
    add x21, x21, #1024
    ldr x10, [x0, #8]
    cmp x10, #1
    b.eq .Ldelta_skip_tag
    lsr x23, x20, #5
    add x23, x23, #0xa000
    mov x24, #12
    HEX_DIGITS
    b .Ldelta_values
.Ldelta_skip_tag:
    add x21, x21, #384
.Ldelta_values:
    mov x20, #60
.Ldelta_digit:
    ldr x10, [x0, #8]
    cmp x10, #1
    b.ne .Ldelta_draw_digit
    ldr x9, [x0]
    eor x9, x9, x19
    lsr x9, x9, x20
    tst x9, #15
    b.eq .Ldelta_skip_digit
.Ldelta_draw_digit:
    lsr x23, x19, x20
    mov x24, #0
    HEX_DIGITS
    b .Ldelta_next
.Ldelta_skip_digit:
    add x21, x21, #96
.Ldelta_next:
    subs x20, x20, #4
    b.ge .Ldelta_digit
    str x19, [x0]
    mov x10, #1
    str x10, [x0, #8]
    adr x9, probe_hex_delta_cache
    add x9, x9, #304
    cmp x0, x9
    b.ne .Ldelta_return
    adr x9, probe_hex_result_cache
    stp x19, x10, [x9]
.Ldelta_return:
    ldp x0, x30, [sp], #16
    ret
.Ldelta_legacy:
'''
    template=template[:start]+body+legacy+template[end:]
    marker='.balign 4096\n.global probe_zero'
    assert template.count(marker)==1
    return template.replace(marker,'.global probe_hex_delta_cache\nprobe_hex_delta_cache:\n    .zero 464\n'+marker)
