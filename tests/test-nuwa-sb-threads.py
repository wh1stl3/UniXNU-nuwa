"""Compile the real sampler and paint helper with host XNU/framebuffer fixtures."""
import argparse
import os
from pathlib import Path
import re
import runpy
import subprocess
import sys
import tempfile
import tomllib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from generate_nuwa_postevent import DRAW_END_ANCHOR, SBTH_DECL, SBTH_PAINT

C = r"""
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define NUWA_SB_THREADS 1
#include "NuwaSbThreads.h"

typedef struct {
  struct { uint64_t pc, lr, sp; unsigned cpsr; } regs;
  bool narrow;
} arm_saved_state_t;
typedef __typeof__(((arm_saved_state_t *)0)->regs) arm_saved_state64_t;
typedef struct mock_thread {
  arm_saved_state_t saved;
  unsigned refs;
  bool missing;
} *thread_t;
typedef struct {
  struct mock_thread thread[SBTH_LIMIT + 1];
  unsigned entries, refs;
  uint64_t gone;
} *task_t;
typedef struct { char p_comm[17]; int p_pid, p_stat; task_t task; } *proc_t;
#define TASK_NULL NULL
#define THREAD_NULL NULL
#define PSR64_IS_USER64(cpsr) (((cpsr) & 0x1c) == 0)
#define PROC_RETURNED 0
#define PROC_RETURNED_DONE 1
#define PROC_ALLPROCLIST 1
#define PROC_NOWAITTRANS 2
static uint64_t nuwa_sb_public;
static __typeof__(*(proc_t)0) targets[2];
static unsigned find_calls, refs_live;
static void proc_iterate(unsigned flags, int (*cb)(proc_t, void *), void *arg,
                         void *filter, void *filterarg) {
  assert(flags == 3 && !filter && !filterarg);
  assert(cb(&targets[0], arg) == PROC_RETURNED);
  if (targets[1].p_comm[0]) assert(cb(&targets[1], arg) == PROC_RETURNED_DONE);
}
static task_t proc_task(proc_t p) { return p->task; }
static void task_reference(task_t task) { ++task->refs; }
static void task_deallocate(task_t task) {
  assert(task->refs == 1 && !refs_live);
  --task->refs;
}
static int fill_taskthreadlist(task_t task, uint64_t *ids, int size, bool unique) {
  assert(task->refs == 1 && unique);
  unsigned n = task->entries < (unsigned)size ? task->entries : (unsigned)size;
  for (unsigned i = 0; i < n; ++i) ids[i] = i + 1;
  return n * sizeof(ids[0]);
}
static thread_t task_findtid(task_t task, uint64_t tid) {
  assert(task->refs == 1 && tid > 0 && tid <= task->entries);
  ++find_calls;
  if (tid == task->gone) return NULL;
  ++task->thread[tid - 1].refs;
  ++refs_live;
  return &task->thread[tid - 1];
}
static void thread_deallocate(thread_t t) { assert(t->refs-- == 1); --refs_live; }
static arm_saved_state_t *get_user_regs(thread_t t) { return t->missing ? NULL : &t->saved; }
static bool is_saved_state64(const arm_saved_state_t *s) { return !s->narrow; }
static const arm_saved_state64_t *const_saved_state64(const arm_saved_state_t *s) {
  return &s->regs;
}

static struct { uintptr_t frame; unsigned scale, stride, width, height, bound, yield_requested; }
    display = { 1, 3, 5760, 1440, 3200, 1, 0 };
#define BP_COLS 120
static unsigned painted_y[5], painted, painted_empty;
static void px_text(unsigned x, unsigned y, const char *s, unsigned cols,
                    uint32_t fg, uint32_t bg) {
  assert(!x && cols == 80 && fg && bg && painted < 5);
  painted_y[painted++] = y;
  if (!s[0]) ++painted_empty;
}
"""

CASES = r"""
static char rows[5][120];
static void one(const char *expected) {
  nuwa_sb_sample();
  assert(nuwa_sbth_rows(rows, 5) == 1);
  assert(!strcmp(rows[0], expected));
}
int main(void) {
  __typeof__(*(task_t)0) task = { 0 };
  strcpy(targets[0].p_comm, "SpringBoardUI");
  targets[0].task = &task;
  one("SBTH none");
  assert(!nuwa_sb_public && !find_calls && !task.refs);
  strcpy(targets[1].p_comm, "SpringBoard");
  targets[1].p_pid = 26;
  targets[1].p_stat = 2;
  one("SBTH denied"); /* no task */
  targets[1].task = &task;
  one("SBTH denied"); /* task disappeared / empty */
  task.entries = SBTH_LIMIT + 1;
  one("SBTH denied"); /* explicit bound, no partial totals */
  assert(!find_calls && !task.refs);
  task.entries = SBTH_LIMIT;
  for (unsigned i = 0; i < task.entries; ++i) {
    thread_t t = &task.thread[i];
    unsigned group = (i % 4 == 0) ? 0 : i % 7 + 1;
    t->saved.regs = (arm_saved_state64_t){ 0x10000 + group, 0x20000 + i, 0x30000 + i, 0 };
  }
  nuwa_sb_sample();
  assert(!refs_live && !task.refs && find_calls == 128);
  assert(nuwa_sbth_rows(rows, 5) == 5);
  assert(!strcmp(rows[0], "SBTH n=128"));
  assert(!strcmp(rows[1], "SBTH pc=10000 x32 non-atomic lr=20000 sp=30000"));
  assert(strstr(rows[2], "pc=10001 x14") && strstr(rows[3], "pc=10002 x14") &&
         strstr(rows[4], "pc=10003 x14"));
  for (unsigned i = 1; i < 5; ++i) assert(strstr(rows[i], " non-atomic "));
  assert(nuwa_sbth_rows(rows, 2) == 2);
  assert(nuwa_sbth_rows(NULL, 0) == 0);
  bp_sbth_paint(0);
  assert(painted == 5 && painted_y[0] == 0 && painted_y[1] == 2016 &&
         painted_y[4] == 2142 && !painted_empty);
  painted = 0;
  display.bound = 0;
  bp_sbth_paint(0);
  assert(!painted);
  bp_sbth_paint(1);
  assert(painted == 1 && painted_y[0] == 0);
  display.bound = 1;
  display.yield_requested = 1;
  painted = 0;
  bp_sbth_paint(0);
  assert(!painted);
  display.yield_requested = 0;
  display.height = 2016;
  painted = 0;
  bp_sbth_paint(0);
  assert(painted == 1);
  display.height = 3200;
  task.gone = 20;
  one("SBTH denied");
  task.gone = 0;
  task.thread[2].missing = true;
  one("SBTH denied");
  task.thread[2].missing = false;
  task.thread[2].saved.narrow = true;
  one("SBTH denied");
  task.thread[2].saved.narrow = false;
  task.thread[2].saved.regs.cpsr = 4;
  one("SBTH denied");
  task.thread[2].saved.regs.cpsr = 0;
  task.thread[2].saved.regs.pc = 0;
  one("SBTH denied");
  targets[1].p_comm[0] = '\0';
  one("SBTH none");
  assert(nuwa_sb_public == (1ull << 63) && !refs_live && !task.refs);
  painted = painted_empty = 0;
  bp_sbth_paint(0);
  assert(painted == 5 && painted_empty == 4);
  ++sbth_snapshot.seq; /* panic interrupted the single writer */
  assert(nuwa_sbth_rows(rows, 5) == 1 && !strcmp(rows[0], "SBTH denied"));
  return 0;
}
"""


def fixture():
    source = (ROOT / "package/nuwa-systemos/nuwa_systemos.c").read_text()
    walk = source[source.index("struct nuwa_sb_local {"):source.index("void\nnuwa_pid1_sample(void)")]
    with tempfile.TemporaryDirectory(prefix="nuwa-sbth-") as tmp:
        src, exe = Path(tmp) / "fixture.c", Path(tmp) / "fixture"
        src.write_text(C + walk + SBTH_PAINT.decode() + CASES)
        subprocess.run([os.getenv("CC", "cc"), "-std=gnu11", "-O2", "-Wall", "-Wextra", "-Werror",
                        "-I", str(ROOT / "package/nuwa-systemos"), src, "-o", exe], check=True)
        subprocess.run([exe], check=True)
    print("SBTH host fixtures: none, exact identity, 128 threads, top four, denied, panic/geometry")


def audit(build, baseline):
    renderer = (build / "BootProgress.c").read_bytes()
    for part in (SBTH_DECL, SBTH_PAINT, b"  bp_sbth_paint(1);\n",
                 b"  if(!__atomic_load_n(&display.yield_requested,__ATOMIC_ACQUIRE)) bp_sbth_paint(0);\n"):
        assert renderer.count(part) == 1
        renderer = renderer.replace(part, b"", 1)
    assert renderer == baseline.read_bytes() and DRAW_END_ANCHOR in renderer
    obj = build / "nuwa_systemos.o"
    assert not re.search(r"^\s*U _thread_info$", subprocess.check_output(
        ["llvm-nm", "-u", obj], text=True), re.M)
    asm = subprocess.check_output(["llvm-objdump", "--macho", "--disassemble", obj], text=True)
    # Bound the audit to the new collection body, not unrelated VFS code in this TU.
    sample = re.split(r"\n_[\w.]+:\n", asm.split("\n_nuwa_sbth_sample:\n", 1)[1], 1)[0]
    calls = set(re.findall(r"\bb(?:l)?\s+(_[\w.]+)", sample))
    expected = {"_fill_taskthreadlist", "_task_findtid", "_get_user_regs",
                "_thread_deallocate", "_task_deallocate_grp"}
    allowed = expected | {"_bzero", "_memset", "_sbth_publish", "___stack_chk_fail"}
    assert expected <= calls <= allowed, calls
    assert not re.search(r"\b(?:blr|br|msr|svc|hvc|smc)\s", sample)
    (build / "sbth-sample.disasm.txt").write_text(sample)
    kernel = build / "kernel.macho"
    symbols = subprocess.check_output(["llvm-nm", "-P", kernel], text=True)
    assert re.search(r"^_nuwa_sbth_rows [ST] ", symbols, re.M)
    linked = subprocess.check_output(["llvm-objdump", "-d", "--disassemble-symbols="
                                      "_nuwa_pid1_sample,_nuwa_sb_cb,_nuwa_sbth_sample,_get_user_regs",
                                      kernel], text=True)
    linked_sample = re.split(r"\n[0-9a-f]+ <", linked.split("<_nuwa_sbth_sample>:\n", 1)[1], 1)[0]
    linked_calls = set(re.findall(r"\bb(?:l)?\s+0x[0-9a-f]+\s+<(_[\w.]+)>", linked_sample))
    assert "_thread_info" not in linked and expected <= linked_calls <= allowed, linked_calls
    assert re.search(r"\bbl\s+0x[0-9a-f]+\s+<_nuwa_sbth_sample>", linked)
    assert not re.search(r"\b(?:blr|br|msr|svc|hvc|smc)\s", linked_sample)
    pcb = re.split(r"\n[0-9a-f]+ <", linked.split("<_get_user_regs>:\n", 1)[1], 1)[0]
    assert re.search(r"\bldr\s+x0,\s*\[x0,", pcb) and not re.search(r"\bstr\b", pcb)
    (build / "sbth-linked.disasm.txt").write_text(linked)
    print("SBTH linked ARM64 call allowlist (no _thread_info):", ", ".join(sorted(linked_calls)))


def audit_outer(package, baseline):
    helpers = runpy.run_path(str(ROOT / "scripts/package-nuwa-crashcap.py"))
    old = helpers["pinned"](baseline, "8d77f769bbc23ce7eb4c93957fe6bd2bb47ee22509dd5cc59c3d8beecb1fcca7")
    old_head, old_fat, old_tail = helpers["regions"](old)
    new_head, new_fat, new_tail = helpers["regions"](package.read_bytes())
    assert (old_head, old_tail) == (new_head, new_tail)
    parser = helpers["OLD"] / "audit2.py"
    text = helpers["pinned"](parser, "9c482847481bfd9d2794bf469f8dfac9f99cf988286e893488360fdb4c85e582")
    ns = {"__file__": str(parser)}
    exec(compile(text.split(b"def main():", 1)[0], str(parser), "exec"), ns)
    before, after = (helpers["files"](ns["FAT32"](fat)) for fat in (old_fat, new_fat))
    assert before.keys() == after.keys()
    assert {path for path in before if before[path] != after[path]} == {helpers["KERNEL"], helpers["ADT"]}
    entry, = (e for e in tomllib.loads(after[helpers["CONFIG"]].decode())["entry"] if e["id"] == "xnu")
    assert len(entry["args"].encode()) == 602
    print("SBTH outer vs no-glyph: kernel and ADT only; header/tail, args, seed and trust unchanged")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--outer", type=Path)
    parser.add_argument("--baseline-outer", type=Path)
    args = parser.parse_args()
    fixture()
    if args.build:
        audit(args.build, args.baseline)
    if args.outer:
        audit_outer(args.outer, args.baseline_outer)
