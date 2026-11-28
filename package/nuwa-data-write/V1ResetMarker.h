// SPDX-License-Identifier: BSD-2-Clause
#pragma once
#include <stddef.h>
#include <stdint.h>
#include <string.h>

// The pinned v1 encoder zeros its entire 4 KiB header and uses only bytes
// [0,64). Any nonzero byte in this reserved range is fail-closed on daily.
// This is a software transaction marker, not a media durability guarantee.
namespace NuwaData::V1ResetMarker {
constexpr size_t Offset = 64, Bytes = 32;
inline bool present(const uint8_t *block) {
  for (size_t i = 0; i < Bytes; ++i) if (block[Offset + i]) return true;
  return false;
}
inline void set(uint8_t *block) {
  memset(block + Offset, 0xa5, Bytes);
  memcpy(block + Offset, "NUWARST1", 8);
}
inline void clear(uint8_t *block) { memset(block + Offset, 0, Bytes); }
}
