// SPDX-License-Identifier: BSD-2-Clause
// Included after StoreGeometry. The root path and this adapter use the same
// retained slot, host lock, command buffer and completion/ownership rules.
#include "DisposableData.h" // Pinned seed identity and legacy format markers only.
extern "C" uint8_t native_ram_block_seed_sha256[32];

namespace {
using namespace NuwaData;
static Window persistWindow{};
static unsigned persistGptStatus;
static LiveGpt cachedLiveGpt() {
  return static_cast<LiveGpt>(__atomic_load_n(&persistGptStatus, __ATOMIC_RELAXED));
}
struct PersistHostLock {
  PersistHostLock() { IOLockLock(gHost.lock); }
  ~PersistHostLock() { IOLockUnlock(gHost.lock); }
};

static bool persistReadLocked(uint64_t lba, unsigned n, void *dst) {
  if (retainedReadLocked(lba, n) != CombinedRead::End::Success) return false;
  memcpy(dst, combined_hardware.virt + CombinedRead::Data, n * Block);
  return true;
}

static bool persistCheckMediaLocked(Window window, GptBuffers &g) {
  const auto &id = nuwaDataIdentity;
  const auto cap = id.capacity;
  if (!retainedReadyLocked() || combined_state.blocks != cap ||
      !RootReadSession::media(combined_state, 0) ||
      !persistReadLocked(1, 1, g.ph) || !persistReadLocked(2, 1, g.pe) ||
      !persistReadLocked(cap - 1, 1, g.bh)) return false;
  const auto backup = le64(g.bh + 72);
  const bool valid = backup > id.lastUsable && backup < cap - 1 &&
      persistReadLocked(backup, 1, g.be) &&
      gpt(0, Block, id, {1, 2, g.ph, g.pe}, {cap - 1, backup, g.bh, g.be});
  __atomic_store_n(&persistGptStatus, unsigned(valid ? LiveGpt::Ok : LiveGpt::Bad), __ATOMIC_RELAXED);
  if (!valid) return false;

  // A v3 window can start below the v1 window but extend into it.
  using Legacy = DualBankLogOverlay<>;
  constexpr auto legacy = Legacy::Media;
  static_assert(Disposable::Overlay::Media.first == legacy.first &&
                Disposable::Overlay::Media.blocks == legacy.blocks);
  if (window.first < legacy.first + legacy.blocks && legacy.first < window.first + window.blocks)
    for (uint32_t i = 0; i < 2; ++i)
      if (!persistReadLocked(legacy.first + i, 1, g.ph) ||
          Legacy::hasSuperblockMarker(g.ph, i) || Disposable::Overlay::hasSuperblockMarker(g.ph, i))
        return false;
  return retainedSlot.dataAllowed(retainedReadyLocked());
}

static bool persistWriteLocked(uint64_t lba, unsigned n, const uint8_t *src) {
  if (!retainedSlot.dataAllowed(retainedReadyLocked()) ||
      !RootReadSession::span(combined_state, 0, lba, n) ||
      !retainedSlot.submit(true, retainedOwnershipLocked())) return false;
  combined_state.readLba = lba;
  combined_state.readBlocks = n;
  const auto end = CombinedRead::issue(combined_hardware, combined_state,
                                       CombinedRead::Command::WriteVolatile, src);
  const auto evidence = end == CombinedRead::End::Success
      ? (combined_state.returned == n * Block ? Evidence::FullWrite : Evidence::Unowned)
      : retainedCompletion(end, false);
  if (retainedSlot.complete(evidence)) return true;
  retainQuarantineLocked();
  return false;
}

static constexpr unsigned persistMax = CombinedRead::Max / Block;
static_assert(persistMax == 32);
}

extern "C" unsigned native_ufs_store_mode (void)
{
  uint32_t mode = 0, conflict = 0;
  return PE_parse_boot_argn("sheng-data-persist", &mode, sizeof mode) && mode == 2 &&
         !PE_parse_boot_argn("sheng-log", &conflict, sizeof conflict) &&
         !PE_parse_boot_argn("sheng-smp", &conflict, sizeof conflict) ? 2 : 0;
}

extern "C" int native_ufs_store_open (uint64_t blocks, uint64_t *firstLba, const char **why)
{
  if (why) *why = "retained persistence window refused";
  if (!native_ufs_store_mode() || !gHost.lock) return 0;
  uint32_t mib = kDefaultReserveMiB;
  if (!PE_parse_boot_argn("sheng-log-reserve", &mib, sizeof mib) || mib > 16384)
    mib = kDefaultReserveMiB;
  const uint64_t reserve = uint64_t(mib) * 256;
  const auto &id = nuwaDataIdentity;
  const auto end = id.userdataLast + 1;
  const auto partition = end - id.userdataFirst;
  if (reserve < kLogReserveBlocks + kExportBlocks || reserve >= partition ||
      !blocks || blocks > partition - reserve) return 0;
  const Window window{end - reserve - blocks, blocks};
  auto *g = static_cast<GptBuffers *>(IOMallocZero(sizeof(GptBuffers)));
  if (!g) return 0;
  bool ok;
  {
    PersistHostLock lock;
    ok = !persistWindow.blocks && gStoreGeometry.valid &&
         gStoreGeometry.first == id.userdataFirst && gStoreGeometry.last == id.userdataLast &&
         Disposable::seedMatches(native_ram_block_seed_sha256) &&
         placement(id, gStoreGeometry.imageBytes, reserve, window) &&
         persistCheckMediaLocked(window, *g);
    if (ok) persistWindow = window;
  }
  IOFree(g, sizeof(GptBuffers));
  if (!ok) return 0;
  if (firstLba) *firstLba = window.first;
  if (why) *why = "";
  return 1;
}

extern "C" int native_ufs_store_read (uint64_t rel, uint32_t blocks, void *dst)
{
  if (!gHost.lock || !dst) return 0;
  PersistHostLock lock;
  if (rel >= persistWindow.blocks ||
      !persistWindow.contains(0, Block, persistWindow.first + rel, blocks)) return 0;
  auto *p = static_cast<uint8_t *>(dst);
  for (uint32_t done = 0; done < blocks;) {
    const auto n = blocks - done > persistMax ? persistMax : blocks - done;
    if (!persistReadLocked(persistWindow.first + rel + done, n, p + uint64_t(done) * Block)) return 0;
    done += n;
  }
  return 1;
}

extern "C" int native_ufs_store_write (uint64_t rel, uint32_t blocks, const void *src)
{
  if (!gHost.lock || !src) return 0;
  PersistHostLock lock;
  if (rel >= persistWindow.blocks ||
      !persistWindow.contains(0, Block, persistWindow.first + rel, blocks)) return 0;
  const auto *p = static_cast<const uint8_t *>(src);
  for (uint32_t done = 0; done < blocks;) {
    const auto n = blocks - done > persistMax ? persistMax : blocks - done;
    if (!persistWriteLocked(persistWindow.first + rel + done, n, p + uint64_t(done) * Block)) return 0;
    done += n;
  }
  return 1;
}

extern "C" int native_ufs_store_sync (void)
{
  if (!gHost.lock) return 0;
  PersistHostLock lock;
  // V1-NODUR: prior commands completed under this lock. This orders host
  // operations and rechecks ownership; it does not flush the device cache.
  return persistWindow.blocks && retainedSlot.dataAllowed(retainedReadyLocked()) &&
         retainedOwnershipLocked();
}
