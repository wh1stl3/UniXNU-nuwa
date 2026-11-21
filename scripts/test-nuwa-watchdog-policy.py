#!/usr/bin/env python3
"""Compile the actual policy-building and argument-handling C on a host."""
from pathlib import Path
import subprocess
import tempfile

source = (Path(__file__).resolve().parents[1] /
          "package/nuwa-watchdog/nuwa_watchdog_policy.c").read_text()
body = source[source.index("#define NUWA_POLICY_DIR"):
              source.index("\n\tif ((error = copyout(NUWA_POLICY_DIR")]
prefix = r"""
#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef void *proc_t;
#define PROC_NULL NULL
static unsigned arg_lite, arg_watchdog, arg_sheng;
static const char *arg_jobs;
static char saved[2048];
static size_t strlcat(char *d, const char *s, size_t n) {
 size_t a = strlen(d), b = strlen(s);
 if (a < n) { size_t k = b < n-a-1 ? b : n-a-1; memcpy(d+a,s,k); d[a+k]=0; }
 return a+b;
}
static int PE_parse_boot_argn(const char *name, void *out, int n) {
 if (!strcmp(name,"nuwa-lite") && arg_lite) { *(unsigned *)out=arg_lite; return 1; }
 if (!strcmp(name,"sheng-lite") && arg_sheng) { *(unsigned *)out=arg_sheng; return 1; }
 if (!strcmp(name,"disable-watchdogd") && arg_watchdog) { *(unsigned *)out=arg_watchdog; return 1; }
 if (!strcmp(name,"disable-jobs") && arg_jobs) {
   size_t k = strlen(arg_jobs); if (k >= (size_t)n) k = n-1;
   memcpy(out,arg_jobs,k); ((char *)out)[k]=0; return 1;
 }
 return 0;
}
"""
suffix = r"""
 (void)scratch; (void)fd; (void)result;
 strcpy(saved, nuwa_policy); nuwa_watchdog_policy_status = 0; return 0;
}
static int run(void) { return nuwa_boot_watchdog_policy((void *)1,0); }
int main(void) {
 arg_lite=1; assert(run()==0); assert(nuwa_watchdog_policy_labels==30);
 assert(strstr(saved,"com.apple.identityservicesd")); assert(!strstr(saved,"iconservicesagent"));
 arg_lite=2; assert(run()==0); assert(nuwa_watchdog_policy_labels==31);
 assert(strstr(saved,"com.apple.iconservices.iconservicesagent"));
 arg_lite=1; arg_jobs="com.apple.locationd,com.apple.example,com.apple.example";
 assert(run()==0); assert(nuwa_watchdog_policy_labels==31);
 assert(strstr(saved,"com.apple.example"));
 assert(strstr(strstr(saved,"com.apple.example")+1,"com.apple.example")==NULL);
 char previous[2048]; strcpy(previous,saved);
 char large[400]; memset(large,0,sizeof(large));
 for (int i=0;i<60;i++) {
   char item[8]; snprintf(item,sizeof(item),"x%02d",i);
   if (i) strcat(large,",");
   strcat(large,item);
 }
 arg_watchdog=1; arg_jobs=large; assert(run()==ENAMETOOLONG);
 assert(nuwa_watchdog_policy_status==ENAMETOOLONG); assert(!strcmp(saved,previous));
 arg_lite=0; arg_watchdog=0; arg_jobs=NULL; assert(run()==0); assert(!strcmp(saved,previous));
 arg_sheng=1; assert(run()==0); assert(!strcmp(saved,previous));
 arg_sheng=0; arg_lite=3; assert(run()==0); assert(!strcmp(saved,previous)); arg_lite=0;
 arg_watchdog=1; assert(run()==0); assert(nuwa_watchdog_policy_labels==2);
 assert(!strstr(saved,"com.apple.locationd"));
 puts("nuwa policy host cases: PASS");
}
"""
with tempfile.TemporaryDirectory() as tmp:
    c = Path(tmp) / "test.c"
    exe = Path(tmp) / "test"
    c.write_text(prefix + body + suffix)
    subprocess.run(["cc", "-std=c99", "-Wall", "-Wextra", str(c), "-o", str(exe)],
                   check=True)
    subprocess.run([str(exe)], check=True)
