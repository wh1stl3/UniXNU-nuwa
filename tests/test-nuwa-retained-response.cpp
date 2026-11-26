// Compile against the candidate's staged CombinedRead.h, not the baseline copy.
#include "../package/nuwa-data-write/Provider.h"
#include "../package/nuwa-data-write/Descriptor.h"
#include "../package/nuwa-data-write/DualBankLogOverlay.h"
#include "NuwaDataFixtureGpt.h"
#include "../package/nuwa-ramblock/PersistOpenReason.h"
#include "PersistOverlay.h"
#include <cassert>
#include <array>
#include <cstdlib>
#include <cstdio>
#include <future>
#include <memory>
#include <mutex>
#include <new>
#include <thread>
#include <unordered_map>
#include <vector>
#include "TransferPoll.h"
#include "PreservedNop.h"
#include "CombinedRead.h"
#include "RootReadSession.h"

struct Response {
  unsigned status = 0, flags = 0, residual = 0, ocs = 0, foreignDb = 0;
  unsigned type = 0x21, lun = 0, dl = 0;
  bool badTag = false, badSense = false, timedOut = false, fatal = false;
};

#if defined(NUWA_SB0_HOST_FIXTURE) && NUWA_SB0_HOST_FIXTURE == 1
#ifdef KERNEL
#error SB0 fixture is not a kernel entry
#endif
#include "NuwaSb0Experiment.h"
#endif

using MediaPage = std::array<uint8_t, NuwaData::Block>;
struct Sb0Media {
  enum class Cut { None, LostOnPowerCut, Torn, ErrorAlreadyWritten };
  Cut cut = Cut::None;
  Response writeWire{};
  uint64_t corruptAt = UINT64_MAX, readErrorAt = UINT64_MAX;
  bool guardAfterPrepare = false;
  std::vector<uint64_t> reads;
  MediaPage existing{}, persisted{};
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
  bool descriptor = false, modeSense = false, dpofua = false, wce = false;
  Response modeWire{};
  unsigned modeCount = 0;
  unsigned descCount = 0, queryCode = 0, descLength = 0;
  const NuwaData::FixtureGpt *gpt = nullptr;
  Sb0Media *sb0 = nullptr;
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
      case 0x50: return Dma + (sb0 && writing && sb0->guardAfterPrepare ? 0x1000 : 0);
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
    if (descriptor) {
      ++descCount;
      const auto *u = virt + 4096;
      assert(u[0] == 0x16 && !u[1] && !u[2] && u[5] == 1 &&
             !u[10] && !u[11] && u[12] == 1 && !u[15] && !u[18] && u[19] == 255 &&
             !(NuwaData::le32(virt) & (3U << 25)) &&
             !(NuwaData::le32(virt + 28) & 0xffff));
      r[0] = 0x36;
      r[3] = u[3] ^ unsigned(wire.badTag);
      r[5] = 1;
      memcpy(r + 12, u + 12, 4);
      r[6] = queryCode;
      if (!r[6] && u[13] == 2 && u[14] == 2) r[6] = 0xfc;
      if (r[6]) return;
      const unsigned n = descLength ? descLength : 32;
      r[10] = n >> 8;
      r[11] = n;
      r[18] = r[10];
      r[19] = r[11];
      uint8_t *d = r + 32;
      d[0] = n;
      d[1] = u[13];
      if (!u[13]) {
        d[6] = 2;
        d[8] = 1;
        d[0x18] = 1;
        d[0x19] = 0xce;
      } else {
        d[2] = u[14];
        d[3] = u[14] == 0 || u[14] == 3;
        d[5] = u[14] == 3 ? 2 : 0;
        d[0xa] = 12;
        d[0x12] = 60;
      }
      return;
    }
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
    if (modeSense) {
      ++modeCount;
      const auto *u = virt + 4096;
      constexpr uint8_t cdb[] = {0x5a, 8, 8, 0, 0, 0, 0, 0, 0x40, 0};
      assert(!memcmp(u + 16, cdb, sizeof cdb) && u[0] == 1 && u[1] == 0x40 && u[2] == 0 &&
             CombinedRead::be32(u + 12) == 64 && (NuwaData::le32(virt) & (3U << 25)) == (2U << 25) &&
             (NuwaData::le32(virt + 28) & 0xffff) == 1 &&
             NuwaData::le64(virt + 5120) == Dma + CombinedRead::Data &&
             NuwaData::le32(virt + 5132) == 63);
      data[1] = 26; // 8 B header + 20 B Caching page.
      data[3] = dpofua ? 0x10 : 0;
      data[8] = 0x88; // PS bit is not part of the page code.
      data[9] = 18;
      data[10] = wce ? 4 : 0;
    } else if (writing) {
      ++writeSubmissions;
      memcpy(lastCdb, virt + 4112, sizeof lastCdb);
      memcpy(written, data, sizeof written);
      assert(virt[4097] == 0x20 && virt[4098] == 0 &&
             CombinedRead::be32(virt + 4108) == NuwaData::Block);
      assert((NuwaData::le32(virt) & (3U << 25)) == (1U << 25));
      assert(NuwaData::le64(virt + 5120) == Dma + CombinedRead::Data &&
             NuwaData::le32(virt + 5132) == NuwaData::Block - 1);
      if (sb0) {
        assert(preparedLba == NuwaData::DualBankLogOverlay<>::Media.first);
        assert(sb0->reads.size() == 5 + NuwaData::DualBankLogOverlay<>::Data0);
        const auto cut = sb0->cut;
        if (cut == Sb0Media::Cut::Torn) memcpy(sb0->persisted.data(), data, NuwaData::Block / 2);
        else if (cut == Sb0Media::Cut::ErrorAlreadyWritten ||
                 (!wire.badTag && !wire.lun &&
                  !wire.residual && !wire.status && !wire.timedOut))
          memcpy(sb0->persisted.data(), data, NuwaData::Block);
        if (wire.timedOut) r[0] = 0; // Completion is not yet present in the old DMA.
      }
    } else if (sb0) {
      const auto *cdb = virt + 4112;
      assert(virt[4097] == 0x40 && virt[4098] == 0 &&
             CombinedRead::be32(virt + 4108) == NuwaData::Block &&
             cdb[0] == 0x28 && CombinedRead::be32(cdb + 2) == preparedLba &&
             cdb[7] == 0 && cdb[8] == 1);
      sb0->reads.push_back(preparedLba);
      const auto *page = gpt->at(preparedLba);
      if (page) memcpy(data, page, NuwaData::Block);
      else if (preparedLba == sb0->corruptAt) memcpy(data, sb0->existing.data(), NuwaData::Block);
      else memset(data, 0, NuwaData::Block);
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
               uint64_t lba, unsigned blocks, const uint8_t *writeSource, NuwaUfsDesc::Request desc) {
    assert(heldLocks && pa == Dma && (c == CombinedRead::Command::Read ||
                                     c == CombinedRead::Command::WriteFua ||
                                      c == CombinedRead::Command::QueryDesc ||
                                      c == CombinedRead::Command::ModeSense));
    ++prepares;
    preparedLba = lba;
    ocsReads = 0;
    writing = c == CombinedRead::Command::WriteFua;
    descriptor = c == CombinedRead::Command::QueryDesc;
    modeSense = c == CombinedRead::Command::ModeSense;
    if (modeSense) wire = modeWire;
    if (sb0) {
      wire = writing ? sb0->writeWire : Response{};
      if (!writing && lba == sb0->readErrorAt) { wire.status = 2; wire.dl = 16; }
    }
    return CombinedRead::encode(virt, pa, c, tag, block, lba, blocks, writeSource, desc);
  }
  uint32_t doorbell() {
    if (!active) return 0;
    if (seen++ == 0) return 1 | wire.foreignDb; // Foreign bit can disappear by final read.
    if (sb0 && wire.timedOut) return 1;
    active = false;
    return 0;
  }
  uint32_t interrupt() const { return active && wire.fatal ? kUfsFatalStatus : 0; }
  uint32_t completedOcs() { ++ocsReads; if (writing) ++writeOcsReads; return wire.ocs; }
  void deadline() {}
  void barrier() {}
  bool expired() const { return wire.timedOut && (sb0 ? seen > 2 : ocsReads > 1); }
  void delay() {}
  void invalidateAll() {}
  const volatile uint8_t *response() const { return virt + 4608; }
  const volatile uint8_t *data() const { return virt + CombinedRead::Data; }
} combined_hardware;

static CombinedRead::State combined_state;
#include "../package/nuwa-data-write/RetainedRead.inc"

// Minimal kernel-only glue for the actual candidate provider.
static struct { bool valid; uint64_t first, last, imageBytes; } gStoreGeometry;
static constexpr NuwaData::GptIdentity nuwaDataIdentity{
  61850624, 6, 61850618, 3110976, 61850618, {1}, {2}, {3}
};
static unsigned descOptIn, dataWriteArg;
static bool PE_parse_boot_argn(const char *name, void *value, size_t n) {
  const unsigned arg = !strcmp(name, "nuwa-ufs-desc") ? descOptIn :
                       !strcmp(name, "nuwa-data-write") ? dataWriteArg : 0;
  if (!arg) return false;
  assert(n == sizeof arg);
  memcpy(value, &arg, n);
  return true;
}
static size_t seenAllocations, seenFrees;
using DataOverlay = NuwaData::DualBankLogOverlay<>;
static void *IOMallocZero(size_t n) {
  if (n == sizeof(DataOverlay::SeenScratch)) ++seenAllocations;
  return std::calloc(1, n);
}
static void *IOMalloc(size_t n) { return std::malloc(n); }
static void IOFree(void *p, size_t n) {
  if (n == sizeof(DataOverlay::SeenScratch)) ++seenFrees;
  std::free(p);
}
#include "../package/nuwa-data-write/KernelPort.inc"
#include "../package/nuwa-data-write/RetainedDesc.inc"

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
struct RamMedia {
  std::unordered_map<uint64_t, MediaPage> pages;
  size_t reads = 0, writes = 0, syncs = 0;
  bool failLog = false, failed = false;
  bool read(uint64_t b, uint32_t n, void *d) {
    assert(b < DataOverlay::Media.blocks && n == 1);
    ++reads;
    const auto i = pages.find(b);
    if (i == pages.end()) memset(d, 0, NuwaData::Block);
    else memcpy(d, i->second.data(), NuwaData::Block);
    return true;
  }
  bool write(uint64_t b, uint32_t n, const void *p) {
    assert(!failed && b < DataOverlay::Media.blocks && n == 1);
    ++writes;
    if (failLog && b >= DataOverlay::Log && b < DataOverlay::Data0) {
      failed = true;
      return false;
    }
    memcpy(pages[b].data(), p, NuwaData::Block);
    return true;
  }
  bool sync() { assert(!failed); ++syncs; return true; }
};
static RamMedia *ramMedia;
static uint64_t candidateFirst, candidateBlocks;
static bool fixtureOpenCandidateData(uint64_t first, uint64_t blocks, uint64_t reserve) {
  candidateFirst = first;
  candidateBlocks = blocks;
  if (ramMedia) {
    assert(NuwaData::placement(nuwaDataIdentity, gStoreGeometry.imageBytes, reserve, {first, blocks}));
    return !ramMedia->failed;
  }
  return openCandidateData(first, blocks, reserve);
}
#define openCandidateData fixtureOpenCandidateData
#include "FixtureStore.inc"
#undef openCandidateData
#include "FixturePart.inc"

static unsigned native_ufs_store_mode() { return storeMode(); }
static int native_ufs_store_read(uint64_t, uint32_t, void *) { assert(false); return 0; }
static void IOLog(const char *, ...) {}
static uint32_t native_data_persist_state, native_data_persist_header, native_data_persist_gpt,
                native_data_persist_gpt_after;
static uint64_t native_data_persist_pages, native_data_persist_loaded, native_data_persist_first_lba,
                 native_data_persist_present, native_ram_block_resident_bytes, native_data_persist_writes,
                 native_data_persist_syncs, native_data_persist_errors;
static const char *nuwa_data_persist_open_why;
static const MediaPage seedPage = [] { MediaPage p{}; p.fill(0x5e); return p; }();
struct NativeRamBlock {
  IOLock *gate = &ramGate;
  struct { uint64_t bytes, resident; uint8_t **pages; const uint8_t *find(uint64_t) { return nullptr; } } sparse{};
  struct { uint64_t bytes = 8589934592ULL; const uint8_t *find(uint64_t) { return seedPage.data(); } } big;
  bool online = true, isBig = true, storeAttached = false, direct = false, directFailed = false;
  uint8_t seedHash[32]{};
  persist::Overlay overlay{};
  DataOverlay dataOverlay{};
  DataOverlay::Workspace *dataWorkspace = nullptr;
  uint8_t *overlayBits = nullptr, *stage = nullptr;
  static constexpr uint32_t kStagePages = 32;
  static bool discardRequested() { return ramMedia != nullptr; }
  struct StoreOps {
    bool read(uint64_t b, uint32_t n, void *d) { return ramMedia ? ramMedia->read(b, n, d) : native_ufs_store_read(b, n, d); }
    bool write(uint64_t b, uint32_t n, const void *p) { return ramMedia ? ramMedia->write(b, n, p) : native_ufs_store_write(b, n, p); }
    bool sync() { return ramMedia ? ramMedia->sync() : native_ufs_store_sync(); }
  };
  ~NativeRamBlock() { std::free(dataWorkspace); std::free(stage); std::free(overlayBits); }
#include "FixtureAttach.inc"
#include "FixtureRamIO.inc"
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
  gStoreRegionFirst = gStoreRegionBlocks = 0;
  // Fixture-only process replacement across independent test scenarios.
  new (&retainedSlot) NuwaData::Slot;
  dataWriteArg = descOptIn = ufsDescClaimed = ufsDescPublished = liveGptStatus = 0;
  ufsDescSnapshot = {};
  ufsModeSnapshot = {};
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

struct RamBuffer {
  std::vector<uint8_t> data;
  size_t limit = SIZE_MAX;
  RamBuffer(size_t n, uint8_t byte) : data(n, byte) {}
  uint64_t read(uint64_t at, void *dst, uint64_t n) {
    assert(at <= data.size() && n <= data.size() - at);
    if (at + n > limit) return 0;
    memcpy(dst, data.data() + at, n);
    return n;
  }
  uint64_t copy(uint64_t at, const void *src, uint64_t n) {
    assert(at <= data.size() && n <= data.size() - at);
    memcpy(data.data() + at, src, n);
    return n;
  }
};

static size_t ramIO(NativeRamBlock &ram, bool write, uint64_t offset, RamBuffer &buffer) {
  IOLockLock(ram.gate);
  const auto n = ram.candidateIO(write, offset, buffer.data.size(), buffer);
  IOLockUnlock(ram.gate);
  return n;
}

static void testRamOverlay() {
  constexpr size_t block = NuwaData::Block, page = 32767, offset = page * block;
  startMockBoot({});
  RamMedia media;
  ramMedia = &media;
  NativeRamBlock ram;
  const auto allocations = seenAllocations, frees = seenFrees;
  ram.attachStore();
  assert(seenAllocations == allocations + 1 && seenFrees == frees + 1);
  assert(ram.direct && native_data_persist_state == 1 && native_data_persist_present == 0);
  assert(candidateFirst == 57393401 && candidateBlocks == 4195074 &&
         candidateFirst + candidateBlocks == 61588475 && gStoreRegionFirst == candidateFirst);
  RamBuffer one(block, 0x11);
  assert(ramIO(ram, true, offset, one) == one.data.size() && native_data_persist_present == 1);
  const auto reads = media.reads;
  one.data.assign(block, 0x22);
  assert(ramIO(ram, true, offset, one) == one.data.size() && media.reads == reads &&
         native_data_persist_present == 1);
  assert(media.pages.at(DataOverlay::Data0 + page).front() == 0x11 &&
         media.pages.at(DataOverlay::Data1 + page).front() == 0x22);
  std::puts("PASS RamBlock first write and full overwrite: bank 0/1, overwrite reads=0");

  RamBuffer partial(31 * block, 0x33); // touches 32 pages, first & last are RMW
  const auto commits = native_data_persist_syncs;
  const auto writes = media.writes;
  assert(ramIO(ram, true, offset + 512, partial) == partial.data.size());
  assert(native_data_persist_syncs == commits + 1 && media.writes == writes + 33 &&
         media.reads == reads + 1 && native_data_persist_present == 32);
  RamBuffer payload(32 * block, 0);
  const auto checkBatch = [&](NativeRamBlock &disk) {
    assert(ramIO(disk, false, offset, payload) == payload.data.size());
    for (size_t i = 0; i < payload.data.size(); ++i)
      assert(payload.data[i] == (i < 512 ? 0x22 : i < 31 * block + 512 ? 0x33 : 0x5e));
  };
  checkBatch(ram);
  assert(ramIO(ram, true, offset, payload) == payload.data.size()); // bank 1 across boundary
  std::puts("PASS RamBlock 32-page batch: one log, partial edges preserved, one media RMW read");

  // Fill the first epoch by updating a separate page; fail the next log
  // after its checkpoint and both inactive data writes have persisted.
  for (uint32_t i = 4; i < DataOverlay::LogBlocks; ++i)
    assert(ramIO(ram, true, 0, one) == one.data.size());
  RamBuffer shortSource(3 * block, 0xff);
  shortSource.limit = 2 * block;
  const auto beforeShort = media.writes;
  assert(ramIO(ram, true, offset, shortSource) == 0 && media.writes == beforeShort && !ram.directFailed);
  media.failLog = true;
  RamBuffer cut(2 * block, 0x44);
  assert(ramIO(ram, true, offset, cut) == 0 && ram.directFailed && native_data_persist_state == 5);
  const auto submitted = media.writes, synced = media.syncs, loaded = media.reads;
  assert(ramIO(ram, true, offset, cut) == 0 && ram.doSynchronizeCache() == kIOReturnIOError);
  ram.attachStore();
  assert(native_data_persist_state == 5 && media.writes == submitted && media.syncs == synced &&
         media.reads == loaded);
  std::puts("PASS RamBlock state=5: write/sync/reopen refused, extra submissions=0");

  startMockBoot({});
  media.failed = media.failLog = false;
  NativeRamBlock resumed;
  resumed.attachStore();
  assert(native_data_persist_state == 2 && native_data_persist_present == 33 &&
         resumed.dataOverlay.generation() == DataOverlay::LogBlocks &&
         seenAllocations == allocations + 2 && seenFrees == frees + 2);
  checkBatch(resumed);
  // Inspect both sides of the bitmap-block boundary in the checkpoint, as
  // well as the actual page data recovered across it.
  assert((media.pages.at(DataOverlay::Map1)[4095] & 0x80) != 0 &&
         (media.pages.at(DataOverlay::Map1 + 1)[0] & 1) != 0);
  assert((media.pages.at(DataOverlay::Map1 + DataOverlay::MapBlocks)[4095] & 0x80) != 0 &&
         (media.pages.at(DataOverlay::Map1 + DataOverlay::MapBlocks + 1)[0] & 1) != 0);
  std::puts("PASS RamBlock checkpoint recovery: old batch across bitmap-block boundary, present=33");
  ramMedia = nullptr;
}

static void testRamAmplification() {
  for (const size_t run : {1, 32}) {
    startMockBoot({});
    RamMedia media;
    ramMedia = &media;
    NativeRamBlock ram;
    ram.attachStore();
    RamBuffer input(run * NuwaData::Block, 0x66);
    assert(ramIO(ram, true, 0, input) == input.data.size());
    const auto initial = media.writes;
    for (uint32_t i = 0; i < DataOverlay::LogBlocks; ++i)
      assert(ramIO(ram, true, 0, input) == input.data.size());
    const auto user = DataOverlay::LogBlocks * run;
    assert(media.writes - initial == user + DataOverlay::LogBlocks + 129);
    std::printf("PASS RamBlock %zu-page amplification: %.6fx\n", run, double(media.writes - initial) / user);
    ramMedia = nullptr;
  }
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
  constexpr auto w = DataOverlay::Media;
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
  constexpr auto window = DataOverlay::Media;
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

static void testDescriptors() {
  using namespace NuwaUfsDesc;
  char row[79]{};
  startMockBoot({});
  probeUfsDescriptors();
  descOptIn = 2;
  probeUfsDescriptors();
  assert(!cachedUfsDescRow(row, sizeof row) && !combined_hardware.mmioReads &&
          !cachedUfsModeRow(row, sizeof row) && !combined_hardware.submissions);
  std::puts("PASS READ_DESC default and invalid opt-in: no MMIO, no row");

  DescriptorPort port;
  uint8_t buf[MaxBytes]{};
  assert(port.read_descriptor(2, MaxLuns, buf).status == Status::Invalid &&
         port.read_descriptor(2, 0xc4, buf).status == Status::Invalid &&
         port.read_descriptor(0, 1, buf).status == Status::Invalid &&
         !combined_hardware.mmioReads && !combined_hardware.submissions);
  std::puts("PASS READ_DESC invalid and well-known LUNs rejected before MMIO");

  descOptIn = 1;
  probeUfsDescriptors();
  probeUfsDescriptors();
  assert(combined_hardware.submissions == 6 && combined_hardware.descCount == 5 &&
          combined_hardware.modeCount == 1 &&
         !combined_hardware.writeSubmissions && retainedSlot.rootAllowed());
  assert(ufsDescSnapshot.bootEnable == 1 && ufsDescSnapshot.lus == 2 &&
         ufsDescSnapshot.units[0].blockSize == 4096 && ufsDescSnapshot.units[3].blocks == 60 &&
         !ufsDescSnapshot.units[1].enabled && !ufsDescSnapshot.units[2].enabled &&
         ufsDescSnapshot.wp == 8);
  const auto before = combined_hardware.mmioReads;
  assert(cachedUfsDescRow(row, sizeof row) &&
         !strcmp(row, "UFS lu=2 bs=4096 wp=00000008 mfr=01ce"));
  assert(combined_hardware.mmioReads == before);
  std::printf("PASS READ_DESC opt-in once: 5 read-only Query UPIUs, %s\n", row);

  for (unsigned fault = 0; fault < 5; ++fault) {
    startMockBoot({});
    descOptIn = 1;
    if (fault == 0) combined_hardware.queryCode = 0xfe;
    if (fault == 1) combined_hardware.descLength = 8; // bounded, attributed, too short
    if (fault == 2) combined_hardware.descLength = 256; // unowned envelope
    if (fault == 3) combined_hardware.wire.badTag = true;
    if (fault == 4) {
      combined_hardware.wire.timedOut = true;
      combined_hardware.wire.ocs = 15;
    }
    static constexpr Status statuses[] = {
      Status::CommandError, Status::Malformed, Status::Unowned, Status::Unowned, Status::Timeout
    };
    static constexpr const char *labels[] = {
      "query result FE", "short descriptor", "oversize envelope", "wrong tag", "timeout"
    };
    probeUfsDescriptors();
    assert(ufsDescSnapshot.result.status == statuses[fault] &&
           cachedUfsDescRow(row, sizeof row) && !strncmp(row, "UFS err=", 8));
    assert(combined_hardware.submissions == (fault < 2 ? 2U : 1U) &&
           combined_hardware.modeCount == (fault < 2 ? 1U : 0U) && combined_hardware.descCount == 1 &&
           !combined_hardware.writeSubmissions && retainedSlot.rootAllowed() == (fault < 2));
    const auto mmio = combined_hardware.mmioReads;
    if (fault >= 2) {
      uint8_t held[CombinedRead::Bytes], page[NuwaData::Block]{};
      memcpy(held, combined_hardware.virt, sizeof held);
      probeUfsDescriptors();
      assert(!native_ufs_part_read(0, 10, 1, page));
      assert(combined_hardware.submissions == 1 && combined_hardware.mmioReads == mmio &&
             !memcmp(held, combined_hardware.virt, sizeof held));
    } else {
      combined_hardware.wire = {};
      uint8_t page[NuwaData::Block]{};
      assert(native_ufs_part_read(0, 10, 1, page) && combined_hardware.submissions == 3);
    }
    std::printf("PASS READ_DESC %s: %s, next root=%s\n", labels[fault],
                row, fault < 2 ? "allowed" : "isolated");
  }
}

static void testModeSense() {
  using namespace NuwaUfsDesc;
  char row[79]{};
  for (unsigned value = 0; value < 4; ++value) {
    startMockBoot({});
    descOptIn = 1;
    combined_hardware.dpofua = value & 2;
    combined_hardware.wce = value & 1;
    // Normal underflow: complete 28-byte parameter list in a 64-byte allocation.
    combined_hardware.modeWire.residual = 36;
    combined_hardware.modeWire.flags = 0x20;
    probeUfsDescriptors();
    probeUfsDescriptors();
    char expected[79];
    snprintf(expected, sizeof expected, "UFS2 dpofua=%u wce=%u gpt=unk", value >> 1, value & 1);
    const auto mmio = combined_hardware.mmioReads;
    assert(cachedUfsModeRow(row, sizeof row) && !strcmp(row, expected) &&
           combined_hardware.modeCount == 1 && combined_hardware.submissions == 6 &&
           !combined_hardware.writeSubmissions && combined_hardware.mmioReads == mmio);
    std::printf("PASS MODE SENSE(10) read-only once: %s\n", row);
  }
  for (unsigned fault = 0; fault < 4; ++fault) {
    startMockBoot({});
    descOptIn = 1;
    auto &r = combined_hardware.modeWire;
    if (fault < 2) { r.flags = 0x20; r.residual = fault == 0 ? 57 : 54; }
    if (fault == 2) { r.status = 2; r.dl = 16; }
    if (fault == 3) { r.ocs = 15; r.timedOut = true; }
    static constexpr const char *rows[] = {
        "UFS2 err=6 sc=000000", "UFS2 err=6 sc=000000",
        "UFS2 err=3 sc=050000", "UFS2 err=5 sc=000000"
    };
    static constexpr const char *labels[] = {"short header", "short caching page", "CHECK CONDITION", "timeout"};
    probeUfsDescriptors();
    assert(cachedUfsModeRow(row, sizeof row) && !strcmp(row, rows[fault]) &&
           combined_hardware.modeCount == 1 && combined_hardware.submissions == 6 &&
           !combined_hardware.writeSubmissions && retainedSlot.rootAllowed() == (fault != 3));
    if (fault == 3) {
      const auto mmio = combined_hardware.mmioReads;
      uint8_t page[NuwaData::Block]{};
      assert(retainedSlot.state() == NuwaData::State::TIMEOUT_ORPHAN);
      probeUfsDescriptors();
      assert(!native_ufs_part_read(0, 10, 1, page) && combined_hardware.mmioReads == mmio &&
             combined_hardware.submissions == 6);
    }
    std::printf("PASS MODE SENSE %s: %s\n", labels[fault], row);
  }
  uint8_t raw[ModeBytes]{};
  raw[1] = 6; raw[3] = 0x10;
  const auto header = parseMode(raw, 8);
  assert(header.result.status == Status::Ok && header.dpofua == Bit::Set && header.wce == Bit::Unknown);
  raw[1] = 12; raw[8] = raw[11] = 0x08; raw[9] = raw[12] = 1;
  assert(parseMode(raw, 14).result.status == Status::Malformed);
  raw[1] = 8; raw[8] = 0x48; raw[9] = 1;
  assert(parseMode(raw, 10).result.status == Status::Malformed);

  for (const bool valid : {false, true}) {
    using namespace NuwaData;
    startMockBoot({});
    FixtureGpt gpt;
    if (!valid) gpt.be[0] ^= 1;
    combined_hardware.gpt = &gpt;
    GptBuffers buffers{};
    LiveGpt live = LiveGpt::Bad;
    constexpr uint64_t root = 8446279680ULL, reserve = 262144;
    assert(!dataProvider.open(gpt.id, 0, Block, root, reserve, DataOverlay::Media, buffers, true, &live)
           && live == LiveGpt::Unknown && !combined_hardware.submissions);
    assert(dataProvider.open(gpt.id, 0, Block, root, reserve, DataOverlay::Media, buffers, false, &live) == valid);
    assert(live == (valid ? LiveGpt::Ok : LiveGpt::Bad) && combined_hardware.submissions == 4);
    // Simulate publication from an open that reached GPT validation. Production
    // mode 2 deliberately never reaches it with the current write gate.
    __atomic_store_n(&liveGptStatus, unsigned(live), __ATOMIC_RELAXED);
    descOptIn = 1;
    probeUfsDescriptors();
    const auto mmio = combined_hardware.mmioReads;
    assert(cachedUfsModeRow(row, sizeof row) && strstr(row, valid ? "gpt=ok" : "gpt=bad") &&
           combined_hardware.submissions == 10 && combined_hardware.mmioReads == mmio &&
           !combined_hardware.writeSubmissions);
    dataProvider.close();
    std::printf("PASS live dual GPT from existing open, no extra I/O: %s\n", row);
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
  constexpr auto window = DataOverlay::Media;
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

static void testSb0ProductionClosed() {
  using namespace NuwaData;
  startMockBoot({});
  assert(BuildWriteOptIn); // Even the old build opt-in cannot bypass false.
  FixtureGpt disk;
  combined_hardware.gpt = &disk;
  for (const unsigned arg : {0U, 1U}) {
    dataWriteArg = arg;
    const char *why = nullptr;
    uint64_t first = 0;
    uint8_t page[Block]{};
    assert(!native_ufs_store_open(DataOverlay::Media.blocks, &first, &why) &&
           !strcmp(why, "window refused") && !first && !gStoreRegionBlocks);
    assert(!native_ufs_store_write(0, 1, page) && !native_ufs_store_sync());
  }
  assert(!combined_hardware.prepares && !combined_hardware.submissions);
  std::puts("PASS SB0 ordinary mode 2 with and without production write arg: zero commands");
}

#if defined(NUWA_SB0_HOST_FIXTURE) && NUWA_SB0_HOST_FIXTURE == 1
static void testSb0Experiment() {
  using namespace NuwaSb0Fixture;
  using Overlay = DataOverlay;
  using Cut = Sb0Media::Cut;
  constexpr auto first = Overlay::Media.first;
  static_assert(first == 57393401 && Overlay::Data0 == 770);
  struct FixturePort : CandidatePort {
    void quarantineLocked() { retainQuarantineLocked(); }
  } port;

  enum Case { ArgOnly, NoArg, NoOwner, NoBackup, WrongLun, WrongBlock, WrongCapacity,
              WrongWindow, WrongReserve, WrongRoot, WrongSeed, MissingSeed,
              Primary, Backup, GptDisagree, NonemptySb, DamagedMap, LastRing, Legacy,
              MetadataError, Guard, Tag, Lun, Short, Scsi, TimeoutLate, Lost, Torn,
              ErrorAlreadyWritten, Good, Count };
  constexpr const char *labels[] = {
    "arg only", "no arg", "missing owner", "missing backup", "wrong LU", "wrong block",
    "wrong capacity", "wrong window", "wrong reserve", "wrong root", "wrong seed", "missing seed",
    "primary CRC", "backup CRC", "valid copies disagree", "existing SB0", "damaged map",
    "last ring page", "legacy anchor", "metadata read error", "guard after prepare",
    "wrong tag", "wrong response LUN", "short response", "attributed command error",
    "timeout + late completion", "GOOD then power loss", "torn + timeout",
    "error but already written", "GOOD"
  };
  static_assert(sizeof labels / sizeof *labels == Count);
  for (unsigned which = 0; which < Count; ++which) {
    startMockBoot({});
    FixtureGpt disk;
    Sb0Media media;
    combined_hardware.gpt = &disk;
    combined_hardware.sb0 = &media;
    Trial trial;
    NuwaSb0Fixture::Request request;
    request.arg = 1;
    request.seed[0] = 0x5e;
    MockBinding binding{true, true, {0x5e}};
    GptBuffers g{};
    auto w = std::make_unique<Overlay::Workspace>();
    MediaPage expected{};
    uint8_t expectedPage[Block]{};
    assert(Overlay::initialSuperblock(expectedPage, request.seed, *w));
    memcpy(expected.data(), expectedPage, Block);
    Result want = Result::Geometry;
    size_t preflight = 0;
    switch (which) {
      case ArgOnly: case NoArg:
        request.arg = which == ArgOnly;
        want = Result::Disabled;
        break;
      case NoOwner: binding.windowOwned = false; want = Result::Binding; break;
      case NoBackup: binding.backupRestorable = false; want = Result::Binding; break;
      case WrongLun: request.lun = 1; break;
      case WrongBlock: combined_state.block = 512; break;
      case WrongCapacity: --combined_state.blocks; break;
      case WrongWindow: ++request.window.first; break;
      case WrongReserve: --request.reserve; break;
      case WrongRoot: ++request.rootBytes; break;
      case WrongSeed: request.seed[0] ^= 1; want = Result::Binding; break;
      case MissingSeed: request.seed[0] = binding.backupSeed[0] = 0; want = Result::Binding; break;
      case Primary: disk.p[16] ^= 1; want = Result::Gpt; preflight = 4; break;
      case Backup: disk.b[16] ^= 1; want = Result::Gpt; preflight = 4; break;
      case GptDisagree: disk.be[31 * 128 + 48] ^= 1; disk.repair();
        want = Result::Gpt; preflight = 4; break;
      case NonemptySb: media.existing = expected; media.corruptAt = first;
        want = Result::Nonempty; preflight = 5; break;
      case DamagedMap: media.corruptAt = first + Overlay::Map1 + 23; media.existing.back() = 1;
        want = Result::Nonempty; preflight = 5 + Overlay::Map1 + 23; break;
      case LastRing: media.corruptAt = first + Overlay::Data0 - 1; media.existing.back() = 1;
        want = Result::Nonempty; preflight = 4 + Overlay::Data0; break;
      case Legacy: media.corruptAt = first + Overlay::LegacyHeader1; media.existing[0] = 1;
        want = Result::Nonempty; preflight = 5 + Overlay::Data0; break;
      case MetadataError: media.readErrorAt = first + Overlay::LegacyHeader0;
        want = Result::ReadError; preflight = 5 + Overlay::LegacyHeader0; break;
      default:
        preflight = 5 + Overlay::Data0;
        want = Result::NotCompleted;
        if (which == Guard) media.guardAfterPrepare = true;
        if (which == Tag) media.writeWire.badTag = true;
        if (which == Lun) media.writeWire.lun = 1;
        if (which == Short) { media.writeWire.flags = 0x20; media.writeWire.residual = 1; }
        if (which == Scsi || which == ErrorAlreadyWritten) {
          media.writeWire.status = 2; media.writeWire.dl = 16;
        }
        if (which == TimeoutLate || which == Torn) {
          media.writeWire.timedOut = true; media.writeWire.ocs = 15;
        }
        if (which == Lost) media.cut = Cut::LostOnPowerCut;
        if (which == Torn) media.cut = Cut::Torn;
        if (which == ErrorAlreadyWritten) media.cut = Cut::ErrorAlreadyWritten;
        if (which == Lost || which == Good) want = Result::CommandCompleted;
        break;
    }

    IOLockLock(gHost.lock);
    const auto result = which == ArgOnly
      ? trial.runLocked<false>(port, retainedSlot, request, binding, nuwaDataIdentity, g, *w)
      : trial.runLocked<true>(port, retainedSlot, request, binding, nuwaDataIdentity, g, *w);
    IOLockUnlock(gHost.lock);
    assert(result == want && media.reads.size() == preflight);
    const uint64_t gptReads[] = {1, 2, disk.id.capacity - 1, disk.id.capacity - 2};
    for (size_t i = 0; i < preflight; ++i)
      assert(media.reads[i] == (i < 4 ? gptReads[i] : first +
             (i - 4 == Overlay::Data0 ? Overlay::LegacyHeader1 : i - 4)));
    const unsigned writes = which > Guard;
    assert(combined_hardware.writeSubmissions == writes &&
           combined_hardware.submissions == preflight + writes &&
           combined_hardware.prepares == preflight + unsigned(which >= Guard));
    if (writes) {
      const uint8_t cdb[] = {0x2a, 0x08, uint8_t(first >> 24), uint8_t(first >> 16),
                             uint8_t(first >> 8), uint8_t(first), 0, 0, 1, 0};
      assert(!memcmp(combined_hardware.lastCdb, cdb, sizeof cdb) &&
             !memcmp(combined_hardware.written, expected.data(), Block));
    }
    if (media.cut == Cut::LostOnPowerCut) {
      assert(media.persisted == expected); // Visible after GOOD, before the simulated cut.
      media.persisted.fill(0);
    }
    MediaPage persisted{};
    if (which == Good || which == ErrorAlreadyWritten) persisted = expected;
    if (which == Torn) memcpy(persisted.data(), expected.data(), Block / 2);
    assert(media.persisted == persisted);

    const bool terminal = which == MetadataError || want == Result::NotCompleted;
    if (terminal) {
      const bool orphan = which == TimeoutLate || which == Torn;
      assert(gHost.poisoned && combined_state.quarantined &&
             retainedSlot.state() == (orphan ? State::TIMEOUT_ORPHAN : State::FATAL_QUARANTINED));
      if (orphan) {
        assert(combined_hardware.active); // DB still owned by the old command.
        combined_hardware.active = false;
        combined_hardware.wire = {};
        combined_hardware.virt[8] = 0;
        auto *late = combined_hardware.virt + 4608;
        memset(late, 0, 512);
        late[0] = 0x21;
        late[3] = combined_hardware.virt[4099];
        combined_hardware.virt[CombinedRead::Data] ^= 0xff;
      }
    }
    uint8_t dma[CombinedRead::Bytes];
    memcpy(dma, combined_hardware.virt, sizeof dma);
    const auto mmio = combined_hardware.mmioReads;
    IOLockLock(gHost.lock);
    if (terminal) assert(!dataPort.readPageLocked(10, w->data));
    if (want != Result::Disabled) {
      assert(trial.runLocked<true>(port, retainedSlot, request, binding, nuwaDataIdentity, g, *w) ==
             Result::Used);
      if (terminal) {
        Trial another;
        assert(another.runLocked<true>(port, retainedSlot, request, binding, nuwaDataIdentity, g, *w) ==
               Result::Geometry);
      }
    }
    IOLockUnlock(gHost.lock);
    if (terminal) {
      NativeUfsBlock block;
      ::Request root;
      root.issue(block);
      assert(root.status == kIOReturnNotReady && root.bytes == 0);
      assert(!dataProvider.open(disk.id, 0, Block, RootBytes, Reserve, Overlay::Media, g));
    }
    assert(!gStoreRegionBlocks && !native_ufs_store_write(0, 1, w->block) &&
           !native_ufs_store_sync() && combined_hardware.mmioReads == mmio &&
           combined_hardware.writeSubmissions == writes &&
           media.persisted == persisted && !memcmp(dma, combined_hardware.virt, sizeof dma));
    std::printf("PASS SB0 %-26s reads=%zu write DB0=%u\n", labels[which], preflight, writes);
  }
}
#endif

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
  // testWrites ended with an orphan in the actual candidate Port.
  const auto before = combined_hardware.mmioReads;
  const auto submissions = combined_hardware.submissions;
  IOLockLock(gHost.lock);
  assert(dataPort.tryReinitLocked() == NuwaData::ReinitResult::PlatformUnproven);
  assert(dataPort.tryReinitLocked() == NuwaData::ReinitResult::AlreadyAttempted);
  IOLockUnlock(gHost.lock);
  assert(combined_hardware.mmioReads == before && combined_hardware.submissions == submissions &&
         !retainedSlot.rootAllowed());
  std::puts("PASS candidate re-init refuses without old-DMA/platform proof; MMIO=0, submissions=0");
  testDescriptors();
  testModeSense();
  testRamOverlay();
  testRamAmplification();
  testSb0ProductionClosed();
#if defined(NUWA_SB0_HOST_FIXTURE) && NUWA_SB0_HOST_FIXTURE == 1
  testSb0Experiment();
#endif
}
