"""Revision44: reduce compressed-read display traffic without changing sites.

Only IDs373..440 become 32x2 strips. Native execution and display memory
attributes are unchanged; this is an observer-cost experiment, not a lock fix.
"""
import hashlib
from pathlib import Path


def plan():
    return dict(source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                first_id=373,last_id=440,width=32,height=2,previous_height=16,
                bytes_per_marker=256,previous_bytes_per_marker=2048,
                native_policy_changed=False,all_observations_retained=True,
                memory_attributes_changed=False)


def transform(template):
    start=template.index('.macro DENSE_ONCE');end=template.index('.endm',start)
    dense=template[start:end]
    old='    mov x13, #dense_tile_height'
    assert dense.count(old)==1
    dense=dense.replace(old,'    .if \\idx >= 373\n    mov x13, #2\n    .else\n'+old+'\n    .endif')
    return template[:start]+dense+template[end:]
