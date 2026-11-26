// SPDX-License-Identifier: BSD-2-Clause
#pragma once
#include "DisposableData.h"
#include "Sb0CandidateInput.h" // Generated from the pinned generator output.

namespace NuwaData::Sb0 {
constexpr uint64_t First = Disposable::Overlay::Media.first;
constexpr uint64_t Remote = First + Disposable::Overlay::LegacyHeader1;
constexpr unsigned Pages = Disposable::Overlay::Data0;
static_assert(First == 57393401 && Pages == 770 && Remote == 59491258);

enum class Result { Blank, Exact, Mismatch, Io, Geometry, Gpt, Seed, Unbound, Good, Unknown, Guard };
static const char *resultName(unsigned result) {
  const char *names[] = {"BLANK", "EXACT-SB0", "MISMATCH", "IO-FAIL", "GEOMETRY",
                         "GPT-FAIL", "SEED-FAIL", "AUTH-UNBOUND", "GOOD-NON-DURABLE",
                         "UNKNOWN-NO-RETRY", "GUARD"};
  return names[result];
}

// Only the WX image owns an instance, accessed under the retained host lock.
// Neither admitting a write nor consuming it is reusable within this boot.
class BootWriteOnce {
  enum State { Fresh, Prepared, Spent } state = Fresh;
public:
  bool begin() {
    if (state != Fresh) return false;
    state = Prepared;
    return true;
  }
  bool consume() {
    if (state != Prepared) return false;
    state = Spent;
    return true;
  }
  bool spent() const { return state == Spent; }
};

struct Report {
  Result result;
  uint64_t lba = 0;
  unsigned pages = 0;
};

inline bool zero(const uint8_t *page) {
  for (unsigned i = 0; i < Block; ++i) if (page[i]) return false;
  return true;
}

template<class Port>
static Report scan(Port &p, bool write, uint8_t *page) {
  Report out{Result::Blank};
  for (unsigned i = 0; i < Pages; ++i) {
    const auto lba = First + i;
    if (!p.read(lba, page)) return {Result::Io, lba, i};
    ++out.pages;
    if (zero(page)) continue;
    if (!write && i == 0 && !memcmp(page, Payload, Block))
      out.result = Result::Exact;
    else if (out.result != Result::Mismatch) {
      out.result = Result::Mismatch;
      out.lba = lba;
    }
  }
  if (!write || out.result != Result::Blank) return out;
  if (!p.read(Remote, page)) return {Result::Io, Remote, out.pages};
  if (!zero(page)) return {Result::Mismatch, Remote, out.pages};
  return out;
}

// Read back the staged wire image, not a second encoding or just the request.
// The caller must already hold the retained lock and the post-prepare guard.
template<class Consume>
static bool checkAndConsume(const uint8_t *v, uint64_t pa, unsigned tag,
                            unsigned block, uint64_t lba, unsigned count,
                            const uint8_t *src, Consume consume) {
  const auto *w = reinterpret_cast<const uint32_t *>(v);
  const auto *p = reinterpret_cast<const uint32_t *>(v + 5120);
  const auto *u = v + 4096;
  constexpr uint8_t cdb[16] = {0x2a, 0, uint8_t(First >> 24), uint8_t(First >> 16),
                              uint8_t(First >> 8), uint8_t(First), 0, 0, 1, 0};
  return lba == First && count == 1 && block == Block && src &&
         w[0] == 0x12000000U && !w[1] && w[2] == 15 && !w[3] &&
         w[4] == uint32_t(pa + 4096) && w[5] == uint32_t((pa + 4096) >> 32) &&
         w[6] == (128 | (128U << 16)) && w[7] == ((256U << 16) | 1) &&
         p[0] == uint32_t(pa + 16384) && p[1] == uint32_t((pa + 16384) >> 32) &&
         !p[2] && p[3] == Block - 1 &&
         u[0] == 1 && u[1] == 0x20 && u[2] == 0 && u[3] == tag &&
         !u[4] && !u[5] && !u[6] && !u[7] && !u[8] && !u[9] &&
         !u[10] && !u[11] && !u[12] && !u[13] && u[14] == 0x10 && !u[15] &&
         !memcmp(u + 16, cdb, sizeof cdb) && !memcmp(src, Payload, Block) &&
         !memcmp(v + 16384, Payload, Block) && consume();
}
} // namespace NuwaData::Sb0
