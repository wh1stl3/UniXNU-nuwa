#!/usr/bin/env python3
"""Package the pinned SystemGroup/HID resume-only control (host only)."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/build-ufs-apfs-root-chmh-r35.py"
SOURCE_SHA = "b5ce56a1784ec1395efa86f32468e8772da516b4b8e4c5e0f6535021c90537e7"
HID_KERNEL = "5ba1be16d8e83c35405ec8d7595e16132be41a22932437e4b23ae90d794ce798"
TEXT_FIXUP_KERNEL = "e161a629690a503d63a1f4a346b3e1f488df6f09ecfb375e51d7e5a62e7e0c5e"
SEED_SHA = "692355638b31d347ced5983a5910491f0556156f79675c2e371ebe9987683247"
SEED_IDENTITY = "fd554672b1b97df139e533e2d8e74964f6351963d55e4a4483abcec654f1a172"
SEED_UUID = "B0E0F71F-A265-4038-8F5C-6D3632859DEF"
SEED_BYTES = 2121888
# Byte-for-byte pin: vendor-boot-hid-stage/unixnu.toml with the two
# nuwa-sb-restart tokens removed (917 B). The reference file is 963 B / 91bb0d9e.
CONFIG_SHA = "0d9a968e9df888c1e8bebe98b023267e9b7ade6239c3f4f9c74b1d96e6189d41"
DISPLAY_SCALE = (3).to_bytes(4, "little")
ARGS = (b"-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid"
        b" boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 aks=1 disable-watchdogd=1"
        b" build-tag=nuwa-r35 boot-progress-scale=3 sheng-data-persist=2 sheng-log-reserve=1024"
        b" offline-mobile-graphics-load=1 offline-legacy-register=1 offline-legacy-gop=1"
        b" offline-legacy-pm=1 offline-legacy-phase=4 offline-legacy-validate=1"
        b" offline-legacy-transfer=1 offline-legacy-cpu-present=1 nuwa-lite=1 nuwa-mg-reset=1"
        b" nuwa-hid-standin=1")

# 20H392 dyld shared cache fixup, bare hex (make-nuwa-adt and cs_text_fixup_parse
# both reject a 0x prefix). The resume-only reference package has no such property.
TEXT_FIXUP_ENTRY = "dyld_shared_cache_arm64.13,1cd5a9c,684a19d0004d47f9,c0035fd6004d47f9"
TEXT_FIXUPS = TEXT_FIXUP_ENTRY.encode() + b"\0"


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def check_args(args, *, xnu=True):
    tokens = args.split()
    if any(t.split("=", 1)[0] == "sheng-data-reset" for t in tokens):
        raise ValueError("Resume-only args contain sheng-data-reset")
    if xnu:
        for required in ("nuwa-hid-standin=1", "nuwa-mg-reset=1", "sheng-data-persist=2"):
            key = required.split("=", 1)[0]
            if [t for t in tokens if t.split("=", 1)[0] == key] != [required]:
                raise ValueError(f"Resume-only args require exactly one {required}")
        # The periodic SpringBoard kill is optional: absent means disabled, but a
        # present value must be the canonical one.
        for key, value in (("nuwa-sb-restart", "400"),
                           ("nuwa-sb-restart-every", "180")):
            got = [t for t in tokens if t.split("=", 1)[0] == key]
            if got and got != [f"{key}={value}"]:
                raise ValueError(f"Optional {key} must be exactly one {key}={value}")


def check_config(config):
    for entry in tomllib.loads(config.decode())["entry"]:
        check_args(entry.get("args", ""), xnu=entry["id"] == "xnu")
    if sha(config) != CONFIG_SHA:
        raise ValueError("unixnu.toml differs from the pinned HID-stage baseline")


def check_chosen(props, *, text_fixup):
    if [p[2] for p in props if p[0] == "display-scale"] != [DISPLAY_SCALE]:
        raise ValueError("/chosen/display-scale must be one u32 3")
    got = [p[2] for p in props if p[0] == "text-fixups"]
    if text_fixup:
        if got != [TEXT_FIXUPS]:
            raise ValueError("/chosen/text-fixups must be the one pinned 20H392 entry")
    elif got:
        raise ValueError("Resume-only control must not contain /chosen/text-fixups")


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument("--kernel-sha256", required=True)
    parser.add_argument("--enable-display", action="store_true", required=True)
    parser.add_argument("--enable-hid-standin", action="store_true", required=True)
    parser.add_argument("--enable-mg-reset-resume-only", action="store_true", required=True)
    parser.add_argument("--board-window", action="store_true", required=True)
    parser.add_argument("--systemgroup-seed", type=Path, required=True)
    parser.add_argument("--text-fixup", action="store_true",
                        help="add the pinned 20H392 /chosen/text-fixups entry and require the rebuilt kernel")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--audit", type=Path)
    a = parser.parse_args()
    kernel = a.kernel.resolve()
    seed = a.systemgroup_seed.resolve()
    output = a.output.resolve()
    audit = a.audit.resolve() if a.audit else None
    for path in (kernel, seed, output, *([audit] if audit else [])):
        if (ROOT / "out").resolve() not in path.parents:
            parser.error(f"expected a path inside device out/: {path}")
    if output.exists():
        parser.error("--output must be new")
    blob = kernel.read_bytes()
    expected_kernel = TEXT_FIXUP_KERNEL if a.text_fixup else HID_KERNEL
    if sha(blob) != a.kernel_sha256 or a.kernel_sha256 != expected_kernel:
        parser.error("resume-only profile requires the pinned audited kernel")
    report = kernel.parent / "hid/final-audit.json"
    if not report.is_file() or json.loads(report.read_text()).get("kernel_sha256") != a.kernel_sha256:
        parser.error("HID ON profile requires the matching final-link audit")
    seed_blob = seed.read_bytes()
    if len(seed_blob) != SEED_BYTES or sha(seed_blob) != SEED_SHA:
        parser.error("SystemGroup seed must match the HID-stage baseline")
    if sha(SOURCE.read_bytes()) != SOURCE_SHA:
        raise ValueError("Pinned r35 packager changed")
    check_args(ARGS.decode())

    sys.argv = [str(SOURCE), "--output", str(output)]
    if audit:
        sys.argv.extend(("--audit", str(audit)))
    spec = importlib.util.spec_from_file_location("r35_display_packager", SOURCE)
    r35 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(r35)
    x = r35.X
    meta = x.PK.inspect(seed)[0]
    if meta != dict(bytes=8589934592, sha256=SEED_IDENTITY, encoded_bytes=SEED_BYTES,
                    encoded_sha256=SEED_SHA, packed=True):
        raise ValueError("SystemGroup packed seed metadata differs from baseline")
    xid, uuid = x.seed_volume_uuid(seed_blob)
    if uuid != SEED_UUID:
        raise ValueError("SystemGroup seed APFS UUID differs from baseline")
    x.SEED, x.SEED_SHA, x.SEED_ENCODED_BYTES = seed, SEED_SHA, SEED_BYTES
    x.SEED_IDENTITY, x.SEED_XID, x.SEED_APSB_UUID = SEED_IDENTITY, xid, uuid
    x.DELTA_SEED = seed_blob
    # Only replace an existing pin: the base parent-input check iterates PINS
    # against a parent dict that has no seed member.
    if "seed" in x.C.PINS:
        x.C.PINS["seed"] = SEED_SHA

    inputs = dict(KERNEL=kernel, KERNEL_BYTES=len(blob), KERNEL_SHA=a.kernel_sha256,
                  PROFILE="nuwa-r35-display-systemgroup-hid-resume-only-control"
                          + ("-textfixup" if a.text_fixup else ""), ARGS=ARGS)
    for module in (r35, x, r35.M):
        vars(module).update(inputs)

    def check_inputs(actual):
        check_config(actual["config"])
        return r35.check_inputs(actual, resume_only=True)

    r35.M.check_inputs = check_inputs
    size = int(tomllib.loads((ROOT / "board.toml").read_text(encoding="utf-8"))
               ["payload"]["adt"]["owned_memory_size"], 0)
    if size != 0x130000000:
        raise ValueError("Resume-only control requires the 4.75 GiB baseline window")
    previous = x.derived
    adt = r35.A

    def derived(parent, digest):
        tree = adt.parse(previous(parent, digest))
        props = adt.find(tree, "/chosen")["properties"]
        matches = [i for i, p in enumerate(props) if p[0] == "darwinboot-memory-size"]
        if len(matches) != 1 or len(props[matches[0]][2]) != 8:
            raise ValueError("parent ADT window is not a unique u64")
        i = matches[0]
        props[i] = (props[i][0], props[i][1], size.to_bytes(8, "little"))
        if adt.properties(adt.find(tree, "/product")).get("artwork-scale-factor") != DISPLAY_SCALE:
            raise ValueError("/product/artwork-scale-factor is not u32 3")
        props.append(("display-scale", 0, DISPLAY_SCALE))
        if a.text_fixup:
            if any(p[0] == "text-fixups" for p in props):
                raise ValueError("parent already has /chosen/text-fixups")
            props.append(("text-fixups", 0, TEXT_FIXUPS))
        check_chosen(props, text_fixup=a.text_fixup)
        return adt.encode(tree)

    x.derived = x.C.derived = derived
    previous_audit = r35.M.audit_image

    def audit_image(blob, selected, actual, material, ev, stock, work):
        report = previous_audit(blob, selected, actual, material, ev, stock, work)
        readback = work / "outer-readback/EFI/UniXNU"
        check_config((readback / "unixnu.toml").read_bytes())
        payloads = readback / "Payloads"
        tree = adt.parse((payloads / "kernel.macho.adt").read_bytes())
        check_chosen(adt.find(tree, "/chosen")["properties"], text_fixup=a.text_fixup)
        if sha((payloads / "scratch-data.img").read_bytes()) != SEED_SHA:
            raise ValueError("Outer readback SystemGroup seed mismatch")
        return report

    r35.M.audit_image = audit_image
    r35.M.main()
    if a.text_fixup and not audit:
        direct_readback(output, adt)


def direct_readback(output, adt):
    """Extract the shipped vendor_boot ramdisk itself and re-check the profile."""
    outer = (output / "vendor_boot.img").read_bytes()
    if outer[:8] != b"VNDRBOOT":
        raise ValueError("vendor_boot magic changed")
    page, fat_size = struct.unpack_from("<I8xI", outer, 12)
    if (page, fat_size) != (4096, 67108864):
        raise ValueError(f"unexpected vendor_boot geometry: {page}, {fat_size}")
    fat = outer[page:page + fat_size]
    if sha(fat) != sha((output / "payload.img").read_bytes()):
        raise ValueError("vendor_boot ramdisk differs from payload.img")
    work = output / "direct-readback"
    work.mkdir()
    (work / "fat.img").write_bytes(fat)
    env = dict(os.environ, MTOOLS_SKIP_CHECK="1")
    wanted = {
        "config": "EFI/UniXNU/unixnu.toml",
        "adt": "EFI/UniXNU/Payloads/kernel.macho.adt",
        "seed": "EFI/UniXNU/Payloads/scratch-data.img",
    }
    for name, dest in wanted.items():
        subprocess.run(["mcopy", "-i", str(work / "fat.img"), "::/" + dest,
                        str(work / name)], check=True, env=env)
    config = (work / "config").read_bytes()
    check_config(config)
    tree = adt.parse((work / "adt").read_bytes())
    node = adt.find(tree, "/chosen")
    check_chosen(node["properties"], text_fixup=True)
    chosen = adt.properties(node)
    seed = (work / "seed").read_bytes()
    if sha(seed) != SEED_SHA:
        raise ValueError("direct vendor_boot seed mismatch")
    args, = [e["args"] for e in tomllib.loads(config.decode())["entry"] if e["id"] == "xnu"]
    print("args:", args)
    print("display-scale:", chosen["display-scale"].hex())
    print("text-fixups:", chosen["text-fixups"])
    print("seed sha256:", sha(seed))


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    main()
