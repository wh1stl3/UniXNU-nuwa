#!/usr/bin/env python3
"""Package pinned r35 OFF or an audited display ON kernel with the r35 chain."""
import argparse
import hashlib
import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/build-ufs-apfs-root-chmh-r35.py"
SOURCE_SHA = "16ed1a3b762152a0426701942224d5c7008edb01829c97bc8132a5262e7d3b96"
R35_SHA = "787610183dc7f772e2d01aa183f72f2fcc52245fc44407e6c815ced614412464"
DISPLAY_KERNELS = {
    "c5e0d39475111198acd7d0ce8900178134f7b6a08785963e25652c34ccf503db",
    "033f1065893aaf489565d732f04672cefa868dd6c71fc80a431ec741d1053c52",
    "476477dab77fe2342128ddd79881d6fd26b1d7b4d48d65e723860478aafdcb17",
    "89355aa4e0dc0f3d2e9ef1971e94d45f6584f66d4ae318e6ac2bdc832fce4b39",
    "7ae5623c8a82ddbbcef1da905de3e39fb4c5e4ec4d5f35e7b9bb3348e062674f",
    "d33ef2ccf95478959ada320174f19203d0d7d6d17077ac60e69a00efbda6dfc5",
    "70575178c4f32674630de7da44ebea3224b10a82db005d6e88527e3880002cae",
}
DISPLAY_ARGS = (b" offline-mobile-graphics-load=1 offline-legacy-register=1 offline-legacy-gop=1"
                b" offline-legacy-pm=1 offline-legacy-phase=4 offline-legacy-validate=1"
                b" offline-legacy-transfer=1 offline-legacy-cpu-present=1")


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument("--kernel-sha256", required=True)
    parser.add_argument("--enable-display", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--audit", type=Path)
    a = parser.parse_args()
    kernel = a.kernel.resolve()
    output = a.output.resolve()
    audit = a.audit.resolve() if a.audit else None
    for path in (kernel, output, *([audit] if audit else [])):
        if (ROOT / "out").resolve() not in path.parents:
            parser.error(f"expected a path inside device out/: {path}")
    if output.exists():
        parser.error("--output must be new")
    blob = kernel.read_bytes()
    if hashlib.sha256(blob).hexdigest() != a.kernel_sha256:
        parser.error("kernel SHA256 mismatch")
    if a.enable_display:
        if a.kernel_sha256 not in DISPLAY_KERNELS:
            parser.error("on profile requires a pinned display kernel SHA256")
    elif a.kernel_sha256 != R35_SHA:
        parser.error("off profile requires the original r35 kernel SHA256")
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != SOURCE_SHA:
        raise ValueError("Pinned r35 packager changed")

    # r35b reuses the pinned r35 packager and overrides its profile inputs.
    # Here kernel size and (optionally) args change as well, without editing
    # the parent or weakening any of its root/ADT/FAT/outer audits.
    sys.argv = [str(SOURCE), "--output", str(output)]
    if audit:
        sys.argv.extend(("--audit", str(audit)))
    spec = importlib.util.spec_from_file_location("r35_display_packager", SOURCE)
    r35 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(r35)
    profile = "nuwa-ufs-apfs-root-chmh-20261120-r35-display"
    inputs = dict(KERNEL=kernel, KERNEL_BYTES=len(blob), KERNEL_SHA=a.kernel_sha256,
                  PROFILE=profile + ("-on" if a.enable_display else "-off"),
                  ARGS=r35.ARGS + (DISPLAY_ARGS + b" nuwa-lite=1" if a.enable_display else b""))
    for module in (r35, r35.X, r35.M):
        vars(module).update(inputs)
    r35.M.main()


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    main()
