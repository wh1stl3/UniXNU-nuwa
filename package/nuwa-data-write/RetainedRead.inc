// Included after CombinedRead and gHost, before the retained RootCommands.h.
static NuwaData::Slot retainedSlot;

// Caller holds gHost.lock. Preserve every allocation and mapping on failure.
static bool retainedReadyLocked() {
  return gHost.ready && !gHost.poisoned && !combined_state.quarantined &&
         retainedSlot.rootAllowed();
}

static void retainQuarantineLocked() {
  retainedSlot.quarantine();
  combined_state.quarantined = gHost.poisoned = true;
  gHost.ready = false;
}

static bool retainedOwnershipLocked() {
  if (CombinedRead::guard(combined_hardware, combined_state)) return true;
  retainQuarantineLocked();
  return false;
}

static CombinedRead::End retainedReadLocked(uint64_t lba, unsigned blocks) {
  using CombinedRead::End;
  using NuwaData::Evidence;
  if (!retainedReadyLocked()) return End::Guard;
  if (!RootReadSession::span(combined_state, 0, lba, blocks)) return End::Capacity;
  if (!retainedSlot.submitRead(true, retainedOwnershipLocked())) return End::Guard;
  combined_state.readLba = lba;
  combined_state.readBlocks = blocks;
  // issue() checks the retained domain before DMA staging and again before
  // the doorbell. Unlike RootReadSession::read, it exposes attributed Scsi.
  const auto end = CombinedRead::issue(combined_hardware, combined_state,
                                      CombinedRead::Command::Read);
  const auto &poll = combined_state.poll;
  // Transfer means timeout only if poll never observed completion (including
  // an OCS error) or fatal. A post-poll fault is not classified by wall time.
  const bool timeout = end == End::Transport && poll.ocs == 15 &&
                       !(poll.doorbellSeen & ~1U) &&
                       !(poll.interruptSeen & kUfsFatalStatus);
  retainedSlot.complete(end == End::Success ? Evidence::ReadOk :
                        end == End::Scsi ? Evidence::AttributedCommandError :
                        timeout ? Evidence::Timeout : Evidence::Unowned);
  if (!retainedSlot.rootAllowed()) retainQuarantineLocked();
  return end;
}
