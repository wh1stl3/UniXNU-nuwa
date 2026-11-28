// SPDX-License-Identifier: BSD-2-Clause-Patent
// Host-only qualification and sequence study; this is not a device initializer.
#define main v1_existing_fixture_main
#include "test-nuwa-v1-entry.cpp"
#undef main

struct ObservedWrite {
  uint64_t lba;
  std::array<uint8_t, 10> cdb;
  Page payload;
};

static std::vector<ObservedWrite> observed;
static unsigned failAt;
static unsigned wireFault;

static Response captureWrite(uint64_t lba, const uint8_t *src) {
  assert(hostGate.held);
  ObservedWrite event{lba, {}, {}};
  memcpy(event.cdb.data(), combined_hardware.virt + 4112, event.cdb.size());
  memcpy(event.payload.data(), src, Block);
  const uint8_t expected[] = {0x2a, 0x08, uint8_t(lba >> 24), uint8_t(lba >> 16),
                              uint8_t(lba >> 8), uint8_t(lba), 0, 0, 1, 0};
  assert(!memcmp(event.cdb.data(), expected, sizeof expected));
  observed.push_back(event);
  Response wire{};
  if (failAt && observed.size() == failAt) {
    switch (wireFault) {
      case 0: wire.status = 2; wire.dl = 16; break; // Attributable CHECK CONDITION.
      case 1: wire.flags = 0x20; wire.residual = 1; break; // Short transfer.
      case 2: wire.badTag = true; break; // Completion cannot be attributed.
      case 3: wire.ocs = 15; wire.timedOut = true; break;
      case 4: wire.ocs = 1; break;
      case 5: wire.fatal = true; break;
      default: assert(false);
    }
    return wire;
  }
  // Simulated GOOD is not a file sync or evidence of persistence.
  assert(pwrite(dataPort.image->fd, src, Block, Image::offset(lba)) == Block);
  return wire;
}

static void prepare(Image &image) {
  setup(image);
  combined_hardware.fileWrite = captureWrite;
  Page old{};
  persist::encodeHeader(old.data(), Pages, Seed, 11);
  assert(image.fua(WFirst, old.data()));
}

static uint64_t referenceLba(unsigned index) {
  assert(index >= 1 && index <= 68);
  if (index == 1 || index == 68) return WFirst;
  if (index <= 3) return V3::Media.first + index - 2;
  return WFirst + index - 3;
}

static void checkTrace(bool reference, unsigned count) {
  assert(observed.size() == count && combined_hardware.writeSubmissions == count);
  for (unsigned i = 1; i <= count; ++i) {
    const auto &event = observed[i - 1];
    const uint64_t lba = reference ? referenceLba(i) : (i <= 64 ? WFirst + i : WFirst);
    assert(event.lba == lba);
    const bool header = reference ? i == 68 : i == 65;
    if (header) {
      uint64_t generation = 0;
      assert(persist::checkHeader(event.payload.data(), Pages, Seed, &generation) == 0);
    } else {
      assert(event.payload == filled(0));
    }
  }
}

static void denial(std::string_view op, unsigned mask) {
  dataPort.identityProven = mask & 1;
  dataPort.producerStopped = dataPort.dmaDone = mask & 2;
  dataPort.fuaProven = mask & 4;
  if (op == "deny-producer") dataPort.producerStopped = false;
  if (op == "deny-dma") dataPort.dmaDone = false;
  resetRequested = true;
  NativeRamBlock ram;
  ram.attachStore();
  auto block = filled(0xff);
  assert(!ram.direct && native_data_persist_state == 4 &&
         !native_ufs_store_write(0, 1, block.data()) && !native_ufs_store_sync() &&
         observed.empty() && !combined_hardware.writeSubmissions);
  if (op == "deny") {
    printf("DENY identity=%u dma=%u fua=%u bottom_writes=0\n",
           !!(mask & 1), !!(mask & 2), !!(mask & 4));
  } else {
    printf("DENY %s bottom_writes=0\n", op == "deny-producer" ? "producer-not-stopped" :
                                                                 "dma-not-drained");
  }
}

// Reference-only recipe: the currently linked v1 entry does NOT call this.
// It opens a synthetic wider window so the two earlier v3 LBAs are addressable.
static bool referenceInit(Image &image) {
  dataPort.evidenceWindow = V3::Media;
  const auto marker = filled(0xa5);
  assert(image.fua(V3::Media.first, marker.data()));
  assert(image.fua(V3::Media.first + 1, marker.data()));
  GptBuffers g{};
  assert(dataProvider.open(dataPort.gpt.id, 0, Block, 8446279680ULL, 262144,
                           V3::Media, g, true));
  const auto zero = filled(0);
  auto writeAbsolute = [&](uint64_t lba) {
    return dataProvider.write(lba - V3::Media.first, 1, zero.data());
  };
  if (!writeAbsolute(WFirst) || !writeAbsolute(V3::Media.first) ||
      !writeAbsolute(V3::Media.first + 1)) return false;
  struct V1Ops {
    bool read(uint64_t b, uint32_t n, void *dst) {
      return dataProvider.read(WFirst - V3::Media.first + b, n, dst);
    }
    bool write(uint64_t b, uint32_t n, const void *src) {
      return dataProvider.write(WFirst - V3::Media.first + b, n, src);
    }
    bool sync() { return dataProvider.sync(); }
  } ops;
  std::vector<uint8_t> bits(persist::bitmapBlocks(Pages) * Block);
  persist::Overlay overlay;
  return overlay.open(ops, Pages, Seed, false, bits.data(), true) == persist::Open::Fresh;
}

static void runReference(Image &image) {
  const bool ok = referenceInit(image);
  if (failAt) {
    assert(!ok && failAt <= 68);
    checkTrace(true, failAt);
    assert(!dataProvider.sync());
    return;
  }
  assert(ok);
  checkTrace(true, 68);
  for (unsigned i = 1; i <= 68; ++i) {
    printf("REFERENCE %02u lba=%llu opcode=2a fua=1 blocks=1 %s\n", i,
           static_cast<unsigned long long>(observed[i - 1].lba),
           i == 68 ? "publish-header" : "zero");
  }
  assert(image.page(V3::Media.first) == filled(0) &&
         image.page(V3::Media.first + 1) == filled(0));
  puts("REFERENCE 68 writes / 67 distinct LBAs: simulated qualification and GOOD responses only");
}

static void runActual(Image &image) {
  const Page old = image.page(WFirst);
  const Page oldMap = filled(0xa5);
  for (unsigned b = 0; b < 64; ++b)
    assert(pwrite(image.fd, oldMap.data(), Block, Image::offset(WFirst + 1 + b)) == Block);
  resetRequested = true;
  NativeRamBlock ram;
  ram.attachStore();
  if (failAt) {
    assert(failAt <= 65 && !ram.direct && !ram.overlay.active &&
           native_data_persist_state == 4 && image.page(WFirst) == old);
    checkTrace(false, failAt);
    assert(image.page(WFirst + 1) == (failAt == 1 ? oldMap : filled(0)));
    assert(!native_ufs_store_sync());
    return;
  }
  assert(ram.direct && ram.overlay.active && native_data_persist_state == 3);
  checkTrace(false, 65);
  puts("BLOCKED actual v1 entry: 65 writes (64 bitmap then header), not the required 68");
  puts("BLOCKED actual v1 entry: no prior header invalidation or v3-anchor clears");
}

int main(int argc, char **argv) {
  assert(argc == 3 || argc == 4);
  const std::string_view op(argv[1]);
  const unsigned value = argc == 4 ? unsigned(strtoul(argv[3], nullptr, 10)) : 7;
  Image image(argv[2], true);
  prepare(image);
  if (op == "deny" || op == "deny-producer" || op == "deny-dma") {
    denial(op, value);
  } else {
    failAt = value;
    if (op == "reference-wire") {
      assert(value >= 1 && value <= 5);
      wireFault = value;
      failAt = 4;
      runReference(image);
      printf("REFERENCE simulated wire fault=%u: no final header\n", value);
    } else if (op == "reference") runReference(image);
    else { assert(op == "actual"); runActual(image); }
  }
  return 0;
}
