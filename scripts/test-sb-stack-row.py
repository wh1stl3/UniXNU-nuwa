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
assert 'snprintf(rows[n++],120,"SHOT %s %u"' in generated
assert 'snprintf(rows[n++],120,"SHOT n=- w=- r=%u%s",shot_rc,to);' in generated
assert 'snprintf(rows[n++],120,"SHOT n=%u w=%u r=0%s",bp_shot_total,bp_shot_wait,to);' in generated

test = r"""
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
DEFINES
#define BP_SHOT_THREAD_CONTAINER 0x904u
static uint8_t bp_shot_buf[BP_SHOT_BUF] __attribute__((aligned(4096)));
PARSER
SELECTOR
#define DROP_END 1
#define BAD_END_ID 2
#define TWICE 4
#define TRANSITIONING 8
#define PID_OFF 16
#define BAD_COMM 32
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
  memcpy(task->comm, bad_comm ? "SpringBoardX" : "SpringBoard", 12);
  return out;
}
static unsigned char *thread_snapshot(unsigned char *at, uint32_t state, uint32_t size) {
  unsigned char *out = emit(at, BP_SHOT_THREAD_SNAPSHOT, size, 0);
  struct bp_shot_thread_snapshot *thread = (struct bp_shot_thread_snapshot *)(at + sizeof(struct bp_shot_item));
  thread->state = state;
  return out;
}
// One ordinary task container with one task snapshot and nthreads thread containers.
static unsigned build(unsigned pid, uint64_t uid, const unsigned *states, unsigned nthreads,
    uint32_t thread_size, int variant) {
  unsigned char *at = bp_shot_buf;
  at = emit(at, BP_SHOT_BEGIN, 0, 0);
  at = begin_container(at, uid, (variant & TRANSITIONING) ? BP_SHOT_TRANSITIONING_TASK : BP_SHOT_TASK_CONTAINER);
  at = task_snapshot(at, pid + ((variant & PID_OFF) ? 1 : 0), uid, variant & BAD_COMM);
  for (unsigned i = 0; i < nthreads; ++i) {
    at = begin_container(at, 0x9000u + i, BP_SHOT_THREAD_CONTAINER);
    at = thread_snapshot(at, states[i], thread_size);
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
int main(void) {
  const unsigned mixed[2] = {1u, 4u};      /* queueing for wait, running */
  const unsigned waiting[1] = {1u};
  const unsigned running[1] = {4u};
  unsigned total = 0xdead, wait = 0xdead, bytes;
  bytes = build(170, 0x1234, mixed, 2, 128, 0);
  assert(bp_shot_parse(170, 0x1234, bytes, &total, &wait) == 0);
  assert(total == 2 && wait == 1);
  bytes = build(170, 0x1234, running, 1, 128, 0);
  total = wait = 0xdead;
  assert(bp_shot_parse(170, 0x1234, bytes, &total, &wait) == 0);
  assert(total == 1 && wait == 0);
  bytes = build(170, 0x1234, waiting, 1, 112, 0);   /* v2 padded / v3 */
  total = wait = 0xdead;
  assert(bp_shot_parse(170, 0x1234, bytes, &total, &wait) == 0);
  assert(total == 1 && wait == 1);
  /* Integrity failures: nothing may be published. */
  bytes = build(170, 0x1234, mixed, 2, 128, DROP_END);
  total = wait = 0xdead;
  assert(bp_shot_parse(170, 0x1234, bytes, &total, &wait) == BP_SHOT_INTEGRITY);
  assert(total == 0xdead && wait == 0xdead);
  bytes = build(170, 0x1234, mixed, 2, 128, BAD_END_ID);
  total = wait = 0xdead;
  assert(bp_shot_parse(170, 0x1234, bytes, &total, &wait) == BP_SHOT_INTEGRITY);
  assert(total == 0xdead && wait == 0xdead);
  bytes = build(170, 0x1234, mixed, 2, 120, 0);     /* unknown thread record size */
  assert(bp_shot_parse(170, 0x1234, bytes, &total, &wait) == BP_SHOT_INTEGRITY);
  /* Identity failures: PID reuse, exec copy, transitioning, duplicate task, name. */
  bytes = build(170, 0x1234, mixed, 2, 128, TWICE);
  total = wait = 0xdead;
  assert(bp_shot_parse(170, 0x1234, bytes, &total, &wait) == BP_SHOT_IDENTITY);
  assert(total == 0xdead && wait == 0xdead);
  bytes = build(170, 0x1234, mixed, 2, 128, TRANSITIONING);
  assert(bp_shot_parse(170, 0x1234, bytes, &total, &wait) == BP_SHOT_IDENTITY);
  bytes = build(170, 0x1234, mixed, 2, 128, PID_OFF);
  assert(bp_shot_parse(170, 0x1234, bytes, &total, &wait) == BP_SHOT_IDENTITY);
  bytes = build(170, 0x1234, mixed, 2, 128, BAD_COMM);
  assert(bp_shot_parse(170, 0x1234, bytes, &total, &wait) == BP_SHOT_IDENTITY);
  bytes = build(170, 0x1234, mixed, 2, 128, 0);
  assert(bp_shot_parse(170, 0x5678, bytes, &total, &wait) == BP_SHOT_IDENTITY);  /* uid mismatch */
  /* Truncation is caught by the bounds check. */
  assert(bp_shot_parse(170, 0x1234, 8, &total, &wait) == BP_SHOT_INTEGRITY);
  /* Banner rows: measured widths and the SHOT priority class. */
  char row[120];
  unsigned lengths[4], at = 0;
  snprintf(row,sizeof row,"SHOT pending %u",255u);
  lengths[at++] = (unsigned)strlen(row);
  snprintf(row,sizeof row,"SHOT done %u",255u);
  lengths[at++] = (unsigned)strlen(row);
  snprintf(row,sizeof row,"SHOT n=- w=- r=%u%s",1002u," to");
  lengths[at++] = (unsigned)strlen(row);
  snprintf(row,sizeof row,"SHOT n=%u w=%u r=0%s",4294967295u,4294967295u," to");
  lengths[at++] = (unsigned)strlen(row);
  for (unsigned i = 0; i < at; ++i) {
    printf("row width %u\n", lengths[i]);
    assert(lengths[i] <= 80);
  }
  {
    char ordered[48][120];
    memset(ordered, 0, sizeof ordered);
    strcpy(ordered[0], "SHOT done 1");
    strcpy(ordered[1], "CRASH x");
    assert(bp_banner_select(ordered, 2, 2) == 2);
    assert(!strcmp(ordered[0], "CRASH x") && !strcmp(ordered[1], "SHOT done 1"));
  }
  assert(bp_banner_priority("SHOT done 1",2) == 1);
  assert(bp_banner_priority("SHOT n=1 w=1 r=0",0) == 1);
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
