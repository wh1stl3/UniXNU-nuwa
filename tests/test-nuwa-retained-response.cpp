// Compile against the candidate's staged CombinedRead.h, not the baseline copy.
#include "../package/nuwa-data-write/Provider.h"
#include "../package/nuwa-data-write/Overlay.h"
#include "NuwaDataFixtureGpt.h"
#include "../package/nuwa-ramblock/PersistOpenReason.h"
#include "PersistOverlay.h"
#include <cassert>
#include <cstdlib>
#include <cstdio>
#include <future>
#include <mutex>
#include <new>
#include <thread>
#include "TransferPoll.h"
#include "PreservedNop.h"
#include "CombinedRead.h"
#include "RootReadSession.h"

struct Response {
  unsigned status = 0, flags = 0, residual = 0, ocs = 0, foreignDb = 0;
  unsigned type = 0x21, lun = 0, dl = 0;
  bool badTag = false, badSense = false, timedOut = false, fatal = false;
};

struct IOLock { std::mutex mutex; };
static struct Host {
  bool ready, poisoned;
  IOLock *lock;
} gHost;
static IOLock hostLock, windowLock, ramGate;
static thread_local unsigned heldLocks;
static thread_local std::promise<void> *waitingWindow;
struct SnapshotSchedule {
  bool after;
  std::promise<void> &atBoundary;
  std::future<void> *resume;
};
static thread_local SnapshotSchedule *snapshotSchedule;
static void snapshotBoundary(IOLock *l, bool after) {
  if (l != &hostLock || !snapshotSchedule || snapshotSchedule->after != after) return;
  auto &hook = *snapshotSchedule;
  snapshotSchedule = nullptr;
  hook.atBoundary.set_value();
  if (hook.resume)
    assert(hook.resume->wait_for(std::chrono::seconds(2)) == std::future_status::ready);
}
static void IOLockLock(IOLock *l) {
  if (l == &windowLock && waitingWindow) waitingWindow->set_value();
  snapshotBoundary(l, false);
  l->mutex.lock();
  ++heldLocks;
}
static void IOLockUnlock(IOLock *l) {
  assert(heldLocks);
  --heldLocks;
  l->mutex.unlock();
  snapshotBoundary(l, true);
}

static struct Hardware {
  static constexpr uint32_t Dma = 0x10000;
  alignas(4096) uint8_t virt[CombinedRead::Bytes]{};
  Response wire{};
  unsigned prepares = 0, submissions = 0, seen = 0, ocsReads = 0, mmioReads = 0;
  unsigned writeSubmissions = 0, writeOcsReads = 0;
  uint64_t preparedLba = 0;
  bool active = false, partMedia = false, writing = false;
  const NuwaData::FixtureGpt *gpt = nullptr;
  uint8_t lastCdb[10]{}, written[NuwaData::Block]{};
  std::promise<void> *submitted = nullptr;
  std::future<void> *allowCompletion = nullptr;
  uint32_t sread(unsigned off) const {
    switch (off) {
      case 0: return 0;
      case 0x20: return (1U << 30) | (1U << 27) | (7U << 9) | 1;
      case 0x24: return 1;
      case 0x28: return 0x1000;
      case 0x800: return 0x80000060;
      case 0xc00: return 0;
      case 0x1000: return 0x1f000;
      case 0x1800: return 1;
      case 0x2000: return 0x0a9f0000;
      default: assert(false); return 0;
    }
  }
  uint32_t hread(unsigned off) {
    ++mmioReads;
    switch (off) {
      case 0x34: return 1;
      case 0x30: return 11;
      case 0x60: return 1;
      case 0x50: return Dma;
      case 0x58: return doorbell();
      case 0x20: case 0x24: case 0x54: case 0x78: case 0x80: return 0;
      default: assert(false); return 0;
    }
  }
  void hwrite(unsigned off, uint32_t val) {
    assert(heldLocks && off == 0x58 && val == 1 && !active);
    ++submissions;
    seen = 0;
    active = true;
    auto *r = virt + 4608;
    r[0] = wire.type;
    r[1] = wire.flags;
    r[2] = wire.lun;
    r[3] = virt[4099] ^ unsigned(wire.badTag);
    r[7] = wire.status;
    r[10] = wire.dl >> 8;
    r[11] = wire.dl;
    CombinedRead::put32(r + 12, wire.residual);
    r[33] = 14;
    r[34] = wire.badSense ? 0 : 0x70;
    r[36] = 5;
    r[41] = 6;
    auto *data = virt + CombinedRead::Data;
    assert(virt[4112] != 0x35);
    if (writing) {
      ++writeSubmissions;
      memcpy(lastCdb, virt + 4112, sizeof lastCdb);
      memcpy(written, data, sizeof written);
      assert(virt[4097] == 0x20 && virt[4098] == 0 &&
             CombinedRead::be32(virt + 4108) == NuwaData::Block);
      assert((NuwaData::le32(virt) & (3U << 25)) == (1U << 25));
      assert(NuwaData::le64(virt + 5120) == Dma + CombinedRead::Data &&
             NuwaData::le32(virt + 5132) == NuwaData::Block - 1);
    } else if (gpt && gpt->at(preparedLba)) {
      memcpy(data, gpt->at(preparedLba), NuwaData::Block);
    } else if (partMedia && (preparedLba == 1 || preparedLba == 2)) {
      // Fixture GPT header and a single 128-byte entry named "modem".
      memset(data, 0, NuwaData::Block);
      if (preparedLba == 1) {
        memcpy(data, "EFI PART", 8);
        NuwaData::putLE(data + 72, 2, 8);
        NuwaData::putLE(data + 80, 1, 4);
        NuwaData::putLE(data + 84, 128, 4);
      } else {
        NuwaData::putLE(data + 32, 10, 8);
        NuwaData::putLE(data + 40, 15, 8);
        for (unsigned i = 0; i < 5; ++i) data[56 + 2*i] = "modem"[i];
      }
    } else memset(data, 0xa5, NuwaData::Block);
    if (submitted) {
      submitted->set_value();
      assert(allowCompletion->wait_for(std::chrono::seconds(2)) == std::future_status::ready);
    }
  }
  bool prepare(uint64_t pa, CombinedRead::Command c, unsigned tag, unsigned block,
               uint64_t lba, unsigned blocks, const uint8_t *writeSource) {
    assert(heldLocks && pa == Dma && (c == CombinedRead::Command::Read ||
                                    c == CombinedRead::Command::WriteFua));
    ++prepares;
    preparedLba = lba;
    ocsReads = 0;
    writing = c == CombinedRead::Command::WriteFua;
    return CombinedRead::encode(virt, pa, c, tag, block, lba, blocks, writeSource);
  }
  uint32_t doorbell() {
    if (!active) return 0;
    if (seen++ == 0) return 1 | wire.foreignDb; // Foreign bit can disappear by final read.
    active = false;
    return 0;
  }
  uint32_t interrupt() const { return active && wire.fatal ? kUfsFatalStatus : 0; }
  uint32_t completedOcs() { ++ocsReads; if (writing) ++writeOcsReads; return wire.ocs; }
  void deadline() {}
  void barrier() {}
  bool expired() const { return wire.timedOut && ocsReads > 1; }
  void delay() {}
  void invalidateAll() {}
  const volatile uint8_t *response() const { return virt + 4608; }
} combined_hardware;

static CombinedRead::State combined_state;
#include "../package/nuwa-data-write/RetainedRead.inc"

// Minimal kernel-only glue for the actual candidate provider.
static struct { bool valid; uint64_t first, last, imageBytes; } gStoreGeometry;
static constexpr NuwaData::GptIdentity nuwaDataIdentity{
  61850624, 6, 61850618, 3110976, 61850618, {1}, {2}, {3}
};
static bool PE_parse_boot_argn(const char *, void *, size_t) { return false; }
static void *IOMallocZero(size_t) { assert(false); return nullptr; }
static void *IOMalloc(size_t n) { return std::malloc(n); }
static void IOFree(void *p, size_t) { std::free(p); }
#include "../package/nuwa-data-write/KernelPort.inc"

using IOReturn = int;
using UInt64 = uint64_t;
constexpr IOReturn kIOReturnSuccess = 0, kIOReturnBadArgument = 1, kIOReturnNotReady = 2,
                    kIOReturnTimeout = 3, kIOReturnIOError = 4, kIOReturnNotWritable = 5;
constexpr unsigned kIODirectionIn = 1;
constexpr size_t kDataMax = CombinedRead::Max;
static struct {
  uint64_t lba;
  unsigned command, ocs, dbSeen, isSeen, scsi, sense, result;
} gRootDiagnostic;
static uint64_t native_ufs_read_ticks, native_ufs_block_reads, native_ufs_block_failures;
static uint64_t timerTicks() { return 0; }
struct IOMemoryDescriptor {
  uint8_t data[512]{};
  size_t getLength() { return sizeof data; }
  unsigned getDirection() { return kIODirectionIn; }
  uint64_t writeBytes(uint64_t off, const void *src, uint64_t n) {
    assert(off <= sizeof data && n <= sizeof data - off);
    memcpy(data + off, src, n);
    return n;
  }
};
struct IOStorageAttributes {};
struct IOStorageCompletion {
  void *target, *parameter;
  void (*action)(void *, void *, IOReturn, uint64_t);
};
struct NativeUfsBlock {
  uint64_t absolute = 10 * 4096, bytes = 4096;
  uint8_t bounce[kDataMax]{};
  IOLock *windowLock = &::windowLock;
  bool online = true;
  IOReturn doAsyncReadWrite(IOMemoryDescriptor *, UInt64, UInt64,
                           IOStorageAttributes *, IOStorageCompletion *);
};
#include "FixtureRoot.inc"
#include "RootWindowRead.h"
#include "FixtureBlock.inc"

static uint64_t gStoreRegionFirst, gStoreRegionBlocks;
static unsigned storeMode() { return 2; }
static uint64_t reserveBlocks() { return 262144; }
#include "FixtureStore.inc"
#include "FixturePart.inc"

static unsigned native_ufs_store_mode() { return storeMode(); }
static int native_ufs_store_read(uint64_t, uint32_t, void *) { assert(false); return 0; }
static void IOLog(const char *, ...) {}
static uint32_t native_data_persist_state, native_data_persist_header, native_data_persist_gpt,
                native_data_persist_gpt_after;
static uint64_t native_data_persist_pages, native_data_persist_loaded, native_data_persist_first_lba,
                native_data_persist_present, native_ram_block_resident_bytes;
static const char *nuwa_data_persist_open_why;
struct NativeRamBlock {
  IOLock *gate = &ramGate;
  struct { uint64_t bytes, resident; uint8_t **pages; } sparse{};
  struct { uint64_t bytes = 8589934592ULL; } big;
  bool isBig = true, storeAttached = false, direct = false, directFailed = false;
  uint8_t seedHash[32]{};
  persist::Overlay overlay{};
  NuwaData::Overlay dataOverlay{};
  size_t dataMapBytes = 0;
  uint8_t *overlayBits = nullptr, *stage = nullptr, *dataMaps = nullptr, *dataScratch = nullptr;
  static constexpr uint32_t kStagePages = 32;
  static bool discardRequested() { return false; }
  struct StoreOps {
    bool read(uint64_t b, uint32_t n, void *d) { return native_ufs_store_read(b, n, d); }
    bool write(uint64_t b, uint32_t n, const void *p) { return native_ufs_store_write(b, n, p); }
    bool sync() { return native_ufs_store_sync(); }
  };
#include "FixtureAttach.inc"
};

static void startMockBoot(Response wire) {
  combined_hardware = {};
  combined_hardware.wire = wire;
  combined_state = {};
  combined_state.block = NuwaData::Block;
  combined_state.blocks = nuwaDataIdentity.capacity;
  combined_state.capacity = combined_state.blocks * NuwaData::Block;
  combined_state.setup.dma = Hardware::Dma;
  assert(PreservedNop::domain(combined_hardware, combined_state.setup));
  gHost = {true, false, &hostLock};
  gStoreGeometry = {true, nuwaDataIdentity.userdataFirst, nuwaDataIdentity.userdataLast, 8446279680ULL};
  // Fixture-only process replacement across independent test scenarios.
  new (&retainedSlot) NuwaData::Slot;
}

static void testAttach(const char *state) {
  const auto before = combined_hardware.submissions;
  const auto mmio = combined_hardware.mmioReads;
  NativeRamBlock ram;
  native_data_persist_state = 0;
  native_data_persist_gpt = 0xff;
  ram.attachStore();
  assert(!heldLocks && ram.storeAttached && native_data_persist_state == 4 &&
         native_data_persist_gpt == 0 && combined_hardware.submissions == before &&
         combined_hardware.mmioReads == mmio);
  std::printf("PASS attachStore %s: cached GPT; diagnostic UFS submissions=0\n", state);
}

static void test(const char *label, Response wire, CombinedRead::End end, NuwaData::State state,
                 bool allowRoot) {
  startMockBoot(wire);
  uint8_t block[NuwaData::Block]{};
  assert(!openCandidateData(0, 1, 1));
  assert(!dataProvider.write(0, 1, block) && !dataProvider.sync());
  IOLockLock(gHost.lock);
  assert(retainedReadLocked(10, 1) == end && retainedSlot.state() == state);
  assert(retainedReadyLocked() == allowRoot && gHost.poisoned == !allowRoot);
  assert(!retainedSlot.dataAllowed(true)); // Faults also disarm the underlying Data slot.
  IOLockUnlock(gHost.lock);
  assert(!dataProvider.write(0, 1, block) && !dataProvider.sync());
  assert(combined_hardware.prepares == 1 && combined_hardware.submissions == 1);

  uint8_t previous[CombinedRead::Bytes];
  memcpy(previous, combined_hardware.virt, sizeof previous);
  combined_hardware.wire = {};
  IOLockLock(gHost.lock);
  assert(dataPort.readPageLocked(10, block) == allowRoot);
  IOLockUnlock(gHost.lock);
  assert(!dataProvider.write(0, 1, block) && !dataProvider.sync());
  if (allowRoot) {
    for (auto b : block) assert(b == 0xa5);
    assert(combined_hardware.prepares == 2 && combined_hardware.submissions == 2);
    assert(!retainedSlot.dataAllowed(true));
  } else {
    assert(NuwaData::zero(block, sizeof block));
    assert(!memcmp(previous, combined_hardware.virt, sizeof previous));
    assert(combined_hardware.prepares == 1 && combined_hardware.submissions == 1);
  }
  std::printf("PASS %-30s next root=%s Data write/sync=denied\n",
              label, allowRoot ? "allowed" : "denied");
}

struct Request {
  IOMemoryDescriptor buffer;
  unsigned callbacks = 0;
  IOReturn status = -1;
  uint64_t bytes = 0;
  IOStorageCompletion completion{this, this, [](void *target, void *cookie, IOReturn result, uint64_t n) {
    auto &self = *static_cast<Request *>(target);
    assert(cookie == target && !heldLocks && ++self.callbacks == 1);
    self.status = result;
    self.bytes = n;
  }};
  void issue(NativeUfsBlock &block) {
    assert(block.doAsyncReadWrite(&buffer, 0, 1, nullptr, &completion) == kIOReturnSuccess);
    assert(callbacks == 1);
  }
};

template<class Entry>
static void runIsolationRace(bool snapshotFirst, Entry entry) {
  using namespace std::chrono_literals;
  Response wire{};
  wire.timedOut = true;
  wire.ocs = 15;
  startMockBoot(wire);
  NativeUfsBlock block;
  Request read;
  std::promise<void> boundary, resume, doorbell, complete;
  auto atBoundary = boundary.get_future(), attachResume = resume.get_future();
  auto rung = doorbell.get_future(), allowCompletion = complete.get_future();
  std::future<void> root;
  if (!snapshotFirst) {
    // Root owns the transport lock when attach tries to sample readiness.
    combined_hardware.submitted = &doorbell;
    combined_hardware.allowCompletion = &allowCompletion;
    root = std::async(std::launch::async, [&] { read.issue(block); });
    assert(rung.wait_for(2s) == std::future_status::ready);
  }

  SnapshotSchedule schedule{snapshotFirst, boundary, snapshotFirst ? &attachResume : nullptr};
  auto concurrent = std::async(std::launch::async, [&] {
    snapshotSchedule = &schedule;
    entry();
    assert(!heldLocks);
  });
  assert(atBoundary.wait_for(2s) == std::future_status::ready);
  assert(concurrent.wait_for(0s) == std::future_status::timeout);
  if (snapshotFirst)
    root = std::async(std::launch::async, [&] { read.issue(block); });
  else
    complete.set_value();
  assert(root.wait_for(2s) == std::future_status::ready);
  root.get();
  if (snapshotFirst) resume.set_value();
  assert(concurrent.wait_for(2s) == std::future_status::ready);
  concurrent.get();
  assert(read.status == kIOReturnTimeout && read.callbacks == 1);
  assert(combined_hardware.submissions == 1 && combined_hardware.prepares == 1);
}

static void testAttachRace(bool snapshotFirst) {
  runIsolationRace(snapshotFirst, [] {
    NativeRamBlock ram;
    ram.attachStore();
    assert(ram.storeAttached && native_data_persist_state == 4);
  });
  assert(!strcmp(nuwa_data_persist_open_why, snapshotFirst ? "window" : "nolayout"));
  assert(native_data_persist_gpt == 0);
  // Even bypassing the early snapshot, the real Provider must refuse a
  // geometrically valid read-only reopen before touching any GPT blocks.
  const auto mmio = combined_hardware.mmioReads;
  NuwaData::GptBuffers g{};
  constexpr NuwaData::Window w{59491258, 2097217};
  assert(!dataProvider.open(nuwaDataIdentity, 0, NuwaData::Block, 8446279680ULL, 262144, w, g));
  assert(!dataProvider.open(nuwaDataIdentity, 0, NuwaData::Block, 8446279680ULL, 262144, w, g, true));
  assert(combined_hardware.mmioReads == mmio && combined_hardware.submissions == 1);
  std::printf("PASS attach race %s: no deadlock, extra UFS submissions=0, write denied\n",
              snapshotFirst ? "snapshot before isolation" : "isolation before snapshot");
}

static void testParts() {
  startMockBoot({});
  combined_hardware.partMedia = true;
  uint32_t lun = 99;
  uint64_t first = 0, blocks = 0;
  uint8_t page[NuwaData::Block]{};
  assert(native_ufs_part_find("modem", &lun, &first, &blocks));
  assert(lun == 0 && first == 10 && blocks == 6 && combined_hardware.submissions == 2);
  assert(native_ufs_part_read(lun, first, 1, page) && combined_hardware.submissions == 3);
  for (auto b : page) assert(b == 0xa5);
  std::puts("PASS part_find/part_read ready: expected LUN, range and payload; 2+1 submissions");
  for (bool find : {true, false}) for (bool firstSnapshot : {true, false}) {
    runIsolationRace(firstSnapshot, [find] {
      uint32_t lun = 99;
      uint64_t first = 0, blocks = 0;
      uint8_t page[NuwaData::Block]{};
      if (find) {
        assert(!native_ufs_part_find("modem", &lun, &first, &blocks));
        assert(lun == 99 && !first && !blocks);
      } else {
        assert(!native_ufs_part_read(0, 10, 1, page));
        assert(NuwaData::zero(page, sizeof page));
      }
    });
    std::printf("PASS part_%s %s: refused, no deadlock, extra UFS submissions=0\n",
                find ? "find" : "read", firstSnapshot ? "snapshot-before-isolation" :
                "isolation-before-snapshot");
  }
}

// Only this fixture can supply positive cold-start/FUA proofs.
struct QualifiedWritePort : CandidatePort {
  static constexpr NuwaData::ColdStartIdentity Identity{11, 22, 33};
  NuwaData::ColdStartIdentity coldStartIdentityLocked(const NuwaData::GptIdentity &,
                                                      NuwaData::Window) { return Identity; }
  NuwaData::ColdStartEvidence coldStartEvidenceLocked(const NuwaData::GptIdentity &,
                                                      NuwaData::Window) {
    const NuwaData::ColdStartFact f{Identity, true};
    return {f, f, f, f, f, f, f, f};
  }
  bool fuaProvenLocked() { return true; }
};

static void testWrites() {
  using namespace NuwaData;
  constexpr Window window{59491258, 2097217};
  constexpr uint64_t rootBytes = 8446279680ULL, reserve = 262144;
  FixtureGpt disk;
  GptBuffers g{};
  uint8_t page[Block];
  for (unsigned i = 0; i < Block; ++i) page[i] = uint8_t(i ^ 0x96U);
  startMockBoot({});
  combined_hardware.gpt = &disk;
  assert(!dataProvider.open(disk.id, 0, Block, rootBytes, reserve, window, g, true));
  assert(dataProvider.open(disk.id, 0, Block, rootBytes, reserve, window, g));
  const unsigned reads = combined_hardware.submissions;
  const unsigned mmio = combined_hardware.mmioReads;
  assert(reads == 4 && !native_ufs_store_write(0, 1, page) && !native_ufs_store_sync() &&
         combined_hardware.submissions == reads && combined_hardware.mmioReads == mmio &&
         !combined_hardware.writeSubmissions);
  dataProvider.close();
  std::puts("PASS production write/sync: even an open read-only window submits no write or MMIO");

  startMockBoot({});
  combined_hardware.gpt = &disk;
  QualifiedWritePort port;
  Provider<QualifiedWritePort, true> provider(port, retainedSlot);
  assert(provider.open(disk.id, 0, Block, rootBytes, reserve, window, g, true));
  assert(combined_hardware.submissions == 4 && !combined_hardware.writeSubmissions);
  assert(!provider.write(window.blocks, 1, page) && combined_hardware.submissions == 4);
  assert(provider.write(0, 1, page));
  const uint8_t *cdb = combined_hardware.lastCdb;
  assert(cdb[0] == 0x2a && cdb[1] == 0x08 && CombinedRead::be32(cdb + 2) == window.first &&
         cdb[6] == 0 && cdb[7] == 0 && cdb[8] == 1 && cdb[9] == 0);
  assert(!memcmp(page, combined_hardware.written, Block) && combined_hardware.submissions == 5 &&
         combined_hardware.writeSubmissions == 1 && combined_hardware.writeOcsReads == 1);
  const auto afterWrite = combined_hardware.mmioReads;
  assert(provider.sync() && combined_hardware.mmioReads == afterWrite &&
         combined_hardware.submissions == 5);
  std::puts("PASS real WRITE(10): LUN0, FUA=1, 4096 B, DB0 once, GOOD; sync no hardware");

  IOLockLock(gHost.lock);
  assert(retainedSlot.submit(true, true));
  assert(port.writePageLocked(1, window, window.first, 1, page) == Evidence::Unowned);
  assert(port.writePageLocked(0, window, window.first + window.blocks, 1, page) == Evidence::Unowned);
  assert(port.writePageLocked(0, window, window.first, 2, page) == Evidence::Unowned);
  IOLockUnlock(gHost.lock);
  assert(!provider.sync() && combined_hardware.submissions == 5 &&
         combined_hardware.prepares == 5 && combined_hardware.mmioReads == afterWrite);
  provider.close();
  std::puts("PASS write port rejects non-LUN0, out-of-window and multi-block before DMA; sync rejects in-flight");

  for (unsigned fault = 0; fault < 3; ++fault) {
    startMockBoot({});
    combined_hardware.gpt = &disk;
    assert(provider.open(disk.id, 0, Block, rootBytes, reserve, window, g, true));
    auto &r = combined_hardware.wire;
    if (fault == 0) { r.status = 2; r.dl = 16; }
    if (fault == 1) { r.flags = 0x20; r.residual = 512; }
    if (fault == 2) { r.timedOut = true; r.ocs = 15; }
    assert(!provider.write(0, 1, page));
    assert(retainedSlot.state() == (fault == 2 ? State::TIMEOUT_ORPHAN : State::FATAL_QUARANTINED));
    assert(!retainedSlot.rootAllowed() && gHost.poisoned && !gHost.ready);
    uint8_t saved[CombinedRead::Bytes];
    memcpy(saved, combined_hardware.virt, sizeof saved);
    const auto failedMmio = combined_hardware.mmioReads;
    combined_hardware.wire = {};
    assert(!provider.sync() && !provider.write(0, 1, page));
    provider.close();
    assert(!provider.open(disk.id, 0, Block, rootBytes, reserve, window, g, true));
    assert(combined_hardware.submissions == 5 && combined_hardware.writeSubmissions == 1 &&
           combined_hardware.mmioReads == failedMmio &&
           !memcmp(saved, combined_hardware.virt, sizeof saved));
    std::printf("PASS write %s: isolated; sync/reopen denied; no replay or DMA reuse\n",
                fault == 0 ? "CHECK CONDITION" : fault == 1 ? "residual" : "timeout");
  }
}

static void testTerminal(bool timeout) {
  using NuwaData::State;
  using namespace std::chrono_literals;
  Response wire{};
  wire.timedOut = timeout;
  wire.ocs = timeout ? 15 : 0;
  wire.fatal = !timeout;
  startMockBoot(wire);
  const auto *const mapping = combined_hardware.virt;
  const auto dma = combined_state.setup.dma;
  uint8_t snapshot[CombinedRead::Bytes];
  uint8_t waitingBlock[NuwaData::Block]{};
  NativeUfsBlock block;
  Request first, waiter, later;
  std::promise<void> submitted, allowCompletion, waiting;
  auto entered = waiting.get_future(), rung = submitted.get_future(), release = allowCompletion.get_future();
  combined_hardware.submitted = &submitted;
  combined_hardware.allowCompletion = &release;
  auto firstDone = std::async(std::launch::async, [&] { first.issue(block); });
  assert(rung.wait_for(2s) == std::future_status::ready);
  auto result = std::async(std::launch::async, [&] {
    waitingWindow = &waiting;
    waiter.issue(block);
  });
  assert(entered.wait_for(2s) == std::future_status::ready);
  assert(result.wait_for(0s) == std::future_status::timeout);
  allowCompletion.set_value();
  assert(firstDone.wait_for(2s) == std::future_status::ready);
  firstDone.get();
  assert(result.wait_for(2s) == std::future_status::ready);
  result.get();
  assert(retainedSlot.state() == (timeout ? State::TIMEOUT_ORPHAN : State::FATAL_QUARANTINED));
  assert(first.status == (timeout ? kIOReturnTimeout : kIOReturnIOError) &&
         waiter.status == kIOReturnNotReady && first.bytes == 0 && waiter.bytes == 0);
  // Hardware changes the old DMA after the fault. Check the software leaves
  // that region untouched even with DB=0, good OCS and new payload bytes.
  combined_hardware.wire = {};
  combined_hardware.active = false;
  combined_hardware.virt[8] = 0;
  combined_hardware.virt[CombinedRead::Data] = 0x77;
  memcpy(snapshot, mapping, sizeof snapshot);
  const auto mmioReads = combined_hardware.mmioReads;
  later.issue(block);
  assert(later.status == kIOReturnNotReady && later.bytes == 0);
  dataProvider.close();
  NuwaData::GptBuffers g{};
  constexpr NuwaData::Window window{59491258, 2097217};
  assert(NuwaData::placement(nuwaDataIdentity, 8446279680ULL, 262144, window));
  assert(!dataProvider.open(nuwaDataIdentity, 0, NuwaData::Block, 8446279680ULL, 262144, window, g));
  assert(!openCandidateData(1, 1, 1));
  IOLockLock(gHost.lock);
  assert(!dataPort.readPageLocked(10, waitingBlock));
  IOLockUnlock(gHost.lock);
  assert(!dataProvider.write(0, 1, waitingBlock) && !dataProvider.sync());
  assert(NuwaData::zero(waitingBlock, sizeof waitingBlock));
  assert(combined_hardware.prepares == 1 && combined_hardware.submissions == 1 &&
         combined_hardware.mmioReads == mmioReads && combined_hardware.virt == mapping &&
         combined_state.setup.dma == dma && !memcmp(snapshot, mapping, sizeof snapshot));
  assert(first.callbacks == 1 && waiter.callbacks == 1 && later.callbacks == 1);
  std::printf("PASS block entry %s: first/waiter/later complete once unlocked; waiter/later NotReady\n",
              timeout ? "timeout" : "fatal");
  std::printf("PASS %s + late completion: waiter denied; close/reopen denied; no DMA/MMIO reuse\n",
              timeout ? "timeout" : "fatal");
  if (timeout) testAttach("isolated");
}

int main() {
  using CombinedRead::End;
  using NuwaData::State;
  const auto fatal = State::FATAL_QUARANTINED;
  Response check{};
  check.status = 2;
  check.dl = 16;
  test("CHECK CONDITION + valid sense", check, End::Scsi, State::COMPLETED_CMDERR, true);
  check.flags = 0x20;
  check.residual = NuwaData::Block;
  test("CHECK CONDITION + underflow", check, End::Scsi, State::COMPLETED_CMDERR, true);
  auto bad = check;
  bad.status = 0xff;
  test("reserved status ff", bad, End::Response, fatal, false);
  bad.status = 8;
  test("unsupported BUSY status", bad, End::Response, fatal, false);
  bad = check; bad.dl = 0;
  test("CHECK CONDITION without sense", bad, End::Response, fatal, false);
  bad = check; bad.badSense = true;
  test("invalid sense", bad, End::Response, fatal, false);
  bad = check; bad.badTag = true;
  test("wrong tag", bad, End::Response, fatal, false);
  bad = check; bad.flags = 0;
  test("contradictory residual", bad, End::Response, fatal, false);
  bad = check; bad.residual++;
  test("oversized residual", bad, End::Response, fatal, false);
  bad = check; bad.foreignDb = 2;
  test("foreign DB bit then clear", bad, End::Transport, fatal, false);
  bad = check; bad.ocs = 1;
  test("nonzero OCS", bad, End::Transport, fatal, false);
  bad = check; bad.type = 0x36;
  test("wrong UPIU type", bad, End::Response, fatal, false);
  bad = check; bad.lun = 1;
  test("wrong LUN", bad, End::Response, fatal, false);
  bad = check; bad.dl = 481;
  test("oversized UPIU length", bad, End::Response, fatal, false);
  startMockBoot({});
  testAttach("write gate closed");
  testTerminal(true);
  testTerminal(false);
  testAttachRace(true);
  testAttachRace(false);
  testParts();
  testWrites();
}
