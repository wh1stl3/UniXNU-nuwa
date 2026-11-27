#!/usr/bin/env python3
"""Host fixture for the reduced PROC row and the SpringBoard/lsd census."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("diag", root / "scripts/generate_r35_display_diag.py")
diag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diag)
source = (root / "scripts/generate_r35_display_diag.py").read_text()
start = source.index("  // PROC keeps only the live process count")
end = source.index("  // SpringBoard's seen/live/pid/state", start)
formatter = source[start:end]
census_start = source.index("// Only touch_monitor calls this")
census_end = source.index("\nstatic void touch_monitor(void *arg, wait_result_t result)", census_start)
census = source[census_start:census_end]
assert 'iconservicesagen' not in source
assert '"PEER ' not in source and '"SVC ' not in source

fixture = r"""
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
static int nprocs = 4;
static uint32_t bp_proc_pid[6], bp_proc_generation, bp_sb_restart_state;
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
static void run(uint32_t sb, const char *expected) {
  char rows[2][120]={{0}}; unsigned n=0;
  bp_proc_pid[0]=sb;
""" + formatter + r"""
  assert(n==1 && !strcmp(rows[0],expected));
  printf("%s\n",rows[0]);
}
int main(void) {
  items[0]=(struct proc){101,"iconservicesagen"};
  items[1]=(struct proc){102,"containermanager"};
  items[2]=(struct proc){103,"lsd"};
  items[3]=(struct proc){104,"SpringBoard"};
  bp_proc_census(0,0);
  assert(bp_proc_pid[0]==104 && bp_proc_pid[2]==103 &&
         !bp_proc_pid[1] && !bp_proc_pid[3] && !bp_proc_pid[4] && !bp_proc_pid[5]);
  memset(items,0,sizeof(items));
  bp_proc_census(0,0);
  assert(!bp_proc_pid[0] && !bp_proc_pid[2]);
  run(88,"PROC n=4 SB=88");
  run(0,"PROC n=4 SB=-");
  return 0;
}
"""
with tempfile.TemporaryDirectory() as tmp:
    c = Path(tmp) / "fixture.c"
    exe = Path(tmp) / "fixture"
    c.write_text(fixture)
    subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", str(c), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
print("PROC row and SpringBoard/lsd census: PASS")
