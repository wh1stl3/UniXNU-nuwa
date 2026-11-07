# Step 5 platform inputs: reviewed facts

Reviewed on 2026-11-07 from an independent review of the archived platform observations. This
file records conclusions only. The platform facts below have no host or device verification: no
firmware was executed and no device was touched for them, so every porting area stays `planned`
until real evidence exists. The exception is "Reproducing the firmware build", which records a
build that the Verifier subagent independently re-ran; that is host build evidence only, not
device evidence, and it closes no area.

## Revisions in scope

| Tree | Revision |
| --- | --- |
| UniXNU base (contains the local iOS 16 profile) | `693f5d9cae8a408dd18b39f3f9fdc4228c934241` |
| This device repository | `279c990a0c7a238aa0a5818493c6cd6a46528749` |
| This device repository (Verifier re-run) | `b1064eb85151ad6200bd16644f115704f5fac33c` |
| SM8550 common | `a9f45dc60c035084b95463781538380f4c3606c9` |
| uefi-nuwa | `322d742fd87d370aac96bb394d1feac61beb9b3a` |
| uefi-nuwa (DSC/FDF integration, built here) | `becd65b921553957899cc069d6ac6c1278dedd08` |
| uefi-nuwa (Advanced Logger producer wiring, built here) | `e494c01b2f679439fdaeaf2084b693c7220543f5` |
| Mu_Basecore edk2 (archive) | `cfb93724a06ff86ff5ba971413368a7809ee42a5` |
| openssl (archive) | `67b5686b4419b4cb8caa502711c41815f5279751` |
| Common/Mu | `b8d46c71` |
| Common/Mu_OEM_Sample | `b70b4b7b` |
| Silicium-ACPI | `2d465ad7` |

The last five rows are the hand-staged build inputs listed under "Reproducing the firmware
build"; the Common/Mu, Common/Mu_OEM_Sample and Silicium-ACPI pins are quoted short because that
is how they were supplied.

Firmware changes after `322d742f` were not reviewed as platform facts; `becd65b9` and `e494c01b`
are only the revisions that were built.

## CPU topology

The live MPIDR Affinity1 values are `0x000..0x700` for the eight cores, and the cluster mix is
3x A510, 2x A715, 2x A710 and 1x X3. Both agree with the board tree; `[payload.adt] cpu_regs =
"0,256,512,768,1024,1280,1536,1792"` already encodes that numbering, so no CPU value changes.

## GIC

`GICD 0x17100000 + 0x10000` and `GICR 0x17180000 + 0x200000` with an `0x40000` stride match the
live machine. The 3-cell versus 4-cell interrupt encoding difference is a legal encoding
difference: ArmCpu's `mapGic` does not read `interrupt-cells`, so neither the addresses nor the
interrupt encoding change.

## Timer

The live PPI set is 13, 14, 11, 12 against the DTB's 13, 14, 11, 10. Only the fourth entry
differs, and it is an EL2 interrupt, so the two are not equivalent; the current path is EL1 only,
and ArmCpu's `CNTV_CTL` handling (INTID 27, PPI 11) does not consume the fourth entry. The IRQ
table therefore stays unchanged. The 19.2 MHz reference frequency comes from a live property,
not from a `CNTFRQ` read-back, so no CNTFRQ value is asserted here.

## Memory High gate

The board DTS geometry `0x8c0000000 + 0x240000000` describes a 9 GiB range, and the live high
end shows two adjacent ranges that support it. Still open:

- the last 4 KiB, `0xafffff000-0xb00000000`;
- the internal and dynamic reservations inside the range.

Two firmware windows overlap historical reservations:

- the current FD window `0xa7100000-0xa7400000` falls inside the historical ramoops
  `0xa7000000-0xa7400000`;
- the DXE heap `0xbae00000-0xbf300000` intersects the historical `iomem` reserved region
  `0xbe000000-0xd4c00000`, and the currently active owner of that region is unknown.

Consequences recorded, not acted on:

- `board.toml` address, size and verified values stay unchanged;
- permanent Linux `reserved` ownership is not inferred, and a full SystemRAM handoff is not
  inferred either;
- the delivered conventional window comes from RAM Partition -> HOB/EFI map -> DarwinBoot
  conventional allocation, not from an automatic ADT subtraction of reserved ranges;
- the XNU handoff stays withheld until the reservation owner question closes.

## DRAM range shape

`scripts/unixnu/devicetree.py` accepts exactly one `/memory` node with exactly one `reg` range
for the ADT handoff. The earlier "replace the nine `reg` entries with the live FDT entries" TODO
was therefore wrong and is corrected in `dts/nuwa.dts` as a comment-only change. The contiguous
geometry and the owned-window contract stay as they are: no numeric or structural change.

## DarwinBoot window allocation (static reading)

Static code reading by the main agent, not verified on hardware. Nothing in this section was
executed on a device, and no firmware was run for it.

1. Window contract. `DarwinBootPkg/Driver/WindowSize.h:6-8` requires the window address to lie in
   `0x10000000..0x200000000` and to be 2 MiB aligned; `owned_memory_size = 0x40000000` (1 GiB)
   satisfies both. The `WINDOW_SIZE` default of 256 MiB at `DarwinBoot.c:20` is only the parse
   upper bound.
2. Allocation path. `AllocateWindow` (`DarwinBoot.c:495-546`) searches only contiguous
   `EfiConventionalMemory`. If no such range fits, it takes the NO WINDOW branch
   (`DarwinBoot.c:531-544`) and prints the NO WINDOW/FREE lines on screen.
3. `boot_args`. `DarwinBoot.c:745-748` sets `boot_args` `PhysicalBase` to the window address and
   `MemorySize` to `WindowSize`, so XNU's physical memory range comes from `boot_args`, not from
   the ADT.
4. Conventional supply today. The nuwa `MemoryMapLib` static table (`uefi-nuwa`
   `Platforms/Xiaomi/nuwaPkg/Library/MemoryMapLib/MemoryMapLib.c:9-35`) has one Conventional entry
   that also produces a HOB: the DXE heap `0xBAE00000+0x4500000` (about 69 MiB). There is no high
   DDR above `0x8c0000000` in that table.
5. How high memory is added. `RamManager.c:48-113` maps gaps of the RAM range that the existing
   EFI map does not cover as `EfiConventionalMemory` with no address or size filter; `ManageRam`
   (`:187-215`) cleans up directly when the RAM range lookup fails; the depex is `TRUE`
   (`RamManagerDxe.inf:26-27`); and `QcomPkg.dsc.inc:30` overrides `RamManagerLib` with
   `QcomPkg/Library/RamManagerLib`, whose `RamManager.c:57` returns an error when
   `LocateProtocol(gEfiRamPartitionProtocolGuid)` fails.
6. Producer unconfirmed. In the nuwa vendor `Binaries/nuwa` `.efi` files the protocol bytes appear
   once each in `EnvDxe.efi` and `QcomBds.efi`, neither in a depex, and the producer is
   unconfirmed. If the protocol is not installed when `RamManagerDxe` runs, no high memory is
   added and `DarwinBoot` reaches NO WINDOW. That is a silent failure point, unverified.
7. `dram-base` consumers. Searches of `UniXNU/drivers` and the SoC repository find no consumer of
   `dram-base`/`dram-size` (documentation only); whether the XNU patch side consumes them is
   unconfirmed. Official `docs/zh/devices/luming-infinityex-rsxq.md:174` requires comparing the
   firmware memory map, the DTS memory node, the ADT chosen `dram-base`/`dram-size` and the
   DarwinBoot owned window.
8. Inference and public reference. Inference (unverified): with a 1 GiB window the low Conventional
   fragments are likely too small, so a first-fit search would land near `0x8c0000000`, and whether
   XNU accepts a window outside the ADT dram range is unknown. Public reference, not nuwa evidence:
   official `docs/zh/devices/alioth.md:193/200/226` records a Mu-Silicium Qualcomm port with 8 GiB
   DRAM using a 4 GiB owned window, measured on hardware. The failure is benign: NO WINDOW only
   prints the memory map on screen and writes no partition.

The Reviewer subagent's follow-up investigation returned on 2026-11-07 with APPROVE WITH
CONDITIONS, scoped to the first `fastboot boot` only; see "First fastboot boot: Reviewer verdict
and conditions". Everything in this section remains static analysis, not verified on hardware.

## MemoryMapLib reconciliation (static)

Static analysis, not verified on hardware. The method was a read-only interval reconciliation of
three sources: the live FDT `reserved-memory` nodes (`live.dts`), the live `/proc/iomem`
`System RAM` list, and the static table in `uefi-nuwa`
`Platforms/Xiaomi/nuwaPkg/Library/MemoryMapLib/MemoryMapLib.c:9-35`. Each table entry inside the
DDR range was compared by address and size containment against those two live views. The local
raw dumps were the input and are not copied into this repository; only aggregates are recorded.

- The static table carries 41 entries, 27 of them inside the DDR range.
- The live FDT carries 35 reserved regions with a fixed `reg`; 6 of them are `no-map` regions the
  static table does not describe: `xbl_ramdump_region@81200000` (`0x81200000+0x280000`),
  `global_sync_region@82600000` (`0x82600000+0x100000`), `mpss_dsm_region@d4d00000`
  (`0xd4d00000+0x3300000`), `xbl_sc_region@d8100000` (`0xd8100000+0x40000`), `hwfence-shmem`
  (`0xe6440000+0x2dd000`) and `llcc_lpi_region@ff800000` (`0xff800000+0x600000`).
- If `RamManagerDxe` pads every uncovered gap of the `System RAM` range as
  `EfiConventionalMemory`, the gaps total 16 fragments, about 10.80 GiB. The largest are
  `0x8c0000000` + about 9216 MiB (ending at `0xafffff000`), `0x880000000` + about 925 MiB,
  `0xe7cb0000` + about 379 MiB, `0xbf300000` + about 346 MiB and `0x82800000` + about 128 MiB.
- Consequence for the 1 GiB window: no low fragment can hold it, so a first-fit search lands in
  the `0x8c0000000` fragment, which is inside the ADT `dram-base`. Shrinking `owned_memory_size`
  to below about 925 MiB would place the window at a low address outside the ADT `dram-base`, so
  it must not be shrunk. Changing any memory number needs the user's explicit confirmation
  regardless.
- The observation that no reserved region overlaps a gap is not safety evidence: the
  `/proc/iomem` `System RAM` list already excludes `no-map` regions, so that check is circular.
  What decides the risk on the `fastboot boot` path is the content of the RAM Partition, which is
  unknown.

## First fastboot boot: Reviewer verdict and conditions

Static analysis, not verified on hardware. The Reviewer subagent's extra investigation
(2026-11-07, Claude Sonnet Low, read-only) downgraded the window-allocation risk from High to
Medium and returned APPROVE WITH CONDITIONS, scoped to the first `fastboot boot` only.

Verdict basis:

1. The failure path writes no partition. `AllocateWindow` returns `EFI_OUT_OF_RESOURCES` when it
   finds no contiguous Conventional range (`DarwinBoot.c:531-545`); the `Fail` path releases the
   resources it held, prints `boot refused`, and shows the large on-screen `NO WINDOW` and `FREE`
   lines (`DarwinBoot.c:534-541`). On success the screen prints `pa`, `va`, `entry`, `args` and
   `owned` (`DarwinBoot.c:785-790`, `:797-811`).
2. Two premises from the previous round were withdrawn. "The window lies outside the ADT DRAM" is
   refuted, and XNU's physical memory range comes from `boot_args` (`DarwinBoot.c:745-748`);
   whether the ADT `dram-base`/`dram-size` has an XNU-side consumer remains unconfirmed.
3. The `RamManagerDxe` `LocateProtocol` silent-failure point is INSUFFICIENT EVIDENCE and cannot
   be settled statically: `apriori` is dispatched before the remaining modules and lists EnvDxe,
   SmemDxe and DALSYSDxe; `RamManagerDxe` is not in `apriori`, has `Depex = TRUE`, and therefore
   executes in FV order at `nuwa.fdf:87`. What is missing is the producer of
   `gEfiRamPartitionProtocolGuid` (EnvDxe is ready; if QcomBds or a deferred module produces it,
   the lookup fails silently). How to obtain it: binary reference-point analysis
   (`InstallProtocolInterface` versus `LocateProtocol`) and the first boot's DEBUG log.
4. Five doubts that had been proposed for escalation to Deep Reviewer each failed the four
   conditions of `docs/ai-orchestration-2026-11-06.md` §2.3; all five were reclassified
   INSUFFICIENT EVIDENCE with the gap stated. No escalation package was produced and Deep
   Reviewer was not used.

Conditions for the first `fastboot boot`:

| # | Condition | State |
| --- | --- | --- |
| 1 | Use a DEBUG build. | Done for the current artifact: `DEBUG_CLANGPDB`, `SILICIUM_UEFI.fd` 3145728 bytes. |
| 2 | Statically reconcile `MemoryMapLib` with the live `live.dts`/`iomem`. | Done: see "MemoryMapLib reconciliation (static)". |
| 3 | Establish the `RamPartition` protocol producer and its ordering. | Observed (run 4): `RamManagerDxe` mapped 14 RAM ranges including `0x8C0000000-0xB00000000`; see "Run 4". |
| 4 | `fastboot boot` only, no partition write; any device action needs the user's explicit authorisation in that round. | Plan only; no device action taken. |
| 5 | Confirm SEC writes the entry parameters into the HOB (`UniXNURamDiskDxe.c:215-233`; a failure only logs and does not block). | Observed (run 4): `UNIXNURAMDISK` found the FDT and published an initrd block device with status Success. |
| 6 | Capture plan: the DarwinBoot on-screen large text and the `NO WINDOW`/`FREE` lines, plus the DXE-stage AdvancedLogger page while the firmware is still running; SEC/PEI logs never enter the buffer and pstore/ramoops cannot serve as a channel because the FD lies in that region. | Done for the DXE stage (run 4): 24 OneSend QR frames decoded to a 179-line log. |
| 7 | The FD `0xA7100000..0xA7400000` overlaps the live ramoops region; keep the current value, user to confirm. | Recorded; user confirmation pending. |

Additional hypothesis risk (Medium): the `MemoryMapLib` table was inherited from sheng and has not
been reconciled item by item with the nuwa machine. If the RAM Partition lists a `no-map` region
that the table lacks as RAM, it would be padded as Conventional and used by DXE; the consequence
would be a wrong access and a reboot rather than flash corruption. The RAM Partition contents are
unknown, so this cannot be judged yet.

## First hardware runs (stage 1, 2026-11-07)

Three `fastboot boot` runs by the user's per-run authorisation, no partition written. Results were read
from phone-camera video (originals stay in the git-ignored `.cache/device-media/`); no bootloader log
or serial output exists, so causes below are inference unless stated.

| Run | Image | Observation | Reading |
| --- | --- | --- | --- |
| 1 | header v1 (copied from sheng) | USB stayed in fastboot, black screen, later the phone reached recovery | bootloader did not hand over; header v1 suspected |
| 2 | header v4, `os_version` 15.0.0, `os_patch_level` 2025-07 (copied from salami, not measured) | USB dropped, DXE log text, vendor DisplayDxe ran, then `abl Failed to read from partition` / `Failed to load ELF file` / `Auto processing of uefipil.cfg failed. Calling target panic`, reset to the Xiaomi logo | firmware runs; PIL `[AUTO] ABL` panics |
| 3 | v4 + local `uefipil.cfg` with empty `[AUTO]` | PIL panic gone; many `AllocatePoolPages: failed to allocate N pages`, `UniXNUDxe: application 9B665204-A133-47A2-9396-9E2B370A4E25 not found in any FV`, `no DTB blob could be loaded`, `Bds Arch Protocol not present!!`, then `ASSERT [DxeCore] DxeMain.c(581) !EFI_ERROR(Status)`, frozen | DXE heap shortage and/or menu app missing from FV; not yet separated |
| 4 | v4 + local uefipil + DXE Heap `0xBAB00000+0x0D1C0000` (`uefi-nuwa` `d7c97a7`) | assert gone; UniXNU menu shown (built-in configuration, 4 action entries, default `Return to firmware` after a 10 s countdown); the countdown ran out, the firmware found no OS and the phone went to the Android boot logo | stage 2 menu reached; Advanced Logger export works |

Checked read-only in TWRP: `abl_a` GPT type GUID equals the `uefipil.cfg` `[ABL]` `PartiGuid`
(`BD6928A1-4CE0-A038-4F3A-1495E3EDDFFB`) and the partition starts with a valid ELF32 (entry
`0x9FA00000`), so the GUID is not the cause. ABL is already running when the firmware starts, so PIL
need not load it; `Binaries/nuwa` is untouched and `RAW.inc` points at the local copy
(`uefi-nuwa` `e69e714`). The rebuilt FD could not be string-searched (compressed volume), so use of the
empty list rests on the build config plus the run-3 behaviour.

Slot side effect: after the failed runs slot A showed `slot-unbootable: yes`, `retry-count: 0` and the
phone looped into fastboot with no logo. `fastboot set_active a` (authorised) restored it to
`retry-count: 7`. Check the slot state before and after every run.

## Run 4: Advanced Logger log (stage 2, 2026-11-07)

Power key = Enter, volume keys = Up/Down. Tools -> Advanced Logger showed 24 OneSend QR frames; a second
camera recorded them and the log was decoded on the host (`.cache/device-media/20261107-stage2-al-qr/`, not
committed). Decoding note: `zbar` returns the binary QR payload Latin-1 expanded into UTF-8, so the decoder
must undo that before parsing the 752-byte frames. All 24 blocks passed CRC; the 17000-byte log has 179 lines;
its file name carries a bogus 2019 date because the RTC is unset. This is a DXE-stage snapshot only.

Observed:

- `RamManagerDxe` printed 14 `Successfully Mapped RAM Range` lines, including `0x8C0000000-0x980000000` and `0x980000000-0xB00000000`. The RAM Partition protocol producer therefore exists and ran before it (closes condition 3), and the high 9 GiB is reported to the firmware.
- The PEI memory allocation dump shows the Conventional window `0xBAB00000-0xC7CBFFFF` (the new DXE Heap).
- `UNIXNURAMDISK: device tree at 0xB5DB1000, 938804 bytes`; `initrd 0xB5FB2000-0xB7FFF1D4 rounded to 0x204D200 bytes`; `initrd block device ... Success` (closes condition 5). The boot image had an empty ramdisk, yet an initrd of about 32 MiB was published: ABL adds its own ramdisk. Unresolved for stage 3: `UniXNURamDiskDxe` publishes the whole chosen initrd, so a payload FAT volume would not sit at its start; check how `unixnu bootimg` and its `vendor_boot` handling place the payload before building one.
- `[Bds]Booting UniXNU` and four FAT filesystems installed; `DarwinBoot.efi` and `AdvancedLogDxe.efi` loaded; `Advanced Logger Info` buffer `0xC6771000-0xC6B71000` (4 MiB, inside the new heap).
- Errors in the log: `SPSSDxe.efi` `Load Error` and `RscDxe.efi` `No mapping` (vendor drivers, not investigated). No `NO WINDOW` line yet because DarwinBoot has not been asked to boot.

Not established: whether the heap size or merely the layout fixed the run-3 assert; whether DarwinBoot can allocate its 1 GiB window.

## Payload delivery through vendor_boot (stage 3, 2026-11-08)

Why `fastboot boot` alone cannot carry a payload: nuwa is a GKI layout (`boot_a` ramdisk_size 0,
`init_boot_a` ramdisk 2968538 bytes, `vendor_boot_a` v4 vendor ramdisk 30899943 bytes, lz4, kernel modules).
The ABL hands the firmware `vendor_boot` + `init_boot` ramdisks (plus bootconfig) as the initrd, so the payload
FAT volume must be the vendor ramdisk, as `UniXNU/docs/zh/guide/boot.md` ("把 payload 放进 vendor_boot") says.
`vendor_boot_a` and `vendor_boot_b` are byte-identical stock images (sha256 `5ad2a9dc…cc23`; read-only copies in
the git-ignored `.cache/stock/`). `unixnu vendor_boot --verify-against` reproduced the stock image byte for byte.
`vendor_boot_a` holds the Android vendor ramdisk, so it was left alone and the unused slot B was used.

Procedure actually run (each device write authorised by the user in that round):

1. Built an 8 MiB FAT16 test payload (`unixnu.toml` with an `xnu` entry and a Tools entry, placeholder files, no
   kernel) and `unixnu vendor_boot --stock vendor_boot_a.img --ramdisk payload.img` (ramdisk 8 MiB at 0x1000, address
   0x1000000).
2. `fastboot flash vendor_boot_b` hung on the 96 MiB transfer (fastboot also stopped answering `getvar`; a
   re-entered fastboot answered again). Nothing was written by it. The image was written from TWRP instead:
   `adb push` to `/tmp`, `dd` to `/dev/block/by-name/vendor_boot_b`, sha256 re-read after dropping caches matched.
3. `bootctl set-active-boot-slot 1`, `adb reboot bootloader`, `fastboot boot boot-stage12-v4-r4.img`; afterwards
   `fastboot set_active a` and a normal reboot into TWRP (slot A `retry-count` is back to 7).

Observed (photo, `.cache/device-media/20261108-stage3-payload/`): the menu header shows
`config: \EFI\UniXNU\unixnu.toml`, entry 1 `UniXNU (stage 3 tes…` (`xnu`) and entry 2 `Tools`; the footer shows
`'Tools' returned: Not Found` and `config error: entry tools: needs 'path'`. The Tools entry was my mistake (no
`type = "action"`, so it parsed as an EFI entry and failed to find a path); the config itself was loaded, the rest
of the entries stayed. Conclusions: the ABL reads the vendor_boot of the **active** slot during `fastboot boot`,
the payload volume reaches UniXNU through the initrd, the FAT volume is mountable, and two official stage 3 checks
are met (config path reported, `xnu` item present). Not yet checked: payload file hashes and the ADT sidecar
(both need a real kernel), the `payload: initrd … fs <n>` status line (no Advanced Logger log was taken), and the
fixed `unixnu.toml` (type = "action") has been built but not yet written to the device.

Constraints found: `vendor_boot_*` is 96 MiB, so the payload volume must stay well under that (`board.toml`
`[payload] size_mib = 192` does not fit); the stock layout leaves 15 MiB between the ramdisk address and the device
tree, so a larger payload needs `--ramdisk-addr`.

## splash_region

The firmware DTB carries no `splash_region` node, while the live machine reports
`0xb8000000` with size `0x2b00000` and MemoryMapLib already describes a Display Reserved
region. Whether ABL consumes that reservation is unproven, so nothing is injected into the DTB;
this two-tree review itself changed no DTB file, and the firmware repository separately carries
an uncommitted, uncompiled DSC/FDF integration candidate. The DTB splash node is a later
decision, not a step 5 blocker.

## ADT identity values

Two ADT `/chosen` properties, `chip-id` (u32) and `unique-chip-id` (u64), are software identity
seeds, not Apple silicon IDs. They seed `IOPlatformUUID`; when they are missing, the zero-timeout
`gethostuuid()` path keeps waiting. The generator only checks that each value is nonzero and of the
right width, and never compares it against the SoC.

The donor iPhone10,3 DeviceTree (`out/ipsw/20H392/DeviceTree.d22ap.dtb`, an LZFSE-compressed ADT)
carries `chip-id = 0` and `unique-chip-id = 0`: template placeholders that iBoot fills at run time.
The donor therefore has no value to copy.

Decision (2026-11-07): draw both values on the host, keep them stable, and never commit the seed.

- `chip_id = 4acab8db`, in `board.toml` `[payload.adt]`: random, nonzero, and different from
  sheng's `0x8142` and from the donor ApChipID `0x8015`.
- `unique-chip-id`: a random 8-hex-digit u64 seed, kept only in the git-ignored `unixnu.local.toml`
  of the base UniXNU checkout. It is never committed, and every build must reuse the same value;
  if it is lost, the same device gets a different `IOPlatformUUID`, so the user must back it up.
- `root_match_volume_uuid` stays commented out for stages 1-5: fastboot boot uses the in-memory
  Data seed, the generator omits `/chosen/root-matching` when the value is empty, and a non-empty
  placeholder fails UUID parsing. Before stage 6, read the OS APFS volume UUID (not the container
  UUID and not the Data volume UUID) from the built userdata image and write it to `board.toml`
  and to the OS profile `[root] os_volume_uuid`.

Self-checked (2026-11-07, in memory, with the real `board.toml`, the iOS 16 profile and the local
seed): the generator returned 12984 bytes. `/chosen` carries `chip-id = 0x4acab8db`, an 8-byte
nonzero `unique-chip-id` matching the local seed, `dram-base = 0x8c0000000`,
`dram-size = 0x240000000` and `darwinboot-memory-size = 0x40000000`; there is no `root-matching`
(expected at this stage); the 8 `cpu` `reg` entries are 0..1792; `timebase-frequency = 0x124f800`
and `psci = smc`. `arm-io` holds only the `intc` child because `nuwa.dts` still describes CPU,
memory and `intc` only, which is step 6 work. `ephemeral-storage` is absent because no Data seed
was passed; that is a property of this run, not a stage 1-5 conclusion.

## Not done here

`[bootimg] dtb` wiring still waits for a separate report. The ADT identity is decided: `chip_id`
is written in `board.toml` and `root_match_volume_uuid` stays commented out until the userdata
image exists (see "ADT identity values"); no boot image is assembled.

## Reproducing the firmware build

First self-checked on 2026-11-07 (the Verifier subagent's early attempts returned "Country,
region, or territory not supported"), then independently re-run by the Verifier subagent on the
same day against device repository `b1064eb8` and uefi-nuwa `e494c01b`: PASS. The build does not
boot, does not write a partition and does not touch a device.

Inputs are hand-staged; no `fetch` step provisions them.

1. edk2 tree: extract the Mu_Basecore GitHub archive
   `cfb93724a06ff86ff5ba971413368a7809ee42a5` into WSL ext4 at `~/nuwa-fw/mu_basecore`. The
   archive carries no submodule contents, so copy the five directories from the already
   checked-out base `out/feeds` tree:
   `MdePkg/Library/BaseFdtLib/libfdt`,
   `MdePkg/Library/MipiSysTLib/mipisyst`,
   `BaseTools/Source/C/BrotliCompress/brotli`,
   `MdeModulePkg/Library/BrotliCustomDecompressLib/brotli`,
   `SecurityPkg/DeviceSecurity/SpdmLib/libspdm`.
2. openssl: place archive `67b5686b4419b4cb8caa502711c41815f5279751` at the `uefi-nuwa` gitlink
   path `Silicon/Silicium/OpensslPkg/Library/OpensslLib/openssl`.
3. Fixed pins: `Common/Mu` `b8d46c71`, `Common/Mu_OEM_Sample` `b70b4b7b` and `Silicium-ACPI`
   `2d465ad7`; `Binaries` comes from the Device-Binaries sparse checkout listed in
   `proprietary-files.txt`.
4. Patch: `Resources/MuPatches/Gic-Spurious.patch` applies cleanly to the shared edk2 tree and
   rolls back cleanly.
5. Network inside WSL: link MTU 1400, proxy passed through environment variables to the Windows
   host gateway port 7890 with allow-lan enabled.
6. `board.toml` `[firmware.defines]` must carry `ENABLE_SECUREBOOT = "0"`: `SiliciumPkg.dsc.inc`
   passes `-D ENABLE_SECUREBOOT=$(ENABLE_SECUREBOOT)` unconditionally, and `unixnu` runs the
   EDK II build directly instead of Mu-Silicium's `build_uefi.py` (default `0`,
   `--enable-secureboot` is opt-in). With the macro empty, `SecureBootHandler.c:216`
   (`#if ENABLE_SECUREBOOT == 1`) fails preprocessing.
7. Build from the base checkout (`cwd = UniXNU`):

   ```sh
   ./unixnu build firmware -D ../nuwa/UniXNU-nuwa --uefi ../nuwa/uefi-nuwa \
     --edk2 /home/wh1stl3/nuwa-fw/mu_basecore
   ```

8. Result (independently re-run by the Verifier: PASS): exit 0, artifact
   `uefi-nuwa/Build/nuwaPkg/DEBUG_CLANGPDB/FV/SILICIUM_UEFI.fd`, 3145728 bytes = `0x300000`,
   which matches `uefi_fd.size` in `uefi-nuwa/Resources/Configs/nuwa.toml`. `FVMAIN.inf` lists
   `UniXNU`, `UniXNUDxe`, `UniXNURamDiskDxe`, `DarwinBoot` and `AdvancedLogDxe`.

`AdvancedLogDxe`'s depex `gAdvancedLoggerProtocolGuid` now has a producer, wired in uefi-nuwa
`e494c01b2f679439fdaeaf2084b693c7220543f5`. DXE_CORE uses AdvLoggerPkg's DxeCore
`AdvancedLoggerLib` instance, whose constructor installs the protocol; DXE_DRIVER, UEFI_DRIVER
and UEFI_APPLICATION use the Dxe instance and DXE_RUNTIME_DRIVER the Runtime instance. The real
`AdvancedLoggerHdwPortLib` runs over `SerialPortLib` (DEBUG keeps `FrameBufferSerialPortLib`, so
the screen log remains and is also written to the buffer). In DEBUG the `DebugLib` is
`BaseDebugLibAdvancedLogger` and RELEASE is unchanged. SEC keeps `BaseDebugLibSerialPort`
because `Sec.c` calls `BaseDebugLibSerialPortConstructor` directly, which made the first link
attempt fail before it was corrected. `PcdAdvancedLoggerBase` is 0 and the DXE_CORE library
allocates a 4 MiB buffer with `AllocateReservedPages` instead of a fixed physical address.

The independent rebuild passed and produced a 3145728-byte `SILICIUM_UEFI.fd`. `DxeMain`
links `DxeCoreAdvancedLoggerLib`, `AdvancedLogDxe` and `UniXNUDxe` link
`DxeAdvancedLoggerLib`, `Guid.xref` contains `gAdvancedLoggerProtocolGuid`, and `FVMAIN.inf`
still lists the five modules. Runtime dispatch and the Tools -> Advanced Logger page are still
unverified and need a device run. The assumption that the 4 MiB reserved-page allocation lands in
the DXE heap is unconfirmed. The change alters every DXE module's debug output path; the boot-chain review returned APPROVE
WITH CONDITIONS on 2026-11-07, scoped to the first `fastboot boot` (see "First fastboot boot:
Reviewer verdict and conditions"). That review is static analysis, not hardware evidence.

## Provenance

The conclusions above were taken from the archived platform observations kept outside this
repository. The backups MANIFEST is read before any other file, so no unlisted asset is used:

- `legacy-nuwa-backups/recovery-cpu-20261021T005937467055Z/running-fdt.dts`
- `legacy-nuwa-backups/recovery-cpu-20261021T005937467055Z/iomem.txt`
- `legacy-nuwa-backups/recovery-cpu-20261021T005937467055Z/cpuinfo.txt`
- `legacy-nuwa-artifacts/platform-inputs/20261020T124109389461Z/nuwa-platform-observed.json`
- `memory-layout/nuwa-layout-tmlq93uo/report.json`

Only the aggregates quoted above are recorded. Raw dumps, device identifiers, serial numbers,
ECID values and platform seeds are not copied into this repository, and this round reused the
reviewed conclusions instead of re-scanning the archives.

## Verification boundary

The platform-review sections are source-level review of archived observations, with no host
command behind them. The "Reproducing the firmware build" section records one build that the
Verifier subagent independently re-ran (exit 0 and the artifact size); it produced no boot and no
device was touched. Nothing here may be cited as device-verified evidence.

The Verifier subagent independently re-ran step 5 on 2026-11-07 against device repository
`b1064eb8` and uefi-nuwa `e494c01b`; all seven checks passed: git state, record check, tree
assembly with the DTB byte comparison, the firmware build (`SILICIUM_UEFI.fd` 3145728 bytes =
`0x300000`), `FVMAIN.inf` with the five modules, `Guid.xref` containing
`gAdvancedLoggerProtocolGuid`, and `DxeMain` linked against `DxeCoreAdvancedLoggerLib`. That
re-run predates the `board.toml` `chip_id` change, and it booted nothing on hardware.

That Verifier's item 6 (secret scan) used an over-broad `androidboot.serialno` keyword: all 42
hits are example values for other vendors' devices in the upstream firmware `Resources/DTBs`,
and searching both repositories for this device's serial number returns 0 hits, so this is a
search-term issue rather than a leak.

The boot-chain review of the Advanced Logger rework was returned by the reviewer subagent on
2026-11-07 as APPROVE WITH CONDITIONS, scoped to the first `fastboot boot`; it is static analysis
only and nothing here is a boot-chain hardware result.

## Open items

- `Binaries/nuwa` is in place (sparse checkout of Device-Binaries `4648d229`); the repository
  declares no licence and the upstream origin of the binaries is unverified.
- The submodule contents required by the build are staged by hand: five Mu_Basecore submodules
  copied from the base `out/feeds` checkout, plus openssl at the `uefi-nuwa` gitlink path. They
  are not provisioned by a checked-out submodule.
- Advanced Logger producer: wired in uefi-nuwa
  `e494c01b2f679439fdaeaf2084b693c7220543f5`. DXE_CORE uses AdvLoggerPkg's DxeCore
  `AdvancedLoggerLib` instance (constructor installs `gAdvancedLoggerProtocolGuid`), drivers use
  the Dxe and Runtime instances, and the rebuild passed (independently re-run by the Verifier on
  2026-11-07) with the GUID present in `Guid.xref`. Runtime dispatch and the Tools -> Advanced
  Logger page are still unverified, the 4 MiB reserved-page allocation's placement in the DXE
  heap is an assumption, and the boot-chain review concluded APPROVE WITH CONDITIONS on
  2026-11-07, scoped to the first `fastboot boot` only.
- ADT identity is decided: `chip_id = 4acab8db` is in `board.toml`, the `unique-chip-id` seed is
  kept only in the base checkout's git-ignored `unixnu.local.toml` and needs a user backup, and
  `root_match_volume_uuid` is due before stage 6.
- The firmware image builds (independently re-run by the Verifier on 2026-11-07: PASS) but has
  not booted; there is no hardware evidence.
- Boot-chain review: concluded on 2026-11-07 with APPROVE WITH CONDITIONS, scoped to the first
  `fastboot boot` only. Deep Reviewer was not used because no candidate met
  `docs/ai-orchestration-2026-11-06.md` §2.3; see "First fastboot boot: Reviewer verdict and
  conditions". This is not a release to boot: conditions 3, 5, 6 and 7 there are still open, and
  any device action needs the user's explicit authorisation in that round.
- The memory ownership gate is still open.
- DarwinBoot window allocation (static analysis, not verified on hardware): the window risk is
  Medium, not High. The `gEfiRamPartitionProtocolGuid` producer is unconfirmed (`RamManagerDxe`
  is not in `apriori`, has `Depex = TRUE` and runs in FV order at `nuwa.fdf:87`); resolve it by
  binary reference-point analysis and the first DEBUG boot log.
- `MemoryMapLib` versus nuwa: 6 live `no-map` regions are not described by the static table
  (`xbl_ramdump_region`, `global_sync_region`, `mpss_dsm_region`, `xbl_sc_region`,
  `hwfence-shmem`, `llcc_lpi_region`; see "MemoryMapLib reconciliation (static)"), and whether
  the RAM Partition reports them as RAM is unknown. Adding them to `MemoryMapLib` is an open user
  decision, not an action taken here.
- Do not shrink `owned_memory_size`: a first-fit window only reaches a low address below about
  925 MiB, which is outside the ADT `dram-base`. Any memory-number change needs user confirmation.
- Whether to inject `splash_region` waits on ABL evidence.
