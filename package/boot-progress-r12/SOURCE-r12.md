# boot progress r12 sources — provenance and the one divergence

Upstream: `https://github.com/UniXNU/UniXNU-sheng` @ `998d0cc5023d4eff54a1ef40cce6ec89dc10083c`
(MIT file header; repository root LICENSE is BSD-2-Clause-Patent). Same source and commit as
r11's `package/boot-progress/`.

## Files

| file | origin | sha256 |
| --- | --- | --- |
| `BootProgress.c` | upstream `package/BootProgress.c` + 15 exact-string edits applied by `out/nuwa-systemos-mount-20261115-r1/make-renderer.py` | see `build-boot-progress-report.json` of the r12 run |
| `nuwa_boot_progress_stubs.c` | r11 `package/boot-progress/nuwa_boot_progress_stubs.c` with two changes (below) | same report |
| `BootProgressCore.h` / `BootProgressDisplay.h` / `BootProgressLifecycle.h` / `BootProgressPulse.h` | **not copied**; the build puts `package/boot-progress/` on the include path, so the pinned upstream headers are used unchanged | pinned in `out/nuwa-systemos-mount-20261115-r1/build-boot-progress.py` |
| `Font.h` | `uefi-nuwa/.../FrameBufferSerialPortLib/Font.h` (unchanged, `-I` only) | same report |

The upstream `package/boot-progress/BootProgress.c` is **not modified**; r11's build script and
pins still work. This directory exists so both variants can be built side by side.

## The 15 renderer edits (N1..N7 in `make-renderer.py`)

1. `extern char nuwa_pid1_row[120]` — one status row for pid 1 and the SystemOS mount.
2. `display.scale` — `boot-progress-scale` (1..3, default **3**), clamped so at least 40 columns
   remain.  The upstream rule `w>=2160 && h>=1400 ? 3 : 1` selected **1** on this board because
   the framebuffer is portrait (1440 wide, 3200 tall), which is why the r11 page used about a
   fifth of the screen with 6x14-pixel glyphs.
3. pid 1 row at **row 3** (continuation row 4), i.e. directly under the time and UFS rows.
4. The `TCR/TTBR/SCTLR` and `last IRQ PC` rows move from 3/4 to **33/34** (rows 3/4 now hold pid 1).
   No row is dropped.
5. Console: seven lines, each with a continuation row (**17..30**), so a kprintf line longer than
   the column budget wraps instead of being cut at the panel edge.
6. Text shortened to fit 80 columns (the scale-3 budget): stage bar (`%.70s`), stage history
   (`%3us %.75s`), UFS probe tail (`%.28s`), MEM, CPU IRQ, CLK, OBS, UFS TIME, GIC row moved to 31.
7. `line_or_wrap(row, spare, text, color)` helper: only wraps when the text exceeds the column
   budget; the spare row is always rewritten so a shorter text leaves nothing stale.

## Stub changes

* the four `native_virtio_*` definitions are removed — the official VirtioMmioBlock component is
  linked in r12 and owns them (keeping both would be a duplicate symbol),
* `boot_process_capture()` calls `nuwa_pid1_sample()`, so the renderer's existing two-second
  process probe refreshes the new row without a new thread.

## Row map (r12, all rows kept)

| row | content |
| --- | --- |
| 0 | title bar (`[nuwa-r12]`) |
| 1 | `time= idle= IRQ= monitor= lost= root= procs= free=` |
| 2 | UFS counters (+ root probe tail when nothing is published) |
| 3-4 | **PID1** (state/comm/initproc/nprocs) + **SYSOS** (stage/errno/device/root-auth) |
| 5 | `stage:` latest |
| 6-11 | stage history (6) |
| 12-15 | PC samples (4) |
| 16 | console bar (or exit bar) |
| 17-30 | console, 7 entries × up to 2 rows |
| 17-23 | exit records, only when `total>0` (they replace console rows, as in r11) |
| 24-33 | sheng process block: inert here (`boot_process_rows` is an absolute-0 stub) |
| 31 | GIC |
| 33 / 34 | TCR/TTBR/SCTLR and last IRQ PC |
| 35-36 | MEM (+ continuation) |
| 37 / 38 | CPU IRQ phase / SMP |
| 39 / 40-41 | cpufreq (inert) / CLK (+ continuation) |
| 42 / 43-44 | TIMER / OBS (+ continuation) |
| 45-46 | UFS CMD/QUEUE (inert) / UFS TIME |
| 47 | reserved for the pulse worker |
