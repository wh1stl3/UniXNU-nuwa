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
the DXE heap is unconfirmed. The change alters every DXE module's debug output path; the
boot-chain review is assigned to the reviewer subagent and is still in progress, so no review
result is claimed.

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

The boot-chain review of the Advanced Logger rework is assigned to the reviewer subagent and is
still in progress; no result has been returned, so nothing here is claimed as a boot-chain
review.

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
  heap is an assumption, and the boot-chain review is still in progress.
- ADT identity is decided: `chip_id = 4acab8db` is in `board.toml`, the `unique-chip-id` seed is
  kept only in the base checkout's git-ignored `unixnu.local.toml` and needs a user backup, and
  `root_match_volume_uuid` is due before stage 6.
- The firmware image builds (independently re-run by the Verifier on 2026-11-07: PASS) but has
  not booted; there is no hardware evidence.
- The boot-chain review by the reviewer subagent is still in progress; no result has arrived.
- The memory ownership gate is still open.
- Whether to inject `splash_region` waits on ABL evidence.
