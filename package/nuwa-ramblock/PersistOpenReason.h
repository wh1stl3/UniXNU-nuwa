// SPDX-License-Identifier: BSD-2-Clause-Patent
#pragma once

// Map the provider's existing why out-parameter, not the later overlay state.
static inline const char *nuwa_persist_open_reason(int ok, const char *why)
{
  if (ok) return "ok";
  if (!why) return "unknown";
  if (!strcmp(why, "off")) return "off";
  if (!strcmp(why, "no root layout")) return "nolayout";
  if (!strcmp(why, "already open")) return "open";
  if (!strcmp(why, "size")) return "size";
  if (!strcmp(why, "overlaps the root image")) return "overlap";
  if (!strcmp(why, "window refused")) return "window";
  return "unknown";
}
