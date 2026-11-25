// UTP diagnostic only. Called from the successful root publisher, not the UI.
struct DescriptorPort {
  NuwaUfsDesc::Result read_descriptor(unsigned type, unsigned index,
                                      uint8_t (&buf)[NuwaUfsDesc::MaxBytes]) {
    using namespace NuwaUfsDesc;
    const Request q{type, index};
    if (!q.valid()) return {Status::Invalid};
    if (!gHost.lock) return {Status::NotReady};
    struct Guard {
      Guard() { IOLockLock(gHost.lock); }
      ~Guard() { IOLockUnlock(gHost.lock); }
    } lock;
    if (!retainedReadyLocked()) return {Status::NotReady};
    if (!retainedSlot.submitRead(true, retainedOwnershipLocked())) return {Status::Unowned};
    combined_state.desc = q;
    const auto end = CombinedRead::issue(combined_hardware, combined_state,
                                         CombinedRead::Command::QueryDesc);
    const auto evidence = retainedCompletion(end, false);
    retainedSlot.complete(evidence);
    if (!retainedSlot.rootAllowed()) retainQuarantineLocked();
    if (end == CombinedRead::End::Success) {
      const auto *response = combined_hardware.response();
      const unsigned n = unsigned(response[10]) << 8 | response[11];
      for (unsigned i = 0; i < n; ++i) buf[i] = response[32 + i];
      return {Status::Ok, n};
    }
    if (end == CombinedRead::End::QueryError)
      return {Status::CommandError, 0, combined_state.queryResult};
    return {evidence == NuwaData::Evidence::Timeout ? Status::Timeout : Status::Unowned};
  }
};

static NuwaUfsDesc::Snapshot ufsDescSnapshot;
static unsigned ufsDescClaimed, ufsDescPublished;

static void probeUfsDescriptors() {
  uint32_t enable = 0;
  if (!PE_parse_boot_argn("nuwa-ufs-desc", &enable, sizeof enable) || enable != 1) return;
  if (__atomic_exchange_n(&ufsDescClaimed, 1U, __ATOMIC_ACQ_REL)) return;
  DescriptorPort port;
  NuwaUfsDesc::collect(port, ufsDescSnapshot);
  __atomic_store_n(&ufsDescPublished, 1U, __ATOMIC_RELEASE);
}

static unsigned cachedUfsDescRow(char *out, size_t n) {
  using NuwaUfsDesc::Status;
  if (!__atomic_load_n(&ufsDescPublished, __ATOMIC_ACQUIRE)) return 0;
  const auto &s = ufsDescSnapshot;
  if (s.result.status != Status::Ok)
    snprintf(out, n, "UFS err=%u q=%02x", unsigned(s.result.status), s.result.code);
  else if (s.units[0].enabled)
    snprintf(out, n, "UFS lu=%u bs=%u wp=%08x mfr=%04x", s.lus,
             s.units[0].blockSize, unsigned(s.wp), s.manufacturer);
  else
    snprintf(out, n, "UFS lu=%u bs=unk wp=%08x mfr=%04x", s.lus, unsigned(s.wp), s.manufacturer);
  return 1;
}
