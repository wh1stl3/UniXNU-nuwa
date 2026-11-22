#!/usr/bin/env python3
"""Replay the real MG reset against a fault-injected initproc syscall model."""
from pathlib import Path
import subprocess
import tempfile

source = (Path(__file__).resolve().parents[1] /
          "package/nuwa-watchdog/nuwa_mg_reset.c").read_text()
prefix = r"""
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
typedef void *proc_t;
typedef uintptr_t user_addr_t;
typedef long user_ssize_t;
#define _PC_CASE_SENSITIVE 11
#define O_NOFOLLOW_ANY 0x20000000
#define RENAME_EXCL 4
#define RENAME_NOFOLLOW_ANY 16
#define stat64 fake_stat64
struct fake_stat64 { dev_t st_dev; int st_mode, st_uid, st_nlink; };
struct openat_args { int fd; user_addr_t path; int flags, mode; };
struct close_args { int fd; };
struct fstat64_args { int fd; user_addr_t ub; };
struct fstatat64_args { int fd; user_addr_t path, ub; int flag; };
struct renameatx_np_args { int fromfd; user_addr_t from; int tofd; user_addr_t to; unsigned flags; };
struct write_args { int fd; user_addr_t cbuf; size_t nbyte; };
struct fsync_args { int fd; };
struct fpathconf_args { int fd, name; };
enum { ROOT=3, DB, JOURNAL, PREFS, CACHES };
static int arg, cs, opens, active, attempt, writes, short_at, sync_error, journal_error;
static int present[3], backup[3], rename_error[3], case_error, parent_error, source_mode;
static char logbuf[2048];
static size_t used;

static int PE_parse_boot_argn(const char *key, void *value, size_t length) {
 assert(!strcmp(key,"nuwa-mg-reset") && length==sizeof(unsigned));
 *(unsigned *)value=arg; return arg>=0;
}
static int copyout(const void *s,user_addr_t d,size_t n) { memcpy((void *)d,s,n); return 0; }
static int copyin(user_addr_t s,void *d,size_t n) { memcpy(d,(void *)s,n); return 0; }
static int fake_openat(proc_t p,struct openat_args *a,int *r) {
 (void)p; ++opens;
 assert(a->flags&O_NOFOLLOW_ANY);
 const char *path=(const char *)a->path;
 if (!strcmp(path,"/private/var")) *r=ROOT;
 else if (!strcmp(path,"/private/var/db")) *r=DB;
 else if (!strcmp(path,"nuwa-mg-reset.journal")) {
  assert(a->fd==DB && (a->flags&O_APPEND) && !(a->flags&O_TRUNC) && a->mode==0600);
  if(journal_error) return journal_error;
  *r=JOURNAL;
 } else if (strstr(path,"/Preferences")) *r=PREFS;
 else if (strstr(path,"/Caches")) {
  if(parent_error) return parent_error;
  *r=CACHES;
 } else assert(0);
 if(*r!=JOURNAL) assert(a->flags&O_DIRECTORY);
 assert(!(active&(1<<*r))); active|=1<<*r;
 return 0;
}
static int sys_close(proc_t p,struct close_args *a,int *r) {
 (void)p; (void)r; assert(active&(1<<a->fd)); active&=~(1<<a->fd); return 0;
}
static int sys_fstat64(proc_t p,struct fstat64_args *a,int *r) {
 (void)p; (void)r;
 struct fake_stat64 st={7,a->fd==JOURNAL ? S_IFREG|0600 : S_IFDIR|0755,0,1};
 return copyout(&st,a->ub,sizeof(st));
}
static int index_of(int fd,const char *name) {
 assert(fd==PREFS || fd==CACHES);
 return fd==CACHES ? 2 : (cs && strstr(name,".mobilegestalt.") ? 1 : 0);
}
static int fstatat64(proc_t p,struct fstatat64_args *a,int *r) {
 (void)p; (void)r; assert(a->flag==AT_SYMLINK_NOFOLLOW);
 const char *name=(const char *)a->path;
 int i=index_of(a->fd,name), bak=strstr(name,".nuwa-bak")!=NULL;
 struct fake_stat64 st={7,bak ? S_IFLNK : source_mode,501,1};
 return !(bak ? backup[i] : present[i]) ? ENOENT : copyout(&st,a->ub,sizeof(st));
}
static int renameatx_np(proc_t p,struct renameatx_np_args *a,int *r) {
 (void)p; (void)r; ++attempt;
 const char *name=(const char *)a->from,*bak=(const char *)a->to;
 int i=index_of(a->fromfd,name); size_t len=strlen(name);
 assert(a->flags==(RENAME_EXCL|RENAME_NOFOLLOW_ANY) && a->fromfd==a->tofd);
 assert(!strncmp(name,bak,len) && !strcmp(bak+len,".nuwa-bak"));
 assert(present[i] && !backup[i]);
 if(rename_error[i]) return rename_error[i];
 present[i]=0; backup[i]=1; return 0;
}
static int sys_fpathconf(proc_t p,struct fpathconf_args *a,int *r) {
 (void)p; assert(a->fd==PREFS && a->name==_PC_CASE_SENSITIVE);
 *r=cs; return case_error;
}
static int fake_write(proc_t p,struct write_args *a,user_ssize_t *r) {
 (void)p; assert(a->fd==JOURNAL && used+a->nbyte<sizeof(logbuf));
 size_t n=a->nbyte-(++writes==short_at);
 memcpy(logbuf+used,(void *)a->cbuf,n); used+=n; logbuf[used]=0; *r=n; return 0;
}
static int fake_fsync(proc_t p,struct fsync_args *a,int *r) {
 (void)p; (void)r; assert(a->fd==JOURNAL); return sync_error;
}
#define openat fake_openat
#define write fake_write
#define fsync fake_fsync
volatile uint32_t native_data_persist_state;
"""
suffix = r"""
static void reset(void) {
 arg=cs=1; source_mode=S_IFREG|0600;
 native_data_persist_state=2;
 opens=attempt=writes=short_at=sync_error=journal_error=case_error=parent_error=0;
 used=0; logbuf[0]=0; nuwa_mg_reset_diag=0;
 for(int i=0;i<3;i++) { present[i]=1; backup[i]=rename_error[i]=0; }
}
static void run(int ro,unsigned diag,int n) {
 char scratch[4096];
 nuwa_mg_reset((void *)1,(uintptr_t)scratch,ro);
 assert(nuwa_mg_reset_diag==diag && attempt==n && !active);
}
int main(void) {
 for(int a=-1;a<=2;a++) if(a!=1) { reset(); arg=a; run(0,0,0); assert(!opens); }
 for(unsigned ds=0;ds<=8;ds++) if(ds!=2) {
  reset(); native_data_persist_state=ds; run(0,0x400,0);
  assert(!opens && !writes && present[0] && present[1] && present[2]);
 }
 reset(); run(1,0x300,0); assert(!opens);
 reset(); run(0,0x103,3); assert(strstr(logbuf,"mobilegestalt.plist exists=yes result=renamed"));
 reset(); cs=0; run(0,0x102,2); assert(strstr(logbuf,"exists=yes result=case-alias-see-first"));
 /* Recreated cache plus existing backup: both entries survive, no new rename. */
 reset(); cs=0; backup[0]=1; parent_error=ENOENT; run(0,0x100,0);
 assert(present[0] && backup[0] && strstr(logbuf,"result=backup-exists") &&
        strstr(logbuf,"exists=no result=parent-absent"));
 reset(); present[0]=0; rename_error[1]=EACCES; rename_error[2]=EEXIST; run(0,0x110,2);
 assert(strstr(logbuf,"exists=no result=absent") && strstr(logbuf,"exists=yes result=rename") &&
        strstr(logbuf,"result=backup-exists"));
 reset(); case_error=ENOTSUP; run(0,0x121,1); assert(strstr(logbuf,"result=case-query"));
 reset(); source_mode=S_IFLNK; run(0,0x130,0); assert(strstr(logbuf,"not-a-local-regular-file"));
 reset(); journal_error=ELOOP; run(0,0x300,0);
 reset(); short_at=1; run(0,0x300,0);
 reset(); short_at=2; run(0,0x301,1); assert(present[1] && present[2]);
 reset(); sync_error=EIO; run(0,0x303,3);
 puts("MG-reset syscall model passed");
}
"""
with tempfile.TemporaryDirectory() as temp:
    c = Path(temp) / "test.c"
    exe = c.with_suffix("")
    c.write_text(prefix + source[source.index('#define DATA '):] + suffix)
    subprocess.run(["cc", "-std=gnu99", "-O2", "-Wall", "-Wextra", "-Werror",
                    str(c), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
