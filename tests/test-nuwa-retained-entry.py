#!/usr/bin/env python3
"""Compile the candidate's actual block and Data attach entries with host shims."""
import argparse
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def body(source, signature, closing="}"):
    lines = source.splitlines()
    start, = (i for i, line in enumerate(lines) if line.startswith(signature))
    end = lines.index(closing, start)
    return "\n".join(lines[start:end + 1]) + "\n"


def main(build, base, output, sb0, disposable=False):
    stage = build / "nuwa-data-provider"
    output.mkdir(parents=True, exist_ok=True)
    banner = (build / "BootProgress.c").read_text()
    assert '!strncmp(s,"UFS2 ",5)' in banner
    assert "if (n < 64 && &nuwa_ufs_mode_row)\n" in banner
    ufs = (stage / "NativeUfs.cpp").read_text()
    commands = (stage / "RootCommands.h").read_text()
    ram = (ROOT / "package/nuwa-ramblock/NativeRamBlock.cpp").read_text()
    source = build.parent / "nuwa-ufs-apfs-root-integration-20261114/run-r5-visible-candidate/source"
    # The staged files pin absolute includes into the original worktree.
    # Rebase only that prefix so one TU uses one copy of each device header.
    original = str(build.parents[1] / "package/nuwa-data-write") + "/"
    local = str(ROOT / "package/nuwa-data-write") + "/"
    for name in ("CombinedRead.h", "PreservedNop.h", "RootCommands.h"):
        (output / name).write_text((stage / name).read_text().replace(
            f'#include "{original}', f'#include "{local}'))
    (output / "FixtureRoot.inc").write_text(commands[
        commands.index("struct RootReadSnapshot {"):commands.index("// ---- Persistent store")])
    (output / "FixtureBlock.inc").write_text(body(ufs, "IOReturn NativeUfsBlock::doAsyncReadWrite"))
    (output / "FixtureStore.inc").write_text(
        body(ufs, 'extern "C" int native_ufs_store_open (') +
        body(ufs, 'extern "C" unsigned native_ufs_store_gpt_check (') +
        body(ufs, 'extern "C" int native_ufs_store_write (') +
        body(ufs, 'extern "C" int native_ufs_store_sync ('))
    (output / "FixturePart.inc").write_text(
        body(ufs, 'extern "C" int native_ufs_part_find (') +
        body(ufs, 'extern "C" int native_ufs_part_read ('))
    (output / "FixtureAttach.inc").write_text(body(ram, "  void attachStore()", "  }"))
    (output / "FixtureRamIO.inc").write_text(
        "  template<class BufferOps>\n" + body(ram, "  uint64_t candidateIO(", "  }") +
        body(ram, "  IOReturn doSynchronizeCache()", "  }").replace(" override", ""))
    binary = output / "test-retained-response"
    subprocess.run([
        os.environ.get("CXX", "c++"), "-std=c++17", "-Wall", "-Wextra", "-Werror",
        "-Wno-unused-function", "-Wno-address", "-pthread", "-O2", "-no-pie",
        "-fsanitize=undefined,address", "-fno-sanitize-recover=all",
        "-DNUWA_DATA_CANDIDATE=1", "-DNUWA_DATA_WRITE_OPT_IN=1",
        *(["-DNUWA_SB0_HOST_FIXTURE=1"] if sb0 else []),
        *(["-DNUWA_DISPOSABLE_FIXTURE=1"] if disposable else []),
        "-I", output, "-I", stage, "-I", source,
        "-I", base / "drivers/RamBlock", ROOT / "tests/test-nuwa-retained-response.cpp",
        "-o", binary,
    ], check=True)
    subprocess.run([binary], check=True)
    print("PASS UFS2 banner: cached hook, bounded row capacity")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("build", type=Path)
    parser.add_argument("base", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--sb0", action="store_true")
    parser.add_argument("--disposable", action="store_true")
    args = parser.parse_args()
    main(args.build.resolve(), args.base.resolve(),
         (args.output or args.build).resolve(), args.sb0, args.disposable)
