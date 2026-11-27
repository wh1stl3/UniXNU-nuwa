#!/usr/bin/env python3
"""Compile/execute and disassemble the post-event diagnostic code.

This is a host test, not a device or kernel-runtime claim.  It extracts the
actual generated functions from the candidate renderer and the actual
SpringBoard sampler from nuwa_systemos.c, compiles them with small stubs, and
executes them.  It then disassembles the linked native-with-stabs.macho to
confirm the critical calls survived optimisation and their order.

Covered:
  * DATA0 is emitted on page row 7 through line(), not row 0 (line() drops 0);
    the fua/flush suffix and the trial label are compiled and checked.
  * boot_progress_critical_paint() with display_owned=1 / bound=0 writes
    non-zero pixels into display.frame only above y = height/8.
  * an unmatched parent prints pp=?; a matched parent prints pp=<n>.
  * the SpringBoard sample publishes one packed word, so a concurrent reader
    never sees seen=1/live=0 while the walk is still in progress.
  * linked _proc_prepareexit calls capture before sync and paint after sync,
    and _boot_progress_critical_paint calls px_text twice without refresh().
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check(label, ok, detail=""):
    print(f"{label:46} {'PASS' if ok else 'FAIL'} {detail}")
    if not ok:
        raise SystemExit("FAIL " + label)


def extract_between(text, start, end):
    at = text.index(start)
    stop = text.index(end, at)
    return text[at:stop]


def extract_braced(text, start):
    at = text.index(start)
    brace = text.index("{", at)
    depth = 0
    for i in range(brace, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[at:i + 1]
    raise SystemExit("unterminated block: " + start)


def host_compile(cc, source, binary, include_dirs, extra=()):
    command = [cc, "-std=c11", "-O0", "-Wall", "-Wextra", "-Wno-unused-function",
               "-Wno-unused-variable", "-Wno-implicit-function-declaration",
               *sum((["-I", str(p)] for p in include_dirs), []), *extra,
               str(source), "-o", str(binary)]
    done = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if done.returncode:
        print(done.stdout[-4000:])
        raise SystemExit(f"host compile failed: {source}")
    return binary


def compile_and_run(cc, code, include_dirs, work, name, extra=()):
    src = work / (name + ".c")
    src.write_text(code)
    binary = work / name
    host_compile(cc, src, binary, include_dirs, extra)
    done = subprocess.run([str(binary)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(done.stdout.strip())
    return done.returncode


def test_data_row(renderer, cc, work, include_dirs):
    text = renderer.read_text()
    start = ("  {\n    char data[BP_COLS],full[BP_COLS];"
             if "  {\n    char data[BP_COLS],full[BP_COLS];" in text else
             "  {\n    char data[80],full[BP_COLS];")
    block = extract_between(text, start,
                            "  __asm__ volatile(\"dsb sy\" ::: \"memory\");\n  last_draw=now;")
    has_suffix = "static void bp_fua_suffix(char *buf,size_t size) {" in text
    suffix = extract_braced(text, "static void bp_fua_suffix(char *buf,size_t size) {") \
        if has_suffix else ""
    harness = """\
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define BP_COLS 120
static unsigned calls, last_row;
static char last_text[160];
static char build_tag[32] = "data-trial";
static int mount_state = 2, post_ready = 0;
static volatile uint64_t nuwa_disposable_fua_requests = 7, nuwa_disposable_flushes = 3;
static void line(unsigned row, const char *s, uint32_t c) {
  (void)c; calls++; last_row = row; snprintf(last_text, sizeof last_text, "%s", s);
}
static int nuwa_data_mount_summary(char *b, size_t n) {
  snprintf(b, n, "DATA0 st=4 err=0 ro=0 dev=12345678 seed=1 first-attempt");
  return mount_state;
}
static int bp_post_ready(void) { return post_ready; }
static int bp_post_event_row(char *b, size_t n) { (void)b; (void)n; return 0; }
""" + suffix + """
static void run_data_block(void) {
""" + block + """
}
int main(void) {
  unsigned before = calls;
  mount_state = 2; post_ready = 0;
  run_data_block();
  if (!(calls > before && last_row == 7 && strstr(last_text, "DATA0") && strstr(last_text, "first-attempt")))
    return 1;
#if HAVE_FUA_SUFFIX
  if (!(strstr(last_text, "fua=7") && strstr(last_text, "flush=3")))
    return 3;
#endif
#if EXPECT_FUA_LABEL
  if (!strstr(last_text, "FUA-EXP-nodur"))
    return 4;
#endif
  before = calls; mount_state = 0; post_ready = 1;
  run_data_block();
  if (!(calls > before && last_row == 7 && strstr(last_text, "DATA0 not run")))
    return 2;
  return 0;
}
"""
    extra = ["-DHAVE_FUA_SUFFIX=1"] if has_suffix else []
    if "NUWA-FUA-TRIAL-20261127" in text:
        extra += ["-DNUWA_FUA_TRIAL=1", "-DEXPECT_FUA_LABEL=1"]
    rc = compile_and_run(cc, harness, include_dirs, work, "test_data_row", extra=extra)
    check("DATA0 on non-zero row through line()", rc == 0,
          "row 7, not row 0; fua/flush fields and trial label when present")


def critical_harness(renderer, systemos_globals):
    text = renderer.read_text()
    state = extract_between(text, "// NUWA-POSTEVENT-20261127: event-time summary",
                            "static int bp_post_ready(void) {")
    state += extract_braced(text[text.index("static int bp_post_ready(void) {"):], "static int bp_post_ready(void) {")
    if "static void bp_fua_suffix(char *buf,size_t size) {" in text:
        state += extract_braced(text, "static void bp_fua_suffix(char *buf,size_t size) {")
    critical = extract_braced(text, "void boot_progress_critical_paint(void) {")
    critical = critical.replace('__asm__ volatile("dsb sy" ::: "memory");', ";")
    px = extract_between(text, "static void px_text(unsigned x0",
                         "extern volatile uint64_t native_legacy_copy_n")
    return """\
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include "BootProgressCore.h"
#include "BootProgressDisplay.h"
static struct bp_display display;
static char build_tag[32] = "data-trial";
volatile uint64_t nuwa_disposable_fua_requests = 7, nuwa_disposable_flushes = 3;
volatile uint32_t nuwa_pid1_present = 1, nuwa_pid1_state = 2;
volatile uint64_t nuwa_sb_public = (1ull << 63) | (1ull << 62) | ((uint64_t)95 << 32) | 2;
static size_t strlcpy(char *d, const char *s, size_t n) {
  size_t l = strlen(s); if (n) { size_t c = l < n ? l : n - 1; memcpy(d, s, c); d[c] = 0; } return l;
}
int nuwa_data_mount_summary(char *b, size_t n) {
  snprintf(b, n, "DATA0 st=4 err=0 ro=0 dev=12345678 seed=1 first-attempt"); return 2;
}
static void px_text(unsigned, unsigned, const char *, unsigned, uint32_t, uint32_t);
""" + state + "\n" + px + "\n" + critical + """
int main(void) {
  size_t bytes = 1440u * 3200u * 4u;
  unsigned char *fb = calloc(1, bytes);
  if (!fb) return 2;
  display.frame = (uintptr_t)fb;
  display.bound = 0;              /* after boot_progress_prepare_scanout() */
  display.width = 1440; display.height = 3200; display.stride = 5760; display.scale = 3;
  boot_progress_critical_capture(17, "tzinit", 45, 0, 0, 1);
  boot_progress_critical_paint();
  unsigned long top = 0, below = 0;
  for (unsigned y = 0; y < 3200; ++y)
    for (unsigned x = 0; x < 1440; ++x) {
      uint32_t v = *(uint32_t *)(fb + (size_t)y * 5760 + x * 4);
      if (!v) continue;
      if (y < 3200 / 8) top++; else below++;
    }
  printf("critical pixels: top=%lu below=%lu\\n", top, below);
  free(fb);
  if (!top) return 3;
  if (below) return 4;            /* strict y < height/8 */
  if (top < 2u * 42u * 1440u) return 5;
  return 0;
}
"""


def test_critical_paint(renderer, cc, work, include_dirs):
    code = critical_harness(renderer, None)
    rc = compile_and_run(cc, code, include_dirs, work, "test_critical_paint")
    check("critical paint: bound=0 writes y<h/8 pixels", rc == 0,
          "two px_text rows, no refresh/bound")


def test_ppid(renderer, cc, work, include_dirs):
    text = renderer.read_text()
    state = extract_between(text, "// NUWA-POSTEVENT-20261127: event-time summary",
                            "static int bp_post_ready(void) {")
    state += extract_braced(text[text.index("static int bp_post_ready(void) {"):], "static int bp_post_ready(void) {")
    harness = """\
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
static char build_tag[32] = "data-trial";
volatile uint64_t nuwa_disposable_fua_requests = 7, nuwa_disposable_flushes = 3;
volatile uint32_t nuwa_pid1_present = 1, nuwa_pid1_state = 2;
volatile uint64_t nuwa_sb_public = (1ull << 63) | (1ull << 62) | ((uint64_t)95 << 32) | 2;
static size_t strlcpy(char *d, const char *s, size_t n) {
  size_t l = strlen(s); if (n) { size_t c = l < n ? l : n - 1; memcpy(d, s, c); d[c] = 0; } return l;
}
int nuwa_data_mount_summary(char *b, size_t n) { (void)b; (void)n; return 0; }
""" + state + """
int main(void) {
  char row[96];
  boot_progress_exit_parent(999, 1);           /* different pid */
  bp_post_latch(17, "tzinit", 45, 0);
  if (!bp_post_event_row(row, sizeof row)) return 2;
  if (!strstr(row, "pp=?")) return 3;
  boot_progress_exit_parent(17, 7);            /* same pid */
  bp_post_latch(17, "tzinit", 45, 0);
  if (!bp_post_event_row(row, sizeof row)) return 4;
  if (!strstr(row, "pp=7")) return 5;
  return 0;
}
"""
    rc = compile_and_run(cc, harness, include_dirs, work, "test_ppid")
    check("unmatched parent prints pp=?; matched pp=<n>", rc == 0, "single 64-bit publish")


def test_sb_concurrency(systemos, renderer, cc, work, include_dirs):
    text = systemos.read_text()
    start = text.index("struct nuwa_sb_local {")
    end = text.index("void\nnuwa_pid1_sample(void)", start)
    block = text[start:end]
    helpers = extract_between(renderer.read_text(), "static const char *bp_post_stat",
                              "static int bp_post_format")
    harness = """\
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <pthread.h>
#include <unistd.h>
#define PROC_RETURNED 0
#define PROC_RETURNED_DONE 1
#define PROC_ALLPROCLIST 0
#define PROC_NOWAITTRANS 0
typedef struct proc { char p_comm[17]; int p_pid; int p_stat; } *proc_t;
static volatile uint64_t nuwa_sb_public;
static volatile int walking;
static volatile int present = 1;
static int proc_iterate(int flags, int (*cb)(proc_t, void *), void *arg, void *a, void *b) {
  (void)flags; (void)a; (void)b;
  walking = 1;
  usleep(2000);
  struct proc p = { "SpringBoard", 95, 2 };
  int r = present ? cb(&p, arg) : PROC_RETURNED;
  walking = 0;
  return r;
}
""" + block + "\n" + helpers + """
static int false_gone;
static void *writer(void *arg) {
  (void)arg;
  for (unsigned i = 0; i < 2000; ++i) nuwa_sb_sample();
  return NULL;
}
static void *reader(void *arg) {
  (void)arg;
  for (unsigned i = 0; i < 400000; ++i) {
    uint64_t w = __atomic_load_n(&nuwa_sb_public, __ATOMIC_ACQUIRE);
    if ((w & (1ull << 63)) && !(w & (1ull << 62))) {
      if (present) false_gone++;
    }
  }
  return NULL;
}
int main(void) {
  pthread_t w, r;
  char sb[32];
  if (strcmp(bp_post_sb(sb, sizeof sb), "never")) return 7;
  present = 1;
  nuwa_sb_sample();
  if (((nuwa_sb_public >> 62) & 3ull) != 3ull) return 8;
  if (strcmp(bp_post_sb(sb, sizeof sb), "95:RUN")) return 9;
  present = 0;
  nuwa_sb_sample();
  if (strcmp(bp_post_sb(sb, sizeof sb), "gone")) return 10;
  present = 1;
  nuwa_sb_sample();
  if (!(nuwa_sb_public & (1ull << 62))) return 2;
  pthread_create(&w, NULL, writer, NULL);
  pthread_create(&r, NULL, reader, NULL);
  pthread_join(w, NULL);
  pthread_join(r, NULL);
  printf("sb word=%016llx false_gone=%d\\n", (unsigned long long)nuwa_sb_public, false_gone);
  if (false_gone) return 3;
  if (!(nuwa_sb_public & (1ull << 62))) return 4;
  if (((nuwa_sb_public >> 32) & 0x3fffffffu) != 95) return 5;
  if ((nuwa_sb_public & 0xffffffffu) != 2) return 6;
  return 0;
}
"""
    rc = compile_and_run(cc, harness, include_dirs, work, "test_sb", extra=["-pthread"])
    check("SpringBoard never -> 95:RUN -> gone, no false gone", rc == 0,
          "high bits 0xc while present")


def test_disassembly(kernel, objdump, cc):
    if not kernel.is_file():
        check("disassembly", False, f"missing {kernel}")
    out = subprocess.check_output([objdump, "-d", "--disassemble-symbols="
                                   "_proc_prepareexit,_boot_progress_critical_paint,"
                                   "_nuwa_pid1_sample",
                                   str(kernel)], text=True, stderr=subprocess.STDOUT)
    prep = out[out.index("<_proc_prepareexit>:"):]
    paint = out[out.index("<_boot_progress_critical_paint>:"):]
    order = ["_boot_progress_critical_capture", "_sync", "_boot_progress_critical_paint",
             "_panic_with_options"]
    positions = [prep.find("<" + name + ">") for name in order]
    check("linked critical order", all(p >= 0 for p in positions) and positions == sorted(positions),
          "capture < sync < paint < panic")
    check("critical paint calls px_text twice", paint.count("<_px_text>") >= 2,
          f"px_text calls={paint.count('<_px_text>')}")
    check("critical paint bypasses refresh/prepare_scanout",
          "<_refresh>" not in paint and "<_boot_progress_prepare_scanout>" not in paint,
          "no full-page refresh")
    strings = subprocess.check_output(["strings", str(kernel)], text=True)
    check("linked marker and summary strings",
          "NUWA-POSTEVENT-20261127" in strings and "DATA0 st=" in strings and "pp=?" in strings,
          "marker, DATA0, pp=? present")
    pid1 = out[out.index("<_nuwa_pid1_sample>:"):]
    check("pid1 sample packs seen|live 0xc000000000000000",
          "orr\tx8, x8, #0xc000000000000000" in pid1 or
          "0xc000000000000000" in pid1,
          "seen bit set on the first found sample")
    gate = prep.find("ldr\tw9, [x8, #932]")  # crash_behavior_test_mode
    capture = prep.find("<_boot_progress_critical_capture>")
    check("capture after test-mode gate in disassembly",
          gate >= 0 and capture > gate, f"gate={gate} capture={capture}")
    staged = kernel.parent / "kern_exit.c"
    if staged.is_file():
        src = staged.read_text()
        body = src[src.index("proc_handle_critical_exit(proc_t p"):]
        order = ["proc_should_trigger_panic", "boot_progress_critical_capture",
                 "proc_crash_coredump", "sync(p, (void *)NULL", "boot_progress_critical_paint",
                 "panic_with_options"]
        pos = [body.find(x) for x in order]
        check("capture after panic decision, paint after sync",
              all(p >= 0 for p in pos) and pos == sorted(pos),
              "source order in proc_handle_critical_exit")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--renderer", type=Path, default=ROOT / "out/nuwa-postevent-20261127-build-r8/BootProgress.c")
    ap.add_argument("--systemos", type=Path, default=ROOT / "package/nuwa-systemos/nuwa_systemos.c")
    ap.add_argument("--kernel", type=Path, default=ROOT / "out/nuwa-postevent-20261127-build-r8/native-with-stabs.macho")
    ap.add_argument("--cc", default=os.environ.get("CC", "cc"))
    ap.add_argument("--objdump", default=os.environ.get("LLVM_OBJDUMP", "llvm-objdump"))
    ap.add_argument("--build-dir", type=Path, default=None)
    a = ap.parse_args()
    build_dir = (a.build_dir or a.renderer.parent).resolve()
    include_dirs = [build_dir, ROOT / "package/boot-progress",
                    ROOT / ".." / "uefi-nuwa/Silicon/Silicium/SiliciumPkg/Library/FrameBufferSerialPortLib"]
    work = Path(tempfile.mkdtemp(prefix="nuwa-postevent-test-"))
    try:
        test_data_row(a.renderer, a.cc, work, include_dirs)
        test_critical_paint(a.renderer, a.cc, work, include_dirs)
        test_ppid(a.renderer, a.cc, work, include_dirs)
        test_sb_concurrency(a.systemos, a.renderer, a.cc, work, include_dirs)
        test_disassembly(a.kernel, a.objdump, a.cc)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print("post-event host tests and linked disassembly: PASS")


if __name__ == "__main__":
    main()
