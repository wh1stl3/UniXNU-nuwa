#!/usr/bin/env python3
"""Assert the NEON identity row survives and the deleted evidence rows are gone.

Host-only source test: the UFS survey rows (HC/DEV/LU/MS/PL) and the reads that
existed only for them were removed; the identity row (build/cid/phase) stays on
the page and in the live banner.
"""
import argparse
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def main(build=None):
    inc = (ROOT / "package/nuwa-data-write/RetainedNeon.inc").read_text()
    driver = (ROOT / "scripts/build-nuwa-display-native.py").read_text()
    for gone in ("NEON HC", "NEON DEV", "NEON LU", "NEON MS", "NEON PL",
                 "probeNeon", "neonPre", "neonDesc", "neonMedia", "neonHc"):
        assert gone not in inc, gone
    assert 'snprintf(rows[0], 120, "%s s=%u old=? rsr=?", NuwaNeon::Identity, phase);' in inc
    assert "neonBegin" in inc and "nuwa_ufs_neon_rows" in inc
    for gone in ("probeNeon", "neonPre", "__atomic_load_n(&neonPhase"):
        assert gone not in driver, gone
    assert "probeUfsDescriptors();" in driver
    if build is not None:
        renderer = (build / "BootProgress.c").read_text()
        assert "nuwa_ufs_neon_rows(evidence,6)" in renderer and "line(37+i,evidence[i]" in renderer
        assert "nuwa_ufs_neon_rows(rows,budget)" in renderer
        assert "bp_cr_rows(rows+neon,budget-neon)" in renderer
        assert not re.search(r'"NEON (HC|DEV|LU|MS|PL)', renderer)
    print("NEON identity row kept; HC/DEV/LU/MS/PL producers and reads removed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("build", type=Path, nargs="?")
    parser.add_argument("base", type=Path, nargs="?")
    parser.add_argument("--fixtures", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    main(args.build.resolve() if args.build else None)
