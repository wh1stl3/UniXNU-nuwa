#!/usr/bin/env python3
"""Replay the generated C hook and its actual row formatter on the host."""
import importlib.util
import pathlib
import subprocess
import sys
import tempfile

script = pathlib.Path(__file__).with_name("generate-r35b-exit-detail.py")
spec = importlib.util.spec_from_file_location("detail", script)
detail = importlib.util.module_from_spec(spec)
spec.loader.exec_module(detail)
src = detail.generate(pathlib.Path(sys.argv[1]).read_bytes()).decode()
assert "line(1,b,0xffffffff);" in src
assert "else line(i+1,b,0xffffffff);" in src
assert "memcpy(exit_ring_snapshot,exit_ring,sizeof(exit_ring));" in src
function = src[src.index("void boot_progress_exit(int pid,"):src.index("// The log's [spawn] section")]
fmt = src[src.index('      if(e->pc_valid)'):src.index('      if (!i) bar(0,b', src.index('      if(e->pc_valid)'))]
harness = r'''
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
typedef struct {uint64_t pc;} arm_saved_state_t;
static arm_saved_state_t saved_state={0x12345678abcdef00ULL};
static int no_saved_state;
static int current_thread(void) {return 1;}
static const arm_saved_state_t *get_user_regs(int t) {(void)t;return no_saved_state?0:&saved_state;}
static uint64_t get_saved_state_pc(const arm_saved_state_t *s) {return s->pc;}
struct bp_exit_ring_entry { char comm[33]; unsigned pid,sig,ns,nprocs,aks_calls,aks_opens,count,pc_valid; uint64_t code,pc; };
static struct bp_exit_ring_entry exit_ring[4],exit_ring_snapshot[4];
static unsigned exit_ring_count,exit_ring_snapshot_count,exit_lock,exit_dropped,nprocs,nuwa_aks_calls,nuwa_aks_opens;
static unsigned nuwa_exit_ring_pid[4],nuwa_exit_ring_sig[4],nuwa_exit_ring_ns[4],nuwa_exit_ring_code[4],nuwa_exit_ring_nprocs[4],nuwa_exit_ring_aks_calls[4],nuwa_exit_ring_aks_opens[4],nuwa_exit_ring_count;
static char nuwa_exit_ring_comm[4][7],boot_progress_throw_text[2];
static struct { unsigned crashes; char crash[3][400],reason[400],thrown[400]; } exit_records;
static int enabled=1;
static void census_note(const char *n,int x) {(void)n;(void)x;}
static int proc_selfpid(void) {return 1;}
static void xpc_fail_note(int s,unsigned n,uint64_t c) {(void)s;(void)n;(void)c;}
static void bp_exit_add(void *r,int p,const char *n,int s,unsigned ns,uint64_t c) {(void)r;(void)p;(void)n;(void)s;(void)ns;(void)c;}
static void (*boot_progress_exit_fault)(int,unsigned,char *,unsigned long);
static void (*boot_progress_exit_reason)(int,unsigned,char *,unsigned long);
static size_t strlcpy(char *d,const char *s,size_t n) {size_t l=strlen(s); if(n){size_t c=l<n-1?l:n-1;memcpy(d,s,c);d[c]=0;}return l;}
''' + function + r'''
int main(void) {
  boot_progress_exit(1,"prefix-one",5,0xffffffffu,0x100000001ULL);
  boot_progress_exit(2,"prefix-two",5,0xffffffffu,0x100000001ULL);
  assert(exit_ring[0].pc_valid==0 && exit_ring[1].pc_valid==1 && exit_ring[1].pc==saved_state.pc);
  for(int i=0;i<200;++i) boot_progress_exit(100+i,"ordinary",0x100,0,0);
  assert(exit_ring_count==2);
  for(int i=0;i<200;++i) {
    boot_progress_exit(200+i,"prefix-one",5,0xffffffffu,0x100000001ULL);
    boot_progress_exit(400+i,"prefix-two",5,0xffffffffu,0x100000001ULL);
  }
  assert(exit_ring_count==2 && exit_ring[0].count==201 && exit_ring[1].count==201);
  boot_progress_exit(3,"prefix-one",5,0xffffffffu,0x200000001ULL);
  boot_progress_exit(4,"prefix-one",6,0xffffffffu,0x100000001ULL);
  assert(exit_ring_count==4 && exit_ring[3].count==201);
  assert(exit_ring[1].code==0x200000001ULL);
  exit_lock=1; boot_progress_exit(5,"ordinary",0x100,0,0); exit_lock=0;
  assert(exit_dropped==1 && exit_ring_count==4);
  char b[200]; unsigned i=0;
  struct bp_exit_ring_entry worst={.comm="abcdef",.sig=127,.ns=0xffffffffu,.code=0xffffffffffffffffULL,.count=0xffffffffu,.pc_valid=1,.pc=0xffffffffffffffffULL};
  const struct bp_exit_ring_entry *e=&worst;
''' + fmt + r'''
  assert(strlen(b)<=80);
  size_t max_width=strlen(b);
  worst.pc_valid=0;
''' + fmt + r'''
  assert(strlen(b)<=80 && strstr(b,"pc=----------------"));
  memset(exit_ring,0,sizeof(exit_ring)); exit_ring_count=0;
  boot_progress_exit(1,"name",5,1,1);
  boot_progress_exit(1,"name",5,2,1);
  assert(exit_ring_count==2 && exit_ring[0].ns!=exit_ring[1].ns);
  exit_ring[0].count=~0u;
  boot_progress_exit(1,"name",5,2,1);
  assert(exit_ring[0].count==~0u && exit_ring_count==2);
  no_saved_state=1;
  boot_progress_exit(1,"other",5,2,1);
  assert(exit_ring[0].pc_valid==0);
  printf("replay: 200 normal exits retained; signal storm keys retained; same-prefix distinct; 64-bit code distinct; dropped=1; max row=%zu/80\n",max_width);
  return 0;
}
'''
with tempfile.TemporaryDirectory() as tmp:
    c = pathlib.Path(tmp) / "replay.c"
    exe = pathlib.Path(tmp) / "replay"
    c.write_text(harness)
    subprocess.run(["cc", "-std=c11", "-O0", str(c), "-o", str(exe)], check=True)
    result = subprocess.run([str(exe)], check=True, text=True, capture_output=True)
    print(result.stdout.splitlines()[-1])
