#include "../package/nuwa-data-write/Reinit.h"
#include <cassert>
#include <cstdio>
#include <initializer_list>

using namespace NuwaData;
using R = ReinitResult;

static constexpr ReinitPermit Permit{{17, 30, 40}, {17, 31, 40}, true, true, true, true};

// Synthetic register readbacks only. This port has no device or medium-write
// operation. Old storage is never handed to any step.
struct MockPort {
  R fault = R::RECOVERY_PROVEN;
  unsigned stages = 0, reads = 0;
  bool freshDmaRetained = true;
  uint8_t freshDma[Block]{};
  bool readback(R stage, uint32_t expected) {
    ++reads;
    return (fault == stage ? expected ^ 1U : expected) == expected;
  }
  bool stopHceAndVerifyLocked() {
    assert(stages++ == 0);
    return readback(R::HceStop, 0);
  }
  bool startHceAndVerifyLocked() {
    assert(stages++ == 1);
    return readback(R::HceStart, 0) && readback(R::HceStart, 1);
  }
  bool interruptPolicyAndVerifyLocked() {
    assert(stages++ == 2);
    return readback(R::InterruptPolicy, 0) && readback(R::InterruptPolicy, 0);
  }
  bool timersAndVerifyLocked() {
    assert(stages++ == 3);
    // Arbitrary mock values, not clock settings for nuwa.
    return readback(R::Timers, 2) && readback(R::Timers, 3) && readback(R::Timers, 4);
  }
  bool linkStartupAndVerifyLocked() {
    assert(stages++ == 4);
    return readback(R::Link, 0);
  }
  bool utrlAndVerifyLocked() {
    assert(stages++ == 5);
    freshDma[0] = 1;
    return readback(R::Utrl, 0x8000) && readback(R::Utrl, 0);
  }
  bool utmrAndVerifyLocked() {
    assert(stages++ == 6);
    freshDma[1] = 1;
    return readback(R::Utmr, 0xc000) && readback(R::Utmr, 0);
  }
  bool listsReadyAndVerifyLocked() {
    assert(stages++ == 7);
    // Readiness first; only then can the two RSRs be set and read back.
    return readback(R::Hcs, 0xf) && readback(R::Hcs, 1) && readback(R::Hcs, 1) &&
           readback(R::Hcs, 0xf);
  }
  Evidence verifyMediaReadOnlyLocked(ColdStartIdentity id, ColdStartEvidence &proof) {
    assert(stages++ == 8 && id.matches(Permit.freshDomain));
    if (fault == R::ReadbackTimeout) return Evidence::Timeout;
    ColdStartFact f{id, true};
    proof = {f, f, f, f, f, f, f, f};
    uint8_t expected[Block], read[Block];
    memset(expected, 0x97, Block);
    memcpy(read, expected, Block);
    if (fault == R::MediaUnproven) read[Block - 1] ^= 1;
    proof.knownRootMatches.verified = !memcmp(read, expected, Block);
    return Evidence::ReadOk;
  }
};

static void failed(R result, unsigned stages, const char *name) {
  Slot old;
  assert(old.submitRead(true, true) && !old.complete(Evidence::Timeout));
  uint8_t oldDma[Block];
  memset(oldDma, 0x53, sizeof oldDma);
  MockPort port{result};
  ReinitAttempt attempt;
  assert(attempt.tryReinitLocked(old, Permit, port).result == result);
  assert(port.stages == stages && port.freshDmaRetained &&
         old.state() == State::TIMEOUT_ORPHAN && !old.submitRead(true, true));
  assert(attempt.tryReinitLocked(old, Permit, port).result == R::AlreadyAttempted);
  for (uint8_t b : oldDma) assert(b == 0x53);
  std::printf("PASS %s: isolated, no retry, old DMA unchanged\n", name);
}

static void deniedPermit(ReinitPermit permit) {
  Slot old;
  assert(old.submitRead(true, true) && !old.complete(Evidence::Timeout));
  MockPort port;
  ReinitAttempt attempt;
  assert(attempt.tryReinitLocked(old, permit, port).result == R::PlatformUnproven);
  assert(port.stages == 0 && port.reads == 0 && !old.rootAllowed());
  assert(attempt.tryReinitLocked(old, Permit, port).result == R::AlreadyAttempted);
  assert(port.stages == 0 && port.reads == 0);
}

int main() {
  Slot old;
  MockPort port;
  ReinitAttempt deny;
  assert(deny.tryReinitLocked(old, Permit, port).result == R::NotIsolated);
  assert(old.submitRead(true, true) && !old.complete(Evidence::Unowned));
  auto incomplete = Permit;
  incomplete.oldDmaExcluded = false;
  assert(deny.tryReinitLocked(old, incomplete, port).result == R::PlatformUnproven);
  assert(port.stages == 0 && port.reads == 0 && !old.rootAllowed());
  for (auto invalid : {Permit.oldDomain, ColdStartIdentity{17, 31, 41},
                      ColdStartIdentity{18, 31, 40}, ColdStartIdentity{}}) {
    auto wrong = Permit;
    wrong.freshDomain = invalid;
    assert(!wrong.qualified());
  }
  std::puts("PASS missing DMA fence/invalid fresh identity: no re-init operations");
  for (unsigned missing = 0; missing < 4; ++missing) {
    auto permit = Permit;
    switch (missing) {
      case 0: permit.otherProducersExcluded = false; break;
      case 1: permit.oldDmaExcluded = false; break;
      case 2: permit.freshQueuesDisjoint = false; break;
      case 3: permit.platformInitQualified = false; break;
    }
    deniedPermit(permit);
  }
  for (auto invalid : {Permit.oldDomain, ColdStartIdentity{17, 31, 41},
                       ColdStartIdentity{18, 31, 40}, ColdStartIdentity{}}) {
    auto permit = Permit;
    permit.freshDomain = invalid;
    deniedPermit(permit);
  }
  auto noOldIdentity = Permit;
  noOldIdentity.oldDomain = {};
  deniedPermit(noOldIdentity);
  std::puts("PASS each missing permit or invalid identity: zero operations, no retry");
  failed(R::HceStop, 1, "HCE stop not observed");
  failed(R::HceStart, 2, "HCE 1-to-0-to-1 unproven");
  failed(R::InterruptPolicy, 3, "interrupt aggregation/IE mismatch");
  failed(R::Timers, 4, "timer readback mismatch");
  failed(R::Link, 5, "UIC link startup failed");
  failed(R::Utrl, 6, "UTRL readback mismatch");
  failed(R::Utmr, 7, "UTMR readback mismatch");
  failed(R::Hcs, 8, "HCS not ready");
  failed(R::MediaUnproven, 9, "known root block mismatch");
  failed(R::ReadbackTimeout, 9, "re-init media validation timed out");

  ReinitAttempt attempt;
  const auto result = attempt.tryReinitLocked(old, Permit, port);
  assert(result.result == R::RECOVERY_PROVEN && port.stages == 9 && !old.rootAllowed());
  Slot successor(result.freshDomain, result.evidence);
  assert(successor.rootAllowed() && successor.submitRead(true, true));
  assert(!successor.complete(Evidence::Timeout) && !successor.rootAllowed());
  assert(attempt.tryReinitLocked(successor, Permit, port).result == R::AlreadyAttempted);
  std::puts("PASS model proves a fresh session only; next timeout isolates it, no second attempt");
}
