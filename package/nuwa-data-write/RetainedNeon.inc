// Setup and successful root publisher each write their own immutable snapshot.
// The renderer acquires the published phase and never enters the transport.
#ifdef NUWA_NEON_SETUP
static NuwaNeon::Hc neonHc;
static unsigned neonPhase;

static bool neonBegin() {
  uint32_t enable = 0;
  if (!PE_parse_boot_argn("nuwa-ufs-neon", &enable, sizeof enable) || enable != 1) return false;
  __atomic_store_n(&neonPhase, 1U, __ATOMIC_RELEASE);
  return true;
}

static void neonPre(const NuwaNeon::Hc &hc) {
  neonHc = hc;
  __atomic_store_n(&neonPhase, 2U, __ATOMIC_RELEASE);
}
#else
static NuwaNeon::Descriptors neonDesc;
static NuwaNeon::Media neonMedia;

static void probeNeon() {
  using namespace NuwaNeon;
  struct Port : DescriptorPort {
    bool ready() { return retainedReadySnapshot(); }
  } port;
  // READ CAPACITY geometry is established once by CombinedRead::run.
  descriptors(port, neonDesc, combined_state.blocks, combined_state.block);
  __atomic_store_n(&neonPhase, 3U, __ATOMIC_RELEASE);
  if (neonDesc.rcBlock == Block && neonDesc.rcBlocks == nuwaDataIdentity.capacity &&
      port.ready()) {
    auto *g = static_cast<GptBuffers *>(IOMallocZero(sizeof(GptBuffers)));
    if (g) {
      const auto read = [](uint64_t lba, void *dst) {
        dataPort.lock();
        const bool ok = dataPort.readyLocked() && dataPort.readPageLocked(lba, dst);
        dataPort.unlock();
        return ok;
      };
      // Read the same policy input as reserveBlocks(), without changing its cache.
      uint32_t mib = kDefaultReserveMiB;
      if (!PE_parse_boot_argn("sheng-log-reserve", &mib, sizeof mib) || mib > 16384)
        mib = kDefaultReserveMiB;
      const uint64_t image = gStoreGeometry.valid &&
          gStoreGeometry.first == nuwaDataIdentity.userdataFirst &&
          gStoreGeometry.last == nuwaDataIdentity.userdataLast &&
          neonDesc.capacity == Check::Ok ? gStoreGeometry.imageBytes : 0;
      media(read, nuwaDataIdentity, image, uint64_t(mib) * 256, NuwaNeon::Overlay::Media, *g, neonMedia);
      IOFree(g, sizeof *g);
    }
  }
  __atomic_store_n(&neonPhase, 4U, __ATOMIC_RELEASE);
}

extern "C" unsigned nuwa_ufs_neon_rows(char rows[][120], unsigned room) {
  using namespace NuwaNeon;
  using namespace NuwaUfsDesc;
  const unsigned phase = __atomic_load_n(&neonPhase, __ATOMIC_ACQUIRE);
  if (!phase || !room) return 0;
  unsigned n = 0;
  snprintf(rows[n++], 120, "%s s=%u old=? rsr=?", Identity, phase);
  if (phase < 2 || n == room) return n;
  char hc[6][9];
  for (unsigned i = 0; i < 6; ++i) {
    if (neonHc.seen & (1U << i)) snprintf(hc[i], sizeof hc[i], "%08x", neonHc.value[i]);
    else memcpy(hc[i], "?", 2);
  }
  snprintf(rows[n++], 120, "NEON HC %s/%s/%s/%s/%s/%s",
           hc[0], hc[1], hc[2], hc[3], hc[4], hc[5]);
  if (phase < 3 || n == room) return n;
  const auto &d = neonDesc;
  if (d.device.status == Status::Ok && d.device.bytes >= 0x1a)
    snprintf(rows[n++], 120, "NEON DEV len=%02x lu=%02x boot=%02x mfr=%02x%02x",
             d.dev[0], d.dev[6], d.dev[8], d.dev[0x18], d.dev[0x19]);
  else
    snprintf(rows[n++], 120, "NEON DEV st=%u q=%02x len=%u",
             unsigned(d.device.status), d.device.code, d.device.bytes);
  if (n == room) return n;
  if (d.unit.bytes >= 0x13) {
    uint64_t raw = 0;
    for (unsigned i = 0x0b; i < 0x13; ++i) raw = (raw << 8) | d.lu0[i];
    snprintf(rows[n++], 120, "NEON LU %02x/%02x/%02x n=%016llx rc=%llx/%x %s",
             d.lu0[3], d.lu0[5], d.lu0[0xa], (unsigned long long)raw,
             (unsigned long long)d.rcBlocks, d.rcBlock, text(d.capacity));
  } else {
    snprintf(rows[n++], 120, "NEON LU st=%u q=%02x rc=%llx/%x",
             unsigned(d.unit.status), d.unit.code, (unsigned long long)d.rcBlocks, d.rcBlock);
  }
  if (n == room) return n;
  const auto bit = [](Bit b) { return b == Bit::Set ? '1' : b == Bit::Clear ? '0' : '?'; };
  const Media pending{};
  const auto &m = phase == 4 ? neonMedia : pending;
  snprintf(rows[n++], 120, "NEON MS %c/%c e=%u:%06x GPT p/b/id=%s/%s/%s",
           bit(d.mode.dpofua), bit(d.mode.wce), unsigned(d.mode.result.status), d.mode.result.code,
           text(m.primary), text(m.backup), text(m.agree));
  if (n == room) return n;
  snprintf(rows[n++], 120, "NEON PL=%s A=%u/4 nz=%x M(part)=%u/%zu nz=%u",
           text(m.place), m.anchorsRead, m.anchorsNonzero, m.samples,
           sizeof Metadata / sizeof Metadata[0], m.nonzero);
  return n;
}
#endif
