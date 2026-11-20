#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Patent
"""Reproduce the incomplete display archive and attempt an isolated native link.

Host-only: this deliberately does not install hooks, package an image, or
qualify the 329/330 contracts. Outputs must stay in the device out directory.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
DONOR_SHA = "2ec297bac95bcba01046fd0148e97e7e5885c05a6c18827f39f534ba375c1221"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args, cwd=None):
    print("+", shlex.join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), cwd=cwd, check=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base", type=Path, required=True)
    p.add_argument("--cpo", type=Path, required=True)
    p.add_argument("--link-dir", type=Path, required=True,
                   help="8796 mach.development.bcm2837.link directory")
    p.add_argument("--linker-dir", type=Path, required=True,
                   help="directory containing the 8796 Mach-O ld")
    p.add_argument("--out", type=Path, required=True, help="new directory under out/")
    a = p.parse_args()
    base, cpo, link, out = (x.resolve() for x in (a.base, a.cpo, a.link_dir, a.out))
    if not out.is_relative_to((ROOT / "out").resolve()) or out == (ROOT / "out").resolve():
        p.error("--out must be a new directory inside device out/")
    out.mkdir(parents=True, exist_ok=False)
    donor = base / "out/ipsw/20H392/kernelcache.decompressed"
    if digest(donor) != DONOR_SHA:
        raise SystemExit("20H392 donor SHA256 mismatch")
    run([sys.executable, "-B", ROOT / "scripts/derive-nuwa-display-abi.py",
         "--base", base, "--kernelcache", donor, "--out", out / "derived"])
    for name in ("OriginalLegacyFramebufferABI.h", "original-bindings.S", "nuwa-display-abi.json"):
        if (out / "derived" / name).read_bytes() != (ROOT / "package" / name).read_bytes():
            raise SystemExit(f"derived {name} differs from device package")
    host = out / "archive"
    run([sys.executable, "-B", ROOT / "scripts/verify-nuwa-display-host-abi.py",
         "--base", base, "--cpo", cpo, "--out", host])
    archive = host / "HOST-ONLY-incomplete-display.a"
    print(f"host-only archive SHA256 {digest(archive)}", flush=True)

    # Replay XNU's exported link inputs, without its historical map output.
    # Force-loading the incomplete archive cannot make it runtime eligible.
    stem = "mach.development.bcm2837"
    flags = shlex.split((link / (stem + ".linkarguments")).read_text())
    libs = shlex.split((link / (stem + ".linkarchives")).read_text())
    libs = [x for x in libs if not x.startswith("-Wl,-map,")]
    record = json.loads(cpo.read_text().strip().rstrip(","))
    native = out / "HOST-ONLY-display-native.unstripped"
    target = [arg for arg in record["arguments"] if arg.startswith("--target=")][-1]
    command = [record["arguments"][0], target, "-B" + str(a.linker_dir.resolve()), *flags,
               "-Wl,-force_load," + str(link / (stem + ".a")),
               "-Wl,-force_load," + str(archive), *libs, "-o", str(native)]
    (out / "link-argv.json").write_text(json.dumps(command, indent=2) + "\n")
    run(command, cwd=record["directory"])
    print(f"host-only native SHA256 {digest(native)}", flush=True)

    sys.path.insert(0, str(base / "kits/XnuPrelink"))
    import emit_prelink
    board = tomllib.loads((ROOT / "board.toml").read_text())
    roots = board["os_overrides"]["ios-16.7.16-20H392"]["kernel"]["prelink"]["roots"]
    roots = list(dict.fromkeys([*roots, "com.apple.iokit.IOMobileGraphicsFamily"]))
    # Read-only gate: do not persist or package emitted bytes, even if accepted.
    emit_prelink.emit(native.read_bytes(), donor.read_bytes(), roots, -0x1000000)
    print("strict emitter accepted; output discarded, runtime still ineligible")


if __name__ == "__main__":
    main()
