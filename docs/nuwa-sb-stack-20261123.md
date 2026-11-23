# One-shot SpringBoard thread snapshot (nuwa-sb-stack)

Host candidate only. The build, the CHMH rebind and the outer readback are
self-checked on this host; nothing was written to a device, and the call has never
run. Reviewer re-review of the kcdata walk, the identity rule and the boot-arg
trigger is pending; the unbounded interrupt-off window and the cross-thread
heartbeat need `deep_reviewer` review. Authentication **NOT REACHED**.

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

Only three numbers of interest are produced: total `THREAD_SNAPSHOT` records in the
matched task container, how many carry `SS_TH_WAIT`, and the result code.

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
- Only record headers are walked. **No stack frame is decoded** and no user memory is
  read: the walk reads item type/size/flags, the one task snapshot's pid/unique
  id/name, and `ths_state` from each thread record.
- `w=n` means every thread record in that task carried `SS_TH_WAIT` at that instant.
  It is a single sample of one task; **it does not prove a deadlock**, and it says
  nothing about why the threads wait, what they wait on, or whether they are running
  on a core.

### Result codes

| r | Meaning |
| --- | --- |
| 0 | Success: `n`/`w` are the counts. |
| other | The `KERN_*` value returned by the kernel, passed through unchanged (40 = `KERN_LOCK_OWNED`, 52 = `KERN_INSUFFICIENT_BUFFER_SIZE`). `n`/`w` show `-`. |
| 1000 | No confirmed positive SpringBoard pid, or that pid no longer resolves to a live `SpringBoard`. Not attempted. |
| 1001 | Buffer integrity failed: BEGIN header, item bounds, container balance, or `BUFFER_END`. Nothing published. |
| 1002 | Identity failed: task-container count, pid, unique id, or process name. Nothing published. |

Any non-zero `r` with `-`/`-` means the counts were rejected as a whole; partial
counts are never published.

## Eleven requirements to implementation

| # | Requirement | Implementation |
| --- | --- | --- |
| 1 | `nuwa-sb-stack=<s>` trigger; absent/0 off, <60 raised to 60, one shot, no retry | `PE_parse_boot_argn("nuwa-sb-stack",...)` + `if (shot_at && shot_at<60) shot_at=60;` in `touch_monitor`; `if (shot_at && !shot_used && now>=shot_at) { shot_used=1; bp_shot_arm(); }` — `shot_used` is never cleared |
| 2 | After `touch_overlay()` returns, before `assert_wait_timeout()`, no busy/lock held | `bp_shot_take()` runs on the line after `touch_overlay();` and before the wait; `touch_overlay` releases `render_busy` before returning; no other lock is taken in between |
| 3 | `STACKSHOT_KCDATA_FORMAT\|STACKSHOT_TRYLOCK`, delta 0, pagetable mask 0, no `THREAD_WAITINFO`, `KERN_LOCK_OWNED` ends it | Single call: `(uint64_t)STACKSHOT_KCDATA_FORMAT \| (uint64_t)STACKSHOT_TRYLOCK, 0, 0`; any non-zero return (40 included) is published as-is with no retry |
| 4 | Static 1 MiB aligned buffer, length 0 before the call, `KERN_INSUFFICIENT_BUFFER_SIZE` for capacity, no growth/retry | `static uint8_t bp_shot_buf[1u<<20] __attribute__((aligned(4096)))`; `unsigned bytes = 0;` immediately before the call; rc 52 passes through untranslated |
| 5 | Parse only `KERN_SUCCESS && 0 < bytes <= sizeof`, check BEGIN/bounds/container balance/`BUFFER_END`, publish nothing on failure | `bp_shot_parse`: header item must be `0x59a25807` with size 0; `item->size > end-data` fails; container END must match the innermost BEGIN identifier and depth must return to 0; `BUFFER_END` (`0xf19158ed`) must close the buffer exactly at `bytes`; `*totalp`/`*waitp` are written only after every check |
| 6 | Confirmed positive pid only; keep pid and unique id; accept one matching ordinary task; verify pid + unique id + `SpringBoard`; reuse/transitioning fails | pid = census `bp_proc_pid[0]`; `bp_shot_resolve` = `proc_find` + `proc_name=="SpringBoard"` + `proc_uniqueid`; parse requires exactly one `STACKSHOT_KCCONTAINER_TASK` (0x903) carrying that id, rejects 0x931 transitioning with that id, and requires the one task snapshot to agree on `ts_unique_pid`, `ts_pid` and `ts_p_comm` |
| 7 | `(ths_state & SS_TH_WAIT)` bit test, only matched task's `THREAD_SNAPSHOT` | `if (thread->state & BP_SHOT_TH_WAIT)` inside the matched container, only for type 0x906 |
| 8 | One row `SHOT n=<n> w=<w> r=<code>`, `-`/`-` when r≠0, ≤80 columns with measured width | `SHOT n=%u w=%u r=0%s` / `SHOT n=- w=- r=%u%s`, read back at the `nuwa_rows()` slot list; measured 16/13/22/37 columns (worst case 37) |
| 9 | Sequenced heartbeat before and after, to separate "this thread did not return" from "whole core paused" | `bp_shot_beat = seq<<8 \| state` stored with release semantics before the call (`pending`) and after it (`done`/`fail`); the pending beat is written before `touch_overlay()` so the pending row is painted **before** the call |
| 10 | CNTPCT delta / `cntfrq` (19.2 MHz) in ms, mark over-threshold with `to` | `mrs cntpct_el0` before/after, `mrs cntfrq_el0` with 19200000 fallback, `ms = delta*1000/freq`, `to` above 1000 ms |
| 11 | Document context, interrupt-off window, buffer cap, count-only behaviour, `w=n` meaning | This section |

### Reading the heartbeat honestly

The banner is painted by the same thread that makes the call. If the call never
returns, the panel keeps its last frame — the one painted between the pending beat
and the call — so `SHOT pending <k>` with no matching `SHOT done/fail <k>` means the
kernel stopped inside the snapshot, not before it. Because only the boot CPU runs, the
same freeze stops every other banner row as well; the heartbeat locates the stop, it
does not isolate the fault to the stackshot by itself. A `done` row without a
following `SHOT n=...` row is not expected: both are published in the same pass.

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
  --out out/nuwa-sb-stack-20261123-build
```

WSL Ubuntu-22.04 as root (the compile tree and `/root/...` inputs are root-owned);
`out/nuwa-sb-stack-20261123-build.log`. `BootProgress.o` carries exactly one
`ARM64_RELOC_BRANCH26 _stack_snapshot_from_kernel` and undefined `_proc_find`,
`_proc_name`, `_proc_uniqueid`; the linked kernel defines
`_stack_snapshot_from_kernel` at `0xfffffff00723ea98`. Linked guards
`test-r35g-ux-linked.py`, `test-r35k-regs-linked.py`, `test-r35e-irqguard-linked.py`
exit 0 on the compact kernel.

Host checks run on the generated source: `scripts/test-sb-stack-row.py`
(`generate(mg_reset=True)` slices the real walker and rows) passes a synthetic kcdata
buffer — BEGIN + ordinary task container + task snapshot + two thread containers
(states 1 and 4 → `n=2 w=1`), v2-padded 112-byte records, plus negative cases: missing
`BUFFER_END`, mismatched container END identifier, 120-byte thread record, duplicate
task container, transitioning container, pid off by one, wrong process name, wrong
unique id and an 8-byte truncated buffer, each returning 1001/1002 with `*totalp`
untouched. `test-banner-budget.py` and `test-banner-short-values.py` still pass.

Packaging used `out/nuwa-systemgroup-seed-20261122/repack-sb-stack.py` (base
`vendor-boot-hid-stage`, baseline outer
`01e6e1c71346c05fb7cc9885d1179346b72e296ef3bbd993952017b6edd6479d`, `HID_KERNEL`
rebound to the new kernel, `--enable-hid-standin` profile retained). The outer
readback `unixnu.toml` differs from the baseline by exactly one appended token, the
xnu args are byte-identical otherwise:

```text
... nuwa-mg-reset=1 nuwa-sb-restart=400 nuwa-sb-restart-every=180 nuwa-hid-standin=1 nuwa-sb-stack=360
```

`fsck.fat -vn` reports 9 files and 106,239 of 129,022 clusters used; `mdir` reports
**11,664,896 B free**, above 8 MiB. Outer-readback seed SHA-256 is unchanged
(`692355638b31d347ced5983a5910491f0556156f79675c2e371ebe9987683247`), `/chosen`
`display-scale` is `03000000`, and the rebound CHMH matches `record.json`.

| Artifact | Digest |
| --- | --- |
| Kernel SHA-256 (52,187,136 B) | `52b13eb2b56530b66e94898ad2e69865151876adfe541c470da2a03c9cfde219` |
| Outer SHA-256 | `f3b15b3f85bc144eb68a8d1c25d3dbe229971bb438c5dbff3627c4b06039b05f` |
| CHMH SHA-384 | `b5e284a7d746d8bdf7d868c06ed81eab1f2ffa4a5291004a0392478f58a847939d28959907a87d8496222c2207f5bcbd` |
| Outer-readback FAT SHA-256 | `25fcd759fad1082b76fee7c22527734d34690646439dae477df53496ffbc6037` |

Product: `out/nuwa-systemgroup-seed-20261122/vendor-boot-sb-stack/vendor_boot.img`.
Kernel, outer, CHMH and FAT digests above are from that directory; `payload.img` and
`outer-audit/actual-vendor-ramdisk.img` both hash to the FAT value.

## Layout effect the reviewer must accept

The 1 MiB zero-fill buffer grows `__DATA` vmsize from `0x34c000` to `0x44c000`, so every
segment above it moves up by exactly `0x100000`: `__BOOTDATA` `0xfffffff007d34000` →
`0xfffffff007e34000`, `__PRELINK_INFO` `0xfffffff008070000` → `0xfffffff008170000`, and
`__LINKEDIT` likewise, leaving the top of the image at `0xfffffff008170000`. Segment
file offsets and the 52,187,136-byte file are unchanged, so the loader walks the same
`LC_SEGMENT_64` records and maps one more MiB of zero-fill where the header now says.
Nothing in this repository pins the old addresses — the linked guard tests recompute
them from the image and pass — but whether the loader's reserved kernel window covers
the new top is **not** checked here.

## What the reviewer must re-decide
1. The kcdata walk: offsets, 112/128-byte thread records (v2 padded, v3, v4), the
   task snapshot layout, and the `at == end` strictness for `BUFFER_END`.
2. The identity rule: is a single `0x903` container + matching `ts_unique_pid`/
   `ts_pid`/`ts_p_comm` sufficient to exclude PID reuse and an exec copy here?
3. The boot-arg clamp, the single-shot flag and the placement relative to
   `touch_overlay()`.
4. The two new banner rows, their priority class and the measured widths.
5. Cross-thread publication of the beat/counts (`deep_reviewer`): the values are
   written by the monitor thread and read by the same thread in `crash_banner`, but the
   release/relaxed pair is a claim worth checking.

Independent verifier should rerun the documented build with `--mg-reset --hid-standin`,
`scripts/test-sb-stack-row.py`, `scripts/test-banner-budget.py`,
`scripts/test-banner-short-values.py`, the three linked guard tests, and the local
repack with fresh names; then repeat the outer-readback comparison, CHMH audit, seed
hash, `fsck.fat -vn` and `mdir`. Device behaviour — whether the trap returns at all,
`n`, `w` and the duration in ms — remains unobserved.
