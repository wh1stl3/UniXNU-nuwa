// SPDX-License-Identifier: BSD-2-Clause
#pragma once
#include "DualBankLogOverlay.h"

namespace NuwaData::Disposable {
using Overlay = DualBankLogOverlay<512, true>;
constexpr uint64_t RootBytes = 8446279680ULL;
constexpr uint64_t Reserve = 262144;
// Logical SHNGSEED2 identity, not the FAT file SHA-256 or raw-image SHA-256.
constexpr uint8_t Seed[32] = {
  0xa1, 0x06, 0xb0, 0xce, 0x02, 0x67, 0x71, 0xe2, 0x21, 0xf5, 0x78, 0x12, 0x5e, 0x10, 0x4a, 0x48,
  0x54, 0xc2, 0xcb, 0xcd, 0xa7, 0xc1, 0xb8, 0x39, 0x0f, 0x6e, 0x05, 0x6a, 0x47, 0xc6, 0x37, 0x43,
};
static_assert(Overlay::Media.first == 57393401 &&
              Overlay::Media.first + Overlay::Media.blocks == 61588475);
inline bool seedMatches(const uint8_t *seed) { return !memcmp(Seed, seed, sizeof Seed); }
}
