#!/usr/bin/env python3
"""Compile and replay generated saved-state capture and X1 rendering."""
import argparse
from pathlib import Path
import re
import runpy
import subprocess
import tempfile


def section(text, start, end):
    i = text.index(start)
    return text[i:text.index(end, i)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("r35i_base", type=Path)
    args = parser.parse_args()
    gen = runpy.run_path(str(Path(__file__).with_name("generate-r35j-ux-lr.py")))
    producer = gen["generate_ux"]((args.r35i_base / "ux_exception.c").read_bytes()).decode()
    baseline = (args.r35i_base / "BootProgress.c").read_bytes()
    renderer = gen["generate_renderer"](baseline).decode()
    ex = ("  for (unsigned i=0; i<4; ++i) {\n    if (i<exit_view.count)",
          "  const struct bp_exception_entry *x=")
    assert section(renderer, *ex) == section(baseline.decode(), *ex)
    tap = section(producer, "\tif (exception > 0", "\n\tuthread_t")
    for forbidden in ("copyin", "vm_map", "get_task_map"):
        assert forbidden not in producer
    view = section(renderer, "struct bp_exception_entry {", "\n// Published so")
    writer = section(renderer, "void boot_progress_exception(", "\n}") + "\n}\n"
    row = section(renderer, ex[1], "\n  // r33:")
    core = Path(__file__).resolve().parents[1] / "package/boot-progress/BootProgressCore.h"
    cols = re.search(r"#\s*define\s+BP_COLS\s+(\d+)", core.read_text())[1]
    harness = f"#define BP_COLS {cols}\n" + r"""
#include <assert.h>
#include <limits.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
enum { EXC_BAD_ACCESS=1, EXC_BREAKPOINT=6, EXC_TYPES_COUNT=14 };
typedef struct { uint64_t pc, fp, lr; bool a64; } arm_saved_state_t;
typedef struct fixture_thread { int pid; const arm_saved_state_t *saved; const char *p_comm; } *thread_t, *proc_t;
static bool is_saved_state64(const arm_saved_state_t *s) { return s->a64; }
static uint64_t get_saved_state_fp(const arm_saved_state_t *s) { return s->fp; }
static uint64_t get_saved_state_lr(const arm_saved_state_t *s) { return s->lr; }
static uint64_t get_saved_state_pc(const arm_saved_state_t *s) { return s->pc; }
static const arm_saved_state_t *get_user_regs(thread_t t) { return t->saved; }
static int proc_pid(proc_t p) { return p->pid; }
struct bp_exit_ring_entry { int sig; };
static struct bp_exit_ring_entry exit_ring[4];
static unsigned exit_lock, exit_ring_count=1, enabled=1;
""" + view + writer + r"""
static struct bp_exception_entry deliver(thread_t thread, int exception, uint64_t code, uint64_t subcode) {
  proc_t p=thread;
""" + tap + r"""
  struct bp_exit_view v;
  assert(bp_exit_view_take(&v) && v.count==1 && v.entries[0].sig==5);
  return v.exception;
}
static char rendered[BP_COLS];
static void line(unsigned row, const char *value, uint32_t color) {
  assert(row==6 && color==0xff00ffcc && strlen(value)<=80);
  strcpy(rendered,value);
}
extern const char *nuwa_systemos_row3(void) __attribute__((weak));
static size_t paint(struct bp_exception_entry entry) {
  struct bp_exit_view exit_view={.exception=entry};
  char b[BP_COLS];
""" + row + r"""
  return strlen(rendered);
}
const char *nuwa_systemos_row3(void) { return "SYSOS"; }
int main(void) {
  arm_saved_state_t saved={.pc=0x12345678abcdef00, .fp=0x1000, .lr=0x1c586c5d4, .a64=true};
  struct fixture_thread t={.pid=26,.saved=&saved,.p_comm="SpringBoard"};
  exit_ring[0].sig=5;
  struct bp_exception_entry e=deliver(&t,EXC_BREAKPOINT,1,0x8a70);
  assert(e.regs_valid && e.regs_requested && e.pc==saved.pc && e.x29==saved.fp && e.x30==saved.lr);
  size_t normal=paint(e);
  assert(!strcmp(rendered,"X1 pid=26 t=6 c=1 s=8a70 pc=12345678abcdef00 x30=1c586c5d4"));
  t.p_comm="SpringBoardX"; e=deliver(&t,EXC_BREAKPOINT,1,0);
  assert(!e.regs_requested && !e.regs_valid); paint(e); assert(!strstr(rendered,"x30="));
  t.p_comm="SpringBoard"; e=deliver(&t,EXC_BAD_ACCESS,1,0);
  assert(!e.regs_requested && !e.regs_valid);
  t.saved=NULL; e=deliver(&t,EXC_BREAKPOINT,1,0);
  assert(e.regs_requested && !e.regs_valid); paint(e); assert(strstr(rendered,"x30=UNKNOWN"));
  t.saved=&saved; saved.a64=false; e=deliver(&t,EXC_BREAKPOINT,1,0);
  assert(e.regs_requested && !e.regs_valid);
  saved.a64=true; saved.lr=0; e=deliver(&t,EXC_BREAKPOINT,1,0);
  assert(e.regs_valid); paint(e); assert(strstr(rendered,"x30=0"));
  t.pid=INT_MAX; saved.pc=UINT64_MAX; saved.lr=UINT64_MAX;
  e=deliver(&t,EXC_BREAKPOINT,UINT64_MAX,UINT64_MAX);
  size_t worst=paint(e);
  assert(worst<=80 && e.code==UINT64_MAX && e.subcode==UINT64_MAX);
  assert(strstr(rendered,"cs16=ffff/ffff") && strstr(rendered,"x30=ffffffffffffffff"));
  printf("X1 normal=%zu worst=%zu/80 columns; EX unchanged; gates and saved registers PASS\n",normal,worst);
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
