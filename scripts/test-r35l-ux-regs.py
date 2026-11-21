#!/usr/bin/env python3
"""Replay the generated exception tap, ring and diagnostic rows as host C."""
import argparse
from pathlib import Path
import re
import runpy
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("r35i_base", type=Path)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    section = runpy.run_path(str(here / "test-r35j-ux-lr.py"))["section"]
    gen = runpy.run_path(str(here / "generate-r35l-ux-regs.py"))
    producer = gen["generate_ux"]((args.r35i_base / "ux_exception.c").read_bytes()).decode()
    baseline = (args.r35i_base / "BootProgress.c").read_bytes()
    renderer = gen["generate_renderer"](baseline).decode()
    ex = ("  for (unsigned i=0; i<4; ++i) {\n    if (i<exit_view.count)",
          "  const struct bp_exception_entry *x=")
    assert section(renderer, *ex) == section(baseline.decode(), *ex)
    tap = section(producer, "\tif (exception == EXC_BREAKPOINT", "\n\tuthread_t")
    for forbidden in ("copyin", "copyout", "vm_map", "get_task_map", "backtrace"):
        assert forbidden not in tap
    view = section(renderer, "struct bp_exception_entry {", "\n// Published so")
    writer = section(renderer, "void boot_progress_exception(", "\n}") + "\n}\n"
    rows = section(renderer, ex[1], "\n  // r33:")
    core = here.parent / "package/boot-progress/BootProgressCore.h"
    cols = re.search(r"#\s*define\s+BP_COLS\s+(\d+)", core.read_text())[1]
    harness = f"#define BP_COLS {cols}\n" + r"""
#include <assert.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
enum { EXC_BAD_ACCESS=1, EXC_BREAKPOINT=6 };
typedef struct { uint64_t x[29]; } arm_saved_state64_t;
typedef struct { arm_saved_state64_t ss64; uint64_t pc; int a64; } arm_saved_state_t;
typedef struct fixture_thread { int pid; const arm_saved_state_t *saved; const char *p_comm; } *thread_t, *proc_t;
static int is_saved_state64(const arm_saved_state_t *s) { return s->a64; }
static unsigned register_reads;
static const arm_saved_state64_t *const_saved_state64(const arm_saved_state_t *s) {
  assert(s->a64);
  ++register_reads;
  return &s->ss64;
}
static uint64_t get_saved_state_pc(const arm_saved_state_t *s) { return s->pc; }
static const arm_saved_state_t *get_user_regs(thread_t t) { return t->saved; }
static int proc_pid(proc_t p) { return p->pid; }
struct bp_exit_ring_entry { int sig; };
static struct bp_exit_ring_entry exit_ring[4];
static unsigned exit_lock, exit_ring_count=1, enabled=1;
""" + view + writer + r"""
static struct bp_exit_view deliver(thread_t thread, int exception, uint64_t code, uint64_t subcode) {
  proc_t p=thread;
""" + tap + r"""
  struct bp_exit_view v;
  assert(bp_exit_view_take(&v) && v.count==1 && v.entries[0].sig==5);
  return v;
}
static char rendered[3][BP_COLS];
static void line(unsigned row, const char *value, uint32_t color) {
  assert(row>=6 && row<=8 && color==0xff00ffcc && strlen(value)<=80);
  strcpy(rendered[row-6],value);
}
extern const char *nuwa_systemos_row3(void) __attribute__((weak));
static void paint(struct bp_exit_view exit_view) {
  char b[BP_COLS];
  memset(rendered,0,sizeof(rendered));
""" + rows + r"""
}
const char *nuwa_systemos_row3(void) { return "SYSOS"; }
int main(void) {
  arm_saved_state_t saved={.pc=0x12345678abcd0ca8, .a64=1, .ss64.x={
    [1]=0x1111222233334444, [2]=0x2222333344445555, [19]=0x193456789abcdef0,
    [20]=0x203456789abcdef0, [21]=0x213456789abcdef0, [22]=0xfedcba9876543210}};
  struct fixture_thread t={.pid=26,.saved=&saved,.p_comm="SpringBoardX"};
  exit_ring[0].sig=5;
  paint(deliver(&t,EXC_BREAKPOINT,UINT64_MAX,UINT64_MAX));
  assert(!strcmp(rendered[0],"SYSOS") && !*rendered[1] && !*rendered[2]);
  t.p_comm="SpringBoard";
  deliver(&t,EXC_BAD_ACCESS,1,2);
  saved.pc ^= 1;
  deliver(&t,EXC_BREAKPOINT,1,2);
  saved.pc ^= 1;
  t.saved=NULL;
  deliver(&t,EXC_BREAKPOINT,1,2);
  t.saved=&saved; saved.a64=0;
  deliver(&t,EXC_BREAKPOINT,1,2);
  assert(exception_next==0 && register_reads==0);
  saved.a64=1;
  const uint64_t x0[]={0,7,0x0000000161234568};
  const char *x2[]={
    "X2 x0=0000000000000000 x19=193456789abcdef0 x20=203456789abcdef0",
    "X2 x0=0000000000000007 x19=193456789abcdef0 x20=203456789abcdef0",
    "X2 x0=0000000161234568 x19=193456789abcdef0 x20=203456789abcdef0"};
  for (unsigned i=0; i<3; ++i) {
    saved.ss64.x[0]=x0[i];
    struct bp_exit_view v=deliver(&t,EXC_BREAKPOINT,1,0x8a70);
    assert(exception_next==i+1 && register_reads==i+1 && v.exception.regs[0]==x0[i]);
    paint(v);
    assert(!strcmp(rendered[0],"X1 pid=26 t=6 c=1 s=8a70 pc=12345678abcd0ca8"));
    assert(!strcmp(rendered[1],x2[i]) && strlen(rendered[1])==64);
    assert(!strcmp(rendered[2],
      "X3 1/2/21/22=1111222233334444/2222333344445555/213456789abcdef0/fedcba9876543210"));
    assert(strlen(rendered[2])==80);
  }
  t.pid=INT_MAX; saved.pc=0xfffffffffffffca8;
  paint(deliver(&t,EXC_BREAKPOINT,UINT64_MAX,UINT64_MAX));
  assert(!strcmp(rendered[0],"X1 pid=2147483647 t=6 c=ffffffffffffffff s=ffffffffffffffff pc=fffffffffffffca8"));
  assert(exception_next==0 && register_reads==4);
  paint(deliver(&t,EXC_BAD_ACCESS,0,0));
  assert(exception_next==0 && register_reads==4 && !strcmp(rendered[1],x2[2]));
  printf("X1/X2/X3 max test widths: %zu/%zu/%zu of 80; EX unchanged; capture and gates PASS\n",
         strlen(rendered[0]),strlen(rendered[1]),strlen(rendered[2]));
}
"""
    with tempfile.TemporaryDirectory() as tmp:
        c = Path(tmp) / "replay.c"
        c.write_text(harness)
        exe = c.with_suffix("")
        subprocess.run(["cc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                        str(c), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == "__main__":
    main()
