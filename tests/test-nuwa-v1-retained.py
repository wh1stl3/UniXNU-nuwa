#!/usr/bin/env python3
"""Exercise the retained profile's staged encoder and the upstream v1 overlay."""
import argparse
import json
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
    cases = ("reset", "reset-recover", "reset-marker-applied", "daily-inprogress", "daily-inprogress-partial",
             "reset-legacy-0", "reset2-legacy-0", "reset-legacy-blank",
             "reset-legacy-1", "reset-legacy-sb1-garbage", "reset-legacy-sb1-garbage-only",
             "reset-legacy-sb1-tail", "reset-legacy-torn",
             "reset-legacy-magic", "reset-legacy-seed-conflict", "reset-legacy-slot-conflict",
             "reset-legacy-header-crc", "reset-legacy-block-crc", "reset-legacy-fields",
             "reset-legacy-noninitial-gen", "reset-legacy-noninitial-head",
             "reset-legacy-noninitial-count", "reset-legacy-noninitial-mapcrc",
             "reset-legacy-second-invalid", "reset-legacy-marker-fail",
             "reset-legacy-both", "reset2-legacy-both",
             "reset-legacy-read-first", "reset-legacy-read-second", "reset-legacy-read-v1-preflight", "reset-legacy-v3",
             "reset-legacy-mixed", "reset-legacy-mixed-reverse", "reset-legacy-ambiguous",
             "reset-legacy-seed", "reset-legacy-primary", "reset-legacy-backup",
             "reset-legacy-reserve", "reset-legacy-rootguard",
             "reset-legacy-owner", "reset-legacy-size", "reset-legacy-bounds",
             "reset-legacy-fail0", "reset-legacy-fail0-applied",
             "reset-legacy-fail1", "reset-legacy-fail1-applied",
             "reset-overlay-alloc", "reset-overlay-read", "reset-overlay-bitmap",
             "reset-overlay-bitmap-mid", "reset-overlay-bitmap-last", "reset-overlay-header", "reset-overlay-header-applied",
             "reset-overlay-commit", "daily-reset-3",
             "retained", "write-scsi", "write-read-scsi", "wrong-header-seed", "wrong-boot-seed",
             "legacy-v3", "legacy-disposable", "legacy-read-scsi", "overlap-root", "overlap-log",
             "wrong-primary-gpt", "wrong-backup-gpt", "reset-scsi",
             "reset-order-before-header", "reset-order-after-header",
             "sync-timeout", "sync-unowned", "sync-ownership", "cache-state")
    p.add_argument("--case", choices=cases)
    a = p.parse_args()
    build = a.build.resolve()
    stage = build / "nuwa-retained-persist"
    ufs = (stage / "NativeUfs.cpp").read_text()
    encoder = (stage / "CombinedRead.h").read_text()
    assert "/RetainedPersist.inc\"" in ufs and "KernelPort.inc" not in ufs
    assert "dataProvider" not in ufs and "WriteVolatile" in encoder
    assert not any(x in encoder for x in ("WriteFua", "SyncCache", "0x35"))
    ram_args = json.loads((build / "ramblock-argv.json").read_text())
    nodur, = (arg for arg in ram_args if arg.startswith("-DNUWA_V1_NODUR="))
    assert nodur == "-DNUWA_V1_NODUR=1"
    assert not any(arg.startswith(("-DNUWA_DATA_CANDIDATE", "-DNUWA_DISPOSABLE_DATA"))
                   for arg in ram_args)
    root = (stage / "RootCommands.h").read_text()
    assert root.index("IOLockLock(gHost.lock)") < root.index("retainedReadLocked(lba, blocks)") < root.index("IOLockUnlock(gHost.lock)")
    ram = (ROOT / "package/nuwa-ramblock/NativeRamBlock.cpp").read_text()
    assert "overlay.open(ops, pages, seedHash, mode == 1, overlayBits, discardRequested())" in ram
    deps = build.parent / "nuwa-ufs-apfs-root-integration-20261114/run-r5-visible-candidate/source"
    with tempfile.TemporaryDirectory(prefix="nuwa-v1-retained-") as tmp:
        tmp = Path(tmp)
        (tmp / "RamBlock.inc").write_text(
            section(ram, "  struct StoreOps {", "  };") +
            next(x for x in ram.splitlines() if x.startswith("  void persistFailed()")) + "\n" +
            next(x for x in ram.splitlines() if x.startswith("  static bool discardRequested()")) + "\n" +
            section(ram, "  void attachStore()", "  }") +
            section(ram, "  IOReturn doSynchronizeCache()", "  }").replace(" override", "") +
            next(x for x in ram.splitlines() if x.startswith("  IOReturn doSynchronize(")).replace(" override", "") + "\n" +
            section(ram, "#if defined(NUWA_DISPOSABLE_DATA) || defined(NUWA_V1_NODUR)",
                    "#endif").replace(" override", ""))
        (tmp / "StoreGptCheck.inc").write_text(
            section(ufs, 'extern "C" unsigned native_ufs_store_gpt_check (', "}"))
        (tmp / "RamIO.inc").write_text(
            section(ram, "IOReturn NativeRamBlock::doAsyncReadWrite(", "}"))
        (tmp / "V1Diag.inc").write_text(
            section(ram, "static void nuwaV1WriteFailure(", "}"))
        exe = tmp / "test"
        subprocess.run(["c++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror",
                         "-Wno-address", "-Wno-unused-function", "-pthread", "-no-pie", nodur,
                        "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
                        "-I", tmp, "-I", stage, "-isystem", deps, "-isystem", a.base / "drivers/RamBlock",
                        ROOT / "tests/test-nuwa-v1-retained.cpp", "-o", exe], check=True)
        for case in (a.case,) if a.case else cases:
            subprocess.run([exe, case], check=True)
            print(f"case={case} exit=0", flush=True)
        if not a.case:
            renderer = (build / "BootProgress.c").read_text()
            rows = (section(renderer, "static const char *bp_v1_write_source(", "}") +
                    section(renderer, "static void bp_v1_rows(char rows[3][BP_COLS]) {", "}"))
            row_src = tmp / "reset-rows.cpp"
            row_src.write_text(r'''
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <initializer_list>
#include "PersistOpenReason.h"
#define BP_COLS 120
volatile uint32_t native_data_persist_state = UINT32_MAX, native_data_persist_header = UINT32_MAX;
volatile uint64_t native_data_persist_present = UINT64_MAX, native_data_persist_writes = 2;
volatile uint64_t native_data_persist_errors = 1, nuwa_v1_write_failure = (4ull << 32) | 1;
volatile uint64_t nuwa_v1_write_failure_attached = (7ull << 32) | 2;
volatile uint64_t nuwa_v1_ufs_write_failure = (5ull << 32) | (2ull << 24) | 0x123456;
const char *volatile nuwa_data_persist_open_why;
''' + rows + r'''
int main() {
  struct Case { int ok; const char *input, *why, *rst; };
  const Case cases[] = {
    {1, "legacy-reset-0", "why=ok", "rst=in0"},
    {1, "legacy-reset-1", "why=ok", "rst=in1"},
    {1, "legacy-reset-2", "why=ok", "rst=in2"},
    {1, "legacy-reset-3", "why=ok", "rst=in3"},
    {0, "legacy-reset-read", "why=window", "rst=read"},
    {0, "legacy-reset-guard", "why=window", "rst=guard"},
    {0, "legacy-reset-invalid", "why=window", "rst=invalid"},
    {0, "legacy-reset-sb1", "why=window", "rst=sb1"},
    {0, "legacy-reset-pending", "why=window", "rst=pending"},
    {0, "legacy-reset-marker-write", "why=window", "rst=markfail"},
    {0, "legacy-reset-write-1", "why=window", "rst=fail1"},
    {0, "legacy-reset-write-2", "why=window", "rst=fail2"},
  };
  for (const auto &c : cases) {
    nuwa_data_persist_open_why = nuwa_persist_open_reason(c.ok, c.input);
    char lines[3][BP_COLS];
    bp_v1_rows(lines);
    assert(strstr(lines[0], c.why) && strstr(lines[0], c.rst) && strlen(lines[0]) <= 80);
    assert(strstr(lines[1], "D2 wr=2 er=1 ufs=5:02:123456"));
    assert(strstr(lines[2], "D3 first=inactive/00000001 after=ufs-w/00000002"));
    puts(lines[0]);
  }
  for (const char *status : {"- rst=ready", "- rst=progress", "- rst=clean1",
                             "- rst=clean2", "ok rst=done0", "ok rst=done1",
                             "ok rst=done2", "ok rst=done3", "ok rst=commitfail"}) {
    nuwa_data_persist_open_why = status;
    char lines[3][BP_COLS];
    bp_v1_rows(lines);
    assert(strstr(lines[0], status) && strlen(lines[0]) <= 80);
    puts(lines[0]);
  }
}
''')
            row_exe = tmp / "reset-rows"
            subprocess.run(["c++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                            "-fsanitize=address,undefined", "-fno-sanitize-recover=all", "-no-pie",
                            "-I", ROOT / "package/nuwa-ramblock", row_src, "-o", row_exe], check=True)
            subprocess.run([row_exe], check=True)


if __name__ == "__main__":
    main()
