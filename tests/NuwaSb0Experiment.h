#pragma once
#include "../package/nuwa-data-write/DualBankLogOverlay.h"
#include "../package/nuwa-data-write/Provider.h"

// This entry only exists in the explicitly enabled host fixture. None of the
// supplied facts constitute firmware, backup, or hardware qualification.
namespace NuwaSb0Fixture {
using namespace NuwaData;
using Overlay = DualBankLogOverlay<>;
constexpr uint64_t RootBytes = 8446279680ULL, Reserve = 262144;
struct Request {
  unsigned arg = 0, lun = 0, block = Block;
  uint64_t rootBytes = RootBytes, reserve = Reserve;
  Window window = Overlay::Media;
  uint8_t seed[32]{};
};
struct MockBinding {
  bool windowOwned = false, backupRestorable = false;
  uint8_t backupSeed[32]{};
};
enum class Result { Disabled, Used, Binding, Geometry, Gpt, ReadError, Nonempty,
                    NotCompleted, CommandCompleted };

class Trial {
  bool used_ = false;
public:
  template<bool HostEnabled, class Port>
  Result runLocked(Port &port, Slot &slot, const Request &r, const MockBinding &mock,
                   const GptIdentity &id, GptBuffers &g, Overlay::Workspace &w) {
    if (!HostEnabled || r.arg != 1) return Result::Disabled;
    if (used_) return Result::Used;
    used_ = true;
    if (!mock.windowOwned || !mock.backupRestorable ||
        zero(r.seed, sizeof r.seed) || memcmp(r.seed, mock.backupSeed, sizeof r.seed))
      return Result::Binding;
    if (!port.readyLocked() || !slot.dataAllowed(true) || r.lun != 0 ||
        r.block != Block || port.blockSizeLocked() != r.block ||
        id.capacity < 4 || port.capacityLocked() != id.capacity ||
        r.rootBytes != RootBytes || r.reserve != Reserve ||
        r.window.first != Overlay::Media.first || r.window.blocks != Overlay::Media.blocks ||
        !placement(id, r.rootBytes, r.reserve, r.window)) return Result::Geometry;

    const auto read = [&](uint64_t lba, void *dst) {
      if (port.readPageLocked(lba, dst)) return true;
      port.quarantineLocked();
      return false;
    };
    if (!read(1, g.ph) || !read(2, g.pe) || !read(id.capacity - 1, g.bh)) return Result::ReadError;
    const uint64_t backup = le64(g.bh + 72);
    if (backup <= id.lastUsable || backup >= id.capacity - 1) return Result::Gpt;
    if (!read(backup, g.be)) return Result::ReadError;
    if (!gpt(r.lun, r.block, id, {1, 2, g.ph, g.pe}, {id.capacity - 1, backup, g.bh, g.be}))
      return Result::Gpt;

    enum class Probe { Clear, ReadError, Nonempty };
    const auto check = [&](uint64_t rel) {
      if (!read(r.window.first + rel, w.data)) return Probe::ReadError;
      return zero(w.data, Block) ? Probe::Clear : Probe::Nonempty;
    };
    // SB0/SB1, both pairs of maps, the entire ring, and legacy anchors.
    for (uint64_t rel = 0; rel < Overlay::Data0; ++rel) {
      const auto result = check(rel);
      if (result != Probe::Clear)
        return result == Probe::ReadError ? Result::ReadError : Result::Nonempty;
    }
    // LegacyHeader0 is inside today's ring and was checked in the scan.
    static_assert(Overlay::LegacyHeader0 < Overlay::Data0 &&
                  Overlay::LegacyHeader1 >= Overlay::Data0 &&
                  Overlay::LegacyHeader1 < Overlay::Media.blocks);
    const auto legacy = check(Overlay::LegacyHeader1);
    if (legacy != Probe::Clear)
      return legacy == Probe::ReadError ? Result::ReadError : Result::Nonempty;

    memset(w.maps, 0, sizeof w.maps);
    if (!Overlay::initialSuperblock(w.block, r.seed, w) ||
        !slot.submit(port.readyLocked(), port.ownershipLocked())) return Result::NotCompleted;
    const auto completion = port.writePageLocked(r.lun, r.window, r.window.first, 1, w.block);
    // FullFua is the shared transport's name for attributed full completion
    // of a command carrying FUA; this experiment exposes no sync or durability.
    return slot.complete(completion) ? Result::CommandCompleted : Result::NotCompleted;
  }
};
}
