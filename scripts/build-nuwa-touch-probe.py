#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Patent
"""Build the isolated probe archive and/or run host-only touch tests."""

import argparse
from pathlib import Path
import shlex
import subprocess


ROOT = Path(__file__).resolve().parents[1]
GENI_REV = "eac47baefe6a5d2368a70351e6ad1b6361bedbe2"
DEFAULT_GENI = ROOT.parent.parent / "UniXNU" / "drivers" / "QcomGeniSpi"
PROBE = ROOT / "package" / "nuwa-touch"
TEST = ROOT / "tests" / "test-nuwa-touch-probe.c"
HID_TEST = ROOT / "tests" / "test-nuwa-hid-report.c"


def run(args):
    print("+", shlex.join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), check=True)


def check_source(geni):
    head = subprocess.check_output(
        ["git", "-C", str(geni), "rev-parse", "HEAD"], text=True
    ).strip()
    if head != GENI_REV:
        raise SystemExit(f"{geni}: expected {GENI_REV}, got {head}")
    for name in ("GeniSpi.c", "GeniSpi.h"):
        source = (geni / name).read_bytes().replace(b"\r\n", b"\n")
        pinned = subprocess.check_output(
            ["git", "-C", str(geni), "show", f"{GENI_REV}:{name}"]
        ).replace(b"\r\n", b"\n")
        if source != pinned:
            raise SystemExit(f"{geni / name}: differs from pinned source")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--geni-dir", type=Path, default=DEFAULT_GENI)
    parser.add_argument("--out", type=Path, default=ROOT / "out" / "nuwa-touch-probe-20261128")
    parser.add_argument("--clang", default="clang")
    parser.add_argument("--ar", default="llvm-ar")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--hid-self-test", action="store_true",
                        help="compile and run the standalone HID report test")
    parser.add_argument("--archive", action="store_true",
                        help="compile a freestanding arm64 Mach-O archive, not an image")
    args = parser.parse_args()
    if not args.self_test and not args.archive and not args.hid_self_test:
        parser.error("select --self-test, --hid-self-test and/or --archive")

    geni = args.geni_dir.resolve()
    out = args.out.resolve()
    if args.self_test or args.archive:
        check_source(geni)
    out.mkdir(parents=True, exist_ok=True)
    flags = ["-std=c11", "-Wall", "-Wextra", "-Werror",
             "-I", str(PROBE), "-I", str(geni)]
    sources = [PROBE / "NuwaTouchProbe.c", geni / "GeniSpi.c"]

    if args.self_test:
        exe = out / "test-nuwa-touch-probe"
        run([args.clang, *flags, *sources, TEST, "-o", exe])
        run([exe])

    if args.hid_self_test:
        exe = out / "test-nuwa-hid-report"
        run([args.clang, "-std=c11", "-Wall", "-Wextra", "-Werror",
             "-I", PROBE, PROBE / "NuwaHidReport.c", HID_TEST, "-o", exe])
        run([exe])

    if args.archive:
        objects = []
        for source in sources:
            obj = out / (source.stem + ".o")
            run([args.clang, "-target", "arm64-apple-macos11", "-ffreestanding",
                 "-fno-stack-protector", "-fno-common", *flags, "-c", source, "-o", obj])
            objects.append(obj)
        archive = out / "libNuwaTouchProbe.a"
        run([args.ar, "rcs", archive, *objects])
        print(f"archive: {archive} (not linked or packaged)")


if __name__ == "__main__":
    main()
