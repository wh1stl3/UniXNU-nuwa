# r35g: Mach exception origin, host only

`--detail --exception` adds one observation at the BSD exception-to-signal
conversion in `handle_ux_exception()`. The generator uses the original
`ux_exception.c` from the pinned XNU 8796.141.3 source (APSL 2.0), and the
existing r35f boot-progress renderer; both source hashes, the replay command
record and the replaced object are checked before use. UniXNU checkout
`693f5d9c…` and the existing 329/330 and r35f drawing gates stay unchanged.

The hook runs after process lookup and translation, before signal delivery.
The reader gets the referenced exception target's saved user PC, not the PC of
the current server thread. It records each valid Mach exception without changing
the return, signal, or delivery conditions. The writer has no drawing, allocation
or sleeping path; it uses the same non-blocking acquire/release try-lock as EX.
A busy lock can drop an event. Four slots are retained independently from EX;
the latest slot is copied under the lock into the same private view as EX.
Row 5 then shows `X1 pid=<d> t=<x> c=<x> s=<x> pc=<x>` (`pc=-` for missing
saved state). Without a capture, the preceding SYSOS row 5 is unchanged; with
a capture, X1 takes that row without altering EX, draw entrypoints or scanout.

A matching breakpoint record (`t=6`) identifies a Mach exception that reached
BSD translation for that PID. X1 is not an exit verdict or a backtrace, and
cannot prove the source of an unmatched EX entry: earlier Mach handlers, signal
delivery outside this call chain, overwrite and lock drops are not covered.

Interpretation rules:

1. If X1 is present but its PC does not point to a `brk` instruction, record
   that result and investigate the actual instruction and exception fields;
   do not force a `brk` interpretation or infer the exit cause from PC alone.
2. A completely absent X1 shows only that no drawing occurred after a
   successful capture; it does not prove that no exception occurred.
3. EX and X1 appearing on the same screen do not automatically refer to the
   same process; check the PID and event context before associating them.

X1 replaces row 5 on capture, sacrificing the SYSOS amfi/cs row. EX and X1
share the try-lock, so contention can lose evidence in either direction;
`exit_dropped` is not a count of lost X1 events.

The host C replay measured 44 columns for breakpoint, 74 with all 64-bit
fields maxed at `PID_MAX`, and 79/80 columns (1,422/1,440 px at scale 3) at
the conservative `INT_MAX` PID. No exception leaves SYSOS in place. The replay
also checked missing versus zero PC, ring wrap, EX isolation, private snapshot
and lock contention. Both final kernels have a single call at
`0xfffffff00779e4e8` from `_handle_ux_exception`, after the call to
`_get_user_regs` (`0xfffffff00779e45c`) and before `_threadsignal`
(`0xfffffff00779e5a8`); no drawing caller. In the compact build, the
recorder is a leaf, with `ldaxr/stxr` at `0xfffffff0079a75b0`/`75b4`
and release `stlr` at `0xfffffff0079a75f8`. The compact linked draw audit
retained one direct `_draw` edge through the r35f IRQ/readiness gate and
six callers of that gate.

Same-source full/compact debug-strip audit matched 49,615 native non-debug
symbols and 52,674 prelink binding records. Full kernel: 55,738,368 B,
SHA-256 `53874b6745562e90c473144d0603effa52c25b5fded955112ebed336a555eeaa`.
Compact kernel: 52,023,296 B, SHA-256
`1748171b49c61937a7148f414ab07040b684de0e76b6cc9dac62dd1a9eda1c56`.

The rebuilt package at `out/nuwa-r35g-ux-package-20261121/vendor_boot.img`
has outer SHA-256
`3222523b0597e7a262a3f9f1faff0f9663a601531d05fb8d885938796c83d9ac`,
freshly rebound CHMH SHA-384
`eeb8b19c63e698769156c9f35dbecf050d83edf85c16613732a7dfb5a7993584c973fd9f43f852217bfb032dc6f611a0`,
and FAT SHA-256
`3c7b0c0a74670f2603cf6e721d4315f1e43f739916c77e95268cc74dee9be228`.
Separate audit recovered the identical FAT from the outer image. FAT scan,
FSInfo and `fsck.fat -vn` agreed on 12,054,016 B free (3,665,408 B above
the 8 MiB floor). The strict linked audit returned `ALL PASS` and the
final 49,615 non-STAB symbol tuples matched. The reused packager labels
this as `r35c-detail`; identify the r35g candidate by these hashes.

**Review:** The parent reports that `deep_reviewer` assessed plan A as
**PASS WITH CONDITIONS**; the interpretation and loss limitations above apply.
Host results are `self-checked`, not independent verification.
No device commands were run; runtime exception origin and authentication remain
unverified (authentication NOT REACHED).

## Reproduction

WSL Ubuntu-22.04 as root, from this worktree, with fresh sibling output paths:

```sh
PY=/home/wh1stl3/.local/bin/python3.11
O=/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out
X=/mnt/d/Code/PortingiOS/UniXNU/out/nuwa/ios-16.7.16-20H392/nuwa/tree/.cache/xnu-work
FULL=$O/nuwa-r35g-verifier-full
COMPACT=$O/nuwa-r35g-verifier-compact
P=$O/nuwa-r35g-verifier-package
A=$O/nuwa-r35g-verifier-audit
$PY -B scripts/test-r35g-ux-exception.py "$X/bsd/uxkern/ux_exception.c" \
    "$O/nuwa-r35f-ready-full-20261121/BootProgress.c"
$PY -B scripts/build-r35b-kernel.py "$O/nuwa-r35-20261119" "$FULL" --detail --exception
$PY -B scripts/build-r35b-kernel.py "$O/nuwa-r35-20261119" "$COMPACT" \
    --detail --exception --compact --audit-against "$FULL"
$PY -B scripts/test-r35g-ux-linked.py "$FULL/kernel.macho"
$PY -B scripts/test-r35g-ux-linked.py "$COMPACT/kernel.macho"
$PY -B scripts/test-r35e-irqguard-linked.py "$COMPACT/kernel.macho"
export NUWA_DETAIL_BUILD="$COMPACT" NUWA_DETAIL_KERNEL="$COMPACT/kernel.macho"
export NUWA_DETAIL_REFERENCE="$FULL/kernel.macho"
export NUWA_DETAIL_SHA=$(sha256sum "$NUWA_DETAIL_KERNEL" | cut -d ' ' -f 1)
export NUWA_DETAIL_BYTES=$(stat -c %s "$NUWA_DETAIL_KERNEL")
$PY -B scripts/build-ufs-apfs-root-chmh-r35b.py --output "$P"
$PY -B scripts/build-ufs-apfs-root-chmh-r35b.py --output "$A" --audit "$P"
$PY -B scripts/test-r35b-compact-package.py "$P" "$A"
```

From the UniXNU checkout, rerun the device record check. WSL needs explicit
Linux paths for the Git metadata of this Windows-created worktree:

```sh
N=/mnt/d/Code/PortingiOS/nuwa
PY=/home/wh1stl3/.local/bin/python3.11
GIT_DIR="$N/UniXNU-nuwa/.git/worktrees/worktree-r35b-packaging" \
GIT_WORK_TREE="$N/worktree-r35b-packaging" \
    "$PY" -B scripts/porting-record.py check \
    --device "$N/worktree-r35b-packaging" --base origin/diag/r35b-packaging
```
