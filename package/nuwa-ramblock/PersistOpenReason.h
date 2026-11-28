// SPDX-License-Identifier: BSD-2-Clause-Patent
#pragma once

// Map the provider's existing why out-parameter, not the later overlay state.
static inline const char *nuwa_persist_open_reason(int ok, const char *why)
{
  if (ok) {
    // Keep D1's why=ok and append a separate cleanup result to the same row.
    if (why && !strcmp(why, "legacy-reset-0")) return "ok rst=in0";
    if (why && !strcmp(why, "legacy-reset-1")) return "ok rst=in1";
    if (why && !strcmp(why, "legacy-reset-2")) return "ok rst=in2";
    if (why && !strcmp(why, "legacy-reset-3")) return "ok rst=in3";
    return "ok";
  }
  if (!why) return "unknown";
  if (!strcmp(why, "off")) return "off";
  if (!strcmp(why, "no root layout")) return "nolayout";
  if (!strcmp(why, "already open")) return "open";
  if (!strcmp(why, "size")) return "size";
  if (!strcmp(why, "overlaps the root image")) return "overlap";
  if (!strcmp(why, "window refused")) return "window";
  if (!strcmp(why, "retained persistence window refused")) return "window";
  if (!strcmp(why, "legacy-v3")) return "legacy-v3";
  if (!strcmp(why, "legacy-disposable")) return "legacy-disposable";
  if (!strcmp(why, "legacy-reset-read")) return "window rst=read";
  if (!strcmp(why, "legacy-reset-guard")) return "window rst=guard";
  if (!strcmp(why, "legacy-reset-invalid")) return "window rst=invalid";
  if (!strcmp(why, "legacy-reset-sb1")) return "window rst=sb1";
  if (!strcmp(why, "legacy-reset-pending")) return "window rst=pending";
  if (!strcmp(why, "legacy-reset-marker-write")) return "window rst=markfail";
  if (!strcmp(why, "legacy-reset-write-1")) return "window rst=fail1";
  if (!strcmp(why, "legacy-reset-write-2")) return "window rst=fail2";
  return "unknown";
}

// Bit 0/1 of the suffix identify the physical legacy anchors cleared.
static inline const char *nuwa_persist_reset_done_reason(const char *why)
{
  if (!strcmp(why, "legacy-reset-1")) return "ok rst=done1";
  if (!strcmp(why, "legacy-reset-2")) return "ok rst=done2";
  if (!strcmp(why, "legacy-reset-3")) return "ok rst=done3";
  return "ok rst=done0";
}
