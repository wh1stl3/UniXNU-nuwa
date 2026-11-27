// SPDX-License-Identifier: BSD-2-Clause-Patent
#if defined(NUWA_DATA_CANDIDATE) || defined(NUWA_DISPOSABLE_DATA)
#error This host candidate must select the RamBlock v1 direct entry.
#endif
#include "DirectDisk.h"
#include "NuwaDataFixtureGpt.h"
#include "../package/nuwa-data-write/DualBankLogOverlay.h"
#include "../package/nuwa-data-write/DisposableData.h"
#include "../package/nuwa-data-write/Descriptor.h"
#include "../package/nuwa-data-write/Provider.h"
#include "../package/nuwa-ramblock/PersistOpenReason.h"
#include <array>
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <fcntl.h>
#include <future>
#include <string_view>
#include <sys/stat.h>
#include <unistd.h>
#include <vector>
#include "TransferPoll.h"
#include "PreservedNop.h"
#include "CombinedRead.h"
#include "RootReadSession.h"

using namespace NuwaData;
using V3 = DualBankLogOverlay<>;
using Page = std::array<uint8_t, Block>;
constexpr uint64_t Pages = 2097152, WFirst = 59491258, WEnd = 61588475;
constexpr uint64_t ImageFirst = V3::Media.first - 1;
constexpr Window V1{WFirst, WEnd - WFirst};
constexpr uint64_t FaultPage = 32769, WorkingFirst = 32760;
constexpr unsigned WorkingPages = 257, Passes = 54;
static_assert(WorkingPages * Passes > 13816);
static constexpr uint8_t Seed[32] = {0x42};

static Page filled(uint8_t value) {
  Page p;
  p.fill(value);
  return p;
}

static uint64_t dataLba(uint64_t page) { return WFirst + persist::pageBlock(Pages, page); }
static uint64_t bitmapLba(uint64_t page) { return WFirst + 1 + page / (8 * Block); }

struct Image {
  int fd;
  explicit Image(const char *path, bool create)
      : fd(open(path, O_RDWR | O_NOFOLLOW | (create ? O_CREAT | O_EXCL : 0), 0600)) {
    struct stat st{};
    assert(fd >= 0 && fstat(fd, &st) == 0 && S_ISREG(st.st_mode));
    if (create) assert(ftruncate(fd, offset(WEnd + 1)) == 0);
  }
  ~Image() { assert(close(fd) == 0); }
  static off_t offset(uint64_t lba) {
    assert(lba >= ImageFirst && lba <= WEnd + 1);
    return (lba - ImageFirst) * Block;
  }
  bool read(uint64_t lba, void *dst) { return pread(fd, dst, Block, offset(lba)) == Block; }
  bool fua(uint64_t lba, const void *src) {
    return pwrite(fd, src, Block, offset(lba)) == Block && fdatasync(fd) == 0;
  }
  Page page(uint64_t lba) {
    Page p;
    assert(read(lba, p.data()));
    return p;
  }
};

struct IOLock { bool held = false; unsigned acquisitions = 0; };
static unsigned heldLocks;
static void IOLockLock(IOLock *lock) {
  assert(!lock->held); lock->held = true; ++lock->acquisitions; ++heldLocks;
}
static void IOLockUnlock(IOLock *lock) { assert(lock->held && heldLocks); lock->held = false; --heldLocks; }
static void *IOMallocZero(size_t size) { return calloc(1, size); }
static void IOFree(void *p, size_t) { free(p); }
static void IOLog(const char *, ...) {}
static bool resetRequested;
static bool PE_parse_boot_argn(const char *arg, void *dst, size_t size) {
  assert(size == sizeof(uint32_t));
  const std::string_view name(arg);
  auto &value = *static_cast<uint32_t *>(dst);
  if (name == "sheng-data-persist") { value = 2; return true; }
  if (name == "nuwa-data-write") { value = 1; return true; }
  if (name == "sheng-data-reset" && resetRequested) { value = 1; return true; }
  return false;
}

using MediaPage = Page;
#include "FixtureHardware.inc"
static CombinedRead::State combined_state;
static IOLock hostGate;
static struct { bool ready = true, poisoned = false; IOLock *lock = &hostGate; } gHost;
#include "../package/nuwa-data-write/RetainedRead.inc"
#include "../package/nuwa-data-write/RetainedWrite.inc"

struct HostFilePort : RetainedWritePort {
  enum class Fault { None, Attributed, Short, Sync, Timeout };
  struct Write { uint64_t lba; const char *result; };
  Image *image = nullptr;
  FixtureGpt gpt;
  uint64_t failLba = UINT64_MAX;
  Fault fault = Fault::None;
  bool fuaProven = true;
  bool identityProven = true, producerStopped = true, dmaDone = true;
  Window evidenceWindow = V1;
  bool failAnchor = false;
  unsigned anchorReads = 0, gptSession = 0;
  std::vector<Write> writes;
  void lock() { IOLockLock(gHost.lock); }
  void unlock() { IOLockUnlock(gHost.lock); }
  bool readyLocked() { assert(hostGate.held); return retainedReadyLocked(); }
  bool ownershipLocked() { return retainedOwnershipLocked(); }
  uint64_t capacityLocked() { return gpt.id.capacity; }
  unsigned blockSizeLocked() { return Block; }
  bool isolationArmedLocked() { return readyLocked(); }
  // Fixture facts apply to the separately opened regular file only.
  bool fuaProvenLocked() { return fuaProven && image != nullptr; }
  ColdStartIdentity coldStartIdentityLocked(const GptIdentity &, Window) {
    return identityProven ? ColdStartIdentity{1, 2, 3} : ColdStartIdentity{};
  }
  ColdStartEvidence coldStartEvidenceLocked(const GptIdentity &, Window w) {
    const ColdStartFact f{{1, 2, 3}, w.first == evidenceWindow.first && w.blocks == evidenceWindow.blocks};
    const ColdStartFact dma{{1, 2, 3}, f.verified && producerStopped && dmaDone};
    return {f, dma, f, f, f, f, f, f};
  }
  bool readPageLocked(uint64_t lba, void *dst) {
    assert(hostGate.held);
    if (const auto *p = gpt.at(lba)) {
      if (lba == 1) gptSession = hostGate.acquisitions;
      assert(gptSession == hostGate.acquisitions);
      memcpy(dst, p, Block);
      return true;
    }
    if (lba == V3::Media.first || lba == V3::Media.first + 1) {
      assert(gptSession == hostGate.acquisitions && lba == V3::Media.first + anchorReads);
      ++anchorReads;
      return !failAnchor && image->read(lba, dst);
    }
    assert(V1.contains(0, Block, lba, 1));
    return image->read(lba, dst);
  }
  Response submitFileWrite(uint64_t lba, const uint8_t *src) {
    assert(hostGate.held && V1.contains(0, Block, lba, 1));
    Response wire{};
    const auto injected = lba == failLba ? fault : Fault::None;
    const char *label = "FUA_OK";
    if (injected == Fault::Attributed) {
      wire.status = 2;
      wire.dl = 16;
      label = "FUA_ERROR";
    } else {
      const size_t n = injected == Fault::Short ? Block - 1 : Block;
      const auto written = pwrite(image->fd, src, n, Image::offset(lba));
      if (written < 0) {
        wire.status = 2;
        wire.dl = 16;
        label = "FUA_ERROR";
      } else if (written != Block) {
        wire.flags = 0x20;
        wire.residual = Block - written;
        label = "SHORT";
      } else if ((injected == Fault::Sync ? -1 : fdatasync(image->fd)) != 0) {
        // File transport has no trustworthy completion after the sync error.
        wire.badTag = true;
        label = "SYNC_UNKNOWN";
      } else if (injected == Fault::Timeout) {
        wire.ocs = 15;
        wire.timedOut = true;
        label = "TIMEOUT_UNKNOWN";
      }
    }
    writes.push_back({lba, label});
    return wire;
  }
};

static HostFilePort dataPort;
static_assert(BuildWriteOptIn);
static Provider<HostFilePort> dataProvider(dataPort, retainedSlot);
static unsigned liveGptStatus;
using IOReturn = int;
enum { kIOReturnSuccess, kIOReturnBadArgument, kIOReturnNotReady, kIOReturnNoMemory, kIOReturnIOError };
static constexpr unsigned kDataMax = 32 * Block;
static IOReturn hostRead4k(unsigned, uint64_t, uint32_t, void *) {
  assert(false && "v1 mode 2 must use the qualified provider");
  return kIOReturnIOError;
}
#include "FixtureUfs.inc"

static volatile uint32_t native_data_persist_state, native_data_persist_header, native_data_persist_gpt,
                         native_data_persist_gpt_after;
static volatile uint64_t native_data_persist_pages, native_data_persist_loaded, native_data_persist_first_lba,
                         native_data_persist_present, native_ram_block_resident_bytes, native_data_persist_writes,
                         native_data_persist_syncs, native_data_persist_errors, native_ram_block_failures,
                         native_ram_block_reads, native_ram_block_writes;
static const char *volatile nuwa_data_persist_open_why;
using UInt64 = uint64_t;
using IOOptionBits = uint32_t;
struct IOStorageAttributes {};
enum { kIODirectionIn, kIODirectionOut };
struct IOMemoryDescriptor {
  Page &bytes;
  bool write;
  uint64_t getLength() { return bytes.size(); }
  int getDirection() { return write ? kIODirectionOut : kIODirectionIn; }
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
  IOLock lock, *gate = &lock;
  uint8_t *memory = nullptr;
  const uint64_t capacity = Pages * Block / 512;
  bool online = true, isBig = true, storeAttached = false, direct = false, directFailed = false;
  RamSparseDisk sparse{};
  SeedDisk big{};
  uint8_t seedHash[32];
  persist::Overlay overlay;
  uint8_t *overlayBits = nullptr, *stage = nullptr;
  static constexpr uint32_t kStagePages = 32;
  NativeRamBlock() { big.bytes = Pages * Block; memcpy(seedHash, Seed, sizeof Seed); }
  ~NativeRamBlock() { free(overlayBits); free(stage); }
  IOReturn doAsyncReadWrite(IOMemoryDescriptor *, UInt64, UInt64, IOStorageAttributes *, IOStorageCompletion *);
#include "FixtureRamClass.inc"
};
#include "FixtureRamIO.inc"

struct Result { IOReturn dispatch = -1, status = -1; uint64_t bytes = 0; };
static Result transfer(NativeRamBlock &ram, bool write, uint64_t page, Page &p) {
  Result result;
  IOMemoryDescriptor buffer{p, write};
  IOStorageCompletion completion{&result, nullptr, [](void *target, void *, IOReturn status, uint64_t bytes) {
    auto &done = *static_cast<Result *>(target);
    assert(done.status == -1);
    done.status = status;
    done.bytes = bytes;
  }};
  result.dispatch = ram.doAsyncReadWrite(&buffer, page * (Block / 512), Block / 512, nullptr, &completion);
  return result;
}
static void transferOk(NativeRamBlock &ram, bool write, uint64_t page, Page &p) {
  const auto r = transfer(ram, write, page, p);
  assert(r.dispatch == kIOReturnSuccess && r.status == kIOReturnSuccess && r.bytes == Block);
}
static void checkWrites(const char *tag, std::initializer_list<HostFilePort::Write> expected) {
  assert(dataPort.writes.size() == expected.size());
  size_t i = 0;
  for (const auto &e : expected) {
    const auto &actual = dataPort.writes[i++];
    assert(actual.lba == e.lba && !strcmp(actual.result, e.result));
    printf("TRACE %s %zu lba=%llu %s\n", tag, i,
           static_cast<unsigned long long>(actual.lba), actual.result);
  }
  dataPort.writes.clear();
}
static bool present(Image &image, uint64_t page) {
  return image.page(bitmapLba(page))[(page / 8) % Block] & (1U << (page % 8));
}
static void setup(Image &image) {
  dataPort.image = &image;
  combined_hardware.fileWrite = [](uint64_t lba, const uint8_t *src) {
    return dataPort.submitFileWrite(lba, src);
  };
  combined_state.block = Block;
  combined_state.blocks = dataPort.gpt.id.capacity;
  combined_state.capacity = combined_state.blocks * Block;
  combined_state.setup.dma = Hardware::Dma;
  assert(PreservedNop::domain(combined_hardware, combined_state.setup));
  auto &gpt = dataPort.gpt;
  auto patch = [](uint8_t *p, const uint8_t *bytes) { memcpy(p, bytes, 16); };
  assert(gpt.id.capacity == nuwaDataIdentity.capacity && gpt.id.firstUsable == nuwaDataIdentity.firstUsable &&
         gpt.id.lastUsable == nuwaDataIdentity.lastUsable && gpt.id.userdataFirst == nuwaDataIdentity.userdataFirst &&
         gpt.id.userdataLast == nuwaDataIdentity.userdataLast);
  gpt.id = nuwaDataIdentity;
  patch(gpt.p + 56, gpt.id.disk); patch(gpt.b + 56, gpt.id.disk);
  patch(gpt.pe + 31 * 128, gpt.id.type); patch(gpt.pe + 31 * 128 + 16, gpt.id.partition);
  memcpy(gpt.be, gpt.pe, Block);
  gpt.repair();
  gStoreGeometry = {true, gpt.id.userdataFirst, gpt.id.userdataLast, 8446279680ULL, 0, 0, 0, 0};
}

static void makeV3(Image &image, std::string_view kind) {
  struct Ops {
    Image &image;
    bool read(uint64_t b, uint32_t n, void *p) {
      assert(n == 1 && b < V3::Media.blocks);
      return image.read(V3::Media.first + b, p);
    }
    bool write(uint64_t b, uint32_t n, const void *p) {
      assert(n == 1 && b < V3::Media.blocks);
      return image.fua(V3::Media.first + b, p);
    }
    bool sync() { return true; } // All fixture writes already synchronized.
  } ops{image};
  if (kind == "make-v3-disposable") {
    using Overlay = Disposable::Overlay;
    static Overlay::Workspace work;
    static Overlay::SeenScratch seen;
    uint8_t sb[Block];
    assert(Overlay::initialSuperblock(sb, Disposable::Seed, work) &&
           ops.write(0, 1, sb));
    Overlay v3;
    assert(v3.open(ops, Disposable::Seed, work, seen, false, false) == Overlay::Open::Resumed);
    puts("PASS disposable v3 with foreign seed reopens");
    return;
  }
  if (kind == "make-v3-torn") {
    // The existing classifier recognizes a tail-only slot 1 write.
    Page sb{};
    persist::put64(sb.data() + Block - 16, 1);
    persist::put32(sb.data() + Block - 8, 1);
    assert(ops.write(1, 1, sb.data()));
    puts("PASS torn slot 1 fixture with slot 0 empty");
    return;
  }
  const bool collision = kind == "make-v3-collision";
  static V3::Workspace work;
  static V3::SeenScratch seen;
  V3 v3;
  constexpr uint64_t overlapping = WFirst - V3::Media.first - V3::Data0;
  static_assert(overlapping < V3::Pages);
  auto p = filled(0x33), read = filled(0);
  if (collision) persist::encodeHeader(p.data(), Pages, Seed, 1);
  assert(v3.open(ops, Seed, work, seen, true, true) == V3::Open::Empty);
  assert(v3.writeRun(ops, overlapping, 1, p.data()));
  assert(v3.open(ops, Seed, work, seen, false, false) == V3::Open::Resumed);
  assert(v3.read(ops, overlapping, read.data()) && read == p && image.page(WFirst) == p);
  puts(collision ? "PASS old v3 reopens and overlapped v1 header is valid for this seed" :
                   "PASS old v3 reopens with ordinary data at v1 header LBA");
}

static Page payload(unsigned i, unsigned pass) {
  auto p = filled(uint8_t(i ^ pass));
  persist::put32(p.data(), i);
  persist::put32(p.data() + 4, pass);
  return p;
}

int main(int argc, char **argv) {
  assert(argc == 3);
  const std::string_view op(argv[1]);
  const bool makeLegacy = op.substr(0, 7) == "make-v3";
  Image image(argv[2], op == "init" || makeLegacy);
  if (makeLegacy) { makeV3(image, op); return 0; }

  setup(image);
  const bool failAnchor = op == "reject-anchor-io";
  dataPort.failAnchor = failAnchor;
  dataPort.fuaProven = op != "reject-no-fua";
  resetRequested = op == "init";
  if (resetRequested) {
    assert(image.fua(WFirst - 1, filled(0xcc).data()));
    assert(image.fua(WEnd, filled(0xdd).data()));
  }
  NativeRamBlock ram;
  if (op == "reject-reserved-size") {
    constexpr uint64_t aliasPages = 4194944;
    assert(persist::windowBlocks(aliasPages) == V3::Media.blocks);
    ram.big.bytes = aliasPages * Block;
    ram.attachStore();
    auto p = filled(0xff);
    assert(!ram.direct && native_data_persist_state == 4 && !gStoreRegionBlocks &&
           !dataPort.gptSession && !native_ufs_store_write(0, 1, p.data()) && dataPort.writes.empty());
    puts("PASS v1 cannot select the reserved v3 window size");
    return 0;
  }
  ram.attachStore();
  if (op == "reject-no-fua") {
    assert(native_data_persist_state == 4 && !gStoreRegionBlocks && !dataPort.anchorReads &&
           !native_ufs_store_sync() && dataPort.writes.empty());
    puts("PASS unproven FUA: Provider refuses open and sync, no writes");
    return 0;
  }
  if (op.substr(0, 9) == "reject-v3" || failAnchor) {
    auto p = filled(0xff);
    const auto denied = transfer(ram, true, 0, p);
    assert(!ram.direct && !ram.overlay.active && native_data_persist_state == 4 &&
           !gStoreRegionBlocks && liveGptStatus == unsigned(LiveGpt::Ok) &&
           dataPort.anchorReads == (op == "reject-v3-torn" ? 2 : 1) &&
           denied.dispatch == kIOReturnNotReady && denied.bytes == 0);
    assert(!native_ufs_store_write(persist::pageBlock(Pages, 0), 1, p.data()) &&
           !native_ufs_store_sync() && dataPort.writes.empty() && !combined_hardware.writeSubmissions);
    puts(failAnchor ? "PASS anchor read error: attach and raw store write/sync refused, zero writes" :
                      "PASS v3 marker: attach and raw store write/sync refused, zero writes");
    return 0;
  }

  assert(native_data_persist_first_lba == WFirst && gStoreRegionBlocks == V1.blocks &&
         gStoreRegionBlocks == persist::windowBlocks(Pages) && liveGptStatus == unsigned(LiveGpt::Ok));
  assert(dataPort.anchorReads == 2 && ram.direct && ram.overlay.active &&
         native_data_persist_state == (resetRequested ? 3 : 2));
  assert(ram.doSynchronize(0, 8, 0) == kIOReturnSuccess);
  if (op == "init") {
    assert(dataPort.writes.size() == 65 && dataPort.writes.back().lba == WFirst);
    for (unsigned b = 0; b < 64; ++b)
      assert(!strcmp(dataPort.writes[b].result, "FUA_OK") && dataPort.writes[b].lba == WFirst + 1 + b);
    assert(!strcmp(dataPort.writes.back().result, "FUA_OK") && native_ufs_store_sync());
    dataPort.writes.clear();
    assert(!present(image, 0));
    auto a = filled(0x11), b = filled(0x22);
    transferOk(ram, true, 0, a);
    checkWrites("first A", {{dataLba(0), "FUA_OK"}, {bitmapLba(0), "FUA_OK"}});
    assert(present(image, 0) && image.page(dataLba(0)) == a);
    const auto bitmap = image.page(bitmapLba(0));
    transferOk(ram, true, 0, b);
    checkWrites("overwrite B", {{dataLba(0), "FUA_OK"}});
    assert(image.page(bitmapLba(0)) == bitmap);
    auto end = filled(0xee);
    transferOk(ram, true, Pages - 1, end);
    checkWrites("last page", {{WEnd - 1, "FUA_OK"}, {bitmapLba(Pages - 1), "FUA_OK"}});
    for (const auto rel : {V1.blocks, UINT64_MAX})
      assert(!native_ufs_store_write(rel, 1, end.data()));
    assert(!native_ufs_store_write(V1.blocks - 1, 2, end.data()));
    assert(dataPort.writes.empty());
  } else if (op == "read-b") {
    Page p;
    transferOk(ram, false, 0, p);
    assert(p == filled(0x22));
    transferOk(ram, false, Pages - 1, p);
    assert(p == filled(0xee));
    puts("PASS new process and reopened file read B and last v1 page");
  } else if (op == "reject-live-fua") {
    dataPort.fuaProven = false;
    assert(ram.doSynchronize(0, 8, 0) == kIOReturnIOError && !ram.directFailed);
    auto p = filled(0xff);
    const auto r = transfer(ram, true, 0, p);
    assert(r.status == kIOReturnIOError && r.bytes == 0 && !native_ufs_store_sync() &&
           dataPort.writes.empty() && !combined_hardware.writeSubmissions);
    puts("PASS FUA proof lost after open: doSynchronize IOError before any write, zero submissions");
  } else if (op.substr(0, 6) == "fault-") {
    const bool bitmapFault = op == "fault-bitmap";
    const bool shortWrite = op == "fault-short", sync = op == "fault-sync", timeout = op == "fault-timeout";
    const uint64_t page = FaultPage + (shortWrite ? 1 : sync ? 2 : timeout ? 3 : 0);
    const auto data = dataLba(page);
    assert(!present(image, page) && image.page(data) == filled(0));
    dataPort.failLba = bitmapFault ? bitmapLba(page) : data;
    using Fault = HostFilePort::Fault;
    dataPort.fault = shortWrite ? Fault::Short : sync ? Fault::Sync : timeout ? Fault::Timeout : Fault::Attributed;
    auto p = filled(0xa5);
    const auto r = transfer(ram, true, page, p);
    assert(r.dispatch == kIOReturnSuccess && r.status == kIOReturnIOError && r.bytes == 0 && ram.directFailed);
    assert(retainedSlot.state() == (timeout ? State::TIMEOUT_ORPHAN : State::FATAL_QUARANTINED) &&
           !native_ufs_store_sync() && ram.doSynchronize(0, 8, 0) == kIOReturnIOError);
    if (bitmapFault) checkWrites("bitmap failure", {{data, "FUA_OK"}, {dataPort.failLba, "FUA_ERROR"}});
    else checkWrites(argv[1], {{data, shortWrite ? "SHORT" : sync ? "SYNC_UNKNOWN" :
                                      timeout ? "TIMEOUT_UNKNOWN" : "FUA_ERROR"}});
    assert(!present(image, page));
    auto raw = filled(bitmapFault || shortWrite || sync || timeout ? 0xa5 : 0);
    if (shortWrite) raw.back() = 0;
    assert(image.page(data) == raw);
    const auto submissions = combined_hardware.writeSubmissions;
    const auto again = transfer(ram, true, 0, p);
    assert(again.status == kIOReturnIOError && again.bytes == 0 && dataPort.writes.empty() &&
           combined_hardware.writeSubmissions == submissions);
    printf("PASS completion IOError/0, %s; present clear, doSynchronize IOError, retry refused\n",
           timeout ? "TIMEOUT_ORPHAN" : "FATAL_QUARANTINED");
  } else if (op == "read-fault") {
    Page p;
    for (uint64_t page = FaultPage; page <= FaultPage + 3; ++page) {
      transferOk(ram, false, page, p);
      assert(p == filled(0) && !ram.overlay.has(page));
    }
    puts("PASS reopened fault page falls back to seed, not uncommitted image slot");
  } else if (op == "stress") {
    for (unsigned pass = 0; pass <= Passes; ++pass) {
      for (unsigned i = 0; i < WorkingPages; ++i) {
        auto p = payload(i, pass);
        transferOk(ram, true, WorkingFirst + i, p);
        const auto &trace = dataPort.writes;
        assert(trace.size() == (pass ? 1 : 2) && trace[0].lba == dataLba(WorkingFirst + i) &&
               !strcmp(trace[0].result, "FUA_OK"));
        if (!pass) assert(trace[1].lba == bitmapLba(WorkingFirst + i) && !strcmp(trace[1].result, "FUA_OK"));
        dataPort.writes.clear();
      }
    }
    printf("PASS %u overwrites across %u pages: one FUA data-slot write each, 0 metadata/log writes\n",
           WorkingPages * Passes, WorkingPages);
  } else {
    assert(op == "read-stress");
    for (unsigned i = 0; i < WorkingPages; ++i) {
      Page p;
      transferOk(ram, false, WorkingFirst + i, p);
      assert(p == payload(i, Passes));
    }
    assert(dataPort.writes.empty());
    printf("PASS new process verified %u final pages byte-for-byte\n", WorkingPages);
  }
  uint64_t generation = 0;
  assert(persist::checkHeader(image.page(WFirst).data(), Pages, Seed, &generation) == 0 && generation == 1);
  assert(image.page(WFirst - 1) == filled(0xcc) && image.page(WEnd) == filled(0xdd));
  printf("PASS v1 [%llu,%llu): header and both outside sentinels intact\n",
         static_cast<unsigned long long>(WFirst), static_cast<unsigned long long>(WEnd));
  return 0;
}
