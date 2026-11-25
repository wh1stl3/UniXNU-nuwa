"""Inject the opt-in, lsd-only saved-register recorder and banner rows."""
from hashlib import sha256

from generate_r35_display_diag import replace_once

UX_SHA = "df306fd79bf6af2827485eab4f2f8bb644ed1d986c7421217b8c012454eb32b1"
HANDLER_SHA = "f467f4441893103ee5efa6b7775c0be5104eefb52508276ae950d84caeae4791"
PROTOTYPE = b"""void boot_progress_lsd_crash(int pid, unsigned sig, uint64_t code,
    uint64_t pc, uint64_t lr, uint64_t sp, uint64_t fp, uint64_t fa, uint64_t k)"""
CAPTURE = b"""void nuwa_ux_capture_lsd(thread_t thread, int pid, unsigned sig, uint64_t code, uint64_t fa)"""
HOOK = b"""	/* Record the final BSD signal and the target's kernel-saved user state. */
	if (ux_signal != 0 && !strncmp(p->p_comm, "lsd", sizeof("lsd"))) {
		nuwa_ux_capture_lsd(thread, proc_pid(p), (unsigned)ux_signal,
		    (uint64_t)code, exception == EXC_BAD_ACCESS ? (uint64_t)subcode : 0);
	}

"""


def generate_ux(src):
    if sha256(src).hexdigest() != UX_SHA:
        raise ValueError("r35l ux_exception.c pin mismatch")
    src = replace_once(src, b"#include <arm/thread.h>\n",
                       b"#include <arm/thread.h>\n\nextern " + CAPTURE + b";\n")
    return replace_once(src, b"\t/* Send signal to thread */",
                        HOOK + b"\t/* Send signal to thread */")


def generate_handler(src):
    if sha256(src).hexdigest() != HANDLER_SHA:
        raise ValueError("ux_handler.c pin mismatch")
    anchor = b"#include <libkern/section_keywords.h>\n"
    return replace_once(src, anchor, anchor + b"""#include <arm/thread.h>
#include <vm/vm_kern.h>

extern """ + PROTOTYPE + b";\n" + CAPTURE + b";\n\n" + CAPTURE + b"""
{
	const arm_saved_state_t *saved = get_user_regs(thread);
	boot_progress_lsd_crash(pid, sig, code,
	    saved ? get_saved_state_pc(saved) : 0,
	    saved ? get_saved_state_lr(saved) : 0,
	    saved ? get_saved_state_sp(saved) : 0,
	    saved ? get_saved_state_fp(saved) : 0, fa,
	    VM_KERNEL_UNSLIDE(thread->continuation));
}
""")


RECORDER = b"""
enum { BP_CR_FREE, BP_CR_WRITING, BP_CR_VALID, BP_CR_MASK = 3 };
#define BP_CR_FIELDS(F) F(pid) F(sig) F(code) F(pc) F(lr) F(sp) F(fp) F(fa) F(k)
struct bp_cr_data {
#define BP_CR_FIELD(f) uint64_t f;
  BP_CR_FIELDS(BP_CR_FIELD)
#undef BP_CR_FIELD
};
// State is the low pair of bits; CAS includes the generation to reject ABA.
// A single SC order for metadata and payload makes the bracketed read a
// snapshot; merely using acquire on both metadata reads would not suffice.
static struct bp_cr_slot {
  uint64_t metadata;
  struct bp_cr_data data;
} bp_cr_slots[2];
static uint64_t bp_cr_wr_seq, bp_cr_dropped;
#define BP_CR_LOAD(p) __atomic_load_n((p), __ATOMIC_SEQ_CST)
#define BP_CR_STORE(p, v) __atomic_store_n((p), (v), __ATOMIC_SEQ_CST)

static int bp_cr_claim(struct bp_cr_slot *slot, uint64_t expected) {
  return __atomic_compare_exchange_n(&slot->metadata, &expected,
      (expected & ~(uint64_t)BP_CR_MASK) | BP_CR_WRITING, 0,
      __ATOMIC_SEQ_CST, __ATOMIC_SEQ_CST);
}

static struct bp_cr_slot *bp_cr_reserve(void) {
  for (unsigned round = 0; round < 2; ++round) {
    for (unsigned i = 0; i < 2; ++i)
      if (bp_cr_claim(&bp_cr_slots[i], BP_CR_FREE)) return &bp_cr_slots[i];
    uint64_t oldest = UINT64_MAX;
    unsigned victim = 0;
    for (unsigned i = 0; i < 2; ++i) {
      uint64_t m = BP_CR_LOAD(&bp_cr_slots[i].metadata);
      if ((m & BP_CR_MASK) == BP_CR_VALID && m < oldest) {
        oldest = m;
        victim = i;
      }
    }
    if (oldest != UINT64_MAX && bp_cr_claim(&bp_cr_slots[victim], oldest))
      return &bp_cr_slots[victim];
  }
  return NULL;
}

""" + PROTOTYPE + b";\n" + PROTOTYPE + b""" {
  struct bp_cr_slot *slot = bp_cr_reserve();
  if (!slot) {
    __atomic_fetch_add(&bp_cr_dropped, 1, __ATOMIC_SEQ_CST);
    return;
  }
#define BP_CR_PUT(f) BP_CR_STORE(&slot->data.f, f);
  BP_CR_FIELDS(BP_CR_PUT)
#undef BP_CR_PUT
  uint64_t gen = __atomic_fetch_add(&bp_cr_wr_seq, 1, __ATOMIC_SEQ_CST) + 1;
  BP_CR_STORE(&slot->metadata, (gen << 2) | BP_CR_VALID); // release publication
}

enum { BP_CR_EMPTY, BP_CR_STABLE, BP_CR_TORN };
static int bp_cr_read(struct bp_cr_slot *slot, struct bp_cr_data *out, uint64_t *gen) {
  for (unsigned attempt = 0; attempt < 3; ++attempt) {
    uint64_t before = BP_CR_LOAD(&slot->metadata);
    if (before == BP_CR_FREE) return BP_CR_EMPTY; // free is never restored
    if ((before & BP_CR_MASK) != BP_CR_VALID) continue;
#define BP_CR_GET(f) out->f = BP_CR_LOAD(&slot->data.f);
    BP_CR_FIELDS(BP_CR_GET)
#undef BP_CR_GET
    if (before == BP_CR_LOAD(&slot->metadata)) {
      *gen = before >> 2;
      return BP_CR_STABLE;
    }
  }
  return BP_CR_TORN;
}
#undef BP_CR_FIELDS

static unsigned bp_cr_rows(char rows[][120], unsigned budget) {
  struct bp_cr_data data[2];
  uint64_t gen[2] = {0};
  int a = bp_cr_read(&bp_cr_slots[0], &data[0], &gen[0]);
  int b = bp_cr_read(&bp_cr_slots[1], &data[1], &gen[1]);
  unsigned long long dr = BP_CR_LOAD(&bp_cr_dropped);
  int torn = a == BP_CR_TORN || b == BP_CR_TORN;
  if (a != BP_CR_STABLE && b != BP_CR_STABLE) {
    if (!budget || (!torn && !dr)) return 0;
    snprintf(rows[0],120,"CR %sdr=%llu",torn ? "torn " : "",dr);
    return 1;
  }
  if (budget < 4) return 0;
  unsigned latest = gen[1] > gen[0];
  const struct bp_cr_data *s = &data[latest];
  // BSD signal numbers fit seven bits (same width as the exit banner).
  snprintf(rows[0],120,"CR p%u lsd sig=%u code=%llx dr=%llu%s",
      (unsigned)s->pid,(unsigned)s->sig&127u,(unsigned long long)s->code,dr,torn ? " torn" : "");
  snprintf(rows[1],120,"CR+ pc=%016llx lr=%016llx",
      (unsigned long long)s->pc,(unsigned long long)s->lr);
  snprintf(rows[2],120,"CR+ sp=%016llx fp=%016llx",
      (unsigned long long)s->sp,(unsigned long long)s->fp);
  snprintf(rows[3],120,"CR+ fa=%016llx k=%016llx",
      (unsigned long long)s->fa,(unsigned long long)s->k);
  if (budget < 5 || a != BP_CR_STABLE || b != BP_CR_STABLE) return 4;
  s = &data[latest ^ 1];
  snprintf(rows[4],120,"CR2 p%u lsd sig=%u pc=%016llx",
      (unsigned)s->pid,(unsigned)s->sig&127u,(unsigned long long)s->pc);
  return 5;
}

static int bp_cr_check_yield(unsigned row, unsigned cr) {
  // After starting the group, finish its three continuation rows before
  // yielding. The existing render_busy owner keeps the frame mapped.
  return row == 0 || row >= 4 || cr < 4;
}
"""

GEOMETRY = b"""  unsigned cell=14*display.scale,cols=display.width/(6*display.scale);if(cols>119)cols=119;
  unsigned half=display.height/2;
  if(half<8+2*cell)return;
  unsigned budget=(half-8)/cell-2;
  if(budget>24)budget=24;
"""


def generate_banner(src):
    anchor = b"static void crash_banner(unsigned now) {"
    src = replace_once(src, anchor, RECORDER + anchor)
    src = replace_once(src, GEOMETRY + b"  n=bp_banner_select(rows,n,budget);",
                       b"  n=cr+bp_banner_select(rows+cr,n-cr,budget-cr);")
    src = replace_once(src, b"  char rows[64][120];unsigned n=0;",
                       GEOMETRY + b"  char rows[64][120];\n"
                       b"  unsigned cr=bp_cr_rows(rows,budget),n=cr;")
    anchor = b"  if(signature==banner_signature)return;"
    src = replace_once(src, anchor, b"""  signature+=BP_CR_LOAD(&bp_cr_slots[0].metadata)*524287ULL
      +BP_CR_LOAD(&bp_cr_slots[1].metadata)*1048573ULL+BP_CR_LOAD(&bp_cr_dropped)*2097143ULL;
""" + anchor)
    return replace_once(src, b"""    if(__atomic_load_n(&display.yield_requested,__ATOMIC_ACQUIRE))return;
    const char *r=rows[i];""", b"""    if(bp_cr_check_yield(i,cr) && __atomic_load_n(&display.yield_requested,__ATOMIC_ACQUIRE))return;
    const char *r=rows[i];""")
