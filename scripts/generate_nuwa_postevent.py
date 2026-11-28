"""Add the nuwa post-event summary row to the r35 diagnostic renderer.

Diagnostic only.  Row 8 is drawn into the panic-safe band (page rows 0-8 at
scale 3, below the panic screen's y = h/8 clear), and row 7 carries the Data
first-attempt result.  Row 0 is left empty because the renderer's line()/bar()
guard drops row 0.  A photograph taken after the critical-process panic still
carries the last user-space state:

    row 7: [data-trial] DATA0 st=4 err=0 ro=0 dev=12345678 seed=1 first-attempt fua=N flush=N
    row 8: [data-trial] S p1=RUN sb=95:RUN EX=17:tzinit:0/45:pp=1

  fua/flush  diagnostic counters from the disposable NativeRamBlock, omitted
       in other builds.  In the FUA-permissive experiment (build define
       NUWA_FUA_TRIAL=1) row 7 also carries " FUA-EXP-nodur"; that label is a
       non-durability statement, not a write or flush success claim.

  p1   pid 1 state from the two-second process probe (absent when proc_find
       fails); this is a sample, not a live read at draw time.
  sb   SpringBoard from the same probe: never / gone / <pid>:<state>.
  EX   last recorded exit (every exit, including status 45 with signal 0):
       pid, comm (12 chars), signal/exit status, parent pid.  pp=? when the
       kernel hook did not supply a parent for that pid.
  DATA0  the completed first Data mount attempt (st/err/ro/dev/seed), latched
       by nuwa_data_mount_prepare before initproc exec.  DATA now is the
       sampled in-progress stage; DATA0 not run means it never started.

The kernel side supplies parent pids through boot_progress_exit_parent(),
called immediately before boot_progress_exit() in proc_prepareexit(), and
paints the two lines synchronously from proc_handle_critical_exit() after
proc_crash_coredump()/sync() and immediately before panic_with_options().
The critical paint writes directly through px_text() into the existing
display.frame rows 7 and 8; it does not require display.bound, render_busy or
exit_lock.  No boot, storage, authentication or write path reads any of this
state.
"""
from hashlib import sha256

MARKER = b"static const char bp_post_event_tag[] __attribute__((used)) = \"NUWA-POSTEVENT-20261127\";\n"

STATE_ANCHOR = b"static char build_tag[32];\nconst char *boot_progress_tag(void) { return build_tag; }\n"

STATE = b"""// NUWA-POSTEVENT-20261127: event-time summary for the panic-safe band.
// Diagnostic only: no boot, storage, authentication or write decision reads it.
struct bp_post_exit {
  unsigned valid,pid,status,ns;
  int ppid;
  char comm[17];
};
static struct bp_post_exit bp_post_exit;
static struct bp_post_exit bp_critical;
static volatile unsigned bp_critical_valid;
static unsigned bp_post_lock;
static volatile uint64_t bp_post_parent; // high 32: pid, low 32: parent pid
""" + MARKER + b"""extern volatile uint32_t nuwa_pid1_present,nuwa_pid1_state;
extern volatile uint64_t nuwa_sb_public;
#if defined(NUWA_DISPOSABLE_DATA)
extern volatile uint64_t nuwa_disposable_fua_requests,nuwa_disposable_flushes;
#endif
extern int nuwa_data_mount_summary(char *,size_t);
#if defined(NUWA_FUA_TRIAL) && NUWA_FUA_TRIAL
static const char bp_fua_trial_tag[] __attribute__((used)) = "NUWA-FUA-TRIAL-20261127";
#endif
void boot_progress_critical_capture(int pid,const char *name,int status,unsigned ns,
  uint64_t code,int ppid);
void boot_progress_critical_capture(int pid,const char *name,int status,unsigned ns,
  uint64_t code,int ppid) {
  (void)code; // the summary shows the wait status, not the Mach exception code
  bp_critical.valid=1;
  bp_critical.pid=(unsigned)pid;
  bp_critical.ppid=ppid;
  bp_critical.status=(unsigned)status;
  bp_critical.ns=ns;
  strlcpy(bp_critical.comm,name?name:"?",sizeof bp_critical.comm);
  __atomic_store_n(&bp_critical_valid,1,__ATOMIC_RELEASE);
}
void boot_progress_exit_parent(int pid,int ppid);
void boot_progress_exit_parent(int pid,int ppid) {
  __atomic_store_n(&bp_post_parent,
    ((uint64_t)(uint32_t)pid<<32)|(uint32_t)ppid,__ATOMIC_RELEASE);
}
static int bp_post_parent_for(unsigned pid) {
  uint64_t v=__atomic_load_n(&bp_post_parent,__ATOMIC_ACQUIRE);
  return ((uint32_t)(v>>32)==pid)?(int32_t)(uint32_t)v:-1;
}
static void bp_post_latch(int pid,const char *name,int status,unsigned ns) {
  if(__atomic_exchange_n(&bp_post_lock,1,__ATOMIC_ACQUIRE)) return;
  bp_post_exit.valid=1;
  bp_post_exit.pid=(unsigned)pid;
  bp_post_exit.ppid=bp_post_parent_for((unsigned)pid);
  bp_post_exit.status=(unsigned)status;
  bp_post_exit.ns=ns;
  strlcpy(bp_post_exit.comm,name?name:"?",sizeof bp_post_exit.comm);
  __atomic_store_n(&bp_post_lock,0,__ATOMIC_RELEASE);
}
static int bp_post_snapshot(struct bp_post_exit *out) {
  if(__atomic_exchange_n(&bp_post_lock,1,__ATOMIC_ACQUIRE)) return 0;
  *out=bp_post_exit;
  int valid=(int)out->valid;
  __atomic_store_n(&bp_post_lock,0,__ATOMIC_RELEASE);
  return valid;
}
static const char *bp_post_stat(unsigned stat) {
  static const char *const names[]={"IDL","RUN","SLP","STP","ZMB"};
  return (stat>=1 && stat<=5)?names[stat-1]:"?";
}
static const char *bp_post_sb(char *out,size_t size) {
  uint64_t w=__atomic_load_n(&nuwa_sb_public,__ATOMIC_ACQUIRE);
  if(!(w & (1ull<<63))) return "never";
  if(!(w & (1ull<<62))) return "gone";
  snprintf(out,size,"%u:%s",(unsigned)((w>>32)&0x3fffffffu),
    bp_post_stat((unsigned)(w&0xffffffffu)));
  return out;
}
static int bp_post_format(char *buf,size_t size,const struct bp_post_exit *e) {
  char core[80],sb[24];
  const char *p1=!__atomic_load_n(&nuwa_pid1_present,__ATOMIC_ACQUIRE)?"absent":
    bp_post_stat(__atomic_load_n(&nuwa_pid1_state,__ATOMIC_ACQUIRE));
  unsigned sig=e->status&127u, code=(e->status>>8)&255u;
  if(e->ppid>=0)
    snprintf(core,sizeof core,"S p1=%s sb=%s EX=%u:%.12s:%u/%u:pp=%d",p1,
      bp_post_sb(sb,sizeof sb),e->pid,e->comm,sig,code,e->ppid);
  else
    snprintf(core,sizeof core,"S p1=%s sb=%s EX=%u:%.12s:%u/%u:pp=?",p1,
      bp_post_sb(sb,sizeof sb),e->pid,e->comm,sig,code);
  if(build_tag[0]) snprintf(buf,size,"[%s] %s",build_tag,core);
  else snprintf(buf,size,"%s",core);
  return 1;
}
static int bp_post_event_row(char *buf,size_t size) {
  struct bp_post_exit e;
  if(!bp_post_snapshot(&e)) return 0;
  return bp_post_format(buf,size,&e);
}
// Same-thread read after boot_progress_critical_capture(); the critical paint
// runs in the exiting thread after coredump/sync, so it uses the copy taken
// before those calls and needs no render/exit lock.
static int bp_post_event_row_direct(char *buf,size_t size) {
  if(__atomic_load_n(&bp_critical_valid,__ATOMIC_ACQUIRE))
    return bp_post_format(buf,size,&bp_critical);
  if(!bp_post_exit.valid) return 0;
  return bp_post_format(buf,size,&bp_post_exit);
}
static int bp_post_ready(void) {
  return (int)__atomic_load_n(&bp_post_exit.valid,__ATOMIC_ACQUIRE);
}
// Diagnostic only: accepted FUA requests and successful non-durable flushes.
// FUA-EXP-nodur is present only in the compile-time experimental package; it
// explicitly says the package is not a media-durability claim.
static void bp_fua_suffix(char *buf,size_t size) {
#if defined(NUWA_DISPOSABLE_DATA)
  size_t used=strlen(buf);
  if(used>=size) return;
  snprintf(buf+used,size-used," fua=%llu flush=%llu%s",
    (unsigned long long)__atomic_load_n(&nuwa_disposable_fua_requests,__ATOMIC_RELAXED),
    (unsigned long long)__atomic_load_n(&nuwa_disposable_flushes,__ATOMIC_RELAXED),
#if defined(NUWA_FUA_TRIAL) && NUWA_FUA_TRIAL
    " FUA-EXP-nodur"
#else
    ""
#endif
  );
#else
  (void)buf;
  (void)size;
#endif
}
"""

BOOT_EXIT_ANCHOR = b"void boot_progress_exit(int pid,const char *name,int status,unsigned ns,uint64_t code) {\n"
BOOT_EXIT_ENABLED_ANCHOR = b"  if(!enabled)return;\n"

CRITICAL_PAINT = b"""static void px_text(unsigned,unsigned,const char *,unsigned,uint32_t,uint32_t);
// Called only from proc_handle_critical_exit(), after proc_crash_coredump() and
// sync(), immediately before panic_with_options().  Draws exactly two rows
// through px_text() into the already-mapped display.frame, so it works after
// boot_progress_prepare_scanout() cleared display.bound.  No full-page refresh,
// no render_busy and no exit_lock.
void boot_progress_critical_paint(void);
void boot_progress_critical_paint(void) {
  if(!display.frame || !display.scale || !display.stride ||
     !display.width || !display.height) return;
  char data[BP_COLS],summary[80];
  (void)nuwa_data_mount_summary(data,sizeof data);
  bp_fua_suffix(data,sizeof data);
  (void)bp_post_event_row_direct(summary,sizeof summary);
  unsigned cell=14u*display.scale;
  unsigned cols=display.width/(6u*display.scale);
  if(cols>BP_COLS-1) cols=BP_COLS-1;
  unsigned limit=display.height/8u;
  unsigned row_data=7u,row_summary=8u;
  if((row_summary+1u)*cell>limit) { row_summary=7u; row_data=6u; }
  if((row_data+1u)*cell<=limit) px_text(0,row_data*cell,data,cols,0xffffaa00,0xff000000);
  if((row_summary+1u)*cell<=limit) px_text(0,row_summary*cell,summary,cols,0xffffff00,0xff000000);
  __asm__ volatile("dsb sy" ::: "memory");
}
"""

V1_ROWS = b"""extern const char *volatile nuwa_data_persist_open_why;
extern volatile uint64_t nuwa_v1_write_failure,nuwa_v1_write_failure_attached;
extern volatile uint64_t nuwa_v1_ufs_write_failure;
static const char *bp_v1_write_source(unsigned source) {
  static const char *const names[]={"-","arg","gate","offline","inactive",
                                    "prior","ufs-r","ufs-w","copy","overlay","memory"};
  return source < sizeof names / sizeof names[0] ? names[source] : "?";
}
static void bp_v1_rows(char rows[3][BP_COLS]) {
  const char *why=nuwa_data_persist_open_why;
  uint64_t first=__atomic_load_n(&nuwa_v1_write_failure,__ATOMIC_RELAXED);
  uint64_t after=__atomic_load_n(&nuwa_v1_write_failure_attached,__ATOMIC_RELAXED);
  uint64_t ufs=__atomic_load_n(&nuwa_v1_ufs_write_failure,__ATOMIC_RELAXED);
  snprintf(rows[0],BP_COLS,"D1 st=%u h=%u pres=%llu why=%s",
    native_data_persist_state,native_data_persist_header,
    (unsigned long long)native_data_persist_present,why?why:"-");
  snprintf(rows[1],BP_COLS,"D2 wr=%llu er=%llu ufs=%x:%02x:%06x",
    (unsigned long long)native_data_persist_writes,
    (unsigned long long)native_data_persist_errors,(unsigned)(ufs>>32),
    (unsigned)(ufs>>24)&0xffu,(unsigned)ufs&0xffffffu);
  snprintf(rows[2],BP_COLS,"D3 first=%s/%08x after=%s/%08x",
    bp_v1_write_source((unsigned)(first>>32)),(unsigned)first,
    bp_v1_write_source((unsigned)(after>>32)),(unsigned)after);
}
"""

DRAW_END_ANCHOR = b"  __asm__ volatile(\"dsb sy\" ::: \"memory\");\n  last_draw=now;"
DRAW_END = b"""  {
    char data[BP_COLS],full[BP_COLS];
    int state=nuwa_data_mount_summary(data,sizeof data);
    if(state>0) {
      bp_fua_suffix(data,sizeof data);
      if(build_tag[0] && snprintf(full,sizeof full,"[%s] %s",build_tag,data)<(int)sizeof full)
        line(7,full,0xffffaa00);
      else line(7,data,0xffffaa00);
    }
    if(bp_post_ready()) {
      char post[80];
      if(bp_post_event_row(post,sizeof post)) line(8,post,0xffffff00);
      if(state==0) line(7,"DATA0 not run",0xffffaa00);
    }
  }
  __asm__ volatile("dsb sy" ::: "memory");
  last_draw=now;"""

SBTH_DECL = b"static void bp_sbth_paint(int);\n"
SBTH_PAINT = b"""extern unsigned nuwa_sbth_rows(char (*)[120], unsigned);
// The unused top row survives the panic clear. Detail rows occupy the
// removed glyph-example area, before the retained comb (48*cell+344).
static void bp_sbth_paint(int critical) {
  if(!display.frame || !display.scale || !display.stride ||
     !display.width || !display.height) return;
  if(!critical && (!display.bound ||
     __atomic_load_n(&display.yield_requested,__ATOMIC_ACQUIRE))) return;
  char rows[5][120];
  unsigned used=nuwa_sbth_rows(rows,critical?1:5);
  unsigned cell=14u*display.scale, cols=display.width/(6u*display.scale);
  if(cols>BP_COLS-1) cols=BP_COLS-1;
  if(cell<=display.height/8u)
    px_text(0,0,rows[0],cols,0xff00ffcc,0xff000000);
  if(critical) return;
  for(unsigned i=0;i<4 && (49u+i)*cell<=display.height && (i+1u)*cell<=344u;++i) {
    if(__atomic_load_n(&display.yield_requested,__ATOMIC_ACQUIRE)) return;
    px_text(0,(48u+i)*cell,i+1<used?rows[i+1]:"",cols,0xff00ffcc,0xff000000);
  }
}
"""


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError("post-event anchor changed: %r" % (old[:80],))
    return text.replace(old, new, 1)


def generate(src, *, sb_threads=False, v1_nodur=False):
    digest = sha256(src).hexdigest()
    text = replace_once(src, STATE_ANCHOR, STATE_ANCHOR + STATE)
    text = replace_once(text, BOOT_EXIT_ANCHOR, CRITICAL_PAINT + BOOT_EXIT_ANCHOR)
    text = replace_once(text, BOOT_EXIT_ENABLED_ANCHOR,
                        BOOT_EXIT_ENABLED_ANCHOR + b"  bp_post_latch(pid,name,status,ns);\n")
    text = replace_once(text, DRAW_END_ANCHOR, DRAW_END)
    if v1_nodur:
        text = replace_once(text, STATE_ANCHOR,
                            STATE_ANCHOR + b"static void bp_v1_rows(char rows[3][BP_COLS]);\n")
        declaration = CRITICAL_PAINT.splitlines(keepends=True)[0]
        text = replace_once(text, declaration, declaration + V1_ROWS)
        text = replace_once(text, b"  unsigned row_data=7u,row_summary=8u;\n"
                                  b"  if((row_summary+1u)*cell>limit) { row_summary=7u; row_data=6u; }",
                            b"  unsigned row_data=7u,row_summary=8u;\n"
                            b"  if((row_summary+1u)*cell>limit) { row_summary=7u; row_data=6u; }\n"
                            b"  if(row_data>=3u && (row_data+1u)*cell<=limit) {\n"
                            b"    char rows[3][BP_COLS]; bp_v1_rows(rows);\n"
                            b"    for(unsigned i=0;i<3;++i)\n"
                            b"      px_text(0,(row_data-3u+i)*cell,rows[i],cols,0xff00ffcc,0xff000000);\n"
                            b"  }")
        text = replace_once(text, b"    char data[BP_COLS],full[BP_COLS];",
                            b"    char rows[3][BP_COLS]; bp_v1_rows(rows);\n"
                            b"    for(unsigned i=0;i<3;++i) line(4u+i,rows[i],0xff00ffcc);\n"
                            b"    char data[BP_COLS],full[BP_COLS];")
        text = replace_once(text, b'line(7,"DATA0 not run",',
                            b'line(7,"[V1-NODUR] DATA0 not run",')
        text = replace_once(text, b"  char data[BP_COLS],summary[80];\n"
                                  b"  (void)nuwa_data_mount_summary(data,sizeof data);",
                            b'  char data[BP_COLS]="[V1-NODUR] ",summary[80];\n'
                            b'  const size_t prefix=sizeof "[V1-NODUR] "-1;\n'
                            b'  (void)nuwa_data_mount_summary(data+prefix,sizeof data-prefix);')
    if sb_threads:
        text = replace_once(text, STATE_ANCHOR, STATE_ANCHOR + SBTH_DECL)
        declaration = CRITICAL_PAINT.splitlines(keepends=True)[0]
        text = replace_once(text, declaration, declaration + SBTH_PAINT)
        text = replace_once(text, b"  unsigned row_data=7u,row_summary=8u;",
                            b"  bp_sbth_paint(1);\n  unsigned row_data=7u,row_summary=8u;")
        text = replace_once(text, DRAW_END_ANCHOR,
                            b"  if(!__atomic_load_n(&display.yield_requested,__ATOMIC_ACQUIRE)) bp_sbth_paint(0);\n"
                            + DRAW_END_ANCHOR)
    return text, digest
