// SPDX-License-Identifier: BSD-2-Clause-Patent
// Isolated diagnostic only. Glyph/number/text primitives adapted from
// UniXNU@693f5d9 scripts/xnu-panic-screen.c and Mu-Silicium Font.h.
// No panic entry, mapping creation, worker or display-stack setup.
#include <console/video_console.h>
#include <pexpert/pexpert.h>
#include "Font.h"
extern "C" struct vc_info vinfo;
static const uint64_t nuwa_ufs_font[] = GLYPH_FONT;
static unsigned nuwa_ufs_marker_line;

// Target mmu_kvtop pattern: mask IRQ/FIQ only for this short AT/PAR window.
// Restore caller PAR before restoring exact DAIF; a later interrupt can of
// course change PAR again, but cannot contaminate the captured result GPR.
// Armv8-A PAR_EL1 PA[47:12], Attr[63:56], F[0].
__attribute__((noinline)) static uint64_t nuwa_ufs_translate(uintptr_t va)
{
  uint64_t daif, saved, par;
  __asm__ volatile("mrs %0, daif\n\tmsr daifset, #3\n\tmrs %1, par_el1\n\t"
                   "at s1e1w, %3\n\tisb\n\tmrs %2, par_el1\n\t"
                   "msr par_el1, %1\n\tmsr daif, %0"
                   : "=&r"(daif), "=&r"(saved), "=&r"(par) : "r"(va) : "memory");
  return par;
}

struct NuwaUfsPixels { uintptr_t base; unsigned rb, x, y, width; };
static void nuwa_ufs_put(NuwaUfsPixels &g, unsigned char c)
{
  // This caller only supplies bounded ASCII labels and hexadecimal digits.
  uint64_t glyph = nuwa_ufs_font[c - 32];
  unsigned top = glyph >> 32, bottom = glyph;
  for (unsigned row = 0; row < 12; ++row) {
    unsigned bits = row < 6 ? top >> (row * 5) : bottom >> ((row - 6) * 5);
    for (unsigned col = 0; col < 5; ++col)
      if ((bits >> col) & 1)
        *reinterpret_cast<volatile uint32_t *>(g.base + (g.y + row) * uint64_t(g.rb) + (g.x + col) * 4) = 0xffffffff;
  }
  g.x += 6;
}
static void nuwa_ufs_text(NuwaUfsPixels &g, const char *s)
{
  while (*s) nuwa_ufs_put(g, *s++);
}
static void nuwa_ufs_hex(NuwaUfsPixels &g, uint64_t value, unsigned digits)
{
  for (unsigned n = digits; n; --n) {
    unsigned v = (value >> ((n - 1) * 4)) & 15;
    nuwa_ufs_put(g, v < 10 ? '0' + v : 'a' + v - 10);
  }
}

// Stage: 0 INIT_ENTER, 1 INIT_RETURN, 2 START_ENTER, 3 MAP_ATTEMPT,
// 4 MAP_FAILED, 5 ATTEMPT, 6 COMPLETED, 7 HC_SNAPSHOT_DONE.
// true means stores/cache publication completed, NOT that the panel scanned it.
extern "C" __attribute__((noinline)) bool nuwa_ufs_marker(unsigned stage, unsigned sequence,
    unsigned completed, uint64_t address, uint32_t raw)
{
  static const char *const label[] = {"INIT_ENTER", "INIT_RETURN", "START_ENTER", "MAP_ATTEMPT",
                                    "MAP_FAILED", "ATTEMPT", "COMPLETED", "HC_SNAPSHOT_DONE"};
  PE_Video boot = {};
  if (PE_current_console(&boot) || stage > 7 || nuwa_ufs_marker_line >= 16) return false;
  const unsigned w = vinfo.v_width, h = vinfo.v_height, rb = vinfo.v_rowbytes;
  const uintptr_t base = vinfo.v_baseaddr;
  // BootVideoFromGop already qualified BGRX32 and backing >= rowbytes*height.
  // Require that exact console geometry and a physical boot framebuffer source.
  if (boot.v_depth != 32 || vinfo.v_depth != 32 || !base || !boot.v_baseAddr ||
      boot.v_baseAddr >= 0xffff000000000000ULL || boot.v_width != w || boot.v_height != h ||
      boot.v_rowBytes != rb || w < 640 || h / 8 < 64 + 16 * 16 || w > rb / 4 || (rb & 3) ||
      boot.v_offset || vinfo.v_rotate) return false;
  const uint64_t phys = boot.v_baseAddr & ~3ULL;
  const uint64_t bytes = uint64_t(h) * rb;
  const unsigned y = 64 + nuwa_ufs_marker_line * 16;
  uintptr_t first = base + uint64_t(y) * rb, end = first + uint64_t(16) * rb;
  if (end < first || end > base + bytes || base + bytes < base) return false;
  unsigned attr = 0x100;
  // Validate every 4K subpage intersecting the row before ANY framebuffer store.
  // PAR gives translated PA and actual memory attribute, not a guessed PA.
  for (uintptr_t va = first & ~uintptr_t(4095); va < end; va += 4096) {
    uint64_t par = nuwa_ufs_translate(va);
    if ((par & 1) || (par & 0x0000fffffffff000ULL) != phys + (va - base)) return false;
    unsigned a = par >> 56;
    if (attr != 0x100 && attr != a) return false;
    attr = a;
  }
  // Fixed append-only row. No other marker row/first-panic sentinel is touched.
  for (unsigned row = 0; row < 16; ++row)
    for (unsigned col = 0; col < w; ++col)
      *reinterpret_cast<volatile uint32_t *>(first + uint64_t(row) * rb + col * 4) = 0;
  NuwaUfsPixels g = {base, rb, 8, y, w};
  nuwa_ufs_text(g, label[stage]);
  nuwa_ufs_text(g, " i="); nuwa_ufs_hex(g, sequence, 1);
  nuwa_ufs_text(g, " completed="); nuwa_ufs_hex(g, completed, 1);
  nuwa_ufs_text(g, " address="); nuwa_ufs_hex(g, address, 8);
  nuwa_ufs_text(g, " raw/state="); nuwa_ufs_hex(g, raw, 8);
  // Device mappings need ordering; normal (including cacheable) mappings also
  // clean to PoC using this CPU's CTR_EL0.DminLine (4 << field), never a delay.
  if (attr & 0xf0) {
    uint64_t ctr;
    __asm__ volatile("mrs %0, ctr_el0" : "=r"(ctr));
    uintptr_t line = uintptr_t(4) << ((ctr >> 16) & 15);
    for (uintptr_t va = first & ~(line - 1); va < end; va += line)
      __asm__ volatile("dc cvac, %0" :: "r"(va) : "memory");
  }
  __asm__ volatile("dsb sy" ::: "memory");
  ++nuwa_ufs_marker_line;
  return true;
}
