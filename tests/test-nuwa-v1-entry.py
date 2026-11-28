#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Patent
"""Link the actual RamBlock v1 and retained store entries to a host file port."""
import argparse
import errno
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BASE_PIN = "693f5d9cae8a408dd18b39f3f9fdc4228c934241"


def section(source, signature, closing="}"):
    lines = source.splitlines()
    start, = (i for i, line in enumerate(lines) if line.startswith(signature))
    return "\n".join(lines[start:lines.index(closing, start) + 1]) + "\n"


def sparse_contents(path):
    # Compare every logical byte: holes are zero, and every allocated extent
    # is compared as bytes (not just a checksum or a list of known v3 pages).
    with path.open("rb", buffering=0) as file:
        length = os.fstat(file.fileno()).st_size
        extents = []
        at = 0
        while at < length:
            try:
                start = os.lseek(file.fileno(), at, os.SEEK_DATA)
            except OSError as error:
                if error.errno != errno.ENXIO:
                    raise
                break
            at = os.lseek(file.fileno(), start, os.SEEK_HOLE)
            file.seek(start)
            extents.append((start, file.read(at - start)))
            assert len(extents[-1][1]) == at - start
        return length, extents


def main(base, stage, transport, qualification=False):
    assert subprocess.check_output(["git", "-C", base, "rev-parse", "HEAD"],
                                   text=True).strip() == BASE_PIN
    ram = (ROOT / "package/nuwa-ramblock/NativeRamBlock.cpp").read_text()
    ufs = stage.read_text()
    kernel = (ROOT / "package/nuwa-data-write/KernelPort.inc").read_text()
    retained = (ROOT / "tests/test-nuwa-retained-response.cpp").read_text()
    deps = stage.parents[2] / "nuwa-ufs-apfs-root-integration-20261114/run-r5-visible-candidate/source"
    identity, = (x for x in ufs.splitlines() if x.startswith(
        "static constexpr NuwaData::GptIdentity nuwaDataIdentity = "))
    mode, = (x for x in ufs.splitlines() if x.startswith(
        'extern "C" unsigned native_ufs_store_mode '))
    discard, = (x for x in ram.splitlines() if x.startswith("  static bool discardRequested()"))
    persist_failed, = (x for x in ram.splitlines() if x.startswith("  void persistFailed()"))
    sync, = (x for x in ram.splitlines() if x.startswith("  IOReturn doSynchronize("))
    # Refuse a disposable build or one with a different mode-2 store route.
    for route in ("openCandidateData (first, blocks, reserve)", "dataProvider.read (",
                  "dataProvider.write (", "dataProvider.sync ()"):
        assert route in ufs, route
    print(f"Input staged NativeUfs.cpp sha256={hashlib.sha256(stage.read_bytes()).hexdigest()}",
          flush=True)
    with tempfile.TemporaryDirectory(prefix="nuwa-v1-host-") as name:
        temp = Path(name)
        text = transport.read_text()
        line, = (s for s in text.splitlines() if s.startswith('#include "') and
                 s.endswith("/RetainedResponse.inc\""))
        response = ROOT / "package/nuwa-data-write/RetainedResponse.inc"
        (temp / "CombinedRead.h").write_text(text.replace(line, f'#include "{response}"'))
        (temp / "FixtureHardware.inc").write_text(
            section(retained, "struct Response {", "};") +
            section(retained, "struct Sb0Media {", "};") +
            section(retained, "static struct Hardware {", "} combined_hardware;"))
        (temp / "FixtureUfs.inc").write_text(
            section(ufs, "struct StoreGeometry {", "};") + "StoreGeometry gStoreGeometry;\n" +
            identity + "\n" +
            'constexpr uint32_t kDefaultReserveMiB = 1024;\n'
            'uint64_t gStoreRegionFirst, gStoreRegionBlocks;\n' +
            section(kernel, "static bool openCandidateData(") +
            section(ufs, "static uint64_t reserveBlocks (") +
            section(ufs, "static unsigned storeMode (") + mode + "\n" +
            "".join(section(ufs, 'extern "C" ' + signature) for signature in (
                "int native_ufs_store_open (", "int native_ufs_store_read (",
                "int native_ufs_store_write (", "int native_ufs_store_sync (",
                "unsigned native_ufs_store_gpt_check (")))
        (temp / "FixtureRamClass.inc").write_text(
            section(ram, "  struct StoreOps {", "  };") + persist_failed + "\n" + discard + "\n" +
            section(ram, "  void attachStore()", "  }") +
            section(ram, "  IOReturn doSynchronizeCache()", "  }").replace(" override", "") +
            sync.replace(" override", "") + "\n")
        (temp / "FixtureRamIO.inc").write_text(section(ram, "IOReturn NativeRamBlock::doAsyncReadWrite"))
        binary = temp / "nuwa-v1-entry"
        source = "test-nuwa-v1-qualification.cpp" if qualification else "test-nuwa-v1-entry.cpp"
        subprocess.run([os.environ.get("CXX", "c++"), "-std=c++17", "-Wall", "-Wextra", "-Werror",
                        "-Wno-address", "-Wno-unused-function", "-O2", "-fno-sanitize-recover=all",
                        "-fsanitize=undefined,address",
                        "-no-pie", "-DNUWA_DATA_WRITE_OPT_IN=1",
                        "-I", temp, "-isystem", deps, "-isystem", base / "drivers/RamBlock",
                        ROOT / "tests" / source, "-o", binary], check=True)

        def run(operation, image, *extra):
            subprocess.run([binary, operation, image, *map(str, extra)], check=True)

        if qualification:
            for mask in range(7):
                run("deny", temp / f"deny-{mask}.img", mask)
            run("deny-producer", temp / "deny-producer.img")
            run("deny-dma", temp / "deny-dma.img")
            run("reference", temp / "reference.img", 0)
            for fault in range(1, 68):
                run("reference", temp / f"reference-fail-{fault}.img", fault)
            print("self-checked reference: 67/67 prior write failures stop before final header", flush=True)
            run("reference", temp / "reference-final-header-fail.img", 68)
            print("self-checked reference: failed final header is not reported successful", flush=True)
            for fault in range(1, 6):
                run("reference-wire", temp / f"reference-wire-{fault}.img", fault)
            run("actual", temp / "actual.img", 0)
            for fault in range(1, 65):
                run("actual", temp / f"actual-fail-{fault}.img", fault)
            print("self-checked actual: 64/64 bitmap failures stop before final header", flush=True)
            run("actual", temp / "actual-final-header-fail.img", 65)
            print("self-checked actual: failed final header is not reported successful", flush=True)
            return

        image = temp / "v1.img"
        for operation in ("init", "read-b", "reject-no-fua", "reject-live-fua", "reject-anchor-io",
                          "reject-reserved-size"):
            run(operation, image)
        for fault in ("data", "bitmap", "short", "sync", "timeout"):
            run("fault-" + fault, image)
            run("read-fault", image)
        for scenario in ("make-v3", "make-v3-collision", "make-v3-disposable", "make-v3-torn"):
            legacy = temp / (scenario + ".img")
            run(scenario, legacy)
            snapshot = sparse_contents(legacy)
            run("reject-v3-torn" if scenario.endswith("-torn") else "reject-v3", legacy)
            assert sparse_contents(legacy) == snapshot
            print(f"PASS v3 unchanged byte-for-byte ({snapshot[0]} logical bytes)", flush=True)
        for operation in ("stress", "read-stress"):
            run(operation, image)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("base", type=Path)
    parser.add_argument("staged_native_ufs", type=Path)
    parser.add_argument("staged_combined_read", type=Path)
    parser.add_argument("--qualification", action="store_true",
                        help="run host-only qualification and initialization sequence fixtures")
    args = parser.parse_args()
    main(args.base.resolve(), args.staged_native_ufs.resolve(), args.staged_combined_read.resolve(),
         args.qualification)
