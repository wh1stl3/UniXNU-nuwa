#!/usr/bin/env python3
"""Assert the deleted banner rows are gone and the SB row is generated.

Host-only: the generator is run on the pinned r35l renderer and the generated
text is inspected.  No device, boot or kernel-runtime claim.
"""
import importlib.util
from pathlib import Path

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("diag", root / "scripts/generate_r35_display_diag.py")
diag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diag)
source = (root / "out/nuwa-r35l-regs-full-20261121/BootProgress.c").read_bytes()
text = diag.generate(source, mg_reset=True, pixsig=True).decode()

# Deleted rows: the format string must not exist any more.
for gone in ('"DSP reg=', '"DSP s=', '"DSP+ ', '"PEER ', '"SVC ',
             '"SC n=', '"SC unavailable"', '"LOAD  user=',
             '"TIMER vct=', '"UFS L r='):
    assert gone not in text, gone

# Kept rows and the new SpringBoard row.
for kept in ('"SB never"', '"SB gone"', '"SB %u:%s"',
             '"PROC n=%d SB=%s"', '"PIX bk=%u so=%u unk=%u chg=%u"',
             '"UFS TIME vf=', '"DATA mnt ', '"DATA hdr=', '"PROP %04x FDR '):
    assert kept in text, kept

# The live banner repaints when the same two-second sample changes.
assert "signature+=(&nuwa_sb_public?__atomic_load_n(&nuwa_sb_public,__ATOMIC_ACQUIRE):0)" in text

# Deleted rows left no reads behind.
for gone in ("host_statistics64(", "nuwa_dsp_reg", "nuwa_sc_calls",
             "bp_icon_pid", "bp_svc_mask", "banner_load", "banner_ufs_"):
    assert gone not in text, gone

print("deleted rows absent, kept rows and SB row present")
