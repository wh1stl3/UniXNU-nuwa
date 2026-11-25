# lsd exception frame capture — 2026-11-25

Host-only candidate, **self-checked**. No device access or flash. Deep review
and independent verifier rerun pending; authentication NOT REACHED.

## Capture and panel contract

- Reuse the exact `p_comm == "lsd"`, nonzero final BSD signal gate just before
  `threadsignal()`. `get_user_regs(target_thread)` supplies PC, LR, SP and
  x29. The four CR register rows retain the old format; `CRS+` lists raw saved
  LRs from the frame chain, not the live PC/LR already shown in `CR+`, and
  does not symbolize or validate the return addresses.
- The existing pinned XNU 8796.141.3 source (`1b191cb58250d0705d8a51287127505aa4bc0789`,
  APSL 2.0) dispatches the kernel IPC kobject inline after unlocking the
  port queue (`osfmk/ipc/ipc_kmsg.c:2964–2974`). The runtime gate is still
  `target_thread == current_thread()`; a different target gives `na` with
  no `copyin`. Actual lsd runtime coverage is unverified.
- With ARM64 saved state, check the whole 16-byte record is in
  `[SP, SP + 1 MiB)`, with an 8-byte-aligned FP and no SP/window wrap.
  Each `copyin` reads `[next FP, saved LR]`. At most eight calls and 128
  bytes; no map switch. `copyin` may block on a page fault: this bounds
  bytes and iterations, not latency. No change to `copyin` semantics.
- Stops: `badfp` for missing ARM64 SP/FP, invalid range/alignment, or a
  null/non-increasing/out-of-range next FP; `readfail` for a failed copy;
  `zero` for LR=0; `limit` after eight records with valid links. A
  successfully read nonzero LR is retained even when the next link is
  invalid. A terminal null link is therefore a short `badfp`, not `zero`.
  An eighth record with a bad link reports `badfp`, not `limit`.
- Each accepted LR goes directly to the reserved slot. The existing
  two-slot CAS, global `wr_seq` and `(state,gen)` publication/bracketing
  are unchanged. Count, stop and frame elements are SC payload fields.
  While `copyin` sleeps, the slot stays WRITING; the reader rejects it
  rather than displaying a partially populated record. Old unused frame
  cells are not read after reuse with a smaller count.
- `CRS n=<shown> stop=<reason>` and `CRS+1 pc=<16hex>` through `CRS+8`
  immediately follow the four `CR`/`CR+` rows; optional `CR2` follows
  the CRS group. Widths are at most 21 and 25 columns for CRS, and 77
  for CR. The existing 1440×3200, scale-3 geometry yields 80 columns
  and the capped 24-row budget: all eight fit with SHOT. With a competing
  full 10-row panel, four frames and the SHOT row fit. A 9-row budget keeps
  four frames even without room for SHOT. With fewer rows CRS can yield
  as a unit rather than print fewer than four from a long trace; genuine
  shorter traces use their actual count. `n` describes the selected
  prefix; `stop` always describes the capture. A paint yield cannot break
  the selected crash row group.

## Executed host fixtures

```text
PASS normal eight (8 copyin): CRS n=8 stop=limit
CRS+1 pc=0000000100001000
CRS+2 pc=0000000100001004
CRS+3 pc=0000000100001008
CRS+4 pc=000000010000100c
CRS+5 pc=0000000100001010
CRS+6 pc=0000000100001014
CRS+7 pc=0000000100001018
CRS+8 pc=000000010000101c
PASS backward link after three (3 copyin): CRS n=3 stop=badfp
PASS failed fifth read (5 copyin): CRS n=4 stop=readfail
PASS zero LR (1 copyin): CRS n=0 stop=zero
PASS short chain (null next FP) (2 copyin): CRS n=2 stop=badfp
PASS non-current (0 copyin): CRS n=0 stop=na
PASS record crosses 1 MiB boundary (0 copyin): CRS n=0 stop=badfp
PASS SP window overflows (0 copyin): CRS n=0 stop=badfp
PASS full 24-row panel: CRS n=8 stop=limit; CRS+4 pc=000000010000100c; SHOT pending 1
PASS full 10-row panel: CRS n=4 stop=limit; CRS+4 pc=000000010000100c; SHOT pending 1
PASS 0–3 rows omit CR; 4–8 omit CRS; yield never interrupts a selected CR/CRS group
PASS maximum CR line width=77/78
PASS maximum CR2 line width=47/78; CRS header=21/78; CRS+ frame=25/78
PASS linked: BSD -> osfmk capture -> recorder before threadsignal; one copyin call site
```

CAS contention/retry, torn reads, DSP count and PEER regressions also exited 0.
All frame values above are synthetic; there is no new lsd crash evidence yet.

## Package and readback

`out/nuwa-crashframes-20261125-package/vendor_boot.img`, 100,663,296 B.
The pure-Python outer/FAT audit reread the outer, checked byte-identical
header/tail and all FAT files against the DSP rollback image, and verified
that only the kernel and its ADT changed (ADT: CHMH field only). This
preserves the complete 561-byte args (`nuwa-sb-stack=900`,
`disable-jobs=com.apple.iconservices.iconservicesagent`, all `offline-legacy-*`,
no `sheng-smp`) and the seed. CHMH is an experimental kernel binding, not
authenticated identity. FAT readback is 67,108,864 B and **11,025,920 B free**
(floor: 8 MiB); `fsck.fat -vn` and `mdir` agreed.

| Artifact | Digest |
|---|---|
| Kernel SHA-256 | `bb758c3cf380a4bad914399de97a7cfbc7025f3a77754f5b21bcd48e8c65c23c` |
| Outer SHA-256 | `b83021a7799cacb3bd4086162cae9474f267dc6dc6294eb11d5c4f0c6374e157` |
| CHMH SHA-384 | `0cf294e7bb627e97cbefc374476b2a6ff99dc2be649d48c78472d6f6cd17413059aca226947baf25ff6163fdc789415a` |
| Readback FAT SHA-256 | `631d654e24e43ccfbdee5a77f7542c888e32cbe0688a512a4cc4083ed09bd6b0` |
| Seed SHA-256 | `3c81135b384d8e090521205f2d69b3c197521e6d03c63682419d021bf0f24e5e` |

Rollback outer SHA-256:
`7c8ee0d61e61951a6115e955dd650461848a0ab16111a89ce2816d6b2e7aba73`.

## Verifier rerun

Use the single-core build command, pins and environment in
[the crashcap recipe](nuwa-crashcap-20261125.md#reproduction), with a fresh
`B` (this run: `out/nuwa-crashframes-20261125-build-r2`). The UniXNU checkout
is still `693f5d9cae8a408dd18b39f3f9fdc4228c934241`; upstream HEAD
`8542980d02b4d2cc5c32ee3542de1760b2562aac` matched before and after building
and was not adopted. Set `P` to a fresh output for repacking; FAT timestamps
can change a new repack's outer and FAT digests.

```sh
"$PY" -B tests/test-nuwa-crashcap.py "$B/kernel.macho"
"$PY" -B tests/test-nuwa-dspcount.py
"$PY" -B tests/test-nuwa-peer-probe.py
MAKEFLAGS=-j1 taskset -c 0 "$PY" -B scripts/package-nuwa-crashcap.py \
  --crashframes --base "$BASE" --kernel "$B/kernel.macho" --out "$P"
"$PY" -B scripts/package-nuwa-crashcap.py --crashframes --audit-only \
  --base "$BASE" --kernel "$B/kernel.macho" --out "$P"
fsck.fat -vn "$P/readback-fat.img"
mdir -i "$P/readback-fat.img" ::/EFI/UniXNU/Payloads
```
