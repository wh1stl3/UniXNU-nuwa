// Diagnostic two-bank Data overlay. Commit ordering follows thyme var_store
// (4bb1a4ee, MIT) as a design reference; no source is copied.
#pragma once
#include "Gate.h"

namespace NuwaData {
inline uint64_t bitmapBlocks(uint64_t pages) {
  return pages / (8 * Block) + (pages % (8 * Block) != 0);
}
inline uint64_t overlayBlocks(uint64_t pages) {
  return pages && pages <= UINT32_MAX / 3 ? 2 * (1 + bitmapBlocks(pages) + pages) : 0;
}
inline void putLE(uint8_t *p, uint64_t value, unsigned bytes) {
  while (bytes--) { *p++ = uint8_t(value); value >>= 8; }
}
inline uint32_t extendCrc(uint32_t sum, const uint8_t *p) {
  for (unsigned i = 0; i < Block; ++i) {
    sum ^= p[i];
    for (unsigned j = 0; j < 8; ++j) sum = (sum >> 1) ^ (0xedb88320U & (0U - (sum & 1)));
  }
  return sum;
}

// The caller serializes all methods. Work buffers: two full padded bitmaps
// and one 4 KiB page, all disjoint from user I/O buffers.
class Overlay {
  enum class Check { Empty, Valid, Damaged, Foreign, Io };
  uint64_t pages_ = 0, bits_ = 0, gen_ = 0;
  unsigned slot_ = 0;
  uint8_t *map_ = nullptr, *pending_ = nullptr, *work_ = nullptr;
  uint8_t seed_[32]{};
  bool ready_ = false, writable_ = false;
  uint64_t start(unsigned n) const { return n * (1 + bits_ + pages_); }
  uint64_t page(unsigned n, uint64_t i) const { return start(n) + 1 + bits_ + i; }
  static bool bit(const uint8_t *map, uint64_t i) { return (map[i / 8] >> (i % 8)) & 1; }
  bool stop() { ready_ = writable_ = false; return false; }
  template<class O> Check scan(O &ops, unsigned slot, uint8_t *map, uint64_t &gen) {
    if (!ops.read(start(slot), 1, work_)) return Check::Io;
    if (zero(work_, Block)) return Check::Empty;
    if (memcmp(work_, "NUWADATA", 8)) return Check::Foreign;
    if (le32(work_ + 8) != 2 || le32(work_ + 12) != slot ||
        le32(work_ + 68) != crc(work_, Block, 68)) return Check::Damaged;
    if (le64(work_ + 16) != pages_ || memcmp(work_ + 32, seed_, 32)) return Check::Foreign;
    gen = le64(work_ + 24);
    if (!gen) return Check::Damaged;
    const uint32_t want = le32(work_ + 64);
    uint32_t sum = ~uint32_t(0);
    for (uint64_t b = 0; b < bits_; ++b) {
      auto *at = map + b * Block;
      if (!ops.read(start(slot) + 1 + b, 1, at)) return Check::Io;
      sum = extendCrc(sum, at);
    }
    for (uint64_t i = pages_; i < bits_ * 8 * Block; ++i)
      if (bit(map, i)) return Check::Damaged;
    for (uint64_t i = 0; i < pages_; ++i) {
      if (!bit(map, i)) continue;
      if (!ops.read(page(slot, i), 1, work_)) return Check::Io;
      sum = extendCrc(sum, work_);
    }
    return ~sum == want ? Check::Valid : Check::Damaged;
  }
public:
  enum class Open { Failed, Empty, Resumed };
  bool ready() const { return ready_; }
  bool writable() const { return writable_; }
  uint64_t generation() const { return gen_; }
  bool has(uint64_t i) const { return ready_ && i < pages_ && bit(map_, i); }

  template<class O> Open open(O &ops, uint64_t pages, const uint8_t *seed,
                              uint8_t *maps, uint8_t *work, bool write, bool create) {
    stop();
    gen_ = 0;
    if (!overlayBlocks(pages) || !maps || !work) return Open::Failed;
    pages_ = pages; bits_ = bitmapBlocks(pages);
    map_ = maps; pending_ = maps + bits_ * Block; work_ = work;
    memcpy(seed_, seed, sizeof seed_);
    uint64_t a = 0, b = 0;
    const auto x = scan(ops, 0, map_, a), y = scan(ops, 1, pending_, b);
    if (x == Check::Io || y == Check::Io) return Open::Failed;
    const bool va = x == Check::Valid, vb = y == Check::Valid;
    if (va || vb) {
      if (va && vb && a == b) return Open::Failed;
      slot_ = vb && (!va || b > a);
      gen_ = slot_ ? b : a;
      const auto other = slot_ ? x : y;
      if (slot_) { auto *old = map_; map_ = pending_; pending_ = old; }
      // Damaged or foreign headers are never overwritten. Even when an
      // intact fallback exists, let it serve reads only.
      writable_ = write && (other == Check::Empty || other == Check::Valid);
      ready_ = true;
      return Open::Resumed; // A creation/reset request cannot drop this generation.
    }
    if (x != Check::Empty || y != Check::Empty) return Open::Failed;
    // Zero header alone does not distinguish an unused window from an
    // interrupted first commit or an unknown format elsewhere in the window.
    for (uint64_t i = 0; i < overlayBlocks(pages); ++i)
      if (!ops.read(i, 1, work_) || !zero(work_, Block)) return Open::Failed;
    memset(map_, 0, bits_ * Block);
    slot_ = 1;
    writable_ = write && create;
    ready_ = true;
    return Open::Empty;
  }

  template<class O> bool read(O &ops, uint64_t i, void *dst) {
    if (!has(i)) return false;
    return ops.read(page(slot_, i), 1, dst) || stop();
  }

  template<class O> bool writeRun(O &ops, uint64_t first, uint32_t count, const void *src) {
    if (!writable_ || !count || first >= pages_ || count > pages_ - first ||
        gen_ == UINT64_MAX || !src) return false;
    if (!ops.sync()) return stop(); // FUA persistence must be proven before the first write.
    const unsigned next = slot_ ^ 1;
    memcpy(pending_, map_, bits_ * Block);
    for (uint64_t i = first; i - first < count; ++i)
      pending_[i / 8] |= uint8_t(1U << (i % 8));

    // Drop the *inactive* header before replacing anything it could name.
    memset(work_, 0, Block);
    if (!ops.write(start(next), 1, work_)) return stop();
    uint32_t sum = ~uint32_t(0);
    for (uint64_t b = 0; b < bits_; ++b)
      sum = extendCrc(sum, pending_ + b * Block);
    for (uint64_t i = 0; i < pages_; ++i) {
      if (!bit(pending_, i)) continue;
      const uint8_t *data = work_;
      if (i >= first && i - first < count) {
        data = static_cast<const uint8_t *>(src) + (i - first) * Block;
      } else if (!ops.read(page(slot_, i), 1, work_)) {
        return stop();
      }
      if (!ops.write(page(next, i), 1, data)) return stop();
      sum = extendCrc(sum, data);
    }
    for (uint64_t b = 0; b < bits_; ++b)
      if (!ops.write(start(next) + 1 + b, 1, pending_ + b * Block)) return stop();
    if (!ops.sync()) return stop();
    memset(work_, 0, Block);
    memcpy(work_, "NUWADATA", 8);
    putLE(work_ + 8, 2, 4);
    putLE(work_ + 12, next, 4);
    putLE(work_ + 16, pages_, 8);
    putLE(work_ + 24, gen_ + 1, 8);
    memcpy(work_ + 32, seed_, sizeof seed_);
    putLE(work_ + 64, ~sum, 4);
    putLE(work_ + 68, crc(work_, Block, 68), 4);
    if (!ops.write(start(next), 1, work_) || !ops.sync()) return stop();
    auto *old = map_; map_ = pending_; pending_ = old;
    slot_ = next;
    ++gen_;
    return true;
  }
};
}
