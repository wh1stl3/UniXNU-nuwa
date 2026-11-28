# Disposable Data initialization review model — 2026-11-26

Status: self-checked; **not a device initialization helper**. The host-only
Python model has no device open, deployment, claim, fd backend, CLI write
command, actual sync or physical readback. The model uses the existing
`prepare.bin` and `commit-sb0.bin` pinned in
`nuwa-disposable-data-20261126.md`; it is not authorization to initialize.

## Current recovery observation

Earlier this round the unique nuwa in root recovery was read using the native
Linux binary-safe collector from `d947c71`, without device writes. Live LU0
4096-byte geometry was 61,850,624 blocks; primary and backup GPT headers and
arrays passed CRC and agreement checks. `userdata` was entry 32,
`[3110976,61850619)`, `/dev/block/sda32`, `259:16`. The only Data read was
metadata `[57393401,57394171)`, 3,153,920 bytes, all zero, SHA-256
`6bdcd73dcf47f64038afbce5c14c7fb2817da9e2074a2597acb8852898e6c3d2`.
Under `9dee6fe` this is empty SB0 and the disposable open fails; it is not
already initialized or a resumable state. This says nothing about ownership
or bank contents.

Snapshot inspection found no sda/sda32 holders, matching mounts, or matching
block rdev `8:0`/`259:16` in accessible process fds; 324 process fd directories
and mountinfo files were accessible in a separate scan, 323 namespace links
readable. The scans are not atomic and do not establish exclusivity.
No device command was issued during model implementation or tests.

## Model and checks

`scripts/nuwa-data-init-review.py` validates fixed whole-device or partition
geometry, pins both artifacts, requires the entire preimage to equal the zero
prepare artifact, then models ordered prepare, sync, full readback, commit,
sync and full readback, stopping on every error or short result. Its abstract
I/O object is not a block implementation. Whole and partition offsets alias
the same absolute interval; geometry values passed to the model are not
independently obtained or proof of identity.

`python3 -B tests/test-nuwa-data-init-review.py` in WSL ran five test methods:
matching and mismatched geometry, artifact/preimage/offset refusal, successful
ordering, injected exceptions at each operation, and short reads/writes or
failed sync at each operation. Tests use only in-memory mock I/O and the
existing local artifacts. Windows `python` was unavailable; WSL Python was
used. No verifier has independently rerun these tests.

## Unclosed requirements

A usable device helper still needs an actual reviewed Linux block backend:
open and retain a single verified sda32 fd using the real kernel block claim;
derive identity and geometry from that fd, verify current dual GPT and
parent/partition alias relationship, and use bounded aligned I/O with checked
lengths. Demonstrate on the exact recovery kernel and storage stack that the
chosen direct-I/O/readback method bypasses the relevant page cache; `fsync`
plus reading cached bytes alone is not physical readback, and even direct
readback does not prove power-loss durability. Keep the claim until the
transaction ends, with errors, uncertainty or interruption stopping without
retry. The current model does not implement these requirements.

Upstream Linux v5.15 `block/bdev.c` holder arbitration is not a ban on
nonexclusive raw opens. The minimum proposed producer closure is a controlled
offline environment with a reviewed allowlist of necessary processes, no
mounts or device-mapper consumer of the target, and an enforced restriction
on opening/writing both target partition and whole-disk aliases throughout
the claim-held transaction; prove enforcement on the actual kernel, and
account for existing open fds and privileged services. A snapshot, flock, or
the block claim alone does not enforce this. Kernel, firmware and DMA
producers outside the restriction remain an explicit unresolved assumption;
do not claim absolute exclusivity.

Before any real execution: exact-source deep review of the claim/concurrency
and I/O design, a reviewed final helper and transaction protocol, independent
verifier rerun of final applicable build/tests before userdata write, explicit
round-specific authorization and disposition of old unrecoverable contents
or verified full-window preimage. Recheck unique nuwa, fixed identity, live GPT
and metadata immediately inside the claimed transaction. No device execution
is approved by this record.
