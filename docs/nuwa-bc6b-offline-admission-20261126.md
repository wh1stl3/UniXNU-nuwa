# bc6b TWRP cannot admit the Data write transaction

**Refuse the ordinary TWRP write path; retain the `82e9634` PID 1 gate.**
Host-only static audit, self-checked. Existing RAM-only no-argument preflight
is unaffected. No device command, service stop, recovery modification, or
new writer was performed.

## Exact inputs and observed state

Rehashed the actual 104,857,600-byte recovery input `bc6b688320fe9d1b41c3294c3ec84254e8c0619ded4068d71ce024729c74f55c`.
Its header-selected ramdisk at byte 4096 (80,494,888 bytes) is identical to
the retained input, SHA-256 `b763936637df810b73fff9ccb9f67a6b52fbb34329022a314fd9f02ef65cc6b9`.
Also opened the paired stock `.44` vendor_boot by the existing UniXNU
`unixnu.vendor_boot.parse`, pinned to `493ca426964adabb195a00ded4ff49793bc7efd5d7bea2a567bcfd0c970a8dad`.
Inputs were decompressed locally, not booted. The source/inventory and
libsepol conversion of the **bundled** binary policy are local-only at
`out/bc6b-environment-audit/`. Key input fingerprints:

| Extracted input | SHA-256 |
| --- | --- |
| `sepolicy` | `07dc483ba46bbf2055a0aa44afd99f2091da317f61b13595324977583f1fb6e8` |
| `system/bin/recovery` | `cc0b8a6e684c511668541e2687ac835ccecc183e3b84c721ed80b38da0d64f56` |
| `system/bin/adbd` | `eecc5471924626bf9efb3d5fceace874e760a50d28eb933182dc1eed47b84066` |
| `system/bin/fastbootd` | `e3b172a074212e835905365d8b4a4acff9d628b1cf5617ef520d2f9b813e4ecc` |
| vendor `first_stage_ramdisk/fstab.qcom` | `13d74e9f4a33af31e644f070a1722375fce8bdb81b317e701477eee6388e4696` |

Historical recovery capture in `../UniXNU-nuwa/out/20261126-recovery-readonly/`
proves an actual root adb shell in `u:r:su:s0` (`recovery/identity.txt:1–6`)
and a configured DWC3 (`recovery/ufs-gpu-usb.txt:55–56`).
`recovery/mountinfo.txt:4,12–13,21–24,28–29` records `hidepid=invisible`,
`blkio`/cgroup2 (not an attached device-deny policy), configfs and the
three FunctionFS mounts, plus rw `/cache` and `/metadata`; the latter is
F2FS with background GC and discard. These historical mounts were not the
target partition and prove neither a userdata mount nor target writes.
`gap-audit-20261126/holders.txt` records the real `sda31` dm-0…dm-7
holders. The earlier `nuwa-data-readonly-claim-20261126-observation.md`
records 324 readable process fd/mountinfo directories, 323 namespace links
and no target/disk rdev match in the block-only fd scan. No raw per-PID
enumeration by identity, security context, thread, child, char rdev or open
flags was retained in that package; these numbers cannot attest the
complete initial namespace or all producers. The adb path itself was live.

## First unclosed producer: the root command service and its supervisor

`system/etc/init/hw/init.rc:103–125,155–165,186–213` declares root
`adbd` (root shell label `su`), property-triggered restart/start, and
on-demand `fastbootd`. `init.recovery.qcom.rc:49–50` sets the adb config
at boot. The exact adbd ELF has `ShellService`, `StartSubprocess` and
`file_sync_service`; the observed root session establishes the external
command path, not just strings in a binary. `prop.default:62,80,82` lists
`ro.adb.secure=0`, `ro.secure=0`, `ro.debuggable=1`; this is an image
configuration observation, not a new measurement of live properties.
The exact bundled policy marks `adbd`, `fastbootd`, `init`, `recovery` and
`su` permissive. It explicitly permits fastbootd write/ioctl on userdata
and dm block/control devices and gives it `sys_rawio`/`sys_admin`
(`sepolicy.conf:4822–4828,8860–8861,8908,8941`). This policy is not an
enforced storage deny. The audited rc files contain no one-shot service
that seals the supervisors and launches the reviewed writer, then
provides file-only receipt export. The shell used to stage the tool
cannot itself provide that assurance.

Other producers that must be closed, not inferred absent:

- **Recovery/UI, mount and dm** — `init.recovery.service.rc:4–6` has no
  `disabled` or `oneshot`; `init.rc:71–92` starts the default class.
  `system/etc/recovery.fstab:55–59` and vendor `fstab.qcom:82–86` admit
  metadata checks/first-stage mount and userdata late mount, crypto and
  formatting paths. The actual recovery ELF contains OpenRecoveryScript,
  dm table/snapshot and `/dev/dm-user` strings; those are entrypoint
  indicators, not proof a script or userdata dm mapping ran.
  `system/etc/init/snapuserd.rc:1–7` and `lpdumpd.rc:17–36` expose
  root storage services, initially disabled; off is not barred from start.
- **USB export** — `init.recovery.usb.rc:31–64,72–139` creates
  `mass_storage.0` and adb/MTP/fastboot FunctionFS and has rebind triggers.
  The compiled recovery names
  `/config/usb_gadget/g1/functions/mass_storage.0/lun.%d/file` and
  `mass_storage,adb`. The `none` trigger clears UDC/config links and
  stops adbd, but does not clear the mass-storage LUN backing attribute
  or attest kernel completion. Configured USB is observed; an attached
  LU0/userdata backing file is **not**. Do not use this gadget for receipts
  by exposing a backing device or general file access.
- **Raw target, parent, pass-through** — an rdev-matched direct block
  open through a different path, whole `sda` (`8:0`), or a fresh node
  remains outside pathname hiding. The ramdisk includes `sg.ko`, and
  `vendor/ueventd.rc:113–117` explicitly knows UFS BSG/GPT listener
  nodes (not proof a LU0 SG/BSG node is live). The prior scan selected
  only block rdev; no evidence shows an enforcing ban on SG/BSG/UFS admin
  open/ioctl, dm creation, or a raw parent open for the whole interval.

Stopping a service, freezing its threads, or unbinding USB is not closure:
already accepted BIO/SCSI requests, inherited fds, descendant commands,
mounted/stacked consumers, and bound kernel gadget references have separate
lifetimes. An in-place design would need a supervisor that first seals
every restart/command ingress, terminates and joins service groups, obtains
normal unmount and target-consumer teardown, detaches gadget backing files
and waits for their release, and proves all relevant submitted I/O completed
before admission. It must enforce the restrictions on all relevant device
types and controls through successful claim close. Neither waiting a fixed
time nor observing an empty fd/holders/queue snapshot acts as that barrier.
No such supervisor, teardown completion contract, or independent running
policy is present in the audited configuration. Do not replace the PID 1
check with a stopped-services or disconnected-cable check.

## Smallest alternate environment

Reuse the pinned recovery **kernel and DTB** if a separately reviewed
transient RAM launch is available; replace only the userspace launch
profile with the minimal RAM init, not another storage backend. Never
start Android init's mount/decrypt/USB/remote-command stack in the write
phase; admit only the writer in the initial namespaces after target
enumeration. The existing PID 1 binary parks on exit. A future reviewed
profile must add a strictly **post-claim-close** handoff to a fixed
file-only exporter: read exactly the two actual 3,153,920-byte RAM
readback files and one final completion receipt, no shell, adb root,
MTP, fastboot, mount, dm, SG/BSG or block access. Publish a successful
receipt only after both comparisons and successful claim close; distinguish
an incomplete export from a failed/uncertain media transaction. Do not
re-enter write mode after an interruption. This avoids importing previous
consumers and outstanding I/O instead of guessing how to drain them.
The transient launch and exporter are not yet qualified; no new boot-chain
or image was built here.
