#!/usr/bin/env python3
"""Exercise the actual generated DSP row and banner priority."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
path = root / "scripts/generate_r35_display_diag.py"
spec = importlib.util.spec_from_file_location("diag", path)
diag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diag)
source = path.read_text()
start = source.index("#define DSP_VALUE")
end = source.index("\n  }\n  // Presentation cost", start)
formatter = source[start:end]
fixture = r"""
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
static volatile uint32_t nuwa_dsp_reg,nuwa_dsp_cli,nuwa_dsp_vo,nuwa_dsp_vb,nuwa_dsp_ret;
static volatile uint32_t nuwa_dsp_co,nuwa_dsp_cb,nuwa_dsp_vy,nuwa_dsp_ve;
""" + diag.BANNER_SELECTION.decode() + r"""
static void run(const char *first, const char *second) {
  char rows[64][120]={{0}}; unsigned n=0;
""" + formatter + r"""
  assert(n==2 && !strcmp(rows[0],first) && !strcmp(rows[1],second));
  assert(strlen(rows[0])<=78 && strlen(rows[1])<=78);
  printf("%zu %s\n%zu %s\n",strlen(rows[0]),rows[0],strlen(rows[1]),rows[1]);
  assert(bp_banner_priority(rows[0],2)==bp_banner_priority("PROC x",2));
  assert(bp_banner_priority(rows[1],2)==bp_banner_priority("PROC x",2));
  strcpy(rows[n++],"GPU x"); strcpy(rows[n++],"PROC x");
  assert(bp_banner_select(rows,n,1)==0);
  assert(bp_banner_select(rows,n,2)==2);
  assert(!strncmp(rows[0],"DSP ",4) && !strncmp(rows[1],"DSP+",4));
}
int main(void) {
  run("DSP reg=0 cli=0 vo=0 vb=0", "DSP+ co=0 cb=0 ret=0 vy=0 ve=0");
  nuwa_dsp_reg=1; nuwa_dsp_vb=3;
  run("DSP reg=1 cli=0 vo=0 vb=3", "DSP+ co=0 cb=0 ret=0 vy=0 ve=0");
  nuwa_dsp_vy=2; nuwa_dsp_ve=1;
  run("DSP reg=1 cli=0 vo=0 vb=3", "DSP+ co=0 cb=0 ret=0 vy=2 ve=1");
  nuwa_dsp_reg=nuwa_dsp_cli=nuwa_dsp_vo=nuwa_dsp_vb=nuwa_dsp_ret=UINT32_MAX;
  nuwa_dsp_co=nuwa_dsp_cb=nuwa_dsp_vy=UINT32_MAX;
  run("DSP reg=4294967295 cli=4294967295 vo=4294967295 vb=4294967295",
      "DSP+ co=4294967295 cb=4294967295 ret=4294967295 vy=4294967295 ve=1");
}
"""
with tempfile.TemporaryDirectory() as tmp:
    c, exe = Path(tmp) / "fixture.c", Path(tmp) / "fixture"
    c.write_text(fixture)
    subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                    "-Wno-address", str(c), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
