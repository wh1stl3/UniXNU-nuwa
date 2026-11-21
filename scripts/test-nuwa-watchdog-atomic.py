#!/usr/bin/env python3
"""Exercise the actual policy transaction against a fault-injected syscall model."""
from pathlib import Path
import subprocess
import tempfile

source = (Path(__file__).resolve().parents[1] /
          "package/nuwa-watchdog/nuwa_watchdog_policy.c").read_text()
body = source[source.index("#define NUWA_POLICY_DIR"):]
prefix = r"""
#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <fcntl.h>
typedef void *proc_t;
typedef uintptr_t user_addr_t;
typedef long user_ssize_t;
#define PROC_NULL NULL
#define stat64 fake_stat64
struct fake_stat64 { unsigned st_uid, st_gid, st_mode; long st_size; };
struct mkdir_args { user_addr_t path; int mode; };
struct open_args { user_addr_t path; int flags, mode; };
struct write_args { int fd; user_addr_t cbuf; size_t nbyte; };
struct fchown_args { int fd, uid, gid; };
struct fchmod_args { int fd, mode; };
struct fsync_args { int fd; };
struct fstat64_args { int fd; user_addr_t ub; };
struct close_args { int fd; };
struct rename_args { user_addr_t from, to; };
struct unlink_args { user_addr_t path; };
enum { FIRST_WRITE=1, SHORT_WRITE, SYNC_FAIL, MARK_FAIL, RENAME_FAIL };
static int fault, writes, temp_exists, marker_exists;
static char old[2048], temp[2048]; static size_t temp_len, old_len;
static char *strnstr(const char *s,const char *n,size_t max) {
 size_t len=strlen(n); while(max>=len && *s) {
  if(!strncmp(s,n,len)) return (char *)s;
  ++s; --max;
 } return NULL;
}
static size_t strlcat(char *d,const char *s,size_t n) {
 size_t a=strlen(d),b=strlen(s); if(a<n) {size_t k=b<n-a-1?b:n-a-1;memcpy(d+a,s,k);d[a+k]=0;} return a+b;
}
static int PE_parse_boot_argn(const char *n,void *v,int len) {
 (void)len; if(!strcmp(n,"nuwa-lite") || !strcmp(n,"disable-watchdogd")) {
 *(unsigned *)v=1; return 1; } return 0;
}
static int copyout(const void *s,user_addr_t d,size_t n) { memcpy((void *)d,s,n); return 0; }
static int copyin(user_addr_t s,void *d,size_t n) { memcpy(d,(void *)s,n); return 0; }
static int fake_mkdir(proc_t p,struct mkdir_args *a,int *r) {(void)p;(void)a;(void)r;return EEXIST;}
static int fake_open(proc_t p,struct open_args *a,int *r) {
 (void)p; const char *path=(const char *)a->path;
 if(strstr(path,"disabled.plist.tmp")) { if(temp_exists)return EEXIST;temp_exists=1;temp_len=0;*r=3;return 0; }
 if(strstr(path,"disabled.migrated")) { if(fault==MARK_FAIL)return EIO;
  if(marker_exists && (a->flags&O_EXCL)) return EEXIST;
  marker_exists=1;*r=4;return 0; }
 return EINVAL;
}
static int fake_write(proc_t p,struct write_args *a,user_ssize_t *r) {
 (void)p; assert(a->fd==3); ++writes;
 if(fault==FIRST_WRITE && writes==1)return EIO;
 size_t n=a->nbyte; if(fault==SHORT_WRITE && writes==2)--n;
 assert(temp_len+n<sizeof(temp));memcpy(temp+temp_len,(void *)a->cbuf,n);temp_len+=n;*r=n;return 0;
}
static int fake_chown(proc_t p,struct fchown_args *a,int *r) {(void)p;(void)a;(void)r;return 0;}
static int fake_chmod(proc_t p,struct fchmod_args *a,int *r) {(void)p;(void)a;(void)r;return 0;}
static int fake_fsync(proc_t p,struct fsync_args *a,int *r) {(void)p;(void)a;(void)r;return fault==SYNC_FAIL?EIO:0;}
static int sys_fstat64(proc_t p,struct fstat64_args *a,int *r) {
 (void)p;(void)r; struct fake_stat64 s={0,0,S_IFREG|0644,a->fd==3?(long)temp_len:0};
 memcpy((void *)a->ub,&s,sizeof(s));return 0;
}
static int sys_close(proc_t p,struct close_args *a,int *r) {(void)p;(void)a;(void)r;return 0;}
static int fake_rename(proc_t p,struct rename_args *a,int *r) {
 (void)p;(void)a;(void)r;if(fault==RENAME_FAIL)return EIO;
 memcpy(old,temp,temp_len);old[temp_len]=0;old_len=temp_len;temp_exists=0;return 0;
}
static int fake_unlink(proc_t p,struct unlink_args *a,int *r) {(void)p;(void)a;(void)r;temp_exists=0;return 0;}
#define mkdir fake_mkdir
#define open fake_open
#define write fake_write
#define fchown fake_chown
#define fchmod fake_chmod
#define fsync fake_fsync
#define rename fake_rename
#define unlink fake_unlink
"""
suffix = r"""
int main(void) {
 char scratch[4096];
 const char prior[] = { 'o', 'l', 'd', 0, 'x', 'm', 'l' };
 for(int f=FIRST_WRITE; f<=RENAME_FAIL; ++f) {
  memcpy(old,prior,sizeof(prior));old_len=sizeof(prior);fault=f;writes=temp_exists=marker_exists=0;
  assert(nuwa_boot_watchdog_policy((void *)1,(uintptr_t)scratch)!=0);
  assert(old_len==sizeof(prior) && !memcmp(old,prior,sizeof(prior)));assert(!temp_exists);
  assert(!nuwa_watchdog_policy_committed && nuwa_watchdog_policy_status!=0);
 }
 memcpy(old,prior,sizeof(prior));old_len=sizeof(prior);fault=writes=temp_exists=marker_exists=0;
 assert(nuwa_boot_watchdog_policy((void *)1,(uintptr_t)scratch)==0);
 assert(nuwa_watchdog_policy_committed && nuwa_watchdog_policy_status==0);
 assert(nuwa_watchdog_policy_labels==32); assert(strlen(old)==1502);
 char jobs[sizeof(nuwa_lite_jobs)]; strcpy(jobs,nuwa_lite_jobs);
 unsigned count=0;
 for(char *s=strtok(jobs,","); s; s=strtok(NULL,",")) {
  char key[160]; snprintf(key,sizeof(key),"<key>%s</key><true/>",s);
  char *at=strstr(old,key); assert(at && !strstr(at+1,key)); ++count;
 }
 assert(count==30);
 assert(strstr(old,"<key>com.apple.watchdogd</key><true/>"));
 assert(strstr(old,"<key>com.apple.watchdog</key><true/>"));
 assert(!temp_exists); puts("atomic watchdog policy cases: PASS");
}
"""
with tempfile.TemporaryDirectory() as tmp:
    c = Path(tmp) / "test.c"
    exe = Path(tmp) / "test"
    c.write_text(prefix + body + suffix)
    subprocess.run(["cc", "-std=gnu99", "-Wall", "-Wextra", str(c), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
