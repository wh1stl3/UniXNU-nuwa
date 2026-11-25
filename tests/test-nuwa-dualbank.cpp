// SPDX-License-Identifier: BSD-2-Clause
#include "../package/nuwa-data-write/DualBankLogOverlay.h"

#include <array>
#include <cstdio>
#include <cstdlib>
#include <memory>
#include <unordered_map>
#include <vector>

using namespace NuwaData;
using Full = DualBankLogOverlay<>;
using Small = DualBankLogOverlay<4>;
using Page = std::array<uint8_t, Block>;
static const uint8_t Seed[32] = {0x26, 0x11, 0x20, 0x26};
static const Page SeedPage = [] { Page p{}; p.fill(0x5e); return p; }();
static const char *test;

#define CHECK(x) do { \
  if (!(x)) { std::fprintf(stderr, "%s:%d (%s): %s\n", __FILE__, __LINE__, test, #x); std::abort(); } \
} while (false)

enum class Cut { Before, After, Prefix, Suffix, Mixed };
struct Event { char kind; uint64_t lba; };
struct Disk {
  uint64_t limit = Full::Media.blocks, failRead = UINT64_MAX;
  std::unordered_map<uint64_t, Page> pages;
  std::vector<Event> events;
  size_t fault = SIZE_MAX, writes = 0;
  Cut cut = Cut::Before;

  bool read(uint64_t lba, uint32_t n, void *dst) const {
    CHECK(n == 1 && lba < limit);
    if (lba == failRead) return false;
    const auto i = pages.find(lba);
    if (i == pages.end()) memset(dst, 0, Block);
    else memcpy(dst, i->second.data(), Block);
    return true;
  }
  bool write(uint64_t lba, uint32_t n, const void *src) {
    CHECK(n == 1 && lba < limit);
    ++writes;
    const bool fail = events.size() == fault;
    events.push_back({'W', lba});
    if (fail && cut == Cut::Before) return false;
    const auto *s = static_cast<const uint8_t *>(src);
    auto &d = pages[lba];
    if (!fail || cut == Cut::After) memcpy(d.data(), s, Block);
    else if (cut == Cut::Prefix) memcpy(d.data(), s, 512);
    else if (cut == Cut::Suffix) memcpy(d.data() + 3584, s + 3584, 512);
    else {
      memcpy(d.data(), s, 512);
      memcpy(d.data() + 3584, s + 3584, 512);
    }
    return !fail;
  }
  bool sync() {
    const bool fail = events.size() == fault;
    events.push_back({'S', 0});
    return !fail;
  }
  void arm(size_t at, Cut mode) {
    events.clear();
    writes = 0;
    fault = at;
    cut = mode;
  }
};

template<class O> struct Handle {
  O overlay;
  std::unique_ptr<typename O::Workspace> workspace{new typename O::Workspace};
  typename O::Open open(Disk &disk, bool write = true, bool create = true) {
    const auto w = disk.writes, e = disk.events.size();
    const std::unique_ptr<typename O::SeenScratch> seen{new typename O::SeenScratch};
    const auto opened = overlay.open(disk, Seed, *workspace, *seen, write, create);
    CHECK(disk.writes == w && disk.events.size() == e);
    return opened;
  }
};

static Page payload(uint32_t n) {
  Page p;
  for (size_t i = 0; i < p.size(); ++i)
    p[i] = uint8_t((n * 29 + (n >> 8) + i / 16) ^ (i * 13));
  return p;
}
template<class O> static Page visible(Handle<O> &h, Disk &disk, uint64_t page) {
  if (!h.overlay.has(page)) return SeedPage;
  Page actual{};
  CHECK(h.overlay.read(disk, page, actual.data()));
  return actual;
}
template<class O> static void putPage(Handle<O> &h, Disk &disk, uint64_t page, uint32_t value) {
  const auto p = payload(value);
  CHECK(h.overlay.writeRun(disk, page, 1, p.data()));
}
static void put(Page &p, size_t off, uint64_t value, unsigned count = 4) {
  while (count--) { p[off++] = uint8_t(value); value >>= 8; }
}
static void reseal(Page &p, size_t header, size_t headerCrc) {
  put(p, headerCrc, crc(p.data(), header, headerCrc));
  put(p, 4092, crc(p.data(), p.size(), 4092));
}
static void checkEvent(const Disk &d, size_t at, char kind, uint64_t lba = 0) {
  CHECK(at < d.events.size() && d.events[at].kind == kind && d.events[at].lba == lba);
}

static void layout() {
  static_assert(Full::Pages == 2097152 && Full::MapBlocks == 64 && Full::LogBlocks == 512);
  static_assert(Full::Map0 == 2 && Full::Map1 == 130 && Full::Log == 258);
  static_assert(Full::Data0 == 770 && Full::Data1 == 2097922);
  static_assert(Full::Media.first == 57393401 && Full::Media.blocks == 4195074 &&
                Full::Media.first + Full::Media.blocks == 61588475);
  static_assert(Full::overlayBlocks(Full::Pages) == 4195074 && !Full::overlayBlocks(Full::Pages - 1));
  const auto end = Full::Media.first + Full::Media.blocks;
  CHECK(Full::Media.contains(0, Block, end - 1, 1));
  CHECK(!Full::Media.contains(0, Block, end, 1));
  CHECK(!Full::Media.contains(0, Block, end - 1, 2));
  CHECK(!Full::Media.contains(0, Block, Full::Media.first - 1, 1));
  CHECK(!Full::Media.contains(1, Block, end - 1, 1));
  CHECK(!Full::Media.contains(0, 512, end - 1, 1));
  CHECK(crc(reinterpret_cast<const uint8_t *>("123456789"), 9) == 0xcbf43926u);

  Disk d;
  Handle<Full> h;
  CHECK(h.open(d, false) == Full::Open::Empty && !h.overlay.writable());
  CHECK(h.open(d, true, false) == Full::Open::Empty && !h.overlay.writable());
  CHECK(h.open(d) == Full::Open::Empty && h.overlay.writable());
  CHECK(!h.overlay.has(Full::Pages) && !h.overlay.read(d, Full::Pages, nullptr));
  const auto p = payload(1);
  CHECK(!h.overlay.writeRun(d, Full::Pages - 1, 2, p.data()) && d.writes == 0);
  CHECK(h.open(d) == Full::Open::Empty);
  CHECK(!h.overlay.writeRun(d, 0, 251, p.data()) && d.writes == 0);
  CHECK(h.open(d) == Full::Open::Empty);
  CHECK(!h.overlay.writeRun(d, UINT64_MAX, 1, p.data()) && d.writes == 0);
  CHECK(h.open(d) == Full::Open::Empty);
  CHECK(!h.overlay.writeRun(d, 0, 0, p.data()) && d.writes == 0);
  CHECK(h.open(d) == Full::Open::Empty);
  std::vector<Page> maxRun(Full::MaxRun, p);
  const auto first = Full::Pages - maxRun.size();
  CHECK(h.overlay.writeRun(d, first, Full::MaxRun, maxRun.data()));
  checkEvent(d, 0, 'W', 0);
  checkEvent(d, 1, 'S');
  checkEvent(d, 2, 'W', Full::Data0 + first);
  checkEvent(d, 251, 'W', Full::Data1 - 1);
  checkEvent(d, 252, 'S');
  checkEvent(d, 253, 'W', Full::Log);
  checkEvent(d, 254, 'S');
  const auto &sb = d.pages.at(0);
  CHECK(!memcmp(sb.data(), "NUWADSB3", 8) && le32(sb.data() + 8) == 3 &&
        le64(sb.data() + 16) == Full::Pages && le64(sb.data() + 24) == 0 &&
        le32(sb.data() + 64) == 64 && le32(sb.data() + 68) == 512 &&
        le32(sb.data() + 92) == crc(sb.data(), 96, 92) &&
        le32(sb.data() + 4092) == crc(sb.data(), Block, 4092));
  const auto &rec = d.pages.at(Full::Log);
  CHECK(!memcmp(rec.data(), "NUWADLOG", 8) && le32(rec.data() + 64) == 250 &&
        le64(rec.data() + 80) == first && le32(rec.data() + 88) == crc(p.data(), Block) &&
        le64(rec.data() + 4080) == 1 && le32(rec.data() + 4092) == crc(rec.data(), Block, 4092));
  CHECK(h.open(d) == Full::Open::Resumed);
  CHECK(visible(h, d, Full::Pages - 1) == p);
  putPage(h, d, Full::Pages - 1, 2);
  CHECK(d.pages.at(Full::Media.blocks - 1) == payload(2));
}

static void alternating() {
  Disk d;
  Handle<Full> h;
  CHECK(h.open(d) == Full::Open::Empty);
  for (uint32_t i = 0; i < 5; ++i) {
    putPage(h, d, 7, 10 + i);
    CHECK(d.pages.at((i % 2 ? Full::Data1 : Full::Data0) + 7) == payload(10 + i));
    if (i) CHECK(d.pages.at((i % 2 ? Full::Data0 : Full::Data1) + 7) == payload(9 + i));
    CHECK(h.open(d) == Full::Open::Resumed && h.overlay.generation() == i + 1);
    CHECK(visible(h, d, 7) == payload(10 + i));
  }
}

static void tornData() {
  for (const auto page : {uint64_t(7), Full::LegacyHeader1 - Full::Data0}) {
    for (uint32_t prior = 0; prior <= 2; ++prior) {
      for (const auto cut : {Cut::Prefix, Cut::Suffix, Cut::Mixed}) {
        Disk d;
        Handle<Full> h;
        CHECK(h.open(d) == Full::Open::Empty);
        for (uint32_t i = 1; i <= prior; ++i) putPage(h, d, page, i);
        d.arm(prior ? 0 : 2, cut);
        const auto p = payload(3);
        CHECK(!h.overlay.writeRun(d, page, 1, p.data()) && !h.overlay.writable());
        CHECK(h.open(d) == Full::Open::Resumed && h.overlay.generation() == prior);
        CHECK(visible(h, d, page) == (prior ? payload(prior) : SeedPage));
      }
    }
  }
}

static void tornLog() {
  // Whole run has live bytes in all eight sectors, including the middle
  // discarded by the mixed tear. Cover both a zero and a stale ring target.
  for (const auto wrapped : {false, true}) {
    for (const auto cut : {Cut::Prefix, Cut::Suffix, Cut::Mixed}) {
      Disk d;
      d.limit = Small::Media.blocks;
      Handle<Small> h;
      CHECK(h.open(d) == Small::Open::Empty);
      std::vector<Page> run(Small::MaxRun);
      for (uint32_t i = 0; i < run.size(); ++i) run[i] = payload(100 + i);
      if (wrapped) {
        for (uint32_t i = 0; i < Small::LogBlocks; ++i)
          CHECK(h.overlay.writeRun(d, 7, Small::MaxRun, run.data()));
      }
      const auto gen = h.overlay.generation();
      std::vector<Page> next(Small::MaxRun, payload(700));
      const auto logOp = (wrapped ? 131U : 2U) + Small::MaxRun + 1;
      d.arm(logOp, cut);
      CHECK(!h.overlay.writeRun(d, 7, Small::MaxRun, next.data()));
      checkEvent(d, logOp, 'W', Small::Log);
      CHECK(h.open(d) == Small::Open::Resumed && h.overlay.generation() == gen);
      for (uint32_t i = 0; i < run.size(); ++i)
        CHECK(visible(h, d, 7 + i) == (wrapped ? run[i] : SeedPage));
      d.arm(SIZE_MAX, Cut::Before);
      CHECK(h.overlay.writeRun(d, 7, Small::MaxRun, next.data()));
      CHECK(h.open(d) == Small::Open::Resumed && h.overlay.generation() == gen + 1);
    }
  }
}

static void runCuts() {
  constexpr uint32_t count = 32;
  const std::vector<Page> fresh(count, payload(100));
  Disk base;
  Handle<Full> init;
  CHECK(init.open(base) == Full::Open::Empty);
  for (uint32_t i = 0; i < count / 2; ++i) putPage(init, base, i, i);
  for (size_t at = 0; at < count + 3; ++at) {
    for (const auto cut : {Cut::Before, Cut::After}) {
      auto d = base;
      Handle<Full> h;
      CHECK(h.open(d) == Full::Open::Resumed);
      d.arm(at, cut);
      CHECK(!h.overlay.writeRun(d, 0, count, fresh.data()));
      const auto attempts = d.events.size();
      CHECK(!h.overlay.writeRun(d, 0, count, fresh.data()) && d.events.size() == attempts);
      const bool committed = at == count + 2 || (at == count + 1 && cut == Cut::After);
      CHECK(h.open(d) == Full::Open::Resumed);
      CHECK(h.overlay.generation() == count / 2 + committed);
      for (uint32_t i = 0; i < count; ++i)
        CHECK(visible(h, d, i) == (committed ? fresh[i] : (i < count / 2 ? payload(i) : SeedPage)));
    }
  }
}

template<class O> static void checkpointCuts(unsigned rounds) {
  Disk base;
  base.limit = O::Media.blocks;
  Handle<O> h;
  CHECK(h.open(base) == O::Open::Empty);
  for (unsigned round = 0; round < rounds; ++round) {
    const auto gen = uint64_t(round + 1) * O::LogBlocks;
    while (h.overlay.generation() < gen)
      putPage(h, base, 7, uint32_t(h.overlay.generation() + 1));
    CHECK(h.overlay.generation() == gen);
    constexpr size_t bmp = 2 * O::MapBlocks;
    for (size_t at = 0; at <= bmp + 6; ++at) {
      for (const auto cut : {Cut::Before, Cut::After, Cut::Prefix, Cut::Suffix, Cut::Mixed}) {
        if (cut != Cut::Before && cut != Cut::After &&
            at != 0 && at != O::MapBlocks && at != bmp + 1) continue;
        auto d = base;
        CHECK(h.open(d) == O::Open::Resumed && h.overlay.generation() == gen);
        d.arm(at, cut);
        const auto p = payload(uint32_t(gen + 1));
        CHECK(!h.overlay.writeRun(d, 7, 1, p.data()));
        const auto next = (round & 1) ^ 1U;
        if (at < bmp) checkEvent(d, at, 'W', (next ? O::Map1 : O::Map0) + at);
        if (at == bmp) checkEvent(d, at, 'S');
        if (at == bmp + 1) checkEvent(d, at, 'W', next);
        CHECK(h.open(d) == O::Open::Resumed);
        const bool committed = at == bmp + 6 || (at == bmp + 5 && cut == Cut::After);
        CHECK(h.overlay.generation() == gen + committed);
        CHECK(visible(h, d, 7) == payload(uint32_t(gen + committed)));
      }
    }
    CHECK(h.open(base) == O::Open::Resumed && h.overlay.generation() == gen);
    putPage(h, base, 7, uint32_t(gen + 1));
  }
}

static void bootstrapCuts() {
  for (size_t at = 0; at < 2; ++at) {
    for (const auto cut : {Cut::Before, Cut::After, Cut::Prefix, Cut::Suffix, Cut::Mixed}) {
      Disk d;
      d.limit = Small::Media.blocks;
      Handle<Small> h;
      CHECK(h.open(d) == Small::Open::Empty);
      d.arm(at, cut);
      CHECK(!h.overlay.writeRun(d, 0, 1, SeedPage.data()));
      const auto want = at != 0 || cut == Cut::After || cut == Cut::Mixed ? Small::Open::Resumed :
                        cut == Cut::Before ? Small::Open::Empty : Small::Open::Failed;
      CHECK(h.open(d) == want);
      if (want != Small::Open::Failed)
        CHECK(h.overlay.generation() == 0 && !h.overlay.has(0));
    }
  }
}

static void wrap() {
  Disk d;
  d.limit = Small::Media.blocks;
  Handle<Small> h;
  CHECK(h.open(d) == Small::Open::Empty);
  // Persist the empty anchor, then synthesize a nonzero, sealed head.
  d.arm(2, Cut::Before);
  const auto p = payload(1);
  CHECK(!h.overlay.writeRun(d, 0, 1, p.data()));
  auto &sb = d.pages.at(0);
  put(sb, 72, 3);
  reseal(sb, 96, 92);
  CHECK(h.open(d) == Small::Open::Resumed);
  for (uint32_t i = 0; i < 3 * Small::LogBlocks + 1; ++i) {
    d.arm(SIZE_MAX, Cut::Before);
    putPage(h, d, 31, i + 1);
    checkEvent(d, d.events.size() - 2, 'W', Small::Log + (3 + i) % Small::LogBlocks);
    CHECK(h.open(d) == Small::Open::Resumed && h.overlay.generation() == i + 1);
    CHECK(visible(h, d, 31) == payload(i + 1));
  }
}

template<class O> static void expectFailed(Disk &d) {
  d.arm(SIZE_MAX, Cut::Before);
  Handle<O> h;
  CHECK(h.open(d) == O::Open::Failed && !h.overlay.ready() && !h.overlay.writable());
  CHECK(!h.overlay.writeRun(d, 0, 1, SeedPage.data()));
  CHECK(d.writes == 0 && d.events.empty());
}

static void failClosed() {
  for (const auto lba : {uint64_t(0), uint64_t(1), Full::Map0, Full::Map1, Full::Log,
                         Full::Data0 - 1, Full::LegacyHeader0, Full::LegacyHeader1}) {
    Disk d;
    d.pages[lba][20] = 1;
    expectFailed<Full>(d);
  }
  Disk base;
  base.limit = Small::Media.blocks;
  Handle<Small> h;
  CHECK(h.open(base) == Small::Open::Empty);
  for (uint32_t i = 1; i <= Small::LogBlocks + 2; ++i) putPage(h, base, 15, i);
  const size_t firstLog = Small::Log;
  for (const auto lba : {uint64_t(0), Small::Map1, Small::Log + 2, Small::Data1 + 15}) {
    auto d = base;
    d.failRead = lba;
    expectFailed<Small>(d);
  }
  {
    auto d = base;
    d.pages.at(0)[0] ^= 1; // foreign alternate, even with a valid latest SB
    expectFailed<Small>(d);
  }
  {
    auto d = base;
    d.pages.at(Small::Map1)[1] ^= 1; // latest BMP CRC; no fallback to SB0
    expectFailed<Small>(d);
  }
  for (unsigned mode = 0; mode < 6; ++mode) {
    auto d = base;
    auto &sb = d.pages.at(1);
    if (mode == 0) put(sb, 80, 0, 8); // count differs from bitmap
    if (mode == 1) put(sb, 72, Small::LogBlocks);
    if (mode == 2) sb[32] ^= 1; // seed mismatch
    if (mode == 3) put(sb, 4088, 0); // tail slot mismatch
    if (mode == 4) {
      put(sb, 24, 0, 8); // equally new SBs
      put(sb, 4080, 0, 8);
    }
    if (mode == 5) {
      d.pages[Small::Map1 + Small::MapBlocks][0] |= 1; // active without present
      std::vector<Page> maps(2 * Small::MapBlocks);
      for (uint32_t i = 0; i < maps.size(); ++i)
        CHECK(d.read(Small::Map1 + i, 1, maps[i].data()));
      put(sb, 88, crc(reinterpret_cast<const uint8_t *>(maps.data()), maps.size() * Block));
    }
    reseal(sb, 96, 92);
    expectFailed<Small>(d);
  }
  for (unsigned mode = 0; mode < 18; ++mode) {
    auto d = base;
    auto &rec = d.pages.at(firstLog);
    if (mode == 0) rec.fill(0); // hole followed by same epoch
    if (mode == 1) rec[100] = 1; // CRC break followed by same epoch
    if (mode == 2) { // two corrupt slots at/after frontier
      d.pages.at(firstLog + 2)[90] ^= 1;
      d.pages.at(firstLog + 3)[91] ^= 1;
    }
    if (mode == 3) { put(rec, 24, 9, 8); put(rec, 16, 10, 8); put(rec, 4080, 10, 8); }
    if (mode == 4) put(rec, 64, 251);
    if (mode == 5) put(rec, 64, 0);
    if (mode == 6) put(rec, 80, Small::Pages, 8);
    if (mode == 7) rec[92] = 2;
    if (mode == 8) rec[92] = 1; // semantically wrong bank
    if (mode == 9) rec[93] = 1;
    if (mode == 10) rec[32] ^= 1;
    if (mode == 11) put(rec, 12, 1);
    if (mode == 12) put(rec, 4080, 0, 8);
    if (mode == 13) { put(rec, 16, 6, 8); put(rec, 4080, 6, 8); }
    if (mode == 14) d.pages.at(Small::Data1 + 15)[100] ^= 1; // newest page bad
    if (mode == 15) { // duplicate entry within one run
      put(rec, 64, 2);
      memcpy(rec.data() + 96, rec.data() + 80, 16);
    }
    if (mode == 16) { // newer epoch after a clean frontier, independently of the prefix
      auto &late = d.pages.at(firstLog + 3);
      put(late, 24, 8, 8);
      put(late, 16, 12, 8);
      put(late, 4080, 12, 8);
      reseal(late, 80, 72);
    }
    if (mode == 17) { // a sealed record may not include stray unused entries
      rec[96] = 1;
    }
    if (mode >= 3 && mode != 14 && mode != 16) reseal(rec, 80, 72);
    expectFailed<Small>(d);
  }
  {
    auto d = base;
    d.pages.at(Small::Data0 + 15)[100] ^= 1; // superseded page is not checked
    CHECK(h.open(d) == Small::Open::Resumed && visible(h, d, 15) == payload(6));
  }
  {
    Disk d;
    CHECK(h.open(d) == Small::Open::Empty);
    d.arm(0, Cut::Prefix); // first anchor is torn; do not create over it
    CHECK(!h.overlay.writeRun(d, 0, 1, SeedPage.data()));
    expectFailed<Small>(d);
  }
}

static void writeAmplification() {
  for (const uint32_t run : {1U, 32U}) {
    Disk d;
    Handle<Full> h;
    CHECK(h.open(d) == Full::Open::Empty);
    const std::vector<Page> pages(run, payload(1));
    CHECK(h.overlay.writeRun(d, 0, run, pages.data()));
    d.arm(SIZE_MAX, Cut::Before);
    // One entire steady-state cycle (512 runs inclusive of one checkpoint).
    for (uint32_t i = 0; i < Full::LogBlocks; ++i)
      CHECK(h.overlay.writeRun(d, 0, run, pages.data()));
    const auto user = Full::LogBlocks * run;
    CHECK(d.writes == user + Full::LogBlocks + 129);
    const double ratio = double(d.writes) / user;
    if (run == 1) CHECK(ratio >= 2.2515 && ratio < 2.2525);
    else CHECK(ratio >= 1.01 && ratio <= 1.04);
    std::printf("  %2u page/run: %zu/%u = %.6fx\n", run, d.writes, user, ratio);
  }
}

int main() {
  const auto run = [](const char *name, void (*fn)()) {
    test = name;
    fn();
    std::printf("PASS %s\n", name);
  };
  run("layout and boundaries", layout);
  run("bank alternation", alternating);
  run("torn data (first write and overwrite)", tornData);
  run("torn log (prefix, suffix, mixed; empty and stale targets)", tornLog);
  run("multi-page run power cuts", runCuts);
  run("checkpoint power cuts (bootstrap, L=4 and L=512)", [] {
    bootstrapCuts();
    checkpointCuts<Small>(2);
    checkpointCuts<Full>(1);
  });
  run("ring wrap", wrap);
  run("fail-closed matrix", failClosed);
  run("write amplification", writeAmplification);
}
