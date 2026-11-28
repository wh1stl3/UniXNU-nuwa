# nuwa post-event summary candidate — 2026-11-27 (review-fix revision)

Status: **host-only, self-checked**, no device access, flash, boot or reboot.
Baseline branch `research/nuwa-ufs-owner-api-20261126` at `adf1057`.
This is a diagnostic increment only: no boot, storage, authentication or write
path changed; the SB0/disposable behaviour and `nuwa-disposable-data=1` gate
are the same as the `6695da98…` candidate.

The previous `ec230dff…` / `8dfe35fa…` pair was returned by deep review and is
**not eligible for flashing**. This revision addresses every review item and
rebuilds the kernel and outer; the old artifacts remain in `out/` as history.

## Why the screen stops after t=112 s

The observed `tzinit[17] exited -- no exit reason available -- (signal 0,
exit status 45)` is a **critical-process exit**, not an ordinary child exit.
`bsd/kern/kern_exit.c::proc_prepareexit()` calls
`proc_handle_critical_exit()` when `p_crash_behavior != 0 || p == initproc`;
that function calls
`panic_with_options(..., DEBUGGER_OPTION_INITPROC_PANIC, "%s -- no exit reason
available -- (signal %d, exit status %d %s)", ...)` (`kern_exit.c:1813-1878`
on this base). The panic screen starts at `y = h/8`
(`scripts/xnu-panic-screen.c:240`) and the diagnostic renderer stops because
the machine panicked. There is no post-event userland to sample in that boot;
the event definitively blocks the lock screen.

The top band (page rows 0-8 at scale 3) survives the panic. The existing page
lost the answers before the panic:

- `EX1..EX4` are drawn on rows 2-5 and overwrite the PID1 row (row 3).
- `DATA mnt` is drawn on row 39, but the `nuwa-ufs-neon=1` evidence rows occupy
  rows 37-42, so the mount row is overwritten before it can be photographed.
- `boot_process_rows` is an absolute-0 stub in this kernel
  (`package/boot-progress-r13/nuwa_boot_progress_stubs.c`), so SpringBoard was
  never sampled.
- `Process exits` keeps per-exit rows in `exit_records`, but the visible rows
  (17-23) are below the panic clear. The EX ring keeps only abnormal exits
  (signal or reason namespace), so `tzinit` status 45 (signal 0, ns 0) is not
  in it at all. The panic message carries the name/status but not the parent.

Existing fields that are collected: last IRQ PC/PSR/SP and an eight-entry
interrupted-PC ring; every exit's pid/name/status/reason namespace/subcode in
`exit_records` (recent/failures/crash, plus a 448-name start/exit census);
an abnormal-exit ring with pid/comm/sig/ns/code/PC/nprocs/AKS; and the panic
message copied into `boot_progress_panic_text`. None of them binds a parent pid
or survives the panic as a single answer.

## Review fixes

1. **Row 0 is dropped, so `DATA0` moves to row 7.** `line()` and `bar()` keep
   `if (!row) return;`; the old `line(0, …)` call was discarded and compiled
   out. The normal page now emits `line(7, …)` for the Data line, and row 0
   stays empty. Row 8 remains the PID1/SpringBoard/EX summary; both rows are
   inside the panic-safe band.
2. **Critical paint does not depend on `display.bound`.** After
   `boot_progress_prepare_scanout()` the renderer sets `display.bound=0`.
   `boot_progress_critical_paint()` now writes two rows directly through
   `px_text()` into `display.frame`, using the still-valid
   `width/height/stride/scale`, and only when `(row+1)*14*scale <= height/8`.
   It does not call `bp_line_bg`, `refresh()` or any bound-gated path.
3. **Paint is called in `proc_handle_critical_exit()`.** The paint call is no
   longer in `proc_prepareexit()`'s critical branch. `boot_progress_critical_capture()`
   sits after `proc_should_trigger_panic()` and the
   `crash_behavior_test_mode` gate; it copies the critical exit's fields before
   `proc_crash_coredump()`/`sync()`, so a later non-panic critical exit cannot
   replace them. The paint sits after `sync()` and immediately before
   `panic_with_options()`, and reads that copy without `exit_lock` or
   `render_busy`.
4. **`ppid` is `int`.** The `pp=?` branch is reachable; an unmatched parent is
   stored as `-1` and rendered as `pp=?`.
5. **Parent publication is one 64-bit atomic word.** `boot_progress_exit_parent`
   stores `((uint64_t)pid << 32) | (uint32_t)ppid` with release semantics;
   `bp_post_latch` loads it with acquire and only accepts it when the high
   pid matches. The critical capture receives `p->p_ppid` directly, so it does
   not depend on the word at all.
6. **SpringBoard sampling is a stack-local walk plus one packed word.**
   `nuwa_sb_cb()` fills a local struct and returns `PROC_RETURNED_DONE` on the
   first match; `nuwa_sb_sample()` starts from the previous word's seen bit,
   walks, then publishes `seen|live|pid|p_stat` as one 64-bit release store.
   The reader acquires that word, so a reader cannot split an in-progress
   sample into a transient `gone`.
7. **Layout/buffer/doc consistency.** The Data buffer is `full[BP_COLS]`
   (120), not `full[96]`; the row is 7; the normal `draw()` paints the summary
   row at its end on every paint, and the critical path paints a separate direct
   copy; the documented comm truncation is `%.12s` (12 characters).
8. **SpringBoard found path sets both top bits.** `nuwa_sb_sample()` now does
   `word |= (1ull << 63) | (1ull << 62) | (pid << 32) | p_stat` for a found
   sample; previously only bit 62 was set when the old word was zero, so
   `bp_post_sb()` (which tests bit 63 first) reported `never`. The host test now
   feeds the actual `nuwa_sb_public` to `bp_post_sb()` and checks
   `never` → `95:RUN` → `gone`, with `word >> 62 == 3` while present.
9. **Critical capture is after the panic decision.** It moved from
   `proc_prepareexit()`'s critical branch into `proc_handle_critical_exit()`
   after `proc_should_trigger_panic()` and the `crash_behavior_test_mode`
   gate, before `exit_reason_get_string_desc()`/coredump/sync.
10. **PID1 state ordering.** The sampler writes `nuwa_pid1_state` first and
    then release-stores `nuwa_pid1_present`; the renderer acquire-loads
    `present` before reading `state`, so it cannot pair a new present flag with
    a stale state.

## On-screen result

```
row 7: [data-trial] DATA0 st=4 err=0 ro=0 dev=12345678 seed=1 first-attempt
row 8: [data-trial] S p1=RUN sb=95:RUN EX=17:tzinit:0/45:pp=1
```

- `p1`: PID1 state from the existing two-second probe (`IDL/RUN/SLP/STP/ZMB`
  or `absent`). It is a sample, not a live read at draw time.
- `sb`: SpringBoard from the same probe: `never`, `gone`, or
  `<pid>:<state>`. `gone` means it was seen and is no longer present.
- `EX`: every exit (including status 45 with signal 0): pid, 12-char comm,
  signal/exit status, parent pid; `pp=?` when unmatched.
- `DATA0`: the completed first mount attempt (st/err/ro/dev/seed), latched by
  `nuwa_data_mount_prepare()` before initproc exec. `DATA now` is the sampled
  in-progress stage; `DATA0 not run` means it never started.

## Build and artifacts

WSL root, device worktree, same inputs as the `6695da98…` candidate:

```sh
python3.11 -B scripts/build-nuwa-display-native.py \
  --base /mnt/d/Code/PortingiOS/UniXNU --cpo <IOPMGR.cpo.json> \
  --linker-dir /opt/unixnu-linux/CommandLineTools/usr/bin \
  --r35-dir out/nuwa-r35-20261119 --r35l-dir out/nuwa-r35l-regs-full-20261121 \
  --cpu-only --no-software-vsync --candidate --mg-reset --hid-standin \
  --crashcap --pixsig --data-persist-diag \
  --data-candidate-gpt ../.cache/device-evidence/20261107-recovery/gpt-sda.bin \
  --disposable-data --post-event --out out/nuwa-postevent-20261127-build-r8

python3.11 -B scripts/package-nuwa-crashcap.py \
  --base /mnt/d/Code/PortingiOS/UniXNU \
  --kernel out/nuwa-postevent-20261127-build-r8/kernel.macho \
  --out out/nuwa-postevent-20261127-package-r6 \
  --disposable-data-template <out/nuwa-ufs-neon-20261126-package/vendor_boot.img> \
  --post-event
```

| Artifact | Value |
| --- | --- |
| Kernel (52,207,616 B) | `4e02af6228d363907d7d3fbe68776d80e649bb4516cd272343f89e4e38818398` |
| Outer (100,663,296 B) | `b9103e97409e83b1a70d058391e260b320500e016ece828fb1dacf02e74497b8` |
| Readback FAT | `29f24dc5888b4965921e4c1a0630afe19b2b1ca53ee6fb0692d3571c507715af` |
| CHMH (experimental) | `d5f1299efaf7a672919b517eb9a27e62f8337da5ef8795991a624c5d264b3b22ebd67e3d04cd7443ef3501c185f314a5` |
| Args | 602 B (same tokens; no new boot arg) |
| Seed / trust | `3c81135b…` / `eb1475f6…` unchanged |
| FAT free | 11,021,312 B |

The outer's only FAT changes are the kernel, its ADT CHMH and the
`nuwa-disposable-data=1` config the template already injects. The header/tail
and seed are unchanged. A rebuild into a different `out/` changes `__FILE__`
paths and FAT timestamps, so these exact hashes belong to the recorded
`build-r8`/`package-r6` directories; a verifier rebuild should compare the
marker, linked symbols and tests rather than require the same outer hash.

## Serial debug check

The console line `Serial requested, consistent debug disabled or debug boot
arg not present, configuring debugging over serial` comes from
`osfmk/kdp/kdp_udp.c:2268-2287` (`kdp_init`), not from the console selection.
The implemented KDP serial path is selected by `kdp_match_name=serial`; on
arm64 it proceeds when consistent debug is disabled or `debug_boot_arg` is
absent. That is a **KDP debugger** transport, not general `kprintf` output.

The separate console path is the `serial=` boot argument
(`osfmk/arm/arm_init.c:544-580`, `SERIALMODE_OUTPUT`). It only switches the
console when `serial_init()` returns a serial device
(`pexpert/arm/pe_serial.c:742`). Neither `dts/nuwa.dts` nor
`dts/sm8550.dtsi` contains a serial/uart/geni/qup node, so `serial_init()`
returns 0 and `PE_init_kprintf` (`pexpert/arm/pe_kprintf.c:61`) falls back to
the video console. The `-v serial=3` token seen in older args is therefore
inert on this board. No supported boot-arg path to serial console output
exists; the screen summary remains the observation method.
(`CONFIG_SERIAL_KDP` is compiled in — the KDP string is present — but the
hardware path is not.)

## Tests and linked audit

`scripts/test-nuwa-postevent.py` now extracts the actual generated functions
and compiles/executes them on the host, then disassembles
`native-with-stabs.macho`:

```text
DATA0 on non-zero row through line()           PASS row 7, not row 0
critical pixels: top=120960 below=0
critical paint: bound=0 writes y<h/8 pixels    PASS two px_text rows, no refresh/bound
unmatched parent prints pp=?; matched pp=<n>   PASS single 64-bit publish
sb word=c000005f00000002 false_gone=0
SpringBoard never -> 95:RUN -> gone, no false gone PASS high bits 0xc while present
linked critical order                          PASS capture < sync < paint < panic
critical paint calls px_text twice             PASS px_text calls=2
critical paint bypasses refresh/prepare_scanout PASS no full-page refresh
linked marker and summary strings              PASS marker, DATA0, pp=? present
pid1 sample packs seen|live 0xc000000000000000 PASS seen bit set on first found sample
capture after test-mode gate in disassembly    PASS gate before capture
capture after panic decision, paint after sync PASS source order in proc_handle_critical_exit
post-event host tests and linked disassembly: PASS
```

`120960` is exactly two full rows (`2 * 14 * 3 * 1440`); the `below=0`
assertion keeps the writes strictly above the panic screen's `y = h/8`.
The linked order check is on `_proc_prepareexit` (the compiler inlines
`proc_handle_critical_exit` into it): capture, then `_sync`, then
`_boot_progress_critical_paint`, then `_panic_with_options`.
`_boot_progress_critical_paint` calls `_px_text` twice and does not call
`_refresh` or `_boot_progress_prepare_scanout`. `_nuwa_pid1_sample` contains
`orr x8, x8, #0xc000000000000000` (the seen|live pair), and the capture call
appears after the `proc_should_trigger_panic`/test-mode gate in the staged
`kern_exit.c`.

Original audits and tests also rerun on this build:

- `tests/test-nuwa-retained-entry.py … --disposable` → exit 0.
- `tests/test-nuwa-crashcap.py` → exit 0.
- `tests/test-nuwa-data-persist.py` → exit 0.
- `tests/test-nuwa-disposable-data.cpp` and `tests/test-nuwa-data-write.cpp`
  (UBSan) → exit 0 (same C sources; the later change is renderer-only).
- `tests/test-nuwa-pixsig.py`, `tests/test-nuwa-dspcount.py` → exit 0.
- `package-nuwa-crashcap.py --audit-only --post-event`, `fsck.fat -vn`,
  `mdir` → exit 0.
- `porting-record.py check --device .` → 14 areas checked.

`tests/test-nuwa-ufs-neon.py` is not applicable to a `--disposable-data` build
— its host fixture does not define the disposable provider and fails with
`openDisposableData` undeclared. That limitation predates this increment.

## Limits

- The two rows are verified in a host framebuffer at `bound=0`; the actual
  panel scanout and panic-screen timing were not measured on glass.
- PID1/SpringBoard remain two-second samples; they do not prove liveness at
  the exact panic instruction. The panic prefix distinguishes an initproc exit
  from a child critical exit.
- The SpringBoard walk runs every two seconds on the existing probe; its cost
  and any process-list interaction were not measured.
- `tzinit` status 45 was not reproduced on the host; the kernel hook records
  what `proc_prepareexit()` / `proc_handle_critical_exit()` receive.
- No device write, flash, boot or reboot was performed. The candidate is not
  approved for flashing; the existing SB0/disposable write gates are unchanged.
