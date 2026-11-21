#!/usr/bin/env python3
"""Compile the actual generated exit function and row formatting for host replay."""
import importlib.util
import pathlib
import subprocess
import sys
import tempfile

root = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("generator", root / "generate-r35-exit-selection.py")
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)
source = pathlib.Path(sys.argv[1]).read_bytes()
changed = gen.generate(source).decode()
assert changed.replace("  if(signal || ns) {\n", "  if(status || ns) {\n", 1).encode() == source
function = changed[changed.index("void boot_progress_exit(int pid,"):changed.index("// The log's [spawn] section")]
render = changed[changed.index("    for(unsigned i=0;i<exit_ring_count && i<4;i++) {"):changed.index("    bar(0, line,", changed.index("    for(unsigned i=0;i<exit_ring_count && i<4;i++) {"))]
harness = r'''
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
struct bp_exit_ring_entry { char comm[7]; unsigned pid,sig,ns,code,nprocs,aks_calls,aks_opens; };
static struct bp_exit_ring_entry exit_ring[4];
static unsigned exit_ring_count, exit_lock, exit_dropped, nprocs, nuwa_aks_calls, nuwa_aks_opens;
static unsigned nuwa_exit_ring_pid[4],nuwa_exit_ring_sig[4],nuwa_exit_ring_ns[4],nuwa_exit_ring_code[4],nuwa_exit_ring_nprocs[4],nuwa_exit_ring_aks_calls[4],nuwa_exit_ring_aks_opens[4],nuwa_exit_ring_count;
static char nuwa_exit_ring_comm[4][7], boot_progress_throw_text[2];
static struct { unsigned crashes; char crash[3][400], reason[400], thrown[400]; } exit_records;
static int enabled=1;
static void census_note(const char *n,int x) {(void)n;(void)x;}
static int proc_selfpid(void) {return -1;}
static void xpc_fail_note(int s,unsigned n,uint64_t c) {(void)s;(void)n;(void)c;}
static void bp_exit_add(void *r,int p,const char *n,int s,unsigned ns,uint64_t c) {(void)r;(void)p;(void)n;(void)s;(void)ns;(void)c;}
static void (*boot_progress_exit_fault)(int,unsigned,char *,unsigned long);
static void (*boot_progress_exit_reason)(int,unsigned,char *,unsigned long);
static size_t strlcpy(char *d,const char *s,size_t n) {size_t l=strlen(s); if(n){size_t c=l<n-1?l:n-1;memcpy(d,s,c);d[c]=0;}return l;}
''' + function + r'''
int main(void) {
  boot_progress_exit(10,"SpringBoard",5,0,0);
  boot_progress_exit(11,"mobileactivationd",5,0,0);
  for (int i=0;i<200;i++) boot_progress_exit(100+i,"ordinary",0x100,0,0);
  assert(exit_ring_count==2 && exit_ring[0].pid==11 && exit_ring[1].pid==10);
  boot_progress_exit(12,"reason",0x100,2,255);
  boot_progress_exit(13,"signal",6,0,0);
  assert(exit_ring_count==4 && exit_ring[3].pid==10);
  for (int i=0;i<200;i++) boot_progress_exit(300+i,"ordinary",0x100,0,0);
  assert(exit_ring_count==4 && exit_ring[0].pid==13 && exit_ring[3].pid==10);
  for (int i=0;i<4;i++) {memcpy(exit_ring[i].comm,"abcdef",7); exit_ring[i].sig=15; exit_ring[i].ns=15; exit_ring[i].code=255;}
  char line[80]; size_t at=0; line[0]=0;
''' + render + r'''
  assert(strlen(line)==71 && strstr(line,"EX4 "));
  printf("replay: 200+200 exit(1), four slots, row=%zu: %s\n",strlen(line),line);
  boot_progress_exit(14,"storm",9,0,0);
  assert(exit_ring_count==4 && exit_ring[3].pid==11);
  return 0;
}
'''
with tempfile.TemporaryDirectory() as tmp:
    c = pathlib.Path(tmp) / "replay.c"
    exe = pathlib.Path(tmp) / "replay"
    c.write_text(harness)
    subprocess.run(["cc", "-std=c11", "-O0", str(c), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
