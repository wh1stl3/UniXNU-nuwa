# r35f: bootstrap readiness before diagnostic rendering

The parent reports r35e showed only the top three color bands, no text
and no enumeration. The offline failure mechanism is that `arm_init`
calls `boot_progress_init()` immediately after `PE_init_platform(FALSE, args)`;
its stage recorder can request drawing before the bootstrap thread is
installed. With IRQs masked, XNU's `ml_at_interrupt_context()` reaches
`getCpuDatap()` and expects valid current-thread state. This is not an
on-device fault-PC attribution.

The pinned, previously linked `arm_init.c` input (SHA-256
`a9931973da35aa0eaa50079ba1e011a02fad843e2c211648b284f313c2db28a4`)
assigns `thread->machine.CpuDatap = &BootCpuData`, calls
`machine_set_current_thread(thread)`, and sets `preemption_count = 0`.
The new hook is immediately after those operations, before
`cpu_bootstrap()`. It publishes a release-store only; it does not
render. The already-initialized `BootCpuData` is accessible through the
installed current thread at this point; no dependency on the monitor or
on a later console bind. Subsequent existing stage and bind events can
draw normally. In the generated `arm_init.c`, line 359 initializes
`BootCpuData`, line 367 records the early init stage, lines 457–459
install the CPU pointer and thread, and line 468 publishes readiness.
XNU `osfmk/arm/cpu_data.h:123` defines `getCpuDatap()` through
`current_thread()->machine.CpuDatap`.

Before publication the common drawing predicate returns without
calling `ml_at_interrupt_context()`. Early console/stage events still
record; bind records geometry but does not clear/paint; refresh and
scanout drawing are excluded. After publication the same predicate
rejects IRQ rendering and leaves the thread monitor/continuous path
available. The EX snapshot, full merge key, `exit_dropped`, first-sample
AKS and saved exit-thread user-PC semantics are unchanged.

Host replay is self-checked. The actual generated gate was also built
into a small freestanding AArch64 ELF and run under QEMU `virt`:
null `TPIDR_EL1` before publication makes zero mock `ml` or draw calls;
an installed synthetic thread and CpuDatap permit the IRQ check, which
rejects IRQ and allows thread drawing. This emulates the gate, not the
full nuwa kernel, console or firmware.

### Linked control flow and build

On the compact final kernel, `arm_init` calls early diagnostics at
`0xfffffff0079c46b0`; `thread_bootstrap` at `0xfffffff0079c47b0`,
stores the CPU pointer at `0xfffffff0079c47b8`, installs the current
thread at `0xfffffff0079c47bc`, and publishes readiness at
`0xfffffff0079c47c4` before `cpu_bootstrap` at `0xfffffff0079c47c8`.
`machine_set_current_thread` writes `TPIDR_EL1` at `0xfffffff0073fe70c`.
In the gate, `ldar` at `0xfffffff0079a83fc` and `cbz` at
`0xfffffff0079a8400` precede the `ml` call at `0xfffffff0079a8408`.
The not-ready and ready-IRQ paths return at `0xfffffff0079a8418`.
The only direct edge to `_draw` in the image is the ready-thread branch
at `0xfffffff0079a8428`; `_draw` allocates 96 + 3,376 B at
`0xfffffff0079ab8e4` and `0xfffffff0079ab900`. Six linked gate call sites
were observed in both full and compact (self-checked).

Same-source full (55,721,984 B) and compact (52,006,912 B) builds passed
the existing native/debug-strip equivalence and prelink audit:
49,611 non-debug symbols and 52,674 binding records matched. The first
compact attempt reached its 120 s command timeout; a fresh output path
with a larger time budget completed. Full kernel SHA-256:
`9a9fcd238ffcdb4aaf8ec28bc9ad2a3400877d14d55968d5074554789acc9cfe`.
Compact kernel SHA-256:
`459b4a49db3a81258d5a5c937b125e1677b85affbd98d0ccb598637e69254e5a`.

### Package and release boundary

Local package: `out/nuwa-r35f-ready-package-20261121/vendor_boot.img`.
Outer SHA-256
`46527f4d1b56a883592a360f18e6952aa584db53e7aa09d4456c002afaca7c6b`;
freshly rebound CHMH SHA-384
`668509e5c9c627265cc45d101424afb914981668bd5375c8e618759b4e4162279a6e738cfdde9162da884e069084caea`.
FAT SHA-256
`7dd138c5af6d21004acdf050e35d401a4ffdc7d7e5edc7f442b6a1badaed5d5d`.
Outer readback matches the packaged FAT, and FAT scan/FSInfo/`fsck.fat -vn`
agree on 12,070,400 B free, 3,681,792 B above the 8 MiB floor. Existing
linked audit reports `ALL PASS`; all 49,611 final non-STAB tuples matched
the same-source full build. These are self-checks. The inherited package
profile remains `r35c-detail` and the screen tag `nuwa-r35`; use hashes
for candidate identity.

Reviewer/deep_reviewer must re-review the final candidate. No device
operation, main merge or independent verifier rerun in this round.
Authentication remains NOT REACHED.

### Reproduction (WSL Ubuntu-22.04 root)

From the diagnostic worktree, with fresh sibling output directories:

```sh
PY=/home/wh1stl3/.local/bin/python3.11
O=/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out
FULL=$O/nuwa-r35f-verifier-full
COMPACT=$O/nuwa-r35f-verifier-compact
P=$O/nuwa-r35f-verifier-package
A=$O/nuwa-r35f-verifier-audit
$PY -B scripts/test-r35b-exit-detail.py "$O/nuwa-r35b-compact-r3-20261120/BootProgress.c" --qemu
$PY -B scripts/build-r35b-kernel.py "$O/nuwa-r35-20261119" "$FULL" --detail
$PY -B scripts/build-r35b-kernel.py "$O/nuwa-r35-20261119" "$COMPACT" --detail --compact --audit-against "$FULL"
$PY -B scripts/test-r35e-irqguard-linked.py "$COMPACT/kernel.macho"
export NUWA_DETAIL_BUILD="$COMPACT" NUWA_DETAIL_KERNEL="$COMPACT/kernel.macho"
export NUWA_DETAIL_SHA=459b4a49db3a81258d5a5c937b125e1677b85affbd98d0ccb598637e69254e5a
export NUWA_DETAIL_BYTES=52006912 NUWA_DETAIL_REFERENCE="$FULL/kernel.macho"
$PY -B scripts/build-ufs-apfs-root-chmh-r35b.py --output "$P"
$PY -B scripts/build-ufs-apfs-root-chmh-r35b.py --output "$A" --audit "$P"
$PY -B scripts/test-r35b-compact-package.py "$P" "$A"
```
