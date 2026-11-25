#!/usr/bin/env python3
"""Compile the production recorder and simulate bounded CAS/read interleavings."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from generate_nuwa_crashcap import RECORDER, generate_banner
from generate_r35_display_diag import BANNER_SELECTION, generate

prelude = r"""
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
static uint64_t *tear_slot;
static unsigned force_cas, cas_count, tear_reads;
static int cas(uint64_t *p, uint64_t *e, uint64_t d, int w, int s, int f) {
  ++cas_count;
  if (force_cas) { --force_cas; return 0; }
  return __atomic_compare_exchange_n(p,e,d,w,s,f);
}
static uint64_t load(uint64_t *p, int order) {
  // A writer publishes a new valid generation on each trailing tuple read.
  if (p == tear_slot && (++tear_reads % 2) == 0)
    __atomic_fetch_add(p,4,__ATOMIC_SEQ_CST);
  return __atomic_load_n(p,order);
}
#define __atomic_compare_exchange_n cas
#define __atomic_load_n load
"""
program = r"""
static void write_cr(int pid, uint64_t pc) {
  boot_progress_lsd_crash(pid,11,1,pc,0x1048,0x2080,0x30a0,8,0xfffffff007123456ULL);
}

static uint64_t gen(unsigned i) {
  return bp_cr_slots[i].metadata >> 2;
}

int main(void) {
  char rows[64][120] = {{0}};
  unsigned n, width=0;
  assert(bp_cr_rows(rows,24)==0 && !gen(0) && !gen(1));
  puts("PASS no crash: no CR rows");
  write_cr(92,0x1adf63478ULL);
  assert(gen(0)==1 && !gen(1) && bp_cr_rows(rows,24)==4);
  const char *first[] = {"CR p92 lsd sig=11 code=1 dr=0",
    "CR+ pc=00000001adf63478 lr=0000000000001048",
    "CR+ sp=0000000000002080 fp=00000000000030a0",
    "CR+ fa=0000000000000008 k=fffffff007123456"};
  for (unsigned i=0;i<4;++i) { assert(!strcmp(rows[i],first[i])); puts(rows[i]); }
  puts("PASS once: slot0 gen=1");
  write_cr(328,0x1adf6347cULL);
  assert(gen(0)==1 && gen(1)==2 && bp_cr_rows(rows,24)==5);
  assert(!strcmp(rows[0],"CR p328 lsd sig=11 code=1 dr=0"));
  assert(!strcmp(rows[4],"CR2 p92 lsd sig=11 pc=00000001adf63478"));
  puts(rows[4]);
  puts("PASS twice: slot1 gen=2; newest first");
  write_cr(329,0x33);
  assert(gen(0)==3 && gen(1)==2 && bp_cr_rows(rows,24)==5);
  assert(!strcmp(rows[4],"CR2 p328 lsd sig=11 pc=00000001adf6347c"));
  puts("PASS third: overwrite slot0 (oldest), retain slot1");

  cas_count=0; force_cas=6;
  write_cr(330,0x44);
  assert(!force_cas && cas_count==6 && bp_cr_dropped==1 && gen(0)==3 && gen(1)==2);
  assert(bp_cr_rows(rows,24)==5 && strstr(rows[0],"dr=1"));
  puts("PASS CAS contention: six failed CAS over two rounds, dr=1");
  cas_count=0; force_cas=3;
  write_cr(331,0x55);
  assert(!force_cas && cas_count==6 && bp_cr_dropped==1 && gen(1)==4);
  puts("PASS CAS retry: second round succeeds without incrementing dr");

  tear_slot=&bp_cr_slots[1].metadata;
  assert(bp_cr_rows(rows,24)==4 && tear_reads==6 && strstr(rows[0],"dr=1 torn"));
  bp_cr_slots[0].metadata=(gen(0)<<2)|BP_CR_WRITING;
  assert(bp_cr_rows(rows,24)==1 && !strcmp(rows[0],"CR torn dr=1"));
  puts("PASS torn: reject changing generation after 3 tries; mark stable survivor or standalone");
  tear_slot=NULL;
  bp_cr_slots[1].metadata=(4ULL<<2)|BP_CR_VALID;
  bp_cr_slots[0].metadata=(gen(0)<<2)|BP_CR_VALID;
  unsigned budget=24, cr=bp_cr_rows(rows,budget);
  n=cr;
  strcpy(rows[n++],"SHOT pending 1");
  strcpy(rows[n++],"EXIT one");
  strcpy(rows[n++],"PROC one");
  while(n<64) strcpy(rows[n++],"LOAD competing priority zero");
  n=cr+bp_banner_select(rows+cr,n-cr,budget-cr);
  assert(n==24 && cr==5 && !strcmp(rows[5],"SHOT pending 1") &&
         !strcmp(rows[6],"EXIT one") && !strcmp(rows[7],"PROC one"));
  puts("PASS SHOT pending, EXIT and PROC survive alongside CR on full panel");
  for(unsigned b=0;b<=5;++b) {
    cr=bp_cr_rows(rows,b);
    assert(cr==(b>=4?b:0));
    if (cr) {
      assert(!strncmp(rows[0],"CR p",4));
      for(unsigned i=1;i<4;++i) assert(!strncmp(rows[i],"CR+ ",4));
      assert(bp_cr_check_yield(0,cr) && bp_cr_check_yield(4,cr));
      for(unsigned i=1;i<4;++i) assert(!bp_cr_check_yield(i,cr));
    }
  }
  puts("PASS full panel: CR stays contiguous; 0..3 rows omit it; mid-group yield deferred");
  bp_cr_dropped=UINT64_MAX;
  boot_progress_lsd_crash(INT32_MAX,UINT32_MAX,UINT64_MAX,UINT64_MAX,
                          UINT64_MAX,UINT64_MAX,UINT64_MAX,UINT64_MAX,UINT64_MAX);
  assert(bp_cr_rows(rows,24)==5);
  bp_cr_slots[1].metadata=(gen(1)<<2)|BP_CR_WRITING;
  assert(bp_cr_rows(rows,24)==4 && strstr(rows[0]," torn"));
  for(unsigned i=0;i<4;++i) {
    unsigned w=(unsigned)strlen(rows[i]); if(w>width) width=w;
    printf("width[%u]=%u\n",i,w);
  }
  assert(width<=78);
  printf("PASS maximum CR line width=%u/78\n",width);
  bp_cr_slots[1].metadata=(gen(1)<<2)|BP_CR_VALID;
  write_cr(332,0x66);
  assert(bp_cr_rows(rows,24)==5);
  unsigned cr2_width=(unsigned)strlen(rows[4]);
  assert(cr2_width<=78 && strstr(rows[4],"p2147483647 lsd sig=127"));
  printf("PASS maximum CR2 line width=%u/78\n",cr2_width);
}
"""

source = (ROOT / "out/nuwa-r35l-regs-full-20261121/BootProgress.c").read_bytes()
banner = generate_banner(generate(source, mg_reset=True))
assert RECORDER in banner and b"n=cr+bp_banner_select(rows+cr,n-cr,budget-cr);" in banner
assert b"unsigned cr=bp_cr_rows(rows,budget),n=cr;" in banner
assert b"if(bp_cr_check_yield(i,cr) && __atomic_load_n" in banner
with tempfile.TemporaryDirectory() as directory:
    c = Path(directory) / "fixture.c"
    exe = c.with_suffix("")
    c.write_bytes(prelude.encode() + RECORDER + b"\n#undef __atomic_load_n\n"
                  + BANNER_SELECTION + program.encode())
    subprocess.run(["cc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                    str(c), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)

if len(sys.argv) == 2:
    symbols = ("_handle_ux_exception", "_nuwa_ux_capture_lsd", "_boot_progress_lsd_crash")
    calls = {}
    for name in symbols:
        text = subprocess.check_output(["llvm-objdump", "-d", "--no-show-raw-insn",
                                        "--disassemble-symbols=" + name, sys.argv[1]], text=True)
        assert f"<{name}>:" in text, name
        targets = re.findall(r"^\s*[0-9a-f]+:\s+bl?\s+0x[0-9a-f]+\s+<([^>]+)>", text, re.M)
        calls[name] = [target for target in targets if not target.startswith(name + "+")]
        assert not any(f in c for c in calls[name] for f in (
            "copyin", "copyout", "map_switch", "stackshot", "backtrace", "lck_", "mutex"))
    bsd, ux, cr = (calls[n] for n in symbols)
    assert bsd.count(symbols[1]) == ux.count(symbols[2]) == 1
    assert bsd.index(symbols[1]) < bsd.index("_threadsignal")
    assert "_get_user_regs" in ux and not cr
    print("PASS linked: BSD -> osfmk capture -> recorder, before threadsignal; no recorder calls out")
