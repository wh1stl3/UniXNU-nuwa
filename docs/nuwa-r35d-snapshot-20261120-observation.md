# r35d exit snapshot repair — host only

Parent reports deep review of r35c as CHANGES REQUIRED. This candidate
does not inherit the earlier review: reviewer and deep_reviewer must
review the final changes and artifacts again. No device action.

Each `draw()` takes a private four-slot/count view while holding
`exit_lock`, releases it before pixels, and uses the view for both the
title and EX rows. Lock acquisition failure returns from `draw()` before
the page update; in particular a frozen polling path can retain an older
page. Existing `exit_dropped` still counts exit-hook lock failures only.
Nested renderers may interleave framebuffer writes; this repair protects
the exit-record view, not the entire renderer or framebuffer.

For A/B/A with distinct AKS values, the last A console record uses A's
slot, hence A's **first-sample** AKS counters, not B's or the latest
event's. The console `np` remains the current event's process count.
Name/signal/namespace/64-bit-code key, saturation, rows 0/2/3/4 and
exit-thread saved-PC semantics remain as in
`nuwa-r35c-exit-detail-20261120-observation.md`; PC is not asserted to
be the fault PC.

The host replay uses the generated hook, snapshot function and the
actual formatting fragment. An outer draw takes its view, an inner draw
records A again and takes another view, then both format: outer sees
`n=1`, inner `n=2`. A busy exit lock leaves the output unchanged and does
not increment `exit_dropped`. A/B/A logs A's first `aks=11/12` after B's
`21/22` and current values `31/32`. These are deterministic host
interleavings, not concurrent hardware execution.

The full-symbol reference kernel is 55,721,984 B, SHA-256
`ba968c2c15f8873e806f4b19b563fe19d6cd8732392a6fa2fa57fd9391705325`.
ARM64 native disassembly of `_draw` shows the r35c prologue allocating
96+3008 = 3,104 B and this same-function full and compact builds
96+3376 = 3,472 B,
an increase of **368 B per invocation**. The `boot_progress_irq` →
`boot_progress_poll` → `draw` frozen path can execute in interrupt context;
the local XNU source defines `INTSTACK_SIZE` as 16,384 B. The complete
interrupt call chain, interrupt nesting and live remaining stack were not
measured, so this does not establish stack safety; deep review is required.

The compact kernel is 52,006,912 B, SHA-256
`9e6a15388c1ac09932eaeb9eef4511d3df9a5587935ee507a4c7fed66a317492`.
The existing same-source full/compact audit self-checked 128,827 STABS
removed, 49,608 non-debug symbols and all 52,674 prelink bindings
preserved. Packaging self-checked: FAT SHA-256
`9a0d799f97d0667441d4f735cbcfd2103141ae563a9fff5422052bbaa826d33f`,
outer SHA-256
`cd92d07d603dd5ac2ea8922d1cfe57d123ce274cf26613201736c03e5973fee1`,
and freshly rebound CHMH SHA-384
`4c49a290616c62e39805f7390cb9bd5ea5772ca4f65542b5767ffc6c6df51bb778cf5d2f7ff5b97a6c3288148b18f48d`.
The inherited packager profile string still says `r35c-detail` and the
screen build tag remains the existing `nuwa-r35`; identify this candidate
by the hashes above. The separate outer readback audit and linked audit
(`ALL PASS`) are self-checked. The FAT scan, FSInfo and `fsck.fat -vn`
agree on **12,070,400 B free**, 3,681,792 B above the 8 MiB floor;
the outer readback FAT matches the packaged FAT. Final 49,608 non-STAB
symbol tuples match the same-source unstripped kernel.

## Reproduction (WSL Ubuntu-22.04 root)

From the diagnostic worktree, use four new sibling output paths:

```sh
PY=/home/wh1stl3/.local/bin/python3.11
O=/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out
FULL=$O/nuwa-r35d-verifier-full
COMPACT=$O/nuwa-r35d-verifier-compact
P=$O/nuwa-r35d-verifier-package
A=$O/nuwa-r35d-verifier-audit
$PY -B scripts/test-r35b-exit-detail.py "$O/nuwa-r35b-compact-r3-20261120/BootProgress.c"
$PY -B scripts/build-r35b-kernel.py "$O/nuwa-r35-20261119" "$FULL" --detail
$PY -B scripts/build-r35b-kernel.py "$O/nuwa-r35-20261119" "$COMPACT" --detail --compact --audit-against "$FULL"
export NUWA_DETAIL_BUILD="$COMPACT" NUWA_DETAIL_KERNEL="$COMPACT/kernel.macho"
export NUWA_DETAIL_SHA=9e6a15388c1ac09932eaeb9eef4511d3df9a5587935ee507a4c7fed66a317492
export NUWA_DETAIL_BYTES=52006912 NUWA_DETAIL_REFERENCE="$FULL/kernel.macho"
$PY -B scripts/build-ufs-apfs-root-chmh-r35b.py --output "$P"
$PY -B scripts/build-ufs-apfs-root-chmh-r35b.py --output "$A" --audit "$P"
$PY -B scripts/test-r35b-compact-package.py "$P" "$A"
```

The pinned hash intentionally rejects a rebuild that differs from the
self-checked candidate. Independent verifier has not rerun these commands.
