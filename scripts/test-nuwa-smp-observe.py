#!/usr/bin/env python3
"""Replay the actual SMP page/title formatters and optionally compare outer inputs."""
import argparse
from hashlib import sha256
from pathlib import Path
import runpy
import subprocess
import tempfile

from generate_r35_display_diag import SMP_OBSERVE_FORMAT, generate

ROOT = Path(__file__).resolve().parents[1]


def check_renderer():
    src = (ROOT / "out/nuwa-r35l-regs-full-20261121/BootProgress.c").read_bytes()
    old = generate(src, mg_reset=True)
    observed = generate(src, mg_reset=True, smp_observe=True)
    page = b"      bp_smp_entry_page(b,sizeof(b));\n"
    title = b"  bp_smp_entry_title(head,sizeof head,build_tag,now,crashes,failed);"
    old_page = old[old.index(b'      unsigned n=(unsigned)snprintf(b,sizeof(b),"SMP req='):
                   old.index(b"      line(38,b,")]
    old_title = old[old.index(b'  snprintf(head,sizeof head," UniXNU live diagnostics'):
                    old.index(b"\n  px_text(0,title,")]
    assert observed.count(page) == observed.count(title) == 1
    assert observed.replace(SMP_OBSERVE_FORMAT, b"", 1).replace(page, old_page).replace(title, old_title) == old

    harness = r"""
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
volatile uint32_t armcpu_smp_requested,armcpu_smp_running,armcpu_smp_conduit;
volatile uint32_t armcpu_smp_step[8],armcpu_smp_fail[8];
volatile int32_t armcpu_smp_psci_rc[8];
volatile uint32_t armcpu_smp_on_state[8],armcpu_smp_on_attempts[8],armcpu_smp_seen_aff_valid[8];
volatile uint64_t armcpu_smp_on_target[8],armcpu_smp_seen_aff[8];
""" + SMP_OBSERVE_FORMAT.decode() + r"""
static void check(const char *expected, const char *live) {
  char page[120], title[120];
  bp_smp_entry_page(page,sizeof page);
  bp_smp_entry_title(title,sizeof title,"nuwa-r35",UINT32_MAX,UINT32_MAX,UINT32_MAX);
  assert(!strcmp(page,expected));
  assert(strstr(title,live));
  assert(strlen(page)<=80 && strlen(title)<=80);
  printf("%2zu %s\n%2zu %s\n",strlen(page),page,strlen(title),title);
}
int main(void) {
  check("SMP 0/0/0 c1=step0 n=0 t=- rc=- aff=-","rc=- aff=-");
  armcpu_smp_requested=1;
  armcpu_smp_step[1]=2;
  armcpu_smp_psci_rc[1]=-1000;
  check("SMP 1/0/0 c1=step2 n=0 t=- rc=- aff=-","rc=- aff=-");
  armcpu_smp_step[1]=3;
  armcpu_smp_psci_rc[1]=-1001;
  armcpu_smp_on_state[1]=1;
  check("SMP 1/0/0 c1=step3 n=0 t=- rc=nc aff=-","rc=nc aff=-");
  armcpu_smp_conduit=1;
  armcpu_smp_step[1]=4;
  armcpu_smp_on_attempts[1]=1;
  armcpu_smp_on_target[1]=0x100;
  armcpu_smp_on_state[1]=0;
  check("SMP 1/0/1 c1=step4 n=1 t=100 rc=- aff=-","rc=- aff=-");
  armcpu_smp_on_state[1]=2;
  armcpu_smp_psci_rc[1]=-1001;
  check("SMP 1/0/1 c1=step4 n=1 t=100 rc=-1001 aff=-","rc=-1001 aff=-");
  armcpu_smp_psci_rc[1]=-4;
  check("SMP 1/0/1 c1=step4 n=1 t=100 rc=-4 aff=-","rc=-4 aff=-");
  armcpu_smp_psci_rc[1]=-5;
  check("SMP 1/0/1 c1=step4 n=1 t=100 rc=-5 aff=-","rc=-5 aff=-");
  armcpu_smp_psci_rc[1]=0;
  check("SMP 1/0/1 c1=step4 n=1 t=100 rc=0 aff=-","rc=0 aff=-");
  armcpu_smp_step[1]=5;
  armcpu_smp_seen_aff_valid[1]=1;
  armcpu_smp_fail[1]=1;
  check("SMP 1/0/1 c1=step5!fail1 n=1 t=100 rc=0 aff=0","rc=0 aff=0");
  armcpu_smp_fail[1]=0;
  armcpu_smp_step[1]=7;
  armcpu_smp_seen_aff[1]=0x100;
  check("SMP 1/0/1 c1=step7 n=1 t=100 rc=0 aff=100","rc=0 aff=100");
  armcpu_smp_running=1;
  check("SMP 1/1/1 c1=step7 n=1 t=100 rc=0 aff=100","rc=0 aff=100");
  armcpu_smp_running=UINT32_MAX;
  armcpu_smp_on_attempts[1]=UINT32_MAX;
  armcpu_smp_psci_rc[1]=INT32_MIN;
  armcpu_smp_seen_aff[1]=0xff00ffffffULL;
  armcpu_smp_conduit=2;
  armcpu_smp_fail[1]=4;
  check("SMP 1/ffffffff/2 c1=step7!fail4 n=ffffffff t=100 rc=-2147483648 aff=ff00ffffff",
        "rc=-2147483648 aff=ff00ffffff");
  return 0;
}
"""
    with tempfile.TemporaryDirectory() as directory:
        c = Path(directory) / "smp.c"
        exe = Path(directory) / "smp"
        c.write_text(harness)
        subprocess.run(["cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
                        str(c), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


def check_package(package):
    m = runpy.run_path(str(ROOT / "scripts/repack-nuwa-smp-gate.py"))
    baseline = m["SMP_BASELINE"] / "vendor_boot.img"
    assert sha256(baseline.read_bytes()).hexdigest() == m["SMP_BASELINE_SHA"]
    read_inputs = m["extract_boot_inputs"]
    before, _, _ = read_inputs(baseline)
    after, _, fat = read_inputs(package / "vendor_boot.img")
    args = m["xnu_args"](after)
    assert args == m["xnu_args"](before) == m["EXPECTED_ARGS"]
    assert all(t.split(b"=", 1)[0] != b"sheng-smp" for t in args.split())
    assert fat == (package / "payload.img").read_bytes()
    print(f"pinned outer args unchanged: {len(args)} bytes, SHA-256 {sha256(args).hexdigest()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path)
    args = parser.parse_args()
    check_renderer()
    if args.package:
        check_package(args.package)
