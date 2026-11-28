// SPDX-License-Identifier: BSD-2-Clause
#include "NuwaDataFixtureGpt.h"
#include "../package/nuwa-data-write/Descriptor.h"
#include "../package/nuwa-data-write/DisposableData.h"
#include "../package/nuwa-data-write/V1ResetMarker.h"
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
#include <new>
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
                native_data_persist_present, native_ram_block_resident_bytes, native_data_persist_errors,
                native_data_persist_writes, native_data_persist_syncs, native_ram_block_reads,
                native_ram_block_writes, native_ram_block_failures;
static unsigned native_data_persist_gpt, native_data_persist_gpt_after, native_data_persist_header,
                native_data_persist_state;
extern "C" { const char *volatile nuwa_data_persist_open_why = nullptr; }
static volatile uint64_t nuwa_v1_write_failure, nuwa_v1_write_failure_attached;
static constexpr unsigned kDefaultReserveMiB = 1024;
static constexpr uint64_t kLogReserveBlocks = 8192, kExportBlocks = 65536;
static struct { bool valid; uint64_t first, last, imageBytes; } gStoreGeometry;
static std::string_view scenario;
static bool prefix(std::string_view text) { return scenario.substr(0, text.size()) == text; }
static void *IOMallocZero(size_t n) {
  if (scenario == "reset-overlay-alloc" && n == persist::bitmapBlocks(Pages) * Block) return nullptr;
  return calloc(1, n);
}
static void IOFree(void *p, size_t) { free(p); }
static void IOLog(const char *, ...) {}
static bool PE_parse_boot_argn(const char *arg, void *ptr, size_t n) {
  assert(n == sizeof(uint32_t));
  if (!strcmp(arg, "sheng-data-persist")) *static_cast<uint32_t *>(ptr) = 2;
  else if (!strcmp(arg, "sheng-log-reserve") &&
           (scenario == "overlap-log" || scenario == "reset-legacy-reserve"))
    *static_cast<uint32_t *>(ptr) = scenario == "overlap-log" ? 287 : 2048;
  else if (!strcmp(arg, "sheng-data-reset") &&
           (prefix("reset") || scenario == "daily-reset-3"))
    *static_cast<uint32_t *>(ptr) = prefix("reset2") ? 2 : scenario == "daily-reset-3" ? 3 : 1;
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
  struct Event { uint8_t op, flags; unsigned n; uint64_t lba; const char *diagnostic; };
  std::vector<Event> events;
  unsigned prepares = 0, polls = 0, headerReads = 0, headerWrites = 0;
  bool submitted = false, timedOut = false, ownershipLost = false, faultRead = false;
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
      case 0x50: return ownershipLost ? Dma + 4096 : Dma;
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
    events.push_back({c[0], c[1], n, lba, nuwa_data_persist_open_why});
    if (c[0] == 0x28) {
      assert(u[1] == 0x40 && n);
      if (lba == First) ++headerReads;
      for (unsigned i = 0; i < n; ++i) {
        auto it = media.find(lba + i);
        const auto *page = it == media.end() ? gptFixture.at(lba + i) : it->second.data();
        if (page) memcpy(data + i * Block, page, Block);
      }
      if (faultRead) {
        if (scenario == "sync-timeout") timedOut = true;
        else if (scenario == "sync-unowned") r[3] ^= 1;
        else if (scenario == "write-read-scsi") {
          r[7] = 2; r[11] = 16; r[33] = 14; r[34] = 0x70; r[41] = 6;
        }
      }
      if ((scenario == "legacy-read-scsi" && lba == Legacy.first) ||
          (scenario == "reset-legacy-read-first" && lba == Legacy.first) ||
          (scenario == "reset-legacy-read-second" && lba == Legacy.first + 1) ||
          (scenario == "reset-legacy-read-v1-preflight" && lba == First && headerReads == 1) ||
          (scenario == "reset-overlay-read" && lba == First && headerReads == 2)) {
        r[7] = 2; r[11] = 16; r[33] = 14; r[34] = 0x70; r[41] = 6;
      }
    } else if (c[0] == 0x2a) {
      const bool cleanup = prefix("reset") && n == 1 &&
                           Window({Legacy.first, 1}).contains(0, Block, lba, n);
      assert(c[1] == 0 && u[1] == 0x20 && n &&
             (cleanup || Window({First, Size}).contains(0, Block, lba, n)));
      assert((le32(virt) & (3U << 25)) == 1U << 25);
      if (lba == First) ++headerWrites;
      if (lba == First && prefix("reset"))
        assert(V1ResetMarker::present(data) == (headerWrites <= 2));
      if (observeBits) {
        const auto bitmap = First + 1 + observePage / (Block * 8);
        assert(observeBits->has(observePage) == (lba == bitmap));
      }
      if (writeRung) {
        writeRung->set_value();
        assert(resume->wait_for(std::chrono::seconds(2)) == std::future_status::ready);
        writeRung = nullptr;
      }
      const bool appliedError = (scenario == "reset-legacy-fail1-applied" && lba == Legacy.first + 1) ||
                                (scenario == "reset-legacy-fail0-applied" && lba == Legacy.first) ||
                                (scenario == "reset-marker-applied" && lba == First && headerWrites == 1) ||
                                (scenario == "reset-overlay-header-applied" && lba == First && headerWrites == 2);
      if (appliedError)
        for (unsigned i = 0; i < n; ++i) memcpy(media[lba + i].data(), data + i * Block, Block);
      if ((scenario == "reset-scsi" && lba != First) || scenario == "write-scsi" || appliedError ||
          (scenario == "reset-legacy-marker-fail" && lba == First && headerWrites == 1) ||
          (scenario == "reset-legacy-fail0" && lba == Legacy.first) ||
          (scenario == "reset-legacy-fail1" && lba == Legacy.first + 1) ||
          (scenario == "reset-overlay-bitmap" && lba == First + 1) ||
          (scenario == "reset-overlay-bitmap-mid" && lba == First + 5) ||
          (scenario == "reset-overlay-bitmap-last" && lba == First + persist::bitmapBlocks(Pages)) ||
          (scenario == "reset-overlay-header" && lba == First && headerWrites == 2) ||
          (scenario == "reset-overlay-commit" && lba == First && headerWrites == 3)) {
        r[7] = 2; r[11] = 16; r[33] = 14; r[34] = 0x70; r[41] = 6;
      } else {
        for (unsigned i = 0; i < n; ++i)
          memcpy(media[lba + i].data(), data + i * Block, Block);
      }
    } else {
      assert(false && "unexpected command (including SYNCHRONIZE CACHE)");
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
  void invalidateAll() {
    const auto &e = events.back();
    if (scenario == "reset-legacy-owner" && e.op == 0x28 && e.lba == Legacy.first + 1)
      ownershipLost = true;
    if (e.op == 0x2a &&
        ((scenario == "reset-order-before-header" && e.lba == First + persist::bitmapBlocks(Pages)) ||
         (scenario == "reset-order-after-header" && e.lba == First && headerWrites == 2)))
      ownershipLost = true;
  }
  const uint8_t *response() const { return virt + 4608; }
} combined_hardware;

static CombinedRead::State combined_state;
#include "../package/nuwa-data-write/RetainedRead.inc"
#include "../package/nuwa-data-write/RetainedPersist.inc"
#include "StoreGptCheck.inc"

using UInt64 = uint64_t;
using IOOptionBits = uint32_t;
using IOReturn = int;
constexpr IOReturn kIOReturnSuccess = 0, kIOReturnNotReady = 1, kIOReturnIOError = 2,
                   kIOReturnBadArgument = 3, kIOReturnNoMemory = 4, kIOReturnUnsupported = 5;
#include "V1Diag.inc"
constexpr IOOptionBits kIOStorageOptionForceUnitAccess = 1;
struct IOStorageAttributes { IOOptionBits options; };
enum { kIODirectionIn, kIODirectionOut };
struct IOMemoryDescriptor {
  Page &bytes;
  size_t getLength() { return bytes.size(); }
  int getDirection() { return kIODirectionOut; }
  uint64_t writeBytes(uint64_t at, const void *p, uint64_t n) {
    assert(at + n <= bytes.size()); memcpy(bytes.data() + at, p, n); return n;
  }
  uint64_t readBytes(uint64_t at, void *p, uint64_t n) {
    assert(at + n <= bytes.size()); memcpy(p, bytes.data() + at, n); return n;
  }
};
struct IOStorageCompletion {
  void *target, *parameter;
  void (*action)(void *, void *, IOReturn, uint64_t);
};
struct NativeRamBlock {
  IOLock ramGate, *gate = &ramGate;
  uint8_t *memory = nullptr;
  const uint64_t capacity = Pages * Block / 512;
  bool online = true, isBig = true, storeAttached = false, direct = false, directFailed = false;
  RamSparseDisk sparse{};
  SeedDisk big{};
  uint8_t seedHash[32];
  persist::Overlay overlay;
  uint8_t *overlayBits = nullptr, *stage = nullptr;
  static constexpr uint32_t kStagePages = 32;
  NativeRamBlock() { big.bytes = Pages * Block; memcpy(seedHash, Disposable::Seed, sizeof seedHash); }
  ~NativeRamBlock() { free(overlayBits); free(stage); }
  IOReturn doAsyncReadWrite(IOMemoryDescriptor *, UInt64, UInt64, IOStorageAttributes *, IOStorageCompletion *);
#include "RamBlock.inc"
};
#include "RamIO.inc"

static void checkSync(NativeRamBlock &ram, IOReturn expected, unsigned locks = 2) {
  const auto count = combined_hardware.events.size();
  const auto prepares = combined_hardware.prepares;
  const auto acquires = hostAcquires;
  const auto tag = combined_state.tag;
  assert(ram.doSynchronizeCache() == expected && ram.doSynchronize(0, 8, 0) == expected);
  assert(combined_hardware.events.size() == count && combined_hardware.prepares == prepares &&
         combined_state.tag == tag && hostAcquires == acquires + locks);
  printf("both IOKit sync entries: %s; zero command preparations/submissions\n",
         expected == kIOReturnSuccess ? "Success" : "IOError");
}

static void sealFixture(Page &page) {
  putLE(page.data() + 92, crc(page.data(), 96, 92), 4);
  putLE(page.data() + Block - 4, crc(page.data(), Block, Block - 4), 4);
}

static void makeDisposable(Page &page, unsigned slot) {
  static Disposable::Overlay::Workspace workspace{};
  uint8_t header[Block]{};
  assert(Disposable::Overlay::initialSuperblock(header, Disposable::Seed, workspace));
  memcpy(page.data(), header, Block);
  putLE(page.data() + 12, slot, 4);
  putLE(page.data() + Block - 8, slot, 4);
  sealFixture(page);
  assert(Disposable::Overlay::validSuperblockForSeed(page.data(), slot, Disposable::Seed));
}

static void expectDailyRefused(const char *expected) {
  persistWindow = {};
  retainedSlot.~Slot();
  new (&retainedSlot) Slot;
  gHost.ready = true;
  gHost.poisoned = combined_state.quarantined = false;
  combined_hardware.ownershipLost = combined_hardware.timedOut = false;
  scenario = "daily-inprogress-probe";
  const auto count = combined_hardware.events.size();
  uint64_t lba = 0;
  const char *why = nullptr;
  assert(!native_ufs_store_open(Size, &lba, &why) &&
         !strcmp(nuwa_persist_open_reason(0, why), expected));
  Page page{};
  assert(!native_ufs_store_write(0, 1, page.data()));
  for (size_t i = count; i < combined_hardware.events.size(); ++i)
    assert(combined_hardware.events[i].op == 0x28);
  puts("simulated next daily refused: zero writes");
}

int main(int argc, char **argv) {
  assert(argc == 2);
  scenario = argv[1];
  printf("case=%s\n", argv[1]);
  if (scenario == "cache-state") {
    NativeRamBlock ram;
    for (bool initial : {false, true}) {
      bool value = initial;
      assert(ram.getWriteCacheState(&value) == kIOReturnUnsupported && value == initial);
    }
    puts("getWriteCacheState: Unsupported; output unchanged");
    return 0;
  }
  combined_state.setup.dma = Hardware::Dma;
  assert(PreservedNop::domain(combined_hardware, combined_state.setup));
  combined_state.block = Block;
  combined_state.blocks = nuwaDataIdentity.capacity;
  combined_state.capacity = combined_state.blocks * Block;
  gStoreGeometry = {true, nuwaDataIdentity.userdataFirst, nuwaDataIdentity.userdataLast,
                    Disposable::RootBytes};
  if (scenario == "reset-legacy-rootguard")
    gStoreGeometry.imageBytes = (Legacy.first - nuwaDataIdentity.userdataFirst - Guard + 1) * Block;
  memcpy(native_ram_block_seed_sha256, Disposable::Seed, 32);
  if (scenario == "wrong-boot-seed" || scenario == "reset-legacy-seed") native_ram_block_seed_sha256[0] ^= 1;
  if (scenario == "wrong-primary-gpt" || scenario == "reset-legacy-primary") gptFixture.pe[0] ^= 1;
  if (scenario == "wrong-backup-gpt" || scenario == "reset-legacy-backup") gptFixture.be[0] ^= 1;
  if (scenario == "legacy-v3" || scenario == "legacy-disposable")
    memcpy(combined_hardware.media[Legacy.first + 1].data(),
           scenario == "legacy-v3" ? "NUWADSB3" : "NUWAXSB3", 8);
  if (prefix("reset-legacy-") || prefix("reset2-legacy-") || scenario == "daily-reset-3" ||
      prefix("reset-overlay-")) {
    auto &a = combined_hardware.media[Legacy.first];
    auto &b = combined_hardware.media[Legacy.first + 1];
    a.fill(0);
    b.fill(0);
    const bool onlySecond = scenario == "reset-legacy-1" || scenario == "reset-legacy-sb1-garbage-only";
    if (!onlySecond && scenario != "reset-legacy-blank") makeDisposable(a, 0);
    if (scenario == "reset-legacy-1" || scenario == "reset-legacy-both" ||
        scenario == "reset2-legacy-both" || scenario == "reset-legacy-fail1" ||
        scenario == "reset-legacy-fail1-applied") makeDisposable(b, 1);
    if (scenario == "reset-legacy-v3" || scenario == "reset-legacy-mixed")
      memcpy(b.data(), "NUWADSB3", 8);
    if (scenario == "reset-legacy-v3") a.fill(0x37);
    if (scenario == "reset-legacy-mixed-reverse") memcpy(a.data(), "NUWADSB3", 8);
    if (scenario == "reset-legacy-torn") {
      a.fill(0);
      memcpy(a.data(), "NUWAX", 5);
    }
    if (scenario == "reset-legacy-magic") {
      a.fill(0x37);
      memcpy(a.data(), "NUWAXSB3", 8);
    }
    if (scenario == "reset-legacy-seed-conflict") { a[32] ^= 1; sealFixture(a); }
    if (scenario == "reset-legacy-slot-conflict") { putLE(a.data() + 12, 1, 4); sealFixture(a); }
    if (scenario == "reset-legacy-fields") { putLE(a.data() + 64, 1, 4); sealFixture(a); }
    if (scenario == "reset-legacy-noninitial-gen") {
      putLE(a.data() + 24, 1, 8);
      putLE(a.data() + Block - 16, 1, 8);
      sealFixture(a);
    }
    if (scenario == "reset-legacy-noninitial-head") { putLE(a.data() + 72, 1, 4); sealFixture(a); }
    if (scenario == "reset-legacy-noninitial-count") { putLE(a.data() + 80, 1, 8); sealFixture(a); }
    if (scenario == "reset-legacy-noninitial-mapcrc") { a[88] ^= 1; sealFixture(a); }
    if (scenario == "reset-legacy-header-crc") {
      a[92] ^= 1;
      putLE(a.data() + Block - 4, crc(a.data(), Block, Block - 4), 4);
    }
    if (scenario == "reset-legacy-block-crc") a[Block - 4] ^= 1;
    if (scenario == "reset-legacy-second-invalid") {
      b.fill(0x38);
      memcpy(b.data(), "NUWAXSB3", 8);
    }
    if (scenario == "reset-legacy-sb1-garbage" || scenario == "reset-legacy-sb1-garbage-only")
      b[17] = 0x38;
    if (scenario == "reset-legacy-sb1-tail") b[Block - 1] = 0x38;
    if (scenario == "reset-legacy-ambiguous") {
      a.fill(0);
      memcpy(a.data(), "NUWA", 4);
    }
  }
  if (scenario == "daily-inprogress" || scenario == "daily-inprogress-partial" ||
      scenario == "reset-recover") {
    auto &header = combined_hardware.media[First];
    persist::encodeHeader(header.data(), Pages, Disposable::Seed, 7);
    if (scenario == "daily-inprogress-partial") header[V1ResetMarker::Offset + 31] = 0xa5;
    else V1ResetMarker::set(header.data());
  }
  uint64_t lba = 0;
  const char *why = nullptr;
  if (scenario == "reset-legacy-bounds") {
    Page zero{};
    IOLockLock(gHost.lock);
    assert(!persistClearLegacyAnchorLocked(Legacy.first - 1, zero.data()) &&
           !persistClearLegacyAnchorLocked(Legacy.first + 1, zero.data()) &&
           !persistClearLegacyAnchorLocked(Legacy.first + 2, zero.data()) &&
           !persistClearLegacyAnchorLocked(First, zero.data()) &&
           !persistClearLegacyAnchorLocked(UINT64_MAX, zero.data()));
    IOLockUnlock(gHost.lock);
    assert(!native_ufs_store_write(0, 1, zero.data()) && combined_hardware.events.empty());
    puts("cleanup target bounds and unopened ordinary v1 window: zero writes");
    return 0;
  }
  if (scenario == "reset-legacy-size") {
    assert(!native_ufs_store_open(Size - 1, &lba, &why) &&
           !strcmp(nuwa_persist_open_reason(0, why), "window rst=guard"));
    for (auto e : combined_hardware.events) assert(e.op == 0x28);
    puts("non-v1 window cannot authorize cleanup: zero writes");
    return 0;
  }
  if (scenario == "daily-inprogress" || scenario == "daily-inprogress-partial") {
    NativeRamBlock ram;
    ram.attachStore();
    assert(native_data_persist_state == 4 && !ram.direct && !ram.overlay.active &&
           !strcmp(nuwa_data_persist_open_why, "window rst=pending"));
    for (auto e : combined_hardware.events) assert(e.op == 0x28);
    puts("daily detects v1 in-progress marker: zero writes");
    return 0;
  }
  if (scenario == "reset-marker-applied") {
    NativeRamBlock ram;
    ram.attachStore();
    assert(native_data_persist_state == 4 && !ram.direct && !ram.overlay.active &&
           !strcmp(nuwa_data_persist_open_why, "window rst=markfail") &&
           V1ResetMarker::present(combined_hardware.media[First].data()));
    unsigned writes = 0;
    for (auto e : combined_hardware.events) if (e.op == 0x2a) {
      ++writes;
      assert(e.lba == First);
    }
    assert(writes == 1);
    expectDailyRefused("window rst=pending");
    return 0;
  }
  if (scenario == "reset-legacy-read-first" || scenario == "reset-legacy-read-second" ||
      scenario == "reset-legacy-read-v1-preflight" ||
      scenario == "reset-legacy-v3" || scenario == "reset-legacy-mixed" ||
      scenario == "reset-legacy-mixed-reverse" || scenario == "reset-legacy-ambiguous" ||
      scenario == "reset-legacy-torn" || scenario == "reset-legacy-magic" ||
      scenario == "reset-legacy-seed-conflict" || scenario == "reset-legacy-slot-conflict" ||
      scenario == "reset-legacy-header-crc" || scenario == "reset-legacy-block-crc" ||
      scenario == "reset-legacy-fields" || scenario == "reset-legacy-second-invalid" ||
      scenario == "reset-legacy-noninitial-gen" || scenario == "reset-legacy-noninitial-head" ||
      scenario == "reset-legacy-noninitial-count" || scenario == "reset-legacy-noninitial-mapcrc" ||
      scenario == "reset-legacy-1" || scenario == "reset-legacy-both" ||
      scenario == "reset2-legacy-both" || scenario == "reset-legacy-sb1-garbage" ||
      scenario == "reset-legacy-sb1-garbage-only" || scenario == "reset-legacy-sb1-tail" ||
      scenario == "reset-legacy-seed" || scenario == "reset-legacy-primary" ||
      scenario == "reset-legacy-backup" || scenario == "reset-legacy-reserve" ||
      scenario == "reset-legacy-rootguard" || scenario == "reset-legacy-owner" ||
      scenario == "daily-reset-3" ||
      scenario == "reset-legacy-fail0" || scenario == "reset-legacy-fail0-applied" ||
      scenario == "reset-legacy-fail1" ||
      scenario == "reset-legacy-fail1-applied" || scenario == "reset-legacy-marker-fail") {
    const auto a = combined_hardware.media[Legacy.first];
    const auto b = combined_hardware.media[Legacy.first + 1];
    NativeRamBlock ram;
    ram.attachStore();
    assert(native_data_persist_state == 4 && !ram.direct && !ram.overlay.active);
    const char *expected =
        scenario == "reset-legacy-read-first" || scenario == "reset-legacy-read-second" ||
        scenario == "reset-legacy-read-v1-preflight" ? "window rst=read" :
        scenario == "reset-legacy-v3" || scenario == "reset-legacy-mixed" ||
        scenario == "reset-legacy-mixed-reverse" || scenario == "reset-legacy-ambiguous" ? "legacy-v3" :
        scenario == "reset-legacy-torn" || scenario == "reset-legacy-magic" ||
        scenario == "reset-legacy-seed-conflict" || scenario == "reset-legacy-slot-conflict" ||
        scenario == "reset-legacy-header-crc" || scenario == "reset-legacy-block-crc" ||
        scenario == "reset-legacy-fields" ||
        scenario == "reset-legacy-noninitial-gen" || scenario == "reset-legacy-noninitial-head" ||
        scenario == "reset-legacy-noninitial-count" || scenario == "reset-legacy-noninitial-mapcrc" ?
        "window rst=invalid" :
        scenario == "reset-legacy-second-invalid" || scenario == "reset-legacy-1" ||
        scenario == "reset-legacy-both" || scenario == "reset2-legacy-both" ||
        scenario == "reset-legacy-sb1-garbage" || scenario == "reset-legacy-sb1-garbage-only" ||
        scenario == "reset-legacy-sb1-tail" || scenario == "reset-legacy-fail1" ||
        scenario == "reset-legacy-fail1-applied" ? "window rst=sb1" :
        scenario == "reset-legacy-reserve" || scenario == "reset-legacy-rootguard" ||
        scenario == "reset-legacy-owner" ? "window rst=guard" :
        scenario == "daily-reset-3" ? "legacy-disposable" :
        scenario == "reset-legacy-marker-fail" ? "window rst=markfail" :
        scenario == "reset-legacy-fail0" || scenario == "reset-legacy-fail0-applied" ?
        "window rst=fail1" : "window";
    assert(!strcmp(nuwa_data_persist_open_why, expected));
    const unsigned attempted = scenario == "reset-legacy-fail0" ||
                               scenario == "reset-legacy-fail0-applied" ? 1 : 0;
    unsigned writes = 0;
    for (auto e : combined_hardware.events) if (e.op == 0x2a) ++writes;
    assert(writes == attempted + (attempted != 0 || scenario == "reset-legacy-marker-fail"));
    if (scenario == "reset-legacy-seed") assert(combined_hardware.events.empty());
    assert(combined_hardware.media[Legacy.first + 1] == b);
    if (scenario == "reset-legacy-fail0-applied")
      assert(zero(combined_hardware.media[Legacy.first].data(), Block));
    else assert(combined_hardware.media[Legacy.first] == a);
    Page page{};
    const auto count = combined_hardware.events.size();
    assert(!native_ufs_store_write(0, 1, page.data()) && !native_ufs_store_sync() &&
           combined_hardware.events.size() == count);
    if (attempted || scenario == "reset-legacy-marker-fail")
      expectDailyRefused(scenario == "reset-legacy-fail0-applied" ?
                         "window rst=pending" : "legacy-disposable");
    printf("refused reset: %u cleanup submissions, no ordinary v1 writes\n", attempted);
    return 0;
  }
  if (scenario == "wrong-boot-seed" || prefix("legacy-") || prefix("overlap-") ||
      scenario == "wrong-primary-gpt" || scenario == "wrong-backup-gpt") {
    assert(!native_ufs_store_open(scenario == "overlap-root" ? 57000000 : Size, &lba, &why));
    const char *expectedWhy = scenario == "legacy-v3" ? "legacy-v3" :
                              scenario == "legacy-disposable" ? "legacy-disposable" : "window";
    assert(!strcmp(nuwa_persist_open_reason(0, why), expectedWhy));
    Page p{};
    assert(why && *why && !native_ufs_store_write(0, 1, p.data()) && !native_ufs_store_sync());
    if (scenario != "overlap-root") {
      NativeRamBlock ram;
      Page payload{};
      IOMemoryDescriptor buffer{payload};
      IOStorageCompletion completion{nullptr, nullptr, [](void *, void *, IOReturn, uint64_t) {
        assert(false && "inactive write must not complete");
      }};
      assert(ram.doAsyncReadWrite(&buffer, 0, 8, nullptr, &completion) == kIOReturnNotReady);
      assert(nuwa_v1_write_failure == ((uint64_t(4) << 32) | kIOReturnNotReady) &&
             !nuwa_v1_write_failure_attached);
      ram.attachStore();
      assert(native_data_persist_state == 4 && !ram.direct && !ram.overlay.active);
      assert(!strcmp(nuwa_data_persist_open_why, expectedWhy));
      assert(ram.doAsyncReadWrite(&buffer, 0, 8, nullptr, &completion) == kIOReturnNotReady);
      assert(nuwa_v1_write_failure_attached == nuwa_v1_write_failure);
      checkSync(ram, kIOReturnIOError, 0);
    }
    for (auto e : combined_hardware.events) assert(e.op == 0x28);
    puts("refused window: zero writes");
    return 0;
  }
  assert(native_ufs_store_mode() == 2);
  NativeRamBlock ram;
  auto &overlay = ram.overlay;
  NativeRamBlock::StoreOps ops;
  auto &hw = combined_hardware;
  if (scenario == "retained" || scenario == "write-scsi" || scenario == "write-read-scsi" ||
      scenario == "wrong-header-seed" || prefix("sync-")) {
    auto &header = hw.media[First];
    Page seed{};
    memcpy(seed.data(), Disposable::Seed, 32);
    if (scenario == "wrong-header-seed") seed[0] ^= 1;
    persist::encodeHeader(header.data(), Pages, seed.data(), 7);
    if (scenario == "write-read-scsi") hw.media[First + 1][0] = 1;
  }
  assert(ram.doSynchronizeCache() == kIOReturnSuccess &&
         ram.doSynchronize(0, 8, 0) == kIOReturnSuccess && hw.events.empty() && !hostAcquires);
  ram.attachStore();
  assert(native_data_persist_first_lba == First);
  if (prefix("reset-overlay-")) {
    assert(native_data_persist_state == 4 && !overlay.active && !ram.direct &&
           V1ResetMarker::present(hw.media[First].data()) &&
           zero(hw.media[Legacy.first].data(), Block) &&
           zero(hw.media[Legacy.first + 1].data(), Block));
    assert(!strcmp(nuwa_data_persist_open_why,
                   scenario == "reset-overlay-commit" ? "ok rst=commitfail" : "ok rst=in1"));
    expectDailyRefused("window rst=pending");
    return 0;
  }
  // Four GPT reads, two legacy anchors and the preflight v1 header.
  const bool cleanupCase = scenario == "reset-legacy-0" || scenario == "reset2-legacy-0";
  const unsigned cleaned = cleanupCase ? 1 : 0;
  const bool resetting = prefix("reset");
  const unsigned before = 7 + unsigned(resetting) + cleaned;
  if (scenario == "wrong-header-seed") {
    assert(native_data_persist_state == 7 && !overlay.active && hw.events.size() == before + 1 &&
           hw.events.back().op == 0x28);
    assert(!strcmp(nuwa_data_persist_open_why, "ok") && native_data_persist_header == 3);
    checkSync(ram, kIOReturnSuccess, 0);
    puts("foreign v1 header kept: zero writes");
    return 0;
  }
  if (scenario == "reset-scsi" || prefix("reset-order-")) {
    assert(native_data_persist_state == 4 && !overlay.active && !ram.direct &&
           retainedSlot.state() == State::FATAL_QUARANTINED);
    const auto bb = persist::bitmapBlocks(Pages);
    const bool last = scenario == "reset-order-after-header";
    const auto writes = scenario == "reset-scsi" ? 1 : bb + last;
    assert(hw.media.count(First) && V1ResetMarker::present(hw.media[First].data()) &&
           hw.events.size() == before + 1 + writes);
    const auto count = hw.events.size();
    const auto acquires = hostAcquires;
    ram.attachStore(); // The failed attempt stays latched; no reattach or sync retry.
    checkSync(ram, kIOReturnIOError, 0);
    assert(hw.events.size() == count && hostAcquires == acquires);
    puts("attachStore failed: both IOKit sync entries return IOError; no retained re-entry");
    expectDailyRefused("window rst=pending");
    return 0;
  }
  if (scenario == "reset" || scenario == "reset-recover" || scenario == "reset-legacy-blank" || cleanupCase) {
    const auto bb = persist::bitmapBlocks(Pages);
    assert(native_data_persist_state == 3 && overlay.active && ram.direct && hw.events.size() == before + bb + 3);
    const char *done = cleanupCase ? "ok rst=done1" : "ok rst=done0";
    assert(!strcmp(nuwa_data_persist_open_why, done) &&
           !V1ResetMarker::present(hw.media[First].data()));
    assert(hw.events[7].op == 0x2a && hw.events[7].lba == First &&
           !strcmp(hw.events[7].diagnostic, "- rst=ready"));
    unsigned seen = 0;
    for (unsigned i = 0; i < 2; ++i) {
      const bool match = cleanupCase && i == 0;
      if (match) {
        assert(zero(hw.media[Legacy.first + i].data(), Block));
        const auto &event = hw.events[8 + seen];
        assert(event.op == 0x2a && event.lba == Legacy.first + i && event.n == 1);
        assert(!strcmp(event.diagnostic, seen ? "- rst=clean1" : "- rst=progress"));
        ++seen;
      } else if (cleanupCase || scenario == "reset-legacy-blank") {
        assert(zero(hw.media[Legacy.first + i].data(), Block));
      }
    }
    assert(seen == cleaned);
    if (scenario == "reset-legacy-blank")
      for (auto event : hw.events)
        assert(event.op != 0x2a || (event.lba != Legacy.first && event.lba != Legacy.first + 1));
    const auto *e = hw.events.data() + before;
    assert(e[0].op == 0x28);
    for (unsigned i = 1; i <= bb; ++i)
      assert(e[i].op == 0x2a && e[i].lba == First + i && e[i].n == 1);
    assert(e[bb + 1].op == 0x2a && e[bb + 1].lba == First && e[bb + 1].n == 1);
    assert(e[bb + 2].op == 0x2a && e[bb + 2].lba == First && e[bb + 2].n == 1);
    checkSync(ram, kIOReturnSuccess);
    if (cleanupCase || scenario == "reset-recover") {
      // Model a new boot's unopened adapter on the same host media.
      const auto count = hw.events.size();
      persistWindow = {};
      scenario = "retained";
      NativeRamBlock daily;
      daily.attachStore();
      assert(native_data_persist_state == 2 && daily.overlay.active && daily.direct &&
             !strcmp(nuwa_data_persist_open_why, "ok"));
      for (size_t i = count; i < hw.events.size(); ++i) assert(hw.events[i].op == 0x28);
      puts("subsequent daily open on same media: Resumed, zero writes");
    }
    return 0;
  }
  assert(native_data_persist_state == 2 && overlay.active && ram.direct);
  assert(!strcmp(nuwa_data_persist_open_why, "ok") && native_data_persist_header == 0);
  if (scenario == "write-scsi" || scenario == "write-read-scsi") {
    Page payload{};
    IOMemoryDescriptor buffer{payload};
    bool completed = false;
    IOStorageCompletion completion{&completed, nullptr, [](void *target, void *, IOReturn status, uint64_t bytes) {
      assert(status == kIOReturnIOError && bytes == 0);
      *static_cast<bool *>(target) = true;
    }};
    hw.faultRead = scenario == "write-read-scsi";
    assert(ram.doAsyncReadWrite(&buffer, hw.faultRead ? 1 : 0, hw.faultRead ? 1 : 8,
                                nullptr, &completion) == kIOReturnSuccess && completed);
    const unsigned source = hw.faultRead ? 6 : 7;
    const uint64_t failure = (uint64_t(source) << 32) | kIOReturnIOError;
    assert(nuwa_v1_write_failure == failure && nuwa_v1_write_failure_attached == failure);
    assert(native_data_persist_state == 5 && native_data_persist_errors == 1 && ram.directFailed);
    assert(nuwa_v1_ufs_write_failure ==
           (hw.faultRead ? 0 : (uint64_t(unsigned(CombinedRead::End::Scsi)) << 32) | (uint64_t(2) << 24)));
    const auto eventCount = hw.events.size();
    completed = false;
    assert(ram.doAsyncReadWrite(&buffer, 0, 8, nullptr, &completion) == kIOReturnSuccess && completed);
    assert(hw.events.size() == eventCount && nuwa_v1_write_failure == failure &&
           nuwa_v1_write_failure_attached == failure);
    puts("first post-attach write error retains source, IOReturn, and attributed UFS status");
    return 0;
  }
  if (prefix("sync-")) {
    checkSync(ram, kIOReturnSuccess);
    if (scenario == "sync-ownership") {
      hw.ownershipLost = true;
    } else {
      hw.faultRead = true;
      IOLockLock(gHost.lock);
      const auto end = retainedReadLocked(gStoreGeometry.first, 1);
      IOLockUnlock(gHost.lock);
      assert(end == (scenario == "sync-timeout" ? CombinedRead::End::Transport : CombinedRead::End::Response));
    }
    checkSync(ram, kIOReturnIOError);
    assert(retainedSlot.state() ==
           (scenario == "sync-timeout" ? State::TIMEOUT_ORPHAN : State::FATAL_QUARANTINED));
    Page p{};
    const auto count = hw.events.size();
    assert(!ram.directFailed && !ops.write(persist::pageBlock(Pages, 0), 1, p.data()) &&
           hw.events.size() == count);
    return 0;
  }
  std::vector<uint8_t> data(33 * Block, 0x5a);
  for (unsigned i = 0; i < 33; ++i) data[i * Block] = uint8_t(i);
  const auto count = hw.events.size();
  assert(!ops.write(Size - 1, 2, data.data()) && !ops.write(Size, 1, data.data()) &&
         !ops.read(UINT64_MAX, 1, data.data()) && !ops.write(0, 0, data.data()) &&
         hw.events.size() == count);
  puts("out of window: zero writes");
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
  hw.observeBits = nullptr;
  Page payload{};
  payload.fill(0xab);
  IOMemoryDescriptor buffer{payload};
  IOStorageAttributes attributes{kIOStorageOptionForceUnitAccess};
  bool completed = false;
  IOStorageCompletion completion{&completed, nullptr, [](void *target, void *, IOReturn status, uint64_t bytes) {
    assert(status == kIOReturnSuccess && bytes == Block);
    *static_cast<bool *>(target) = true;
  }};
  const auto beforeFua = hw.events.size();
  assert(ram.doAsyncReadWrite(&buffer, 9 * (Block / 512), Block / 512, &attributes, &completion) ==
         kIOReturnSuccess && completed);
  assert(hw.events.size() == beforeFua + 1 && hw.events.back().op == 0x2a &&
         !hw.events.back().flags && hw.events.back().lba == page && hw.media[page] == payload);
  puts("FUA attribute: dispatch and completion Success, plain WRITE(10)");
  checkSync(ram, kIOReturnSuccess);
}
