// SPDX-License-Identifier: BSD-2-Clause
// Window predicate and WRITE(10) encoding adapted from UniXNU/ShengUfs
// f020bd693c34790c04e97c52720af3cd842336fb, RootCommands.h.
#pragma once
#include <stddef.h>
#include <stdint.h>
#include <string.h>

namespace NuwaData {
constexpr uint32_t Block = 4096;
constexpr uint64_t Guard = 1024;

struct Window {
  uint64_t first, blocks;
  bool contains(unsigned lun, unsigned block, uint64_t lba, uint64_t count) const {
    return lun == 0 && block == Block && first <= UINT32_MAX && blocks &&
           blocks - 1 <= UINT32_MAX - first && lba >= first &&
           lba - first < blocks && count && count <= blocks - (lba - first);
  }
};

// Exactly one 4 KiB LBA, FUA mandatory. Caller must validate the window
// under the shared transport lock before preparing anything in shared DMA.
inline void write10(uint8_t (&cdb)[10], uint32_t lba) {
  const uint8_t wire[10] = {0x2a, 0x08, uint8_t(lba >> 24), uint8_t(lba >> 16),
                            uint8_t(lba >> 8), uint8_t(lba), 0, 0, 1, 0};
  memcpy(cdb, wire, sizeof(wire));
}

enum class State {
  IDLE, SUBMITTED, COMPLETED_OK, COMPLETED_CMDERR, TIMEOUT_ORPHAN,
  FATAL_QUARANTINED
};
enum class Evidence { ReadOk, FullFua, AttributedCommandError, Timeout, Unowned };

// Evidence for a NEW firmware/transport domain, never a transition of the
// old Slot. Each fact must refer to the same new domain and expected media.
struct ColdStartIdentity {
  uint64_t boot_session_id = 0, domain_id = 0, media_id = 0;
  constexpr bool matches(ColdStartIdentity expected) const {
    return boot_session_id && domain_id && media_id &&
           boot_session_id == expected.boot_session_id &&
           domain_id == expected.domain_id && media_id == expected.media_id;
  }
};
struct ColdStartFact {
  ColdStartIdentity source{};
  bool verified = false;
  constexpr bool validFor(ColdStartIdentity expected) const {
    return verified && source.matches(expected);
  }
};
struct ColdStartEvidence {
  ColdStartFact firmwareReinitialized, oldDmaExcluded;
  ColdStartFact lunMatches, primaryGptMatches, backupGptMatches;
  ColdStartFact windowMatches, knownRootMatches, overlayGenerationMatches;
  // expected must come independently from the current session/domain and
  // requested media, never be copied from the submitted evidence.
  constexpr bool qualified(ColdStartIdentity expected) const {
    return firmwareReinitialized.validFor(expected) && oldDmaExcluded.validFor(expected) &&
           lunMatches.validFor(expected) && primaryGptMatches.validFor(expected) &&
           backupGptMatches.validFor(expected) && windowMatches.validFor(expected) &&
           knownRootMatches.validFor(expected) && overlayGenerationMatches.validFor(expected);
  }
};

// All access, including sync and root submission admission, requires the
// same host lock. No method touches DMA or acknowledges controller state.
class Slot {
  State state_ = State::IDLE;
  bool writeError_ = false;
  bool writing_ = false;
  bool submitCommand(bool ready, bool owned, bool writing) {
    if (!ready || !rootAllowed() || (writing && writeError_)) return false;
    if (!owned) { quarantine(); return false; }
    writing_ = writing;
    state_ = State::SUBMITTED;
    return true;
  }
public:
  constexpr Slot() = default;
  // Host model of a successor to a quarantined domain. The ordinary initial
  // read-only session does not certify a cold restart or enable Data writes.
  explicit constexpr Slot(ColdStartIdentity expected, ColdStartEvidence boot)
      : state_(boot.qualified(expected) ? State::IDLE : State::FATAL_QUARANTINED),
        writeError_(!boot.qualified(expected)) {}
  Slot(const Slot &) = delete;
  Slot &operator=(const Slot &) = delete;
  State state() const { return state_; }
  bool rootAllowed() const {
    return state_ == State::IDLE || state_ == State::COMPLETED_OK ||
           state_ == State::COMPLETED_CMDERR;
  }
  bool dataAllowed(bool ready) const { return ready && rootAllowed() && !writeError_; }
  void quarantine() {
    writeError_ = true;
    // Neither a late response nor a second fault can reclaim an orphan.
    if (state_ != State::TIMEOUT_ORPHAN) state_ = State::FATAL_QUARANTINED;
  }
  bool submit(bool ready, bool owned) {
    return submitCommand(ready, owned, true);
  }
  bool submitRead(bool ready, bool owned) { return submitCommand(ready, owned, false); }
  bool complete(Evidence evidence) {
    if (state_ != State::SUBMITTED) return false; // stale or late evidence
    switch (evidence) {
      case Evidence::ReadOk:
      case Evidence::FullFua:
        if (writing_ != (evidence == Evidence::FullFua)) { quarantine(); return false; }
        state_ = State::COMPLETED_OK;
        return true;
      case Evidence::AttributedCommandError: // Returned slot, attributed SCSI error.
        state_ = State::COMPLETED_CMDERR;
        break;
      case Evidence::Timeout: // No proof the controller stopped accessing DMA.
        state_ = State::TIMEOUT_ORPHAN;
        break;
      case Evidence::Unowned: // Fatal status, invalid response, or uncertain ownership.
        quarantine();
        break;
    }
    writeError_ = true;
    return false;
  }
};

inline uint32_t le32(const uint8_t *p) {
  return p[0] | uint32_t(p[1]) << 8 | uint32_t(p[2]) << 16 | uint32_t(p[3]) << 24;
}
inline uint64_t le64(const uint8_t *p) { return le32(p) | uint64_t(le32(p + 4)) << 32; }
inline bool zero(const uint8_t *p, size_t bytes) {
  for (size_t i = 0; i < bytes; ++i) if (p[i]) return false;
  return true;
}
inline uint32_t crc(const uint8_t *p, size_t bytes, size_t clearAt = SIZE_MAX) {
  uint32_t c = ~uint32_t(0);
  for (size_t i = 0; i < bytes; ++i) {
    c ^= i >= clearAt && i - clearAt < 4 ? 0 : p[i];
    for (unsigned bit = 0; bit < 8; ++bit) c = (c >> 1) ^ (0xedb88320U & (0U - (c & 1)));
  }
  return ~c;
}

// Fixed single-block entry array (32 * 128 B) of the captured nuwa LUN0.
// The identity input must come from outside the GPT being checked.
struct GptIdentity {
  uint64_t capacity, firstUsable, lastUsable, userdataFirst, userdataLast;
  uint8_t disk[16], type[16], partition[16];
};
struct GptCopy {
  uint64_t headerLba, entriesLba;
  const uint8_t (&header)[Block], (&entries)[Block];
};

inline bool gptCopy(const GptCopy &g, const GptIdentity &id, bool back) {
  const auto *h = g.header;
  const uint64_t last = id.capacity - 1;
  const uint32_t size = le32(h + 12);
  // The backup entry array is one block; it must be outside the usable
  // area, but need not be immediately adjacent to the backup header.
  const uint64_t entries = le64(h + 72);
  return !memcmp(h, "EFI PART", 8) && le32(h + 8) == 0x10000 &&
         size == 92 && !le32(h + 20) &&
         g.headerLba == (back ? last : 1) && le64(h + 24) == g.headerLba &&
         le64(h + 32) == (back ? 1 : last) &&
         le64(h + 40) == id.firstUsable && le64(h + 48) == id.lastUsable &&
         !memcmp(h + 56, id.disk, 16) &&
         entries == g.entriesLba &&
         (back ? entries > id.lastUsable && entries < last : entries == 2) &&
         le32(h + 80) == 32 && le32(h + 84) == 128 &&
         le32(h + 16) == crc(h, size, 16) && le32(h + 88) == crc(g.entries, Block);
}

inline bool gpt(unsigned lun, unsigned block, const GptIdentity &id,
                const GptCopy &primary, const GptCopy &backup) {
  if (lun != 0 || block != Block || id.firstUsable <= 2 ||
      id.firstUsable > id.lastUsable || id.lastUsable >= id.capacity ||
      id.capacity - id.lastUsable < 3 || id.userdataFirst < id.firstUsable ||
      id.userdataFirst > id.userdataLast || id.userdataLast > id.lastUsable ||
      zero(id.disk, 16) || zero(id.type, 16) || zero(id.partition, 16) ||
      !gptCopy(primary, id, false) || !gptCopy(backup, id, true) ||
      memcmp(primary.entries, backup.entries, Block)) return false;
  const uint8_t *e = primary.entries + 31 * 128; // sda32
  constexpr uint8_t name[] = {'u',0,'s',0,'e',0,'r',0,'d',0,'a',0,'t',0,'a',0};
  if (memcmp(e, id.type, 16) || memcmp(e + 16, id.partition, 16) ||
      le64(e + 32) != id.userdataFirst || le64(e + 40) != id.userdataLast ||
      memcmp(e + 56, name, sizeof(name)) || !zero(e + 56 + sizeof(name), 72 - sizeof(name)))
    return false;
  for (unsigned i = 0; i < 31; ++i) {
    const uint8_t *other = primary.entries + i * 128;
    if (zero(other, 16)) continue;
    const uint64_t first = le64(other + 32), last = le64(other + 40);
    if (first < id.firstUsable || first > last || last > id.lastUsable ||
        (first <= id.userdataLast && id.userdataFirst <= last) ||
        !memcmp(other + 16, id.partition, 16)) return false;
  }
  return true;
}

inline bool placement(const GptIdentity &id, uint64_t imageBytes, uint64_t reserve,
                      const Window &w) {
  if (!imageBytes || !reserve || id.userdataFirst > id.userdataLast ||
      id.userdataLast > UINT32_MAX || !w.contains(0, Block, w.first, w.blocks) ||
      w.first < id.userdataFirst || w.first > id.userdataLast) return false;
  const uint64_t image = imageBytes / Block + (imageBytes % Block != 0);
  const uint64_t before = w.first - id.userdataFirst;
  const uint64_t available = id.userdataLast - w.first + 1;
  return before >= Guard && image <= before - Guard &&
         reserve < available && w.blocks == available - reserve;
}
}
