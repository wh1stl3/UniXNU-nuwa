// Included only in the pinned nuwa retained-root provider, after StoreGeometry.
struct CandidatePort {
  void lock() { IOLockLock(gHost.lock); }
  void unlock() { IOLockUnlock(gHost.lock); }
  bool readyLocked() { return retainedReadyLocked(); }
  bool ownershipLocked() { return retainedOwnershipLocked(); }
  uint64_t capacityLocked() { return combined_state.blocks; }
  unsigned blockSizeLocked() { return combined_state.block; }
  // TODO: no retained task termination/DMA drain or restart contract.
  // Do not invoke Slot::tryRecover or clear the transport quarantine here.
  bool recoveryProvenLocked() { return false; }
  bool fuaProvenLocked() { return false; }
  bool readPageLocked(uint64_t lba, void *dst) {
    if (retainedReadLocked(lba, 1) != CombinedRead::End::Success) return false;
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
static NuwaData::Provider<CandidatePort, false> dataProvider(dataPort, retainedSlot);

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
