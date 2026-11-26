#!/usr/bin/env python3
"""Replay actual NEON formatting, pre-write predicate, and probe on the host."""
import argparse
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]

CPP = r'''
#include "NeonRetainedHarness.inc"
static unsigned neonOptIn;
static bool neonBootArg(const char *name, void *out, size_t n) {
  if (strcmp(name, "nuwa-ufs-neon") || !neonOptIn) return false;
  assert(n == sizeof neonOptIn);
  memcpy(out, &neonOptIn, n);
  return true;
}
#define PE_parse_boot_argn neonBootArg
#define NUWA_NEON_SETUP
#include "RetainedNeon.inc"
#undef NUWA_NEON_SETUP
static constexpr uint32_t kDefaultReserveMiB = 1024;
#include "RetainedNeon.inc"
#undef PE_parse_boot_argn

static void checkPre() {
  using namespace PreservedNop;
  for (unsigned fail = 0; fail < 7; ++fail) {
    const unsigned offsets[] = {0, 0x34, 0x30, 0x58, 0x78, 0x20};
    struct Port {
      const unsigned *offsets;
      unsigned calls = 0, fail;
      uint32_t hread(unsigned off) {
        assert(off == offsets[calls]);
        const uint32_t good[] = {1 << 24, 1, 9, 0, 0, 0};
        const uint32_t bad[] = {0, 0, 0, 1, 1, kUfsFatalStatus};
        const auto i = calls++;
        return i + 1 == fail ? bad[i] : good[i];
      }
    } p{offsets, 0, fail};
    PreservedNop::State s{};
    s.dma = fail == 1 ? 0x100000000ULL : 0x10000;
    s.id2 = 0x1555;
    const bool neon = true;
    auto run = [&]() {
      #include "NeonPrerequisite.inc"
      return End::Success;
    };
    const bool good = run() == End::Success;
    assert(good == (fail == 0));
    assert(p.calls == (fail ? fail : 6) && neonHc.seen == ((1U << p.calls) - 1));
  }
}

static void checkMedia() {
  using namespace NuwaNeon;
  constexpr uint64_t root = 8446279680ULL, reserve = 262144;
  const auto w = NuwaNeon::Overlay::Media;
  // CRC failures are independent, and neither placement failures nor
  // faulted reads can advance to subsequent I/O.
  for (unsigned which = 0; which < 24; ++which) {
    FixtureGpt disk;
    GptBuffers buffers{};
    Media m;
    if (which == 1) disk.pe[0] ^= 1;
    if (which == 2) disk.be[0] ^= 1;
    if (which == 3) { disk.be[127] ^= 1; disk.repair(); }
    if (which == 5) putLE(disk.b + 72, disk.id.userdataFirst, 8);
    const uint64_t ordered[] = {1, 2, disk.id.capacity - 1, disk.id.capacity - 2};
    unsigned calls = 0;
    auto read = [&](uint64_t lba, void *dst) {
      const auto i = calls++;
      if (i < 4) assert(lba == ordered[i]);
      else if (i < 8) assert(lba == w.first + Anchors[i - 4]);
      else assert(i < 18 && lba == w.first + Metadata[i - 8]);
      if (which >= 6 && i == which - 6) return false;
      if (const auto *data = disk.at(lba)) memcpy(dst, data, Block);
      else memset(dst, i == 7 || i == 10 ? 0x80 : 0, Block);
      return true;
    };
    media(read, disk.id, root, which == 4 ? reserve - 1 : reserve, w, buffers, m);
    if (which == 0)
      assert(calls == 18 && m.place == Check::Ok && m.anchorsRead == 4 &&
             m.anchorsNonzero == 8 && m.samples == 10 && m.nonzero == 1);
    if (which >= 1 && which <= 5) {
      assert(calls == (which == 5 ? 3U : 4U) && !m.anchorsRead && !m.samples);
      assert(m.primary == (which == 1 ? Check::Bad : Check::Ok));
      assert(m.backup == (which == 2 || which == 5 ? Check::Bad : Check::Ok));
      if (which == 3) assert(m.agree == Check::Bad);
      if (which == 4) assert(m.place == Check::Bad);
    }
    if (which >= 6) assert(calls == which - 5);
  }
}

int main() {
  using namespace NuwaNeon;
  startMockBoot({});
  char rows[Rows + 1][120]{};
  for (unsigned off : {0, 2}) {
    neonOptIn = off;
    assert(!neonBegin() && !nuwa_ufs_neon_rows(rows, Rows));
    assert(!combined_hardware.mmioReads && !combined_hardware.submissions);
  }
  neonOptIn = 1;
  assert(neonBegin() && nuwa_ufs_neon_rows(rows, Rows) == 1);
  checkPre();
  assert(nuwa_ufs_neon_rows(rows, Rows) == 2 && strstr(rows[1], "00000000"));
  const auto mmio = combined_hardware.mmioReads;
  assert(nuwa_ufs_neon_rows(rows, 1) == 1 && combined_hardware.mmioReads == mmio);
  checkMedia();
  for (unsigned timeout : {0, 1}) {
    startMockBoot({});
    FixtureGpt disk;
    combined_hardware.gpt = &disk;
    combined_hardware.wce = true;
    if (timeout) {
      combined_hardware.modeWire.timedOut = true;
      combined_hardware.modeWire.ocs = 15;
    }
    neonDesc = {};
    neonMedia = {};
    probeNeon();
    assert(combined_hardware.descCount == 2 && combined_hardware.modeCount == 1);
    assert(combined_hardware.submissions == (timeout ? 3U : 7U));
    assert(!combined_hardware.writeSubmissions && !dataProvider.sync());
    assert(neonDesc.capacity == Check::Bad); // mock Unit=60, READ CAPACITY=61850624
    assert(neonDesc.dev[0x19] == 0xce && neonDesc.lu0[0x12] == 60);
    assert(neonMedia.place == (timeout ? Check::Unknown : Check::Bad));
    assert(nuwa_ufs_neon_rows(rows, Rows + 1) == Rows && !rows[Rows][0]);
    for (unsigned room = 0; room <= Rows; ++room)
      assert(nuwa_ufs_neon_rows(rows, room) == room);
    for (unsigned i = 0; i < Rows; ++i) assert(strlen(rows[i]) <= Cols);
    assert(strstr(rows[0], "cid=N261126A") && strstr(rows[0], "old=? rsr=?"));
    assert(strstr(rows[5], "M(part)=0/10"));
    if (timeout) {
      const auto reads = combined_hardware.mmioReads;
      assert(retainedSlot.state() == NuwaData::State::TIMEOUT_ORPHAN);
      assert(nuwa_ufs_neon_rows(rows, Rows) == Rows && combined_hardware.mmioReads == reads);
    }
  }
  std::puts("PASS NEON partial HC evidence, read-only survey, isolation and six-row budget");
}
'''


def main(build, base, fixtures, output):
    stage = build / "nuwa-data-provider"
    baseline = build.parent / "nuwa-ufs-apfs-root-integration-20261114/run-r5-visible-candidate/source"
    output.mkdir(parents=True, exist_ok=True)
    renderer = (build / "BootProgress.c").read_text()
    assert "nuwa_ufs_neon_rows(evidence,6)" in renderer and "line(37+i,evidence[i]" in renderer
    assert "nuwa_ufs_neon_rows(rows,budget)" in renderer
    assert "bp_cr_rows(rows+neon,budget-neon)" in renderer
    # 1440 x 3200 at scale 3; y and width budget of both existing consumers.
    assert 8 + 43 * 14 * 3 <= 3200 and (1440 - 16) // 18 >= 66
    assert min(24, (3200 // 2 - 8) // 42 - 2) >= 6
    preserved = (stage / "PreservedNop.h").read_text()
    original = (baseline / "PreservedNop.h").read_text()
    for op in ("hwrite", "sread"):
        assert re.findall(rf"p\.{op}\([^\n]+", preserved) == re.findall(rf"p\.{op}\([^\n]+", original)
    first_write = preserved.index("  p.hwrite(0x24, 0);")
    assert preserved.index("if (neon) neonPre(pre);") < first_write
    snippet = preserved[preserved.index("  NuwaNeon::Hc pre;"):preserved.index("  s.stage = 2;")]
    (output / "NeonPrerequisite.inc").write_text(snippet)
    harness = (ROOT / "tests/test-nuwa-retained-response.cpp").read_text()
    assert harness.count("\nint main() {") == 1
    (output / "NeonRetainedHarness.inc").write_text(harness.split("\nint main() {", 1)[0])
    source = output / "test-neon.cpp"
    source.write_text(CPP)
    binary = output / "test-neon"
    subprocess.run([
        os.environ.get("CXX", "c++"), "-std=c++17", "-Wall", "-Wextra", "-Werror",
        "-Wno-unused-function", "-Wno-address", "-pthread", "-O2", "-no-pie",
        "-fsanitize=undefined,address", "-fno-sanitize-recover=all",
        "-DNUWA_DATA_CANDIDATE=1", "-I", fixtures, "-I", stage, "-I", baseline,
        "-I", ROOT / "tests", "-I", ROOT / "package/nuwa-data-write",
        "-I", base / "drivers/RamBlock", source, "-o", binary,
    ], check=True)
    subprocess.run([binary], check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("build", type=Path)
    parser.add_argument("base", type=Path)
    parser.add_argument("--fixtures", type=Path, help="output of test-nuwa-retained-entry.py")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    main(args.build.resolve(), args.base.resolve(),
         (args.fixtures or args.build).resolve(), (args.output or args.build).resolve())
