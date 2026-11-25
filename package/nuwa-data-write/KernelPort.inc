// Included only in the pinned nuwa retained-root provider, after StoreGeometry.
struct CandidatePort {
  void lock() { IOLockLock(gHost.lock); }
  void unlock() { IOLockUnlock(gHost.lock); }
  bool readyLocked() {
    return gHost.ready && !gHost.poisoned && !combined_state.quarantined;
  }
  bool ownershipLocked() {
    if (CombinedRead::guard(combined_hardware, combined_state)) return true;
    combined_state.quarantined = gHost.poisoned = true;
    gHost.ready = false;
    return false;
  }
  uint64_t capacityLocked() { return combined_state.blocks; }
  unsigned blockSizeLocked() { return combined_state.block; }
  bool recoveryProvenLocked() { return false; }
  bool fuaProvenLocked() { return false; }
  bool readPageLocked(uint64_t lba, void *dst) {
    if (!RootReadSession::span(combined_state, 0, lba, 1)) return false;
    if (RootReadSession::read(combined_hardware, combined_state, lba, 1) != CombinedRead::End::Success) {
      combined_state.quarantined = gHost.poisoned = true;
      gHost.ready = false;
      return false;
    }
    memcpy(dst, combined_hardware.virt + CombinedRead::Data, NuwaData::Block);
    return true;
  }
  NuwaData::Evidence writePageLocked(const uint8_t (&)[10], const uint8_t *) {
    // No retained write backend before FUA and DMA reclamation are proven.
    // Do not touch descriptors, doorbell, mapping or the bounce buffer.
    return NuwaData::Evidence::Unowned;
  }
};
static CandidatePort dataPort;
static NuwaData::Slot dataSlot;
static NuwaData::Provider<CandidatePort> dataProvider(dataPort, dataSlot);

static bool openCandidateData(uint64_t first, uint64_t blocks, uint64_t reserve) {
  if (!gHost.lock || gStoreGeometry.first != nuwaDataIdentity.userdataFirst ||
      gStoreGeometry.last != nuwaDataIdentity.userdataLast) return false;
  uint32_t request = 0;
  if (!NuwaData::BuildWriteOptIn ||
      !PE_parse_boot_argn("nuwa-data-write", &request, sizeof request) || request != 1)
    return false;
  auto *g = static_cast<NuwaData::GptBuffers *>(IOMallocZero(sizeof(NuwaData::GptBuffers)));
  if (!g) return false;
  bool result = dataProvider.open(nuwaDataIdentity, 0, NuwaData::Block, gStoreGeometry.imageBytes,
                                  reserve, {first, blocks}, *g, true);
  IOFree(g, sizeof(NuwaData::GptBuffers));
  return result;
}
