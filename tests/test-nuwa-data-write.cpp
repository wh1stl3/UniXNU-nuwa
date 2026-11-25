#include "../package/nuwa-data-write/Gate.h"
#include "../package/nuwa-data-write/Provider.h"
#include "../package/nuwa-data-write/Overlay.h"
#include <cassert>
#include <cstdio>
#include <future>
#include <initializer_list>
#include <mutex>
#include <thread>

using namespace NuwaData;

static void put(uint8_t *p, uint64_t value, unsigned bytes = 8) {
  for (unsigned i = 0; i < bytes; ++i) p[i] = uint8_t(value >> (8 * i));
}

struct Disk {
  GptIdentity id{61850624, 6, 61850618, 3110976, 61850618, {1}, {2}, {3}};
  uint8_t p[Block]{}, b[Block]{}, pe[Block]{}, be[Block]{};
  Disk() {
    auto *e = pe + 31 * 128;
    memcpy(e, id.type, 16);
    memcpy(e + 16, id.partition, 16);
    put(e + 32, id.userdataFirst);
    put(e + 40, id.userdataLast);
    for (unsigned i = 0; i < 8; ++i) e[56 + i * 2] = "userdata"[i];
    memcpy(be, pe, Block);
    for (auto *h : {&p, &b}) {
      const bool backup = h == &b;
      memcpy(*h, "EFI PART", 8);
      put(*h + 8, 0x10000, 4);
      put(*h + 12, 92, 4);
      put(*h + 24, backup ? id.capacity - 1 : 1);
      put(*h + 32, backup ? 1 : id.capacity - 1);
      put(*h + 40, id.firstUsable);
      put(*h + 48, id.lastUsable);
      memcpy(*h + 56, id.disk, 16);
      put(*h + 72, backup ? id.capacity - 2 : 2);
      put(*h + 80, 32, 4);
      put(*h + 84, 128, 4);
    }
    repair();
  }
  void repair() {
    put(p + 88, crc(pe, Block), 4);
    put(b + 88, crc(be, Block), 4);
    put(p + 16, crc(p, 92, 16), 4);
    put(b + 16, crc(b, 92, 16), 4);
  }
  bool accept(unsigned lun = 0, unsigned block = Block) const {
    return gpt(lun, block, id, {1, 2, p, pe}, {id.capacity - 1, id.capacity - 2, b, be});
  }
};

struct MemoryStore {
  uint8_t bytes[8][Block]{};
  unsigned writes = 0, cut = 0;
  bool syncOK = true;
  bool read(uint64_t at, uint32_t n, void *dst) {
    assert(n == 1 && at < 8);
    memcpy(dst, bytes[at], Block);
    return true;
  }
  bool write(uint64_t at, uint32_t n, const void *src) {
    assert(n == 1 && at < 8);
    if (++writes == cut) {
      memcpy(bytes[at], src, 64); // interrupted media program, not an atomic block
      return false;
    }
    memcpy(bytes[at], src, Block);
    return true;
  }
  bool sync() { return syncOK; }
};

struct Session {
  Overlay overlay;
  uint8_t map[2 * Block], scratch[Block], seed[32]{};
  Overlay::Open open(MemoryStore &s, bool create = true) {
    return overlay.open(s, 2, seed, map, scratch, true, create);
  }
};

static void powercuts() {
  MemoryStore origin;
  Session a;
  uint8_t first[2 * Block], second[2 * Block], readback[Block];
  memset(first, 0x11, Block); memset(first + Block, 0x12, Block);
  memset(second, 0x21, Block); memset(second + Block, 0x22, Block);
  assert(a.open(origin) == Overlay::Open::Empty);
  assert(a.overlay.writeRun(origin, 0, 2, first));
  for (unsigned cut = 1; cut <= 5; ++cut) { // invalidation, pages 0/1, bitmap, final header
    MemoryStore s = origin;
    Session w;
    assert(w.open(s) == Overlay::Open::Resumed);
    s.writes = 0; s.cut = cut;
    assert(!w.overlay.writeRun(s, 0, 2, second));
    assert(!w.overlay.ready() && !w.overlay.has(0) && !w.overlay.read(s, 0, readback));
    Session reboot;
    assert(reboot.open(s) == Overlay::Open::Resumed && reboot.overlay.generation() == 1);
    for (unsigned i = 0; i < 2; ++i) {
      assert(reboot.overlay.read(s, i, readback));
      assert(!memcmp(readback, first + i * Block, Block));
    }
    std::printf("PASS power cut %u preserves both old pages; unpublished bitmap invisible\n", cut);
  }
  // Replace one page: the other page is carried to the other bank.
  assert(a.overlay.writeRun(origin, 0, 1, second));
  Session next;
  assert(next.open(origin) == Overlay::Open::Resumed && next.overlay.generation() == 2);
  assert(next.overlay.read(origin, 0, readback) && !memcmp(readback, second, Block));
  assert(next.overlay.read(origin, 1, readback) && !memcmp(readback, first + Block, Block));
  std::puts("PASS slot flip and partial update survive reboot without reset");
  MemoryStore badPage = origin;
  badPage.bytes[6][20] ^= 1;
  Session fallback;
  assert(fallback.open(badPage) == Overlay::Open::Resumed &&
         fallback.overlay.generation() == 1 && !fallback.overlay.writable());
  std::puts("PASS data checksum failure falls back read-only");
  origin.bytes[4][68] ^= 1;
  assert(fallback.open(origin) == Overlay::Open::Resumed &&
         fallback.overlay.generation() == 1 && !fallback.overlay.writable());
  origin.bytes[0][68] ^= 1;
  assert(fallback.open(origin) == Overlay::Open::Failed && !fallback.overlay.ready());
  std::puts("PASS one damaged header falls back read-only; two fail closed");
  MemoryStore foreign;
  foreign.bytes[0][0] = 1;
  assert(fallback.open(foreign) == Overlay::Open::Failed && !foreign.writes);
  foreign.bytes[0][0] = 0;
  foreign.bytes[3][0] = 1;
  assert(fallback.open(foreign) == Overlay::Open::Failed && !foreign.writes);
  std::puts("PASS foreign header and nonempty blank-header window not overwritten");
  MemoryStore noFua;
  assert(fallback.open(noFua) == Overlay::Open::Empty);
  noFua.syncOK = false;
  assert(!fallback.overlay.writeRun(noFua, 0, 1, first) && !noFua.writes);
  std::puts("PASS no writes without proven FUA barrier");
}

struct MockPort {
  Disk &disk;
  bool locked = false, fua = false, isolation = false, ownership = true;
  ColdStartIdentity expected{21, 31, 41};
  ColdStartEvidence boot{};
  unsigned writes = 0;
  Evidence result = Evidence::FullFua;
  void lock() { assert(!locked); locked = true; }
  void unlock() { assert(locked); locked = false; }
  bool readyLocked() { assert(locked); return true; }
  bool ownershipLocked() { assert(locked); return ownership; }
  uint64_t capacityLocked() { assert(locked); return disk.id.capacity; }
  unsigned blockSizeLocked() { assert(locked); return Block; }
  bool isolationArmedLocked() { assert(locked); return isolation; }
  ColdStartIdentity coldStartIdentityLocked(const GptIdentity &, Window) {
    assert(locked);
    return expected;
  }
  ColdStartEvidence coldStartEvidenceLocked(const GptIdentity &, Window) {
    assert(locked);
    return boot;
  }
  bool fuaProvenLocked() { assert(locked); return fua; }
  bool readPageLocked(uint64_t lba, void *dst) {
    assert(locked);
    const uint8_t *src = lba == 1 ? disk.p : lba == 2 ? disk.pe :
                         lba == disk.id.capacity - 1 ? disk.b : disk.be;
    memcpy(dst, src, Block);
    return true;
  }
  Evidence writePageLocked(const uint8_t (&cdb)[10], const uint8_t *) {
    assert(locked && ownership && cdb[0] == 0x2a && cdb[1] == 8 && cdb[8] == 1);
    ++writes;
    return result;
  }
};

static constexpr ColdStartEvidence qualifiedFrom(ColdStartIdentity source) {
  const ColdStartFact fact{source, true};
  return {fact, fact, fact, fact, fact, fact, fact, fact};
}
static constexpr ColdStartIdentity Current{21, 31, 41};
static constexpr ColdStartEvidence Qualified = qualifiedFrom(Current);

static void providerTest(Disk &disk, Window w) {
  Slot slot;
  MockPort port{disk};
  GptBuffers buffers{};
  const uint8_t zeroBlock[Block * 2]{};
  Provider<MockPort> disabled(port, slot);
  port.fua = port.isolation = true;
  port.boot = Qualified;
  assert(!disabled.open(disk.id, 0, Block, 8446279680ULL, 262144, w, buffers, true));
  assert(disabled.open(disk.id, 0, Block, 8446279680ULL, 262144, w, buffers));
  assert(!disabled.write(0, 1, zeroBlock) && !disabled.sync() &&
         !disabled.writeLog() && !disabled.writeExport() && !disabled.writePanic() && !port.writes);
  std::puts("PASS default provider gate and log/export/panic deny every write");
  Provider<MockPort, true> optIn(port, slot);
  port.fua = false;
  assert(!optIn.open(disk.id, 0, Block, 8446279680ULL, 262144, w, buffers, true));
  port.fua = true;
  assert(optIn.open(disk.id, 0, Block, 8446279680ULL, 262144, w, buffers, true));
  assert(!optIn.write(w.blocks - 1, 2, zeroBlock) && !port.writes);
  assert(optIn.write(0, 2, zeroBlock) && port.writes == 2 && !optIn.sync());
  port.result = Evidence::Timeout;
  assert(!optIn.write(0, 2, zeroBlock) && port.writes == 3);
  assert(!optIn.write(0, 1, zeroBlock) && !optIn.sync() &&
         !slot.rootAllowed() && port.writes == 3);
  optIn.close();
  assert(!optIn.open(disk.id, 0, Block, 8446279680ULL, 262144, w, buffers, true));
  assert(!optIn.open(disk.id, 0, Block, 8446279680ULL, 262144, w, buffers));
  std::puts("PASS opt-in mock uses one FUA per page, stops on orphan without replay");
}

static void coldStartTest(Disk &disk, Window w) {
  constexpr std::pair<const char *, ColdStartFact ColdStartEvidence::*> facts[] = {
    {"firmware reinit", &ColdStartEvidence::firmwareReinitialized},
    {"old DMA exclusion", &ColdStartEvidence::oldDmaExcluded},
    {"LUN", &ColdStartEvidence::lunMatches},
    {"primary GPT", &ColdStartEvidence::primaryGptMatches},
    {"backup GPT", &ColdStartEvidence::backupGptMatches},
    {"window", &ColdStartEvidence::windowMatches},
    {"known root block", &ColdStartEvidence::knownRootMatches},
    {"overlay generation", &ColdStartEvidence::overlayGenerationMatches},
  };
  GptBuffers g{};
  Slot old;
  assert(old.submitRead(true, true) && !old.complete(Evidence::Timeout));
  assert(!ColdStartEvidence{}.qualified(Current));
  MockPort port{disk};
  port.fua = port.isolation = true;
  Slot initial;
  Provider<MockPort, true> probe(port, initial);
  for (auto [name, field] : facts) {
    port.boot = Qualified;
    (port.boot.*field).verified = false;
    Slot denied(Current, port.boot);
    assert(!denied.rootAllowed());
    assert(!probe.open(disk.id, 0, Block, 8446279680ULL, 262144, w, g, true));
    std::printf("PASS cold start missing %s: isolated; write open denied\n", name);
  }
  auto reject = [&](const char *name, ColdStartEvidence evidence) {
    port.boot = evidence;
    Slot denied(Current, evidence);
    assert(!denied.rootAllowed());
    assert(!probe.open(disk.id, 0, Block, 8446279680ULL, 262144, w, g, true));
    std::printf("PASS cold start rejects %s\n", name);
  };
  reject("all-true old boot session", qualifiedFrom({20, 31, 41}));
  auto mixed = Qualified;
  mixed.oldDmaExcluded.source.domain_id++;
  reject("cross-domain proof", mixed);
  mixed = Qualified;
  mixed.backupGptMatches.source.media_id++;
  reject("mixed-media proof", mixed);
  reject("all-true empty provenance", qualifiedFrom({}));
  port.expected = {};
  assert(!Qualified.qualified(port.expected));
  port.expected = Current;
  port.boot = Qualified;
  port.isolation = false;
  assert(!probe.open(disk.id, 0, Block, 8446279680ULL, 262144, w, g, true));
  Slot successor(Current, Qualified);
  assert(successor.rootAllowed() && !old.rootAllowed() && !old.complete(Evidence::ReadOk));
  std::puts("PASS all cold-start proofs admit only a fresh slot; old slot remains isolated");
}

struct WaitingPort : MockPort {
  explicit WaitingPort(Disk &disk) : MockPort{disk} {}
  std::mutex mutex;
  std::promise<void> *arrival = nullptr;
  void lock() {
    if (arrival) arrival->set_value();
    mutex.lock();
    MockPort::lock();
  }
  void unlock() { MockPort::unlock(); mutex.unlock(); }
};

static void waitingWriterTest(Disk &disk, Window w) {
  WaitingPort port(disk);
  Slot slot;
  Provider<WaitingPort, true> provider(port, slot);
  GptBuffers buffers{};
  port.fua = port.isolation = true;
  port.boot = Qualified;
  assert(provider.open(disk.id, 0, Block, 8446279680ULL, 262144, w, buffers, true));
  port.lock(); // Root owns the shared submission lock and slot.
  assert(slot.submitRead(true, true));
  std::promise<void> arrival;
  auto waiting = arrival.get_future();
  port.arrival = &arrival;
  uint8_t src[Block]{};
  bool written = true;
  std::thread writer([&] { written = provider.write(0, 1, src); });
  waiting.get();
  assert(!slot.complete(Evidence::Timeout));
  port.unlock();
  writer.join();
  assert(!written && port.writes == 0 && !slot.rootAllowed());
  std::puts("PASS Data waits for root lock, rechecks orphan state and submits nothing");
}

int main() {
  Disk disk;
  assert(disk.accept());
  std::puts("PASS GPT valid nuwa geometry with synthetic GUIDs");
  assert(!disk.accept(1) && !disk.accept(0, 512));
  std::puts("PASS GPT wrong LUN/block size rejected");
  Disk wrong = disk;
  wrong.pe[31 * 128 + 16] ^= 4;
  wrong.be[31 * 128 + 16] ^= 4;
  wrong.repair();
  assert(!wrong.accept());
  std::puts("PASS GPT CRC-correct wrong userdata unique GUID rejected");
  wrong = disk;
  wrong.be[3 * 128 + 56] ^= 1;
  wrong.repair();
  assert(!wrong.accept());
  wrong = disk;
  put(wrong.b + 32, 2);
  wrong.repair();
  assert(!wrong.accept());
  std::puts("PASS GPT CRC-correct disagreeing entry arrays and reciprocal LBA rejected");
  wrong = disk;
  wrong.b[16] ^= 1;
  assert(!wrong.accept());
  wrong = disk;
  wrong.pe[20] ^= 1;
  assert(!wrong.accept());
  std::puts("PASS GPT bad header CRC and bad entry CRC rejected");
  const Window w{59491258, 2097217};
  assert(placement(disk.id, 8446279680ULL, 262144, w));
  assert(!placement(disk.id, UINT64_MAX, 262144, w));
  assert(!placement(disk.id, 8446279680ULL, 262144, {w.first, w.blocks + 1}));
  assert(w.contains(0, Block, w.first + w.blocks - 1, 1));
  assert(!w.contains(0, Block, w.first + w.blocks - 1, 2));
  assert(!w.contains(0, Block, w.first, UINT64_MAX));
  assert(!Window({UINT32_MAX, 2}).contains(0, Block, UINT32_MAX, 1));
  assert(!Window({UINT64_MAX, 1}).contains(0, Block, UINT64_MAX, 1));
  std::puts("PASS placement guard/tail, one-block overrun and integer wrap rejected");
  uint8_t cdb[10];
  write10(cdb, 0x12345678);
  const uint8_t expected[] = {0x2a, 8, 0x12, 0x34, 0x56, 0x78, 0, 0, 1, 0};
  assert(!memcmp(cdb, expected, sizeof(cdb)));
  std::puts("PASS CDB encodes one WRITE(10) FUA page");
  Slot good;
  assert(!good.submit(false, true) && good.submit(true, true));
  assert(!good.rootAllowed() && !good.dataAllowed(true));
  assert(good.complete(Evidence::FullFua) && good.dataAllowed(true));
  std::puts("PASS Data gate rejects SUBMITTED and accepts attributed FUA completion");
  Slot cmdErr;
  assert(cmdErr.submit(true, true) && !cmdErr.complete(Evidence::AttributedCommandError));
  assert(cmdErr.state() == State::COMPLETED_CMDERR && cmdErr.rootAllowed() &&
         !cmdErr.dataAllowed(true) && !cmdErr.submit(true, true));
  std::puts("PASS attributed command error is sticky for Data");
  Slot orphan;
  assert(orphan.submit(true, true) && !orphan.complete(Evidence::Timeout));
  assert(orphan.state() == State::TIMEOUT_ORPHAN && !orphan.complete(Evidence::FullFua) &&
         !orphan.dataAllowed(true) && !orphan.rootAllowed() &&
         !orphan.submit(true, true));
  std::puts("PASS orphan rejects late completion, root and Data");
  Slot fatal;
  assert(fatal.submit(true, true) && !fatal.complete(Evidence::Unowned));
  assert(fatal.state() == State::FATAL_QUARANTINED && !fatal.rootAllowed() && !fatal.dataAllowed(true));
  Slot unowned;
  assert(!unowned.submit(true, false) && unowned.state() == State::FATAL_QUARANTINED);
  std::puts("PASS unowned before/after submission quarantines slot");
  providerTest(disk, w);
  coldStartTest(disk, w);
  waitingWriterTest(disk, w);
  powercuts();
}
