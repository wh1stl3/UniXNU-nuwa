// SPDX-License-Identifier: BSD-2-Clause
// Staged only for the exclusive SB0 kernel. Uses the unchanged retained queue.
#if NUWA_SB0_PROFILE == 4
#include "Sb0R2.h"
#endif
namespace {
namespace Sb0 = NuwaData::Sb0;
#if NUWA_SB0_PROFILE == 4
namespace Sb0R2 = NuwaData::Sb0R2;
#endif
// Profiles 2 (R) and 4 (R2) are read-only; neither may compile a write case.
constexpr bool sb0Write = NUWA_SB0_PROFILE != 2 && NUWA_SB0_PROFILE != 4;
#if NUWA_SB0_PROFILE != 3
static constexpr const char *sb0Identity =
    NUWA_SB0_PROFILE == 4 ? "NUWA SB0-R2 READONLY" :
    sb0Write ? "NUWA SB0-W UNBOUND" : "NUWA SB0-R READONLY";
#endif

static bool sb0Seed() {
  // Same loader memory-map contract as NativeRamBlock. Verify exact packed
  // bytes (whose logical identity is independently checked during packaging),
  // without starting/publishing RamBlock or importing the seed.
  auto *map = IORegistryEntry::fromPath("/chosen/memory-map", gIODTPlane);
  if (!map) return false;
  auto *packed = OSDynamicCast(OSData, map->getProperty("PackedRAMDisk"));
  uint64_t range[2] = {};
  if (!map->getProperty("RAMDisk") && packed && packed->getLength() == sizeof range)
    memcpy(range, packed->getBytesNoCopy(), sizeof range);
  map->release();
  const auto pa = range[0], bytes = range[1];
  if (bytes != Sb0::EncodedBytes || pa & 4095 || pa < gPhysBase ||
      bytes > gPhysSize || pa - gPhysBase > gPhysSize - bytes) return false;
  const auto va = ml_static_ptovirt(pa);
  if (!va) return false;
  SHA256_CTX ctx;
  uint8_t hash[32];
  SHA256_Init(&ctx);
  SHA256_Update(&ctx, reinterpret_cast<const void *>(va), bytes);
  SHA256_Final(hash, &ctx);
  return !memcmp(hash, Sb0::EncodedHash, sizeof hash);
}

struct Sb0Port {
  bool read(uint64_t lba, uint8_t *out) {
    if (retainedReadLocked(lba, 1) != CombinedRead::End::Success ||
        combined_state.returned != NuwaData::Block) {
      retainQuarantineLocked();
      return false;
    }
    memcpy(out, combined_hardware.virt + CombinedRead::Data, NuwaData::Block);
    return true;
  }
};

struct Sb0HostLock {
  Sb0HostLock() { IOLockLock(gHost.lock); }
  ~Sb0HostLock() {
    retainQuarantineLocked(); // Never hand off the retained DMA session.
    IOLockUnlock(gHost.lock);
  }
};

#if NUWA_SB0_PROFILE == 1
// No consumer is connected in the on-device build. The mock's grant is
// neither a linker import nor a runtime option of this build.
static constexpr bool sb0GrantBound() { return false; }
#endif

#if NUWA_SB0_PROFILE == 1 || NUWA_SB0_PROFILE == 3
__attribute__((noinline)) static Sb0::Report sb0Submit(Sb0::Report out) {
  using namespace NuwaData;
  using Sb0::Result;
#if NUWA_SB0_PROFILE == 1
  if (!sb0GrantBound()) { out.result = Result::Unbound; return out; }
#endif
  if (!retainedSlot.submit(true, retainedOwnershipLocked()))
    return {Result::Guard, Sb0::First, out.pages};
#if NUWA_SB0_PROFILE == 3
  if (!combined_hardware.sb0BootWrite.begin())
    return {Result::Guard, Sb0::First, out.pages};
#endif
  combined_state.readLba = Sb0::First;
  combined_state.readBlocks = 1;
  const unsigned before = combined_state.count;
  const auto end = CombinedRead::issue(combined_hardware, combined_state,
                                       CombinedRead::Command::WriteVolatile, Sb0::Payload);
  out.result = combined_state.count == before ? Result::Guard :
      end == CombinedRead::End::Success && combined_state.returned == Block ?
      Result::Good : Result::Unknown;
  return out;
}
#endif

static Sb0::Report sb0Preflight(NuwaData::GptBuffers &g) {
  using namespace NuwaData;
  using Sb0::Result;
  Sb0HostLock lock;
  const auto cap = nuwaDataIdentity.capacity;
  if (combined_state.blocks != cap || combined_state.block != Block ||
      !placement(nuwaDataIdentity, Disposable::RootBytes, Disposable::Reserve,
                 Disposable::Overlay::Media)) return {Result::Geometry};
  Sb0Port port;
  if (!port.read(1, g.ph)) return {Result::Io, 1};
  if (!port.read(2, g.pe)) return {Result::Io, 2};
  if (!port.read(cap - 1, g.bh)) return {Result::Io, cap - 1};
  // The captured LU uses 61850619, not capacity-2. Use the same bounded
  // backup-header pointer policy as DisposablePort; gpt() checks the copies.
  const auto backup = le64(g.bh + 72);
  if (backup <= nuwaDataIdentity.lastUsable || backup >= cap - 1) return {Result::Gpt};
  if (!port.read(backup, g.be)) return {Result::Io, backup};
  if (!gpt(0, Block, nuwaDataIdentity, {1, 2, g.ph, g.pe},
           {cap - 1, backup, g.bh, g.be})) return {Result::Gpt};
  auto out = Sb0::scan(port, sb0Write, g.ph);
#if NUWA_SB0_PROFILE == 1 || NUWA_SB0_PROFILE == 3
  if (out.result == Result::Blank) out = sb0Submit(out);
#endif
  return out;
}

#if NUWA_SB0_PROFILE == 4
// Defined after sb0Run; the forward declarations keep the legacy R/W slice
// boundaries used by the host transport fixture unchanged.
static Sb0R2::Diagnosis sb0R2Preflight(NuwaData::GptBuffers &);
__attribute__((noreturn)) static void sb0StopR2(const Sb0R2::Diagnosis &);
#endif

__attribute__((noinline, noreturn)) static void sb0Stop(Sb0::Report r) {
  const bool submitted = r.result == Sb0::Result::Good || r.result == Sb0::Result::Unknown;
#if NUWA_SB0_PROFILE == 3
  // Do not enter the panic/reboot path, dispatch a root publisher, or touch UFS.
  (void)nuwa_ufs_marker(13, unsigned(r.result), unsigned(submitted), r.lba ? r.lba : Sb0::First, r.pages);
  asm volatile("msr daifset, #0xf\n\tdsb sy" ::: "memory");
  for (;;) asm volatile("wfe" ::: "memory");
#else
  panic("%s %s LU0 target=57393401 lba=%llu pages=%u commands=%u writes=%u",
        sb0Identity, Sb0::resultName(unsigned(r.result)), r.lba, r.pages, combined_state.count, unsigned(submitted));
#endif
}

__attribute__((noinline, noreturn)) static void sb0Run() {
#if NUWA_SB0_PROFILE == 4
  Sb0R2::Diagnosis diag;
  if (!sb0Seed()) {
    diag.fault = Sb0R2::Fault::Seed;
    sb0StopR2(diag);
  }
#else
  if (!sb0Seed()) sb0Stop({Sb0::Result::Seed});
#endif
  auto *g = static_cast<NuwaData::GptBuffers *>(IOMallocZero(sizeof(NuwaData::GptBuffers)));
  if (!g) {
#if NUWA_SB0_PROFILE == 4
    diag.fault = Sb0R2::Fault::Io;
    sb0StopR2(diag);
#else
    sb0Stop({Sb0::Result::Io});
#endif
  }
  const char *why = nullptr;
#if NUWA_SB0_PROFILE == 3
  if (!hostBringUp(&why)) {
    IOFree(g, sizeof(*g));
    sb0Stop({Sb0::Result::Guard});
  }
#elif NUWA_SB0_PROFILE == 4
  if (!hostBringUp(&why)) {
    IOFree(g, sizeof(*g));
    diag.fault = Sb0R2::Fault::Guard;
    diag.why = why;
    sb0StopR2(diag);
  }
#else
  if (!hostBringUp(&why)) panic("%s IO-FAIL setup=%s", sb0Identity, why);
#endif
#if NUWA_SB0_PROFILE == 4
  const auto report = sb0R2Preflight(*g);
  IOFree(g, sizeof(*g));
  sb0StopR2(report);
#else
  const auto report = sb0Preflight(*g);
  IOFree(g, sizeof(*g));
  sb0Stop(report);
#endif
}

#if NUWA_SB0_PROFILE == 4
// The production adapter is the same host-testable template used by the
// fixture; it is the only place that turns window-relative pages into LU0
// absolute LBAs. GPT reads below still use the bare Sb0Port.
using Sb0R2Port = Sb0R2::Sb0R2Port<Sb0Port>;

// Same geometry, GPT and retained read gate as R. The additional pages are
// the two superblocks, both map copies, the whole ring and each referenced
// data page. No page is written, created or published.
static Sb0R2::Diagnosis sb0R2Preflight(NuwaData::GptBuffers &g) {
  using namespace NuwaData;
  Sb0HostLock lock;
  Sb0R2::Diagnosis d;
  const auto cap = nuwaDataIdentity.capacity;
  if (combined_state.blocks != cap || combined_state.block != Block ||
      !placement(nuwaDataIdentity, Disposable::RootBytes, Disposable::Reserve,
                 Disposable::Overlay::Media)) {
    d.fault = Sb0R2::Fault::Geometry;
    return d;
  }
  Sb0Port port;
  if (!port.read(1, g.ph)) { d.fault = Sb0R2::Fault::Io; d.lba = 1; return d; }
  if (!port.read(2, g.pe)) { d.fault = Sb0R2::Fault::Io; d.lba = 2; return d; }
  if (!port.read(cap - 1, g.bh)) { d.fault = Sb0R2::Fault::Io; d.lba = cap - 1; return d; }
  const auto backup = le64(g.bh + 72);
  if (backup <= nuwaDataIdentity.lastUsable || backup >= cap - 1) {
    d.fault = Sb0R2::Fault::Gpt;
    return d;
  }
  if (!port.read(backup, g.be)) { d.fault = Sb0R2::Fault::Io; d.lba = backup; return d; }
  if (!gpt(0, Block, nuwaDataIdentity, {1, 2, g.ph, g.pe},
           {cap - 1, backup, g.bh, g.be})) {
    d.fault = Sb0R2::Fault::Gpt;
    return d;
  }
  static Sb0R2::Workspace workspace;
  static Sb0R2::SeenScratch seen;
  memset(&workspace, 0, sizeof workspace);
  memset(&seen, 0, sizeof seen);
  Sb0R2Port overlay{port};
  Sb0R2::parse(overlay, Disposable::Seed, Sb0::Payload, workspace, seen, d);
  return d;
}

__attribute__((noinline, noreturn)) static void sb0StopR2(const Sb0R2::Diagnosis &d) {
  char detail[8][128] = {};
  const unsigned details = Sb0R2::detail(d, detail, 8);
  char summary[2][96] = {};
  const unsigned lines = Sb0R2::summary(d, summary);
  char out[768];
  snprintf(out, sizeof out, "NUWA SB0-R2 READONLY");
  size_t used = strlen(out);
#define SB0_R2_APPEND(fmt, ...) \
  do { if (used < sizeof out) \
    used += size_t(snprintf(out + used, sizeof out - used, fmt, __VA_ARGS__)); \
  } while (false)
  SB0_R2_APPEND("\n%s", summary[0]);
  if (lines == 2) SB0_R2_APPEND("\n%s", summary[1]);
  for (unsigned i = 0; i < details; ++i)
    SB0_R2_APPEND("\n%s", detail[i]);
#undef SB0_R2_APPEND
  panic("%s", out);
}
#endif
} // namespace
