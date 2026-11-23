#!/usr/bin/env python3
"""Package the SMP-gate kernel with the current display ON argument set.

Host only: no device I/O, no flash. Reuse the pinned r35 display packager
with the freshly built kernel and the selected argument set, preserving all
parent root/ADT/FAT/outer/CHMH audits.

By default, remove only the two restart probes from the old HID-stage args.
With --enable-smp-entry, append only sheng-smp=1 to the default-off SMP package.

  --baseline  a previous vendor_boot package whose args differ only by
              " nuwa-sb-restart=400 nuwa-sb-restart-every=180" (default: the
              hid-stage package), or the default-off SMP package in entry mode.
              The outer SHA is pinned in each mode.

The FAT and the non-FAT bytes are compared against that baseline; the args are
then re-extracted from the produced vendor_boot.img itself (FAT sliced out,
members copied with mtools) and checked a second time.
"""
import argparse
import hashlib
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import tomllib

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/build-ufs-apfs-root-chmh-r35-display.py"
SOURCE_SHA = "456886f312bd79d6cedcf8b26e23ca9beebef5c3c65125d080816cd95ca69b08"
PARENT = ROOT / "scripts/build-ufs-apfs-root-chmh-r35.py"
SEED = ROOT / "out/nuwa-systemgroup-seed-20261122/data-8g-sg.dbr"
SEED_SHA = "692355638b31d347ced5983a5910491f0556156f79675c2e371ebe9987683247"
SEED_IDENTITY = "fd554672b1b97df139e533e2d8e74964f6351963d55e4a4483abcec654f1a172"
SEED_UUID = "B0E0F71F-A265-4038-8F5C-6D3632859DEF"
BASELINE = ROOT / "out/nuwa-systemgroup-seed-20261122/vendor-boot-hid-stage"
BASELINE_SHA = "01e6e1c71346c05fb7cc9885d1179346b72e296ef3bbd993952017b6edd6479d"
RESTART = b" nuwa-sb-restart=400 nuwa-sb-restart-every=180"
# The renderer's default-off regression test compares against the gate-only package.
SMP_BASELINE = ROOT / "out/nuwa-smp-gate-20261123-package"
SMP_BASELINE_SHA = "b02007f707302915ec62516dff21bec5d1dd4e0dbaa95ccfe5440d18b3655999"
ENTRY_BASELINE = ROOT / "out/nuwa-smp-observe-20261123-package"
ENTRY_BASELINE_SHA = "9db3c82bd36b6953d3eb35e17a418053a192d78d5d18442a38372ad50e20f599"
ENTRY_KERNEL_SHA = "825eaa8ffdb12fde9f57d7f5bd3cb66fe2d9ac234ffa0955d1038bcbe633332d"
SMP_SUFFIX = b" sheng-smp=1"
# Exact argument text of outer d6de71fcb7caa4c210f2d40e4729fe98611e5336b267eba301fdc8595b723769
# (worktree-textfixup final4): the same profile without any SMP token.
EXPECTED_ARGS = (
    b"-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid "
    b"boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 aks=1 "
    b"disable-watchdogd=1 build-tag=nuwa-r35 boot-progress-scale=3 sheng-data-persist=2 "
    b"sheng-log-reserve=1024 offline-mobile-graphics-load=1 offline-legacy-register=1 "
    b"offline-legacy-gop=1 offline-legacy-pm=1 offline-legacy-phase=4 offline-legacy-validate=1 "
    b"offline-legacy-transfer=1 offline-legacy-cpu-present=1 nuwa-lite=1 nuwa-mg-reset=1 "
    b"nuwa-hid-standin=1")
OLD_HID_PIN = "HID_KERNEL = \"5ba1be16d8e83c35405ec8d7595e16132be41a22932437e4b23ae90d794ce798\""
FORBIDDEN_KEYS = (b"nuwa-sb-restart", b"nuwa-sb-stack", b"sheng-data-reset", b"sheng-smp")
sha = lambda data: hashlib.sha256(data).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def geometry(outer):
    require(outer[:8] == b"VNDRBOOT", "vendor_boot.img has no magic")
    page, fat_size = struct.unpack_from("<I8xI", outer, 12)
    require((page, fat_size) == (4096, 67108864), "unexpected outer geometry")
    return outer[page:page + fat_size], (outer[:page], outer[page + fat_size:])


def split_build(directory):
    outer = (directory / "vendor_boot.img").read_bytes()
    fat, outside = geometry(outer)
    require(fat == (directory / "payload.img").read_bytes(), f"staged FAT differs: {directory}")
    require(fat == (directory / "outer-audit/actual-vendor-ramdisk.img").read_bytes(),
            f"outer readback differs: {directory}")
    return outer, fat, outside


def extract_boot_inputs(outer_path):
    """Read the boot config and ADT directly from the outer's FAT."""
    fat, _ = geometry(outer_path.read_bytes())
    with tempfile.TemporaryDirectory(dir=ROOT / "out", prefix="smp-gate-args-") as tmp:
        image = Path(tmp) / "payload.img"
        image.write_bytes(fat)
        config = Path(tmp) / "unixnu.toml"
        subprocess.run(["mcopy", "-o", "-i", str(image), "::/EFI/UniXNU/unixnu.toml", str(config)],
                       check=True, capture_output=True)
        adt = Path(tmp) / "kernel.macho.adt"
        subprocess.run(["mcopy", "-o", "-i", str(image),
                        "::/EFI/UniXNU/Payloads/kernel.macho.adt", str(adt)],
                       check=True, capture_output=True)
        return config.read_bytes(), adt.read_bytes(), fat


def xnu_args(config):
    args, = [e["args"].encode() for e in tomllib.loads(config.decode())["entry"] if e["id"] == "xnu"]
    return args


class CandidateSeedLoader(importlib.machinery.SourceFileLoader):
    modules = []

    def exec_module(self, r35):
        super().exec_module(r35)
        x = r35.X
        meta, _ = x.PK.inspect(SEED)
        expected = dict(bytes=8589934592, sha256=SEED_IDENTITY, encoded_bytes=SEED.stat().st_size,
                        encoded_sha256=SEED_SHA, packed=True)
        require(meta == expected, f"candidate seed metadata differs: {meta}")
        xid, uuid = x.seed_volume_uuid(SEED.read_bytes())
        require(uuid == SEED_UUID, f"candidate APFS volume UUID differs: {uuid}")
        x.SEED = SEED
        x.SEED_SHA = SEED_SHA
        x.SEED_ENCODED_BYTES = SEED.stat().st_size
        x.SEED_IDENTITY = SEED_IDENTITY
        x.SEED_UUID = uuid
        x.SEED_XID = xid
        x.SEED_APSB_UUID = uuid
        x.DELTA_SEED = SEED.read_bytes()
        if "seed" in x.C.PINS:
            x.C.PINS["seed"] = SEED_SHA
        CandidateSeedLoader.modules.append(r35)


def run_packager(argv, kernel_sha256, *, enable_smp_entry):
    spec_from_file = importlib.util.spec_from_file_location
    CandidateSeedLoader.modules.clear()

    def with_candidate(name, location=None, **kwargs):
        if name == "r35_display_packager" and Path(location).resolve() == PARENT:
            kwargs["loader"] = CandidateSeedLoader(name, str(location))
        return spec_from_file(name, location, **kwargs)

    sys.argv = [str(SOURCE), *map(str, argv)]
    importlib.util.spec_from_file_location = with_candidate
    try:
        packager = SOURCE.read_text()
        require(packager.count(OLD_HID_PIN) == 1, "HID kernel pin anchor changed")
        packager = packager.replace(OLD_HID_PIN, 'HID_KERNEL = "' + kernel_sha256 + '"')
        if enable_smp_entry:
            anchor = '        inputs["ARGS"] += b" nuwa-hid-standin=1"'
            require(packager.count(anchor) == 1, "HID argument anchor changed")
            packager = packager.replace(anchor, anchor + f'\n        inputs["ARGS"] += {SMP_SUFFIX!r}')
        exec(compile(packager, str(SOURCE), "exec"), {"__name__": "__main__", "__file__": str(SOURCE)})
    finally:
        importlib.util.spec_from_file_location = spec_from_file
    require(len(CandidateSeedLoader.modules) == 1, "candidate seed was not bound exactly once")
    return CandidateSeedLoader.modules[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument("--kernel-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--audit", type=Path, help="optional second pass that re-extracts the package")
    parser.add_argument("--enable-smp-entry", action="store_true",
                        help="append only sheng-smp=1 to the pinned default-off SMP package")
    parser.add_argument("--baseline", type=Path)
    a = parser.parse_args()
    default_baseline = ENTRY_BASELINE if a.enable_smp_entry else BASELINE
    kernel, output, baseline = a.kernel.resolve(), a.output.resolve(), (a.baseline or default_baseline).resolve()
    audit = a.audit.resolve() if a.audit else None
    for path in (kernel, output, baseline, *([audit] if audit else [])):
        if (ROOT / "out").resolve() not in path.parents:
            parser.error(f"expected a path inside device out/: {path}")
    if output.exists() or (audit and audit.exists()):
        parser.error("--output and --audit must be new")
    if a.enable_smp_entry:
        require(a.kernel_sha256 == ENTRY_KERNEL_SHA, "entry mode requires the default-off observational SMP kernel")
    require(sha(kernel.read_bytes()) == a.kernel_sha256, "kernel SHA256 mismatch")
    require(sha(SOURCE.read_bytes()) == SOURCE_SHA, "display packager changed")
    require(sha(SEED.read_bytes()) == SEED_SHA, "SystemGroup seed changed")
    report = kernel.parent / "hid/final-audit.json"
    require(report.is_file() and json.loads(report.read_text()).get("kernel_sha256") == a.kernel_sha256,
            "kernel is not the audited HID final link")
    baseline_outer, baseline_fat, baseline_outside = split_build(baseline)
    baseline_sha = ENTRY_BASELINE_SHA if a.enable_smp_entry else BASELINE_SHA
    require(sha(baseline_outer) == baseline_sha, "baseline outer SHA256 mismatch")

    flags = ["--kernel", kernel, "--kernel-sha256", a.kernel_sha256,
             "--enable-display", "--board-window", "--enable-mg-reset-resume-only",
             "--enable-hid-standin"]
    r35 = run_packager([*flags, "--output", output], a.kernel_sha256, enable_smp_entry=a.enable_smp_entry)
    if audit:
        run_packager([*flags, "--output", audit, "--audit", output], a.kernel_sha256,
                     enable_smp_entry=a.enable_smp_entry)

    outer, fat, outside = split_build(output)
    require(outside == baseline_outside, "bytes outside the vendor ramdisk FAT changed")
    require(fat == (output / "payload.img").read_bytes(), "outer FAT differs from payload.img")
    require(len(fat) == len(baseline_fat), "payload FAT size changed")

    readback = (output / "outer-audit/outer-readback/EFI/UniXNU")
    args = xnu_args((readback / "unixnu.toml").read_bytes())
    baseline_config, baseline_adt, _ = extract_boot_inputs(baseline / "vendor_boot.img")
    baseline_args = xnu_args(baseline_config)
    if a.enable_smp_entry:
        require(baseline_args == EXPECTED_ARGS, "default-off SMP baseline args differ")
        require(args == baseline_args + SMP_SUFFIX, "args differ beyond appending sheng-smp=1")
    else:
        require(baseline_args.count(RESTART) == 1, "baseline does not carry the restart pair once")
        require(args == baseline_args.replace(RESTART, b""), "args differ beyond the restart pair")
        require(args == EXPECTED_ARGS, "args are not the pinned current-device set")
    tokens = args.split()
    for key in FORBIDDEN_KEYS:
        if a.enable_smp_entry and key == b"sheng-smp":
            continue
        require(not any(t == key or t.startswith(key + b"=") for t in tokens),
                f"forbidden argument present: {key!r}")
    for token in (b"sheng-data-persist=2", b"nuwa-lite=1", b"nuwa-mg-reset=1", b"boot-progress=2",
                  b"nuwa-hid-standin=1", b"build-tag=nuwa-r35"):
        require(tokens.count(token) == 1, f"expected once in args: {token!r}")

    # Re-extract from the produced image itself, not only from the packager's readback.
    direct, direct_adt, direct_fat = extract_boot_inputs(output / "vendor_boot.img")
    require(direct_fat == fat, "re-extracted FAT differs from payload.img")
    direct_args = xnu_args(direct)
    require(direct_args == args, "args re-extracted from vendor_boot.img differ")
    if a.enable_smp_entry:
        require(direct == baseline_config.replace(baseline_args, baseline_args + SMP_SUFFIX, 1),
                "boot config differs beyond appending sheng-smp=1")

    require(sha((readback / "Payloads/kernel.macho").read_bytes()) == a.kernel_sha256,
            "outer readback kernel differs from the requested SHA256")
    require(sha((readback / "Payloads/scratch-data.img").read_bytes()) == SEED_SHA,
            "outer readback seed differs")
    adt = r35.A
    tree = adt.parse(direct_adt)
    chosen = adt.properties(adt.find(tree, "/chosen"))
    require(chosen.get("display-scale") == bytes.fromhex("03000000"), "unexpected display-scale")
    record = json.loads((output / "record.json").read_text())
    chmh = chosen.get("boot-manifest-hash", b"").hex()
    require(chmh == record["chmh_hex"], "CHMH differs from the package record")
    if a.enable_smp_entry:
        original_chmh = adt.properties(adt.find(adt.parse(baseline_adt), "/chosen"))["boot-manifest-hash"]
        require(chmh != original_chmh.hex() and
                direct_adt == baseline_adt.replace(original_chmh, bytes.fromhex(chmh), 1),
                "rebound CHMH must be the only ADT change")
        states = {adt.properties(node)["name"].rstrip(b"\0").decode(): adt.properties(node)["state"]
                  for node in adt.find(tree, "/cpus")["children"]}
        require(states == {f"cpu{i}": b"running\0" if i == 0 else b"waiting\0" for i in range(8)},
                "unexpected /cpus state")
        method = adt.properties(adt.find(tree, "/psci"))["method"]
        require(method == b"smc\0", "unexpected /psci/method")
    cluster_bytes, _, free_clusters = r35.X.fat_clusters(fat)
    require(cluster_bytes * free_clusters >= 8388608, "FAT free space below 8 MiB")
    if audit:
        audit_fat = (audit / "actual-vendor-ramdisk.img").read_bytes()
        audited = json.loads((audit / "audit.json").read_text())
        require(audit_fat == fat and audited["outer_sha256"] == sha(outer),
                "separate audit disagrees with the package")

    print(f"kernel SHA-256: {a.kernel_sha256}")
    print(f"outer SHA-256: {sha(outer)}")
    print(f"CHMH SHA-384: {chmh}")
    print(f"FAT SHA-256: {sha(fat)}")
    print(f"FAT free bytes: {cluster_bytes * free_clusters}")
    print(f"args ({len(args)} bytes, {len(tokens)} tokens) SHA-256: {sha(args)}")
    print(direct_args.decode())
    if a.enable_smp_entry:
        for cpu, state in sorted(states.items()):
            print(f"/cpus/{cpu}/state: {state[:-1].decode()}")
        print(f"/psci/method: {method[:-1].decode()}")
    print("PACKAGE_VERIFY_DONE")


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    main()
