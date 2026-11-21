#!/usr/bin/env python3
"""Compile and replay the generated LR walk, ring writer and X1 row."""
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
    base_renderer = (args.r35i_base / "BootProgress.c").read_bytes()
    renderer = gen["generate_renderer"](base_renderer).decode()
    ex = ("  for (unsigned i=0; i<4; ++i) {\n    if (i<exit_view.count)",
          "  const struct bp_exception_entry *x=")
    assert section(renderer, *ex) == section(base_renderer.decode(), *ex)
    walk = section(producer, "static unsigned\nnuwa_breakpoint_lr(", "\n/*")
    tap = section(producer, "\tif (exception > 0", "\n\tuthread_t")
    view = section(renderer, "struct bp_exception_entry {", "\n// Published so")
    writer = section(renderer, "void boot_progress_exception(", "\n}") + "\n}\n"
    row = section(renderer, ex[1], "\n  // r33:")
    # Use the buffer width of the actual renderer, not a larger harness buffer.
    core = Path(__file__).resolve().parents[1] / "package/boot-progress/BootProgressCore.h"
    cols = re.search(r"#\s*define\s+BP_COLS\s+(\d+)", core.read_text())[1]
    harness = f"#define BP_COLS {cols}\n" + r"""
#include <assert.h>
#include <limits.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

enum { EXC_BAD_ACCESS=1, EXC_BREAKPOINT=6, EXC_TYPES_COUNT=14, KERN_SUCCESS=0 };
typedef uint64_t user_addr_t;
typedef struct { uint64_t pc, fp; bool a64; } arm_saved_state_t;
typedef struct { uint64_t prev, lr; } record_t;
typedef struct {
  uint64_t min, max;
  bool kernel, active;
  unsigned refs;
  record_t frame[4];
  bool readable[4];
} fixture_map_t, *vm_map_t;
typedef struct fixture_thread {
  int pid;
  const arm_saved_state_t *saved;
  const char *p_comm;
  vm_map_t map;
} *thread_t, *proc_t;

#define VM_MAP_NULL NULL
static unsigned copies, maps;
static bool interrupts=true;
static vm_map_t active_map, expected_map;
static bool ml_get_interrupts_enabled(void) { return interrupts; }
static bool is_saved_state64(const arm_saved_state_t *s) { return s->a64; }
static uint64_t get_saved_state_fp(const arm_saved_state_t *s) { return s->fp; }
static uint64_t get_saved_state_pc(const arm_saved_state_t *s) { return s->pc; }
static const arm_saved_state_t *get_user_regs(thread_t t) { return t->saved; }
static int proc_pid(proc_t p) { return p->pid; }
static vm_map_t get_threadtask(thread_t t) { return t->map; }
static vm_map_t get_task_map_reference(vm_map_t m) {
  ++maps;
  if (!m->active) return NULL;
  ++m->refs;
  return m;
}
static bool vm_map_get_pmap(vm_map_t m) { return m->kernel; }
static bool pmap_kernel(void) { return true; }
static void vm_map_deallocate(vm_map_t m) { assert(m->refs==1); --m->refs; }
static vm_map_t current_map(void) { return active_map; }
static vm_map_t vm_map_switch(vm_map_t m) {
  vm_map_t old=active_map;
  active_map=m;
  return old;
}
static int copyin(uint64_t fp, void *dest, size_t len) {
  vm_map_t m=current_map();
  assert(m==expected_map && !m->kernel && m->refs==1 && len==16 && !(fp&15));
  ++copies;
  if (fp<m->min || fp>=m->max || m->max-fp<len) return 1;
  uint64_t index=(fp-m->min)/16;
  if (index>=4 || !m->readable[index]) {
    memset(dest, 0xff, 8); /* Do not consume partial data on error. */
    return 1;
  }
  memcpy(dest, &m->frame[index], len);
  return KERN_SUCCESS;
}
struct bp_exit_ring_entry { int sig; };
static struct bp_exit_ring_entry exit_ring[4];
static unsigned exit_lock, exit_ring_count=1, enabled=1;
""" + walk + view + writer + r"""
static struct bp_exception_entry deliver(thread_t thread, int exception, uint64_t code, uint64_t subcode) {
  proc_t p=thread;
""" + tap + r"""
  struct bp_exit_view exit_view;
  assert(bp_exit_view_take(&exit_view) && exit_view.count==1 && exit_view.entries[0].sig==5);
  return exit_view.exception;
}

static char rendered[BP_COLS];
static void line(unsigned row, const char *value, uint32_t color) {
  assert(row==6 && color==0xff00ffcc && strlen(value)<=1440/(6*3));
  strcpy(rendered, value);
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
  arm_saved_state_t saved={.pc=0x12345678abcdef00, .fp=0x1000, .a64=true};
  struct fixture_thread t={.pid=26, .saved=&saved, .p_comm="SpringBoard"};
  struct bp_exception_entry e;
  fixture_map_t caller_map={0};
  active_map=&caller_map;
  t.map=expected_map=&(fixture_map_t){
    .min=0x1000, .max=0x2000, .active=true,
    .frame={{0x1010,0x1c586c5d4},{0x1020,0x1c586c790},{0x1030,0xfff},{0,0x444}},
    .readable={true,true,true,true}
  };
  exit_ring[0].sig=5;
  e=deliver(&t,EXC_BREAKPOINT,1,0x8a70);
  assert(copies==3 && e.lr_requested && e.lr_count==3 && !t.map->refs && active_map==&caller_map);
  assert(e.lr[0]==0x1c586c5d4 && e.lr[1]==0x1c586c790 && e.lr[2]==0xfff);
  size_t normal=paint(e);
  assert(!strcmp(rendered,"X1 pid=26 t=6 c=1 s=8a70 pc=12345678abcdef00 lr=1c586c5d4"));
  saved.fp=0x1010;
  paint(deliver(&t,EXC_BREAKPOINT,1,0x8a70));
  assert(!strcmp(rendered,"X1 pid=26 t=6 c=1 s=8a70 pc=12345678abcdef00 lr=1c586c790"));

  copies=0; saved.fp=0x1000; t.map->frame[0].prev=0x1018;
  e=deliver(&t,EXC_BREAKPOINT,1,0);
  assert(copies==1 && e.lr_count==1 && !e.lr[1] && !e.lr[2]);
  copies=0; t.map->frame[0].prev=saved.fp;
  e=deliver(&t,EXC_BREAKPOINT,1,0);
  assert(copies==1 && e.lr_count==1 && !e.lr[1]);
  copies=0; t.map->frame[0].prev=0x1010; t.map->readable[1]=false;
  e=deliver(&t,EXC_BREAKPOINT,1,0);
  assert(copies==2 && e.lr_count==1 && !e.lr[1] && !t.map->refs && active_map==&caller_map);
  copies=0; saved.fp=0x1010;
  e=deliver(&t,EXC_BREAKPOINT,1,0);
  assert(copies==1 && e.lr_count==0 && e.lr_requested && !t.map->refs);
  paint(e);
  assert(strstr(rendered,"lr=UNKNOWN"));

  copies=0; saved.fp=0x1008;
  assert(!deliver(&t,EXC_BREAKPOINT,1,0).lr_count && copies==0);
  saved.fp=0xfffffffffffffff0ULL;
  assert(!deliver(&t,EXC_BREAKPOINT,1,0).lr_count && copies==1);
  copies=0; saved.fp=0x1000; t.map->kernel=true;
  assert(!deliver(&t,EXC_BREAKPOINT,1,0).lr_count && copies==0 && !t.map->refs);
  t.map->kernel=false; t.map->active=false;
  assert(!deliver(&t,EXC_BREAKPOINT,1,0).lr_count && copies==0 && !t.map->refs);
  t.map->active=true; t.map->frame[0].lr=0;
  assert(!deliver(&t,EXC_BREAKPOINT,1,0).lr_count && copies==1);

  copies=maps=0; t.p_comm="SpringBoardX";
  e=deliver(&t,EXC_BREAKPOINT,1,0);
  assert(!e.lr_requested && copies==0 && maps==0);
  paint(e);
  assert(!strstr(rendered," lr="));
  t.p_comm="SpringBoard";
  assert(!deliver(&t,EXC_BAD_ACCESS,1,0).lr_requested && maps==0);
  t.saved=NULL;
  assert(!deliver(&t,EXC_BREAKPOINT,1,0).lr_count && maps==0);
  t.saved=&saved; saved.a64=false;
  assert(!deliver(&t,EXC_BREAKPOINT,1,0).lr_count && maps==0);
  saved.a64=true; interrupts=false;
  assert(!deliver(&t,EXC_BREAKPOINT,1,0).lr_count && maps==0);

  interrupts=true; t.pid=INT_MAX; saved.pc=UINT64_MAX; t.map->frame[0].lr=UINT64_MAX;
  active_map=t.map;
  e=deliver(&t,EXC_BREAKPOINT,UINT64_MAX,UINT64_MAX);
  size_t worst=paint(e);
  assert(worst==80 && e.code==UINT64_MAX && e.subcode==UINT64_MAX && active_map==t.map);
  assert(strstr(rendered,"cs24=ffffff/ffffff") && strstr(rendered,"lr=ffffffffffffffff"));
  printf("X1 row 6: normal %zu cols, worst %zu cols / %zu pixels; EX rows 2-5 unchanged\n",
      normal,worst,worst*18);
  puts("valid, damaged, self-linked, unreadable, alignment, user-map and capture gates: PASS");
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
