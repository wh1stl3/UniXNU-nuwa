# Dedicated RAM recovery PID 1 and receipt transport

**Host review payload only. No flashable recovery, no device action.**
`2813aca`'s ordinary-TWRP write refusal stands. The `.44` boot and
vendor_boot artifacts are preserved; no `fastboot boot` or vendor rebuild.

## Bound inputs and unresolved entrypoint

The historical normal recovery transition was authorized
`fastboot reboot recovery` in slot a after `.44` boot/vendor and independent
`bc6b` recovery writes. It reached TWRP root adb, but did not read back boot
partitions or identify which ramdisk supplied the first exec; see
`nuwa-disposable-data-20261126-observation.md`. Host parsing now pins:

| Local input | Finding |
| --- | --- |
| `.44` `boot.img` `594ff64b…` | v4, kernel 44,689,920 B, no generic ramdisk. Embedded IKCONFIG and the historical `5.15.215-KylinKernel-260925-Release` literal match the investigated route; this is not a live partition hash. |
| `.44` `vendor_boot.img` `493ca426…` | One type-1 (platform) ramdisk fragment (not type-2 recovery); no `/init`; contains `/lib/modules`, platform and first-stage material. Reused UniXNU `unixnu.vendor_boot.parse` (`693f5d9cae8a408dd18b39f3f9fdc4228c934241`). |
| `.44` `init_boot.img` `4da48a59…` | Local generic ramdisk contains a regular executable `/init`, SHA-256 `af850a61510b…`; its active slot contents and participation in recovery were not measured. |
| `.44` `dtbo.img` `c5dd80b3…` | Local DTBO table has 57 entries; audit records each id/rev/custom/hash, not the ABL-chosen index or active slot contents. Existing live recovery FDT shows Qualcomm UFS, DWC3 and key nodes, but does not establish an overlay index or source. |
| `bc6b…` recovery | Kernel size 0; 80,494,888 B recovery ramdisk with `/init -> /system/bin/init`; empty boot header command line; original AVB footer. Actual effective command line showed `init=/init`, not `rdinit=`. |

**Deep-review question:** with the existing `.44` `boot_a`/`vendor_boot_a`
and independent `recovery_a` normal entry, what does this ABL select for
`init_boot_a` and DTBO, in what order are the CPIO archives unpacked, and
will an authenticated/accepted replacement recovery supply an effective
unique `rdinit=/nuwa-recovery-init` rather than fall through to Android init?
The candidate fragment provides both `/nuwa-recovery-init` and `/init`, but
an overwritten `/init`, ignored recovery header cmdline, or AVB rejection
would invalidate that binding. No invented precedence or copied stale
authentication metadata; no `.img` is emitted.

**Second concrete blocker:** exact `.44` IKCONFIG has no built-in
`SCSI_UFS_QCOM`, no `DEVTMPFS`; `ufshcd-qcom` actually bound historically.
The pinned vendor fragment supplies `ufs_qcom.ko`, the Kalama PHY provider,
`dwc3-msm.ko`, and `pm8941-pwrkey.ko`; the audit resolves the 25-entry hard
dependency set. A hard dependency graph is not a safe load plan: it does
not prove provider/DT/firmware closure, early init callbacks, or absence of
storage I/O. Do not load the complete Android module list. PID 1 creates
private nodes but intentionally does not preload an unreviewed module set;
it stops on missing topology, keys or UDC. Obtain an exact minimal module
order/firmware path and audit its init effects before image binding.

The historical command line contains
`block2mtd.block2mtd=/dev/block/sda16,2097152` and `mtdoops.dump_oops=0`;
exact `.44` IKCONFIG has `CONFIG_MTD` disabled, so these strings are not
evidence of an active MTD producer in that kernel. `PSTORE_RAM=y` and
`PSTORE_BLK` disabled establish the compiled options, not all vendor
producers. `DM_INIT=y`, with no `dm-mod.create=` in the captured command
line. Linux UFS/partition discovery itself reads capacity and partition
tables; if “no reads outside userdata” includes kernel/ABL discovery and
boot inputs, the `.44` route cannot meet that literal condition. The
adapter starts no userspace reads of other partitions, no non-RAM mounts,
no service and no other media writer. Early producer closure remains
required for a production admission decision.

## One-shot confirmation and export

- The default **CHECK** build compiles out the media-write backend. It
  accepts only the exact blank window or the exact initial SB0 with the
  rest zero, returning `CHECK-BLANK`/`CHECK-SB0`; no normal boot auto-initializes
  or repairs. An evolved Data state is out of scope. Use this profile for
  initial launch qualification and later dedicated read-only rescue.
- The separately compiled **WRITE review** build takes no runtime command.
  It requires RAM root, unique expected root PID 1, offline gate and a
  blank read-only preflight. After entering confirmation, both keys must
  initially be up, then an exact physical down/up/down **press-release**
  sequence is required within 60 seconds. Devices map from `pmic_resin`
  and `gpio-keys`; live FDT assigns `0x72` and `0x73`. Held, wrong, repeated
  or dropped events stop. It then reruns whole admission and blank preimage
  under the write transaction. No USB connection is required or accepted
  by the offline gate; no on-boot retry. A visible readiness channel for
  that physical prompt and the evdev path are not yet hardware-qualified.
- `run(true)` returns only after both actual target rereads match and
  the target claim closes successfully. Only then mount configfs/
  FunctionFS and present one vendor-specific bulk **IN** endpoint.
  No data-OUT endpoint, shell, ADB, fastboot, MTP, mass-storage, or USB
  request dispatcher. Emit two exact 3,153,920-byte RAM readback files and
  `FINAL <run-id> CLAIM-CLOSED`. A timeout, malformed input, bad media
  readback, ambiguous close or incomplete transfer cannot yield a
  successful host receipt. Export failure is distinct from media failure;
  absent a final receipt the host cannot infer which occurred. The demo
  gadget VID/PID are Linux's composite test identifiers, not production
  identities; run ID and single-device topology must also match. USB
  hardware and receiving dependencies (`PyUSB`/libusb) were not exercised.
- Reserve the unique first-init journal on a host Linux filesystem before
  any future physical confirmation; preserve it even if no receipt arrives.
  The receiver durably marks its one attempt before USB configuration,
  verifies run ID, mode and both payloads, then commits the final receipt
  last. Neither device PID 1 nor receiver replays a transaction. Host
  journal is **operator enforcement**, not a persistent device marker:
  after an uncertain attempt with a blank preimage, a reboot and manual
  re-confirmation cannot be distinguished by on-device state. Do not
  re-confirm or reserve a second ID for that target. A successful SB0 is
  separately rejected by the write-mode blank gate on reentry.

## Review bundle and future device operations

`out/nuwa-ram-recovery-review-r3/` contains two static AArch64 executables,
`UNBOUND-pid1-fragment.cpio.lz4` fragments, original backend rerun inputs,
and audits. ELF and fragment SHA-256:

| Profile | ELF | LZ4 CPIO |
| --- | --- | --- |
| CHECK | `d42df26f294e6cae8a45c8fea6f9b3a83d99a28c231a15a460e7e1d8e24510b5` | `d04d90f50374b728e5ec9b8f04d4fadc884d071c06bd5597a6c86064304a4a8c` |
| WRITE review | `8abbbfeee3c2b9d349ca023247350a86b4398869b9b81afea5f42efde5fdc31f` | `f867375ba9059dad89c91e7832da035227415954723112ae77ad1aaba51c7942` |

Rebuild from the worktree in WSL with the common arguments to
`scripts/build-nuwa-ufs-ram-recovery.py`:
`--stock ../out/nuwa44-recovery-original --bc6b <exact bc6b source>
--unixnu ../../UniXNU --observed-cmdline ../UniXNU-nuwa/out/20261126-recovery-readonly/recovery/cmdline.txt
--gpt ../UniXNU-nuwa/out/20261126-recovery-readonly/recovery/gpt-v2
--init out/nuwa-disposable-data-init --package out/nuwa-disposable-data-package-r2`.
Use fresh outputs, `--run-id 99990000aaaabbbbccccddddeeeeffff` for CHECK and
`--run-id 11112222333344445555666677778888 --arm-for-review` for WRITE review.
Run `tests/test-nuwa-ufs-ram-recovery.py --check <check> --armed <armed>
--sb0 out/nuwa-disposable-data-init/commit-sb0.bin`, then rebuild and rerun
the original backend commands in `nuwa-ufs-data-init-backend-20261126.md`.
Four new tests and six original direct-file tests self-checked; original
recovery CLI SHA-256 unchanged (`f059f027…`). Framer/journal executed
natively against exact artifacts; no cross-boot, input or USB runtime test.

**No device action now.** If binding and early-producer review close, the
first separate authorized device action should be **CHECK only**: confirm
unique nuwa and slot a, replace only `recovery_a` with the exact reviewed
CHECK image, enter ordinary recovery, and receive `CHECK-*`. Do not touch
`boot_a`/`vendor_boot_a`/`init_boot_a`/DTBO or another partition. A first
WRITE candidate requires separate exact-image review and authorization,
independent verifier, a final blank preimage and rollback disposition.
Save the 104,857,600-byte original `bc6b688320fe9d1b41c3294c3ec84254e8c0619ded4068d71ce024729c74f55c`
as the `recovery_a` rollback input; separately authorized restore affects
recovery only, not Data. Reuse CHECK or restore bc6b after initial
qualification, not the armed profile. Normal TWRP remains outside the
safe Data-write (and strict dedicated read-only rescue) contract.
