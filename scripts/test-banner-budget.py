#!/usr/bin/env python3
"""Check the banner geometry and generated source contract."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_r35_display_diag import generate

root = Path(__file__).resolve().parents[1]
source = (root / "out/nuwa-r35l-regs-full-20261121/BootProgress.c").read_bytes()
generated = generate(source, mg_reset=True)
assert b"if(cols>80)cols=80;" in generated
assert b"if(!n || display.height<(n+2)*cell+8)return;" in generated
for height in range(1, 4000):
    for scale in range(1, 5):
        cell = 14 * scale
        half = height // 2
        if half < 8 + 2 * cell:
            continue
        budget = min(24, (half - 8) // cell - 2)
        assert (budget + 2) * cell + 8 <= half
print("banner geometry source contract: PASS")
