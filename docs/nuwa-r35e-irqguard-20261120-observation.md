# r35e IRQ render guard — host only

The parent reports the remaining r35d deep-review blocker: early console
callbacks can enter the 3,472-byte `_draw` frame in interrupt context;
no complete worst-case interrupt stack bound was established.

All seven direct `draw` call sites now use `draw_thread_only`, which
checks `ml_at_interrupt_context` before entering `draw`. IRQ paths keep
their existing sample/record work but skip drawing. The IRQ hook skips
`boot_progress_poll` after sampling; its thread monitor continues polling.
The bind/refresh clear operations and scanout handoff banner do not paint
in interrupt context. Thread-context monitor/continuous refresh is
unchanged. Early IRQ-only observations may not appear until a later
thread-context redraw; this is the diagnostic tradeoff.

The snapshot, full merge key, `exit_dropped`, per-slot first AKS values
and saved user-PC sampling semantics are unchanged. Existing host replay
still covers nested views, failed lock and A/B/A; the guard host replay
checks interrupt suppression and repeated thread calls. These are host
checks, not a device or framebuffer concurrency test.

The same-source full and compact kernels built successfully; the compact
kernel is 52,006,912 B with SHA-256
`9464ca7d5102de700e35afa0b36094b3cc042054daeac07ecfd2fb1eb7c8ba03`.
The full-symbol reference is 55,721,984 B, SHA-256
`1d5f4fca1d00213754778a26d448963a494c349287f24c571a14573b1f0a0dde`.
The full/compact native equivalence and prelink inventory audit is
self-checked.

On the final compact `kernel.macho`, `_draw_thread_only` allocates only
32 B. `0xfffffff0079a8394` calls `_ml_at_interrupt_context`,
`0xfffffff0079a8398` branches on zero, nonzero returns at
`0xfffffff0079a83a4`; only the zero path branches at
`0xfffffff0079a83b4` to `_draw` at `0xfffffff0079ab864`, whose
3,472 B frame is allocated at `0xfffffff0079ab864` and
`0xfffffff0079ab880`. Automated
disassembly finds six linked calls to the gate and exactly one direct
branch to `_draw`, from that gate. XNU
`osfmk/arm/machine_routines_common.c:1117–1128` defines the check as
interrupts disabled and `cpu_int_state != NULL`; no numerical IRQ stack
bound is claimed. Linked checks and branch inventory are self-checked.

The CHMH-rebound package is self-checked: outer SHA-256
`e33207c6e13d1f95ad6192f704dd01ef78beeb45ad76c41596cdc2e03a37ace1`,
FAT SHA-256 `21e426d91e0f2d9e4fdf10666a54c5e6d304f4deaffb46bd6b75ca32550e8e08`
and CHMH SHA-384
`2fc372e93029aabee9b2d5a7e0139382576e9b9518285f1fbb72be7583946e8f9afd48b714adf8f782a189d4d10236e8`.
The outer readback matches the packaged FAT; linked audit reports
`ALL PASS`. FAT scan, FSInfo and `fsck.fat -vn` agree on **12,070,400 B
free**, 3,681,792 B above 8 MiB. The 49,609 final non-STAB tuples
match the same-source full-symbol kernel. All are self-checked.

The inherited profile still says `r35c-detail` and the screen tag is
`nuwa-r35`; identify this candidate by its hashes, not those labels.
Authentication remains NOT REACHED. The final candidate needs fresh
reviewer and deep_reviewer review; independent verifier has not rerun the
build or tests. No device operation or main merge. The first full build
command reported exit 1 with no captured error; a fresh-directory
foreground rerun produced the reference above and exited 0.

## Independent rerun (WSL Ubuntu-22.04 root)

From the diagnostic worktree, use fresh sibling output paths:

```sh
PY=/home/wh1stl3/.local/bin/python3.11
O=/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out
FULL=$O/nuwa-r35e-verifier-full
COMPACT=$O/nuwa-r35e-verifier-compact
P=$O/nuwa-r35e-verifier-package
A=$O/nuwa-r35e-verifier-audit
$PY -B scripts/test-r35b-exit-detail.py "$O/nuwa-r35b-compact-r3-20261120/BootProgress.c"
$PY -B scripts/build-r35b-kernel.py "$O/nuwa-r35-20261119" "$FULL" --detail
$PY -B scripts/build-r35b-kernel.py "$O/nuwa-r35-20261119" "$COMPACT" --detail --compact --audit-against "$FULL"
$PY -B scripts/test-r35e-irqguard-linked.py "$COMPACT/kernel.macho"
export NUWA_DETAIL_BUILD="$COMPACT" NUWA_DETAIL_KERNEL="$COMPACT/kernel.macho"
export NUWA_DETAIL_SHA=9464ca7d5102de700e35afa0b36094b3cc042054daeac07ecfd2fb1eb7c8ba03
export NUWA_DETAIL_BYTES=52006912 NUWA_DETAIL_REFERENCE="$FULL/kernel.macho"
$PY -B scripts/build-ufs-apfs-root-chmh-r35b.py --output "$P"
$PY -B scripts/build-ufs-apfs-root-chmh-r35b.py --output "$A" --audit "$P"
$PY -B scripts/test-r35b-compact-package.py "$P" "$A"
```
