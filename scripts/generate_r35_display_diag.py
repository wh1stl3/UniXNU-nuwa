#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Patent
"""Add the display bring-up status to the pinned r35l diagnostic renderer."""

from hashlib import sha256

RENDERER_SHA = "bdfa725105977af83a9917be0209fe6701914587808d7f1b9c04a6fb4adb0c3e"

BANNER_SELECTION = b"""
// Stable within each priority class; continuation rows inherit their header.
static unsigned bp_banner_priority(const char *s, unsigned previous) {
  if (s[0]==' ') return previous;
  if (!strncmp(s,"SHOT",4) || !strncmp(s,"T0 ",3) ||
      !strncmp(s,"T0+",3) || !strncmp(s,"EXIT",4) ||
      !strncmp(s,"PROC",4) || !strncmp(s,"SC ",3) ||
      !strncmp(s,"LOAD",4)) return 0;
  if (!strncmp(s,"CRASH",5) || !strncmp(s,"REASON",6) ||
      !strncmp(s,"PANIC",5) || !strncmp(s,"XR",2) ||
      !strncmp(s,"SVC",3) ||
      (s[0]=='T' && s[1]>='1' && s[1]<='3' && s[2]==' ')) return 1;
  if (!strncmp(s,"UFS",3) || !strncmp(s,"SCHED",5)) return 2;
  if (s[0]=='T' && s[1]>='1' && s[1]<='3' && s[2]=='+') return 5;
  if (!strncmp(s,"GPU",3)) return 4;
  return 3;
}
static unsigned bp_banner_select(char rows[][120], unsigned n, unsigned budget) {
  unsigned priority[64], previous=2;
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

# nuwa-sb-stack=<seconds>: one-shot lsd thread snapshot. The state and the
# buffer are declared before the banner (which renders them) and the helpers before
# touch_monitor (which arms and takes the snapshot).
SHOT_STATE = b"""
// nuwa-sb-stack=<seconds>: one-shot lsd thread snapshot. One static MiB,
// page aligned; every field is written by the monitor thread only.
#define BP_SHOT_BUF (1u << 20)
#define BP_SHOT_NO_PID 1000u     // no confirmed positive pid, or that pid no longer names lsd
#define BP_SHOT_INTEGRITY 1001u  // BEGIN, bounds, container balance or BUFFER_END failed
#define BP_SHOT_IDENTITY 1002u   // container count, pid, unique id or process name mismatch
#define BP_SHOT_NO_PAINT 1003u   // the pending row was never painted, so the stackshot was not called
#define BP_SHOT_PAINT_WAIT 60u   // seconds to wait for the pending row before giving up
#define BP_SHOT_LONG_MS 1000u    // durations above this append "to"
#define BP_SHOT_BEGIN 0x59a25807u
#define BP_SHOT_END 0xf19158edu
#define BP_SHOT_CONTAINER_BEGIN 0x13u
#define BP_SHOT_CONTAINER_END 0x14u
#define BP_SHOT_ARRAY 0x11u
#define BP_SHOT_ARRAY_PAD0 0x20u
#define BP_SHOT_LOADINFO64 0x31u
#define BP_SHOT_TASK_CONTAINER 0x903u
#define BP_SHOT_THREAD_CONTAINER 0x904u
#define BP_SHOT_TRANSITIONING_TASK 0x931u
#define BP_SHOT_TASK_SNAPSHOT 0x905u
#define BP_SHOT_THREAD_SNAPSHOT 0x906u
#define BP_SHOT_SHAREDCACHE_LOADINFO 0x908u
#define BP_SHOT_USER_STACKFRAME64 0x90du
#define BP_SHOT_KERN_STACKLR64 0x914u
#define BP_SHOT_USER_STACKLR64 0x916u
#define BP_SHOT_TH_WAIT 0x01u
#define BP_SHOT_SHARED_SYSTEM 0x40000000u // kTaskSharedRegionSystem
#define BP_SHOT_TRUNC_USER 0x8000u      // kThreadTruncUserBT
#define BP_SHOT_THREADS 4u
#define BP_SHOT_USER_PCS 12u
#define BP_SHOT_KERN_PCS 2u
struct bp_shot_thread {
  uint64_t continuation, user[BP_SHOT_USER_PCS], kern[BP_SHOT_KERN_PCS];
  unsigned users, kerns, have_user, truncated;
};
struct bp_shot_sample {
  uint64_t cache_slide, binary_base;
  unsigned total, wait, have_cache, have_binary;
  struct bp_shot_thread threads[BP_SHOT_THREADS];
};
static uint8_t bp_shot_buf[BP_SHOT_BUF] __attribute__((aligned(4096)));
static struct bp_shot_sample bp_shot_result;
static unsigned bp_shot_armed, bp_shot_seq, bp_shot_beat, bp_shot_armed_at;
static unsigned bp_shot_pid, bp_shot_rc, bp_shot_ms, bp_shot_to;
static uint64_t bp_shot_uid;
// The pending row is expected for bp_shot_pending_seq and is confirmed only by the paint
// path's own record in bp_shot_painted. Nothing infers "it should have been painted".
static unsigned bp_shot_pending_seq, bp_shot_painted;
static char bp_shot_pending_row[24];
static void bp_shot_paint_row(const char *row);
static unsigned bp_shot_format(char rows[][120], const struct bp_shot_sample *s,
                               uint64_t ks, unsigned rc, unsigned late);
"""

# Helpers, inserted before touch_monitor. The call is made from the monitor thread,
# after touch_overlay() has returned and released render_busy, and before the 30 ms
# wait: no recorder, overlay or process-list lock is held. The stackshot takes its own
# subsystem lock (try-lock only) and disables interrupts around the snapshot trap for a
# window with no upper bound, so the counter delta is measured and shown. Nothing calls
# it before the banner's paint path has stored the pending row: no pixel, no call.
# The parser reads recorded addresses, not task memory. "w=n" means every
# thread record carried SS_TH_WAIT at that instant; it does not prove a deadlock.
SHOT_PROBE = b"""
struct bp_shot_item { uint32_t type; uint32_t size; uint64_t flags; };
// osfmk/kern/kcdata.h: items are 16-byte aligned and item->size already includes the
// padding of the payload, so only the leading fields below are read.
struct bp_shot_task_snapshot {
  uint64_t unique_pid, ss_flags, user_time, system_time, p_start_sec, task_size, max_resident_size;
  uint32_t suspend_count, faults, pageins, cow_faults, was_throttled, did_throttle, latency_qos;
  int32_t pid;
  char comm[32];
} __attribute__((packed));
struct bp_shot_thread_snapshot {
  uint64_t tid, wait_event, continuation, total_syscalls, voucher, dqserialnum;
  uint64_t user_time, sys_time, ss_flags, last_run_time, last_made_runnable_time;
  uint32_t state, sched_flags;
  int16_t base_priority, sched_priority;
  uint8_t eqos, rqos, rqos_override, io_tier;
} __attribute__((packed));
static int bp_shot_name_is(const char *text, const char *want, unsigned cap) {
  for (unsigned i = 0; i < cap; ++i) {
    if (text[i] != want[i]) return 0;
    if (!text[i]) return 1;
  }
  return 0;
}
static uint64_t bp_shot_word(const unsigned char *data) {
  uint64_t word;
  memcpy(&word, data, sizeof(word));
  return word;
}

// KCData array flags carry element type in the high word and count in the low word.
// Legacy arrays infer the tail padding from count and known stride; PADn declares it.
static int bp_shot_elements(const struct bp_shot_item *item, unsigned stride, unsigned *count) {
  unsigned type = item->type;
  if (type != BP_SHOT_ARRAY && (type & ~15u) != BP_SHOT_ARRAY_PAD0) {
    if (item->size != ((stride + 15u) & ~15u)) return 0;
    *count = 1;
    return 1;
  }
  *count = (uint32_t)item->flags;
  if (!*count) return item->size == 0 && (type == BP_SHOT_ARRAY || type == BP_SHOT_ARRAY_PAD0);
  if (*count > item->size / stride) return 0;
  unsigned padding = item->size - *count * stride;
  return type == BP_SHOT_ARRAY ? padding < 16 : padding == (type & 15u);
}
// Whole-buffer check: BEGIN first, every item inside bytes_traced, containers balanced
// and matched by identifier, exactly one ordinary task container carrying our unique id,
// exactly one task snapshot agreeing on pid, unique id and name, BUFFER_END last.
static unsigned bp_shot_parse(unsigned pid, uint64_t uid, unsigned bytes, struct bp_shot_sample *out) {
  if (bytes < sizeof(struct bp_shot_item) || bytes > BP_SHOT_BUF) return BP_SHOT_INTEGRITY;
  const unsigned char *const begin = bp_shot_buf, *const end = begin + bytes;
  const unsigned char *at = begin;
  uint32_t depth = 0, container[8];
  uint64_t identity[8];
  struct bp_shot_sample sample = {0};
  struct bp_shot_thread thread = {0};
  uint64_t system_slide = 0, task_flags = 0;
  int task_depth = -1, header = 1, ended = 0;
  unsigned tasks = 0, snapshots = 0, have_system = 0, have_thread = 0, waiting = 0;
  while ((size_t)(end - at) >= sizeof(struct bp_shot_item)) {
    const struct bp_shot_item *item = (const struct bp_shot_item *)at;
    const unsigned char *data = at + sizeof(*item);
    if (header) {
      if (item->type != BP_SHOT_BEGIN || item->size != 0) return BP_SHOT_INTEGRITY;
      header = 0;
    } else if (item->type == BP_SHOT_END) {
      if (item->size != 0) return BP_SHOT_INTEGRITY;
      at = data;
      ended = 1;
      break;
    }
    if ((item->size & 15u) || (size_t)item->size > (size_t)(end - data)) return BP_SHOT_INTEGRITY;
    if (item->type == BP_SHOT_CONTAINER_BEGIN) {
      if (item->size < sizeof(uint32_t) || depth >= 8) return BP_SHOT_INTEGRITY;
      memcpy(&container[depth], data, sizeof(uint32_t));
      identity[depth] = item->flags;
      if (container[depth] == BP_SHOT_TRANSITIONING_TASK && item->flags == uid) return BP_SHOT_IDENTITY;
      if (container[depth] == BP_SHOT_TASK_CONTAINER && item->flags == uid) { ++tasks; task_depth = (int)depth; }
      if (task_depth >= 0 && (int)depth == task_depth + 1 && container[depth] == BP_SHOT_THREAD_CONTAINER) {
        memset(&thread, 0, sizeof(thread));
        have_thread = waiting = 0;
      }
      ++depth;
    } else if (item->type == BP_SHOT_CONTAINER_END) {
      if (!depth || identity[depth - 1] != item->flags) return BP_SHOT_INTEGRITY;
      --depth;
      if (task_depth >= 0 && (int)depth == task_depth + 1 &&
          container[depth] == BP_SHOT_THREAD_CONTAINER && have_thread) {
        if (waiting) {
          if (sample.wait < BP_SHOT_THREADS) sample.threads[sample.wait] = thread;
          ++sample.wait;
        }
        ++sample.total;
      }
      if (task_depth >= 0 && (uint32_t)task_depth == depth) task_depth = -1;
    } else {
      unsigned type = item->type, count;
      if (type == BP_SHOT_ARRAY || (type & ~15u) == BP_SHOT_ARRAY_PAD0) type = item->flags >> 32;
      const int in_task = task_depth >= 0 && (int)depth == task_depth + 1;
      const int in_thread = task_depth >= 0 && (int)depth == task_depth + 2 &&
        container[depth - 1] == BP_SHOT_THREAD_CONTAINER;
      if (item->type == BP_SHOT_SHAREDCACHE_LOADINFO && (!depth || in_task)) {
        if (item->size < 32) return BP_SHOT_INTEGRITY; // padded v1 has 24 bytes of data
        if (in_task) {
          sample.cache_slide = bp_shot_word(data);
          sample.have_cache = 1;
        } else {
          system_slide = bp_shot_word(data);
          have_system = 1;
        }
      } else if (in_task && type == BP_SHOT_LOADINFO64) {
        if (!bp_shot_elements(item, 24, &count)) return BP_SHOT_INTEGRITY;
        // dyld's first UUID entry is the main image (also the kernel's one-entry fallback).
        if (count && !sample.have_binary) {
          sample.have_binary = 1;
          sample.binary_base = bp_shot_word(data);
        }
      } else if (in_task && item->type == BP_SHOT_TASK_SNAPSHOT) {
        const struct bp_shot_task_snapshot *task = (const void *)data;
        if (item->size < sizeof(*task)) return BP_SHOT_INTEGRITY;
        if (++snapshots > 1 || task->unique_pid != uid || task->pid != (int32_t)pid ||
            !bp_shot_name_is(task->comm, "lsd", sizeof(task->comm))) return BP_SHOT_IDENTITY;
        task_flags = task->ss_flags;
      } else if (in_thread && item->type == BP_SHOT_THREAD_SNAPSHOT) {
        const struct bp_shot_thread_snapshot *snap = (const void *)data;
        // thread_snapshot_v2 (padded) and v3 are 112 bytes, v4 is 128; state is at +88.
        if (have_thread || (item->size != 112 && item->size != 128)) return BP_SHOT_INTEGRITY;
        have_thread = 1;
        thread.continuation = snap->continuation; // already VM_KERNEL_UNSLIDE'd by the producer
        thread.truncated = (snap->ss_flags & BP_SHOT_TRUNC_USER) != 0;
        waiting = (snap->state & BP_SHOT_TH_WAIT) != 0;
      } else if (in_thread && (type == BP_SHOT_USER_STACKFRAME64 || type == BP_SHOT_USER_STACKLR64 ||
                               type == BP_SHOT_KERN_STACKLR64)) {
        unsigned stride = type == BP_SHOT_USER_STACKFRAME64 ? 16 : 8;
        if (!bp_shot_elements(item, stride, &count)) return BP_SHOT_INTEGRITY;
        if (type != BP_SHOT_KERN_STACKLR64) thread.have_user = 1;
        unsigned *used = type == BP_SHOT_KERN_STACKLR64 ? &thread.kerns : &thread.users;
        unsigned limit = type == BP_SHOT_KERN_STACKLR64 ? BP_SHOT_KERN_PCS : BP_SHOT_USER_PCS;
        uint64_t *pc = type == BP_SHOT_KERN_STACKLR64 ? thread.kern : thread.user;
        for (unsigned i = 0; i < count && *used + i < limit; ++i)
          pc[*used + i] = bp_shot_word(data + i * stride);
        *used += count;
      }
    }
    at = data + item->size;
  }
  if (!ended || header || depth || at != end) return BP_SHOT_INTEGRITY;
  if (tasks != 1 || snapshots != 1) return BP_SHOT_IDENTITY;
  if (!sample.have_cache && have_system && (task_flags & BP_SHOT_SHARED_SYSTEM)) {
    sample.have_cache = 1;
    sample.cache_slide = system_slide;
  }
  *out = sample;
  return 0;
}
static void bp_shot_hex(char out[17], int present, uint64_t value, unsigned digits) {
  if (!present) { out[0] = '-'; out[1] = 0; return; }
  const char hex[] = "0123456789abcdef";
  out[digits] = 0;
  while (digits) { out[--digits] = hex[value & 15u]; value >>= 4; }
}
static void bp_shot_base(char out[17], const struct bp_shot_sample *s, unsigned digits) {
  if (s->have_binary && !s->binary_base) { memcpy(out, "0!", 3); return; }
  bp_shot_hex(out, s->have_binary, s->binary_base, digits);
}
static unsigned bp_shot_format(char rows[][120], const struct bp_shot_sample *s,
                               uint64_t ks, unsigned rc, unsigned late) {
  char k[17], sc[17], sb[17];
  if (rc) {
    snprintf(rows[0], 120, "SHOT lsd n=- w=- r=%u ks=- sc=- sb=-%s", rc, late ? " to" : "");
    return 1;
  }
  bp_shot_hex(k, 1, ks, 8);
  bp_shot_hex(sc, s->have_cache, s->cache_slide, 8);
  bp_shot_base(sb, s, 8);
  snprintf(rows[0], 120, "SHOT lsd n=%u w=%u r=0 ks=%s sc=%s sb=%s%s",
    s->total, s->wait, k, sc, sb, late ? " to" : "");
  for (unsigned i = 0; i < BP_SHOT_THREADS; ++i) {
    char *row = rows[1 + i];
    if (i >= s->wait) { snprintf(row, 120, "T%u -", i); continue; }
    const struct bp_shot_thread *t = &s->threads[i];
    char top[24], pcs[40] = "-";
    if (t->continuation) {
      bp_shot_hex(k, 1, t->continuation, 16);
      snprintf(top, sizeof(top), "C=%s", k);
    } else {
      bp_shot_hex(k, t->kerns > 0, t->kern[0], 10);
      bp_shot_hex(sc, t->kerns > 1, t->kern[1], 10);
      snprintf(top, sizeof(top), "K=%.10s,%.10s", k, sc);
    }
    // iOS arm64 user VA fits in 36 bits. K uses the low 40 of a canonical kernel VA.
    for (unsigned j = 0; j < t->users && j < 4; ++j) {
      bp_shot_hex(k, 1, t->user[j], 9);
      memcpy(pcs + 10 * j, k, 10);
      if (j) pcs[10 * j - 1] = ',';
    }
    char frames[12] = "-";
    if (t->have_user) snprintf(frames, sizeof(frames), "%u", t->users);
    snprintf(row, 120, "T%u %s U=%s f=%s%s", i, top, pcs, frames,
      t->users > 4 || t->truncated ? "!" : "");
  }
  unsigned n = 5;
  if ((ks >> 32) || (s->binary_base >> 32) || (s->have_cache && (s->cache_slide >> 32))) {
    bp_shot_hex(k, 1, ks, 16);
    bp_shot_base(sb, s, 16);
    bp_shot_hex(sc, 1, s->cache_slide, 16);
    snprintf(rows[5], 120, "SHOT2 ks=%s sb=%s%s%s", k, sb,
      s->have_cache && (s->cache_slide >> 32) ? " sc=" : "",
      s->have_cache && (s->cache_slide >> 32) ? sc : "");
    n = 6;
  }
  for (unsigned i = 0; i < BP_SHOT_THREADS && i < s->wait; ++i) {
    const struct bp_shot_thread *t = &s->threads[i];
    for (unsigned start = 4; start < t->users && start < BP_SHOT_USER_PCS; start += 4) {
      char pcs[40] = "";
      for (unsigned j = start; j < t->users && j < start + 4 && j < BP_SHOT_USER_PCS; ++j) {
        bp_shot_hex(k, 1, t->user[j], 9);
        memcpy(pcs + 10 * (j - start), k, 10);
        if (j > start) pcs[10 * (j - start) - 1] = ',';
      }
      snprintf(rows[n++], 120, "T%u+%u U=%s", i, start, pcs);
    }
  }
  return n;
}
extern uint64_t proc_uniqueid(struct proc *);
static unsigned bp_shot_resolve(unsigned pid, uint64_t *uid) {
  char name[32];
  if (!pid || pid > 0x7fffffffu) return 0;
  struct proc *p = proc_find((int)pid);
  if (!p) return 0;
  *uid = proc_uniqueid(p);
  proc_name((int)pid, name, sizeof(name));
  proc_rele(p);
  return bp_shot_name_is(name, "lsd", sizeof(name));
}
// Runs before touch_overlay() so this pass is eligible to repaint. Whether the pending
// row really reaches the panel is not decided here: only bp_shot_paint_row() records it.
static void bp_shot_arm(unsigned now) {
  uint64_t uid = 0;
  unsigned pid = __atomic_load_n(&bp_proc_pid[2], __ATOMIC_RELAXED);
  ++bp_shot_seq;
  bp_shot_armed = 0;
  bp_shot_pending_seq = 0;
  __atomic_store_n(&bp_shot_painted, 0, __ATOMIC_RELAXED);
  bp_shot_ms = bp_shot_to = 0;
  if (!pid || !bp_shot_resolve(pid, &uid)) {
    bp_shot_rc = BP_SHOT_NO_PID;
    __atomic_store_n(&bp_shot_beat, (bp_shot_seq << 8) | 3u, __ATOMIC_RELEASE);
    printf("nuwa-sb-stack: seq=%u pid=%u rc=%u not attempted\\n", bp_shot_seq, pid, bp_shot_rc);
    return;
  }
  bp_shot_pid = pid;
  bp_shot_uid = uid;
  bp_shot_rc = 0;
  snprintf(bp_shot_pending_row, sizeof(bp_shot_pending_row), "SHOT pending %u", bp_shot_seq);
  bp_shot_pending_seq = bp_shot_seq;
  bp_shot_armed = 1;
  bp_shot_armed_at = now;
  __atomic_store_n(&bp_shot_beat, (bp_shot_seq << 8) | 1u, __ATOMIC_RELEASE);
}
// Called by the banner's row loop for every row it is about to store: after the yield
// check, and only for rows that survived the height and budget selection. This is the
// only record of "the pending row was painted"; nothing infers it from the flags.
static void bp_shot_paint_row(const char *row) {
  if (bp_shot_pending_seq && !strcmp(row, bp_shot_pending_row))
    __atomic_store_n(&bp_shot_painted, bp_shot_pending_seq, __ATOMIC_RELEASE);
}
// The gate itself: without the paint path's record for this sequence there is no call.
static int bp_shot_may_call(void) {
  return bp_shot_pending_seq && bp_shot_seq == bp_shot_pending_seq &&
         __atomic_load_n(&bp_shot_painted, __ATOMIC_ACQUIRE) == bp_shot_seq;
}
static uint64_t bp_shot_ticks(void) {
  uint64_t ticks;
  __asm__ volatile("isb\\n\\tmrs %0, cntpct_el0" : "=r"(ticks));
  return ticks;
}
static uint64_t bp_shot_frequency(void) {
  uint64_t frequency;
  __asm__ volatile("mrs %0, cntfrq_el0" : "=r"(frequency));
  return frequency ? frequency : 19200000;
}
static void bp_shot_take(unsigned now) {
  uint64_t start;
  unsigned bytes = 0, rc;
  if (!bp_shot_armed) return;
  if (!bp_shot_may_call()) {
    // Painting only. The pending row has not been stored yet, so the stackshot is not
    // called; a later pass may paint it. Give up after BP_SHOT_PAINT_WAIT seconds.
    if (now - bp_shot_armed_at < BP_SHOT_PAINT_WAIT) return;
    bp_shot_armed = 0;
    bp_shot_pending_seq = 0;
    bp_shot_rc = BP_SHOT_NO_PAINT;
    __atomic_store_n(&bp_shot_beat, (bp_shot_seq << 8) | 3u, __ATOMIC_RELEASE);
    printf("nuwa-sb-stack: seq=%u pid=%u rc=%u not attempted: pending row never painted\\n",
      bp_shot_seq, bp_shot_pid, bp_shot_rc);
    return;
  }
  bp_shot_armed = 0;
  bp_shot_pending_seq = 0;
  start = bp_shot_ticks();
  rc = (unsigned)stack_snapshot_from_kernel((int)bp_shot_pid, bp_shot_buf, (uint32_t)sizeof(bp_shot_buf),
    (uint64_t)STACKSHOT_KCDATA_FORMAT | STACKSHOT_TRYLOCK | STACKSHOT_SAVE_LOADINFO, 0, 0, &bytes);
  bp_shot_ms = (unsigned)((bp_shot_ticks() - start) * 1000 / bp_shot_frequency());
  if (bp_shot_ms > BP_SHOT_LONG_MS) bp_shot_to = 1;
  if (rc == KERN_SUCCESS) rc = bp_shot_parse(bp_shot_pid, bp_shot_uid, bytes, &bp_shot_result);
  bp_shot_rc = rc;
  __atomic_store_n(&bp_shot_beat, (bp_shot_seq << 8) | (rc ? 3u : 2u), __ATOMIC_RELEASE);
  printf("nuwa-sb-stack: seq=%u pid=%u uid=%llx rc=%u n=%u w=%u ms=%u%s\\n", bp_shot_seq, bp_shot_pid,
    (unsigned long long)bp_shot_uid, rc, rc ? 0 : bp_shot_result.total,
    rc ? 0 : bp_shot_result.wait, bp_shot_ms, bp_shot_to ? " to" : "");
}
"""

# Put the temporary stackshot priority-0 block first, ahead of other priority-0 rows.
SHOT_ROWS = b"""
  {
    unsigned beat = __atomic_load_n(&bp_shot_beat, __ATOMIC_ACQUIRE);
    unsigned shot_seq = beat >> 8, shot_state = beat & 255u;
    if (shot_seq && shot_state == 1) {
      snprintf(rows[n++],120,"SHOT pending %u",shot_seq);
    } else if (shot_seq) {
      unsigned shot_rc = __atomic_load_n(&bp_shot_rc, __ATOMIC_RELAXED);
      n += bp_shot_format(rows + n, &bp_shot_result, vm_kernel_slide, shot_rc, bp_shot_to);
    }
  }
"""


def replace_once(src, anchor, replacement):
    if src.count(anchor) != 1:
        raise ValueError(f"r35l renderer anchor changed: {anchor!r}")
    return src.replace(anchor, replacement, 1)


SMP_OBSERVE_FORMAT = b"""
// The gate admits only logical CPU 1 (ADT reg 0x100).
extern volatile uint32_t armcpu_smp_on_state[8],armcpu_smp_on_attempts[8],armcpu_smp_seen_aff_valid[8];
extern volatile uint64_t armcpu_smp_on_target[8],armcpu_smp_seen_aff[8];

static void bp_smp_entry_values(char rc[12], char aff[11]) {
  unsigned state=__atomic_load_n(&armcpu_smp_on_state[1],__ATOMIC_ACQUIRE);
  if(state==2)
    snprintf(rc,12,"%d",__atomic_load_n(&armcpu_smp_psci_rc[1],__ATOMIC_RELAXED));
  else snprintf(rc,12,"%s",state==1?"nc":"-");
  if(__atomic_load_n(&armcpu_smp_seen_aff_valid[1],__ATOMIC_ACQUIRE))
    snprintf(aff,11,"%llx",(unsigned long long)__atomic_load_n(&armcpu_smp_seen_aff[1],__ATOMIC_RELAXED));
  else snprintf(aff,11,"-");
}

static void bp_smp_entry_page(char *out, size_t len) {
  unsigned attempts=__atomic_load_n(&armcpu_smp_on_attempts[1],__ATOMIC_ACQUIRE);
  char to[11]="-",rc[12],aff[11],fail[16]="";
  if(attempts)
    snprintf(to,sizeof(to),"%llx",(unsigned long long)__atomic_load_n(&armcpu_smp_on_target[1],__ATOMIC_RELAXED));
  unsigned f=armcpu_smp_fail[1];
  if(f)snprintf(fail,sizeof(fail),"!fail%u",f);
  bp_smp_entry_values(rc,aff);
  snprintf(out,len,"SMP %u/%x/%u c1=step%u%s n=%x t=%s rc=%s aff=%s",
    armcpu_smp_requested,armcpu_smp_running,armcpu_smp_conduit,armcpu_smp_step[1],fail,attempts,to,rc,aff);
}

static void bp_smp_entry_title(char *out, size_t len, const char *tag, unsigned now,
                               unsigned crashes, unsigned failed) {
  char rc[12],aff[11];
  bp_smp_entry_values(rc,aff);
  // Use the title slot so diagnostics and stacks keep exactly their original budget.
  snprintf(out,len," LIVE rc=%s aff=%s %.8s %us C%u E%u",rc,aff,tag,now,crashes,failed);
}
"""


def add_smp_observe(src):
    anchor = b"extern volatile int32_t __attribute__((weak_import)) armcpu_smp_psci_rc[8];\n"
    src = replace_once(src, anchor, anchor + SMP_OBSERVE_FORMAT)
    return replace_once(replace_once(src, b"""      unsigned n=(unsigned)snprintf(b,sizeof(b),"SMP req=%u run=%u cond=%u boot=%x |",
        armcpu_smp_requested,armcpu_smp_running,armcpu_smp_conduit,armcpu_boot_mpidr&0xffffff);
      for(unsigned c=1;c<8&&n<sizeof(b)-14;++c)if(armcpu_smp_step[c]||armcpu_smp_psci_rc[c])
      {
        n+=(unsigned)snprintf(b+n,sizeof(b)-n," c%u=step%u",c,armcpu_smp_step[c]);
        if(armcpu_smp_fail[c]&&n<sizeof(b)-14)n+=(unsigned)snprintf(b+n,sizeof(b)-n,"!fail%u",armcpu_smp_fail[c]);
      }
""", b"      bp_smp_entry_page(b,sizeof(b));\n"), b"""  snprintf(head,sizeof head," UniXNU live diagnostics%s%s%s  t=%us  crashes=%u exits=%u",build_tag[0]?"  [":"",build_tag,
    build_tag[0]?"]":"",now,crashes,failed);""",
        b"  bp_smp_entry_title(head,sizeof head,build_tag,now,crashes,failed);")


def generate(src, *, mg_reset=False, smp_observe=False):
    if sha256(src).hexdigest() != RENDERER_SHA:
        raise ValueError("expected the pinned r35l full renderer")
    # stack_snapshot_from_kernel and the STACKSHOT_* flags live in <kern/debug.h>
    # (XNU_KERNEL_PRIVATE), the same declaration kern_stackshot.c implements.
    src = replace_once(src, b"#include <kern/boot_progress.h>\n",
                       b"#include <kern/boot_progress.h>\n#include <kern/debug.h>\n")
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
    src = replace_once(src, b"static void touch_monitor(void *arg, wait_result_t result) {",
                       SHOT_PROBE + b"static void touch_monitor(void *arg, wait_result_t result) {")
    src = replace_once(src, b"  for(;;) {\n    touch_overlay();", b"""  unsigned census_at=0, census_started=0, restart_at=0, restart_every=0;
  unsigned restart_count=0, restart_last=0;
  unsigned shot_at=0, shot_used=0;
  PE_parse_boot_argn("nuwa-sb-restart",&restart_at,sizeof(restart_at));
  PE_parse_boot_argn("nuwa-sb-restart-every",&restart_every,sizeof(restart_every));
  // One shot only: absent or zero disables it, values below 60 are raised to 60 and a
  // failed attempt is never retried.
  PE_parse_boot_argn("nuwa-sb-stack",&shot_at,sizeof(shot_at));
  if (restart_at && restart_at<60) restart_at=60;
  if (restart_every && restart_every<120) restart_every=120;
  if (shot_at && shot_at<60) shot_at=60;
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
    if (shot_at && !shot_used && now>=shot_at) { shot_used=1; bp_shot_arm(now); }
    touch_overlay();
    bp_shot_take(now);""")
    anchor = b"char boot_progress_page_text[48][BP_COLS];"
    src = replace_once(src, anchor, SHOT_STATE + b"""static uint32_t bp_proc_pid[6], bp_proc_generation, bp_svc_mask, bp_sb_restart_state;
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
    src = replace_once(src, b"+gpu_sig*17ULL;", b"+gpu_sig*17ULL+__atomic_load_n(&bp_proc_generation,__ATOMIC_ACQUIRE)*65537ULL+__atomic_load_n(&bp_shot_beat,__ATOMIC_ACQUIRE)*131071ULL;")
    # The pending row is confirmed only after it has been stored by this loop: the record
    # sits past the yield check and past the height/budget selection, so a skipped pass,
    # a throttle, an unchanged signature or a clipped row cannot confirm anything.
    src = replace_once(src, b"""    if(__atomic_load_n(&display.yield_requested,__ATOMIC_ACQUIRE))return;
    const char *r=rows[i];""", b"""    if(__atomic_load_n(&display.yield_requested,__ATOMIC_ACQUIRE))return;
    const char *r=rows[i];
    bp_shot_paint_row(r);""")
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
    src = replace_once(src, b"  char rows[48][120];unsigned n=0;\n",
                       b"  char rows[64][120];unsigned n=0;\n" + SHOT_ROWS)
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
    return add_smp_observe(src) if smp_observe else src
