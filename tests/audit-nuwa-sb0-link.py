#!/usr/bin/env python3
"""Audit the existing NEON link/package and the two SB0 fixture links offline."""
import argparse
import hashlib
from pathlib import Path
import re
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]
KERNEL = "48637103823e84726de1654c07629118d6b63021340cc88d58a8d15d62196f72"
OUTER = "18fa4941696667d1813442022ea71fc48e4c414b1abadb1caf73774fcc76202a"
MARKERS = ("NuwaSb0Fixture", "NUWA_SB0_HOST_FIXTURE", "testSb0Experiment", "initialSuperblock")


def tool(*args):
    return subprocess.check_output(args)


def absent(data):
    for mark in MARKERS:
        assert mark.encode() not in data, mark


def main(build, review):
    old_tree = build.parents[1]
    refs = old_tree / "package/nuwa-data-write"
    local = ROOT / "package/nuwa-data-write"
    stage = build / "nuwa-data-provider"
    for name in ("NativeUfs.cpp", "CombinedRead.h", "PreservedNop.h", "RootCommands.h"):
        contents = (stage / name).read_bytes()
        absent(contents)
        print(f"staged {name} sha256={hashlib.sha256(contents).hexdigest()}")
        if name != "NativeUfs.cpp":
            for mode in ("default", "enabled"):
                rebased = (review / mode / name).read_text()
                assert rebased.replace(f'#include "{local}/', f'#include "{refs}/') == (
                    stage / name).read_text(), (mode, name)
    for name in ("KernelPort.inc", "Gate.h", "Provider.h", "RetainedRead.inc", "RetainedWrite.inc",
                 "RetainedResponse.inc", "Descriptor.h", "RetainedDesc.inc", "Neon.h", "Reinit.h"):
        a, b = refs / name, local / name
        assert a.read_text() == b.read_text(), name
        absent(a.read_bytes())
    port = (local / "KernelPort.inc").read_text()
    assert "Provider<CandidatePort, false>" in port and "fuaProvenLocked() { return false; }" in port
    for name in ("ramblock-argv.json", "native-link-argv.json", "native-link.map"):
        absent((build / name).read_bytes())
    for path in (stage / "NativeUfs.o", build / "NativeRamBlock.o", build / "native.macho"):
        absent(tool("llvm-nm", "-C", path))
    off = review / "default/test-retained-response"
    on = review / "enabled/test-retained-response"
    absent(tool("llvm-nm", "-C", off))
    assert b"testSb0Experiment()" in tool("llvm-nm", "-C", on)
    print("PASS staged transport unchanged except fixture include root; experiment only in enabled link")

    kernel = build / "kernel.macho"
    symbols = tool("llvm-nm", "-C", kernel)
    absent(symbols)
    assert b"RetainedWritePort::" not in symbols
    for name, expected in {
        "_native_ufs_store_write": {"_PE_parse_boot_argn", "_lck_mtx_lock", "_lck_mtx_unlock"},
        "_native_ufs_store_sync": {"_PE_parse_boot_argn"},
        "_native_ufs_log_write": set(),
        "_native_ufs_export_write": set(),
        "_native_ufs_log_sync": set(),
    }.items():
        code = tool("llvm-objdump", "-d", f"--disassemble-symbols={name}", kernel).decode()
        assert f"<{name}>:" in code, name
        calls = set(re.findall(r"\bbl\s+0x[0-9a-f]+\s+<([^>]+)>", code))
        assert calls == expected and not re.search(r"\b(?:br|blr|b)\s", code), name
        assert re.search(r"\bmov\s+w0, #0\b", code) and len(re.findall(r"\bret\b", code)) == 1, name
        (review / f"{name}.disasm").write_text(code)
    print("PASS existing linked write/sync entries: no command path, return zero")

    baseline = build.parent / "nuwa-ufs-neon-20261126-build-r2/kernel.macho"
    package = build.parent / "nuwa-ufs-neon-20261126-package"
    boot = package / "vendor_boot.img"
    binary = kernel.read_bytes()
    assert binary == baseline.read_bytes()
    assert hashlib.sha256(binary).hexdigest() == KERNEL
    outer = boot.read_bytes()
    assert hashlib.sha256(outer).hexdigest() == OUTER and outer[:8] == b"VNDRBOOT"
    _, page, _, _, fat_size = struct.unpack_from("<5I", outer, 8)
    fat = package / "readback-fat.img"
    assert outer[page:page + fat_size] == fat.read_bytes() == (package / "payload.img").read_bytes()
    assert binary == tool("mcopy", "-i", fat, "::/EFI/UniXNU/Payloads/kernel.macho", "-")
    absent(binary)
    print(f"PASS existing kernel r2=r3=outer FAT member: {KERNEL}")
    print(f"PASS existing outer header/FAT readback byte identity: {OUTER}; no new package")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("build", type=Path)
    parser.add_argument("review", type=Path)
    args = parser.parse_args()
    main(args.build.resolve(), args.review.resolve())
