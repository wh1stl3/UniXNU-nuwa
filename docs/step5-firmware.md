# Step 5 platform inputs: reviewed facts

Reviewed on 2026-11-07 from an independent review of the archived platform observations. This
file records conclusions only. It adds no host or device verification: no build ran, no firmware
was executed and no device was touched for the facts below, so every porting area stays
`planned` until real evidence exists.

## Revisions in scope

| Tree | Revision |
| --- | --- |
| UniXNU base (contains the local iOS 16 profile) | `693f5d9cae8a408dd18b39f3f9fdc4228c934241` |
| This device repository | `279c990a0c7a238aa0a5818493c6cd6a46528749` |
| SM8550 common | `a9f45dc60c035084b95463781538380f4c3606c9` |
| uefi-nuwa | `322d742fd87d370aac96bb394d1feac61beb9b3a` |

Firmware changes after `322d742f` were not reviewed here.

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

## Not done here

`[bootimg] dtb` wiring and the `[payload.adt] chip_id` / `root_match_volume_uuid` values are
deferred to a separate report. They stay unset (`REQUIRED_*` for the ADT fields), and no boot
image is assembled.

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

Everything here is source-level review of archived observations. There is no host command, build
result or device observation behind it, so it must not be cited as host-verified or
device-verified evidence.

## Open items

- `Binaries/nuwa` is missing.
- The submodule contents are not checked out.
- Advanced Logger has no verified producer on AARCH64, and `AdvancedLogDxe` depends on
  `gAdvancedLoggerProtocolGuid`, so no logs appear until a producer is connected.
- The memory ownership gate is still open.
- `payload.adt.chip_id` and `root_match_volume_uuid` remain placeholders.
- Whether to inject `splash_region` waits on ABL evidence.
