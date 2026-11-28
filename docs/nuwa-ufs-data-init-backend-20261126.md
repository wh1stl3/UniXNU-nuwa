# nuwa offline Data initializer — standalone backend

**Host self-checked; no device command, deployment, write authorization, or
production Provider change.** This is the Linux backend follow-up to `331ea5e`,
not a new TWRP/recovery image. Ordinary TWRP is suitable only for read-only
preflight. Its observed configured DWC3, recovery tasks and Android device
mappings do not satisfy the write gate.

## Transaction and identity

- No paths, range, LBA, or payload supplied at runtime. No argument is read-only;
  `--authorize-nuwa-blank-data-init` selects write mode, not authorization by
  itself. `/dev/block/sda32` must be the actual block node `259:16` (not a
  symlink); any existing `by-name/userdata` must identify the same rdev, and
  that alias is required in ordinary read-only recovery.
- sysfs ties `259:16` to partition 32 and parent `8:0`, Qualcomm
  `1d84000.ufshc`, SCSI `0:0:0:0`, observed KIOXIA vendor/model/revision.
  Size/start must match sysfs's 512-byte units. Each actual opened block fd
  must independently report 4096 via `BLKSSZGET` and the exact capacity via
  `BLKGETSIZE64` (61,850,624 blocks for LU0, 58,739,643 for userdata).
  A missing or changed fact stops, including a kernel with other devnums.
- Open and retain **one** target `O_EXCL|O_DIRECT` fd (default `O_RDONLY`, only
  explicit mode `O_RDWR`). While held, open the parent **read-only** with
  `O_DIRECT` and compare four full blocks at LBAs 1, 2, 61850623 and 61850619
  with the exact captured GPT windows. Build-time admission proves the pinned
  headers/arrays have valid CRCs, agree and identify userdata as entry 32,
  `[3110976,61850619)`. Runtime equality verifies those same bytes including
  the disk and partition GUIDs, not just the name and extent. Close the parent
  before any transaction; it is not a write target.
- Build verifies SHA-256 of existing `prepare.bin` and `commit-sb0.bin`; only
  the all-zero 770-page pattern and the pinned 4096-byte SB0 are compiled in.
  SHA-check existing outer/FAT and extract and check the actual packed seed
  (FAT readback also equals the pinned outer slice). SB0 embeds that seed's
  previously audited logical identity. No filesystem seed is used for device
  I/O; this binds the reviewed input pair, not the runtime identity of a
  different or subsequently booted outer.
- With the original target fd, pread all 770 pages at userdata byte
  `222340812800` (LU0 `[57393401,57394171)` in 4K units); require every byte
  zero. Write exactly 770 pages of zero, `fsync`, then pread and compare all
  770. Write exactly one SB0 at the same start, `fsync`, then separately pread
  and compare all 770 again. Each positioned call uses a 64 KiB-aligned buffer
  and requires an exact result. No application-level retry, buffered fallback,
  implicit repair, bank write, erase, GPT write, or rollback.
- Actual returned buffers are saved as `prepare-readback.bin` and
  `commit-readback.bin` in a fresh `/tmp/nuwa-data-init-receipts` RAM directory.
  An I/O, sync, receipt, or compare failure stops. An error after a write
  attempt does not mean that zero bytes changed. A short/failed prepare,
  receipt or prepare check cannot fall through to SB0. There is no automatic
  resume; a failed or interrupted run needs disposition, even if a new run
  would still see all-zero metadata. Only the final completion line after
  successful checks and claim close is a success receipt.

## Exclusion and deployment boundary

`O_EXCL` is Linux block holder arbitration, **not** a prohibition on
nonexclusive raw opens of `sda32`, an alias with the same rdev, overlapping
whole-disk `sda`/`8:0` or SCSI pass-through. A proc/holders snapshot from
running TWRP is not enough. The executable instead refuses write unless it
is the sole userspace PID 1 in the reviewed RAM-only boot environment.
The gate checks PID/proc view, root/proc/sys FS types, all visible other
processes for kernel-thread-only status, RAM/pseudo-filesystem mounts, no
swap, disconnected DWC3, only inherited console stdio (null stdin also
allowed), and empty partition and parent holder sets while claimed. The
mount allowlist rejects device-backed mounts, including dm devices; the
inherited fd allowlist excludes block/whole-disk aliases by **type**, as well
as sg/bsg/BSG controller nodes, dm-control, sockets and async-I/O handles.
It creates no child and starts no services. A missing/unreadable evidence
surface or an unexpected task/mount/fd is a refusal, not a warning.

The launch contract still requires a **reviewed RAM-only recovery in the
initial PID, mount and user namespaces**, fresh proc/sys/dev mounts, no
background service ever started, no outstanding async work/privileged raw
handles, no network or USB mass-storage export (disable the gadget; keep USB
disconnected during the write), no Android/recovery mount or automount,
vold, TWRP UI, adbd, fastbootd, update/backup jobs, dm/loop consumer or other
storage producer. Do not use a nested PID/mount namespace, `unshare`, chroot,
or a filtered proc view to make existing tasks disappear. The helper cannot
prove the initial-namespace and launch-history contract from an arbitrary
root shell, or rule out kernel, firmware, DMA or external producers.
`O_DIRECT` requests page-cache-bypassing block I/O; `fsync` requests the
kernel's flush semantics. Exact nuwa kernel behavior is unobserved; neither
matching direct readback nor `fsync` certifies hardware power-loss durability.
Device/SCSI internal retries are not controlled by this userspace program.

For a separately authorized **read-only** run: identify exactly one nuwa and
fix its serial, verify `/tmp` is RAM (`stat -f` and mountinfo), transfer only
the exact AArch64 ELF to `/tmp` using `adb -s <serial> push`, confirm its
SHA-256 there, set executable permissions in RAM, then invoke it without
arguments in the root recovery shell. Do not stage on `/data`, `/metadata`,
or a persistent mount.

For a future **write** run, a separate, reviewed transient RAM boot must
set up the RAM root, proc/sys/dev mounts, block nodes under `/dev/block`,
`/tmp`, and console, then `exec` this exact helper as PID 1 with the exact
write option **only after** round-specific authorization, rollback disposition,
deep review, and independent verifier. The helper releases any target claim
then parks PID 1 rather than panicking or restarting. No such launch profile
or post-transaction RAM receipt export is verified or supplied by this
increment; do not substitute ordinary TWRP or reboot expecting to retain RAM
receipts. The known TWRP cannot execute the write path as delivered.

## Reproduce and review

From the `research/nuwa-ufs-owner-api-20261126` worktree in WSL (fresh `o`):

```sh
g=../UniXNU-nuwa/out/20261126-recovery-readonly/recovery/gpt-v2
i=out/nuwa-disposable-data-init
o=out/nuwa-ufs-data-init-review-r3
python3 -B scripts/build-nuwa-ufs-data-init.py --init "$i" --gpt "$g" \
    --package out/nuwa-disposable-data-package-r2 --output "$o"
python3 -B tests/test-nuwa-ufs-data-init.py --built "$o" --gpt "$g" \
    --sb0 "$i/commit-sb0.bin"
readelf -h -l -d -n "$o/nuwa-data-init"
```

Review bundle: `out/nuwa-ufs-data-init-review-r3/`. ELF is 754,056 bytes;
SHA-256 `f059f027ae6bfd989139705adb96835a5f30ae229aa1e73ac605136228357ce7`;
GNU build ID `c1cf1acb553407d6b58ba80e5d745ab0f2718b21`. Static
AArch64 Linux/glibc executable, no interpreter or dynamic section, 64 KiB
ELF segment alignment; no Bionic dependency. Ubuntu cross GCC 11.4.0,
arm64 glibc sysroot 2.35, binutils 2.38. Linux AArch64 ABI checked
statically, not executed on recovery. Sources and generated pin hashes are
in the bundle. Upstream UniXNU HEAD before/after `e7bddb9a7eecdcf81f36da9fa38bd9d4d3f155c2`,
not adopted.

Six native tests used actual Linux `O_DIRECT` on temporary sparse regular
files at the exact offsets, with syscall traces, unchanged neighboring
sentinels, two matched receipts, nonblank reentry refusal, wrong primary and
backup GPT refusal, short preimage from actual EOF, and one-shot strace
injection for short/error writes, flush errors and readback errors. A
separate host build of the production CLI rejects free LBAs and write outside
PID 1 before opening a block device. Files do not exercise the real block
holder, recovery namespaces/SELinux device admission, or controller flush.
The fixture entry is not compiled into the AArch64 recovery ELF.
