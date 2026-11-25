#pragma once
#include "Gate.h"

namespace NuwaData {
// Production default. The transport must separately prove recovery and FUA
// durability; a boot request alone must never grant writes.
#ifdef NUWA_DATA_WRITE_OPT_IN
constexpr bool BuildWriteOptIn = NUWA_DATA_WRITE_OPT_IN == 1;
#else
constexpr bool BuildWriteOptIn = false;
#endif

struct GptBuffers { uint8_t ph[Block], pe[Block], bh[Block], be[Block]; };

// Port contract: methods suffixed Locked run under the same lock as root
// reads. ownershipLocked inspects evidence without accessing shared DMA.
// writePageLocked must recheck ownership before staging DMA, submit once,
// and return only classified completion evidence for that specific command.
// No teardown or reuse of a quarantined queue is delegated to this wrapper.
template<class Port, bool BuildEnabled = BuildWriteOptIn>
class Provider {
  Port &port_;
  Slot &slot_;
  Window data_{};
  bool open_ = false, writeEnabled_ = false;
  struct Lock {
    Port &port;
    explicit Lock(Port &p) : port(p) { port.lock(); }
    ~Lock() { port.unlock(); }
  };
  bool canTouchLocked() {
    if (!port_.readyLocked() || !slot_.rootAllowed()) return false;
    if (port_.ownershipLocked()) return true;
    slot_.quarantine();
    return false;
  }
  bool readLocked(uint64_t lba, void *dst) {
    return canTouchLocked() && port_.readPageLocked(lba, dst);
  }
public:
  constexpr Provider(Port &port, Slot &slot) : port_(port), slot_(slot) {}
  Provider(const Provider &) = delete;
  Provider &operator=(const Provider &) = delete;

  bool open(const GptIdentity &id, unsigned lun, unsigned block, uint64_t rootBytes,
            uint64_t reserve, Window window, GptBuffers &g, bool requestWrite = false) {
    Lock lock(port_);
    if (open_ || lun != 0 || block != Block || id.capacity < 4 ||
        port_.capacityLocked() != id.capacity ||
        port_.blockSizeLocked() != block || !placement(id, rootBytes, reserve, window) ||
        !readLocked(1, g.ph) || !readLocked(2, g.pe) ||
        !readLocked(id.capacity - 1, g.bh)) return false;
    const uint64_t backup = le64(g.bh + 72);
    if (backup <= id.lastUsable || backup >= id.capacity - 1 ||
        !readLocked(backup, g.be) || !gpt(lun, block, id, {1, 2, g.ph, g.pe},
                                        {id.capacity - 1, backup, g.bh, g.be})) return false;
    data_ = window;
    open_ = true;
    writeEnabled_ = BuildEnabled && requestWrite && port_.recoveryProvenLocked() &&
                    port_.fuaProvenLocked();
    // A write request is not silently downgraded to read-only.
    if (requestWrite && !writeEnabled_) { open_ = false; return false; }
    return true;
  }

  bool read(uint64_t rel, uint32_t n, void *dst) {
    Lock lock(port_);
    if (!open_ || !dst || rel >= data_.blocks ||
        !data_.contains(0, Block, data_.first + rel, n)) return false;
    for (uint32_t i = 0; i < n; ++i)
      if (!readLocked(data_.first + rel + i, static_cast<uint8_t *>(dst) + uint64_t(i) * Block))
        return false;
    return true;
  }

  bool write(uint64_t rel, uint32_t n, const void *src) {
    Lock lock(port_);
    if (!open_ || !writeEnabled_ || !src || rel >= data_.blocks ||
        !data_.contains(0, Block, data_.first + rel, n) ||
        !port_.fuaProvenLocked() || !slot_.sync(port_.readyLocked())) return false;
    for (uint32_t i = 0; i < n; ++i) {
      const uint64_t lba = data_.first + rel + i;
      if (!data_.contains(0, Block, lba, 1) || !canTouchLocked() ||
          !slot_.submit(port_.readyLocked(), true)) return false;
      uint8_t cdb[10];
      write10(cdb, uint32_t(lba));
      if (!slot_.complete(port_.writePageLocked(cdb, static_cast<const uint8_t *>(src) +
                                               uint64_t(i) * Block))) return false;
    }
    return true;
  }

  bool sync() {
    Lock lock(port_);
    return open_ && writeEnabled_ && port_.fuaProvenLocked() && slot_.sync(port_.readyLocked());
  }

  static bool writeLog() { return false; }
  static bool writeExport() { return false; }
  static bool writePanic() { return false; }
};
}
