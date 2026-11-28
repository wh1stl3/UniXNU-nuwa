// SPDX-License-Identifier: BSD-2-Clause
#pragma once
#include "Gate.h"

namespace NuwaData {
// Caller serializes the overlay and supplies an already qualified window.
// Production Ops uses Provider's FUA contract. The disposable format uses only
// ordered command completion, never checkpoints/reuses log slots, and cannot create.
template<uint32_t RingBlocks = 512, bool Disposable = false>
class DualBankLogOverlay {
public:
  static constexpr uint64_t Pages = 2097152;
  static constexpr uint32_t MapBlocks = 64, LogBlocks = RingBlocks, MaxRun = 250;
  static constexpr uint64_t Map0 = 2, Map1 = 130, Log = 258;
  static constexpr uint64_t Data0 = Log + LogBlocks, Data1 = Data0 + Pages;
  static constexpr Window Media{57393401, Data1 + Pages};
  static constexpr uint64_t LegacyHeader0 = 640, LegacyHeader1 = 2097857;
  static constexpr size_t MapBytes = MapBlocks * Block;
  static_assert(LogBlocks > 0 && LogBlocks <= 512, "test ring must fit the production ring");
  static constexpr uint64_t overlayBlocks(uint64_t pages) { return pages == Pages ? Media.blocks : 0; }

  enum class Open { Failed, Empty, Resumed };
  // Keep this outside the stack on constrained callers. No allocation or
  // seed I/O is performed here; a page absent from the overlay belongs to seed.
  struct Workspace {
    uint8_t maps[2 * MapBytes], block[Block], data[Block];
  };
  struct SeenScratch { uint8_t bits[MapBytes]; };

private:
  enum class Header { Empty, Foreign, Damaged, Valid };
  enum class Record { Empty, Corrupt, Invalid, Valid };
  struct Checkpoint {
    uint64_t gen, count;
    uint32_t head, mapCrc;
  };
  struct LogRecord {
    uint64_t gen, epoch;
    uint32_t count;
  };
  static constexpr size_t SbHeader = 96, LogHeader = 80, EntryBytes = 16;
  static constexpr const char *SbMagic = Disposable ? "NUWAXSB3" : "NUWADSB3";
  static constexpr const char *LogMagic = Disposable ? "NUWAXLOG" : "NUWADLOG";
  static constexpr size_t Tail = Block - 16, BlockCrc = Block - 4;
  static_assert(LogHeader + EntryBytes * MaxRun == Tail, "log framing");
  Workspace *w_ = nullptr;
  uint8_t seed_[32]{};
  uint64_t gen_ = 0, epoch_ = 0, present_ = 0;
  uint32_t slot_ = 0, head_ = 0, used_ = 0;
  bool ready_ = false, writable_ = false, anchored_ = false;

  static void put(uint8_t *p, uint64_t value, unsigned n) {
    for (; n; --n, value >>= 8) *p++ = uint8_t(value);
  }
  static bool bit(const uint8_t *map, uint64_t i) {
    return (map[i >> 3] >> (i & 7)) & 1;
  }
  static void set(uint8_t *map, uint64_t i, bool value) {
    const auto mask = uint8_t(1U << (i & 7));
    if (value) map[i >> 3] |= mask;
    else map[i >> 3] &= uint8_t(~mask);
  }
  static uint64_t dataLba(bool bank, uint64_t page) { return (bank ? Data1 : Data0) + page; }
  static uint64_t mapLba(uint32_t slot) { return slot ? Map1 : Map0; }
  uint8_t *active() const { return w_->maps + MapBytes; }
  uint32_t ring(uint32_t n) const { return (head_ + n) % LogBlocks; }
  bool stop() { ready_ = writable_ = false; return false; }
  bool target(uint64_t page) const { return bit(w_->maps, page) && !bit(active(), page); }
  void apply(uint64_t page, bool bank) {
    if (!bit(w_->maps, page)) ++present_;
    set(w_->maps, page, true);
    set(active(), page, bank);
  }
  static uint8_t *entry(uint8_t *b, uint32_t n) { return b + LogHeader + n * EntryBytes; }
  static void seal(uint8_t *b, size_t header, size_t headerCrc, uint64_t gen, uint32_t slot) {
    put(b + Tail, gen, 8);
    put(b + Tail + 8, slot, 4);
    put(b + headerCrc, crc(b, header, headerCrc), 4);
    put(b + BlockCrc, crc(b, Block, BlockCrc), 4);
  }
  static void encodeSuperblock(uint8_t *b, const uint8_t *seed, const uint8_t *maps,
                               uint32_t slot, uint32_t head, uint64_t gen, uint64_t count) {
    memset(b, 0, Block);
    memcpy(b, SbMagic, 8);
    put(b + 8, 3, 4);
    put(b + 12, slot, 4);
    put(b + 16, Pages, 8);
    put(b + 24, gen, 8);
    memcpy(b + 32, seed, 32);
    put(b + 64, MapBlocks, 4);
    put(b + 68, LogBlocks, 4);
    put(b + 72, head, 4);
    put(b + 80, count, 8);
    put(b + 88, crc(maps, 2 * MapBytes), 4);
    seal(b, SbHeader, 92, gen, slot);
  }

  static bool tornSuperblockMarker(const uint8_t *b, uint32_t slot) {
    for (size_t i = 1; i < 8; ++i)
      if (!memcmp(b, SbMagic, i) && zero(b + i, Tail - i)) return true;
    return zero(b, Tail) && le32(b + Tail + 8) == slot && le64(b + Tail);
  }

  static Header decodeSuperblock(const uint8_t *b, const uint8_t *seed,
                                 uint32_t slot, Checkpoint &cp) {
    if (zero(b, Block)) return Header::Empty;
    if (memcmp(b, SbMagic, 8)) {
      // A torn first write to the alternate SB can leave only its tail,
      // or a prefix of the magic over an all-zero header.
      return tornSuperblockMarker(b, slot) ? Header::Damaged : Header::Foreign;
    }
    if (le32(b + BlockCrc) != crc(b, Block, BlockCrc)) return Header::Damaged;
    if (le32(b + 8) != 3 || le64(b + 16) != Pages || memcmp(b + 32, seed, 32) ||
        le32(b + 64) != MapBlocks || le32(b + 68) != LogBlocks)
      return Header::Foreign;
    cp = {le64(b + 24), le64(b + 80), le32(b + 72), le32(b + 88)};
    if (le32(b + 12) != slot || cp.head >= LogBlocks || le32(b + 76) ||
        cp.count > Pages || le32(b + 92) != crc(b, SbHeader, 92) ||
        !zero(b + SbHeader, Tail - SbHeader) || le64(b + Tail) != cp.gen ||
        le32(b + Tail + 8) != slot) return Header::Foreign; // sealed, but impossible
    return Header::Valid;
  }
  Header superblock(uint32_t slot, Checkpoint &cp) const {
    return decodeSuperblock(w_->block, seed_, slot, cp);
  }

  bool checkMap(const Checkpoint &cp) const {
    // Pages == MapBytes * 8, hence there is no unused tail in either map.
    static_assert(Pages == MapBytes * 8, "bitmap tail must be validated if geometry changes");
    if (crc(w_->maps, sizeof w_->maps) != cp.mapCrc) return false;
    uint64_t count = 0;
    for (size_t i = 0; i < MapBytes; ++i) {
      auto p = w_->maps[i];
      if (active()[i] & ~p) return false;
      for (; p; p &= uint8_t(p - 1)) ++count;
    }
    return count == cp.count;
  }

  Record record(uint32_t physical, LogRecord &r) const {
    auto *b = w_->block;
    if (zero(b, Block)) return Record::Empty;
    if (le32(b + BlockCrc) != crc(b, Block, BlockCrc)) return Record::Corrupt;
    r = {le64(b + 16), le64(b + 24), le32(b + 64)};
    if (memcmp(b, LogMagic, 8) || le32(b + 8) != 3 || le32(b + 12) != physical ||
        memcmp(b + 32, seed_, 32) || !r.count || r.count > MaxRun ||
        le32(b + 68) || le32(b + 72) != crc(b, LogHeader, 72) || le32(b + 76) ||
        le64(b + Tail) != r.gen || le32(b + Tail + 8) != physical ||
        r.gen <= r.epoch || r.gen - r.epoch > LogBlocks ||
        !zero(entry(b, r.count), (MaxRun - r.count) * EntryBytes))
      return Record::Invalid;
    for (uint32_t i = 0; i < r.count; ++i) {
      const auto *e = entry(b, i);
      const auto page = le64(e);
      if (page >= Pages || e[12] > 1 || !zero(e + 13, 3)) return Record::Invalid;
      for (uint32_t j = 0; j < i; ++j)
        if (page == le64(entry(b, j))) return Record::Invalid;
    }
    return Record::Valid;
  }

  template<class Ops> bool replay(Ops &ops, SeenScratch &seen) {
    for (uint32_t i = 0; i < LogBlocks; ++i) {
      const auto physical = ring(i);
      if (!ops.read(Log + physical, 1, w_->block)) return false;
      LogRecord r{};
      const auto state = record(physical, r);
      if (state == Record::Invalid || (state == Record::Corrupt && (Disposable || i != used_)))
        return false;
      if (state != Record::Valid) continue;
      if (r.gen - r.epoch != uint64_t(i) + 1) return false;
      if (r.epoch < epoch_) {
        if (r.gen > epoch_) return false;
        continue;
      }
      if (r.epoch != epoch_ || i != used_ || gen_ == UINT64_MAX || r.gen != gen_ + 1)
        return false;
      for (uint32_t j = 0; j < r.count; ++j) {
        const auto *e = entry(w_->block, j);
        const auto page = le64(e);
        if (bool(e[12]) != target(page)) return false;
        apply(page, e[12]);
      }
      gen_ = r.gen;
      ++used_;
    }

    memset(seen.bits, 0, sizeof seen.bits);
    for (uint32_t n = used_; n; --n) {
      const auto physical = ring(n - 1);
      if (!ops.read(Log + physical, 1, w_->block)) return false;
      LogRecord r{};
      if (record(physical, r) != Record::Valid || r.epoch != epoch_ ||
          r.gen - r.epoch != n) return false;
      for (uint32_t j = 0; j < r.count; ++j) {
        const auto *e = entry(w_->block, j);
        const auto page = le64(e);
        if (bit(seen.bits, page)) continue;
        if (!ops.read(dataLba(e[12], page), 1, w_->data) ||
            crc(w_->data, Block) != le32(e + 8)) return false;
        set(seen.bits, page, true);
      }
    }
    return true;
  }

  template<class Ops> bool checkpoint(Ops &ops) {
    const uint32_t next = anchored_ ? slot_ ^ 1U : 0;
    if (anchored_) {
      for (uint32_t i = 0; i < 2 * MapBlocks; ++i)
        if (!ops.write(mapLba(next) + i, 1, w_->maps + size_t(i) * Block)) return false;
      if (!ops.sync()) return false;
    }
    // On first use, open already verified BMP0 is entirely zero.
    const auto nextHead = ring(used_);
    auto *b = w_->block;
    encodeSuperblock(b, seed_, w_->maps, next, nextHead, gen_, present_);
    if (!ops.write(next, 1, b) || !ops.sync()) return false;
    slot_ = next;
    epoch_ = gen_;
    head_ = nextHead;
    used_ = 0;
    anchored_ = true;
    return true;
  }

public:
  // Marker recognition, not validation for replay: a foreign seed or bad CRC
  // does not make a superblock safe for another format to overwrite.
  static bool hasSuperblockMarker(const uint8_t *b, uint32_t slot) {
    return !memcmp(b, SbMagic, 8) || tornSuperblockMarker(b, slot);
  }
  // Erasure requires the complete sealed header, not the weaker deny marker.
  static bool validSuperblockForSeed(const uint8_t *b, uint32_t slot, const uint8_t *seed) {
    Checkpoint cp{};
    if (decodeSuperblock(b, seed, slot, cp) != Header::Valid) return false;
    if constexpr (Disposable) {
      // Disposable creation starts with zero maps and never checkpoints.
      // IEEE CRC32 of 2 * MapBytes (524288) zero bytes, as in encodeSuperblock.
      static_assert(MapBytes == 262144);
      return !cp.gen && !cp.head && !cp.count && cp.mapCrc == 0x75660aacU;
    }
    return true;
  }
  // Pure format helper: no admission, transport, ownership or durability claim.
  static bool initialSuperblock(uint8_t (&out)[Block], const uint8_t (&seed)[32],
                                const Workspace &workspace) {
    if (!zero(workspace.maps, sizeof workspace.maps)) return false;
    encodeSuperblock(out, seed, workspace.maps, 0, 0, 0, 0);
    return true;
  }
  DualBankLogOverlay() = default;
  DualBankLogOverlay(const DualBankLogOverlay &) = delete;
  DualBankLogOverlay &operator=(const DualBankLogOverlay &) = delete;
  bool ready() const { return ready_; }
  bool writable() const { return writable_; }
  uint64_t generation() const { return gen_; }
  uint64_t presentCount() const { return ready_ ? present_ : 0; }
  bool has(uint64_t i) const { return ready_ && i < Pages && bit(w_->maps, i); }

  template<class Ops>
  Open open(Ops &ops, const uint8_t (&seed)[32], Workspace &workspace, SeenScratch &seen,
            bool write, bool create) {
    stop();
    gen_ = epoch_ = present_ = 0;
    slot_ = head_ = used_ = 0;
    anchored_ = false;
    w_ = &workspace;
    memcpy(seed_, seed, sizeof seed_);
    Header headers[2];
    Checkpoint cp[2]{};
    for (uint32_t i = 0; i < 2; ++i) {
      if (!ops.read(i, 1, w_->block)) return Open::Failed;
      headers[i] = superblock(i, cp[i]);
      if (headers[i] == Header::Foreign) return Open::Failed;
    }
    const bool a = headers[0] == Header::Valid, b = headers[1] == Header::Valid;
    if constexpr (Disposable) {
      // The separate initializer produces only SB0 and zero maps/ring.
      // Without FUA there is no unchecked checkpoint and no in-kernel create.
      if (!a || headers[1] != Header::Empty || cp[0].gen || cp[0].count || cp[0].head)
        return Open::Failed;
    }
    if (!a && !b) {
      if (headers[0] != Header::Empty || headers[1] != Header::Empty) return Open::Failed;
      for (uint64_t i = 2; i < Data0; ++i)
        if (!ops.read(i, 1, w_->block) || !zero(w_->block, Block)) return Open::Failed;
      const uint64_t probes[] = {LegacyHeader0, LegacyHeader1};
      for (const auto i : probes)
        if (i >= Data0 && (!ops.read(i, 1, w_->block) || !zero(w_->block, Block)))
          return Open::Failed;
      memset(w_->maps, 0, sizeof w_->maps);
      ready_ = true;
      writable_ = write && create;
      return Open::Empty;
    }
    if (a && b && cp[0].gen == cp[1].gen) return Open::Failed;
    slot_ = b && (!a || cp[1].gen > cp[0].gen);
    const auto &latest = cp[slot_];
    for (uint32_t i = 0; i < 2 * MapBlocks; ++i)
      if (!ops.read(mapLba(slot_) + i, 1, w_->maps + size_t(i) * Block)) return Open::Failed;
    if (!checkMap(latest)) return Open::Failed; // No fallback from a sealed new checkpoint.
    gen_ = epoch_ = latest.gen;
    present_ = latest.count;
    head_ = latest.head;
    if (!replay(ops, seen)) return Open::Failed;
    anchored_ = ready_ = true;
    writable_ = write && gen_ != UINT64_MAX && (!Disposable || used_ < LogBlocks);
    return Open::Resumed;
  }

  template<class Ops> bool read(Ops &ops, uint64_t page, void *dst) {
    if (!dst || !has(page)) return false;
    return ops.read(dataLba(bit(active(), page), page), 1, dst) || stop();
  }

  // One contiguous run, committed by one log block. src must not alias Workspace.
  template<class Ops> bool writeRun(Ops &ops, uint64_t first, uint32_t count, const void *src) {
    if (!writable_ || !src || first >= Pages || !count || count > MaxRun ||
        count > Pages - first || gen_ == UINT64_MAX) return stop();
    if constexpr (Disposable) {
      if (!anchored_ || used_ == LogBlocks) return stop();
    } else {
      if ((!anchored_ || used_ == LogBlocks) && !checkpoint(ops)) return stop();
    }
    const auto physical = ring(used_);
    const auto *data = static_cast<const uint8_t *>(src);
    auto *b = w_->block;
    memset(b, 0, Block);
    for (uint32_t i = 0; i < count; ++i) {
      const auto page = first + i;
      const bool bank = target(page);
      auto *e = entry(b, i);
      put(e, page, 8);
      put(e + 8, crc(data + size_t(i) * Block, Block), 4);
      e[12] = uint8_t(bank);
      if (!ops.write(dataLba(bank, page), 1, data + size_t(i) * Block)) return stop();
    }
    if (!ops.sync()) return stop();
    memcpy(b, LogMagic, 8);
    put(b + 8, 3, 4);
    put(b + 12, physical, 4);
    put(b + 16, gen_ + 1, 8);
    put(b + 24, epoch_, 8);
    memcpy(b + 32, seed_, 32);
    put(b + 64, count, 4);
    seal(b, LogHeader, 72, gen_ + 1, physical);
    if (!ops.write(Log + physical, 1, b) || !ops.sync()) return stop();
    for (uint32_t i = 0; i < count; ++i) apply(first + i, entry(b, i)[12]);
    ++gen_;
    ++used_;
    if (gen_ == UINT64_MAX || (Disposable && used_ == LogBlocks)) writable_ = false;
    return true;
  }
};
} // namespace NuwaData
