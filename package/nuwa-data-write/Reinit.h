#pragma once
#include "Gate.h"

namespace NuwaData {
enum class ReinitResult {
  NotIsolated, AlreadyAttempted, PlatformUnproven, ReadyForSteps,
  HceStop, HceStart, InterruptPolicy, Timers, Link, Utrl, Utmr, Hcs,
  ReadbackTimeout, MediaUnproven, RECOVERY_PROVEN,
};

struct ReinitPermit {
  ColdStartIdentity oldDomain{}, freshDomain{};
  bool otherProducersExcluded = false, oldDmaExcluded = false;
  bool freshQueuesDisjoint = false, platformInitQualified = false;
  constexpr bool qualified() const {
    return oldDomain.matches(oldDomain) && freshDomain.matches(freshDomain) &&
           oldDomain.boot_session_id == freshDomain.boot_session_id &&
           oldDomain.domain_id != freshDomain.domain_id &&
           oldDomain.media_id == freshDomain.media_id && otherProducersExcluded &&
           oldDmaExcluded && freshQueuesDisjoint && platformInitQualified;
  }
};

struct ReinitOutcome {
  ReinitResult result;
  ColdStartIdentity freshDomain{};
  ColdStartEvidence evidence{};
};

// All calls are serialized by the transport lock. The old slot is never
// changed. The platform permit must be established independently, without
// probing/reprogramming the isolated controller to manufacture proof.
class ReinitAttempt {
  bool attempted_ = false;
public:
  ReinitResult beginLocked(const Slot &oldSlot, const ReinitPermit &permit) {
    if (oldSlot.state() != State::TIMEOUT_ORPHAN && oldSlot.state() != State::FATAL_QUARANTINED)
      return ReinitResult::NotIsolated;
    if (attempted_) return ReinitResult::AlreadyAttempted;
    attempted_ = true;
    return permit.qualified() ? ReinitResult::ReadyForSteps : ReinitResult::PlatformUnproven;
  }

  // Host-testable sequence, not a hardware port. Each operation must check
  // its bounded ordered readback. Failed verification leaves both sessions
  // unusable; the port must retain all DMA and never attempt a cleanup reset.
  template<class Port>
  ReinitOutcome tryReinitLocked(const Slot &oldSlot, const ReinitPermit &permit, Port &port) {
    using R = ReinitResult;
    const auto start = beginLocked(oldSlot, permit);
    if (start != R::ReadyForSteps) return {start};
    if (!port.stopHceAndVerifyLocked()) return {R::HceStop};
    if (!port.startHceAndVerifyLocked()) return {R::HceStart};
    if (!port.interruptPolicyAndVerifyLocked()) return {R::InterruptPolicy};
    if (!port.timersAndVerifyLocked()) return {R::Timers};
    if (!port.linkStartupAndVerifyLocked()) return {R::Link};
    if (!port.utrlAndVerifyLocked()) return {R::Utrl};
    if (!port.utmrAndVerifyLocked()) return {R::Utmr};
    if (!port.listsReadyAndVerifyLocked()) return {R::Hcs};
    ColdStartEvidence proof{};
    const auto read = port.verifyMediaReadOnlyLocked(permit.freshDomain, proof);
    if (read == Evidence::Timeout) return {R::ReadbackTimeout};
    if (read != Evidence::ReadOk || !proof.qualified(permit.freshDomain))
      return {R::MediaUnproven};
    return {R::RECOVERY_PROVEN, permit.freshDomain, proof};
  }
};
}
