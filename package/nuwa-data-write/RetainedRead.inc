// Included after CombinedRead and gHost, before the retained RootCommands.h.
static NuwaData::Slot retainedSlot;

// Caller holds gHost.lock. Preserve every allocation and mapping on failure.
static bool retainedHostUsableLocked() {
  return gHost.ready && !gHost.poisoned && !combined_state.quarantined;
}
static bool retainedReadyLocked() { return retainedHostUsableLocked() && retainedSlot.rootAllowed(); }

// Before bring-up the lock may not exist. Once services are published, it
// is retained. A snapshot is only a precheck; never hold it across admission.
static bool retainedReadySnapshot() {
  if (!gHost.lock) return false;
  IOLockLock(gHost.lock);
  const bool ready = retainedReadyLocked();
  IOLockUnlock(gHost.lock);
  return ready;
}

static void blockRetainedHostLocked() {
  combined_state.quarantined = gHost.poisoned = true;
  gHost.ready = false;
}

static void retainQuarantineLocked() {
  retainedSlot.quarantine();
  blockRetainedHostLocked();
}

static NuwaData::Evidence retainedCompletion(CombinedRead::End end, bool write) {
  using CombinedRead::End;
  using NuwaData::Evidence;
  if (end == End::Success) return write ? Evidence::FullFua : Evidence::ReadOk;
  if (end == End::Scsi || end == End::QueryError) return Evidence::AttributedCommandError;
  const auto &poll = combined_state.poll;
  // Transfer means timeout only if poll saw neither completion nor fatal.
  if (end == End::Transport && poll.ocs == 15 && !(poll.doorbellSeen & ~1U) &&
      !(poll.interruptSeen & kUfsFatalStatus)) return Evidence::Timeout;
  return Evidence::Unowned;
}

static bool retainedOwnershipLocked() {
  if (CombinedRead::guard(combined_hardware, combined_state)) return true;
  retainQuarantineLocked();
  return false;
}

static CombinedRead::End retainedReadLocked(uint64_t lba, unsigned blocks) {
  using CombinedRead::End;
  if (!retainedReadyLocked()) return End::Guard;
  if (!RootReadSession::span(combined_state, 0, lba, blocks)) return End::Capacity;
  if (!retainedSlot.submitRead(true, retainedOwnershipLocked())) return End::Guard;
  combined_state.readLba = lba;
  combined_state.readBlocks = blocks;
  // issue() checks the retained domain before DMA staging and again before
  // the doorbell. Unlike RootReadSession::read, it exposes attributed Scsi.
  const auto end = CombinedRead::issue(combined_hardware, combined_state,
                                      CombinedRead::Command::Read);
  retainedSlot.complete(retainedCompletion(end, false));
  if (!retainedSlot.rootAllowed()) retainQuarantineLocked();
  return end;
}
