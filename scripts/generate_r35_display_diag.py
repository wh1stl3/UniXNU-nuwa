#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Patent
"""Add the display bring-up status to the pinned r35l diagnostic renderer."""

from hashlib import sha256

RENDERER_SHA = "bdfa725105977af83a9917be0209fe6701914587808d7f1b9c04a6fb4adb0c3e"

BANNER_SELECTION = b"""
// Stable within each priority class; continuation rows inherit their header.
static unsigned bp_banner_priority(const char *s, unsigned previous) {
  if (s[0]==' ') return previous;
  if (!strncmp(s,"CRASH",5) || !strncmp(s,"REASON",6) ||
      !strncmp(s,"PANIC",5) || !strncmp(s,"EXIT",4) ||
      !strncmp(s,"XR",2) || !strncmp(s,"PROC",4) ||
      !strncmp(s,"SVC",3) || !strncmp(s,"SC ",3)) return 0;
  if (!strncmp(s,"LOAD",4) || !strncmp(s,"UFS",3) ||
      !strncmp(s,"SCHED",5)) return 1;
  if (!strncmp(s,"GPU",3)) return 3;
  return 2;
}
static unsigned bp_banner_select(char rows[][120], unsigned n, unsigned budget) {
  unsigned priority[48], previous=2;
  for (unsigned i=0;i<n;++i) {
    previous=bp_banner_priority(rows[i],previous);
    priority[i]=previous;
  }
  for (unsigned i=1;i<n;++i) {
    char row[120]; unsigned p=priority[i],j=i;
    memcpy(row,rows[i],120);
    while (j && priority[j-1]>p) {
      memcpy(rows[j],rows[j-1],120); priority[j]=priority[j-1]; --j;
    }
    memcpy(rows[j],row,120); priority[j]=p;
  }
  return n<budget?n:budget;
}
"""


def replace_once(src, anchor, replacement):
    if src.count(anchor) != 1:
        raise ValueError(f"r35l renderer anchor changed: {anchor!r}")
    return src.replace(anchor, replacement, 1)


def generate(src, *, mg_reset=False):
    if sha256(src).hexdigest() != RENDERER_SHA:
        raise ValueError("expected the pinned r35l full renderer")
    src = replace_once(src, b"static void crash_banner(unsigned now) {", b"""
// At most six characters including unit; a prefix denotes rounding down.
static void bp_short_value(char out[7], uint64_t value, const char *unit) {
  static const char prefix[] = " kMGTPE";
  unsigned p=0;
  if (value > (unit[0] ? 9999ULL : 999999ULL)) {
    do { value /= 1000; ++p; } while (value > 999 && p < 6);
    snprintf(out,7,"%llu%c%s",(unsigned long long)value,prefix[p],unit);
  } else snprintf(out,7,"%llu%s",(unsigned long long)value,unit);
}
static void crash_banner(unsigned now) {""")
    src = replace_once(src, b"""      snprintf(rows[n++],120,"UFS   since last: verify=%llums read=%llums blocks=%llu reqs=%llu | total verify=%llums read=%llums reqs=%llu",
        (unsigned long long)((v-banner_ufs_v)*1000/f),(unsigned long long)((r-banner_ufs_r)*1000/f),(unsigned long long)(b-banner_ufs_b),
        (unsigned long long)(q-banner_ufs_n),(unsigned long long)(v*1000/f),(unsigned long long)(r*1000/f),(unsigned long long)q);""", b"""      char lr[7],ld[7],tr[7],td[7];
      bp_short_value(lr,q-banner_ufs_n,"");
      bp_short_value(ld,(r-banner_ufs_r)*1000/f,"ms");
      bp_short_value(tr,q,"");
      bp_short_value(td,r*1000/f,"ms");
      (void)(v-banner_ufs_v); (void)(b-banner_ufs_b);
      snprintf(rows[n++],120,"UFS L r=%s rd=%s T r=%s rd=%s",lr,ld,tr,td);""")
    src = replace_once(src, b"""    snprintf(rows[n++],120,"SCHED 30ms sleeps since last: n=%llu mean_late_us=%llu max_late_us=%llu >50ms=%llu | irq timer=%llu ipi=%llu",
      (unsigned long long)(sn-banner_sleep_n),(unsigned long long)((ss-banner_sleep_sum)/dn),(unsigned long long)sm,
      (unsigned long long)(sl-banner_sleep_late),(unsigned long long)(ti-banner_tint),(unsigned long long)(ip-banner_ipi));""", b"""    char count[7],mean[7],max[7],late[7];
    bp_short_value(count,sn-banner_sleep_n,"");
    bp_short_value(mean,(ss-banner_sleep_sum)/dn,"us");
    bp_short_value(max,sm,"us");
    bp_short_value(late,sl-banner_sleep_late,"");
    (void)(ti-banner_tint); (void)(ip-banner_ipi);
    snprintf(rows[n++],120,"SCHED n=%s m=%s x=%s >50=%s",count,mean,max,late);""")
    src = replace_once(src, b'#include <string.h>\n', b"""#include <string.h>
struct proc;
extern struct proc *proc_find(int);
extern int proc_rele(struct proc *);
extern void proc_name(int, char *, int);
extern void psignal(struct proc *, int);
""")
    src = replace_once(src, b"static void touch_monitor(void *arg, wait_result_t result) {", b"""
// Only touch_monitor calls this, before acquiring render_busy.
static void bp_proc_census(unsigned restart, unsigned now) {
  uint32_t found[6]={0}, services=0;
  unsigned killed_pid=0;
  for (int pid=1;pid<=4096;++pid) {
    struct proc *p=proc_find(pid);
    if (!p) continue;
    char name[32];
    proc_name(pid,name,sizeof(name));
    if (!strcmp(name,"SpringBoard")) {
      found[0]=(uint32_t)pid;
      if (restart && !killed_pid) {
        killed_pid=(unsigned)pid;
        psignal(p,9);
      }
    }
    else if (!strcmp(name,"backboardd")) found[1]=(uint32_t)pid;
    else if (!strcmp(name,"lsd")) found[2]=(uint32_t)pid;
    else if (!strcmp(name,"launchd")) found[3]=(uint32_t)pid;
    else if (!strcmp(name,"lockdownd")) found[4]=(uint32_t)pid;
    else if (!strcmp(name,"containermanager")) found[5]=(uint32_t)pid;
    else if (!strcmp(name,"runningboardd")) services|=1u<<0;
    else if (!strcmp(name,"distnoted")) services|=1u<<1;
    else if (!strcmp(name,"cfprefsd")) services|=1u<<2;
    else if (!strcmp(name,"notifyd")) services|=1u<<3;
    else if (!strcmp(name,"securityd")) services|=1u<<4;
    else if (!strcmp(name,"mobileactivation")) services|=1u<<5;
    proc_rele(p);
  }
  if (restart) {
    unsigned state=__atomic_load_n(&bp_sb_restart_state,__ATOMIC_RELAXED);
    unsigned failures=(state>>8)+(killed_pid ? 0u : 1u);
    __atomic_store_n(&bp_sb_restart_state,restart|(failures<<8),__ATOMIC_RELAXED);
    printf("nuwa-sb-restart: attempt=%u time=%u pid=%u psignal=%s\\n",
      restart,now,killed_pid,killed_pid ? "called" : "not-called");
  }
  for (unsigned i=0;i<6;++i) __atomic_store_n(&bp_proc_pid[i],found[i],__ATOMIC_RELAXED);
  __atomic_store_n(&bp_svc_mask,services,__ATOMIC_RELAXED);
  __atomic_fetch_add(&bp_proc_generation,1,__ATOMIC_RELEASE);
}
static void touch_monitor(void *arg, wait_result_t result) {""")
    src = replace_once(src, b"  for(;;) {\n    touch_overlay();", b"""  unsigned census_at=0, census_started=0, restart_at=0, restart_every=0;
  unsigned restart_count=0, restart_last=0;
  PE_parse_boot_argn("nuwa-sb-restart",&restart_at,sizeof(restart_at));
  PE_parse_boot_argn("nuwa-sb-restart-every",&restart_every,sizeof(restart_every));
  if (restart_at && restart_at<60) restart_at=60;
  if (restart_every && restart_every<120) restart_every=120;
  for(;;) {
    unsigned now=seconds();
    if (nprocs>0 && (!census_started || now-census_at>=10)) {
      unsigned restart=0;
      if (restart_at && restart_count<4 &&
          ((!restart_count && now>=restart_at) ||
           (restart_count && restart_every && now-restart_last>=restart_every))) {
        restart=++restart_count;
        restart_last=now;
      }
      bp_proc_census(restart,now);
      census_at=now; census_started=1;
    }
    touch_overlay();""")
    anchor = b"char boot_progress_page_text[48][BP_COLS];"
    src = replace_once(src, anchor, b"""static uint32_t bp_proc_pid[6], bp_proc_generation, bp_svc_mask, bp_sb_restart_state;
// FDR exits are independent of the best-effort exit ring.
static uint64_t bp_fdr_exit;
// Diagnostic only: two independent byte samples; no synchronization of display state.
static uint8_t bp_dsp_stage, bp_dsp_reason;
static uint16_t bp_dsp_properties;
extern uint64_t nuwa_cli_enter __attribute__((weak_import));
extern uint64_t nuwa_cli_observed __attribute__((weak_import));
extern uint64_t nuwa_cli_identity __attribute__((weak_import));
extern uint32_t nuwa_sc_calls __attribute__((weak_import));
extern uint32_t nuwa_sc_rejects __attribute__((weak_import));
extern uint32_t nuwa_sc_ok __attribute__((weak_import));
// 8796-native-text-fixup exports these; absent means the mechanism is not compiled in.
extern uint32_t cs_text_fixup_parsed __attribute__((weak_import));
extern uint32_t cs_text_fixup_applied __attribute__((weak_import));
#if NUWA_HID_STANDIN
extern uint32_t nuwa_hid_stage;
#endif
void boot_progress_diag_set(uint8_t stage, uint8_t reason);
void boot_progress_diag_set(uint8_t stage, uint8_t reason) {
  __atomic_store_n(&bp_dsp_reason,reason,__ATOMIC_RELAXED);
  __atomic_store_n(&bp_dsp_stage,stage,__ATOMIC_RELAXED);
}
void boot_progress_prop_set(uint16_t properties);
void boot_progress_prop_set(uint16_t properties) {
  __atomic_store_n(&bp_dsp_properties,properties,__ATOMIC_RELAXED);
}
""" + anchor)
    src = replace_once(src, b"+gpu_sig*17ULL;", b"+gpu_sig*17ULL+__atomic_load_n(&bp_proc_generation,__ATOMIC_ACQUIRE)*65537ULL;")
    src = replace_once(src, b"static void crash_banner(unsigned now) {",
                       BANNER_SELECTION + b"static void crash_banner(unsigned now) {")
    start = src.index(b"  // SpringBoard's threads as the stack tracer")
    end = src.index(b"  // Where the time goes:", start)
    src = src[:start] + b"  unsigned stack_rows=0;\n" + src[end:]
    src = replace_once(src,
        b"  if(!n)return;\n  unsigned cell=14*display.scale,cols=display.width/(6*display.scale);if(cols>119)cols=119;\n  if(display.height<(n+2)*cell+8)return;",
        b"""  unsigned cell=14*display.scale,cols=display.width/(6*display.scale);if(cols>119)cols=119;
  unsigned half=display.height/2;
  if(half<8+2*cell)return;
  unsigned budget=(half-8)/cell-2;
  if(budget>24)budget=24;
  n=bp_banner_select(rows,n,budget);
  // Existing diagnostic rows own the budget first; stacks use only the remainder.
  if(&boot_ui_trace_role_rows && n<budget) {
    static const unsigned roles[3]={1,3,0},limit[3]={8,7,6};
    for(unsigned k=0;k<3 && n<budget;++k) {
      unsigned room=budget-n;
      unsigned got=boot_ui_trace_role_rows(roles[k],rows+n,room<limit[k]?room:limit[k],k==0);
      n+=got;
    }
  }
  if(!n || display.height<(n+2)*cell+8)return;""")
    # Use the short DATA-summary slot; its full detail remains on row 39.
    start = src.index(b"  // Row 9: the Data mount result")
    end = src.index(b"#endif\n", start)
    src = src[:start] + b"""  unsigned dsp_stage = __atomic_load_n(&bp_dsp_stage,__ATOMIC_RELAXED);
  unsigned dsp_reason = __atomic_load_n(&bp_dsp_reason,__ATOMIC_RELAXED);
  if (&nuwa_cli_enter && &nuwa_cli_observed && &nuwa_cli_identity) {
    uint64_t in = __atomic_load_n(&nuwa_cli_enter,__ATOMIC_RELAXED);
    uint64_t out = __atomic_load_n(&nuwa_cli_observed,__ATOMIC_RELAXED);
    uint64_t identity = __atomic_load_n(&nuwa_cli_identity,__ATOMIC_RELAXED);
    char bb = ((identity >> 32) || (identity & 2)) ? '?' : ((identity & 1) ? '1' : '0');
    snprintf(b,sizeof(b),"DSP s=%u r=%u CLI in=%u out=%u ret=%08x bb=%c",
      dsp_stage,dsp_reason,(unsigned)(in>>32),(unsigned)(out>>32),
      (unsigned)out,bb);
  } else snprintf(b,sizeof(b),"DSP s=%u r=%u CLI unavailable",dsp_stage,dsp_reason);
  line(9,b,dsp_reason ? 0xffffaa00 : 0xff00ffcc);
""" + src[end:]
    src = replace_once(src, b"  nuwa_rows();\n", b"""  nuwa_rows();
  uint64_t fdr = __atomic_load_n(&bp_fdr_exit,__ATOMIC_RELAXED);
  unsigned prop = __atomic_load_n(&bp_dsp_properties,__ATOMIC_RELAXED);
  if (fdr)
    snprintf(b,sizeof(b),"PROP %04x FDR %us st=%u sig=%u",prop,(unsigned)(fdr>>32),
      (unsigned)((fdr>>16)&0xffffu),(unsigned)(fdr&0xffu));
  else snprintf(b,sizeof(b),"PROP %04x FDR no exit seen",prop);
  line(10,b,0xff00ffcc);
  if (&nuwa_sc_calls && &nuwa_sc_rejects && &nuwa_sc_ok)
    snprintf(b,sizeof(b),"SC n=%u r=%u o=%u",
      __atomic_load_n(&nuwa_sc_calls,__ATOMIC_RELAXED),
      __atomic_load_n(&nuwa_sc_rejects,__ATOMIC_RELAXED),
      __atomic_load_n(&nuwa_sc_ok,__ATOMIC_RELAXED));
  else snprintf(b,sizeof(b),"SC unavailable");
  line(11,b,0xff00ffcc);
""")
    src = replace_once(src, b"  __atomic_store_n(&exit_lock,0,__ATOMIC_RELEASE);\n  // Presentation cost: swaps in the last second", b"""  // exit_lock already protects both rings; XR describes only exit_ring.
  {
    char xr[80]="XR";
    for(unsigned i=0;i<exit_ring_count && i<1;++i) {
      const struct bp_exit_ring_entry *e=&exit_ring[i];
      char pc[9], part[48];
      if(e->pc_valid) snprintf(pc,sizeof(pc),"%08x",(unsigned)(e->pc&0xffffffffULL));
      else { pc[0]='-'; pc[1]=0; }
      snprintf(part,sizeof(part),"%s p%u %.9s %s sig=%u",
        i?" |":"",e->pid,e->comm,pc,e->sig&127u);
      strlcat(xr,part,sizeof(xr));
    }
    if(exit_ring_count) snprintf(rows[n++],120,"%s",xr);
  }
  __atomic_store_n(&exit_lock,0,__ATOMIC_RELEASE);
  // Presentation cost: swaps in the last second""")
    src = replace_once(src, b"  // Presentation cost: swaps in the last second", b"""  // Sample the bridge after handoff, not the earlier diagnostic page.
  {
    uint32_t pid[6];
    char value[6][12];
    for (unsigned i=0;i<6;++i) {
      pid[i]=__atomic_load_n(&bp_proc_pid[i],__ATOMIC_RELAXED);
      if(pid[i]) snprintf(value[i],sizeof(value[i]),"%u",pid[i]);
      else { value[i][0]='-'; value[i][1]=0; }
    }
    snprintf(rows[n++],120,"PROC n=%d SB=%s bb=%s lsd=%s ld=%s lk=%s cm=%s",
      nprocs,value[0],value[1],value[2],value[3],value[4],value[5]);
  }
  unsigned restart_state=__atomic_load_n(&bp_sb_restart_state,__ATOMIC_RELAXED);
  unsigned hid_stage=0;
#if NUWA_HID_STANDIN
  hid_stage=__atomic_load_n(&nuwa_hid_stage,__ATOMIC_RELAXED);
#endif
  snprintf(rows[n++],120,"SVC %02x K=%ux%u H=%u",__atomic_load_n(&bp_svc_mask,__ATOMIC_RELAXED),
    restart_state&255u,restart_state>>8,hid_stage);
  // Signed-text fixup readout: parsed/applied, only when the mechanism is linked in.
  if (&cs_text_fixup_parsed && &cs_text_fixup_applied) {
    char *row=rows[n-1];
    size_t used=strlen(row);
    snprintf(row+used,120-used," TF=%u/%u",
      __atomic_load_n(&cs_text_fixup_parsed,__ATOMIC_RELAXED),
      __atomic_load_n(&cs_text_fixup_applied,__ATOMIC_RELAXED));
  }
  if (&nuwa_sc_calls && &nuwa_sc_rejects && &nuwa_sc_ok) {
    static unsigned previous_calls, previous_time;
    unsigned calls = __atomic_load_n(&nuwa_sc_calls,__ATOMIC_RELAXED);
    unsigned rejects = __atomic_load_n(&nuwa_sc_rejects,__ATOMIC_RELAXED);
    unsigned ok = __atomic_load_n(&nuwa_sc_ok,__ATOMIC_RELAXED);
    snprintf(rows[n++],120,"SC n=%u r=%u o=%u",calls,rejects,ok);
    if (previous_time)
      snprintf(rows[n++],120,"SC +%u in %us",calls-previous_calls,now-previous_time);
    else snprintf(rows[n++],120,"SC interval unavailable");
    previous_calls=calls; previous_time=now;
  } else snprintf(rows[n++],120,"SC unavailable");
  // Presentation cost: swaps in the last second""")
    src = replace_once(src, b"  census_note(name,1);\n", b"""  if(name && !strcmp(name,"IOMFB_FDR_Loader")) {
    uint64_t fdr = ((uint64_t)seconds()<<32) | (((uint64_t)(unsigned)status&0xffffu)<<16) |
      ((unsigned)status&127u);
    __atomic_store_n(&bp_fdr_exit,fdr,__ATOMIC_RELAXED);
  }
  census_note(name,1);
""")
    src = replace_once(src, b"  if(signal || ns) {\n",
                       b'  if((signal || ns) && !(name && !strcmp(name,"IOMFB_FDR_Loader"))) {\n')
    if mg_reset:
        src = replace_once(src, anchor, b"extern uint32_t nuwa_mg_reset_diag;\n" + anchor)
        src = replace_once(src, b"  if (&nuwa_cli_enter", b"""  unsigned ds = &native_data_persist_state ? native_data_persist_state : 0;
  char mg[16] = "";
  uint32_t mr = __atomic_load_n(&nuwa_mg_reset_diag,__ATOMIC_RELAXED);
  if (mr & 0x400u)
    snprintf(mg,sizeof(mg)," MG skip");
  else if (mr & 0x100u)
    snprintf(mg,sizeof(mg)," MG r=%u/%u%s",mr&15u,(mr>>4)&15u,(mr&0x200u)?" j!":"");
  if (&nuwa_cli_enter""")
        src = replace_once(src, b'DSP s=%u r=%u CLI in=', b'DSP s=%u r=%u DS=%u%s CLI in=')
        src = replace_once(src, b'dsp_stage,dsp_reason,(unsigned)(in>>32)',
                           b'dsp_stage,dsp_reason,ds,mg,(unsigned)(in>>32)')
        src = replace_once(src, b' CLI unavailable",dsp_stage,dsp_reason);',
                           b' DS=%u%s CLI unavailable",dsp_stage,dsp_reason,ds,mg);')
    return src
