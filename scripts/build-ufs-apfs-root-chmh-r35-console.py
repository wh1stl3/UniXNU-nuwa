#!/usr/bin/env python3
"""Package the pinned FDR kernel with console-only boot arguments."""
import argparse
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/build-ufs-apfs-root-chmh-r35.py"
SOURCE_SHA = "b5ce56a1784ec1395efa86f32468e8772da516b4b8e4c5e0f6535021c90537e7"
KERNEL_SHA = "033f1065893aaf489565d732f04672cefa868dd6c71fc80a431ec741d1053c52"
OFFLINE = (b" offline-mobile-graphics-load=1 offline-legacy-register=1 offline-legacy-gop=1"
           b" offline-legacy-pm=1 offline-legacy-phase=4 offline-legacy-validate=1"
           b" offline-legacy-transfer=1 offline-legacy-cpu-present=1 nuwa-lite=1")


def main():
    p = argparse.ArgumentParser(allow_abbrev=False)
    p.add_argument("--no-serial", action="store_true")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--audit", type=Path)
    a = p.parse_args()
    out = a.output.resolve()
    audit = a.audit.resolve() if a.audit else None
    kernel = (ROOT / "out/nuwa-r35l-fdr-on-compact/kernel.macho").resolve()
    for path in (out, kernel, *([audit] if audit else [])):
        if (ROOT / "out").resolve() not in path.parents:
            p.error("paths must be within device out/")
    if out.exists():
        p.error("output must be new")
    blob = kernel.read_bytes()
    if hashlib.sha256(blob).hexdigest() != KERNEL_SHA:
        raise ValueError("FDR kernel pin mismatch")
    source = SOURCE.read_bytes()
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA:
        raise ValueError("r35 source pin mismatch")
    text = source.decode()
    old = "'native-ufs-root=1', 'boot-progress=2',"
    new = "'native-ufs-root=1', 'debug=0x14e',"
    if text.count(old) != 1:
        raise ValueError("r35 args check anchor changed")
    text = text.replace(old, new)
    sys.argv = [str(SOURCE), "--output", str(out)]
    if audit:
        sys.argv.extend(("--audit", str(audit)))
    ns = {"__file__": str(SOURCE), "__name__": "r35_console_packager"}
    exec(compile(text, str(SOURCE), "exec"), ns)
    args = ns["ARGS"].replace(b" boot-progress=2", b" debug=0x14e") + OFFLINE
    if a.no_serial:
        args = args.replace(b" serial=3", b"")
    tokens = args.split()
    if b"debug=0x14e" not in tokens or any(t.startswith(b"boot-progress=") for t in tokens):
        raise ValueError("console argument transform failed")
    profile = "nuwa-r35-fdr-console-" + ("video" if a.no_serial else "serial")
    inputs = dict(KERNEL=kernel, KERNEL_BYTES=len(blob), KERNEL_SHA=KERNEL_SHA,
                  PROFILE=profile, ARGS=args)
    ns.update(inputs)
    for module in (ns["X"], ns["M"]):
        vars(module).update(inputs)
    ns["M"].main()


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    main()
