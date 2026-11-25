// UTP diagnostic only. Called from the successful root publisher, not the UI.
struct DescriptorPort {
private:
  template<class Decode>
  NuwaUfsDesc::Result read(CombinedRead::Command cmd, NuwaUfsDesc::Request q, Decode decode) {
    using namespace NuwaUfsDesc;
    if (!gHost.lock) return {Status::NotReady};
    struct Guard {
      Guard() { IOLockLock(gHost.lock); }
      ~Guard() { IOLockUnlock(gHost.lock); }
    } lock;
    if (!retainedReadyLocked()) return {Status::NotReady};
    if (!retainedSlot.submitRead(true, retainedOwnershipLocked())) return {Status::Unowned};
    combined_state.desc = q;
    const auto end = CombinedRead::issue(combined_hardware, combined_state, cmd);
    const auto evidence = retainedCompletion(end, false);
    retainedSlot.complete(evidence);
    if (!retainedSlot.rootAllowed()) retainQuarantineLocked();
    if (end == CombinedRead::End::Success) return decode();
    if (end == CombinedRead::End::QueryError)
      return {Status::CommandError, 0, combined_state.queryResult};
    if (end == CombinedRead::End::Scsi)
      return {Status::CommandError, 0, combined_state.sense};
    return {evidence == NuwaData::Evidence::Timeout ? Status::Timeout : Status::Unowned};
  }
public:
  NuwaUfsDesc::Result read_descriptor(unsigned type, unsigned index,
                                      uint8_t (&buf)[NuwaUfsDesc::MaxBytes]) {
    using namespace NuwaUfsDesc;
    const Request q{type, index};
    if (!q.valid()) return {Status::Invalid};
    return read(CombinedRead::Command::QueryDesc, q, [&]() -> Result {
      const auto *response = combined_hardware.response();
      const unsigned n = unsigned(response[10]) << 8 | response[11];
      for (unsigned i = 0; i < n; ++i) buf[i] = response[32 + i];
      return {Status::Ok, n};
    });
  }
  NuwaUfsDesc::Mode modeSense() {
    using namespace NuwaUfsDesc;
    Mode mode;
    mode.result = read(CombinedRead::Command::ModeSense, {}, [&] {
      const auto *data = combined_hardware.data();
      uint8_t p[ModeBytes];
      const auto n = combined_state.returned; // bounded by the attributed residual
      for (unsigned i = 0; i < n; ++i) p[i] = data[i];
      mode = parseMode(p, n);
      return mode.result;
    });
    return mode;
  }
};

static NuwaUfsDesc::Snapshot ufsDescSnapshot;
static NuwaUfsDesc::Mode ufsModeSnapshot;
static unsigned ufsDescClaimed, ufsDescPublished;
static NuwaData::LiveGpt cachedLiveGpt();

static void probeUfsDescriptors() {
  uint32_t enable = 0;
  if (!PE_parse_boot_argn("nuwa-ufs-desc", &enable, sizeof enable) || enable != 1) return;
  if (__atomic_exchange_n(&ufsDescClaimed, 1U, __ATOMIC_ACQ_REL)) return;
  DescriptorPort port;
  NuwaUfsDesc::collect(port, ufsDescSnapshot);
  ufsModeSnapshot = port.modeSense();
  __atomic_store_n(&ufsDescPublished, 1U, __ATOMIC_RELEASE);
}

static unsigned cachedUfsModeRow(char *out, size_t n) {
  using namespace NuwaUfsDesc;
  if (!__atomic_load_n(&ufsDescPublished, __ATOMIC_ACQUIRE)) return 0;
  const auto &s = ufsModeSnapshot;
  if (s.result.status != Status::Ok) {
    snprintf(out, n, "UFS2 err=%u sc=%06x", unsigned(s.result.status), s.result.code);
  } else {
    const auto bit = [](Bit b) { return b == Bit::Set ? "1" : b == Bit::Clear ? "0" : "unk"; };
    const auto gpt = cachedLiveGpt();
    snprintf(out, n, "UFS2 dpofua=%s wce=%s gpt=%s", bit(s.dpofua), bit(s.wce),
             gpt == NuwaData::LiveGpt::Ok ? "ok" : gpt == NuwaData::LiveGpt::Bad ? "bad" : "unk");
  }
  return 1;
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
