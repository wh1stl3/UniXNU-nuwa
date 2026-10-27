"""Revision40: write each HEX rectangle pixel once, preserving the final image.

Only generated diagnostic macros change. Native code, board values and the
historical renderer template remain untouched.
"""
from pathlib import Path
import hashlib


def plan():
    return dict(source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                rectangle=[480, 20], previous_bytes_per_field=64000,
                bytes_per_field=38400, native_policy_changed=False)


def transform(template):
    start = template.index('    // Clear the entire 480x20 data rectangle')
    end = template.index('    mov x23, #(0xa000', start)
    template = template[:start] + template[end:]
    old = '    add         x28, x28, #1\n    cmp         x28, #5'
    assert template.count(old) == 1
    # Four glyph columns already fill 16 pixels. Clear only the remaining eight
    # spacing pixels, for each of the four physical rows of this glyph bit row.
    gap = r'''    lsl         x14, x28, #2
    madd        x13, x14, x22, x21
    add         x13, x13, #64
    mov         x12, #4
.Ldigits_gap_row\@:
    stp         wzr, wzr, [x13]
    stp         wzr, wzr, [x13, #8]
    stp         wzr, wzr, [x13, #16]
    stp         wzr, wzr, [x13, #24]
    add         x13, x13, x22
    subs        x12, x12, #1
    b.ne        .Ldigits_gap_row\@
'''
    return template.replace(old, gap + old)
