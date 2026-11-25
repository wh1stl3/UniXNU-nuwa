#!/usr/bin/env python3
"""Exercise the production stack walker, slot publication and panel layout."""
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
typedef unsigned thread_t;
static thread_t current_thread(void) { return 1; }
static uint64_t memory[8][2], stack_base;
static unsigned copies, fail_read;
static int copyin(uint64_t from, void *to, size_t size) {
  unsigned i = copies++;
  assert(i < 8 && size == 16 && from == stack_base + i*16);
  if (i == fail_read) return 1;
  memcpy(to, memory[i], size);
  return 0;
}
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
  boot_progress_lsd_crash(2,pid,11,1,pc,0x1048,0x2080,0x30a0,8,0xfffffff007123456ULL);
}

static uint64_t gen(unsigned i) {
  return bp_cr_slots[i].metadata >> 2;
}

static void frames(thread_t thread, uint64_t sp, uint64_t fp) {
  copies = 0;
  boot_progress_lsd_crash(thread,92,11,1,0x1234,0x1048,sp,fp,8,0);
}

static void walk_case(char rows[][120], const char *label, unsigned count,
    unsigned calls, const char *stop) {
  char expected[120];
  assert(copies == calls && bp_cr_rows(rows,24) >= 5+count);
  snprintf(expected,sizeof(expected),"CRS n=%u stop=%s",count,stop);
  assert(!strcmp(rows[4],expected));
  printf("PASS %s (%u copyin): %s\n",label,calls,rows[4]);
  for (unsigned i=0;i<count;++i) {
    snprintf(expected,sizeof(expected),"CRS+%u pc=%016llx",i+1,
        (unsigned long long)memory[i][1]);
    assert(!strcmp(rows[5+i],expected) && strlen(rows[5+i])==25);
    if (count==8) puts(rows[5+i]);
  }
  assert(strncmp(rows[5+count],"CRS+",4) || !rows[5+count][0]);
}

int main(void) {
  char rows[64][120] = {{0}};
  unsigned n, width=0;
  assert(bp_cr_rows(rows,24)==0 && !gen(0) && !gen(1));
  puts("PASS no crash: no CR rows");
  write_cr(92,0x1adf63478ULL);
  assert(gen(0)==1 && !gen(1) && bp_cr_rows(rows,24)==5);
  const char *first[] = {"CR p92 lsd sig=11 code=1 dr=0",
    "CR+ pc=00000001adf63478 lr=0000000000001048",
    "CR+ sp=0000000000002080 fp=00000000000030a0",
    "CR+ fa=0000000000000008 k=fffffff007123456"};
  for (unsigned i=0;i<4;++i) { assert(!strcmp(rows[i],first[i])); puts(rows[i]); }
  puts("PASS once: slot0 gen=1");
  write_cr(328,0x1adf6347cULL);
  assert(gen(0)==1 && gen(1)==2 && bp_cr_rows(rows,24)==6);
  assert(!strcmp(rows[0],"CR p328 lsd sig=11 code=1 dr=0"));
  assert(!strcmp(rows[5],"CR2 p92 lsd sig=11 pc=00000001adf63478"));
  puts(rows[5]);
  puts("PASS twice: slot1 gen=2; newest first");
  write_cr(329,0x33);
  assert(gen(0)==3 && gen(1)==2 && bp_cr_rows(rows,24)==6);
  assert(!strcmp(rows[5],"CR2 p328 lsd sig=11 pc=00000001adf6347c"));
  puts("PASS third: overwrite slot0 (oldest), retain slot1");

  cas_count=0; force_cas=6;
  write_cr(330,0x44);
  assert(!force_cas && cas_count==6 && bp_cr_dropped==1 && gen(0)==3 && gen(1)==2);
  assert(bp_cr_rows(rows,24)==6 && strstr(rows[0],"dr=1"));
  puts("PASS CAS contention: six failed CAS over two rounds, dr=1");
  cas_count=0; force_cas=3;
  write_cr(331,0x55);
  assert(!force_cas && cas_count==6 && bp_cr_dropped==1 && gen(1)==4);
  puts("PASS CAS retry: second round succeeds without incrementing dr");

  tear_slot=&bp_cr_slots[1].metadata;
  assert(bp_cr_rows(rows,24)==5 && tear_reads==6 && strstr(rows[0],"dr=1 torn"));
  bp_cr_slots[0].metadata=(gen(0)<<2)|BP_CR_WRITING;
  assert(bp_cr_rows(rows,24)==1 && !strcmp(rows[0],"CR torn dr=1"));
  puts("PASS torn: reject changing generation after 3 tries; mark stable survivor or standalone");
  tear_slot=NULL;
  bp_cr_slots[1].metadata=(4ULL<<2)|BP_CR_VALID;
  bp_cr_slots[0].metadata=(gen(0)<<2)|BP_CR_VALID;
  stack_base=0x4000;
  fail_read=8;
  for (unsigned i=0;i<8;++i) {
    memory[i][0]=stack_base+(i+1)*16;
    memory[i][1]=0x100001000ULL+i*4;
  }
  frames(1,stack_base,stack_base);
  walk_case(rows,"normal eight",8,8,"limit");
  memory[2][0]=stack_base+16;
  frames(1,stack_base,stack_base);
  walk_case(rows,"backward link after three",3,3,"badfp");
  memory[2][0]=stack_base+48;
  fail_read=4;
  frames(1,stack_base,stack_base);
  walk_case(rows,"failed fifth read",4,5,"readfail");
  fail_read=8;
  uint64_t lr=memory[0][1];
  memory[0][1]=0;
  frames(1,stack_base,stack_base);
  walk_case(rows,"zero LR",0,1,"zero");
  memory[0][1]=lr;
  memory[1][0]=0;
  frames(1,stack_base,stack_base);
  walk_case(rows,"short chain (null next FP)",2,2,"badfp");
  memory[1][0]=stack_base+32;
  frames(2,stack_base,stack_base);
  walk_case(rows,"non-current",0,0,"na");
  frames(1,stack_base,stack_base+BP_CRS_WINDOW-8);
  walk_case(rows,"record crosses 1 MiB boundary",0,0,"badfp");
  frames(1,UINT64_MAX-15,UINT64_MAX-15);
  walk_case(rows,"SP window overflows",0,0,"badfp");
  frames(1,stack_base,stack_base);
  unsigned budget=24, cr=bp_cr_rows(rows,budget);
  n=cr;
  strcpy(rows[n++],"SHOT pending 1");
  strcpy(rows[n++],"EXIT one");
  strcpy(rows[n++],"PROC one");
  while(n<64) strcpy(rows[n++],"LOAD competing priority zero");
  n=cr+bp_banner_select(rows+cr,n-cr,budget-cr);
  assert(n==24 && cr==14 && !strcmp(rows[12],"CRS+8 pc=000000010000101c") &&
         !strcmp(rows[14],"SHOT pending 1") &&
         !strcmp(rows[15],"EXIT one") && !strcmp(rows[16],"PROC one"));
  printf("PASS full 24-row panel: %s; %s; %s\n",rows[4],rows[8],rows[14]);
  for(unsigned b=0;b<=14;++b) {
    cr=bp_cr_rows(rows,b);
    if (b<4) assert(cr==0);
    else if (b<9) {
      assert(cr==(b>=6?5:4));
      if (cr==5) assert(!strncmp(rows[4],"CR2 ",4));
    }
    else {
      unsigned shown=b>9 ? b-6 : 4;
      char header[32];
      snprintf(header,sizeof(header),"CRS n=%u stop=limit",shown);
      assert(cr==5+shown && !strcmp(rows[4],header) &&
             !strcmp(rows[8],"CRS+4 pc=000000010000100c"));
    }
    if (cr) {
      assert(!strncmp(rows[0],"CR p",4));
      for(unsigned i=1;i<4;++i) assert(!strncmp(rows[i],"CR+ ",4));
      assert(bp_cr_check_yield(0,cr) && bp_cr_check_yield(cr,cr));
      for(unsigned i=1;i<cr;++i) assert(!bp_cr_check_yield(i,cr));
    }
  }
  cr=bp_cr_rows(rows,10);
  strcpy(rows[cr],"SHOT pending 1");
  for (unsigned i=cr+1;i<64;++i) strcpy(rows[i],"LOAD competing priority zero");
  n=cr+bp_banner_select(rows+cr,64-cr,10-cr);
  assert(n==10 && cr==9 && !strcmp(rows[9],"SHOT pending 1"));
  printf("PASS full 10-row panel: %s; %s; %s\n",rows[4],rows[8],rows[9]);
  puts("PASS 0–3 rows omit CR; 4–8 omit CRS; yield never interrupts a selected CR/CRS group");
  bp_cr_dropped=UINT64_MAX;
  boot_progress_lsd_crash(2,INT32_MAX,UINT32_MAX,UINT64_MAX,UINT64_MAX,
                          UINT64_MAX,UINT64_MAX,UINT64_MAX,UINT64_MAX,UINT64_MAX);
  assert(bp_cr_rows(rows,24)==6);
  unsigned older=gen(0)>gen(1);
  bp_cr_slots[older].metadata=(gen(older)<<2)|BP_CR_WRITING;
  assert(bp_cr_rows(rows,24)==5 && strstr(rows[0]," torn"));
  for(unsigned i=0;i<4;++i) {
    unsigned w=(unsigned)strlen(rows[i]); if(w>width) width=w;
    printf("width[%u]=%u\n",i,w);
  }
  assert(width<=78);
  printf("PASS maximum CR line width=%u/78\n",width);
  bp_cr_slots[older].metadata=(gen(older)<<2)|BP_CR_VALID;
  write_cr(332,0x66);
  assert(bp_cr_rows(rows,24)==6);
  unsigned cr2_width=(unsigned)strlen(rows[5]);
  assert(cr2_width<=78 && strstr(rows[5],"p2147483647 lsd sig=127"));
  printf("PASS maximum CR2 line width=%u/78; CRS header=%zu/78; CRS+ frame=25/78\n",
         cr2_width,strlen("CRS n=4 stop=readfail"));
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
            "copyout", "map_switch", "stackshot", "backtrace", "lck_", "mutex"))
    bsd, ux, cr = (calls[n] for n in symbols)
    assert bsd.count(symbols[1]) == ux.count(symbols[2]) == 1
    assert bsd.index(symbols[1]) < bsd.index("_threadsignal")
    assert "_get_user_regs" in ux
    assert not any("copyin" in c for c in bsd + ux)
    assert sum("copyin" in c for c in cr) == 1, cr
    print("PASS linked: BSD -> osfmk capture -> recorder before threadsignal; one copyin call site")
