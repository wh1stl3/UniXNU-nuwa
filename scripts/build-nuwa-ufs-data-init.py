#!/usr/bin/env python3
"""Pin the existing nuwa recovery GPT and disposable artifacts, then build."""
import argparse
import hashlib
from pathlib import Path
import struct
import subprocess
import zlib


SEED = "3c81135b384d8e090521205f2d69b3c197521e6d03c63682419d021bf0f24e5e"
IDENTITY = "a106b0ce026771e221f578125e104a4854c2cbcda7c1b8390f6e056a47c63743"
FAT = "087c692478cd3060f34b62d3eb9575bde8f045816eccac52aa74edc51da5ab52"
OUTER = "6695da9842f4da4d26c1f028adc48f3ffb8f6f369420653492028a74bf362fa5"
GPT = {
    "primary_header": "5da0934e38031178980c684e86c495f7f838f675e03963461ea169284726a16c",
    "backup_header": "3cc5d9b00bf0236d8683d9d68fa7a2ddcbc25fb2415a9fed6d4d316450fc698d",
    "primary_entries": "6e97160f0943bbaaba43b8980e93caa779d1b2f5552d2184d7a422697406de69",
    "backup_entries": "6e97160f0943bbaaba43b8980e93caa779d1b2f5552d2184d7a422697406de69",
}


def check(data, sha, label, size=None):
    if (size is not None and len(data) != size) or hashlib.sha256(data).hexdigest() != sha:
        raise SystemExit(f"refused: {label} identity")
    return data


def require(ok, label):
    if not ok:
        raise SystemExit(f"refused: {label}")


def make_header(args):
    z = check((args.init / "prepare.bin").read_bytes(),
              "6bdcd73dcf47f64038afbce5c14c7fb2817da9e2074a2597acb8852898e6c3d2",
              "prepare", 770 * 4096)
    require(not any(z), "zero prepare")
    sb = check((args.init / "commit-sb0.bin").read_bytes(),
               "b227e878961df9b0d30ccdd73663206e396d3d2a0466141377439d11f74a86f5",
               "SB0", 4096)
    require(sb[:8] == b"NUWAXSB3" and sb[32:64] == bytes.fromhex(IDENTITY), "SB0 seed binding")
    outer = check((args.package / "vendor_boot.img").read_bytes(), OUTER, "outer", 100663296)
    fat_path = args.package / "readback-fat.img"
    fat = check(fat_path.read_bytes(), FAT, "readback FAT", 67108864)
    require(outer[4096:4096 + len(fat)] == fat, "outer FAT binding")
    seed = subprocess.check_output(["mcopy", "-i", str(fat_path),
                                    "::/EFI/UniXNU/Payloads/scratch-data.img", "-"])
    check(seed, SEED, "packed seed")
    # Exact encoded SHA binds the eight extents and the earlier audited logical
    # SHNGSEED2 identity; do not reinterpret the packed filesystem on recovery.
    gpt = {n: check((args.gpt / f"sda-{n.replace('_', '-')}.bin").read_bytes(), h, n, 4096)
           for n, h in GPT.items()}
    for copy, there, other, table in [
        ("primary", 1, 61850623, 2), ("backup", 61850623, 1, 61850619)
    ]:
        header, entries = gpt[copy + "_header"], gpt[copy + "_entries"]
        signature, version, size, crc, reserved = struct.unpack_from("<8sIIII", header)
        require((signature, version, size, reserved) == (b"EFI PART", 0x10000, 92, 0)
                and zlib.crc32(header[:16] + bytes(4) + header[20:size]) == crc, copy + " header")
        require(struct.unpack_from("<QQQQ16xQIII", header, 24)
                == (there, other, 6, 61850618, table, 32, 128, zlib.crc32(entries)), copy + " table")
    entries = gpt["primary_entries"]
    require(entries == gpt.pop("backup_entries")
            and gpt["primary_header"][56:72] == gpt["backup_header"][56:72], "GPT agreement")
    entry = entries[31 * 128:]
    require(all(any(entry[i:i + 16]) for i in (0, 16))
            and struct.unpack_from("<QQ", entry, 32) == (3110976, 61850618)
            and entry[56:].decode("utf-16le").rstrip("\0") == "userdata"
            and 3110976 <= 57393401 < 57393401 + 770 <= 61588475 <= 61850619,
            "userdata window")
    return "".join(f"static const unsigned char {name}[4096] = {{\n"
                   + "".join("    " + ",".join(f"0x{x:02x}" for x in data[i:i+16]) + ",\n"
                             for i in range(0, len(data), 16)) + "};\n"
                   for name, data in {**gpt, "sb0": sb}.items())


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("init", "gpt", "package", "output"):
        p.add_argument("--" + name, type=Path, required=True)
    a = p.parse_args()
    header = make_header(a)
    a.output.mkdir(parents=True, exist_ok=False)
    (a.output / "nuwa-data-pins.h").write_text(header, encoding="ascii")
    src = Path(__file__).with_name("nuwa-ufs-data-init.c")
    base = ["-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", "-I", str(a.output), str(src)]
    for cc, extra, name in [
        ("aarch64-linux-gnu-gcc", ["-static", "-march=armv8-a"], "nuwa-data-init"),
        ("cc", ["-DNUWA_HOST_FIXTURE"], "nuwa-data-init-host"),
        ("cc", [], "nuwa-data-init-cli-host"),
    ]:
        binary = a.output / name
        subprocess.run([cc, *extra, *base, "-o", str(binary)], check=True)
        print(hashlib.sha256(binary.read_bytes()).hexdigest(), name)


if __name__ == "__main__":
    main()
