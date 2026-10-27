"""Revision39: visible initialization checkpoints, retaining all body observations."""
import read_body_sites as PREVIOUS

MIN_HEIGHT = 1040
CHECKPOINTS = {
    'F901': 'before A037 reset; entry tile already cleared',
    'F902': 'A037 reset completed; before A036 reset',
    'F903': 'A036 reset completed; before body state and tile reset',
    'F904': 'body state and tiles reset; before A038/A039 reset',
}


def checkpoint(value):
    return f'    mov x23, #{value}\n    HEXROW_VAL 1664\n    dsb sy\n'


def observe(site):
    source = PREVIOUS.observe(site)
    if site != PREVIOUS.PREVIOUS.PREVIOUS.FIRST:
        return source
    fields = '    mov x23, #0\n    HEXROW_VAL 1728\n    mov x23, #0\n    HEXROW_VAL 1760\n'
    assert source.count(fields) == 1
    source = source.replace(fields,
        checkpoint(0xf901) + '    mov x23, #0\n    HEXROW_VAL 1760\n    dsb sy\n' +
        checkpoint(0xf902) + '    mov x23, #0\n    HEXROW_VAL 1728\n    dsb sy\n' +
        checkpoint(0xf903))
    tail = '    mov x23, #0\n    HEXROW_VAL 1792\n    mov x23, #-1\n    HEXROW_VAL 1824\n'
    assert source.endswith(tail)
    return source[:-len(tail)] + checkpoint(0xf904) + tail + '    dsb sy\n' + checkpoint(250)
