# Retained UFS route and Data next step — 2026-11-26

Status: static source inspection and host fixtures **self-checked**. No device
command, new image, write-gate change, qualification or independent verifier.
The user selected Sheng's preserve-link/replace-queue approach and accepted its
remaining assumption risk; that is not evidence that old DMA has drained or
that FUA is durable, nor authorization to flash, reboot or write media.

## What the running candidate actually builds

The observed candidate is identified in
`nuwa-ufs-neon-20261126-observation.md`: outer SHA-256
`18fa4941696667d1813442022ea71fc48e4c414b1abadb1caf73774fcc76202a`;
the flash had no image-level readback and the screen label is not a boot nonce.
The final build r3 kernel locally hashes to
`48637103823e84726de1654c07629118d6b63021340cc88d58a8d15d62196f72`,
matching `nuwa-ufs-neon-20261126.md`; that document records the r3/r2
kernel identity. The following references are to the actual staged files under
`worktree-ufs-neon-20261126/out/nuwa-ufs-neon-20261126-build-r3/nuwa-data-provider/`.

`NativeUfs.cpp:837–858` replaces production `hostBringUp` with
`CombinedRead::run` then `hostAdoptClaimed`; the latter adopts the same
retained allocation and mapping (`:818–834`). `PreservedNop.h:76–148`
claims once, checks the existing SID 0x60 domain and controller prerequisites,
allocates its own DMA region, masks interrupts, stops both lists, replaces
UTRL base, starts the transfer list and submits a NOP. It does not restart
HCE or the link. `CombinedRead.h:150–193` then queries power, optionally
wakes, runs TUR, READ CAPACITY and LBA0 read. Subsequent root and Data reads
use the retained shared session; the screen reports successful limited reads,
not a producer-exclusion proof. No second read-only candidate is needed to
demonstrate this same selection.

## Difference from upstream production

Reference: [UniXNU/ShengUfs f020bd693c34790c04e97c52720af3cd842336fb,
NativeUfs.cpp](https://github.com/UniXNU/ShengUfs/blob/f020bd693c34790c04e97c52720af3cd842336fb/NativeUfs.cpp)
(BSD-2-Clause-Patent), `hostBringUp` lines 1212–1465. Both retain the link,
replace the queue and send NOP, power query, optional wake and TUR. The nuwa
route is an adaptation, not a byte-identical call to upstream hostBringUp:

* Upstream configures SMMU via `smmuBypassStream` after stopping the queue;
  retained checks an already existing, narrow pass-through domain and refuses
  changes rather than programming a new one.
* Upstream allocates multiple slots when possible and can enable completion
  interrupts, waits and TUR retries; retained uses slot 0, polling, bounded
  single-attempt completion and sticky quarantine on transport ambiguity.
* Upstream allows its general power/wake and retry sequence; retained accepts
  specific power values, has no general retry, and additionally checks geometry
  and reads LBA0 before adoption.
* Retained checks the domain and queue before staging and submission and
  never clears IS W1C in its command path. Neither these checks nor a zero
  doorbell establish that all earlier producers and fabric DMA are excluded.

Do not transplant upstream SMMU, multi-slot or interrupt code as an incidental
part of this decision.

## Minimum next increment and review boundary

The reviewed offline command experiment is implemented separately in
[nuwa-sb0-offline-20261126.md](nuwa-sb0-offline-20261126.md). Its positive
case is synthetic only; the remainder of this section describes the still
unimplemented production-integration boundary.

The real Data backend is already connected to the retained port:
`KernelPort.inc:28–35` and staged `NativeUfs.cpp:926–977`. Mode 2 cannot
open: `Provider<CandidatePort, false>` is hard disabled, the identity and
cold-start evidence are empty, and `fuaProvenLocked()` is false. Provider
also requires the build opt-in, explicit boot request, isolation latch, live
primary/backup GPT and placement checks. Its write path uses one page per
FUA WRITE(10), and its sync is a logical barrier predicated on proven FUA.
The observed 4 anchors and 10 of 768 metadata pages being zero do not establish
an empty overlay or permission to initialize it.

The next meaningful increment is a separately reviewed, default-off
**experimental acceptance policy**, explicitly representing assumed
producer/DMA exclusion and unproven durability as assumptions rather than
inventing `ColdStartEvidence`, `ReinitPermit`, or setting `fuaProvenLocked`
to a false claim. It must keep GPT/window bounds, attributed completions,
terminal quarantine, and the single existing transport; its exact first
media operation and behavior on nonempty/invalid metadata must be specified.
The existing host fixture already exercises a simulated writable port and
negative cases. A production-integrated policy changes the write gate and its
durability contract: stop here and send the following question to
`deep_reviewer`, rather than implement that change unreviewed.

Review request: repository `UniXNU-nuwa`, branch
`research/nuwa-ufs-owner-api-20261126`, `Provider.h::open/write/sync`,
`KernelPort.inc::CandidatePort`, `RetainedWrite.inc`, staged
`PreservedNop::run` / `CombinedRead::issue`, and the v3 overlay attach/recovery
path. With the user explicitly accepting *unproved* earlier-producer/DMA and
FUA assumptions, what minimal opt-in policy can submit bounded Data writes
without mislabeling either assumption as evidence; what ordering, power-loss,
timeout, late DMA, metadata validation, root-volume corruption and recovery
failure cases require a stop? In particular, is the overlay's FUA-dependent
sync contract acceptable as an explicitly unqualified experiment, or is an
independent durability experiment required first? No online reset or reused
old-memory zero probe is proposed.

## Binding and recovery

Bind any future reviewed candidate to exact source diff, upstream and base
revisions, staged source/build configuration, kernel and outer hashes, CHMH,
boot arguments, GPT identity, LUN, block size and precise window/reserve;
re-review after a change. Keep the experimental risk acceptance separate from
hardware facts. Full overlay validation and a backup/recovery strategy must
precede destructive initialization; sampled zeros alone are insufficient.
Recovery of the prior `vendor_boot_a` is not rollback of Data writes, and a
timeout or failed write does not prove the affected media unchanged. Existing
boot backups and the separately authorized rollback procedure remain in
`nuwa-launchd-reached-20261115.md`.

Any new flash, reboot/boot, and actual Data/media write need explicit
round-specific authorization, with unique nuwa selection and the device
gate; a boot of a write-enabled image can itself cause media writes and must
be authorized as such. Precise target range, backup/readback and recovery
limits must be agreed before the action. No authorization is implied here.

## Self-checks and reproduction

Upstream HEAD checks: ShengUfs `f020bd693c34790c04e97c52720af3cd842336fb`,
UniXNU `e7bddb9a7eecdcf81f36da9fa38bd9d4d3f155c2`,
device `4548bbd2be0d7bccc0c789ca62934842026c6384`; none merged.

From this worktree, with a C++17 compiler:

```sh
c++ -std=c++17 -Wall -Wextra -Werror -pthread -fsanitize=undefined \
  -fno-sanitize-recover=all tests/test-nuwa-data-write.cpp -o /tmp/nuwa-data-write-owner-selfcheck
/tmp/nuwa-data-write-owner-selfcheck
```

From `worktree-ufs-neon-20261126`:

```sh
python3 -B tests/test-nuwa-retained-entry.py out/nuwa-ufs-neon-20261126-build-r3 /mnt/d/Code/PortingiOS/UniXNU
```

Both ran successfully in WSL. Their writable positive cases use simulated
admission/transport and do not establish physical media writes or durability.
Independent `verifier` should rerun these on the final reviewed revision and
the final affected build/test once there is an implementation to verify.
