#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Patent
"""Execute the adapted retirement body and its actual RG formatter on the host."""
import argparse
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


adapter = load("display_adapter", ROOT / "scripts/verify-nuwa-display-host-abi.py")
diag = load("display_diag", ROOT / "scripts/generate_r35_display_diag.py")
parser = argparse.ArgumentParser()
parser.add_argument("--base", type=Path, default=ROOT.parents[1] / "UniXNU")
parser.add_argument("--build", type=Path, help="also check the actual generated build source")
parser.add_argument("--normal-build", action="store_true",
                    help="check a normal source build instead of the frozen binary-input replay")
args = parser.parse_args()
if args.normal_build and not args.build:
    parser.error("--normal-build requires --build")
upstream = args.base / "drivers/GopFramebuffer/NativeLegacyDisplay.cpp"
text = adapter.adapt_source(upstream.read_text(), upstream)
text = adapter.cpu_only_source(text, upstream)
text = adapter.no_software_vsync_source(text, upstream)
text = adapter.pixsig_source(text, upstream)


def retirement(source):
    first = source.index("    bool retireSwap(")
    end = source.index("    // Separately gated retirement", first)
    return source[first:end]


method = retirement(text)
baseline = retirement((ROOT / "out/nuwa-swap-probe-baseline-20261128/NativeLegacyDisplay.cpp").read_text())
assert method.replace("        const uint32_t retirementGeneration=nuwa_retire_entered();\n", "").replace(
    "        nuwa_retire_returned(retirementGeneration);\n", "") == baseline
assert method.index("activateOnlyPendingSwap(request)") < method.index("nuwa_retire_entered()")
assert method.index("nuwa_retire_entered()") < method.index("completeCurrentSwap()")
assert method.index("completeCurrentSwap()") < method.index("nuwa_retire_returned(retirementGeneration)")
assert "request" not in method[method.index("completeCurrentSwap()"):]
if args.build:
    source = (args.build / "archive/NativeLegacyDisplay.cpp" if args.normal_build else
              args.build / "NativeLegacyDisplay.cpp")
    actual = source.read_text()
    assert retirement(actual) == method

renderer = diag.generate((ROOT / "out/nuwa-r35l-regs-full-20261121/BootProgress.c").read_bytes(),
                         mg_reset=True, pixsig=True).decode()
banner_selection = renderer[renderer.index("static unsigned bp_banner_priority("):
                            renderer.index("static unsigned bp_pix_rows(")]
assert renderer.count("bp_rg_row(b,sizeof(b)); line(9,b,0xff00ffcc);") == 1
assert renderer.count("bp_rg_row(rows[n++],120);") == 1
assert renderer.index("bp_rg_row(b,sizeof(b))") < renderer.index("line(10,b,0xff00ffcc)")
assert '"SC n=' not in renderer and '"SC unavailable"' not in renderer
assert "nuwa_rg_entered" not in diag.generate(
    (ROOT / "out/nuwa-r35l-regs-full-20261121/BootProgress.c").read_bytes()).decode()
if args.build:
    built_renderer = (args.build / "BootProgress.c").read_text()
    if not args.normal_build:
        baseline_renderer = (ROOT / "out/nuwa-v1-nodur-diag-20261128-build-r3/BootProgress.c").read_bytes()
        assert built_renderer.encode() == diag.retire_generation(baseline_renderer)
    assert 'bp_rg_row(b,sizeof(b)); line(9,b,0xff00ffcc);' in built_renderer
    assert 'bp_rg_row(rows[n++],120);' in built_renderer
    for row in ('"D1 st=', '"D2 wr=', '"D3 first='):
        assert built_renderer.count(row) == 1

fixture = r"""
#include "NuwaRetireGeneration.h"
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <sys/mman.h>
#include <unistd.h>

extern "C" {
volatile uint32_t nuwa_rg_entered,nuwa_rg_returned,nuwa_rg_returned_generation;
}
struct OriginalLegacySwapRequest { unsigned valid; };
static size_t page_size;
static unsigned total_completed;
static OriginalLegacySwapRequest *new_request() {
    void *p=mmap(nullptr,page_size,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
    assert(p!=MAP_FAILED);
    auto *r=static_cast<OriginalLegacySwapRequest *>(p);
    r->valid=1;
    return r;
}
static void forget(OriginalLegacySwapRequest *r) { assert(munmap(r,page_size)==0); }
static void reset() {
    nuwa_rg_entered=nuwa_rg_returned=nuwa_rg_returned_generation=0;
    total_completed=0;
}
static int PE_parse_boot_argn(const char *,unsigned *,size_t) { return 0; }
class IOMobileFramebufferLegacy {
public:
    void completeCurrentSwap();
};
static void native_legacy_retirement_observed(IOMobileFramebufferLegacy *) {}
class FakeDisplay : public IOMobileFramebufferLegacy {
public:
    bool activate=true, reenter=false;
    OriginalLegacySwapRequest *current=nullptr, *next=nullptr;
    bool activateOnlyPendingSwap(const OriginalLegacySwapRequest *r) {
        if (!activate) return false;
        assert(r && r->valid);
        current=const_cast<OriginalLegacySwapRequest *>(r);
        return true;
    }
    void stat(unsigned) {}
    void note(unsigned,int,const OriginalLegacySwapRequest *r) { assert(r->valid); }
    void removeValidated(const OriginalLegacySwapRequest *r) { assert(r->valid); }
""" + method + r"""
};
void IOMobileFramebufferLegacy::completeCurrentSwap() {
    auto *d=static_cast<FakeDisplay *>(this);
    auto *r=d->current;
    assert(nuwa_rg_entered>=total_completed+1);
    if (d->reenter) {
        d->reenter=false;
        assert(d->retireSwap(d->next,true));
        assert(nuwa_rg_entered==2 && nuwa_rg_returned==1 && nuwa_rg_returned_generation==2);
    }
    ++total_completed;
    // Simulate the family releasing this request before the call returns.
    assert(mprotect(r,page_size,PROT_NONE)==0);
}
int main() {
    page_size=(size_t)sysconf(_SC_PAGESIZE);
    {
        reset(); FakeDisplay d; auto *r=new_request();
        assert(r->valid);                 // validation succeeded
        bool submitted=false;             // family submission failed
        if (submitted) assert(d.retireSwap(r,true));
        assert(!nuwa_rg_entered && !nuwa_rg_returned && !total_completed);
        d.activate=false;                 // cancelled/not the pending head
        assert(!d.retireSwap(r,true));
        assert(!nuwa_rg_entered && !nuwa_rg_returned && !total_completed);
        assert(!d.retireSwap(r,false));   // disabled/cancelled, not a completion
        assert(!nuwa_rg_entered && !nuwa_rg_returned && !total_completed);
        forget(r);
        puts("validation success, failed submission/cancel: en=0 ret=0");
    }
    {
        reset(); FakeDisplay d; auto *r=new_request();
        assert(d.retireSwap(r,true));
        assert(nuwa_rg_entered==1 && nuwa_rg_returned==1 && nuwa_rg_returned_generation==1);
        forget(r);
        puts("one successful retirement: en=1 ret=1 g=1 last=1");
    }
    {
        reset(); FakeDisplay d; auto *outer=new_request(), *inner=new_request();
        d.next=inner; d.reenter=true;
        assert(d.retireSwap(outer,true));
        assert(nuwa_rg_entered==2 && nuwa_rg_returned==2 && nuwa_rg_returned_generation==1);
        forget(outer); forget(inner);
        puts("nested completion: en=2 ret=2 g=2 last=1");
    }
}
"""

formatter = r"""
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
volatile uint32_t nuwa_rg_entered,nuwa_rg_returned,nuwa_rg_returned_generation;
""" + banner_selection + diag.RETIRE_ROWS.decode() + r"""
int main(void) {
    char text[120], rows[4][120]={{"SB never"},{"RG en=1"},{"PROC x"},{"PIX x"}};
    bp_rg_row(text,sizeof text);
    assert(!strcmp(text,"RG en=0 ret=0 g=0 last=0"));
    nuwa_rg_entered=2; nuwa_rg_returned=1; nuwa_rg_returned_generation=2;
    bp_rg_row(text,sizeof text);
    assert(!strcmp(text,"RG en=2 ret=1 g=2 last=2"));
    nuwa_rg_entered=nuwa_rg_returned=nuwa_rg_returned_generation=UINT32_MAX;
    bp_rg_row(text,sizeof text);
    assert(strlen(text)<=78);
    assert(bp_banner_priority("RG x",2)==bp_banner_priority("PROC x",2));
    assert(bp_banner_select(rows,4,2)==2 && !strncmp(rows[1],"RG ",3));
    printf("formatter max %zu columns: %s\n",strlen(text),text);
}
"""

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    cpp, c = tmp / "retire.cpp", tmp / "formatter.c"
    cpp.write_text(fixture)
    c.write_text(formatter)
    subprocess.run(["clang++", "-std=c++17", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
                    "-fsanitize=address,undefined", "-no-pie", "-I", ROOT / "package", cpp,
                    "-o", tmp / "retire"], check=True)
    subprocess.run([tmp / "retire"], check=True)
    subprocess.run(["clang", "-std=c11", "-O1", "-Wall", "-Wextra", "-Werror", c,
                    "-o", tmp / "formatter"], check=True)
    subprocess.run([tmp / "formatter"], check=True)
print("production source anchors, page/banner and host fixtures self-checked")
