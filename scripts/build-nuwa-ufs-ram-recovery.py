#!/usr/bin/env python3
"""Build an unbound RAM PID 1 review payload; never emit a flashable image."""
import argparse
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys


STOCK = {
    "boot.img": "594ff64b1adf14abb54b433ced9e6942b8148547d8ce35235be6baf5caa7b10c",
    "vendor_boot.img": "493ca426964adabb195a00ded4ff49793bc7efd5d7bea2a567bcfd0c970a8dad",
    "init_boot.img": "4da48a59d20c0deb74a9f0d712c329b62223f5e77e84505e12fa1ff3ba73a8a4",
    "dtbo.img": "c5dd80b3846b725aabb3df5ba4cfc8c869af565235e4e29a4e7b8c7f5e0ca1fb",
    "recovery.img": "4bc16c42d75afc4959bd659e2d2973daf4709f36df8e08aa3a4459f1f9a7340e",
}
BC6B = "bc6b688320fe9d1b41c3294c3ec84254e8c0619ded4068d71ce024729c74f55c"
HERE = Path(__file__).resolve().parent


def sha(data):
    return hashlib.sha256(data).hexdigest()


def pinned(path, digest):
    data = path.read_bytes()
    if sha(data) != digest:
        raise SystemExit(f"refused input hash: {path.name}")
    return data


def header(image):
    if image[:8] != b"ANDROID!" or struct.unpack_from("<I", image, 40)[0] != 4:
        raise ValueError("boot-v4 identity")
    k, r, os_version, h = struct.unpack_from("<4I", image, 8)
    cmdline = image[44:1580].split(b"\0", 1)[0].decode("ascii")
    offset = 4096 + (k + 4095) // 4096 * 4096
    return dict(kernel=k, ramdisk=r, header=h, os_version=os_version, offset=offset,
                cmdline=cmdline, avb_footer=image[-64:-60] == b"AVBf")


def members(compressed):
    blob = subprocess.check_output(["lz4", "-dc"], input=compressed)
    entries, cursor = {}, 0
    while blob[cursor:cursor+6] == b"070701":
        h = [int(blob[i:i+8], 16) for i in range(cursor+6, cursor+110, 8)]
        mode, size, count = h[1], h[6], h[11]
        name = blob[cursor+110:cursor+109+count].decode()
        cursor = (cursor + 110 + count + 3) & ~3
        if name == "TRAILER!!!":
            if any(blob[cursor:]):
                raise ValueError("unparsed nonzero CPIO tail")
            return entries
        if name in entries or name.startswith("/") or ".." in Path(name).parts:
            raise ValueError(f"unsafe/duplicate CPIO entry: {name}")
        entries[name] = (mode, blob[cursor:cursor+size])
        cursor = (cursor + size + 3) & ~3
    raise ValueError("incomplete CPIO")


def ramdisk(image):
    h = header(image)
    return members(image[h["offset"]:h["offset"] + h["ramdisk"]])


def init_record(entries):
    row = entries.get("init")
    if not row:
        return None
    mode, data = row
    return {"mode": oct(mode), "sha256": sha(data),
            "symlink": data.decode() if mode & 0o170000 == 0o120000 else None}


def dtbo_records(image):
    magic, total, head, width, count, first, page, version = struct.unpack_from(">8I", image)
    if (magic != 0xD7B7AB1E or head != 32 or width != 32 or first < head
            or first + count * width > total or total > len(image)):
        raise ValueError("DTBO table geometry")
    records = []
    for i in range(count):
        n, offset, ident, rev, *custom = struct.unpack_from(">8I", image, first + i * width)
        if offset < first + count * width or offset + n > total:
            raise ValueError("DTBO entry geometry")
        records.append({"index": i, "id": ident, "rev": rev, "custom": custom,
                        "sha256": sha(image[offset:offset+n])})
    return {"version": version, "page": page, "records": records, "selected": None}


def boot_audit(a):
    sys.path.insert(0, str(a.unixnu / "scripts"))
    from unixnu.vendor_boot import parse

    d = {name: pinned(a.stock / name, digest) for name, digest in STOCK.items()}
    recovery = pinned(a.bc6b, BC6B)
    vendor = parse(d["vendor_boot.img"])
    vint = members(vendor["ramdisk"])
    init_boot = ramdisk(d["init_boot.img"])
    current = ramdisk(recovery)
    k = header(d["boot.img"])["kernel"]
    kernel = d["boot.img"][4096:4096 + k]
    conf = gzip.decompress(kernel.split(b"IKCFG_ST", 1)[1].split(b"IKCFG_ED", 1)[0]).decode()
    selected = [s for s in conf.splitlines()
                if re.search(r"\bCONFIG_(?:MTD|PSTORE_BLK|PSTORE_RAM|DM_INIT|DEVTMPFS|UEVENT_HELPER|SCSI_UFS_QCOM|SCSI_UFSHCD|SCSI_UFS_BSG|INPUT_EVDEV|KEYBOARD_GPIO|MODULE_SIG_FORCE|USB_CONFIGFS_F_FS|USB_CONFIGFS_MASS_STORAGE)\b", s)]
    cmd = a.observed_cmdline.read_text().split()
    wanted = [arg for arg in cmd if arg.startswith(
        ("rdinit=", "init=", "block2mtd.", "mtdoops.dump_oops=", "dm-mod.create="))]
    deps = vint["lib/modules/modules.dep"][1].decode()
    roots = ("/lib/modules/ufs_qcom.ko", "/lib/modules/phy-qcom-ufs-qmp-v4-kalama.ko",
             "/lib/modules/dwc3-msm.ko", "/lib/modules/pm8941-pwrkey.ko")
    graph = {n: r.split() for n, r in (line.split(":", 1) for line in deps.splitlines())}
    todo, seen = list(roots), set()
    while todo:
        n = todo.pop()
        if n not in seen:
            seen.add(n)
            todo.extend(graph[n])
    return {
        "flashable": False,
        "images": {**STOCK, "bc6b": BC6B},
        "boot_headers": {**{n: header(d[n]) for n in ("boot.img", "init_boot.img", "recovery.img")},
                         "bc6b": header(recovery)},
        "overlay_init": {"init_boot": init_record(init_boot), "vendor": init_record(vint),
                         "bc6b": init_record(current)},
        "dtbo": dtbo_records(d["dtbo.img"]),
        "vendor_fragment_types": [struct.unpack_from("<I", vendor["table"], i * vendor["table_entry"] + 8)[0]
                                  for i in range(vendor["table_count"])],
        "kernel_config": selected,
        "kernel_contains_observed_release": b"5.15.215-KylinKernel-260925-Release" in kernel,
        "observed_filtered_cmdline": wanted,
        "vendor_module_hard_deps_only_NOT_a_load_list": {n: sha(vint[n[1:]][1]) for n in sorted(seen)},
        "unbound": [
            "Recovery ABL ramdisk order, effective rdinit precedence, and AVB acceptance unproven",
            "DTBO entry actually selected by ABL unbound",
            "Module hard deps are not proof of supplier/softdep/firmware or no other partition I/O",
            "Kernel scan and early producer boundary not closed",
        ],
    }


def build(a):
    report = boot_audit(a)
    spec = importlib.util.spec_from_file_location("pins", HERE / "build-nuwa-ufs-data-init.py")
    pins = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pins)
    pinned_header = pins.make_header(a)
    a.output.mkdir(parents=True, exist_ok=False)
    (a.output / "nuwa-data-pins.h").write_text(pinned_header, encoding="ascii")
    opts = ["-std=c11", "-Wall", "-Wextra", "-Werror", "-O2", "-I", str(a.output),
            f'-DNUWA_RAM_RUN_ID="{a.run_id}"', f"-DNUWA_RAM_ARMED={int(a.arm_for_review)}",
            "-DNUWA_RAM_PID1", str(HERE / "nuwa-ufs-data-init.c")]
    elf = a.output / "nuwa-recovery-init"
    subprocess.run(["aarch64-linux-gnu-gcc", "-static", "-march=armv8-a", *opts, "-o", elf], check=True)
    subprocess.run(["cc", "-DNUWA_RAM_EXPORT_FIXTURE", "-Wno-unused-function", *opts,
                    "-o", a.output / "export-fixture"], check=True)
    # Allow review of both init entrypoints, not a boot/recovery header.
    stage = a.output / "fragment"
    stage.mkdir()
    for name in ("init", "nuwa-recovery-init"):
        p = stage / name
        p.write_bytes(elf.read_bytes())
        p.chmod(0o755)
        os.utime(p, (0, 0))
    cpio = subprocess.check_output(["cpio", "-o", "--quiet", "--format=newc", "--reproducible", "--owner=0:0"],
                                   cwd=stage, input=b"init\nnuwa-recovery-init\n")
    compressed = subprocess.check_output(["lz4", "-l", "-12", "-c"], input=cpio)
    if any(data != elf.read_bytes() for _, data in members(compressed).values()):
        raise ValueError("fragment readback")
    (a.output / "UNBOUND-pid1-fragment.cpio.lz4").write_bytes(compressed)
    report.update(run_id=a.run_id, armed_for_review=a.arm_for_review,
                  elf_sha256=sha(elf.read_bytes()), fragment_sha256=sha(compressed))
    (a.output / "audit.json").write_text(json.dumps(report, indent=2) + "\n", encoding="ascii")
    print(json.dumps({k: report[k] for k in ("flashable", "elf_sha256", "fragment_sha256", "unbound")}, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("stock", "bc6b", "unixnu", "observed-cmdline", "init", "gpt", "package", "output"):
        p.add_argument("--" + name, type=Path, required=True)
    p.add_argument("--run-id", required=True)
    p.add_argument("--arm-for-review", action="store_true")
    args = p.parse_args()
    if not re.fullmatch("[0-9a-f]{32}", args.run_id):
        p.error("run ID must be 32 lowercase hex characters")
    build(args)
