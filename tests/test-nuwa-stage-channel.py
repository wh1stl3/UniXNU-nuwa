#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Patent
"""Check the actual generated stage observer and patch blocks on the host."""
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from generate_r35_display_diag import generate, stage_channel
from generate_nuwa_crashcap import generate_banner


def between(text, start, end):
    return text[text.index(start):text.index(end, text.index(start))]


r35l = ROOT / "out/nuwa-r35l-regs-full-20261121"
base = generate_banner(generate((r35l / "BootProgress.c").read_bytes(),
                                mg_reset=True, pixsig=True)).decode()
banner = stage_channel(base.encode()).decode()
assert base.count("STAGE pid=") == 0 and banner.count("STAGE pid=") == 1
fmt = between(banner, "  if(stage) snprintf(rows[n++]", "\n")
sig = between(banner, "  char stage_name[MAXTHREADNAMESIZE]", "  if(signature==")
assert "if(stage)" in fmt and "%.40s" in fmt
assert "signature+=stage_sig;" in sig
assert '!strncmp(s,"STAGE ",6)' in banner

build = runpy.run_path(str(ROOT / "scripts/build-nuwa-display-native.py"))
source = (r35l / "tree/bsd/kern/kern_exec.c").read_bytes()
header = (r35l / "tree/osfmk/kern/boot_progress.h").read_bytes()
src, hdr = build["stage_sources"](build["STAGE_PATCH"].read_text().encode(), source, header)
hook = between(src.decode(), "#if defined(XNU_BOOT_PROGRESS) && XNU_BOOT_PROGRESS && defined(XNU_NUWA_STAGE_CHANNEL)",
               "\n\t\terror = proc_process_signature")
decl = between(hdr.decode(), "#if defined(XNU_NUWA_STAGE_CHANNEL)", "#else")
assert src.decode().replace(hook + "\n", "").encode() == source
assert hdr.decode().replace(decl, "").encode() == header
functions = between(banner, "static LCK_GRP_DECLARE(stage_group", "void boot_progress_exit")
exit_hook = "void boot_progress_exit(int pid,const char *name,int status,unsigned ns,uint64_t code) {\n"
cleanup = banner.split(exit_hook, 1)[1].split("\n  }\n", 1)[0] + "\n  }\n"
assert cleanup.startswith("  if((unsigned)pid==") and "stage_thread=THREAD_NULL;" in cleanup

fixture = r"""
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define XNU_BOOT_PROGRESS 1
#define XNU_NUWA_STAGE_CHANNEL 1
#define MAXTHREADNAMESIZE 64
#define THREAD_NULL ((thread_t)0)
#define LCK_GRP_DECLARE(a,b) int a __attribute__((unused))
#define LCK_MTX_DECLARE(a,b) int a
typedef struct thread { unsigned refs; char name[MAXTHREADNAMESIZE]; } *thread_t;
static void lck_mtx_lock(int *lock) { assert(!(*lock)++); }
static void lck_mtx_unlock(int *lock) { assert((*lock)-- == 1); }
static void thread_reference(thread_t t) { assert(t->refs++); }
static void thread_deallocate(thread_t t) { assert(t->refs-- > 1); }
static void thread_get_thread_name(thread_t t, char *n) { memcpy(n,t->name,MAXTHREADNAMESIZE); }
static const char *arg;
static int PE_parse_boot_argn(const char *key, void *value, size_t size) {
    assert(!strcmp(key,"nuwa-init"));
    if (!arg) return 0;
    snprintf(value,size,"%s",arg);
    return 1;
}
struct proc { unsigned pid; };
static struct proc init = {1}, other = {2};
static struct proc *initproc = &init;
#define proc_getpid(p) ((p)->pid)
""" + decl + functions + """
static void publish(struct proc *p, thread_t t) {
    struct { thread_t ip_new_thread; } image = {t}, *imgp=&image;
""" + hook + """
}
static void cleanup(int pid) {
""" + cleanup + """
}
static uint64_t row(char rows[1][120]) {
    uint64_t signature=0;
    unsigned n=0;
""" + sig + fmt + """
    assert(n<=1);
    return signature;
}
int main(void) {
    struct thread t={1,""}, next={1,"display-stop"};
    char rows[1][120]={{0}};
    publish(&init,&t);
    assert(t.refs==1 && !row(rows) && !rows[0][0]);
    arg="display-client-extra";
    publish(&init,&t);
    assert(t.refs==1 && !row(rows) && !rows[0][0]);
    arg="display-client";
    publish(&other,&t);
    assert(t.refs==1 && !row(rows));
    publish(&init,&t);
    assert(t.refs==2 && !row(rows));
    strcpy(t.name,"display-main");
    uint64_t initial=row(rows);
    assert(initial && !strcmp(rows[0],"STAGE pid=1 name=display-main"));
    strcpy(t.name,"display-wait");
    assert(initial!=row(rows) && !strcmp(rows[0],"STAGE pid=1 name=display-wait"));
    memset(t.name,'a',sizeof(t.name));
    assert(row(rows) && strlen(rows[0])==strlen("STAGE pid=1 name=")+40);
    cleanup(2);
    assert(t.refs==2);
    publish(&init,&next);
    assert(t.refs==1 && next.refs==2 && row(rows));
    cleanup(1);
    rows[0][0]=0;
    assert(next.refs==1 && !row(rows) && !rows[0][0]);
}
"""
with tempfile.TemporaryDirectory() as tmp:
    c, exe = Path(tmp) / "fixture.c", Path(tmp) / "fixture"
    c.write_text(fixture)
    subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", c, "-o", exe], check=True)
    subprocess.run([exe], check=True)
print("PASS: stage text, exact-gate fixture, name repaint, replacement and exit")
