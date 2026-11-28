// Setup and successful root publisher each write their own immutable snapshot.
// The renderer acquires the published phase and never enters the transport.
//
// The HC/DEV/LU/MS/PL evidence rows are gone: the UFS survey that they served is
// closed, and their reads (six pre-command HC registers, the descriptor chain and
// the GPT page read) existed only for those rows.  The identity row stays so a
// photograph still says which build and cid produced the boot.
#ifdef NUWA_NEON_SETUP
static unsigned neonPhase;

static bool neonBegin() {
  uint32_t enable = 0;
  if (!PE_parse_boot_argn("nuwa-ufs-neon", &enable, sizeof enable) || enable != 1) return false;
  __atomic_store_n(&neonPhase, 1U, __ATOMIC_RELEASE);
  return true;
}
#else
extern "C" unsigned nuwa_ufs_neon_rows(char rows[][120], unsigned room) {
  const unsigned phase = __atomic_load_n(&neonPhase, __ATOMIC_ACQUIRE);
  if (!phase || !room) return 0;
  snprintf(rows[0], 120, "%s s=%u old=? rsr=?", NuwaNeon::Identity, phase);
  return 1;
}
#endif
