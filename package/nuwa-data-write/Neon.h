#pragma once
#include "Descriptor.h"
#include "DualBankLogOverlay.h"

namespace NuwaNeon {
using namespace NuwaData;
using Overlay = DualBankLogOverlay<>;
constexpr char Identity[] = "IO cid=N261126A";
constexpr unsigned Rows = 6, Cols = 66;
struct Hc {
  unsigned seen = 0;
  uint32_t value[6]{};
  uint32_t record(unsigned i, uint32_t v) {
    value[i] = v;
    seen |= 1U << i;
    return v;
  }
};
enum class Check : unsigned { Unknown, Ok, Bad };
inline const char *text(Check c) {
  return c == Check::Ok ? "ok" : c == Check::Bad ? "bad" : "unk";
}
struct Descriptors {
  NuwaUfsDesc::Result device{NuwaUfsDesc::Status::NotReady}, unit = device;
  uint8_t dev[NuwaUfsDesc::MaxBytes]{}, lu0[NuwaUfsDesc::MaxBytes]{};
  uint64_t blocks = 0, rcBlocks = 0;
  unsigned rcBlock = 0;
  Check capacity = Check::Unknown;
  NuwaUfsDesc::Mode mode;
};
template<class Port>
void descriptors(Port &port, Descriptors &out, uint64_t blocks, unsigned block) {
  using NuwaUfsDesc::Status;
  out.rcBlocks = blocks;
  out.rcBlock = block;
  out.device = port.read_descriptor(0, 0, out.dev);
  if (!port.ready()) return;
  out.unit = port.read_descriptor(2, 0, out.lu0);
  if (out.unit.status == Status::Ok) {
    NuwaUfsDesc::Unit unit;
    if (!NuwaUfsDesc::parseUnit(out.lu0, out.unit.bytes, 0, unit))
      out.unit.status = Status::Malformed;
    else {
      out.blocks = unit.blocks;
      out.capacity = unit.enabled && unit.blocks == blocks && unit.blockSize == block
                     ? Check::Ok : Check::Bad;
    }
  }
  if (port.ready()) out.mode = port.modeSense();
}

constexpr uint64_t Anchors[] = {0, 1, Overlay::LegacyHeader0, Overlay::LegacyHeader1};
constexpr uint64_t Metadata[] = {
  Overlay::Map0, Overlay::Map0 + Overlay::MapBlocks - 1,
  Overlay::Map0 + Overlay::MapBlocks, Overlay::Map1 - 1,
  Overlay::Map1, Overlay::Map1 + Overlay::MapBlocks - 1,
  Overlay::Map1 + Overlay::MapBlocks, Overlay::Log - 1,
  Overlay::Log, Overlay::Log + Overlay::LogBlocks - 1,
};
struct Media {
  Check primary = Check::Unknown, backup = Check::Unknown, agree = Check::Unknown;
  Check place = Check::Unknown;
  unsigned anchorsRead = 0, anchorsNonzero = 0, samples = 0, nonzero = 0;
};

// Read is exactly one retained LUN0 4 KiB READ(10), with attribution checked
// by the caller. No reads in the proposed window until both GPTs and placement.
template<class Read>
void media(Read read, const GptIdentity &id, uint64_t image, uint64_t reserve,
           Window w, GptBuffers &g, Media &out) {
  if (!read(1, g.ph) || !read(2, g.pe)) return;
  const GptCopy primary{1, 2, g.ph, g.pe};
  out.primary = gptCopy(primary, id, false) ? Check::Ok : Check::Bad;
  if (!read(id.capacity - 1, g.bh)) return;
  const uint64_t be = le64(g.bh + 72);
  if (be <= id.lastUsable || be >= id.capacity - 1) {
    out.backup = Check::Bad;
    return;
  }
  if (!read(be, g.be)) return;
  const GptCopy backup{id.capacity - 1, be, g.bh, g.be};
  out.backup = gptCopy(backup, id, true) ? Check::Ok : Check::Bad;
  if (out.primary != Check::Ok || out.backup != Check::Ok) return;
  out.agree = gpt(0, Block, id, primary, backup) ? Check::Ok : Check::Bad;
  if (out.agree != Check::Ok) return;
  const bool fits = w.first == Overlay::Media.first && w.blocks == Overlay::Media.blocks &&
                    placement(id, image, reserve, w);
  out.place = fits ? Check::Ok : Check::Bad;
  if (!fits) return;
  for (unsigned i = 0; i < sizeof Anchors / sizeof Anchors[0]; ++i) {
    if (!read(w.first + Anchors[i], g.ph)) return;
    ++out.anchorsRead;
    if (!zero(g.ph, Block)) out.anchorsNonzero |= 1U << i;
  }
  for (const auto offset : Metadata) {
    if (!read(w.first + offset, g.ph)) return;
    ++out.samples;
    if (!zero(g.ph, Block)) ++out.nonzero;
  }
}
}
