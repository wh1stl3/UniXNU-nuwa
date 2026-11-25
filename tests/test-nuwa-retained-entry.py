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
    banner = (build / "BootProgress.c").read_text()
    assert '!strncmp(s,"UFS2 ",5)' in banner
    assert "if (n < 64 && &nuwa_ufs_mode_row)\n" in banner
    ufs = (stage / "NativeUfs.cpp").read_text()
    commands = (stage / "RootCommands.h").read_text()
    ram = (ROOT / "package/nuwa-ramblock/NativeRamBlock.cpp").read_text()
    source = ROOT / "out/nuwa-ufs-apfs-root-integration-20261114/run-r5-visible-candidate/source"
    (build / "FixtureRoot.inc").write_text(commands[
        commands.index("struct RootReadSnapshot {"):commands.index("// ---- Persistent store")])
    (build / "FixtureBlock.inc").write_text(body(ufs, "IOReturn NativeUfsBlock::doAsyncReadWrite"))
    (build / "FixtureStore.inc").write_text(
        body(ufs, 'extern "C" int native_ufs_store_open (') +
        body(ufs, 'extern "C" unsigned native_ufs_store_gpt_check (') +
        body(ufs, 'extern "C" int native_ufs_store_write (') +
        body(ufs, 'extern "C" int native_ufs_store_sync (') +
        body(ufs, 'extern "C" int native_ufs_store_isolated ('))
    (build / "FixturePart.inc").write_text(
        body(ufs, 'extern "C" int native_ufs_part_find (') +
        body(ufs, 'extern "C" int native_ufs_part_read ('))
    (build / "FixtureAttach.inc").write_text(body(ram, "  void attachStore()", "  }"))
    start = body(ram, "bool NativeRamBlock::start(")
    assert start.index("  prepareCandidateView();") < start.index("  online = true;") < start.index("  registerService();")
    helpers = "".join(body(ram, name, "  }") for name in (
        "  void setDataView(", "  void prepareCandidateView()", "  void isolateCandidate()",
        "  static bool candidateReadOnly()", "  bool seedInfo("))
    available, = (line for line in ram.splitlines() if line.startswith("  bool available()"))
    (build / "FixtureRamIO.inc").write_text(
        helpers + available + "\n  template<class BufferOps>\n" + body(ram, "  IOReturn candidateIO(", "  }") +
        "".join(body(ram, name, "  }").replace(" override", "") for name in (
            "  IOReturn doSynchronizeCache()", "  IOReturn reportWriteProtection(")))
    binary = build / "test-retained-response"
    subprocess.run([
        os.environ.get("CXX", "c++"), "-std=c++17", "-Wall", "-Wextra", "-Werror",
        "-Wno-unused-function", "-Wno-address", "-pthread", "-O2", "-no-pie",
        "-fsanitize=undefined,address", "-fno-sanitize-recover=all",
        "-DNUWA_DATA_CANDIDATE=1", "-I", build, "-I", stage, "-I", source,
        "-I", base / "drivers/RamBlock", ROOT / "tests/test-nuwa-retained-response.cpp",
        "-o", binary,
    ], check=True)
    subprocess.run([binary], check=True)
    print("PASS UFS2 banner: cached hook, bounded row capacity")


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())
