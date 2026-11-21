# r35c exit detail — host only

Baseline: compact r35b kernel SHA-256
`6262a25ab2211c8010a105d9456cdf46d38832c5edf3667f2b09a8262639deb8`,
vendor boot `56e78d27d48e6368cd3f96fa2993bfcba44bea8684d9a6dbc87355dcfd198dbd`,
FAT free 12,070,400 B. No device action.

The four slots key on the full XNU `p_name` (32 bytes plus NUL),
signal, 32-bit namespace and 64-bit reason code. Display uses six name
characters and the low 32 bits of the code; count saturates at `UINT_MAX`.
Existing exit lock failure increments `exit_dropped` before filtering;
the per-slot count is separate. Repeated keys do not reorder the slots.
The four screen rows are 0, 2, 3 and 4; row 1 counters remain, at the
cost of overwriting the title and the existing UFS/PID1 detail rows when
four exits are present. Snapshot copies are taken under the existing lock.

When `proc_selfpid()` equals the exit PID, `get_user_regs(current_thread())`
provides the current thread's `machine.upcb` (ARM64 `status.c:1672–1675`);
`get_saved_state_pc` reads its PC as in XNU `backtrace.c:453–460`. A null
saved state or a different current PID displays dashes. This is a saved
exit-thread user PC, not necessarily the faulting thread or faulting PC;
`proc_prepareexit` also has external termination callers. No LR or slide
is claimed.

Host C replay of the generated function self-checked 200 `exit(1)` calls,
two 200-event signal storms, same-prefix distinct names, distinct upper
32 bits of reason code, distinct namespaces, count saturation and one
pre-filter lock drop. Maximum formatted row is 79 columns at the recorded
1440-pixel / scale-3 capacity of 80 columns. No concurrency execution or
framebuffer rendering was tested.

Reviewer and deep_reviewer of the new candidate are pending; the old
candidate's review does not cover this change. No independent verifier
has rerun the final build or tests. Authentication remains NOT REACHED.

The full-symbol reference kernel built with the original r35 entry and
the generated r35c source is 55,721,984 B, SHA-256
`cadafd25cf2bd5d222096e5d29b0076e506c96a2dde61e9082b7e85c12db2900`
(self-checked). It is the reference for the new compact audit, not the
old r35b kernel.

The compact kernel is 52,006,912 B, SHA-256
`36e4a5bf18e0917fb81e5149a4a171906e606cdd9a3b56847fae61729f30474b`.
The existing native strip audit compared this candidate to the
same-source full-symbol build: 128,829 STABS removed, 49,610 non-debug
symbols and all 52,674 prelink bindings preserved (self-checked).

Package build and separate outer readback audit are self-checked:
vendor boot SHA-256
`37ebfbed30046bdaf3077ad278ae9716e582905947374e7e7e346c536fcd0734`,
FAT SHA-256 `90fd8602034c6351b42b3c31a8f861bf40ebd5245c9b82e23cded098fc9c5df1`,
ADT SHA-256 `c1d1d5b2c12e186a1ce8d6039bf38cf42e7ef6963aacaf6e90d7f68619edcb2c`,
and new kernel-bound CHMH SHA-384
`a2a63d57d618553ee89e986d820c36fbc329c88d7d5ff8850208d4fe56a5303c382ef030f1990b082d441a583bfa2010`.
The strict linked audit reports `ALL PASS`; the final 49,610 non-STAB
symbol tuples match the same-source full-symbol kernel. FAT scan, FSInfo
and `fsck.fat -vn` agree: 12,070,400 B free, 3,681,792 B above the
8,388,608 B floor and unchanged from the compact r35b baseline. The
outer readback FAT hash matches the packaged FAT (all self-checked).

## Reproduction (WSL Ubuntu-22.04 root, diagnostic worktree)

```sh
PY=/home/wh1stl3/.local/bin/python3.11
O=/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out
R=$O/nuwa-r35-20261119
FULL=$O/nuwa-r35c-detail-verifier-full
COMPACT=$O/nuwa-r35c-detail-verifier-compact
P=$O/nuwa-r35c-detail-verifier-package
A=$O/nuwa-r35c-detail-verifier-audit
$PY -B scripts/test-r35b-exit-detail.py "$O/nuwa-r35b-compact-r3-20261120/BootProgress.c"
# Choose four fresh sibling directories; do not overwrite the self-check outputs:
$PY -B scripts/build-r35b-kernel.py "$R" "$FULL" --detail
$PY -B scripts/build-r35b-kernel.py "$R" "$COMPACT" --detail --compact --audit-against "$FULL"
export NUWA_DETAIL_BUILD="$COMPACT" NUWA_DETAIL_KERNEL="$COMPACT/kernel.macho"
export NUWA_DETAIL_SHA=36e4a5bf18e0917fb81e5149a4a171906e606cdd9a3b56847fae61729f30474b
export NUWA_DETAIL_BYTES=52006912 NUWA_DETAIL_REFERENCE="$FULL/kernel.macho"
$PY -B scripts/build-ufs-apfs-root-chmh-r35b.py --output "$P"
$PY -B scripts/build-ufs-apfs-root-chmh-r35b.py --output "$A" --audit "$P"
$PY -B scripts/test-r35b-compact-package.py "$P" "$A"
```
