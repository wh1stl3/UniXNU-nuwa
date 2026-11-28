// Included only in the pinned nuwa retained-root provider, after StoreGeometry.
#include "RetainedWrite.inc"
#include "DualBankLogOverlay.h"
struct CandidatePort : RetainedWritePort {
  NuwaData::ReinitAttempt reinit;
  void lock() { IOLockLock(gHost.lock); }
  void unlock() { IOLockUnlock(gHost.lock); }
  bool readyLocked() { return retainedReadyLocked(); }
  bool ownershipLocked() { return retainedOwnershipLocked(); }
  uint64_t capacityLocked() { return combined_state.blocks; }
  unsigned blockSizeLocked() { return combined_state.block; }
  bool isolationArmedLocked() { return true; } // RetainedRead's terminal, shared latch.
  NuwaData::ReinitResult tryReinitLocked() {
    // No proof that old DMA is blocked, or that this domain can survive an
    // HCE/PHY/clock/ICE/link transition. Do not touch hardware after isolation.
    return reinit.beginLocked(retainedSlot, {});
  }
  NuwaData::ColdStartIdentity coldStartIdentityLocked(const NuwaData::GptIdentity &,
                                                     NuwaData::Window) {
    return {}; // No trusted boot/session, domain or media identifier source.
  }
  NuwaData::ColdStartEvidence coldStartEvidenceLocked(const NuwaData::GptIdentity &,
                                                     NuwaData::Window) {
    // No hardware evidence that old DMA is excluded after a firmware restart.
    // Never infer qualification from boot args, a reset indication or DB=0.
    return {};
  }
  bool fuaProvenLocked() { return false; }
  bool readPageLocked(uint64_t lba, void *dst) {
    if (retainedReadLocked(lba, 1) != CombinedRead::End::Success) return false;
    memcpy(dst, combined_hardware.virt + CombinedRead::Data, NuwaData::Block);
    return true;
  }
};
static CandidatePort dataPort;
static NuwaData::Provider<CandidatePort, false> dataProvider(dataPort, retainedSlot);
static unsigned liveGptStatus;
static NuwaData::LiveGpt cachedLiveGpt() {
  return static_cast<NuwaData::LiveGpt>(__atomic_load_n(&liveGptStatus, __ATOMIC_RELAXED));
}

static bool openCandidateData(uint64_t first, uint64_t blocks, uint64_t reserve) {
  if (!gHost.lock || gStoreGeometry.first != nuwaDataIdentity.userdataFirst ||
      gStoreGeometry.last != nuwaDataIdentity.userdataLast) return false;
  uint32_t request = 0;
  if (!NuwaData::BuildWriteOptIn ||
      !PE_parse_boot_argn("nuwa-data-write", &request, sizeof request) || request != 1)
    return false;
  auto *g = static_cast<NuwaData::GptBuffers *>(IOMallocZero(sizeof(NuwaData::GptBuffers)));
  if (!g) return false;
  NuwaData::LiveGpt live;
  const auto preflight = [&](const auto &read) {
    using DualBank = NuwaData::DualBankLogOverlay<>;
    using Disposable = NuwaData::DualBankLogOverlay<512, true>;
    constexpr auto legacy = DualBank::Media;
    // This store size is reserved for v3. Its normal open/replay stays intact.
    if (blocks == legacy.blocks || first >= legacy.first + legacy.blocks ||
        (first < legacy.first && blocks <= legacy.first - first)) return true;
    static_assert(Disposable::Media.first == legacy.first && Disposable::Media.blocks == legacy.blocks);
    for (uint32_t slot = 0; slot < 2; ++slot)
      if (!read(legacy.first + slot, g->ph) || DualBank::hasSuperblockMarker(g->ph, slot) ||
          Disposable::hasSuperblockMarker(g->ph, slot)) return false;
    return true;
  };
  bool result = dataProvider.openWithPreflight(nuwaDataIdentity, 0, NuwaData::Block,
      gStoreGeometry.imageBytes, reserve, {first, blocks}, *g, true, &live, preflight);
  __atomic_store_n(&liveGptStatus, unsigned(live), __ATOMIC_RELAXED);
  IOFree(g, sizeof(NuwaData::GptBuffers));
  return result;
}

#if defined(NUWA_DISPOSABLE_DATA)
#include "DisposablePort.inc"
#endif
