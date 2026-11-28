// SPDX-License-Identifier: BSD-2-Clause
// Included after StoreGeometry. The root path and this adapter use the same
// retained slot, host lock, command buffer and completion/ownership rules.
#include "DisposableData.h" // Pinned seed identity and legacy format markers only.
#include "V1ResetMarker.h"
extern "C" uint8_t native_ram_block_seed_sha256[32];
extern "C" const char *volatile nuwa_data_persist_open_why;
// Diagnostic only: high word is the first failed store-write reason, low
// word is SCSI status/sense for an attributed CHECK CONDITION.
extern "C" {
volatile uint64_t nuwa_v1_ufs_write_failure = 0;
}

namespace {
using namespace NuwaData;
static Window persistWindow{};
static unsigned persistGptStatus;
static void persistWriteFailure(unsigned code, unsigned status = 0, unsigned sense = 0) {
  uint64_t expected = 0;
  const uint64_t value = (uint64_t(code) << 32) | (uint64_t(status & 0xff) << 24) |
                         (sense & 0xffffff);
  __atomic_compare_exchange_n(&nuwa_v1_ufs_write_failure, &expected, value, false,
                              __ATOMIC_RELAXED, __ATOMIC_RELAXED);
}
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

static bool persistClearLegacyAnchorLocked(uint64_t lba, const uint8_t *zeroBlock);
static bool persistWriteLocked(uint64_t lba, unsigned n, const uint8_t *src);

static bool persistCheckMediaLocked(Window window, uint64_t reserve, bool reset,
                                    GptBuffers &g, unsigned &cleared, const char **why) {
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
  constexpr uint64_t v1Blocks = 1 + Legacy::Pages +
      (Legacy::Pages + 8ULL * Block - 1) / (8ULL * Block);
  static_assert(Disposable::Overlay::Media.first == legacy.first &&
                Disposable::Overlay::Media.blocks == legacy.blocks);
  bool disposable[2]{};
  if (window.first < legacy.first + legacy.blocks && legacy.first < window.first + window.blocks) {
    for (uint32_t i = 0; i < 2; ++i) {
      if (!persistReadLocked(legacy.first + i, 1, g.ph)) {
        if (reset) *why = "legacy-reset-read";
        return false;
      }
      if (Legacy::hasSuperblockMarker(g.ph, i)) { *why = "legacy-v3"; return false; }
      // Disposable initialization permits only SB0; SB1 must be entirely
      // empty even if it resembles a well-formed slot-1 superblock.
      if (reset && i == 1 && !zero(g.ph, Block)) {
        *why = "legacy-reset-sb1";
        return false;
      }
      disposable[i] = Disposable::Overlay::hasSuperblockMarker(g.ph, i);
      if (disposable[i] && !reset) { *why = "legacy-disposable"; return false; }
      if (disposable[i] && !Disposable::Overlay::validSuperblockForSeed(g.ph, i, Disposable::Seed)) {
        *why = "legacy-reset-invalid";
        return false;
      }
    }
    if (disposable[0]) {
      // The cleanup is a separate target, not an enlargement of the v1 window.
      // Require the exact v1 size and independently qualify the entire old
      // disposable window against the same root-image guard and reserve.
      if (!reset || window.blocks != v1Blocks ||
          !placement(id, gStoreGeometry.imageBytes, reserve, legacy) ||
          !retainedSlot.dataAllowed(retainedReadyLocked()) || !retainedOwnershipLocked()) {
        *why = "legacy-reset-guard";
        return false;
      }
    }
  }
  if (reset && window.blocks != v1Blocks) { *why = "legacy-reset-guard"; return false; }
  if (window.blocks == v1Blocks) {
    // Read both legacy anchors and the v1 header before the first reset write.
    if (!persistReadLocked(window.first, 1, g.bh)) {
      if (reset) *why = "legacy-reset-read";
      return false;
    }
    if (!reset && V1ResetMarker::present(g.bh)) {
      *why = "legacy-reset-pending";
      return false;
    }
    if (reset) {
      if (!retainedSlot.dataAllowed(retainedReadyLocked()) || !retainedOwnershipLocked()) {
        *why = "legacy-reset-guard";
        return false;
      }
      nuwa_data_persist_open_why = "- rst=ready";
      V1ResetMarker::set(g.bh);
      if (!persistWriteLocked(window.first, 1, g.bh)) {
        *why = "legacy-reset-marker-write";
        return false;
      }
      nuwa_data_persist_open_why = "- rst=progress";
      memset(g.ph, 0, Block);
      if (disposable[0]) {
        if (!persistClearLegacyAnchorLocked(legacy.first, g.ph)) {
          *why = "legacy-reset-write-1";
          return false;
        }
        cleared = 1;
        nuwa_data_persist_open_why = "- rst=clean1";
      }
    }
  }
  return retainedSlot.dataAllowed(retainedReadyLocked());
}

static bool persistWriteLocked(uint64_t lba, unsigned n, const uint8_t *src) {
  if (!retainedSlot.dataAllowed(retainedReadyLocked()) ||
      !RootReadSession::span(combined_state, 0, lba, n) ||
      !retainedSlot.submit(true, retainedOwnershipLocked())) {
    persistWriteFailure(0x100); // admission, span, or ownership refusal
    return false;
  }
  combined_state.readLba = lba;
  combined_state.readBlocks = n;
  const auto end = CombinedRead::issue(combined_hardware, combined_state,
                                       CombinedRead::Command::WriteVolatile, src);
  const auto evidence = end == CombinedRead::End::Success
      ? (combined_state.returned == n * Block ? Evidence::FullWrite : Evidence::Unowned)
      : retainedCompletion(end, false);
  if (retainedSlot.complete(evidence)) return true;
  persistWriteFailure(end == CombinedRead::End::Success ?
      (combined_state.returned == n * Block ? 0x103 : 0x102) : unsigned(end),
      end == CombinedRead::End::Scsi ? combined_state.status : 0,
      end == CombinedRead::End::Scsi ? combined_state.sense : 0);
  retainQuarantineLocked();
  return false;
}

static bool persistClearLegacyAnchorLocked(uint64_t lba, const uint8_t *zeroBlock) {
  constexpr Window anchors{DualBankLogOverlay<>::Media.first, 1};
  return anchors.contains(0, Block, lba, 1) && persistWriteLocked(lba, 1, zeroBlock);
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
  uint32_t resetValue = 0;
  const bool reset = PE_parse_boot_argn("sheng-data-reset", &resetValue, sizeof resetValue) &&
                     (resetValue == 1 || resetValue == 2);
  auto *g = static_cast<GptBuffers *>(IOMallocZero(sizeof(GptBuffers)));
  if (!g) return 0;
  bool ok;
  unsigned cleared = 0;
  const char *failure = "retained persistence window refused";
  {
    PersistHostLock lock;
    ok = !persistWindow.blocks && gStoreGeometry.valid &&
         gStoreGeometry.first == id.userdataFirst && gStoreGeometry.last == id.userdataLast &&
         Disposable::seedMatches(native_ram_block_seed_sha256) &&
         placement(id, gStoreGeometry.imageBytes, reserve, window) &&
         persistCheckMediaLocked(window, reserve, reset, *g, cleared, &failure);
    if (ok) persistWindow = window;
  }
  IOFree(g, sizeof(GptBuffers));
  if (!ok) { if (why) *why = failure; return 0; }
  if (firstLba) *firstLba = window.first;
  if (why) *why = reset ? (cleared == 3 ? "legacy-reset-3" :
                           cleared == 2 ? "legacy-reset-2" :
                           cleared == 1 ? "legacy-reset-1" : "legacy-reset-0") : "";
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
  if (!gHost.lock || !src) { persistWriteFailure(0x101); return 0; }
  PersistHostLock lock;
  if (rel >= persistWindow.blocks ||
      !persistWindow.contains(0, Block, persistWindow.first + rel, blocks)) {
    persistWriteFailure(0x101); return 0;
  }
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
