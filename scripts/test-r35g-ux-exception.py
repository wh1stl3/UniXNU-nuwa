#!/usr/bin/env python3
"""Replay the generated conversion/tap/snapshot/row with synthetic host inputs."""
import argparse
import importlib.util
from pathlib import Path
import subprocess
import tempfile


def extract(source, start, end):
    i = source.index(start)
    return source[i:source.index(end, i)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("ux_base", type=Path)
    parser.add_argument("renderer_base", type=Path)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("ux", Path(__file__).with_name("generate-r35g-ux-exception.py"))
    ux = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ux)
    producer = ux.generate_ux(args.ux_base.read_bytes()).decode()
    renderer = ux.generate_renderer(args.renderer_base.read_bytes()).decode()
    view = extract(renderer, "struct bp_exception_entry {", "\n// Published so")
    writer = extract(renderer, "void boot_progress_exception(", "\n}")
    convert = extract(producer, "static int\nux_exception(", "\n/*\n * Sends")
    tap = extract(producer, "\tint ux_signal = ux_exception(", "\n\tuthread_t")
    row = extract(renderer, "  const struct bp_exception_entry *x=", "\n  else line(5")
    harness = r"""
#include <assert.h>
#include <limits.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

enum {
  EXC_BAD_ACCESS=1, EXC_BAD_INSTRUCTION=2, EXC_ARITHMETIC=3, EXC_EMULATION=4,
  EXC_SOFTWARE=5, EXC_BREAKPOINT=6, EXC_SYSCALL=7, EXC_TYPES_COUNT=14,
  EXC_UNIX_BAD_SYSCALL=1, EXC_UNIX_BAD_PIPE=2, EXC_UNIX_ABORT=3, EXC_SOFT_SIGNAL=4,
  KERN_INVALID_ADDRESS=1
};
#define SIGEMT 7
typedef int64_t mach_exception_code_t, mach_exception_subcode_t;
typedef struct { uint64_t pc; } arm_saved_state_t;
typedef struct fixture_thread { int pid; arm_saved_state_t *saved; } *thread_t, *proc_t;
static const arm_saved_state_t *get_user_regs(thread_t t) { return t->saved; }
static uint64_t get_saved_state_pc(const arm_saved_state_t *s) { return s->pc; }
static int proc_pid(proc_t p) { return p->pid; }
static int send_sigsys, machine_result;
static int machine_exception(int t, int64_t c, int64_t s) { (void)t; (void)c; (void)s; return machine_result; }

struct bp_exit_ring_entry { int sig; };
static struct bp_exit_ring_entry exit_ring[4];
static unsigned exit_lock, exit_ring_count, enabled=1;
""" + view + writer + "\n}\n" + convert + r"""
static int deliver(thread_t thread, int exception, int64_t code, int64_t subcode) {
  proc_t p=thread;
""" + tap + r"""
  return ux_signal;
}

static char rendered[256];
static void line(unsigned row, const char *text, uint32_t color) {
  assert(row==5 && color==0xff00ffcc);
  strcpy(rendered,text);
}
extern const char *nuwa_systemos_row3(void) __attribute__((weak));
static void paint(struct bp_exit_view exit_view) {
  char b[256];
""" + row + r"""
  else line(5,"",0xff00ffcc);
}
const char *nuwa_systemos_row3(void) { return "SYSOS"; }
int main(void) {
  arm_saved_state_t saved={0x12345678abcdef00ULL};
  struct bp_exit_view before,trap,other,live;
  struct fixture_thread target={26,&saved};
  thread_t t=&target;
  assert(deliver(t,0,0,0)==0);
  assert(bp_exit_view_take(&before) && !before.exception.type && exception_next==0);
  paint(before);
  assert(!strcmp(rendered,"SYSOS"));

  exit_ring[0].sig=SIGTRAP;
  exit_ring_count=1;
  assert(deliver(t,EXC_BREAKPOINT,1,0x8a70)==SIGTRAP);
  assert(bp_exit_view_take(&trap) && trap.count==1 && trap.entries[0].sig==SIGTRAP);
  paint(trap);
  assert(!strcmp(rendered,"X1 pid=26 t=6 c=1 s=8a70 pc=12345678abcdef00"));
  size_t bp_width=strlen(rendered);

  target.pid=99999; saved.pc=UINT64_MAX;
  machine_result=SIGBUS;
  assert(deliver(t,EXC_BAD_ACCESS,-1,-1)==SIGBUS);
  assert(bp_exit_view_take(&other));
  paint(other);
  assert(!strcmp(rendered,"X1 pid=99999 t=1 c=ffffffffffffffff s=ffffffffffffffff pc=ffffffffffffffff"));
  size_t pid_max_width=strlen(rendered);
  target.pid=INT_MAX;
  deliver(t,EXC_TYPES_COUNT-1,-1,-1);  /* All supported types fit one hex digit. */
  assert(bp_exit_view_take(&live));
  paint(live);
  size_t max_width=strlen(rendered);
  assert(pid_max_width==74 && max_width==79 && max_width<=1440/(6*3));

  target.saved=NULL;
  deliver(t,EXC_BAD_ACCESS,1,2);
  assert(bp_exit_view_take(&live));
  paint(live);
  assert(strstr(rendered,"pc=-"));
  target.saved=&saved; saved.pc=0;
  deliver(t,EXC_BAD_ACCESS,1,2);
  assert(exception_next==1 && exception_ring[0].type==EXC_BAD_ACCESS &&
         exception_ring[1].code==UINT64_MAX && exception_ring[3].pc_valid==0);
  assert(bp_exit_view_take(&live));
  paint(live);
  assert(strstr(rendered,"pc=0"));
  paint(trap);
  assert(!strcmp(rendered,"X1 pid=26 t=6 c=1 s=8a70 pc=12345678abcdef00"));
  paint(before);
  assert(!strcmp(rendered,"SYSOS"));

  exit_lock=1;
  deliver(t,EXC_BREAKPOINT,0,0);
  assert(!bp_exit_view_take(&live) && exception_next==1 && exit_lock==1);
  exit_lock=0;
  enabled=0;
  deliver(t,EXC_BREAKPOINT,0,0);
  assert(exception_next==1);
  printf("breakpoint=%zu; other (PID_MAX)=%zu; empty=no X1; widest=%zu/80 columns (%zu/1440 px)\n",
         bp_width,pid_max_width,max_width,max_width*18);
  puts("64-bit fields, missing vs zero PC, 4-slot wrap, EX isolation, private snapshot and lock contention: PASS");
}
"""
    with tempfile.TemporaryDirectory() as tmp:
        c = Path(tmp) / "replay.c"
        c.write_text(harness)
        exe = c.with_suffix("")
        subprocess.run(["cc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", str(c), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == "__main__":
    main()
