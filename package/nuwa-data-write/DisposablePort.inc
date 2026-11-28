// SPDX-License-Identifier: BSD-2-Clause
// Same retained gHost.lock, DMA allocation, and Slot0 as root, no second queue.
static bool disposableOpen;

static bool disposableRequested() {
  uint32_t request = 0, conflict = 0;
  return PE_parse_boot_argn("nuwa-disposable-data", &request, sizeof request) && request == 1 &&
         !PE_parse_boot_argn("nuwa-data-write", &conflict, sizeof conflict) &&
         !PE_parse_boot_argn("sheng-data-reset", &conflict, sizeof conflict) &&
         !PE_parse_boot_argn("sheng-log", &conflict, sizeof conflict) &&
         !PE_parse_boot_argn("sheng-smp", &conflict, sizeof conflict);
}

struct DisposableHostLock {
  DisposableHostLock() { IOLockLock(gHost.lock); }
  ~DisposableHostLock() { IOLockUnlock(gHost.lock); }
};

static bool disposableReadLocked(uint64_t lba, void *dst) {
  if (!retainedReadyLocked()) return false;
  if (retainedReadLocked(lba, 1) != CombinedRead::End::Success) {
    retainQuarantineLocked();
    return false;
  }
  memcpy(dst, combined_hardware.virt + CombinedRead::Data, NuwaData::Block);
  return true;
}

static bool openDisposableData(uint64_t first, uint64_t blocks, uint64_t reserve) {
  using namespace NuwaData;
  const auto media = Disposable::Overlay::Media;
  if (!gHost.lock || !disposableRequested() ||
      !Disposable::seedMatches(native_ram_block_seed_sha256) ||
      gStoreGeometry.first != nuwaDataIdentity.userdataFirst ||
      gStoreGeometry.last != nuwaDataIdentity.userdataLast ||
      gStoreGeometry.imageBytes != Disposable::RootBytes ||
      reserve != Disposable::Reserve || first != media.first || blocks != media.blocks ||
      !placement(nuwaDataIdentity, gStoreGeometry.imageBytes, reserve, media)) return false;
  auto *g = static_cast<GptBuffers *>(IOMallocZero(sizeof(GptBuffers)));
  if (!g) return false;
  bool ok = false;
  {
    DisposableHostLock lock;
    const auto cap = nuwaDataIdentity.capacity;
    if (!disposableOpen && retainedSlot.dataAllowed(retainedReadyLocked()) &&
        combined_state.blocks == cap && combined_state.block == Block &&
        disposableReadLocked(1, g->ph) && disposableReadLocked(2, g->pe) &&
        disposableReadLocked(cap - 1, g->bh)) {
      const auto backup = le64(g->bh + 72);
      if (backup > nuwaDataIdentity.lastUsable && backup < cap - 1 &&
          disposableReadLocked(backup, g->be)) {
        ok = gpt(0, Block, nuwaDataIdentity, {1, 2, g->ph, g->pe},
                 {cap - 1, backup, g->bh, g->be});
        disposableOpen = ok;
      }
    }
  }
  IOFree(g, sizeof(GptBuffers));
  return ok;
}

static bool disposableRead(uint64_t rel, uint32_t n, void *dst) {
  using namespace NuwaData;
  const auto media = Disposable::Overlay::Media;
  if (!gHost.lock || !dst || rel >= media.blocks || !n || n > media.blocks - rel)
    return false;
  DisposableHostLock lock;
  if (!disposableOpen) return false;
  for (uint32_t i = 0; i < n; ++i)
    if (!disposableReadLocked(media.first + rel + i, static_cast<uint8_t *>(dst) + uint64_t(i) * Block))
      return false;
  return true;
}

static bool disposableWrite(uint64_t rel, uint32_t n, const void *src) {
  using namespace NuwaData;
  using Overlay = Disposable::Overlay;
  if (!gHost.lock || !src || n != 1 || rel < Overlay::Log || rel >= Overlay::Media.blocks)
    return false; // Runtime never writes either superblock or either map.
  const auto lba = Overlay::Media.first + rel;
  DisposableHostLock lock;
  if (!disposableOpen || !retainedSlot.dataAllowed(retainedReadyLocked()) ||
      !RootReadSession::span(combined_state, 0, lba, 1) ||
      !retainedSlot.submit(true, retainedOwnershipLocked())) return false;
  combined_state.readLba = lba;
  combined_state.readBlocks = 1;
  auto end = CombinedRead::issue(combined_hardware, combined_state,
                                CombinedRead::Command::WriteVolatile,
                                static_cast<const uint8_t *>(src));
  auto evidence = end == CombinedRead::End::Success
      ? (combined_state.returned == Block ? Evidence::FullWrite : Evidence::Unowned)
      : retainedCompletion(end, false);
  if (retainedSlot.complete(evidence)) return true;
  retainQuarantineLocked();
  return false;
}

static bool disposableOrder() {
  if (!gHost.lock) return false;
  DisposableHostLock lock;
  // All earlier commands returned under this lock. This does not flush UFS.
  return disposableOpen && retainedSlot.dataAllowed(retainedReadyLocked()) &&
         retainedOwnershipLocked();
}
