#!/usr/bin/env python3
"""Exercise the generated C row selector and banner geometry on the host."""
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_r35_display_diag import BANNER_SELECTION, generate

root = Path(__file__).resolve().parents[1]
source = (root / "out/nuwa-r35l-regs-full-20261121/BootProgress.c").read_bytes()
generated = generate(source, mg_reset=True)
assert b"if(cols>119)cols=119;" in generated
assert generated.index(b"n=bp_banner_select(rows,n,budget);") < generated.index(
    b"boot_ui_trace_role_rows(roles[k],rows+n")
for height in range(1, 4000):
    for scale in range(1, 5):
        cell = 14 * scale
        half = height // 2
        if half >= 8 + 2 * cell:
            budget = min(24, (half - 8) // cell - 2)
            assert (budget + 2) * cell + 8 <= half

test = r"""
#include <string.h>
#include <stdio.h>
#include <assert.h>
""" + BANNER_SELECTION.decode() + r"""
int main(void) {
  char rows[48][120]={"CRASH one","      continuation","EXIT one","XR one",
    "PROC one","SVC one","SC one","FB one","SWAP one","GPUC one",
    "GPUW one","PROC two","LOAD one","UFS one","SCHED one","CPU one",
    "GPU1 one","GPU2 one"};
  const char *expected[]={"EXIT one","PROC one","PROC two","CRASH one",
    "      continuation","XR one","UFS one","SCHED one","SVC one","SC one",
    "FB one","SWAP one","LOAD one","CPU one","GPUC one","GPUW one",
    "GPU1 one","GPU2 one","STACK one"};
  unsigned n=bp_banner_select(rows,18,19);
  if(n<19) strcpy(rows[n++],"STACK one");
  assert(n==19);
  for(unsigned i=0;i<n;++i) assert(!strcmp(rows[i],expected[i]));
  char limited[48][120]={"GPU1","FB","LOAD","CRASH","EXIT","XR","PROC",
    "SVC","SC n","UFS","SCHED","GPU2"};
  const char *first[]={"EXIT","PROC","CRASH","XR","UFS","SCHED","FB","LOAD","SVC"};
  n=bp_banner_select(limited,12,9);
  assert(n==9);
  for(unsigned i=0;i<n;++i) {
    if (strcmp(limited[i],first[i])) fprintf(stderr,"%u got %s expected %s\n",i,limited[i],first[i]);
    assert(!strcmp(limited[i],first[i]));
  }
  return 0;
}
"""
with tempfile.TemporaryDirectory() as directory:
    c = Path(directory) / "selector.c"
    exe = Path(directory) / "selector"
    c.write_text(test)
    subprocess.run(["cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
                    str(c), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
print("banner selection and geometry: PASS")
