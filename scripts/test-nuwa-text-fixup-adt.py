#!/usr/bin/env python3
"""Check that the packager's /chosen/text-fixups bytes are exactly what
scripts/make-nuwa-adt.py --text-fixup writes for the pinned 20H392 entry."""
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import nuwa_launch_context as adt  # noqa: E402


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


packager = load("r35_display_textfixup", ROOT / "scripts/build-ufs-apfs-root-chmh-r35-display.py")
assert packager.TEXT_FIXUPS == packager.TEXT_FIXUP_ENTRY.encode() + b"\0"
assert packager.TEXT_FIXUPS.endswith(b"\0")

name, offset, original, replacement = packager.TEXT_FIXUP_ENTRY.split(",")
assert offset == "1cd5a9c", "offset must be bare hex; cs_text_fixup_parse rejects 0x"
offset = int(offset, 16)
assert len(name) <= 63
assert len(original) == len(replacement) == 16
assert (offset & 0xFFF) + len(original) // 2 <= 4096, "fixup crosses a page"

with tempfile.TemporaryDirectory() as tmp:
    out = Path(tmp) / "kernel.macho.adt"
    subprocess.run([sys.executable, "-B", str(ROOT / "scripts/make-nuwa-adt.py"),
                    "--output", str(out), "--dram-size", "0x240000000",
                    "--text-fixup", packager.TEXT_FIXUP_ENTRY], check=True)
    tree = adt.parse(out.read_bytes())
    got = adt.properties(adt.find(tree, "/chosen")).get("text-fixups")
    assert got == packager.TEXT_FIXUPS, (got, packager.TEXT_FIXUPS)
    print("make-nuwa-adt text-fixups bytes:", got)
print("text-fixup ADT entry: PASS")
