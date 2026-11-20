#!/usr/bin/env python3
"""Strict host-only linked and FAT readback checks for compact r35b."""
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import shlex
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT.parent / "UniXNU-nuwa"
OUT = ORIGINAL / "out"
BUILD = Path(os.environ.get("NUWA_DETAIL_BUILD", OUT / "nuwa-r35b-compact-r3-20261120"))
VERIFY_SHA = "aa76ca5add61a9a552043cc01b287f9fb2bfabb0549d68bbda678090840f6f2c"
OLD_CHMH = "9ea4853ca37f2e59310720d6803a30d39c2a74da60d12c30896d168ed80fafbe246969138120f6b1b512a3d6fc3be0be"
COMPACT_CHMH = "ca463c3f4ba9168203323e4350255d2b0c5f53e4033211dcf2f3124291c63ea7104b5d6fac7da9a3b859dafaefe58528"
DETAIL_CHMH = "a2a63d57d618553ee89e986d820c36fbc329c88d7d5ff8850208d4fe56a5303c382ef030f1990b082d441a583bfa2010"
SNAPSHOT_CHMH = "4c49a290616c62e39805f7390cb9bd5ea5772ca4f65542b5767ffc6c6df51bb778cf5d2f7ff5b97a6c3288148b18f48d"
OLD_KERNEL_SHA = "ad7e70f7e615494c6162cec1a72610e119e897414bb89e4e038075244442da2f"


def linked(package):
    verify = OUT / "nuwa-r35-20261119/verify_r35.sh"
    source = verify.read_bytes()
    if hashlib.sha256(source).hexdigest() != VERIFY_SHA:
        raise ValueError("pinned linked audit source changed")
    text = source.decode()
    replacements = {
        f"D={verify.parent}": f"D={shlex.quote(str(BUILD))}",
        f"P={OUT}/nuwa-ufs-apfs-root-chmh-20261119-r35": f"P={shlex.quote(str(package))}",
        f"R={verify.parent}/BootProgress.c": 'R="$D/BootProgress.c"',
        "grep -qaF 'if(status || ns) {' \"$R\"":
            "grep -qaF 'if(signal || ns) {' \"$R\" && ! grep -qaF 'if(status || ns) {' \"$R\"",
        "import importlib.util\nspec = importlib.util.spec_from_file_location(\n"
        f"    'r34', '{ORIGINAL}/scripts/build-ufs-apfs-root-chmh-r34.py')\n"
        "saved = sys.argv\nsys.argv = ['r34']\nmod = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(mod)\nsys.argv = saved":
            f"import runpy\nprofile = runpy.run_path({str(ROOT / 'scripts/build-ufs-apfs-root-chmh-r35b.py')!r})"
            "['load_profile']()",
        "mod.X.C.extract(pkg / 'payload.img', work)": "profile['X'].C.extract(pkg / 'payload.img', work)",
    }
    if os.environ.get("NUWA_DETAIL_BUILD"):
        replacements["grep -qaF 'bar(0, line,' \"$R\""] = \
            "grep -qaF 'if (!i) bar(0,b,' \"$R\""
        replacements['ck "EX%u %.6s %x:%x:%x"'] = \
            'ck "EX%u %-6.6s sig=%u ns=%08x code=0x%08x n=%u pc=%016llx"'
    for old, new in replacements.items():
        if text.count(old) != 1:
            raise ValueError("linked audit anchor changed: " + old)
        text = text.replace(old, new, 1)
    proc = subprocess.run(["bash", "-s"], input=text, text=True, capture_output=True, cwd=ORIGINAL)
    (BUILD / "check-linked.log").write_text(proc.stdout + proc.stderr)
    if proc.returncode or proc.stderr or proc.stdout.splitlines()[-1:] != ["ALL PASS"]:
        failure = next((line for line in proc.stdout.splitlines() if line.startswith("FAIL")), proc.stderr.strip())
        raise ValueError("linked audit failed: " + failure)
    print("linked audit: ALL PASS")


def strict_fat(package, audit, fat_clusters):
    def inspect(path):
        blob = path.read_bytes()
        cb, count, free = fat_clusters(blob)
        bps = struct.unpack_from("<H", blob, 0x0b)[0]
        fs = struct.unpack_from("<H", blob, 0x30)[0] * bps
        if (blob[fs:fs + 4], blob[fs + 484:fs + 488], blob[fs + 508:fs + 512]) != (
                b"RRaA", b"rrAa", b"\0\0\x55\xaa"):
            raise ValueError("bad FSInfo signatures")
        fsfree = struct.unpack_from("<I", blob, fs + 488)[0]
        proc = subprocess.run(["fsck.fat", "-vn", str(path)], text=True, capture_output=True, check=True)
        result = re.search(r"(\d+)/(\d+) clusters", proc.stdout)
        if not result or int(result[2]) != count or count - int(result[1]) != free or fsfree != free:
            raise ValueError("data-cluster count differs across FAT, FSInfo and fsck")
        return {"sha256": hashlib.sha256(blob).hexdigest(), "cluster_bytes": cb,
                "clusters": count, "used_clusters": count - free, "free_bytes": free * cb}

    old = inspect(OUT / "nuwa-ufs-apfs-root-chmh-20261120-r35b/payload.img")
    actual = inspect(audit / "actual-vendor-ramdisk.img")
    if old["free_bytes"] >= 8388608 or actual["free_bytes"] < 8388608:
        raise ValueError("8 MiB floor: old package must fail and compact package must pass")
    audit_report = json.loads((audit / "audit.json").read_text())
    if actual["sha256"] != audit_report["ramdisk_sha256"] or actual["sha256"] != hashlib.sha256(
            (package / "payload.img").read_bytes()).hexdigest():
        raise ValueError("outer readback differs from packaged FAT")
    if hashlib.sha256((package / "vendor_boot.img").read_bytes()).hexdigest() != audit_report["outer_sha256"]:
        raise ValueError("audit does not cover the selected vendor_boot")
    return {"old": old, "compact": actual, "floor_bytes": 8388608}


def final_symbols(blob):
    offset = 32
    for _ in range(struct.unpack_from("<I", blob, 16)[0]):
        cmd, size = struct.unpack_from("<II", blob, offset)
        if cmd == 2:  # LC_SYMTAB
            sym, count, strings, strings_size = struct.unpack_from("<IIII", blob, offset + 8)
            names = blob[strings:strings + strings_size]
            return Counter(
                (names[index:names.index(0, index)], kind, section, desc, value)
                for index, kind, section, desc, value in struct.iter_unpack(
                    "<IBBHQ", blob[sym:sym + count * 16])
                if not kind & 0xe0)
        offset += size
    raise ValueError("final Mach-O has no LC_SYMTAB")


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: test-r35b-compact-package.py PACKAGE AUDIT")
    package, audit = (Path(p).resolve(strict=True) for p in sys.argv[1:])
    profile = runpy.run_path(str(ROOT / "scripts/build-ufs-apfs-root-chmh-r35b.py"))["load_profile"]()
    linked(package)
    report = strict_fat(package, audit, profile["X"].fat_clusters)
    reference = os.environ.get("NUWA_DETAIL_REFERENCE")
    old_kernel = (Path(reference) if reference else OUT / "nuwa-r35b-exit-selection-20261120/kernel.macho").read_bytes()
    new_kernel = (package / "kernel.macho").read_bytes()
    if (not reference and hashlib.sha256(old_kernel).hexdigest() != OLD_KERNEL_SHA) or hashlib.sha256(
            new_kernel).hexdigest() != profile["KERNEL_SHA"]:
        raise ValueError("final kernel pin mismatch")
    old_symbols, new_symbols = final_symbols(old_kernel), final_symbols(new_kernel)
    if old_symbols != new_symbols:
        raise ValueError("final non-STAB symbol tuples changed")
    report["final_non_stab_symbols_preserved"] = sum(new_symbols.values())
    record = json.loads((package / "record.json").read_text())
    digest = record["chmh_hex"]
    if digest == OLD_CHMH or (reference and digest in (COMPACT_CHMH, DETAIL_CHMH)) or \
            (profile["KERNEL_SHA"] != "9e6a15388c1ac09932eaeb9eef4511d3df9a5587935ee507a4c7fed66a317492" and digest == SNAPSHOT_CHMH) or len(digest) != 96:
        raise ValueError("new CHMH missing")
    report["chmh"] = digest
    (BUILD / "strict-package.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
