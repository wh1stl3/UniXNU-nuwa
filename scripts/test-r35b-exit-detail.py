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
draw = src[src.index("static void draw(unsigned now) {"):src.index("// A framebuffer write", src.index("static void draw(unsigned now) {"))]
assert "if(!bp_exit_view_take(&exit_view)) return;" in draw
assert "exit_ring_count" not in draw and "exit_ring[" not in draw
assert draw.index("bp_exit_view_take(&exit_view)") < draw.index("bar(0,")
view = src[src.index("struct bp_exit_view {"):src.index("// Published so", src.index("struct bp_exit_view {"))]
take = "  struct bp_exit_view exit_view;\n  if(!bp_exit_view_take(&exit_view)) return;"
assert take in draw
function = src[src.index("void boot_progress_exit(int pid,"):src.index("// The log's [spawn] section")]
fmt = src[src.index('      if(e->pc_valid)'):src.index('      if (!i) bar(0,b', src.index('      if(e->pc_valid)'))]
harness = r'''
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
#include <stdarg.h>
typedef struct {uint64_t pc;} arm_saved_state_t;
static arm_saved_state_t saved_state={0x12345678abcdef00ULL};
static int no_saved_state;
static int current_thread(void) {return 1;}
static const arm_saved_state_t *get_user_regs(int t) {(void)t;return no_saved_state?0:&saved_state;}
static uint64_t get_saved_state_pc(const arm_saved_state_t *s) {return s->pc;}
struct bp_exit_ring_entry { char comm[33]; unsigned pid,sig,ns,nprocs,aks_calls,aks_opens,count,pc_valid; uint64_t code,pc; };
static struct bp_exit_ring_entry exit_ring[4];
static unsigned exit_ring_count,exit_lock,exit_dropped,nprocs,nuwa_aks_calls,nuwa_aks_opens;
''' + view + r'''
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
static char last_log[512];
static int hook_printf(const char *fmt,...) { va_list a;va_start(a,fmt);int n=vsnprintf(last_log,sizeof(last_log),fmt,a);va_end(a);return n; }
#define printf hook_printf
''' + function + r'''
#undef printf
static char rendered[2][200];
static void replay_draw(int depth) {
''' + take + r'''
  if(depth==0) {
    boot_progress_exit(3,"A",5,1,1);
    replay_draw(1);
  }
  unsigned i=1; const struct bp_exit_ring_entry *e=&exit_view.entries[i]; char b[200];
''' + fmt + r'''
  strlcpy(rendered[depth],b,sizeof(rendered[depth]));
}
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
  memset(exit_ring,0,sizeof(exit_ring)); exit_ring_count=0;
  nuwa_aks_calls=11; nuwa_aks_opens=12;
  boot_progress_exit(1,"A",5,1,1);
  nuwa_aks_calls=21; nuwa_aks_opens=22;
  boot_progress_exit(2,"B",5,1,1);
  assert(strstr(last_log,"aks=21/22"));
  struct bp_exit_view outer,inner,blocked;
  assert(bp_exit_view_take(&outer) && outer.count==2);
  nuwa_aks_calls=31; nuwa_aks_opens=32;
  boot_progress_exit(3,"A",5,1,1);
  assert(strstr(last_log,"aks=11/12") && exit_ring[1].count==2);
  assert(bp_exit_view_take(&inner) && inner.entries[1].count==2);
  assert(outer.count==2 && outer.entries[1].count==1 && !strcmp(outer.entries[1].comm,"A"));
  memset(&blocked,0xa5,sizeof(blocked));
  exit_lock=1; assert(!bp_exit_view_take(&blocked)); exit_lock=0;
  for(size_t k=0;k<sizeof(blocked);++k) assert(((unsigned char *)&blocked)[k]==0xa5);
  assert(outer.entries[1].count==1 && exit_dropped==1);
  memset(exit_ring,0,sizeof(exit_ring)); exit_ring_count=0;
  boot_progress_exit(1,"A",5,1,1); boot_progress_exit(2,"B",5,1,1);
  replay_draw(0);
  assert(strstr(rendered[0],"n=1 ") && strstr(rendered[1],"n=2 "));
  strcpy(rendered[0],"unchanged");
  exit_lock=1; replay_draw(0); exit_lock=0;
  assert(!strcmp(rendered[0],"unchanged") && exit_dropped==1);
  printf("replay: 200 normal exits retained; signal storm keys retained; same-prefix distinct; 64-bit code distinct; dropped=1; max row=%zu/80\n",max_width);
  printf("nested snapshot preserved; lock failure skips; A/B/A logs A first AKS 11/12\n");
  return 0;
}
'''
with tempfile.TemporaryDirectory() as tmp:
    c = pathlib.Path(tmp) / "replay.c"
    exe = pathlib.Path(tmp) / "replay"
    c.write_text(harness)
    subprocess.run(["cc", "-std=c11", "-O0", str(c), "-o", str(exe)], check=True)
    result = subprocess.run([str(exe)], check=True, text=True, capture_output=True)
    print(result.stdout, end="")
