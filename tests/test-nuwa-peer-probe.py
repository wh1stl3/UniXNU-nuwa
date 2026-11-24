#!/usr/bin/env python3
"""Host fixture for the generated PEER formatter and real banner selection."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("diag", root / "scripts/generate_r35_display_diag.py")
diag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diag)
source = (root / "scripts/generate_r35_display_diag.py").read_text()
start = source.index("    uint32_t pid[6];")
end = source.index("\n  }\n  unsigned restart_state", start)
formatter = source[start:end]
census_start = source.index("// Only touch_monitor calls this")
census_end = source.index("\nstatic void touch_monitor(void *arg, wait_result_t result)", census_start)
census = source[census_start:census_end]
assert 'strcmp(name,"iconservicesagen")' in source
assert '#define BP_SHOT_USER_PCS 12u' in source

fixture = r"""
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
static uint32_t bp_proc_pid[6], bp_icon_pid;
static uint32_t bp_svc_mask, bp_proc_generation, bp_sb_restart_state;
struct proc { int pid; const char *name; };
static struct proc items[4];
static struct proc *proc_find(int pid) {
  for (unsigned i=0;i<4;++i) if(items[i].pid==pid) return &items[i];
  return 0;
}
static void proc_name(int pid,char *out,int size) {
  struct proc *p=proc_find(pid); snprintf(out,size,"%s",p->name);
}
static void proc_rele(struct proc *p) { (void)p; }
static void psignal(struct proc *p,int sig) { (void)p; (void)sig; }
""" + census + r"""
""" + diag.BANNER_SELECTION.decode() + r"""
static void run(uint32_t icon_pid, uint32_t cm, uint32_t lsd, uint32_t sb,
                const char *expected) {
  char rows[48][120]={{0}}; unsigned n=0; int nprocs=4;
  bp_proc_pid[0]=sb; bp_proc_pid[2]=lsd; bp_proc_pid[5]=cm; bp_icon_pid=icon_pid;
""" + formatter + r"""
  assert(n==2 && !strcmp(rows[1],expected) && strlen(rows[1])<=78);
  printf("%s\n",rows[1]);
  char all[48][120]={{0}}; unsigned count=0;
  const char *required[]={"SHOT lsd","SHOT2 x","T0 U=1","T0+ U=2","T0+ U=3",
                           "EXIT 1","EXIT 2","EXIT 3","PROC x",rows[1],
                           "SC n=0","SC +0","LOAD x"};
  for(unsigned i=0;i<sizeof(required)/sizeof(required[0]);++i)
    snprintf(all[count++],120,"%s",required[i]);
  for(unsigned i=0;i<20;++i) snprintf(all[count++],120,"GPU x");
  assert(bp_banner_priority(rows[1],2)==bp_banner_priority("PROC x",2));
  unsigned required_count=sizeof(required)/sizeof(required[0]);
  unsigned kept=bp_banner_select(all,count,24);
  assert(kept==24);
  for(unsigned i=0;i<required_count;++i) assert(!strcmp(all[i],required[i]));
}
int main(void) {
  items[0]=(struct proc){101,"iconservicesagen"};
  items[1]=(struct proc){102,"containermanager"};
  items[2]=(struct proc){103,"lsd"};
  items[3]=(struct proc){104,"SpringBoard"};
  bp_proc_census(0,0);
  assert(bp_icon_pid==101 && bp_proc_pid[5]==102 &&
         bp_proc_pid[2]==103 && bp_proc_pid[0]==104);
  items[0].name="iconservicesagent"; items[2].pid=0;
  bp_proc_census(0,0);
  assert(bp_icon_pid==0 && bp_proc_pid[5]==102 &&
         bp_proc_pid[2]==0 && bp_proc_pid[0]==104);
  memset(items,0,sizeof(items));
  bp_proc_census(0,0);
  assert(bp_icon_pid==0 && bp_proc_pid[5]==0 &&
         bp_proc_pid[2]==0 && bp_proc_pid[0]==0);
  run(4096,4095,4094,4093,"PEER icon=4096 cm=4095 lsd=4094 SB=4093");
  run(0,55,0,88,"PEER icon=- cm=55 lsd=- SB=88");
  run(0,0,0,0,"PEER icon=- cm=- lsd=- SB=-");
}
"""
with tempfile.TemporaryDirectory() as tmp:
    c = Path(tmp) / "fixture.c"
    exe = Path(tmp) / "fixture"
    c.write_text(fixture)
    subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", str(c), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
