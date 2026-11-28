#!/usr/bin/env python3
"""Exercise the retained profile's staged encoder and the upstream v1 overlay."""
import argparse
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def section(source, signature, closing):
    lines = source.splitlines()
    start, = (i for i, line in enumerate(lines) if line.startswith(signature))
    return "\n".join(lines[start:lines.index(closing, start) + 1]) + "\n"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("base", type=Path)
    p.add_argument("build", type=Path)
    cases = ("reset", "retained", "wrong-header-seed", "wrong-boot-seed",
             "legacy-v3", "legacy-disposable", "overlap-root", "overlap-log",
             "sync-scsi", "sync-timeout", "sync-unowned", "sync-header")
    p.add_argument("--case", choices=cases)
    a = p.parse_args()
    build = a.build.resolve()
    stage = build / "nuwa-retained-persist"
    ufs = (stage / "NativeUfs.cpp").read_text()
    encoder = (stage / "CombinedRead.h").read_text()
    assert "/RetainedPersist.inc\"" in ufs and "KernelPort.inc" not in ufs
    assert "dataProvider" not in ufs and "WriteVolatile" not in encoder
    assert not any(x in (build / "ramblock-argv.json").read_text()
                   for x in ("NUWA_DATA_CANDIDATE", "NUWA_DISPOSABLE_DATA"))
    root = (stage / "RootCommands.h").read_text()
    assert root.index("IOLockLock(gHost.lock)") < root.index("retainedReadLocked(lba, blocks)") < root.index("IOLockUnlock(gHost.lock)")
    ram = (ROOT / "package/nuwa-ramblock/NativeRamBlock.cpp").read_text()
    assert "overlay.open(ops, pages, seedHash, mode == 1, overlayBits, discardRequested())" in ram
    deps = build.parent / "nuwa-ufs-apfs-root-integration-20261114/run-r5-visible-candidate/source"
    with tempfile.TemporaryDirectory(prefix="nuwa-v1-retained-") as tmp:
        tmp = Path(tmp)
        (tmp / "RamBlock.inc").write_text(
            section(ram, "  struct StoreOps {", "  };") +
            next(x for x in ram.splitlines() if x.startswith("  static bool discardRequested()")) + "\n" +
            section(ram, "  void attachStore()", "  }") +
            section(ram, "  IOReturn doSynchronizeCache()", "  }").replace(" override", "") +
            next(x for x in ram.splitlines() if x.startswith("  IOReturn doSynchronize(")).replace(" override", "") + "\n")
        (tmp / "StoreGptCheck.inc").write_text(
            section(ufs, 'extern "C" unsigned native_ufs_store_gpt_check (', "}"))
        exe = tmp / "test"
        subprocess.run(["c++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror",
                        "-Wno-address", "-Wno-unused-function", "-pthread", "-no-pie",
                        "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
                        "-I", tmp, "-I", stage, "-isystem", deps, "-isystem", a.base / "drivers/RamBlock",
                        ROOT / "tests/test-nuwa-v1-retained.cpp", "-o", exe], check=True)
        for case in (a.case,) if a.case else cases:
            subprocess.run([exe, case], check=True)


if __name__ == "__main__":
    main()
