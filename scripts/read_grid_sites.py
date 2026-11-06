"""Revision41: retain every body tile, defer expensive HEX until native RET.

Last native site and paired raw x0 are always buffered, including no-video.
No native instruction, error, call or scheduling policy is changed.
"""
from pathlib import Path
import hashlib
import read_init_sites as PREVIOUS
import read_body_sites as BODY

RET = 0xfffffff0051a5978
FIRST = BODY.PREVIOUS.PREVIOUS.FIRST


def plan():
    return dict(source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                state_bytes=16, flush_site=hex(RET), all_body_tiles_retained=True,
                hex_policy='A038/A039 initialized at header; buffered body state displayed only at native RET',
                native_policy_changed=False)


def observe(site):
    source = PREVIOUS.observe(site)
    if site == FIRST:
        return source + '''    adr x14, probe_read_trace_state
    str xzr, [x14]
    mov x15, #-1
    str x15, [x14, #8]
'''
    if not any(p['site'] == site for p in BODY.points()):
        return source
    source = source.replace('    mov x23, x0\n    HEXROW_VAL 1824\n',
                            '    adr x14, probe_read_trace_state\n    str x0, [x14, #8]\n')
    old = f'    LOADABS x23, {site:#x}\n    HEXROW_VAL 1792\n'
    assert old in source
    source = source.replace(old, f'    LOADABS x23, {site:#x}\n    adr x14, probe_read_trace_state\n    str x23, [x14]\n')
    if site == RET:
        done = f'.Lbody_done_{site:x}:\n'
        assert source.endswith(done)
        source = source[:-len(done)] + '''    adr x14, probe_read_trace_state
    ldr x23, [x14]
    HEXROW_VAL 1792
    adr x14, probe_read_trace_state
    ldr x23, [x14, #8]
    HEXROW_VAL 1824
''' + done
    return source
