// Compile against the candidate's staged CombinedRead.h, not the baseline copy.
#include "../package/nuwa-data-write/Provider.h"
#include <cassert>
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

static struct Host {
  bool ready, poisoned;
  bool *lock;
} gHost;
static bool locked;
static std::mutex mutex;
static void IOLockLock(bool *l) { mutex.lock(); assert(!*l); *l = true; }
static void IOLockUnlock(bool *l) { assert(*l); *l = false; mutex.unlock(); }

static struct Hardware {
  static constexpr uint32_t Dma = 0x10000;
  alignas(4096) uint8_t virt[CombinedRead::Bytes]{};
  Response wire{};
  unsigned prepares = 0, submissions = 0, seen = 0, ocsReads = 0, mmioReads = 0;
  bool active = false;
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
    assert(locked && off == 0x58 && val == 1 && !active);
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
    memset(virt + CombinedRead::Data, 0xa5, NuwaData::Block);
  }
  bool prepare(uint64_t pa, CombinedRead::Command c, unsigned tag, unsigned block,
               uint64_t lba, unsigned blocks) {
    assert(locked && pa == Dma && c == CombinedRead::Command::Read);
    ++prepares;
    return CombinedRead::encode(virt, pa, c, tag, block, lba, blocks);
  }
  uint32_t doorbell() {
    if (!active) return 0;
    if (seen++ == 0) return 1 | wire.foreignDb; // Foreign bit can disappear by final read.
    active = false;
    return 0;
  }
  uint32_t interrupt() const { return active && wire.fatal ? kUfsFatalStatus : 0; }
  uint32_t completedOcs() { ++ocsReads; return wire.ocs; }
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
static struct { uint64_t first, last, imageBytes; } gStoreGeometry;
static constexpr NuwaData::GptIdentity nuwaDataIdentity{
  61850624, 6, 61850618, 3110976, 61850618, {1}, {2}, {3}
};
static bool PE_parse_boot_argn(const char *, void *, size_t) { return false; }
static void *IOMallocZero(size_t) { assert(false); return nullptr; }
static void IOFree(void *, size_t) { assert(false); }
#include "../package/nuwa-data-write/KernelPort.inc"

static void startMockBoot(Response wire) {
  combined_hardware = {};
  combined_hardware.wire = wire;
  combined_state = {};
  combined_state.block = NuwaData::Block;
  combined_state.blocks = nuwaDataIdentity.capacity;
  combined_state.capacity = combined_state.blocks * NuwaData::Block;
  combined_state.setup.dma = Hardware::Dma;
  assert(PreservedNop::domain(combined_hardware, combined_state.setup));
  gHost = {true, false, &locked};
  // Fixture-only process replacement across independent test scenarios.
  new (&retainedSlot) NuwaData::Slot;
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

static void testTerminal(bool timeout) {
  using CombinedRead::End;
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
  std::promise<void> waiting;
  auto entered = waiting.get_future();
  IOLockLock(gHost.lock);
  auto result = std::async(std::launch::async, [&] {
    waiting.set_value();
    IOLockLock(gHost.lock);
    auto end = retainedReadLocked(11, 1);
    IOLockUnlock(gHost.lock);
    return end;
  });
  assert(entered.wait_for(2s) == std::future_status::ready);
  assert(result.wait_for(0s) == std::future_status::timeout);
  assert(retainedReadLocked(10, 1) == End::Transport);
  assert(retainedSlot.state() == (timeout ? State::TIMEOUT_ORPHAN : State::FATAL_QUARANTINED));
  // Hardware changes the old DMA after the fault. Check the software leaves
  // that region untouched even with DB=0, good OCS and new payload bytes.
  combined_hardware.wire = {};
  combined_hardware.active = false;
  combined_hardware.virt[8] = 0;
  combined_hardware.virt[CombinedRead::Data] = 0x77;
  memcpy(snapshot, mapping, sizeof snapshot);
  const auto mmioReads = combined_hardware.mmioReads;
  IOLockUnlock(gHost.lock);
  assert(result.wait_for(2s) == std::future_status::ready && result.get() == End::Guard);
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
  std::printf("PASS %s + late completion: waiter denied; close/reopen denied; no DMA/MMIO reuse\n",
              timeout ? "timeout" : "fatal");
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
  testTerminal(true);
  testTerminal(false);
}
