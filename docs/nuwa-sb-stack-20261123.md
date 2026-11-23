# One-shot SpringBoard thread snapshot (nuwa-sb-stack)

Revision 2, after deep review: the stackshot call is now gated on the banner's own
record that the `SHOT pending <k>` row was stored. Revision 1 could call after a pass
that never painted the row; that path no longer exists. Host candidate only — the
build, the CHMH rebind and the outer readback are self-checked on this host, nothing
was written to a device, and the call has never run. Reviewer re-review of the kcdata
walk, the identity rule, the boot-arg clamp and the rows is pending; `deep_reviewer`
should re-check only the paint gate below and the corrected evidence wording.
Authentication **NOT REACHED**.

Branch `display/20h392-dsp-diag`, base `3cd1476`. UniXNU upstream main before and
after the build: `693f5d9cae8a408dd18b39f3f9fdc4228c934241` (read-only pin, unchanged).

## What runs

`nuwa-sb-stack=<seconds>` arms a single call to `stack_snapshot_from_kernel`
(`osfmk/kern/debug.h:653-668`, implemented at `osfmk/kern/kern_stackshot.c:348`) from
the existing 30 ms `touch_monitor` thread, then publishes two banner rows:

```text
SHOT pending 1
SHOT n=12 w=12 r=0
```

Only three numbers are produced: total `THREAD_SNAPSHOT` records in the matched task
container, how many carry `SS_TH_WAIT`, and the result code.

### Call context and limits

- The call is made in `touch_monitor`, immediately **after** `touch_overlay()` has
  returned (which released `render_busy`) and **before** `assert_wait_timeout`. No
  render/overlay/recorder lock, process-list lock, task lock or thread lock is held
  across it. `proc_find`/`proc_name`/`proc_uniqueid` run before the call, each with the
  reference released.
- `stack_snapshot_from_kernel` takes the stackshot subsystem lock with
  `STACKSHOT_TRYLOCK` and disables interrupts around the snapshot trap
  (`ml_set_interrupts_enabled(FALSE)` → `stackshot_trap()` → restore). **That
  interrupt-off window has no upper bound**: on this board only the boot CPU runs, so
  a trap that never returns freezes the whole system, not just this thread. The
  measured CNTPCT delta is the only bound the package can report.
- The buffer is one static, 4096-byte aligned 1 MiB array in kernel BSS. The call is
  capped by the kernel's own `max_tracebuf_size` (at least `SANE_TRACEBUF_SIZE`, 8 MiB),
  so 1 MiB is passed through unchanged. Capacity shortfall surfaces as
  `KERN_INSUFFICIENT_BUFFER_SIZE` (52); the length is never used to infer it, and the
  buffer is never grown nor the call retried.
- **This parser** walks record headers only: item type/size/flags, the one task
  snapshot's pid/unique id/name, and `ths_state` from each thread record. It does not
  decode stack frames and reads no user memory. The **producer** (`kern_stackshot.c`)
  is outside this change: stackshot may fault in user pages while collecting stack and
  load records, and nothing here restricts or measures that. "No user memory is read"
  must not be extended from the parser to the producer.
- `w=n` means every thread record in that task carried `SS_TH_WAIT` at that instant.
  It is a single sample of one task; **it does not prove a deadlock**, and it says
  nothing about what the threads wait on or whether they run.

## The paint gate (deep review item)

The call is not made because a pass "should have" painted the heartbeat; it is made
only after the paint path reports that it stored that row.

- `bp_shot_paint_row(row)` is called by the banner's row loop for every row it is
  about to store: **after** the `display.yield_requested` check, and only for rows that
  already survived `bp_banner_select()` (budget) and the height check. It records
  `bp_shot_painted = bp_shot_pending_seq` only when the row text equals the exact
  pending row for the armed sequence (`"SHOT pending <k>"`, built by `bp_shot_arm`).
  Every other row, and every stale or truncated variant, records nothing.
- `bp_shot_may_call()` requires `bp_shot_pending_seq == bp_shot_seq` **and**
  `bp_shot_painted == bp_shot_seq`. `bp_shot_take()` returns without calling when it is
  false: no pixel, no call.
- The four ways a pass can miss the row all return before the hook, so none of them can
  confirm anything: `render_busy` held (`touch_overlay` returns before `crash_banner`),
  the existing `now-banner_second<2` gate, an unchanged signature, and a
  `yield_requested` seen before that row. A row clipped by the budget is never iterated.
- Arming also changes the banner signature (the `bp_shot_beat` term), so the arming pass
  is eligible to repaint; the two-second gate is **not** bypassed — if it blocks, the
  next pass paints.
- Without a confirmed paint the attempt keeps waiting (painting only) and, after
  `BP_SHOT_PAINT_WAIT` = 60 s, publishes `r=1003` and never calls, so a pass that can
  never paint does not leave a silent forever-pending state.
- `done`/`fail` change the beat again and therefore the signature: the terminal rows get
  their own eligible repaint, again subject to the two-second gate.
- The sequence is never re-used: `bp_shot_take()` clears both the arm flag and
  `bp_shot_pending_seq` before the call, so a second call for the same `<k>` cannot
  happen, whatever the return code.

### Evidence levels

The gate records a **pixel store**: `px_text` wrote the row into the framebuffer this
pass. That is not the same evidence as the panel scanning that frame out — an
already-queued scanout, a later hand-off, or a compositor frame can still replace it.
A painted pending row therefore proves the gate opened; it does not prove a human or
the panel ever saw it. Equally, a row that is missing from a capture may have been
painted and then overwritten.

## Reading a frozen `SHOT pending <k>`

Because the pending row is painted before the call, a panel that still shows
`SHOT pending <k>` with no matching `SHOT done/fail <k>` means the gate opened and the
probe thread did not reach the publish point. That covers the call itself, the parse,
and any other stop on the same core: **it does not prove the thread is inside the
snapshot trap.** With only the boot CPU running, the same stop freezes every other
banner row, so the heartbeat locates the stop; it does not isolate the fault.

If the panel never showed `SHOT pending <k>` at all, the gate did not open, the probe
never called, and `r` stays pending until `1003`. That is a probe-side outcome, not a
SpringBoard observation.

## Result codes

| r | Meaning | Sample expected? |
| --- | --- | --- |
| 0 | Success: `n`/`w` are the counts. | yes |
| 40 | `KERN_LOCK_OWNED`: the stackshot subsystem lock was held; the attempt ended. | no |
| 52 | `KERN_INSUFFICIENT_BUFFER_SIZE`: the 1 MiB buffer was too small; not retried. | no |
| other `KERN_*` | Passed through from the kernel unchanged. | no |
| 1000 | No confirmed positive SpringBoard pid, or that pid no longer resolves to a live `SpringBoard`. Not attempted. | no |
| 1001 | Buffer integrity failed: BEGIN header, item bounds, container balance, or `BUFFER_END`. Nothing published. | no |
| 1002 | Identity failed: task-container count, pid, unique id, or process name. Nothing published. | no |
| 1003 | The pending row was never painted within 60 s, so the stackshot was never called. | no |

Any non-zero `r` with `-`/`-` means the counts were rejected as a whole; partial
counts are never published.

**Probe violations** — these indicate a bug in this patch, and no SpringBoard
conclusion may be drawn from the run: the same `<k>` calling the stackshot twice, a
non-zero `r` shown together with counts, `w > n`, or any call that happened without a
paint record (only demonstrable offline, by instrumenting the gate).

## Eleven requirements to implementation

| # | Requirement | Implementation |
| --- | --- | --- |
| 1 | `nuwa-sb-stack=<s>` trigger; absent/0 off, <60 raised to 60, one shot, no retry | `PE_parse_boot_argn("nuwa-sb-stack",...)` + `if (shot_at && shot_at<60) shot_at=60;` in `touch_monitor`; `if (shot_at && !shot_used && now>=shot_at) { shot_used=1; bp_shot_arm(now); }` — `shot_used` is never cleared |
| 2 | After `touch_overlay()` returns, before `assert_wait_timeout()`, no busy/lock held | `bp_shot_take(now)` runs on the line after `touch_overlay();` and before the wait; `touch_overlay` releases `render_busy` before returning; no other lock is taken in between |
| 3 | `STACKSHOT_KCDATA_FORMAT\|STACKSHOT_TRYLOCK`, delta 0, pagetable mask 0, no `THREAD_WAITINFO`, `KERN_LOCK_OWNED` ends it | Single call: `(uint64_t)STACKSHOT_KCDATA_FORMAT \| (uint64_t)STACKSHOT_TRYLOCK, 0, 0`; any non-zero return (40 included) is published as-is with no retry |
| 4 | Static 1 MiB aligned buffer, length 0 before the call, `KERN_INSUFFICIENT_BUFFER_SIZE` for capacity, no growth/retry | `static uint8_t bp_shot_buf[1u<<20] __attribute__((aligned(4096)))`; `unsigned bytes = 0;` immediately before the call; rc 52 passes through untranslated |
| 5 | Parse only `KERN_SUCCESS && 0 < bytes <= sizeof`, check BEGIN/bounds/container balance/`BUFFER_END`, publish nothing on failure | `bp_shot_parse`: header item must be `0x59a25807` with size 0; `item->size > end-data` fails; container END must match the innermost BEGIN identifier and depth must return to 0; `BUFFER_END` (`0xf19158ed`) must close the buffer exactly at `bytes`; `*totalp`/`*waitp` are written only after every check |
| 6 | Confirmed positive pid only; keep pid and unique id; accept one matching ordinary task; verify pid + unique id + `SpringBoard`; reuse/transitioning fails | pid = census `bp_proc_pid[0]`; `bp_shot_resolve` = `proc_find` + `proc_name=="SpringBoard"` + `proc_uniqueid`; parse requires exactly one `STACKSHOT_KCCONTAINER_TASK` (0x903) carrying that id, rejects 0x931 transitioning with that id, and requires the one task snapshot to agree on `ts_unique_pid`, `ts_pid` and `ts_p_comm` |
| 7 | `(ths_state & SS_TH_WAIT)` bit test, only matched task's `THREAD_SNAPSHOT` | `if (thread->state & BP_SHOT_TH_WAIT)` inside the matched container, only for type 0x906 |
| 8 | One row `SHOT n=<n> w=<w> r=<code>`, `-`/`-` when r≠0, ≤80 columns with measured width | `SHOT n=%u w=%u r=0%s` / `SHOT n=- w=- r=%u%s`; measured 16/13/22/37 columns (worst case 37) |
| 9 | Sequenced heartbeat before and after, to separate "this thread did not return" from "whole core paused" | `bp_shot_beat = seq<<8 \| state` release-stored `pending` before `touch_overlay()` and `done`/`fail` after; the beat is also a signature term, so both transitions are eligible to repaint |
| 9a | (deep review) the call happens only after the paint path stored the pending row | `bp_shot_paint_row(row)` records the sequence past the yield check and past selection; `bp_shot_may_call()` gates `bp_shot_take()`; no record, no call, `1003` after 60 s |
| 10 | CNTPCT delta / `cntfrq` (19.2 MHz) in ms, mark over-threshold with `to` | `bp_shot_ticks()` before/after, `bp_shot_frequency()` with 19200000 fallback, `ms = delta*1000/freq`, `to` above 1000 ms |
| 11 | Document context, interrupt-off window, buffer cap, count-only behaviour, `w=n` meaning | This section, including the parser-versus-producer limit and the evidence levels |

## Layout effect the reviewer must accept

The 1 MiB zero-fill buffer grows `__DATA` vmsize from `0x34c000` to `0x44c000`, so every
segment above it moves up by exactly `0x100000`. `__PRELINK_INFO` now starts at
`0xfffffff008170000` and is `0x71000` long; the **highest segment end is
`0xfffffff0081e1000` (exclusive)**, not the start of `__PRELINK_INFO`. The packaged
`layout.json` already records the correct span, `kernel_vm_span = 71405568` =
`0x4419000` (`0xfffffff0081e1000 - 0xfffffff003dc8000`), against
`window_bytes = 5100273664` and `remaining_window_bytes = 5026627584`, so the window
capacity risk is low and the buffer does not need to shrink. Segment file offsets and
the 52,187,136-byte file are unchanged, so the loader walks the same `LC_SEGMENT_64`
records and maps one more MiB of zero-fill where the header now says. Nothing in this
repository pins the old addresses; the linked guard tests recompute them and pass.

## Host build and package — self-checked

Built as the compact r35l display recipe with `--mg-reset --hid-standin`:

```sh
PY=/home/wh1stl3/.local/bin/python3.11
BASE=/mnt/d/Code/PortingiOS/UniXNU
CPO=/root/nuwa-pmap-ret-native-20261111/nuwa/ios-16.7.16-20H392/nuwa_pmap_ret/tree/build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/iokit/DEVELOPMENT/IOPMGR.cpo.json
"$PY" -B scripts/build-nuwa-display-native.py --base "$BASE" --cpo "$CPO" \
  --linker-dir /opt/unixnu-linux/CommandLineTools/usr/bin \
  --r35-dir out/nuwa-r35-20261119 --r35l-dir out/nuwa-r35l-regs-full-20261121 \
  --cpu-only --no-software-vsync --candidate --mg-reset --hid-standin \
  --out out/nuwa-sb-stack2-20261123-build
```

WSL Ubuntu-22.04 as root (the compile tree and `/root/...` inputs are root-owned);
`out/nuwa-sb-stack2-20261123-build.log`. `BootProgress.o` carries exactly one
`ARM64_RELOC_BRANCH26 _stack_snapshot_from_kernel` and undefined `_proc_find`,
`_proc_name`, `_proc_uniqueid`; the linked kernel defines
`_stack_snapshot_from_kernel` at `0xfffffff00723ea98`. Linked guards
`test-r35g-ux-linked.py`, `test-r35k-regs-linked.py`, `test-r35e-irqguard-linked.py`
exit 0 on the compact kernel.

Host tests, all on the generated source:

- `scripts/test-sb-stack-paint.py` slices `bp_shot_arm`, `bp_shot_paint_row`,
  `bp_shot_may_call`, `bp_shot_take` and `bp_shot_parse` verbatim and stubs only the
  counter, the proc lookups and `stack_snapshot_from_kernel`. The four passes that
  cannot paint (render busy, two-second throttle, row clipped by the budget, yield
  before the row) are each asserted to make **0** calls and to end in `1003` after the
  wait bound; a painted pending row makes **exactly 1** call with the expected flags and
  `n=1 w=1`; a `KERN_LOCK_OWNED` return makes exactly 1 call, publishes `r=40` with no
  counts and never retries; an unresolvable process makes 0 calls. It also asserts the
  structural placement of the hook: one call site, after the hold/throttle/signature
  returns, after `bp_banner_select`, and immediately after the `yield_requested` check.
- `scripts/test-sb-stack-row.py` exercises the kcdata walker: a synthetic buffer
  (`n=2 w=1`), 112-byte thread records, and nine negative cases (missing `BUFFER_END`,
  mismatched container END, 120-byte thread record, duplicate task container,
  transitioning container, pid off by one, wrong name, wrong unique id, truncated
  buffer) returning 1001/1002 with the counts untouched; plus the measured row widths
  and the `SHOT` priority class.
- `test-banner-budget.py` and `test-banner-short-values.py` still pass.

Packaging used `out/nuwa-systemgroup-seed-20261122/repack-sb-stack2.py` (base
`vendor-boot-sb-stack`, baseline outer
`f3b15b3f85bc144eb68a8d1c25d3dbe229971bb438c5dbff3627c4b06039b05f`, `HID_KERNEL`
rebound to the new kernel). The outer readback `unixnu.toml` is byte-identical to the
previous candidate and the xnu args are unchanged (553 bytes, SHA-256
`6005cc3715b29547950f05e189ac4d843f08b144d25c2953ffc0524fa96bf663`):

```text
... nuwa-mg-reset=1 nuwa-sb-restart=400 nuwa-sb-restart-every=180 nuwa-hid-standin=1 nuwa-sb-stack=360
```

`fsck.fat -vn` reports 9 files and 106,239 of 129,022 clusters used; `mdir` reports
**11,664,896 B free**, above 8 MiB. Outer-readback seed SHA-256 is unchanged
(`692355638b31d347ced5983a5910491f0556156f79675c2e371ebe9987683247`), `/chosen`
`display-scale` is `03000000`, and the rebound CHMH matches `record.json`.

| Artifact | Digest |
| --- | --- |
| Kernel SHA-256 (52,187,136 B) | `64a97b23eb26870f05e57173f507fd2724e5f2afbd1785da634543becf8b5e35` |
| Outer SHA-256 | `0d0339cc0210a167c79d15a8a92c04c366801c1cec53a942357d7953af22ec75` |
| CHMH SHA-384 | `e141689e004589b8c292f08903b6b6dc5d7d68af3d21477f718395e8366c61abb73de64ac8a85a3b9bf0d1d4e9ca1ca6` |
| Outer-readback FAT SHA-256 | `f6846ce1618adaf7048ddf32feb02fb7a24c6d8c7668c5012082cdca2472ee84` |

Product: `out/nuwa-systemgroup-seed-20261122/vendor-boot-sb-stack2/vendor_boot.img`.
`payload.img` and `outer-audit/actual-vendor-ramdisk.img` both hash to the FAT value.

## What the reviewer must re-decide

1. The paint gate: the hook position, the exact-text match, the 60 s wait bound and
   `1003`, and whether anything else in the file can write `bp_shot_painted`.
2. The kcdata walk offsets, the 112/128-byte thread records and the `at == end`
   strictness for `BUFFER_END`.
3. The identity rule: one `0x903` container plus matching `ts_unique_pid`/`ts_pid`/
   `ts_p_comm` as the exclusion of PID reuse and an exec copy.
4. The boot-arg clamp, the single-shot flag, and the two banner rows with their
   measured widths.

Independent verifier should rerun the documented build with `--mg-reset --hid-standin`,
`scripts/test-sb-stack-paint.py`, `scripts/test-sb-stack-row.py`,
`scripts/test-banner-budget.py`, `scripts/test-banner-short-values.py`, the three linked
guard tests, and the local repack with fresh names; then repeat the outer-readback
comparison, CHMH audit, seed hash, `fsck.fat -vn` and `mdir`. Device behaviour — whether
the gate opens, whether the trap returns, `n`, `w` and the duration — remains
unobserved.

## Revision history

1. Initial candidate: paint-before-call assumed, not proven.
2. Deep review: the call is gated on the paint path's record; a pass that never stores
   the row cannot call, and `r=1003` reports it. Evidence wording corrected (frozen
   pending is not proof of being inside the trap; image top; parser-versus-producer).
