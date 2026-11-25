#!/usr/bin/env python3
"""Compile the candidate's actual block and Data attach entries with host shims."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def body(source, signature, closing="}"):
    lines = source.splitlines()
    start, = (i for i, line in enumerate(lines) if line.startswith(signature))
    end = lines.index(closing, start)
    return "\n".join(lines[start:end + 1]) + "\n"


def main(build, base):
    stage = build / "nuwa-data-provider"
    ufs = (stage / "NativeUfs.cpp").read_text()
    commands = (stage / "RootCommands.h").read_text()
    ram = (ROOT / "package/nuwa-ramblock/NativeRamBlock.cpp").read_text()
    source = ROOT / "out/nuwa-ufs-apfs-root-integration-20261114/run-r5-visible-candidate/source"
    (build / "FixtureRoot.inc").write_text(commands[
        commands.index("struct RootReadSnapshot {"):commands.index("// ---- Persistent store")])
    (build / "FixtureBlock.inc").write_text(body(ufs, "IOReturn NativeUfsBlock::doAsyncReadWrite"))
    (build / "FixtureStore.inc").write_text(
        body(ufs, 'extern "C" int native_ufs_store_open (') +
        body(ufs, 'extern "C" unsigned native_ufs_store_gpt_check ('))
    (build / "FixtureAttach.inc").write_text(body(ram, "  void attachStore()", "  }"))
    binary = build / "test-retained-response"
    subprocess.run([
        os.environ.get("CXX", "c++"), "-std=c++17", "-Wall", "-Wextra", "-Werror",
        "-Wno-unused-function", "-Wno-address", "-pthread", "-fsanitize=undefined",
        "-DNUWA_DATA_CANDIDATE=1", "-I", build, "-I", stage, "-I", source,
        "-I", base / "drivers/RamBlock", ROOT / "tests/test-nuwa-retained-response.cpp",
        "-o", binary,
    ], check=True)
    subprocess.run([binary], check=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())
