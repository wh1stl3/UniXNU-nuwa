#!/usr/bin/env python3
"""Exercise the paint-confirmation gate of nuwa-sb-stack on the host.

The arm/take/gate/publish code is sliced verbatim out of the generated renderer, so
the state machine under test is the one compiled into the kernel, with only the
architectural counter, the proc lookups and the stackshot call stubbed.
"""
import pathlib
import sys
import tempfile
import subprocess

root = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "scripts"))
from generate_r35_display_diag import generate  # noqa: E402

generated = generate((root / "out/nuwa-r35l-regs-full-20261121/BootProgress.c").read_bytes(),
                     mg_reset=True).decode()

# The four ways a pass can skip the pending row all return before the row loop.
assert generated.count("bp_shot_paint_row(r);") == 1
assert generated.count("static void bp_shot_paint_row(const char *row)") == 2  # prototype, definition
touch = generated.index("static void touch_overlay(void) {")
assert generated.index("if(__atomic_exchange_n(&render_busy,1,__ATOMIC_ACQUIRE))return;", touch) < \
    generated.index("crash_banner(seconds());", touch), "render_busy return must precede the banner"
banner = generated.index("static void crash_banner(unsigned now) {")
assert generated.index("now-banner_second<2)return;", banner) < generated.index("bp_shot_paint_row(r);")
assert generated.index("if(signature==banner_signature)return;", banner) < \
    generated.index("bp_shot_paint_row(r);")
assert generated.index("n=bp_banner_select(rows,n,budget);", banner) < \
    generated.index("bp_shot_paint_row(r);")
assert generated.index("if(__atomic_load_n(&display.yield_requested,__ATOMIC_ACQUIRE))return;\n"
                       "    const char *r=rows[i];\n    bp_shot_paint_row(r);", banner) > 0
assert "bp_shot_beat,__ATOMIC_ACQUIRE)*131071ULL" in generated

state = generated[generated.index("#define BP_SHOT_BUF"):generated.index("static uint32_t bp_proc_pid[6]")]
portable = generated[generated.index("struct bp_shot_item {"):
                     generated.index("static uint64_t bp_shot_ticks(void)")]
take_at = generated.index("static void bp_shot_take(unsigned now) {")
take = generated[take_at:generated.index("\n}\n", take_at) + 3]
assert "bp_shot_may_call()" in take and "stack_snapshot_from_kernel" in take

test = r"""
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <assert.h>
typedef int kern_return_t;
#define KERN_SUCCESS 0
#define KERN_LOCK_OWNED 40
#define KERN_INSUFFICIENT_BUFFER_SIZE 52
#define STACKSHOT_KCDATA_FORMAT 0x10000
#define STACKSHOT_TRYLOCK 0x100000
#define STACKSHOT_SAVE_LOADINFO 0x02
struct proc { int unused; };
static struct proc shot_proc;
static int shot_proc_found = 1;
struct proc *proc_find(int pid) { (void)pid; return shot_proc_found ? &shot_proc : NULL; }
int proc_rele(struct proc *p) { (void)p; return 0; }
void proc_name(int pid, char *out, int cap) { (void)pid; snprintf(out, (size_t)cap, "lsd"); }
uint64_t proc_uniqueid(struct proc *p) { (void)p; return 0x1234; }
static uint32_t bp_proc_pid[6];
static uint64_t bp_shot_ticks(void);
static uint64_t bp_shot_frequency(void);
static unsigned build_valid(unsigned char *buf, unsigned pid, uint64_t uid);
static unsigned shot_calls, shot_rc, shot_valid;
static uint64_t shot_flags;
kern_return_t stack_snapshot_from_kernel(int pid, void *buf, uint32_t size, uint64_t flags,
    uint64_t delta, uint32_t mask, unsigned *bytes) {
  assert(size == (1u << 20) && delta == 0 && mask == 0);
  ++shot_calls;
  shot_flags = flags;
  *bytes = shot_valid ? build_valid(buf, (unsigned)pid, 0x1234) : 0;
  return shot_rc;
}
STATE
PORTABLE
TAKE
#define DROP_END 1
#define BAD_END_ID 2
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
static unsigned build_valid(unsigned char *buf, unsigned pid, uint64_t uid) {
  unsigned char *at = buf;
  at = emit(at, BP_SHOT_BEGIN, 0, 0);
  at = begin_container(at, uid, BP_SHOT_TASK_CONTAINER);
  at = emit(at, BP_SHOT_TASK_SNAPSHOT, 128, 0);
  struct bp_shot_task_snapshot *task = (struct bp_shot_task_snapshot *)(at - 128);
  task->unique_pid = uid; task->pid = (int32_t)pid; memcpy(task->comm, "lsd", 4);
  at = begin_container(at, 0x9001u, 0x904u);
  at = emit(at, BP_SHOT_THREAD_SNAPSHOT, 128, 0);
  ((struct bp_shot_thread_snapshot *)(at - 128))->state = 1u;
  at = emit(at, BP_SHOT_CONTAINER_END, 0, 0x9001u);
  at = emit(at, BP_SHOT_CONTAINER_END, 0, uid);
  at = emit(at, BP_SHOT_END, 0, 0);
  return (unsigned)(at - buf);
}
static uint64_t bp_shot_ticks(void) { static uint64_t t = 1000; return t += 19200; }
static uint64_t bp_shot_frequency(void) { return 19200000; }
static void reset(unsigned now) {
  shot_calls = 0; shot_rc = 0; shot_valid = 0; shot_proc_found = 1;
  bp_proc_pid[2] = 170;
  bp_shot_beat = 0; bp_shot_armed = 0; bp_shot_pending_seq = 0; bp_shot_painted = 0;
  bp_shot_seq = 0;
  bp_shot_rc = 0; bp_shot_to = 0;
  memset(&bp_shot_result, 0, sizeof(bp_shot_result));
  bp_shot_arm(now);
}
int main(void) {
  /* Four passes that never reach bp_shot_paint_row: render_busy taken, the two-second
     throttle, the row clipped by the budget, and a yield before that row. From the
     gate's side all four are "no paint record", so no call may happen. */
  const char *skipped[] = {"render busy", "throttled", "clipped", "yielded before row"};
  for (unsigned i = 0; i < 4; ++i) {
    reset(100);
    assert((bp_shot_beat >> 8) == 1 && (bp_shot_beat & 255u) == 1u);
    assert(bp_shot_may_call() == 0);
    bp_shot_take(101);
    assert(shot_calls == 0);
    assert(bp_shot_armed == 1);                 /* still waiting for the paint */
    bp_shot_take(159);                           /* under the wait bound */
    assert(shot_calls == 0 && bp_shot_armed == 1);
    bp_shot_take(160);                           /* gives up, never calls */
    assert(shot_calls == 0 && bp_shot_armed == 0);
    assert(bp_shot_rc == BP_SHOT_NO_PAINT && (bp_shot_beat & 255u) == 3u);
    printf("%-20s -> stackshot calls 0, rc %u\n", skipped[i], bp_shot_rc);
  }
  /* A pass that really painted the pending row: exactly one call, then never again. */
  reset(100);
  bp_shot_paint_row("SHOT pending 0");           /* stale text cannot confirm the new seq */
  assert(bp_shot_may_call() == 0);
  bp_shot_paint_row(bp_shot_pending_row);
  assert(bp_shot_may_call() == 1);
  shot_valid = 1;
  bp_shot_take(101);
  assert(shot_calls == 1);
  assert(shot_flags == (uint64_t)(STACKSHOT_KCDATA_FORMAT | STACKSHOT_TRYLOCK | STACKSHOT_SAVE_LOADINFO));
  assert(bp_shot_rc == 0 && bp_shot_result.total == 1 && bp_shot_result.wait == 1);
  assert((bp_shot_beat & 255u) == 2u);
  bp_shot_take(102);
  bp_shot_take(200);
  assert(shot_calls == 1);                       /* same sequence is never called twice */
  printf("painted            -> stackshot calls 1, n=1 w=1\n");
  /* A non-zero return: one fail, no retry, and no counts are published. */
  reset(100);
  bp_shot_paint_row(bp_shot_pending_row);
  shot_rc = KERN_LOCK_OWNED;
  bp_shot_take(101);
  assert(shot_calls == 1);
  assert(bp_shot_rc == KERN_LOCK_OWNED && bp_shot_result.total == 0 && bp_shot_result.wait == 0);
  assert((bp_shot_beat & 255u) == 3u);
  bp_shot_take(102);
  bp_shot_take(300);
  assert(shot_calls == 1);
  printf("lock owned         -> stackshot calls 1, rc %u, no counts, no retry\n", bp_shot_rc);
  reset(100);
  bp_shot_paint_row(bp_shot_pending_row);
  shot_rc = KERN_INSUFFICIENT_BUFFER_SIZE;
  bp_shot_take(101);
  bp_shot_take(102);
  assert(shot_calls == 1 && bp_shot_rc == 52 && (bp_shot_beat & 255u) == 3u);
  char rows[6][120];
  assert(bp_shot_format(rows, &bp_shot_result, 0, bp_shot_rc, bp_shot_to) == 1);
  assert(!strcmp(rows[0], "SHOT lsd n=- w=- r=52 ks=- sc=- sb=-"));
  printf("capacity error     -> %zu columns, one row, no retry\n", strlen(rows[0]));
  /* An unresolvable process arms nothing and never calls. */
  reset(100);
  shot_proc_found = 0;
  bp_shot_pending_seq = 0; bp_shot_armed = 0;
  bp_shot_seq = 0; bp_shot_beat = 0;
  bp_shot_arm(100);
  assert(bp_shot_armed == 0 && bp_shot_rc == BP_SHOT_NO_PID);
  bp_shot_paint_row("SHOT pending 1");
  bp_shot_take(101);
  assert(shot_calls == 0);
  printf("no lsd     -> stackshot calls 0, rc %u\n", bp_shot_rc);
  printf("paint-confirmation gate: PASS\n");
  return 0;
}
""".replace("STATE", state).replace("PORTABLE", portable).replace("TAKE", take)

with tempfile.TemporaryDirectory() as directory:
    path = pathlib.Path(directory) / "test.c"
    executable = pathlib.Path(directory) / "test"
    path.write_text(test)
    subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-Wno-type-limits",
                    "-Wno-unused-function", str(path), "-o", str(executable)], check=True)
    subprocess.run([str(executable)], check=True)
