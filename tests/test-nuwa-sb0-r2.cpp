// SPDX-License-Identifier: BSD-2-Clause
// Host-only R2 diagnostic fixture. It builds the exact disposable overlay
// bytes, runs the new read-only parser, and cross-checks every verdict against
// the real DualBankLogOverlay<512,true>::open() on the same pages.
#include <array>
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <vector>

#include "../package/nuwa-data-write/Sb0R2.h"

using namespace NuwaData;
using Overlay = Disposable::Overlay;
using Page = std::array<uint8_t, Block>;

struct Disk {
  std::map<uint64_t, Page> pages;
  std::map<uint64_t, unsigned> readCounts;
  unsigned writes = 0;
  uint64_t failAt = UINT64_MAX, zeroSecondReadAt = UINT64_MAX;
  bool read(uint64_t lba, uint32_t n, void *dst) {
    assert(n == 1);
    ++readCounts[lba];
    if (lba == failAt) return false;
    if (lba == zeroSecondReadAt && readCounts[lba] == 2) {
      std::memset(dst, 0, Block);
      return true;
    }
    const auto it = pages.find(lba);
    if (it == pages.end()) std::memset(dst, 0, Block);
    else std::memcpy(dst, it->second.data(), Block);
    return true;
  }
  void resetReads() { readCounts.clear(); }
  bool write(uint64_t lba, uint32_t n, const void *src) {
    assert(n == 1);
    ++writes;
    std::memcpy(pages[lba].data(), src, Block);
    return true;
  }
  bool sync() { return true; }
};

// Records the absolute LBAs actually presented to the base port. This is the
// same production adapter template used by Sb0CandidatePort.inc.
struct RecordingPort {
  Disk disk;
  std::vector<uint64_t> lbas;
  bool read(uint64_t lba, uint8_t *out) {
    lbas.push_back(lba);
    if (lba < Overlay::Media.first) return false;
    const uint64_t rel = lba - Overlay::Media.first;
    if (rel >= Overlay::Media.blocks) return false;
    return disk.read(rel, 1, out);
  }
};

static Sb0R2::Workspace diagWorkspace;
static Sb0R2::SeenScratch diagSeen;
static Overlay::Workspace openWorkspace;
static Overlay::SeenScratch openSeen;

static void putLE(uint8_t *p, uint64_t value, unsigned n) {
  for (unsigned i = 0; i < n; ++i) p[i] = uint8_t(value >> (8 * i));
}

static const Page &initialPayload() {
  static const Page page = [] {
    static Overlay::Workspace w;
    std::memset(&w, 0, sizeof w);
    uint8_t sb0[Block];
    assert(Overlay::initialSuperblock(sb0, Disposable::Seed, w));
    Page out{};
    std::memcpy(out.data(), sb0, Block);
    return out;
  }();
  return page;
}

static void sealHeader(Page &page) {
  putLE(page.data() + 92, crc(page.data(), 96, 92), 4);
  putLE(page.data() + 4092, crc(page.data(), Block, 4092), 4);
}

static void sealBlock(Page &page) {
  putLE(page.data() + 4092, crc(page.data(), Block, 4092), 4);
}

static Sb0R2::Diagnosis diagnose(Disk &disk) {
  const unsigned before = disk.writes;
  disk.resetReads();
  std::memset(&diagWorkspace, 0, sizeof diagWorkspace);
  std::memset(&diagSeen, 0, sizeof diagSeen);
  Sb0R2::Diagnosis d;
  Sb0R2::parse(disk, Disposable::Seed, initialPayload().data(),
               diagWorkspace, diagSeen, d);
  assert(disk.writes == before);
  return d;
}

static Overlay::Open openVerdict(Disk &disk, Overlay &overlay) {
  const unsigned before = disk.writes;
  disk.resetReads();
  std::memset(&openWorkspace, 0, sizeof openWorkspace);
  std::memset(&openSeen, 0, sizeof openSeen);
  const auto open = overlay.open(disk, Disposable::Seed, openWorkspace, openSeen, false, false);
  assert(disk.writes == before);
  return open;
}

static Disk freshDisk() {
  Disk disk;
  disk.pages[0] = initialPayload();
  return disk;
}

// rec0 page 10 -> bank 0; rec1 page 10 -> bank 1; rec2 pages 11,12 -> bank 0.
static Disk healthyDisk() {
  Disk disk = freshDisk();
  static Overlay::Workspace w;
  static Overlay::SeenScratch s;
  std::memset(&w, 0, sizeof w);
  std::memset(&s, 0, sizeof s);
  Overlay overlay;
  assert(overlay.open(disk, Disposable::Seed, w, s, true, false) == Overlay::Open::Resumed);
  Page page{};
  std::memset(page.data(), 0x11, Block);
  assert(overlay.writeRun(disk, 10, 1, page.data()));
  std::memset(page.data(), 0x22, Block);
  assert(overlay.writeRun(disk, 10, 1, page.data()));
  std::vector<Page> run(2);
  std::memset(run[0].data(), 0x33, Block);
  std::memset(run[1].data(), 0x44, Block);
  assert(overlay.writeRun(disk, 11, 2, run.data()));
  return disk;
}

static void expectSummary(const Sb0R2::Diagnosis &d, const char *line1,
                          const char *line2 = nullptr) {
  char summary[2][96] = {};
  const unsigned lines = Sb0R2::summary(d, summary);
  assert(lines == (line2 ? 2U : 1U));
  assert(std::strcmp(summary[0], line1) == 0);
  if (line2) assert(std::strcmp(summary[1], line2) == 0);
  std::printf("  %s\n", summary[0]);
  if (line2) std::printf("  %s\n", summary[1]);
}

static void expect(const char *name, Disk &disk, Overlay::Open expectedOpen,
                   Sb0R2::Fault fault, Sb0R2::Anchor anchor, uint32_t flags,
                   uint32_t rec, uint32_t refs, uint32_t pages) {
  char summary[2][96] = {};
  const auto d = diagnose(disk);
  const unsigned lines = Sb0R2::summary(d, summary);
  assert(lines == 1 || lines == 2);
  assert(d.fault == fault);
  assert(d.anchor == anchor);
  assert(d.sb0Valid == bool(flags & 1));
  assert(d.rec == rec);
  assert(d.refs == refs);
  assert(d.pages == pages);
  Overlay opened;
  const auto open = openVerdict(disk, opened);
  assert(open == expectedOpen);
  if (open == Overlay::Open::Resumed) {
    assert(opened.generation() == d.records);
    assert(opened.presentCount() == d.pages);
  }
  std::printf("CASE %s open=%s fault=%s anchor=%s rec=", name,
              open == Overlay::Open::Resumed ? "RESUMED" : "FAILED",
              Sb0R2::faultName(d.fault), Sb0R2::anchorName(d.anchor));
  if (d.rec == UINT32_MAX) std::printf("-\n");
  else std::printf("%u\n", d.rec);
  std::printf("  %s\n", summary[0]);
  if (lines == 2) std::printf("  %s\n", summary[1]);
}

int main() {
  // 1. Fresh exact anchor, empty ring: the disposable initializer state.
  {
    Disk disk = freshDisk();
    expect("fresh-exact", disk, Overlay::Open::Resumed, Sb0R2::Fault::None,
           Sb0R2::Anchor::Exact, 1, UINT32_MAX, 0, 0);
  }
  // 2. Healthy non-empty log: three records, three unique pages.
  {
    Disk disk = healthyDisk();
    expect("healthy-log", disk, Overlay::Open::Resumed, Sb0R2::Fault::None,
           Sb0R2::Anchor::Exact, 1, UINT32_MAX, 3, 3);
  }
  // 3. Log block CRC damaged at record 1.
  {
    Disk disk = healthyDisk();
    disk.pages[Overlay::Log + 1][4092] ^= 1;
    expect("log-crc", disk, Overlay::Open::Failed, Sb0R2::Fault::LogCrc,
           Sb0R2::Anchor::Exact, 1, 1, 0, 0);
  }
  // 4. Referenced data page hash mismatch: page 10 bank 1 in record 1.
  {
    Disk disk = healthyDisk();
    disk.pages[Overlay::Data1 + 10][Block - 1] ^= 1;
    expect("data-crc", disk, Overlay::Open::Failed, Sb0R2::Fault::DataCrc,
           Sb0R2::Anchor::Exact, 1, 1, 3, 2);
  }
  // 5. Anchor non-zero and not the expected SB0.
  {
    Disk disk = healthyDisk();
    std::memset(disk.pages[0].data(), 0xa5, Block);
    expect("anchor-other", disk, Overlay::Open::Failed, Sb0R2::Fault::Sb0Foreign,
           Sb0R2::Anchor::Other, 0, UINT32_MAX, 0, 0);
  }
  // 6. Anchor zero (no committed SB0).
  {
    Disk disk;
    expect("anchor-zero", disk, Overlay::Open::Failed, Sb0R2::Fault::Sb0Empty,
           Sb0R2::Anchor::Zero, 0, UINT32_MAX, 0, 0);
  }
  // 7. Valid header with a non-initial generation: exact-byte status is OTHER.
  {
    Disk disk = freshDisk();
    Page &sb0 = disk.pages[0];
    putLE(sb0.data() + 24, 1, 8);   // generation
    putLE(sb0.data() + 80, 0, 8);   // count
    putLE(sb0.data() + 72, 0, 4);   // head
    putLE(sb0.data() + Block - 16, 1, 8);
    sealHeader(sb0);
    expect("not-initial", disk, Overlay::Open::Failed, Sb0R2::Fault::NotInitial,
           Sb0R2::Anchor::Other, 1, UINT32_MAX, 0, 0);
  }
  // 8. SB1 must be empty; a valid SB1 is refused by disposable admission.
  {
    Disk disk = freshDisk();
    disk.pages[1] = disk.pages[0];
    putLE(disk.pages[1].data() + 12, 1, 4);
    putLE(disk.pages[1].data() + Block - 8, 1, 4);
    sealHeader(disk.pages[1]);
    expect("sb1-present", disk, Overlay::Open::Failed, Sb0R2::Fault::Sb1Present,
           Sb0R2::Anchor::Exact, 1, UINT32_MAX, 0, 0);
  }
  // 9. Map CRC mismatch (map byte changed, SB0 still exact).
  {
    Disk disk = freshDisk();
    disk.pages[Overlay::Map0][0] ^= 1;
    expect("map-crc", disk, Overlay::Open::Failed, Sb0R2::Fault::MapCrc,
           Sb0R2::Anchor::Exact, 1, UINT32_MAX, 0, 0);
  }
  // 10. Ring sequence gap: record 1 removed, record 2 is not the next slot.
  {
    Disk disk = healthyDisk();
    disk.pages[Overlay::Log + 1].fill(0);
    expect("sequence-gap", disk, Overlay::Open::Failed, Sb0R2::Fault::Chain,
           Sb0R2::Anchor::Exact, 1, 2, 0, 0);
  }
  // 11. Log header CRC damaged while the block CRC is resealed.
  {
    Disk disk = healthyDisk();
    disk.pages[Overlay::Log][72] ^= 1;
    sealBlock(disk.pages[Overlay::Log]);
    expect("log-header-crc", disk, Overlay::Open::Failed, Sb0R2::Fault::LogFormat,
           Sb0R2::Anchor::Exact, 1, 0, 0, 0);
  }

  // 11b. The first bad record's parsed fields and offending entry are reported.
  {
    Disk disk = healthyDisk();
    disk.pages[Overlay::Data1 + 10][Block - 1] ^= 1;
    const auto d = diagnose(disk);
    assert(d.badGen == 2 && d.badEpoch == 0 && d.badCount == 1);
    assert(d.badPage == 10 && d.badBank == 1);
    char lines[8][128] = {};
    const unsigned n = Sb0R2::detail(d, lines, 8);
    assert(n == 6);
    assert(std::strstr(lines[4], "RECORD GEN=2 EPOCH=0 N=1"));
    assert(std::strstr(lines[5], "ENTRY PAGE=10 BANK=1"));
    std::printf("  %s\n  %s\n", lines[4], lines[5]);
  }

  // 11c. Same slot reads valid once, then all-zero: both open() and R2 must
  // refuse; the reverse scan must not treat Empty as success or skip pages.
  {
    Disk disk = healthyDisk();
    disk.zeroSecondReadAt = Overlay::Log;
    expect("reread-empty", disk, Overlay::Open::Failed, Sb0R2::Fault::LogEmpty,
           Sb0R2::Anchor::Exact, 1, 0, 3, 3);
    std::puts("PASS reverse re-read: Empty is a non-None refusal");
  }

  // 11d. Production adapter address translation. The parser speaks relative
  // pages; Sb0R2::Sb0R2Port is the only translation point.
  {
    RecordingPort rec;
    rec.disk = healthyDisk();
    Sb0R2::Sb0R2Port<RecordingPort> mapped{rec};
    std::memset(&diagWorkspace, 0, sizeof diagWorkspace);
    std::memset(&diagSeen, 0, sizeof diagSeen);
    Sb0R2::Diagnosis d;
    Sb0R2::parse(mapped, Disposable::Seed, initialPayload().data(),
                 diagWorkspace, diagSeen, d);
    assert(d.fault == Sb0R2::Fault::None && d.pages == 3);
    assert(rec.lbas.size() == d.read);
    assert(rec.lbas[0] == Overlay::Media.first);
    assert(rec.lbas[1] == Overlay::Media.first + 1);
    for (uint32_t i = 0; i < 2 * Overlay::MapBlocks; ++i)
      assert(rec.lbas[2 + i] == Overlay::Media.first + Overlay::Map0 + i);
    const size_t ring = 2 + 2 * Overlay::MapBlocks;
    for (uint32_t i = 0; i < Overlay::LogBlocks; ++i)
      assert(rec.lbas[ring + i] == Overlay::Media.first + Overlay::Log + i);
    const size_t after = ring + Overlay::LogBlocks;
    assert(rec.lbas.size() == after + 6);
    assert(rec.lbas[after + 0] == Overlay::Media.first + Overlay::Log + 2);
    assert(rec.lbas[after + 1] == Overlay::Media.first + Overlay::Data0 + 11);
    assert(rec.lbas[after + 2] == Overlay::Media.first + Overlay::Data0 + 12);
    assert(rec.lbas[after + 3] == Overlay::Media.first + Overlay::Log + 1);
    assert(rec.lbas[after + 4] == Overlay::Media.first + Overlay::Data1 + 10);
    assert(rec.lbas[after + 5] == Overlay::Media.first + Overlay::Log + 0);
    for (const auto lba : rec.lbas) assert(lba >= Overlay::Media.first);
    std::printf("PASS overlay address mapping: SB0=%llu SB1=%llu map=%llu ring=%llu data=%llu\n",
                (unsigned long long)rec.lbas[0], (unsigned long long)rec.lbas[1],
                (unsigned long long)rec.lbas[2], (unsigned long long)rec.lbas[ring],
                (unsigned long long)rec.lbas[after + 4]);
  }

  // 11e. Gate/preflight failure: no successful read means UNKNOWN, not ZERO.
  {
    Sb0R2::Diagnosis d;
    d.fault = Sb0R2::Fault::Guard;
    d.why = "no root layout";
    expectSummary(d, "NUWA SB0-R2 ANCHOR=UNKNOWN HDR=UNKNOWN REC=- REASON=GUARD PAGES=0 WRITES=0");
    char lines[8][128] = {};
    const unsigned n = Sb0R2::detail(d, lines, 8);
    assert(n >= 2);
    assert(std::strstr(lines[1], "SB0=UNKNOWN SB1=UNKNOWN HDR=UNKNOWN SLOT=?"));
    assert(std::strstr(lines[1], "GEN=? HEAD=? COUNT=? MAPCRC=?"));
    std::puts("PASS gate failure summary: ANCHOR/HDR are UNKNOWN");
  }

  // 11f. SB0 read failure: anchor, SB0 and SB1 are all UNKNOWN.
  {
    Disk disk = healthyDisk();
    disk.failAt = 0;
    const auto d = diagnose(disk);
    assert(d.fault == Sb0R2::Fault::Io && d.lba == 0);
    assert(d.anchor == Sb0R2::Anchor::Unknown);
    assert(d.sb0 == Sb0R2::Header::Unknown && d.sb1 == Sb0R2::Header::Unknown);
    expectSummary(d, "NUWA SB0-R2 ANCHOR=UNKNOWN HDR=UNKNOWN REC=- REASON=IO PAGES=0 WRITES=0");
    Overlay opened;
    assert(openVerdict(disk, opened) == Overlay::Open::Failed);
    std::puts("PASS SB0 read failure: ANCHOR/HDR are UNKNOWN");
  }

  // 11g. SB1 read failure: SB0 facts stay committed, SB1/HDR admission does not.
  {
    Disk disk = healthyDisk();
    disk.failAt = 1;
    const auto d = diagnose(disk);
    assert(d.fault == Sb0R2::Fault::Io && d.lba == 1);
    assert(d.anchor == Sb0R2::Anchor::Exact);
    assert(d.sb0 == Sb0R2::Header::Valid && d.sb1 == Sb0R2::Header::Unknown);
    expectSummary(d, "NUWA SB0-R2 ANCHOR=EXACT-SB0 HDR=1 REC=- REASON=IO PAGES=0 WRITES=0");
    char lines[8][128] = {};
    const unsigned n = Sb0R2::detail(d, lines, 8);
    assert(n >= 2);
    assert(std::strstr(lines[1], "SB0=VALID SB1=UNKNOWN HDR=1 SLOT=0"));
    Overlay opened;
    assert(openVerdict(disk, opened) == Overlay::Open::Failed);
    std::puts("PASS SB1 read failure: SB1=UNKNOWN, SB0 facts retained");
  }

  // 12. Formatting: healthy summary is one line inside the 80-column budget.
  {
    Disk disk = freshDisk();
    const auto d = diagnose(disk);
    char summary[2][96] = {};
    assert(Sb0R2::summary(d, summary) == 1);
    assert(std::strlen(summary[0]) <= 80);
    expectSummary(d, "NUWA SB0-R2 ANCHOR=EXACT-SB0 HDR=1 REC=- REASON=NONE PAGES=0 WRITES=0");
  }
  // 13. Formatting: over-budget line splits before REASON and keeps all fields.
  {
    Disk disk = freshDisk();
    auto d = diagnose(disk);
    d.pages = 100000;
    d.fault = Sb0R2::Fault::BankTarget;
    d.rec = 511;
    char summary[2][96] = {};
    assert(Sb0R2::summary(d, summary) == 2);
    assert(std::strlen(summary[0]) <= 80 && std::strlen(summary[1]) <= 80);
    assert(std::strstr(summary[0], "ANCHOR=EXACT-SB0") &&
           std::strstr(summary[0], "HDR=1") &&
           std::strstr(summary[0], "REC=511"));
    assert(std::strstr(summary[1], "REASON=BANK-MISMATCH") &&
           std::strstr(summary[1], "PAGES=100000") &&
           std::strstr(summary[1], "WRITES=0"));
    expectSummary(d, summary[0], summary[1]);
  }
  // 14. Deterministic single-bit mutation cross-check: every verdict must
  // agree with the production open() on the same bytes.
  {
    uint32_t state = 0x12345678;
    const auto rnd = [&] {
      state = state * 1664525U + 1013904223U;
      return state;
    };
    for (unsigned iter = 0; iter < 300; ++iter) {
      Disk disk = healthyDisk();
      std::vector<uint64_t> keys;
      for (const auto &entry : disk.pages) keys.push_back(entry.first);
      const auto key = keys[rnd() % keys.size()];
      disk.pages[key][rnd() % Block] ^= uint8_t(1U << (rnd() & 7));
      Overlay overlay;
      const auto open = openVerdict(disk, overlay);
      const auto d = diagnose(disk);
      const bool replayOk = d.fault == Sb0R2::Fault::None;
      if ((open == Overlay::Open::Resumed) != replayOk) {
        std::printf("MISMATCH iter=%u lba=%llu open=%s fault=%s\n", iter,
                    (unsigned long long)key,
                    open == Overlay::Open::Resumed ? "RESUMED" : "FAILED",
                    Sb0R2::faultName(d.fault));
        std::abort();
      }
    }
    std::puts("PASS mutation cross-check: 300 single-bit mutations agree with open()");
  }

  std::puts("PASS SB0-R2 host fixture: fresh, healthy, log CRC, data CRC, anchor OTHER, "
            "zero anchor, non-initial header, SB1, map CRC, sequence, header CRC, split");
  return 0;
}
