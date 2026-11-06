"""Retain native exec errors across fallback attempts without changing native flow."""
import hashlib
from pathlib import Path
import exec_trace_sites as V32
if hashlib.sha256(Path(V32.__file__).read_bytes()).hexdigest()!='dfa3b9e54eb3333184f6c5d13f26eb4d7e40d7a07d3e4236199eecf172ffa5de':
    raise ValueError('Frozen v32 exec observations changed')
add_sites=V32.add_sites

def observe(site):
    source=V32.observe(site)
    if site==V32.FIRST:
        # Keep the last completed error visible when a native fallback starts.
        start=source.index('    mov x23, #-1')
        source=source[:start]+'''    ldr x10, [x9, #80]
    cbnz x10, .Lexec_keep_completed_results
    mov x23, #-1
    HEXROW_VAL 1440
    mov x23, #-1
    HEXROW_VAL 1472
    mov x23, #-1
    HEXROW_VAL 1536
    mov x23, #-1
    HEXROW_VAL 1600
    mov x23, #0
    HEXROW_VAL 1504
.Lexec_keep_completed_results:
    adr x9, probe_exec_state
    ldr x10, [x9, #80]
    add x10, x10, #1
    str x10, [x9, #80]
    mov x23, x10
    HEXROW_VAL 1408
'''
        return source
    row={0xfffffff00769cfac:1440,V32.RETURN:1536,0xfffffff00769d110:1472}.get(site)
    if row is not None:
        # This is the actual native post-call value even if trace state was lost.
        source=f'    mov w23, w0\n    HEXROW_VAL {row}\n'+source
    if site in (0xfffffff00769d0d8,0xfffffff00769d0dc):
        # Native successful switch is sufficient to arm the restore boundary;
        # do not depend on an earlier diagnostic active bit surviving cloneproc.
        source=source.replace(f'    cbz x10, .Lexec_observe_done_{site:x}',
                              '    mov x10, #1\n    str x10, [x9]')
    return source
