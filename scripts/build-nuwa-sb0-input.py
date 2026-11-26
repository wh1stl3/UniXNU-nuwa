#!/usr/bin/env python3
"""Build a standalone, no-grant, no-storage EFI input probe for the exact r4 FD."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import uuid
import zlib

ROOT = Path(__file__).resolve().parents[1]
BOOT = "692cfcca51af81230fecbba15425cf598182fbe53abb362b6046dec0f24dc2e5"
FD = "85bb651a746304343f5baf0d2e1f158405b4054e7886a2815e568fde59fd9256"
W = "810cdd214aeaef507998d6a15e79100ee97387292b45ec4762a9f9225065f247"
SEED = "a106b0ce026771e221f578125e104a4854c2cbcda7c1b8390f6e056a47c63743"
SB0 = "b227e878961df9b0d30ccdd73663206e396d3d2a0466141377439d11f74a86f5"


def read_pin(path, pin):
    blob = path.read_bytes()
    if hashlib.sha256(blob).hexdigest() != pin:
        raise SystemExit(f"{path}: input SHA-256 does not match r4 SB0 probe pin")
    return blob


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("r4-boot", "w-outer", "sb0", "basecore", "out"):
        p.add_argument(f"--{name}", type=Path, required=True)
    a = p.parse_args()
    out = a.out.resolve()
    if ROOT / "out" not in out.parents:
        p.error("--out must be a new directory under device out/")
    boot = read_pin(a.r4_boot, BOOT)
    fd = zlib.decompress(boot[4096:4096 + 1483112], wbits=31)[192:]
    if len(fd) != 3145728 or hashlib.sha256(fd).hexdigest() != FD:
        raise SystemExit("r4 FD hash mismatch")
    read_pin(a.w_outer, W)
    sb0 = read_pin(a.sb0, SB0)
    if len(sb0) != 4096 or sb0[:8] != b"NUWAXSB3" or bytes.fromhex(SEED) not in sb0:
        raise SystemExit("fixed SB0 page and seed do not match")
    out.mkdir()
    (out / "Sb0InputBinding.h").write_text(
        f'#define SB0_W_OUTER L"{W}"\n#define SB0_SEED_ID L"{SEED}"\n#define SB0_PAYLOAD L"{SB0}"\n')
    includes = a.basecore.resolve() / "MdePkg/Include"
    src = ROOT / "package/nuwa-sb0-input/Probe.c"
    obj = out / "Probe.obj"
    efi = out / "SB0-INPUT-NO-GRANT.efi"
    commands = [
        ["clang", "--target=aarch64-pc-windows-msvc", "-ffreestanding", "-fshort-wchar",
         "-fno-stack-protector", "-O2", "-Wall", "-Wextra", "-Werror",
         "-I", includes, "-I", includes / "AArch64", "-I", out, "-c", src, "-o", obj],
        ["lld-link", "/machine:arm64", "/entry:EfiMain", "/subsystem:efi_application",
         "/nodefaultlib", "/timestamp:0", f"/out:{efi}", obj],
    ]
    for cmd in commands:
        subprocess.run(cmd, check=True)
    pe = subprocess.check_output(["llvm-readobj", "--file-headers", "--coff-imports", efi], text=True)
    (out / "pe.txt").write_text(pe)
    assert "IMAGE_FILE_MACHINE_ARM64" in pe and "IMAGE_SUBSYSTEM_EFI_APPLICATION" in pe
    assert re.search(r"ImportTableRVA: 0x0\s+ImportTableSize: 0x0", pe)
    assert re.search(r"CertificateTableRVA: 0x0\s+CertificateTableSize: 0x0", pe)
    dis = subprocess.check_output(["llvm-objdump", "-d", efi], text=True)
    (out / "disasm.txt").write_text(dis)
    blob = efi.read_bytes()
    # No block/disk IO, file system, local authorization channel or SB0
    # bytes in this application. EFI PE has no external import table.
    for forbidden_efi_guid in ("964e5b21-6459-11d2-8e39-00a0c969723b",  # BlockIo
                               "ce345171-ba0b-11d2-8e4f-00a0c969723b",  # DiskIo
                               "964e5b22-6459-11d2-8e39-00a0c969723b"): # SimpleFileSystem
        assert uuid.UUID(forbidden_efi_guid).bytes_le not in blob
    assert sb0 not in blob
    report = dict(efi_sha256=hashlib.sha256(blob).hexdigest(), size=len(blob),
                  boot_sha256=BOOT, fd_sha256=FD, w_outer_sha256=W, seed_identity=SEED,
                  page_sha256=SB0, target={"lun": 0, "lba": 57393401, "bytes": 4096},
                  admission_grant=False, device_release=False,
                  commands=[[str(arg) for arg in cmd] for cmd in commands])
    (out / "audit.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
