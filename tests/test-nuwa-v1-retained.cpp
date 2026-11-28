// SPDX-License-Identifier: BSD-2-Clause
#include "NuwaDataFixtureGpt.h"
#include "../package/nuwa-data-write/Descriptor.h"
#include "../package/nuwa-data-write/DisposableData.h"
#include "../package/nuwa-data-write/Provider.h"
#include "../package/nuwa-ramblock/PersistOpenReason.h"
#include "DirectDisk.h"
#include <algorithm>
#include <array>
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <future>
#include <map>
#include <mutex>
#include <string_view>
#include <vector>
#include "TransferPoll.h"
#include "PreservedNop.h"
#include "CombinedRead.h"
#include "RootReadSession.h"

using namespace NuwaData;
using Page = std::array<uint8_t, Block>;
constexpr uint64_t Pages = 2097152, First = 59491258;
static const uint64_t Size = persist::windowBlocks(Pages);
constexpr auto Legacy = DualBankLogOverlay<>::Media;
static FixtureGpt gptFixture;
static const auto &nuwaDataIdentity = gptFixture.id;
extern "C" { uint8_t native_ram_block_seed_sha256[32]; }
static uint64_t native_data_persist_loaded, native_data_persist_pages, native_data_persist_first_lba,
                native_data_persist_present, native_ram_block_resident_bytes;
static unsigned native_data_persist_gpt, native_data_persist_gpt_after, native_data_persist_header,
                native_data_persist_state;
static const char *nuwa_data_persist_open_why;
static constexpr unsigned kDefaultReserveMiB = 1024;
static constexpr uint64_t kLogReserveBlocks = 8192, kExportBlocks = 65536;
static struct { bool valid; uint64_t first, last, imageBytes; } gStoreGeometry;
static std::string_view scenario;
static bool prefix(std::string_view text) { return scenario.substr(0, text.size()) == text; }
static void *IOMallocZero(size_t n) { return calloc(1, n); }
static void IOFree(void *p, size_t) { free(p); }
static void IOLog(const char *, ...) {}
static bool PE_parse_boot_argn(const char *arg, void *ptr, size_t n) {
  assert(n == sizeof(uint32_t));
  if (!strcmp(arg, "sheng-data-persist")) *static_cast<uint32_t *>(ptr) = 2;
  else if (!strcmp(arg, "sheng-log-reserve") && scenario == "overlap-log")
    *static_cast<uint32_t *>(ptr) = 287;
  else if (!strcmp(arg, "sheng-data-reset") && (scenario == "reset" || prefix("sync-")))
    *static_cast<uint32_t *>(ptr) = 1;
  else return false;
  return true;
}
struct IOLock { std::mutex mutex; };
static IOLock hostLock;
static struct { bool ready, poisoned; IOLock *lock; } gHost{true, false, &hostLock};
static thread_local bool holdingHost;
static unsigned hostAcquires;
static void IOLockLock(IOLock *l) {
  l->mutex.lock();
  if (l == &hostLock) {
    assert(!holdingHost);
    holdingHost = true;
    ++hostAcquires;
  }
}
static void IOLockUnlock(IOLock *l) {
  if (l == &hostLock) {
    assert(holdingHost);
    holdingHost = false;
  } else {
    assert(!holdingHost);
  }
  l->mutex.unlock();
}

static struct Hardware {
  static constexpr uint32_t Dma = 0x10000;
  alignas(4096) uint8_t virt[CombinedRead::Bytes]{};
  std::map<uint64_t, Page> media;
  struct Event { uint8_t op, flags; unsigned n; uint64_t lba; };
  std::vector<Event> events;
  unsigned prepares = 0, syncs = 0, polls = 0;
  bool submitted = false, timedOut = false;
  std::promise<void> *writeRung = nullptr;
  std::future<void> *resume = nullptr;
  persist::Overlay *observeBits = nullptr;
  uint64_t observePage = 0;

  uint32_t sread(unsigned off) const {
    switch (off) {
      case 0: case 0xc00: return 0;
      case 0x20: return (1U << 30) | (1U << 27) | (7U << 9) | 1;
      case 0x24: return 1;
      case 0x28: return 0x1000;
      case 0x800: return 0x80000060;
      case 0x1000: return 0x1f000;
      case 0x1800: return 1;
      case 0x2000: return 0x0a9f0000;
      default: assert(false); return 0;
    }
  }
  uint32_t hread(unsigned off) {
    assert(holdingHost);
    switch (off) {
      case 0x34: case 0x60: return 1;
      case 0x30: return 11;
      case 0x50: return Dma;
      case 0x58: return doorbell();
      case 0x20: case 0x24: case 0x54: case 0x78: case 0x80: return 0;
      default: assert(false); return 0;
    }
  }
  bool prepare(uint64_t pa, CombinedRead::Command c, unsigned tag, unsigned block,
               uint64_t lba, unsigned n, const uint8_t *src, NuwaUfsDesc::Request desc) {
    assert(holdingHost && pa == Dma);
    ++prepares;
    return CombinedRead::encode(virt, pa, c, tag, block, lba, n, src, desc);
  }
  void hwrite(unsigned off, uint32_t val) {
    assert(holdingHost && !submitted && off == 0x58 && val == 1);
    submitted = true;
    polls = 0;
    const auto *u = virt + 4096;
    const auto *c = u + 16;
    auto *r = virt + 4608;
    auto *data = virt + CombinedRead::Data;
    assert(u[0] == 1 && !u[2]);
    r[0] = 0x21;
    r[3] = u[3];
    const auto lba = CombinedRead::be32(c + 2);
    const auto n = unsigned(c[7]) * 256 + c[8];
    assert(CombinedRead::be32(u + 12) == n * Block);
    assert((le32(virt + 28) & 0xffff) == unsigned(n != 0));
    if (n) assert(le64(virt + 5120) == Dma + CombinedRead::Data &&
                  le32(virt + 5132) == n * Block - 1 && n <= 32);
    events.push_back({c[0], c[1], n, lba});
    if (c[0] == 0x28) {
      assert(u[1] == 0x40 && n);
      for (unsigned i = 0; i < n; ++i) {
        auto it = media.find(lba + i);
        const auto *page = it == media.end() ? gptFixture.at(lba + i) : it->second.data();
        if (page) memcpy(data + i * Block, page, Block);
      }
    } else if (c[0] == 0x2a) {
      assert(c[1] == 8 && u[1] == 0x20 && n && Window({First, Size}).contains(0, Block, lba, n));
      assert((le32(virt) & (3U << 25)) == 1U << 25);
      if (observeBits) {
        const auto bitmap = First + 1 + observePage / (Block * 8);
        assert(observeBits->has(observePage) == (lba == bitmap));
      }
      if (writeRung) {
        writeRung->set_value();
        assert(resume->wait_for(std::chrono::seconds(2)) == std::future_status::ready);
        writeRung = nullptr;
      }
      for (unsigned i = 0; i < n; ++i)
        memcpy(media[lba + i].data(), data + i * Block, Block);
    } else {
      assert(c[0] == 0x35 && zero(c + 1, 9) && !u[1] && !(le32(virt) & (3U << 25)));
      ++syncs;
      if ((scenario == "sync-scsi" && syncs == 1) || (scenario == "sync-header" && syncs == 2)) {
        r[7] = 2; r[11] = 16; r[33] = 14; r[34] = 0x70; r[41] = 6;
      } else if (scenario == "sync-unowned") {
        r[3] ^= 1;
      } else if (scenario == "sync-timeout") {
        timedOut = true;
      }
    }
    if (c[0] != 0x28)
      printf("CDB=%02x byte1=%02x LBA=%u blocks=%u\n", c[0], c[1], lba, n);
  }
  uint32_t doorbell() {
    if (!submitted) return 0;
    if (++polls == 1 || timedOut) return 1;
    submitted = false;
    return 0;
  }
  uint32_t interrupt() const { return 0; }
  uint32_t completedOcs() const { return 0; }
  void deadline() {}
  void barrier() {}
  bool expired() const { return timedOut && polls > 2; }
  void delay() {}
  void invalidateAll() {}
  const uint8_t *response() const { return virt + 4608; }
} combined_hardware;

static CombinedRead::State combined_state;
#include "../package/nuwa-data-write/RetainedRead.inc"
#include "../package/nuwa-data-write/RetainedPersist.inc"
#include "StoreGptCheck.inc"

using UInt64 = uint64_t;
using IOOptionBits = uint32_t;
using IOReturn = int;
constexpr IOReturn kIOReturnSuccess = 0, kIOReturnNotReady = 1, kIOReturnIOError = 2;
struct NativeRamBlock {
  IOLock ramGate, *gate = &ramGate;
  bool online = true, isBig = true, storeAttached = false, direct = false, directFailed = false;
  RamSparseDisk sparse{};
  SeedDisk big{};
  uint8_t seedHash[32];
  persist::Overlay overlay;
  uint8_t *overlayBits = nullptr, *stage = nullptr;
  static constexpr uint32_t kStagePages = 32;
  NativeRamBlock() { big.bytes = Pages * Block; memcpy(seedHash, Disposable::Seed, sizeof seedHash); }
  ~NativeRamBlock() { free(overlayBits); free(stage); }
#include "RamBlock.inc"
};

int main(int argc, char **argv) {
  assert(argc == 2);
  scenario = argv[1];
  printf("case=%s\n", argv[1]);
  combined_state.setup.dma = Hardware::Dma;
  assert(PreservedNop::domain(combined_hardware, combined_state.setup));
  combined_state.block = Block;
  combined_state.blocks = nuwaDataIdentity.capacity;
  combined_state.capacity = combined_state.blocks * Block;
  gStoreGeometry = {true, nuwaDataIdentity.userdataFirst, nuwaDataIdentity.userdataLast,
                    Disposable::RootBytes};
  memcpy(native_ram_block_seed_sha256, Disposable::Seed, 32);
  if (scenario == "wrong-boot-seed") native_ram_block_seed_sha256[0] ^= 1;
  if (scenario == "legacy-v3" || scenario == "legacy-disposable")
    memcpy(combined_hardware.media[Legacy.first + 1].data(),
           scenario == "legacy-v3" ? "NUWADSB3" : "NUWAXSB3", 8);
  uint64_t lba = 0;
  const char *why = nullptr;
  if (scenario == "wrong-boot-seed" || prefix("legacy-") || prefix("overlap-")) {
    assert(!native_ufs_store_open(scenario == "overlap-root" ? 57000000 : Size, &lba, &why));
    Page p{};
    assert(why && *why && !native_ufs_store_write(0, 1, p.data()) && !native_ufs_store_sync());
    if (scenario != "overlap-root") {
      NativeRamBlock ram;
      ram.attachStore();
      const auto acquires = hostAcquires;
      assert(native_data_persist_state == 4 && !ram.direct && !ram.overlay.active);
      assert(ram.doSynchronizeCache() == kIOReturnIOError &&
             ram.doSynchronize(0, 8, 0) == kIOReturnIOError && hostAcquires == acquires);
    }
    for (auto e : combined_hardware.events) assert(e.op == 0x28);
    return 0;
  }
  assert(native_ufs_store_mode() == 2);
  NativeRamBlock ram;
  auto &overlay = ram.overlay;
  NativeRamBlock::StoreOps ops;
  auto &hw = combined_hardware;
  if (scenario == "retained" || scenario == "wrong-header-seed") {
    auto &header = hw.media[First];
    Page seed{};
    memcpy(seed.data(), Disposable::Seed, 32);
    if (scenario == "wrong-header-seed") seed[0] ^= 1;
    persist::encodeHeader(header.data(), Pages, seed.data(), 7);
  }
  assert(ram.doSynchronizeCache() == kIOReturnSuccess &&
         ram.doSynchronize(0, 8, 0) == kIOReturnSuccess && hw.events.empty() && !hostAcquires);
  ram.attachStore();
  assert(native_data_persist_first_lba == First);
  // Primary/backup GPT (4 commands) and two legacy anchors precede the header.
  constexpr unsigned before = 6;
  if (scenario == "wrong-header-seed") {
    const auto acquires = hostAcquires;
    assert(native_data_persist_state == 7 && !overlay.active && hw.events.size() == before + 1 &&
           hw.events.back().op == 0x28);
    assert(ram.doSynchronizeCache() == kIOReturnSuccess &&
           ram.doSynchronize(0, 8, 0) == kIOReturnSuccess && hostAcquires == acquires);
    return 0;
  }
  if (prefix("sync-")) {
    assert(native_data_persist_state == 4 && !overlay.active && !ram.direct &&
           retainedSlot.state() == (scenario == "sync-timeout" ? State::TIMEOUT_ORPHAN : State::FATAL_QUARANTINED));
    const bool last = scenario == "sync-header";
    assert(hw.media.count(First) == last && hw.syncs == (last ? 2U : 1U));
    const auto count = hw.events.size();
    const auto acquires = hostAcquires;
    ram.attachStore(); // The failed attempt stays latched; no reattach or sync retry.
    assert(ram.doSynchronizeCache() == kIOReturnIOError);
    assert(ram.doSynchronize(0, 8, 0) == kIOReturnIOError);
    assert(hw.events.size() == count && hostAcquires == acquires);
    puts("attachStore failed: both IOKit sync entries return IOError; no retained re-entry");
    return 0;
  }
  if (scenario == "reset") {
    const auto bb = persist::bitmapBlocks(Pages);
    assert(native_data_persist_state == 3 && overlay.active && ram.direct && hw.events.size() == before + bb + 4);
    const auto *e = hw.events.data() + before;
    assert(e[0].op == 0x28);
    for (unsigned i = 1; i <= bb; ++i)
      assert(e[i].op == 0x2a && e[i].lba == First + i && e[i].n == 1);
    assert(e[bb + 1].op == 0x35 && e[bb + 2].lba == First &&
           e[bb + 2].n == 1 && e[bb + 3].op == 0x35);
    assert(ram.doSynchronizeCache() == kIOReturnSuccess && hw.syncs == 3 &&
           hw.events.back().op == 0x35);
    return 0;
  }
  assert(native_data_persist_state == 2 && overlay.active && ram.direct);
  std::vector<uint8_t> data(33 * Block, 0x5a);
  for (unsigned i = 0; i < 33; ++i) data[i * Block] = uint8_t(i);
  const auto count = hw.events.size();
  assert(!ops.write(Size - 1, 2, data.data()) && !ops.write(Size, 1, data.data()) &&
         !ops.read(UINT64_MAX, 1, data.data()) && !ops.write(0, 0, data.data()) &&
         hw.events.size() == count);
  hw.observeBits = &overlay;
  hw.observePage = 9;
  std::promise<void> rung, rootWaiting, release;
  auto queued = rung.get_future(), attempting = rootWaiting.get_future(), resume = release.get_future();
  hw.writeRung = &rung;
  hw.resume = &resume;
  auto writer = std::async(std::launch::async, [&] { return overlay.writeRun(ops, 9, 33, data.data()); });
  assert(queued.wait_for(std::chrono::seconds(2)) == std::future_status::ready);
  auto reader = std::async(std::launch::async, [&] {
    rootWaiting.set_value();
    IOLockLock(gHost.lock);
    auto e = retainedReadLocked(gStoreGeometry.first, 1);
    IOLockUnlock(gHost.lock);
    return e;
  });
  assert(attempting.wait_for(std::chrono::seconds(2)) == std::future_status::ready);
  assert(reader.wait_for(std::chrono::milliseconds(20)) == std::future_status::timeout);
  release.set_value();
  assert(writer.get() && reader.get() == CombinedRead::End::Success && overlay.present == 33);
  std::vector<Hardware::Event> writes;
  for (size_t i = count; i < hw.events.size(); ++i)
    if (hw.events[i].op == 0x2a) writes.push_back(hw.events[i]);
  const auto page = First + persist::pageBlock(Pages, 9);
  assert(writes.size() == 3 && writes[0].lba == page && writes[0].n == 32 &&
         writes[1].lba == page + 32 && writes[1].n == 1 &&
         writes[2].lba == First + 1 && writes[2].n == 1);
  for (unsigned i = 0; i < 33; ++i) assert(!memcmp(hw.media[page + i].data(), data.data() + i * Block, Block));
  assert(hw.media[First + 1][1] == 0xfe && hw.media[First + 1][5] == 0x03);
  puts("writeRun: data completed before set bits and bitmap write; root waits on same host lock");
}
