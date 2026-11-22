#!/usr/bin/env python3
"""Package pinned r35 OFF or an audited display ON kernel with the r35 chain."""
import argparse
from functools import partial
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/build-ufs-apfs-root-chmh-r35.py"
SOURCE_SHA = "b5ce56a1784ec1395efa86f32468e8772da516b4b8e4c5e0f6535021c90537e7"
R35_SHA = "787610183dc7f772e2d01aa183f72f2fcc52245fc44407e6c815ced614412464"
HID_KERNEL = "0a17b5fde4264546bbfcb710adb1752252cdbafb184c796342d8ade53e2a5509"
MG_KERNEL = "0637d5f37a78370085c03da762888dadb6ba6269dbbb0b2a517d3b47972a5d9b"
MG_PROP_KERNEL = "591957c24f510e5e77c43936fe6480cd874dce49fb0b3b48b09db51b3ebbb1f9"
MG_PROP_SC_KERNEL = "a6f2218eb2ee544390d344c1b555c9d5b226f70d7d702e971079af79f24525a5"
MG_PROP_SC_REFRESH_KERNEL = "8358b013cf9f28a7fb8649491cd7f0b9931ab4750f05260ff7ef1e178ac94f1c"
MG_ROTATION_KERNEL = "0bf8950fba416b9537782df245c43f8099e0e10f7c93c6f2d3fc35e604f50e5a"
MG_HANDOFF_SC_KERNEL = "ba1f6913cf0412b3e8714b3f3dfca8daa8922768aa427e12b6d8d0f4cf53729b"
DISPLAY_KERNELS = {
    # Client identity probe (sticky bb); fingerprint delta recorded separately.
    "daa0288fb7786a0b6078a0608b2d09fc5c4a71252a5d4a42944ac5b7da14293b",
    # NormalModeEnable/ADCLLoadAll publication build; fingerprint change is
    # separately recorded in docs/nuwa-fdr-properties-20261122.md.
    "e9f0b5e125be778b9c3fff8939659a6c9f67c61fb722c70a331c5ee8c8547b2d",
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
    parser.add_argument("--enable-hid-standin", action="store_true",
                        help="append only nuwa-hid-standin=1 to the 4.75 GiB display ON profile")
    parser.add_argument("--enable-mg-reset-resume-only", action="store_true",
                        help="4.75 GiB display ON, resume Data without reset and enable MG backup")
    parser.add_argument("--board-window", action="store_true",
                        help="derive the window from board.toml")
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
    if a.enable_mg_reset_resume_only:
        if not (a.enable_display and a.board_window) or a.enable_hid_standin:
            parser.error("--enable-mg-reset-resume-only requires --enable-display --board-window without HID")
        if a.kernel_sha256 not in (MG_KERNEL, MG_PROP_KERNEL, MG_PROP_SC_KERNEL, MG_PROP_SC_REFRESH_KERNEL, MG_ROTATION_KERNEL, MG_HANDOFF_SC_KERNEL):
            parser.error("MG ON profile requires the pinned MG reset kernel")
    elif a.enable_hid_standin:
        if not (a.enable_display and a.board_window):
            parser.error("--enable-hid-standin requires --enable-display and --board-window")
        if a.kernel_sha256 != HID_KERNEL:
            parser.error("HID ON profile requires the pinned audited kernel")
        report = kernel.parent / "hid/final-audit.json"
        if not report.is_file() or json.loads(report.read_text()).get("kernel_sha256") != HID_KERNEL:
            parser.error("HID ON profile requires the matching final-link audit")
    elif a.enable_display:
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
    if a.enable_hid_standin:
        inputs["PROFILE"] += "-hid"
        inputs["ARGS"] += b" nuwa-hid-standin=1"
    if a.enable_mg_reset_resume_only:
        inputs["PROFILE"] += "-mg-reset-resume-only"
        tokens = inputs["ARGS"].split()
        tokens.remove(b"sheng-data-reset=1")
        inputs["ARGS"] = b" ".join(tokens + [b"nuwa-mg-reset=1"])
        r35.M.check_inputs = partial(r35.check_inputs, resume_only=True)
    for module in (r35, r35.X, r35.M):
        vars(module).update(inputs)
    if a.board_window:
        size = int(tomllib.loads((ROOT / "board.toml").read_text(encoding="utf-8"))
                   ["payload"]["adt"]["owned_memory_size"], 0)
        if not 0x10000000 <= size <= 0x200000000 or size % 0x200000:
            raise ValueError("board window outside UniXNU's ADT size contract")
        if a.enable_mg_reset_resume_only and size != 0x130000000:
            raise ValueError("MG ON profile requires the 4.75 GiB baseline window")
        previous = r35.X.derived
        adt = r35.A

        def derived(parent, digest):
            tree = adt.parse(previous(parent, digest))
            chosen = adt.find(tree, "/chosen")
            props = chosen["properties"]
            matches = [i for i, p in enumerate(props) if p[0] == "darwinboot-memory-size"]
            if len(matches) != 1 or len(props[matches[0]][2]) != 8:
                raise ValueError("parent ADT window is not a unique u64")
            i = matches[0]
            props[i] = (props[i][0], props[i][1], size.to_bytes(8, "little"))
            if a.enable_mg_reset_resume_only:
                value = (3).to_bytes(4, "little")
                if "display-scale" in adt.properties(chosen):
                    raise ValueError("parent already has /chosen/display-scale")
                if adt.properties(adt.find(tree, "/product")).get("artwork-scale-factor") != value:
                    raise ValueError("/product/artwork-scale-factor is not u32 3")
                props.append(("display-scale", 0, value))
            return adt.encode(tree)

        r35.X.derived = r35.X.C.derived = derived
    r35.M.main()
    if a.enable_mg_reset_resume_only:
        readback = output if audit else output / "outer-audit"
        config = tomllib.loads((readback / "outer-readback/EFI/UniXNU/unixnu.toml")
                               .read_text(encoding="utf-8"))
        for entry in config["entry"]:
            tokens = entry.get("args", "").split()
            r35.require(not any(t.split("=", 1)[0] == "sheng-data-reset" for t in tokens),
                        "Outer readback contains sheng-data-reset")


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    main()
