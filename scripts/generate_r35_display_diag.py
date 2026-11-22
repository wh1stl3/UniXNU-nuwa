#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Patent
"""Add the display bring-up status to the pinned r35l diagnostic renderer."""

from hashlib import sha256

RENDERER_SHA = "bdfa725105977af83a9917be0209fe6701914587808d7f1b9c04a6fb4adb0c3e"


def replace_once(src, anchor, replacement):
    if src.count(anchor) != 1:
        raise ValueError(f"r35l renderer anchor changed: {anchor!r}")
    return src.replace(anchor, replacement, 1)


def generate(src, *, mg_reset=False):
    if sha256(src).hexdigest() != RENDERER_SHA:
        raise ValueError("expected the pinned r35l full renderer")
    src = replace_once(src, b'#include <string.h>\n', b"""#include <string.h>
struct proc;
extern struct proc *proc_find(int);
extern int proc_rele(struct proc *);
extern void proc_name(int, char *, int);
""")
    src = replace_once(src, b"static void touch_monitor(void *arg, wait_result_t result) {", b"""
// Only touch_monitor calls this, before acquiring render_busy.
static void bp_proc_census(void) {
  uint32_t found[6]={0};
  for (int pid=1;pid<=4096;++pid) {
    struct proc *p=proc_find(pid);
    if (!p) continue;
    char name[32];
    proc_name(pid,name,sizeof(name));
    if (!strcmp(name,"SpringBoard")) found[0]=(uint32_t)pid;
    else if (!strcmp(name,"backboardd")) found[1]=(uint32_t)pid;
    else if (!strcmp(name,"lsd")) found[2]=(uint32_t)pid;
    else if (!strcmp(name,"launchd")) found[3]=(uint32_t)pid;
    else if (!strcmp(name,"lockdownd")) found[4]=(uint32_t)pid;
    else if (!strcmp(name,"containermanager")) found[5]=(uint32_t)pid;
    proc_rele(p);
  }
  for (unsigned i=0;i<6;++i) __atomic_store_n(&bp_proc_pid[i],found[i],__ATOMIC_RELAXED);
  __atomic_fetch_add(&bp_proc_generation,1,__ATOMIC_RELEASE);
}
static void touch_monitor(void *arg, wait_result_t result) {""")
    src = replace_once(src, b"  for(;;) {\n    touch_overlay();", b"""  unsigned census_at=0, census_started=0;
  for(;;) {
    unsigned now=seconds();
    if (nprocs>0 && (!census_started || now-census_at>=10)) {
      bp_proc_census();
      census_at=now; census_started=1;
    }
    touch_overlay();""")
    anchor = b"char boot_progress_page_text[48][BP_COLS];"
    src = replace_once(src, anchor, b"""static uint32_t bp_proc_pid[6], bp_proc_generation;
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
