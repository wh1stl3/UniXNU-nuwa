#!/usr/bin/env python3
"""Check the FDR overlay against the pinned r35l renderer."""
import sys
from pathlib import Path
from generate_r35_display_diag import generate

src = generate(Path(sys.argv[1]).read_bytes()).decode()
exit_fn = src[src.index("void boot_progress_exit(int pid,"):]
assert exit_fn.index('__atomic_store_n(&bp_fdr_exit') < exit_fn.index('__atomic_exchange_n(&exit_lock')
assert 'strcmp(name,"IOMFB_FDR_Loader")' in exit_fn
assert 'if((signal || ns) && !(name && !strcmp(name,"IOMFB_FDR_Loader")))' in exit_fn
assert src.count('__atomic_load_n(&bp_fdr_exit,__ATOMIC_RELAXED)') == 1
assert 'line(10,b,0xff00ffcc);' in src
assert 'FDR no exit seen' in src
assert len(f"FDR {0xffffffff}s st={0xffff} sig={0xff}") <= 80
assert 'CLI in=%u out=%u ret=%08x bb=%c' in src
assert len(f"DSP s={255} r={255} CLI in={0xffffffff} out={0xffffffff} ret={0xffffffff:08x} bb=?") <= 80
assert 'CLI unavailable' in src
for second, status in [(1, 0), (388, 0x100), (42, 5), (0xffffffff, 0xffff)]:
    value = second << 32 | (status & 0xffff) << 16 | status & 127
    assert (value >> 32, (value >> 16) & 0xffff, value & 0xff) == (second, status, status & 127)
print("FDR overlay checks passed")
