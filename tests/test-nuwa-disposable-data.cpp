// SPDX-License-Identifier: BSD-2-Clause
#include <array>
#include <cassert>
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <map>
#include <vector>
#include "../package/nuwa-data-write/DisposableData.h"

using namespace NuwaData;
using Overlay = DualBankLogOverlay<2, true>;
using Production = DualBankLogOverlay<2>;
static Overlay::Workspace w;
static Overlay::SeenScratch seen;

struct Ops {
  std::map<uint64_t, std::array<uint8_t, Block>> pages;
  std::vector<uint64_t> events;
  unsigned failAt = 0;
  bool read(uint64_t b, unsigned n, void *d) {
    assert(n == 1);
    auto p = pages.find(b);
    if (p == pages.end()) memset(d, 0, Block);
    else memcpy(d, p->second.data(), Block);
    return true;
  }
  bool issue(uint64_t b) {
    events.push_back(b);
    return !failAt || events.size() != failAt;
  }
  bool write(uint64_t b, unsigned n, const void *s) {
    assert(n == 1 && b >= Overlay::Log && b < Overlay::Media.blocks);
    if (!issue(b)) return false;
    memcpy(pages[b].data(), s, Block);
    return true;
  }
  bool sync() { return issue(UINT64_MAX); }
};

int main() {
  using Open = Overlay::Open;
  static constexpr auto &seed = Disposable::Seed;
  uint8_t wrong[32]{};
  Ops ops;
  Overlay x;
  assert(x.open(ops, seed, w, seen, true, true) == Open::Failed);
  assert(ops.events.empty());
  static Production::Workspace prod{};
  assert(Production::initialSuperblock(prod.block, seed, prod));
  memcpy(ops.pages[0].data(), prod.block, Block);
  assert(x.open(ops, seed, w, seen, true, true) == Open::Failed);
  assert(Overlay::initialSuperblock(w.block, seed, w));
  memcpy(ops.pages[0].data(), w.block, Block);
  assert(x.open(ops, wrong, w, seen, true, true) == Open::Failed);
  assert(ops.events.empty());
  ops.pages[Overlay::Data0 + 7].fill(0xc5); // stale preimage, not part of fresh Data
  assert(x.open(ops, seed, w, seen, true, false) == Open::Resumed);
  assert(x.generation() == 0 && x.presentCount() == 0 && x.writable() && !x.has(7));

  std::array<uint8_t, Block> page{};
  page.fill(0x6a);
  const Ops fresh = ops;
  for (unsigned fail = 1; fail <= 4; ++fail) {
    Ops interrupted = fresh;
    interrupted.failAt = fail;
    Overlay trial;
    assert(trial.open(interrupted, seed, w, seen, true, false) == Open::Resumed);
    assert(!trial.writeRun(interrupted, 7, 1, page.data()));
    assert(!trial.writeRun(interrupted, 7, 1, page.data()));
    assert(interrupted.events.size() == fail && !trial.ready());
  }
  assert(x.writeRun(ops, 7, 1, page.data()));
  assert((ops.events == std::vector<uint64_t>{Overlay::Data0 + 7, UINT64_MAX, Overlay::Log, UINT64_MAX}));
  Overlay y;
  assert(y.open(ops, seed, w, seen, true, false) == Open::Resumed);
  assert(y.generation() == 1 && y.presentCount() == 1 && y.has(7));
  std::array<uint8_t, Block> dst{};
  assert(y.read(ops, 7, dst.data()) && dst == page);
  Ops corrupt = ops;
  corrupt.pages[Overlay::Log][2] ^= 1;
  assert(x.open(corrupt, seed, w, seen, true, true) == Open::Failed);
  corrupt = ops;
  corrupt.pages[Overlay::Data0 + 7][Block - 1] ^= 1;
  assert(x.open(corrupt, seed, w, seen, true, true) == Open::Failed);
  corrupt = ops;
  corrupt.pages[1][3] ^= 1;
  assert(x.open(corrupt, seed, w, seen, true, true) == Open::Failed);

  assert(y.open(ops, seed, w, seen, true, false) == Open::Resumed);
  page.fill(0x74);
  assert(y.writeRun(ops, 7, 1, page.data()));
  assert(y.generation() == 2 && !y.writable());
  assert((ops.events == std::vector<uint64_t>{Overlay::Data0 + 7, UINT64_MAX, Overlay::Log, UINT64_MAX,
                                              Overlay::Data1 + 7, UINT64_MAX, Overlay::Log + 1, UINT64_MAX}));
  assert(!y.writeRun(ops, 7, 1, page.data()) && ops.events.size() == 8);
  assert(x.open(ops, seed, w, seen, true, false) == Open::Resumed);
  assert(!x.writable() && x.read(ops, 7, dst.data()) && dst == page);
  puts("PASS disposable: no runtime creation, seed/format/corruption rejection, ordered completion, replay, no rollover");
}
