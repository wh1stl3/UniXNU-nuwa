#!/usr/bin/env python3
"""Read-only regression for the two fixed split FAT images and ON outer pin."""
import ast
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/build-ufs-apfs-root-chmh-r14.py"
OUTER = "09d11016b7710a29f8aba936fe397aae79bf7ec01cef5ef27b760ec37b967efa"
FATS = {
    "off": ("90a5447c8c67a18c9f14fdb6a67c1620252f5ab472555b018478c9149518121e", 8355328),
    "on": ("3d8ed2bd8009d704c570adda524aa3b378165c243feb61d044fda66a4a620664", 11931136),
}


def main():
    node = next(n for n in ast.parse(SOURCE.read_text()).body
                if isinstance(n, ast.FunctionDef) and n.name == "fat_clusters")

    def require(ok, message):
        if not ok:
            raise ValueError(message)

    namespace = {"require": require, "struct": struct}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(SOURCE), "exec"), namespace)
    for mode, (pin, expected) in FATS.items():
        path = ROOT / f"out/nuwa-r35-display-split-{mode}/payload.img"
        blob = path.read_bytes()
        require(hashlib.sha256(blob).hexdigest() == pin, f"{mode} FAT pin changed")
        cb, clusters, free = namespace["fat_clusters"](blob)
        bps = struct.unpack_from("<H", blob, 0x0b)[0]
        fs = struct.unpack_from("<H", blob, 0x30)[0] * bps
        require(blob[fs:fs + 4] == b"RRaA" and blob[fs + 484:fs + 488] == b"rrAa"
                and blob[fs + 508:fs + 512] == b"\x00\x00\x55\xaa", "FSInfo signatures")
        fsfree = struct.unpack_from("<I", blob, fs + 488)[0]
        require(free * cb == expected == fsfree * cb, f"{mode} FAT/FSInfo disagree")
        proc = subprocess.run(["fsck.fat", "-vn", str(path)], capture_output=True, text=True)
        require(proc.returncode == 0, f"{mode} fsck failed: {proc.stdout}\n{proc.stderr}")
        match = re.search(r"(\d+)/(\d+) clusters", proc.stdout)
        require(match and int(match[2]) == clusters
                and (int(match[2]) - int(match[1])) * cb == expected,
                f"{mode} directory-chain fsck mismatch")
        old_total = struct.unpack_from("<I", blob, 0x20)[0] // blob[0x0d]
        at = struct.unpack_from("<H", blob, 0x0e)[0] * bps
        old_used = sum(bool(struct.unpack_from("<I", blob, at + i * 4)[0] & 0x0fffffff)
                       for i in range(2, old_total))
        old_free = (old_total - 2 - old_used) * cb
        print(f"{mode}: clusters={clusters} used={match[1]} FSInfo={fsfree} "
              f"old={old_free} corrected={free * cb} "
              f"threshold={'PASS' if free * cb >= 8388608 else 'FAIL'}")
    pkg = ROOT / "out/nuwa-r35-display-split-on"
    audit = ROOT / "out/nuwa-r35-display-split-on-audit"
    outer = hashlib.sha256((pkg / "vendor_boot.img").read_bytes()).hexdigest()
    require(outer == OUTER == json.loads((audit / "audit.json").read_text())["outer_sha256"],
            "ON outer/image audit pin mismatch")
    require(hashlib.sha256((audit / "actual-vendor-ramdisk.img").read_bytes()).hexdigest()
            == FATS["on"][0], "ON outer FAT readback mismatch")
    print(f"on outer SHA256={outer}; outer readback FAT SHA256={FATS['on'][0]}")


if __name__ == "__main__":
    main()
