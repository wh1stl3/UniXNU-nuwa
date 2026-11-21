#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Patent
"""Add the display bring-up status to the pinned r35l diagnostic renderer."""

from hashlib import sha256

RENDERER_SHA = "bdfa725105977af83a9917be0209fe6701914587808d7f1b9c04a6fb4adb0c3e"


def replace_once(src, anchor, replacement):
    if src.count(anchor) != 1:
        raise ValueError(f"r35l renderer anchor changed: {anchor!r}")
    return src.replace(anchor, replacement, 1)


def generate(src):
    if sha256(src).hexdigest() != RENDERER_SHA:
        raise ValueError("expected the pinned r35l full renderer")
    anchor = b"char boot_progress_page_text[48][BP_COLS];"
    src = replace_once(src, anchor, b"""// Diagnostic only: two independent byte samples; no synchronization of display state.
static uint8_t bp_dsp_stage, bp_dsp_reason;
void boot_progress_diag_set(uint8_t stage, uint8_t reason);
void boot_progress_diag_set(uint8_t stage, uint8_t reason) {
  __atomic_store_n(&bp_dsp_reason,reason,__ATOMIC_RELAXED);
  __atomic_store_n(&bp_dsp_stage,stage,__ATOMIC_RELAXED);
}
""" + anchor)
    # Use the short DATA-summary slot; its full detail remains on row 39.
    start = src.index(b"  // Row 9: the Data mount result")
    end = src.index(b"#endif\n", start)
    return src[:start] + b"""  unsigned dsp_stage = __atomic_load_n(&bp_dsp_stage,__ATOMIC_RELAXED);
  unsigned dsp_reason = __atomic_load_n(&bp_dsp_reason,__ATOMIC_RELAXED);
  snprintf(b,sizeof(b),"DSP s=%u r=%u",dsp_stage,dsp_reason);
  line(9,b,dsp_reason ? 0xffffaa00 : 0xff00ffcc);
""" + src[end:]
