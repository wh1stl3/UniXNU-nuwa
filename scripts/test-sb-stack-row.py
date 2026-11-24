#!/usr/bin/env python3
"""Exercise the generated nuwa-sb-stack kcdata walker and banner rows on the host.

The C under test is sliced out of the generated renderer, so the checked code is the
code that is compiled into the kernel: record bounds, container balance, BEGIN/END,
unique-id and pid identity, the SS_TH_WAIT bit test, and the row widths.
"""
import pathlib
import subprocess
import sys
import tempfile

root = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "scripts"))
from generate_r35_display_diag import BANNER_SELECTION, generate  # noqa: E402

source = (root / "out/nuwa-r35l-regs-full-20261121/BootProgress.c").read_bytes()
generated = generate(source, mg_reset=True).decode()

start = generated.index("#define BP_SHOT_BUF")
stop = generated.index("static uint8_t bp_shot_buf[")
defines = generated[start:stop]
start = generated.index("struct bp_shot_item {")
stop = generated.index("extern uint64_t proc_uniqueid")
parser = generated[start:stop]
assert "BP_SHOT_IDENTITY" in parser and "BP_SHOT_TH_WAIT" in defines
assert 'snprintf(rows[n++],120,"SHOT pending %u",shot_seq);' in generated
assert generated.index("n += bp_shot_format(rows + n") < generated.index("    for(unsigned part=0;part<4")

test = r"""
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
DEFINES
static uint8_t bp_shot_buf[BP_SHOT_BUF] __attribute__((aligned(4096)));
PARSER
SELECTOR
#define DROP_END 1
#define BAD_END_ID 2
#define TWICE 4
#define TRANSITIONING 8
#define PID_OFF 16
#define BAD_COMM 32
#define DETAILS 64
#define BAD_ARRAY 128
#define ZERO_LOAD 256
#define EMPTY_LOAD 512
#define ZERO_SC 1024
#define TAG_THREADS 2048
#define USER_PRESENCE 4096
#define FRAME_CASE 8192
static unsigned frame_case;
static unsigned char *emit(unsigned char *at, uint32_t type, uint32_t size, uint64_t flags) {
  struct bp_shot_item header;
  header.type = type; header.size = size; header.flags = flags;
  memcpy(at, &header, sizeof header);
  memset(at + sizeof header, 0, size);
  return at + sizeof header + size;
}
static unsigned char *begin_container(unsigned char *at, uint64_t id, uint32_t type) {
  unsigned char *out = emit(at, BP_SHOT_CONTAINER_BEGIN, 16, id);
  memcpy(at + sizeof(struct bp_shot_item), &type, sizeof type);
  return out;
}
static unsigned char *end_container(unsigned char *at, uint64_t id) {
  return emit(at, BP_SHOT_CONTAINER_END, 0, id);
}
static unsigned char *task_snapshot(unsigned char *at, unsigned pid, uint64_t uid, int bad_comm) {
  unsigned char *out = emit(at, BP_SHOT_TASK_SNAPSHOT, 128, 0);
  struct bp_shot_task_snapshot *task = (struct bp_shot_task_snapshot *)(at + sizeof(struct bp_shot_item));
  task->unique_pid = uid;
  task->pid = (int32_t)pid;
  memcpy(task->comm, bad_comm ? "lsdX" : "lsd", bad_comm ? 5 : 4);
  return out;
}
static unsigned char *thread_snapshot(unsigned char *at, uint32_t state, uint32_t size) {
  unsigned char *out = emit(at, BP_SHOT_THREAD_SNAPSHOT, size, 0);
  struct bp_shot_thread_snapshot *thread = (struct bp_shot_thread_snapshot *)(at + sizeof(struct bp_shot_item));
  thread->state = state;
  return out;
}
static unsigned char *words(unsigned char *at, uint32_t kind, unsigned count, unsigned stride,
    const uint64_t *values, int legacy, int bad) {
  unsigned size = (count * stride + 15) & ~15u;
  unsigned pad = size - count * stride;
  unsigned char *out = emit(at, legacy ? BP_SHOT_ARRAY : BP_SHOT_ARRAY_PAD0 + pad,
    size, ((uint64_t)kind << 32) | (count + bad));
  for (unsigned i = 0; i < count; ++i)
    memcpy(at + sizeof(struct bp_shot_item) + stride * i, &values[i], sizeof(values[i]));
  return out;
}
// One ordinary task container with one task snapshot and nthreads thread containers.
static unsigned build(unsigned pid, uint64_t uid, const unsigned *states, unsigned nthreads,
    uint32_t thread_size, int variant) {
  unsigned char *at = bp_shot_buf;
  at = emit(at, BP_SHOT_BEGIN, 0, 0);
  uint64_t sc = variant & ZERO_SC ? 0 : 0x31323334;
  unsigned char *sc_item = at;
  at = emit(at, BP_SHOT_SHAREDCACHE_LOADINFO, 48, 0);
  memcpy(sc_item + sizeof(struct bp_shot_item), &sc, sizeof sc);
  at = begin_container(at, uid, (variant & TRANSITIONING) ? BP_SHOT_TRANSITIONING_TASK : BP_SHOT_TASK_CONTAINER);
  at = task_snapshot(at, pid + ((variant & PID_OFF) ? 1 : 0), uid, variant & BAD_COMM);
  if (variant & (DETAILS | ZERO_LOAD | EMPTY_LOAD | ZERO_SC)) {
    ((struct bp_shot_task_snapshot *)(at - 128))->ss_flags = BP_SHOT_SHARED_SYSTEM;
    const uint64_t base[] = {variant & ZERO_LOAD ? 0 : 0x104123000};
    if (variant & (DETAILS | ZERO_LOAD | EMPTY_LOAD))
      at = words(at, BP_SHOT_LOADINFO64, variant & EMPTY_LOAD ? 0 : 1, 24, base, 0,
        variant & BAD_ARRAY ? 1 : 0);
  }
  for (unsigned i = 0; i < nthreads; ++i) {
    at = begin_container(at, 0x9000u + i, BP_SHOT_THREAD_CONTAINER);
    at = thread_snapshot(at, states[i], thread_size);
    if (variant & TAG_THREADS)
      ((struct bp_shot_thread_snapshot *)(at - thread_size))->continuation = 0xfffffff007020000ULL + 4 * i;
    if (variant & USER_PRESENCE) {
      const uint64_t zero[] = {0};
      if (i == 1 || i == 2) at = words(at, BP_SHOT_USER_STACKLR64, i - 1, 8, zero, 0, 0);
      if (i == 3) ((struct bp_shot_thread_snapshot *)(at - thread_size))->ss_flags = BP_SHOT_TRUNC_USER;
    }
    if ((variant & FRAME_CASE) && i == 0) {
      uint64_t values[35];
      for (unsigned j = 0; j < 35; ++j) values[j] = 0x100000000ULL + j;
      at = words(at, BP_SHOT_USER_STACKLR64, frame_case, 8, values, 0, 0);
    }
    if ((variant & DETAILS) && i == 0) {
      ((struct bp_shot_thread_snapshot *)(at - thread_size))->continuation = 0xfffffff00700cafeULL;
      const uint64_t lr[] = {0x104123450, 0x18123abcd, 0x192340008, 0x11234000c, 0x202020204};
      at = words(at, BP_SHOT_USER_STACKLR64, 5, 8, lr, 0, 0);
    }
    if ((variant & DETAILS) && i == 1) {
      const uint64_t kern[] = {0xfffffff007123456ULL, 0xfffffff007abcdefULL, 0xfffffff007abcdefULL};
      const uint64_t user[] = {0x104dead00, 0x104dead04};
      ((struct bp_shot_thread_snapshot *)(at - thread_size))->ss_flags = BP_SHOT_TRUNC_USER;
      at = words(at, BP_SHOT_KERN_STACKLR64, 3, 8, kern, 0, 0);
      at = words(at, BP_SHOT_USER_STACKFRAME64, 2, 16, user, 1, 0);
    }
    at = end_container(at, 0x9000u + i);
  }
  at = end_container(at, (variant & BAD_END_ID) ? uid + 1 : uid);
  if (variant & TWICE) {
    at = begin_container(at, uid, BP_SHOT_TASK_CONTAINER);
    at = task_snapshot(at, pid, uid, 0);
    at = end_container(at, uid);
  }
  if (!(variant & DROP_END)) at = emit(at, BP_SHOT_END, 0, 0);
  return (unsigned)(at - bp_shot_buf);
}
static void check_rows(char rows[][120], unsigned n) {
  for (unsigned i = 0; i < n; ++i) {
    printf("%zu: %s\n", strlen(rows[i]), rows[i]);
    assert(strlen(rows[i]) <= 78);
  }
}
int main(void) {
  const unsigned mixed[2] = {1u, 4u};      /* queueing for wait, running */
  const unsigned waiting[1] = {1u};
  const unsigned running[1] = {4u};
  const unsigned two_waiting[2] = {1u, 1u};
  const unsigned run_then_wait[5] = {4u, 1u, 1u, 1u, 1u};
  const unsigned four_waiting[4] = {1u, 1u, 1u, 1u};
  struct bp_shot_sample s;
  unsigned bytes;
  char rows[48][120];
#define PARSE(n) bp_shot_parse(170, 0x1234, (n), &s)
  const unsigned cases[] = {0, 1, 4, 5, 12, 35};
  for (unsigned c = 0; c < 6; ++c) {
    frame_case = cases[c];
    bytes = build(170, 0x1234, waiting, 1, 128, FRAME_CASE);
    assert(PARSE(bytes) == 0 && s.threads[0].users == frame_case);
    unsigned n = bp_shot_format(rows, &s, 0, 0, 0);
    unsigned kept = frame_case < 12 ? frame_case : 12;
    assert(n == 5u + (kept > 4) + (kept > 8));
    for (unsigned j = 0; j < kept; ++j) assert(s.threads[0].user[j] == 0x100000000ULL + j);
    if (kept > 4) assert(!strncmp(rows[5], "T0+4 U=", 7));
    if (kept > 8) assert(!strncmp(rows[6], "T0+8 U=", 7));
    if (kept == 5) assert(!strcmp(rows[5], "T0+4 U=100000004"));
    printf("CASE %u\n", frame_case);
    for (unsigned j = 0; j < n; ++j) printf("%zu: %s\n", strlen(rows[j]), rows[j]);
    for (unsigned j = 0; j < n; ++j) assert(strlen(rows[j]) <= 78);
  }
  {
    char budget_rows[64][120] = {
      "SHOT lsd", "T0 C=x", "T0+4 U=x", "T0+8 U=x",
      "SHOT2 x", "EXIT x", "XR x", "PROC x", "SVC x", "SC x",
      "LOAD x", "UFS x", "SCHED x", "SU x"
    };
    unsigned n = bp_banner_select(budget_rows, 14, 12);
    assert(n == 12);
    assert(!strcmp(budget_rows[2], "T0+4 U=x"));
    assert(!strcmp(budget_rows[3], "T0+8 U=x"));
  }
  {
    char full[64][120];
    frame_case = 35;
    bytes = build(170, 0x1234, four_waiting, 4, 128, FRAME_CASE);
    assert(PARSE(bytes) == 0);
    for (unsigned i = 1; i < 4; ++i) {
      s.threads[i] = s.threads[0];
    }
    unsigned n = bp_shot_format(full, &s, 0x100000000ULL, 0, 0);
    const char *extra[] = {"EXIT a", "EXIT b", "EXIT c", "XR x", "PROC n=6",
      "SVC x", "SC n=12", "SC +0", "LOAD x", "UFS x", "SCHED x",
      "SS x", "SU x", "FB x", "SWAP x", "GPU1 x", "GPU2 x",
      "GPU3 x", "GPU4 x", "GPU5 x", "GPU6 x", "GPU7 x", "GPU8 x"};
    for (unsigned i = 0; i < sizeof(extra)/sizeof(extra[0]); ++i)
      snprintf(full[n++], 120, "%s", extra[i]);
    for (unsigned i = 0; i < 10; ++i)
      snprintf(full[n++], 120, "PROC  detail%u", i);
    assert(n > 24);
    n = bp_banner_select(full, n, 24);
    const char *must[] = {"SHOT lsd", "SHOT2 ", "T0 ", "T0+4 ", "T0+8 ",
      "EXIT a", "EXIT b", "EXIT c", "PROC n=", "SC n=", "SC +", "LOAD "};
    for (unsigned i = 0; i < sizeof(must)/sizeof(must[0]); ++i) {
      int found = 0;
      for (unsigned j = 0; j < n; ++j)
        if (!strncmp(full[j], must[i], strlen(must[i]))) found = 1;
      assert(found);
    }
    unsigned proc_details = 0;
    for (unsigned j = 0; j < n; ++j)
      if (!strncmp(full[j], "PROC  detail", 12)) ++proc_details;
    assert(proc_details == 10);
    for (unsigned j = 0; j < n; ++j) assert(strlen(full[j]) <= 78);
    printf("full banner 35 frames: T0 main/+4/+8 and required rows retained\n");
  }
  bytes = build(170, 0x1234, mixed, 2, 128, TAG_THREADS);
  assert(PARSE(bytes) == 0);
  assert(s.total == 2 && s.wait == 1);
  assert(bp_shot_format(rows, &s, 0, 0, 0) == 5);
  assert(!strcmp(rows[0], "SHOT lsd n=2 w=1 r=0 ks=00000000 sc=- sb=-"));
  assert(!strcmp(rows[1], "T0 C=fffffff007020000 U=- f=-"));
  assert(!strcmp(rows[2], "T1 -") && !strcmp(rows[3], "T2 -") && !strcmp(rows[4], "T3 -"));
  check_rows(rows, 5);
  bytes = build(170, 0x1234, run_then_wait, 5, 128, TAG_THREADS);
  assert(PARSE(bytes) == 0 && s.total == 5 && s.wait == 4);
  assert(bp_shot_format(rows, &s, 0, 0, 0) == 5);
  assert(!strcmp(rows[1], "T0 C=fffffff007020004 U=- f=-"));
  assert(!strcmp(rows[2], "T1 C=fffffff007020008 U=- f=-"));
  assert(!strcmp(rows[3], "T2 C=fffffff00702000c U=- f=-"));
  assert(!strcmp(rows[4], "T3 C=fffffff007020010 U=- f=-"));
  check_rows(rows, 5);
  bytes = build(170, 0x1234, four_waiting, 4, 128, USER_PRESENCE | EMPTY_LOAD | ZERO_SC);
  assert(PARSE(bytes) == 0 && !s.have_binary && s.have_cache && s.cache_slide == 0);
  assert(bp_shot_format(rows, &s, 0, 0, 0) == 5);
  assert(!strcmp(rows[0], "SHOT lsd n=4 w=4 r=0 ks=00000000 sc=00000000 sb=-"));
  assert(!strcmp(rows[1], "T0 K=-,- U=- f=-"));
  assert(!strcmp(rows[2], "T1 K=-,- U=- f=0"));
  assert(!strcmp(rows[3], "T2 K=-,- U=000000000 f=1"));
  assert(!strcmp(rows[4], "T3 K=-,- U=- f=-!"));
  check_rows(rows, 5);
  bytes = build(170, 0x1234, waiting, 1, 128, ZERO_LOAD);
  assert(PARSE(bytes) == 0 && s.have_binary && s.binary_base == 0);
  assert(bp_shot_format(rows, &s, 0x123456789ULL, 0, 0) == 6);
  assert(!strcmp(rows[0], "SHOT lsd n=1 w=1 r=0 ks=23456789 sc=31323334 sb=0!"));
  assert(!strcmp(rows[5], "SHOT2 ks=0000000123456789 sb=0!"));
  check_rows(rows, 6);
  bytes = build(170, 0x1234, two_waiting, 2, 128, DETAILS);
  assert(PARSE(bytes) == 0);
  assert(bp_shot_format(rows, &s, 0x123456789ULL, 0, 0) == 7);
  assert(!strcmp(rows[0], "SHOT lsd n=2 w=2 r=0 ks=23456789 sc=31323334 sb=04123000"));
  assert(!strcmp(rows[1], "T0 C=fffffff00700cafe U=104123450,18123abcd,192340008,11234000c f=5!"));
  assert(!strcmp(rows[2], "T1 K=f007123456,f007abcdef U=104dead00,104dead04 f=2!"));
  assert(!strcmp(rows[5], "SHOT2 ks=0000000123456789 sb=0000000104123000"));
  check_rows(rows, 7);
  strcpy(rows[7], "CRASH excerpt");
  assert(bp_banner_select(rows, 8, 7) == 7 && !strncmp(rows[2], "SHOT2 ", 6));
  s.cache_slide = 0x20031323334ULL;
  s.threads[1].users = 131072;  /* upper bound from the size of the capture buffer */
  assert(bp_shot_format(rows, &s, 0, 0, 1) == 9);
  assert(!strcmp(rows[5], "SHOT2 ks=0000000000000000 sb=0000000104123000 sc=0000020031323334"));
  assert(strlen(rows[2]) == 78);
  check_rows(rows, 9);
  bytes = build(170, 0x1234, mixed, 2, 128, DETAILS | BAD_ARRAY);
  s.total = s.wait = 0xdead;
  assert(PARSE(bytes) == BP_SHOT_INTEGRITY && s.total == 0xdead && s.wait == 0xdead);
  bytes = build(170, 0x1234, running, 1, 128, 0);
  assert(PARSE(bytes) == 0);
  assert(s.total == 1 && s.wait == 0);
  bytes = build(170, 0x1234, waiting, 1, 112, 0);   /* v2 padded / v3 */
  assert(PARSE(bytes) == 0);
  assert(s.total == 1 && s.wait == 1);
  /* Integrity failures: nothing may be published. */
  bytes = build(170, 0x1234, mixed, 2, 128, DROP_END);
  s.total = s.wait = 0xdead;
  assert(PARSE(bytes) == BP_SHOT_INTEGRITY);
  assert(s.total == 0xdead && s.wait == 0xdead);
  bytes = build(170, 0x1234, mixed, 2, 128, BAD_END_ID);
  assert(PARSE(bytes) == BP_SHOT_INTEGRITY);
  assert(s.total == 0xdead && s.wait == 0xdead);
  bytes = build(170, 0x1234, mixed, 2, 120, 0);     /* unknown thread record size */
  assert(PARSE(bytes) == BP_SHOT_INTEGRITY);
  /* Identity failures: PID reuse, exec copy, transitioning, duplicate task, name. */
  bytes = build(170, 0x1234, mixed, 2, 128, TWICE);
  assert(PARSE(bytes) == BP_SHOT_IDENTITY);
  assert(s.total == 0xdead && s.wait == 0xdead);
  bytes = build(170, 0x1234, mixed, 2, 128, TRANSITIONING);
  assert(PARSE(bytes) == BP_SHOT_IDENTITY);
  bytes = build(170, 0x1234, mixed, 2, 128, PID_OFF);
  assert(PARSE(bytes) == BP_SHOT_IDENTITY);
  bytes = build(170, 0x1234, mixed, 2, 128, BAD_COMM);
  assert(PARSE(bytes) == BP_SHOT_IDENTITY);
  bytes = build(170, 0x1234, mixed, 2, 128, 0);
  assert(bp_shot_parse(170, 0x5678, bytes, &s) == BP_SHOT_IDENTITY);  /* uid mismatch */
  /* Truncation is caught by the bounds check. */
  assert(PARSE(8) == BP_SHOT_INTEGRITY);
  assert(bp_banner_priority("SHOT pending 1",2) == 0);
  printf("kcdata walker, identity, wait bit and rows: PASS\n");
  return 0;
}
""".replace("DEFINES", defines).replace("PARSER", parser).replace(
    "SELECTOR", BANNER_SELECTION.decode())

with tempfile.TemporaryDirectory() as directory:
    path = pathlib.Path(directory) / "test.c"
    executable = pathlib.Path(directory) / "test"
    path.write_text(test)
    subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-Wno-type-limits",
                    str(path), "-o", str(executable)], check=True)
    subprocess.run([str(executable)], check=True)
