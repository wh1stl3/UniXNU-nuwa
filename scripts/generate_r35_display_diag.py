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
    anchor = b"char boot_progress_page_text[48][BP_COLS];"
    src = replace_once(src, anchor, b"""// FDR exits are independent of the best-effort exit ring.
static uint64_t bp_fdr_exit;
// Diagnostic only: two independent byte samples; no synchronization of display state.
static uint8_t bp_dsp_stage, bp_dsp_reason;
extern uint64_t nuwa_cli_enter __attribute__((weak_import));
extern uint64_t nuwa_cli_observed __attribute__((weak_import));
extern uint64_t nuwa_cli_identity __attribute__((weak_import));
void boot_progress_diag_set(uint8_t stage, uint8_t reason);
void boot_progress_diag_set(uint8_t stage, uint8_t reason) {
  __atomic_store_n(&bp_dsp_reason,reason,__ATOMIC_RELAXED);
  __atomic_store_n(&bp_dsp_stage,stage,__ATOMIC_RELAXED);
}
""" + anchor)
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
  if (fdr)
    snprintf(b,sizeof(b),"FDR %us st=%u sig=%u",(unsigned)(fdr>>32),
      (unsigned)((fdr>>16)&0xffffu),(unsigned)(fdr&0xffu));
  else snprintf(b,sizeof(b),"FDR no exit seen");
  line(10,b,0xff00ffcc);
""")
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
