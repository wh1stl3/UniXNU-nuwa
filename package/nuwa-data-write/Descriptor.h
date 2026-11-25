#pragma once
#include <stdint.h>

namespace NuwaUfsDesc {
constexpr unsigned MaxBytes = 255, MaxLuns = 32;
constexpr uint8_t ModeCdb[] = {0x5a, 0x08, 0x08, 0, 0, 0, 0, 0, 0x40, 0};
constexpr unsigned ModeBytes = ModeCdb[8];
struct Request {
  unsigned type = 0, index = 0;
  constexpr bool valid() const {
    return (type == 0 && index == 0) || (type == 2 && index < MaxLuns);
  }
};
enum class Reply { Good, Rejected, Unowned };

inline bool encode(Request q, uint8_t *u) {
  if (!q.valid()) return false;
  u[0] = 0x16;
  u[5] = 1;
  u[12] = 1; // READ_DESC, not WRITE_DESC.
  u[13] = uint8_t(q.type);
  u[14] = uint8_t(q.index);
  u[19] = MaxBytes;
  return true;
}

// Generic type/LUN/tag/EHS and transport ownership have already been checked.
inline Reply response(Request q, const volatile uint8_t *r, unsigned dl) {
  if (!q.valid() || r[1] || r[5] != 1 || r[7] || r[12] != 1 ||
      r[13] != q.type || r[14] != q.index || r[15] || r[16] || r[17])
    return Reply::Unowned;
  const unsigned length = unsigned(r[18]) << 8 | r[19];
  if (length > MaxBytes) return Reply::Unowned;
  if (r[6]) {
    // Whitelist documented read-query rejections with no descriptor payload.
    switch (r[6]) {
      case 0xf6: case 0xf9: case 0xfa: case 0xfb:
      case 0xfc: case 0xfd: case 0xfe: case 0xff:
        return dl ? Reply::Unowned : Reply::Rejected;
      default: return Reply::Unowned;
    }
  }
  if (dl != length || length < 2 || r[32] != length || r[33] != q.type)
    return Reply::Unowned;
  return Reply::Good;
}

enum class Status : unsigned {
  Ok, Invalid, NotReady, CommandError, Unowned, Timeout, Malformed, Incomplete
};
struct Result {
  Status status;
  unsigned bytes = 0, code = 0;
};
enum class Bit : unsigned { Unknown, Clear, Set };
struct Mode {
  Result result{Status::NotReady};
  Bit dpofua = Bit::Unknown, wce = Bit::Unknown;
};

inline Mode parseMode(const uint8_t *p, unsigned n) {
  const Mode bad{{Status::Malformed}};
  if (n < 8 || n > ModeBytes) return bad;
  const unsigned end = (unsigned(p[0]) << 8 | p[1]) + 2;
  const unsigned start = 8 + (unsigned(p[6]) << 8 | p[7]);
  if (start > end || end > n) return bad;
  Mode mode{{Status::Ok, n}, p[3] & 0x10 ? Bit::Set : Bit::Clear};
  for (unsigned i = start; i < end;) {
    if (end - i < 2) return bad;
    const bool subpage = p[i] & 0x40;
    if (subpage && end - i < 4) return bad;
    const unsigned length = subpage ? 4 + (unsigned(p[i + 2]) << 8 | p[i + 3]) : 2 + p[i + 1];
    if (length > end - i) return bad;
    if (!subpage && (p[i] & 0x3f) == 8) {
      if (length < 3 || mode.wce != Bit::Unknown) return bad;
      mode.wce = p[i + 2] & 4 ? Bit::Set : Bit::Clear;
    }
    i += length;
  }
  return mode;
}
struct Unit {
  bool enabled = false;
  unsigned wp = 0, blockSize = 0;
  uint64_t blocks = 0;
};
struct Snapshot {
  Result result{Status::NotReady};
  unsigned lus = 0, bootEnable = 0, manufacturer = 0;
  uint32_t wp = 0;
  Unit units[MaxLuns]{};
};
inline bool parseUnit(const uint8_t *p, unsigned n, unsigned index, Unit &u) {
  if (n < 0x13 || p[2] != index || p[3] > 1 || p[5] > 2) return false;
  if (!p[3]) return true;
  if (p[0xa] < 9 || p[0xa] > 31) return false;
  u.enabled = true;
  u.wp = p[5];
  u.blockSize = 1U << p[0xa];
  for (unsigned i = 0xb; i < 0x13; ++i) u.blocks = (u.blocks << 8) | p[i];
  return u.blocks != 0;
}

template<class Port>
static void collect(Port &p, Snapshot &out) {
  uint8_t buf[MaxBytes];
  out.result = p.read_descriptor(0, 0, buf);
  if (out.result.status != Status::Ok) return;
  if (out.result.bytes < 0x1a || !buf[6] || buf[6] > MaxLuns || buf[8] > 1) {
    out.result = {Status::Malformed};
    return;
  }
  out.lus = buf[6];
  out.bootEnable = buf[8];
  out.manufacturer = unsigned(buf[0x18]) << 8 | buf[0x19];
  unsigned found = 0;
  for (unsigned i = 0; i < MaxLuns && found < out.lus; ++i) {
    const auto result = p.read_descriptor(2, i, buf);
    if (result.status == Status::CommandError && result.code == 0xfc) continue;
    if (result.status != Status::Ok) { out.result = result; return; }
    auto &unit = out.units[i];
    if (!parseUnit(buf, result.bytes, i, unit)) {
      out.result = {Status::Malformed};
      return;
    }
    if (unit.enabled) {
      ++found;
      if (unit.wp) out.wp |= uint32_t(1) << i;
    }
  }
  out.result = {found == out.lus ? Status::Ok : Status::Incomplete};
}
}
