#!/usr/bin/env python3
"""Compare the built renderer with the pinned banner-r2 source (host only)."""
import argparse
from hashlib import sha256
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "out/nuwa-sb-banner-20261127-build-r2/BootProgress.c"
BASELINE_SHA256 = "5087c779f3b0c16f10dd54cc934ecb8481dd7faef94e2b4ab884a4c40364f49e"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--renderer", type=Path, required=True)
    ap.add_argument("--kernel", type=Path, required=True)
    args = ap.parse_args()

    original = BASELINE.read_bytes()
    assert sha256(original).hexdigest() == BASELINE_SHA256
    actual = args.renderer.read_bytes()

    # Compare every byte outside the three removed example-only source regions.
    ranges = (
        (b"/*\n * nuwa r21: glyph path self test.", b"#define ST_BAND_PAD 8\n",
         b"/* Retain the r21 non-glyph pixel probes at their original positions. */\n"),
        (b"// One character cell with an explicit scale.", b"static void st_bar(", b""),
        (b'  const char *l1="0123456789"', b"  for(unsigned i=0;i<16;++i) st_bar(",
         b"  unsigned y=top+336;\n"),
    )
    expected = original
    for first, last, replacement in ranges:
        assert expected.count(first) == expected.count(last) == 1
        start = expected.index(first)
        end = expected.index(last, start)
        expected = expected[:start] + replacement + expected[end:]
    assert actual == expected, "renderer differs beyond the glyph-example removal"

    for text in (b"nuwa_glyph_selftest(now);", b"unsigned y=top+336;",
                 b"st_bar(4+i*33,y,3,40,0xffffffff)",
                 b"st_bar(0,y,display.width,1,0xffffffff)"):
        assert text in actual
    for text in (b"static void st_char(", b"static void st_text(",
                 b"0123456789\",*l2=", b"=_-+iIl1", b"p1=0 uni=1 amfi=1"):
        assert text not in actual
    kernel = args.kernel.read_bytes()
    assert b"=_-+iIl1\0" not in kernel
    assert b"p1=0 uni=1 amfi=1\0" not in kernel
    print("glyph examples removed; remaining renderer and pixel probes unchanged: PASS")


if __name__ == "__main__":
    main()
