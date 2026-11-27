// SPDX-License-Identifier: BSD-2-Clause
// Read-only replay diagnostic for the disposable Data overlay.
//
// This mirrors DualBankLogOverlay<512,true>::open/replay but records the first
// refusal instead of returning Open::Failed. It performs reads only; it never
// creates, checkpoints, updates maps, writes a record, mounts, publishes Data,
// or admits a write. The host fixture cross-checks every verdict against the
// real DualBankLogOverlay open() on the same bytes.
#pragma once
#include "DisposableData.h"
#if defined(KERNEL) || defined(_KERNEL)
#include <libkern/libkern.h>
#else
#include <stdio.h>
#endif

namespace NuwaData::Sb0R2 {
using Overlay = Disposable::Overlay;
using Workspace = Overlay::Workspace;
using SeenScratch = Overlay::SeenScratch;

constexpr uint32_t MapBlocks = Overlay::MapBlocks;
constexpr uint32_t LogBlocks = Overlay::LogBlocks;
constexpr uint64_t Pages = Overlay::Pages;
constexpr uint32_t MapBytes = Overlay::MapBytes;
constexpr uint32_t SbHeader = 96, LogHeader = 80, EntryBytes = 16;
constexpr uint32_t Tail = Block - 16, BlockCrc = Block - 4;
// Disposable format only. dualbank selects these with the same template flag.
constexpr char SbMagic[] = "NUWAXSB3";
constexpr char LogMagic[] = "NUWAXLOG";
static_assert(LogBlocks == 512 && Pages == 2097152 && MapBlocks == 64, "layout changed");
static_assert(LogHeader + EntryBytes * Overlay::MaxRun == Tail, "log framing changed");

enum class Anchor : uint8_t { Unknown, Zero, Exact, Other };
enum class Header : uint8_t { Unknown, Empty, Valid, Damaged, Foreign };
enum class RecordState : uint8_t { Empty, Corrupt, Invalid, Valid };

// Ordered to match the checks in DualBankLogOverlay::open/replay. NONE means
// the disposable overlay would open and replay under its own rules.
enum class Fault : uint8_t {
  None, Seed, Guard, Geometry, Gpt, Io,
  Sb0Empty, Sb0Damaged, Sb0Foreign,
  Sb1Present, Sb1Damaged, Sb1Foreign,
  NotInitial, BothValid,
  MapCrc, MapActive, MapCount,
  LogCrc, LogEmpty, LogFormat, LogGeneration, LogTail,
  EntryRange, EntryBank, EntryDuplicate,
  Sequence, Epoch, Chain, BankTarget,
  DataIo, DataCrc,
};

struct Checkpoint { uint64_t gen, count; uint32_t head, mapCrc; };
struct Rec { uint64_t gen, epoch; uint32_t count; };

struct Diagnosis {
  Anchor anchor = Anchor::Unknown;
  uint8_t anchor16[16]{};
  Header sb0 = Header::Unknown, sb1 = Header::Unknown;
  bool sb0Valid = false;
  uint32_t slot = 0;
  uint64_t gen = 0, epoch = 0, count = 0;
  uint32_t head = 0, mapCrc = 0, present = 0;
  bool mapRead = false;
  Fault fault = Fault::None;
  // First bad record: 0-based physical log slot in the ring window.
  uint32_t rec = UINT32_MAX, ring = UINT32_MAX, entry = UINT32_MAX;
  uint64_t lba = 0;
  // First bad record's own fields and offending entry, when parsed.
  uint64_t badGen = 0, badEpoch = 0, badPage = 0;
  uint32_t badCount = 0, badBank = 0, badEntryCrc = 0, badDataCrc = 0;
  uint32_t records = 0; // records replayed
  uint32_t refs = 0;    // unique referenced data pages encountered
  uint32_t pages = 0;   // referenced data pages read and CRC-matched
  uint32_t read = 0;    // total successful 4 KiB reads through the gate
  const char *why = nullptr; // preflight note only (seed/bring-up/geometry)
};

inline bool bit(const uint8_t *map, uint64_t i) {
  return (map[i >> 3] >> (i & 7)) & 1;
}
inline void set(uint8_t *map, uint64_t i, bool value) {
  const auto mask = uint8_t(1U << (i & 7));
  if (value) map[i >> 3] |= mask;
  else map[i >> 3] &= uint8_t(~mask);
}
inline uint64_t dataLba(bool bank, uint64_t page) {
  return (bank ? Overlay::Data1 : Overlay::Data0) + page;
}
inline uint64_t mapLba(uint32_t slot) { return slot ? Overlay::Map1 : Overlay::Map0; }

// Production overlay adapter. The parser speaks window-relative pages; this
// is the only place that translates them to LU0 absolute LBAs. GPT/geometry
// reads stay outside this wrapper and keep their absolute LBAs.
template<class Port>
struct Sb0R2Port {
  Port &p;
  bool read(uint64_t rel, uint32_t n, void *dst) {
    if (n != 1 || !dst || rel >= Overlay::Media.blocks) return false;
    return p.read(Overlay::Media.first + rel, static_cast<uint8_t *>(dst));
  }
};

// Same classification and byte checks as DualBankLogOverlay::superblock().
inline Header header(const uint8_t *b, uint32_t slot, const uint8_t (&seed)[32],
                     Checkpoint &cp) {
  if (zero(b, Block)) return Header::Empty;
  if (memcmp(b, SbMagic, 8)) {
    for (size_t i = 1; i < 8; ++i)
      if (!memcmp(b, SbMagic, i) && zero(b + i, Tail - i)) return Header::Damaged;
    if (zero(b, Tail) && le32(b + Tail + 8) == slot && le64(b + Tail)) return Header::Damaged;
    return Header::Foreign;
  }
  if (le32(b + BlockCrc) != crc(b, Block, BlockCrc)) return Header::Damaged;
  if (le32(b + 8) != 3 || le64(b + 16) != Pages || memcmp(b + 32, seed, 32) ||
      le32(b + 64) != MapBlocks || le32(b + 68) != LogBlocks) return Header::Foreign;
  cp = {le64(b + 24), le64(b + 80), le32(b + 72), le32(b + 88)};
  if (le32(b + 12) != slot || cp.head >= LogBlocks || le32(b + 76) ||
      cp.count > Pages || le32(b + 92) != crc(b, SbHeader, 92) ||
      !zero(b + SbHeader, Tail - SbHeader) || le64(b + Tail) != cp.gen ||
      le32(b + Tail + 8) != slot) return Header::Foreign;
  return Header::Valid;
}

// Same field and entry checks as DualBankLogOverlay::record().
inline RecordState record(const uint8_t *b, uint32_t physical, const uint8_t (&seed)[32],
                          Rec &r, Fault &why, uint32_t &entry) {
  entry = UINT32_MAX;
  if (zero(b, Block)) return RecordState::Empty;
  if (le32(b + BlockCrc) != crc(b, Block, BlockCrc)) {
    why = Fault::LogCrc;
    return RecordState::Corrupt;
  }
  r = {le64(b + 16), le64(b + 24), le32(b + 64)};
  if (memcmp(b, LogMagic, 8) || le32(b + 8) != 3 || le32(b + 12) != physical ||
      memcmp(b + 32, seed, 32) || !r.count || r.count > Overlay::MaxRun ||
      le32(b + 68) || le32(b + 72) != crc(b, LogHeader, 72) || le32(b + 76) ||
      le64(b + Tail) != r.gen || le32(b + Tail + 8) != physical) {
    why = Fault::LogFormat;
    return RecordState::Invalid;
  }
  if (r.gen <= r.epoch || r.gen - r.epoch > LogBlocks) {
    why = Fault::LogGeneration;
    return RecordState::Invalid;
  }
  if (!zero(b + LogHeader + r.count * EntryBytes,
            (Overlay::MaxRun - r.count) * EntryBytes)) {
    why = Fault::LogTail;
    return RecordState::Invalid;
  }
  for (uint32_t i = 0; i < r.count; ++i) {
    const auto *e = b + LogHeader + i * EntryBytes;
    const auto page = le64(e);
    if (page >= Pages) { why = Fault::EntryRange; entry = i; return RecordState::Invalid; }
    if (e[12] > 1 || !zero(e + 13, 3)) {
      why = Fault::EntryBank;
      entry = i;
      return RecordState::Invalid;
    }
    for (uint32_t j = 0; j < i; ++j)
      if (page == le64(b + LogHeader + j * EntryBytes)) {
        why = Fault::EntryDuplicate;
        entry = i;
        return RecordState::Invalid;
      }
  }
  why = Fault::None;
  return RecordState::Valid;
}

// Same map checks as DualBankLogOverlay::checkMap().
inline Fault checkMap(const uint8_t *maps, const Checkpoint &cp, uint32_t &present) {
  if (crc(maps, 2 * MapBytes) != cp.mapCrc) return Fault::MapCrc;
  const uint8_t *active = maps + MapBytes;
  uint64_t count = 0;
  for (uint32_t i = 0; i < MapBytes; ++i) {
    if (uint8_t(active[i] & ~maps[i])) return Fault::MapActive;
    for (uint8_t p = maps[i]; p; p &= uint8_t(p - 1)) ++count;
  }
  present = uint32_t(count);
  return count == cp.count ? Fault::None : Fault::MapCount;
}

// Read-only mirror of Disposable open() + replay(). Caller supplies storage;
// no allocation or mutation of media occurs here.
template<class Ops>
inline void parse(Ops &ops, const uint8_t (&seed)[32], const uint8_t *exact,
                  Workspace &w, SeenScratch &seen, Diagnosis &d) {
  auto *present = w.maps;
  auto *active = w.maps + MapBytes;
  Header hs[2] = {Header::Unknown, Header::Unknown};
  Checkpoint cp[2]{};
  for (uint32_t i = 0; i < 2; ++i) {
    if (!ops.read(i, 1, w.block)) {
      d.fault = Fault::Io;
      d.lba = i;
      return;
    }
    ++d.read;
    if (!i) {
      memcpy(d.anchor16, w.block, sizeof d.anchor16);
      d.anchor = zero(w.block, Block) ? Anchor::Zero
               : !memcmp(w.block, exact, Block) ? Anchor::Exact : Anchor::Other;
    }
    hs[i] = header(w.block, i, seed, cp[i]);
    if (!i) {
      d.sb0 = hs[i];
      d.sb0Valid = hs[i] == Header::Valid;
    } else {
      d.sb1 = hs[i];
    }
    if (hs[i] == Header::Foreign) {
      d.fault = i ? Fault::Sb1Foreign : Fault::Sb0Foreign;
      d.lba = i;
      break;
    }
  }
  if (d.fault != Fault::None) return;
  const bool a = hs[0] == Header::Valid, b = hs[1] == Header::Valid;
  // Disposable admission: exactly one valid SB0 and an empty SB1; no
  // checkpoint generation, count or head is accepted.
  if (!a || hs[1] != Header::Empty) {
    d.fault = !a ? (hs[0] == Header::Empty ? Fault::Sb0Empty
                  : hs[0] == Header::Damaged ? Fault::Sb0Damaged : Fault::Sb0Foreign)
                 : (hs[1] == Header::Damaged ? Fault::Sb1Damaged : Fault::Sb1Present);
    return;
  }
  if (cp[0].gen || cp[0].count || cp[0].head) {
    d.fault = Fault::NotInitial;
    return;
  }
  if (a && b && cp[0].gen == cp[1].gen) {
    d.fault = Fault::BothValid;
    return;
  }
  d.slot = b && (!a || cp[1].gen > cp[0].gen) ? 1U : 0U;
  const auto &latest = cp[d.slot];
  d.gen = latest.gen;
  d.epoch = latest.gen;
  d.count = latest.count;
  d.head = latest.head;
  d.mapCrc = latest.mapCrc;
  for (uint32_t i = 0; i < 2 * MapBlocks; ++i) {
    if (!ops.read(mapLba(d.slot) + i, 1, present + size_t(i) * Block)) {
      d.fault = Fault::Io;
      d.lba = mapLba(d.slot) + i;
      return;
    }
    ++d.read;
  }
  d.mapRead = true;
  d.fault = checkMap(present, latest, d.present);
  if (d.fault != Fault::None) return;

  const auto setRec = [&](uint32_t physical, uint32_t ring, const Rec &r) {
    d.rec = physical;
    d.ring = ring;
    d.badGen = r.gen;
    d.badEpoch = r.epoch;
    d.badCount = r.count;
  };
  const auto setEntry = [&](uint32_t j) {
    d.entry = j;
    const auto *e = w.block + LogHeader + j * EntryBytes;
    d.badPage = le64(e);
    d.badBank = e[12];
    d.badEntryCrc = le32(e + 8);
  };
  uint64_t gen = 0, epoch = 0;
  uint32_t used = 0;
  for (uint32_t i = 0; i < LogBlocks; ++i) {
    const uint32_t physical = uint32_t((d.head + i) % LogBlocks);
    if (!ops.read(Overlay::Log + physical, 1, w.block)) {
      d.fault = Fault::Io;
      d.rec = physical;
      d.ring = i;
      d.lba = Overlay::Log + physical;
      return;
    }
    ++d.read;
    Rec r{};
    Fault why = Fault::None;
    uint32_t entry = UINT32_MAX;
    const auto st = record(w.block, physical, seed, r, why, entry);
    if (st == RecordState::Invalid) {
      d.fault = why;
      setRec(physical, i, r);
      if (entry != UINT32_MAX) setEntry(entry);
      d.lba = Overlay::Log + physical;
      return;
    }
    if (st == RecordState::Corrupt) {
      // Disposable never tolerates a corrupt tail record.
      d.fault = Fault::LogCrc;
      setRec(physical, i, r);
      d.lba = Overlay::Log + physical;
      return;
    }
    if (st != RecordState::Valid) continue;
    if (r.gen - r.epoch != uint64_t(i) + 1) {
      d.fault = Fault::Sequence;
      setRec(physical, i, r);
      d.lba = Overlay::Log + physical;
      return;
    }
    if (r.epoch < epoch) {
      if (r.gen > epoch) {
        d.fault = Fault::Epoch;
        setRec(physical, i, r);
        d.lba = Overlay::Log + physical;
        return;
      }
      continue;
    }
    if (r.epoch != epoch || i != used || gen == UINT64_MAX || r.gen != gen + 1) {
      d.fault = Fault::Chain;
      setRec(physical, i, r);
      d.lba = Overlay::Log + physical;
      return;
    }
    for (uint32_t j = 0; j < r.count; ++j) {
      const auto *e = w.block + LogHeader + j * EntryBytes;
      const auto page = le64(e);
      const bool bank = e[12] != 0;
      const bool target = bit(present, page) && !bit(active, page);
      if (bank != target) {
        d.fault = Fault::BankTarget;
        setRec(physical, i, r);
        setEntry(j);
        d.lba = dataLba(bank, page);
        return;
      }
      if (!bit(present, page)) ++d.present;
      set(present, page, true);
      set(active, page, bank);
    }
    gen = r.gen;
    ++used;
  }
  d.records = used;

  memset(seen.bits, 0, sizeof seen.bits);
  uint32_t refs = 0, pages = 0;
  for (uint32_t n = used; n; --n) {
    const uint32_t physical = uint32_t((d.head + n - 1) % LogBlocks);
    if (!ops.read(Overlay::Log + physical, 1, w.block)) {
      d.fault = Fault::DataIo;
      d.rec = physical;
      d.ring = n - 1;
      d.lba = Overlay::Log + physical;
      d.refs = refs;
      d.pages = pages;
      return;
    }
    ++d.read;
    Rec r{};
    Fault why = Fault::None;
    uint32_t entry = UINT32_MAX;
    const auto st = record(w.block, physical, seed, r, why, entry);
    if (st == RecordState::Empty) {
      // A used slot must still contain its record on the reverse read. Treat
      // the all-zero re-read as a refusal, never as a successful end.
      d.fault = Fault::LogEmpty;
      setRec(physical, n - 1, r);
      d.lba = Overlay::Log + physical;
      d.refs = refs;
      d.pages = pages;
      return;
    }
    if (st != RecordState::Valid) {
      d.fault = st == RecordState::Corrupt ? Fault::LogCrc : why;
      setRec(physical, n - 1, r);
      if (entry != UINT32_MAX) setEntry(entry);
      d.lba = Overlay::Log + physical;
      d.refs = refs;
      d.pages = pages;
      return;
    }
    if (r.epoch != epoch || r.gen - r.epoch != n) {
      d.fault = Fault::Chain;
      setRec(physical, n - 1, r);
      d.lba = Overlay::Log + physical;
      d.refs = refs;
      d.pages = pages;
      return;
    }
    for (uint32_t j = 0; j < r.count; ++j) {
      const auto *e = w.block + LogHeader + j * EntryBytes;
      const auto page = le64(e);
      if (bit(seen.bits, page)) continue;
      ++refs;
      if (!ops.read(dataLba(e[12], page), 1, w.data)) {
        d.fault = Fault::DataIo;
        setRec(physical, n - 1, r);
        setEntry(j);
        d.lba = dataLba(e[12], page);
        d.refs = refs;
        d.pages = pages;
        return;
      }
      ++d.read;
      const uint32_t dataCrc = crc(w.data, Block);
      if (dataCrc != le32(e + 8)) {
        d.fault = Fault::DataCrc;
        setRec(physical, n - 1, r);
        setEntry(j);
        d.badDataCrc = dataCrc;
        d.lba = dataLba(e[12], page);
        d.refs = refs;
        d.pages = pages;
        return;
      }
      ++pages;
      set(seen.bits, page, true);
    }
  }
  d.refs = refs;
  d.pages = pages;
  d.fault = Fault::None;
}

inline const char *anchorName(Anchor a) {
  switch (a) {
    case Anchor::Unknown: return "UNKNOWN";
    case Anchor::Zero: return "ZERO";
    case Anchor::Exact: return "EXACT-SB0";
    case Anchor::Other: return "OTHER";
  }
  return "?";
}
inline const char *headerName(Header h) {
  switch (h) {
    case Header::Unknown: return "UNKNOWN";
    case Header::Empty: return "EMPTY";
    case Header::Valid: return "VALID";
    case Header::Damaged: return "DAMAGED";
    case Header::Foreign: return "FOREIGN";
  }
  return "?";
}
inline const char *faultName(Fault f) {
  switch (f) {
    case Fault::None: return "NONE";
    case Fault::Seed: return "SEED";
    case Fault::Guard: return "GUARD";
    case Fault::Geometry: return "GEOMETRY";
    case Fault::Gpt: return "GPT";
    case Fault::Io: return "IO";
    case Fault::Sb0Empty: return "SB0-EMPTY";
    case Fault::Sb0Damaged: return "SB0-DAMAGED";
    case Fault::Sb0Foreign: return "SB0-FOREIGN";
    case Fault::Sb1Present: return "SB1-PRESENT";
    case Fault::Sb1Damaged: return "SB1-DAMAGED";
    case Fault::Sb1Foreign: return "SB1-FOREIGN";
    case Fault::NotInitial: return "NOT-INITIAL";
    case Fault::BothValid: return "BOTH-VALID";
    case Fault::MapCrc: return "MAP-CRC";
    case Fault::MapActive: return "MAP-ACTIVE";
    case Fault::MapCount: return "MAP-COUNT";
    case Fault::LogCrc: return "LOG-CRC";
    case Fault::LogEmpty: return "LOG-EMPTY";
    case Fault::LogFormat: return "LOG-FORMAT";
    case Fault::LogGeneration: return "LOG-GEN";
    case Fault::LogTail: return "LOG-TAIL";
    case Fault::EntryRange: return "ENTRY-RANGE";
    case Fault::EntryBank: return "ENTRY-BANK";
    case Fault::EntryDuplicate: return "ENTRY-DUP";
    case Fault::Sequence: return "SEQ";
    case Fault::Epoch: return "EPOCH";
    case Fault::Chain: return "CHAIN";
    case Fault::BankTarget: return "BANK-MISMATCH";
    case Fault::DataIo: return "DATA-IO";
    case Fault::DataCrc: return "DATA-CRC";
  }
  return "?";
}

// One logical line; split before REASON= only when the 80-column scale-3
// budget would be exceeded. Every field is retained.
inline unsigned summary(const Diagnosis &d, char lines[2][96]) {
  char rec[12];
  if (d.rec == UINT32_MAX) snprintf(rec, sizeof rec, "-");
  else snprintf(rec, sizeof rec, "%u", d.rec);
  const char *hdr = d.sb0 == Header::Unknown ? "UNKNOWN"
                  : d.sb0Valid ? "1" : "0";
  char all[176];
  snprintf(all, sizeof all,
           "NUWA SB0-R2 ANCHOR=%s HDR=%s REC=%s REASON=%s PAGES=%u WRITES=0",
           anchorName(d.anchor), hdr, rec, faultName(d.fault), d.pages);
  const size_t n = strlen(all);
  if (n <= 80) {
    memcpy(lines[0], all, n + 1);
    lines[1][0] = 0;
    return 1;
  }
  size_t split = SIZE_MAX;
  for (size_t i = 0; i + 8 <= n; ++i)
    if (!memcmp(all + i, " REASON=", 8)) { split = i; break; }
  if (split != SIZE_MAX) {
    memcpy(lines[0], all, split);
    lines[0][split] = 0;
    snprintf(lines[1], 96, "%s", all + split + 1);
    return 2;
  }
  memcpy(lines[0], all, 80);
  lines[0][80] = 0;
  snprintf(lines[1], 96, "%s", all + 80);
  return 2;
}

// Bounded detail rows for the stop screen. Every value comes from the same
// read-only pass; this does not re-read or infer media state.
inline unsigned detail(const Diagnosis &d, char lines[][128], unsigned room) {
  unsigned n = 0;
  char hex[33];
  for (unsigned i = 0; i < 16; ++i) snprintf(hex + 2 * i, 3, "%02x", d.anchor16[i]);
  auto num = [](char *buf, size_t cap, uint32_t v) {
    if (v == UINT32_MAX) snprintf(buf, cap, "-");
    else snprintf(buf, cap, "%u", v);
  };
  char rec[12], ring[12], entry[12];
  num(rec, sizeof rec, d.rec);
  num(ring, sizeof ring, d.ring);
  num(entry, sizeof entry, d.entry);
  const char *hdr = d.sb0 == Header::Unknown ? "UNKNOWN"
                  : d.sb0Valid ? "1" : "0";
  char slot[12];
  if (d.sb0 == Header::Unknown) snprintf(slot, sizeof slot, "?");
  else snprintf(slot, sizeof slot, "%u", d.slot);
  if (n < room)
    snprintf(lines[n++], 128, "ANCHOR16=%s", hex);
  if (n < room) {
    if (d.sb0 == Header::Valid)
      snprintf(lines[n++], 128,
               "SB0=%s SB1=%s HDR=%s SLOT=%s GEN=%llu HEAD=%u COUNT=%llu MAPCRC=%08x",
               headerName(d.sb0), headerName(d.sb1), hdr, slot,
               (unsigned long long)d.gen, d.head, (unsigned long long)d.count, d.mapCrc);
    else
      snprintf(lines[n++], 128,
               "SB0=%s SB1=%s HDR=%s SLOT=%s GEN=? HEAD=? COUNT=? MAPCRC=?",
               headerName(d.sb0), headerName(d.sb1), hdr, slot);
  }
  if (n < room) {
    if (d.mapRead)
      snprintf(lines[n++], 128, "MAP PRESENT=%u RECORDS=%u REFS=%u PAGES=%u READ=%u",
               d.present, d.records, d.refs, d.pages, d.read);
    else
      snprintf(lines[n++], 128, "MAP PRESENT=? RECORDS=? REFS=? PAGES=? READ=%u", d.read);
  }
  if (n < room)
    snprintf(lines[n++], 128, "FAULT=%s REC=%s RING=%s ENTRY=%s LBA=%llu",
             faultName(d.fault), rec, ring, entry, (unsigned long long)d.lba);
  if (n < room && d.rec != UINT32_MAX)
    snprintf(lines[n++], 128, "RECORD GEN=%llu EPOCH=%llu N=%u",
             (unsigned long long)d.badGen, (unsigned long long)d.badEpoch, d.badCount);
  if (n < room && d.rec != UINT32_MAX)
    snprintf(lines[n++], 128, "ENTRY PAGE=%llu BANK=%u ECRC=%08x DCRC=%08x",
             (unsigned long long)d.badPage, d.badBank, d.badEntryCrc, d.badDataCrc);
  if (n < room && d.why)
    snprintf(lines[n++], 128, "NOTE=%s", d.why);
  return n;
}
} // namespace NuwaData::Sb0R2
