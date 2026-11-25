#pragma once
#include "Gate.h"
#include "Reinit.h"

namespace NuwaData {
// Production default. The transport must separately prove cold-start qualification and FUA
// durability; a boot request alone must never grant writes.
#ifdef NUWA_DATA_WRITE_OPT_IN
constexpr bool BuildWriteOptIn = NUWA_DATA_WRITE_OPT_IN == 1;
#else
constexpr bool BuildWriteOptIn = false;
#endif

struct GptBuffers { uint8_t ph[Block], pe[Block], bh[Block], be[Block]; };
enum class LiveGpt : unsigned { Unknown, Ok, Bad };

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
            uint64_t reserve, Window window, GptBuffers &g, bool requestWrite = false,
            LiveGpt *live = nullptr) {
    Lock lock(port_);
    if (live) *live = LiveGpt::Unknown;
    if (open_ || !slot_.rootAllowed() || !port_.readyLocked() ||
        lun != 0 || block != Block || id.capacity < 4 ||
        port_.capacityLocked() != id.capacity ||
        port_.blockSizeLocked() != block || !placement(id, rootBytes, reserve, window))
      return false;
    if (requestWrite && (!BuildEnabled || !slot_.dataAllowed(true) ||
                         !port_.isolationArmedLocked() ||
                         !port_.coldStartEvidenceLocked(id, window).qualified(
                             port_.coldStartIdentityLocked(id, window)) ||
                         !port_.fuaProvenLocked())) return false;
    if (!readLocked(1, g.ph) || !readLocked(2, g.pe) ||
        !readLocked(id.capacity - 1, g.bh)) return false;
    const uint64_t backup = le64(g.bh + 72);
    if (backup <= id.lastUsable || backup >= id.capacity - 1) {
      if (live) *live = LiveGpt::Bad;
      return false;
    }
    if (!readLocked(backup, g.be)) return false;
    const bool valid = gpt(lun, block, id, {1, 2, g.ph, g.pe},
                           {id.capacity - 1, backup, g.bh, g.be});
    if (live) *live = valid ? LiveGpt::Ok : LiveGpt::Bad;
    if (!valid) return false;
    // Recheck the sticky write gate after the GPT reads.
    if (requestWrite && !slot_.dataAllowed(port_.readyLocked())) return false;
    data_ = window;
    open_ = true;
    writeEnabled_ = BuildEnabled && requestWrite;
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
        !slot_.dataAllowed(port_.readyLocked()) || !port_.fuaProvenLocked()) return false;
    for (uint32_t i = 0; i < n; ++i) {
      const uint64_t lba = data_.first + rel + i;
      if (!data_.contains(0, Block, lba, 1) || !canTouchLocked() ||
          !slot_.submit(port_.readyLocked(), true)) return false;
      if (!slot_.complete(port_.writePageLocked(0, data_, lba, 1,
                        static_cast<const uint8_t *>(src) + uint64_t(i) * Block))) return false;
    }
    return true;
  }

  // Logical handle only. This has no transport teardown or recovery callback.
  void close() {
    Lock lock(port_);
    open_ = writeEnabled_ = false;
  }

  // Completion barrier for this window, not SYNCHRONIZE CACHE on the LUN.
  bool sync() {
    if constexpr (!BuildEnabled) return false;
    Lock lock(port_);
    return open_ && writeEnabled_ && slot_.dataAllowed(port_.readyLocked()) &&
           port_.fuaProvenLocked();
  }
  static bool writeLog() { return false; }
  static bool writeExport() { return false; }
  static bool writePanic() { return false; }
};
}
