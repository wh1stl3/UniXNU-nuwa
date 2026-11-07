# Device evidence, 2026-11-07: read-only recovery capture

Read-only facts collected on 2026-11-07 from a Xiaomi 13 Pro (nuwa, SM8550) running a TWRP
recovery. This document records observations only. It closes no porting area: every area in
`porting.toml` stays `planned`, and no `host` or `device` evidence entry is added because those
require a command plus a full 40-character repository revision that only exists after a commit.

## Method and read-only boundary

| Item | Value |
| --- | --- |
| Device | nuwa / Xiaomi 13 Pro (SM8550) |
| Environment | TWRP 3.7.1_12 recovery, root adb shell |
| Active slot | `_a` |
| Kernel under test | 5.15.195 (Android kernel in recovery) |
| Access | read-only |

Read-only operations used: `cat` of `/proc` and `/sys` files, `dmesg`, `ls`, `blockdev --get*`,
`adb pull /sys/firmware/fdt`, and `adb exec-out dd` to copy the head of each block device to the
host for parsing.

Explicitly not done in this capture: no partition was written, no `fastboot` command was run, no
slot or boot state was changed, and no reboot or pstore persistence test was performed.

## Raw capture: local only, never committed

The raw files live outside every repository, in
`D:/Code/PortingiOS/nuwa/.cache/device-evidence/20261107-recovery/`, and are not part of any
commit. Filenames present:

```
blk-sizes.txt  blockdev.txt  by-name.txt  cmdline.txt  cpuinfo.txt  dmesg-hw.txt
gpt-sda.bin  gpt-sdb.bin  gpt-sdc.bin  gpt-sdd.bin  gpt-sde.bin  gpt-sdf.bin
iomem.txt  live.dts  live.fdt  meminfo.txt  midr.txt  pstore.txt
sgdisk-sda.txt  sgdisk-sdb.txt  sgdisk-sdc.txt  sgdisk-sdd.txt  sgdisk-sde.txt  sgdisk-sdf.txt
soc.txt  version.txt
```

The capture also contains a kernel command line and GPT images. This document and `porting.toml`
only reference the directory and file names; they reproduce no raw content, no serial number
(device or USB), no GPT disk or partition GUID, no `/proc/cmdline` content and no unique chip ID
or ECID.

## 1. Storage

### LUN inventory

| LUN | Size as 4096-byte LBAs | Size as 512-byte sectors | Logical / physical block |
| --- | --- | --- | --- |
| sda | 61850624 | 494804992 | 4096 / 4096 |
| sdb..sdf | present | not recorded here | 4096 / 4096 |

`sda` GPT: 32 entries, usable LBAs `6..61850618`.

### Selected partitions (LBAs are 4096-byte units)

| Partition | LUN | first_lba | last_lba | LBAs | Bytes |
| --- | --- | --- | --- | --- | --- |
| userdata | sda32 | 3110976 | 61850618 | 58739643 | 240597577728 (about 224 GiB) |
| super | sda31 | 751680 | 3110975 | 2361296 | 9671868416 |
| metadata | sda17 | 16384 | 32767 | 16384 | 67108864 |
| persist | sda18 | 32768 | 49151 | 16384 | 67108864 |
| boot_a | sde14 | 149126 | 198277 | 49152 | 201326592 (192 MiB) |
| vendor_boot_a | sde24 | 217670 | 242245 | 24576 | 100663296 |
| abl_a | sde11 | not recorded | not recorded | - | - |
| modem_a | sde7 | not recorded | not recorded | - | - |
| xbl_a | sdb1 | not recorded | not recorded | - | - |

The byte column is arithmetic (`LBAs x 4096`), not a separately observed value.

### Unit trap

GPT LBAs are 4096-byte units taken from the GPT header parsed on the host, while
`/sys/block/*/size` and `blockdev --getsz` report 512-byte sectors. The two must not be mixed
without conversion; mixing them is an off-by-8 error (for `sda`, 61850624 x 4096 =
494804992 x 512).

### Tooling note

`sgdisk -p` is not supported by this recovery image (it answers `invalid option -p`). The GPT
header and entry array were therefore copied with `dd` to the host and parsed there.

### Observation

`userdata` (`sda32`) has `last_lba = 61850618`, equal to the last usable LBA of `sda`. This is an
observation about the GPT; it is not a conclusion about the root-volume layout or about who may
write there.

### Board sync

`board.toml` `[userdata]` carries `first_lba = 3110976`, `last_lba = 61850618`,
`lba_bytes = 4096`.

## 2. CPU

| Cores | MIDR | Core |
| --- | --- | --- |
| cpu0-cpu2 | 0x411fd461 | A510 |
| cpu3-cpu4 | 0x411fd4d0 | A715 |
| cpu5-cpu6 | 0x412fd470 | A710 |
| cpu7 | 0x411fd4e0 | X3 |

SoC identity from the live system: `soc_id = 519`, `machine = KALAMA`,
`family = Snapdragon`, `revision = 2.0`.

Live FDT: `cpu@0`..`cpu@700`, eight nodes; `psci` `method = smc`,
`compatible = arm,psci-1.0`.

## 3. Interrupts and timer

| Item | Observed value |
| --- | --- |
| GICD | 0x17100000, size 0x10000 |
| GICR | 0x17180000, size 0x200000 |
| redistributor-stride | 0x40000 |
| #interrupt-cells | 3 |
| Timer interrupts | PPI 13, 14, 11, 12 |
| Timer clock-frequency | 0x124f800 (19.2 MHz) |

At Android runtime `arch_timer` appears as GICv3 virq 11 (virtual timer PPI 11, matching ArmCpu
INTID 27). The firmware DTB's fourth timer entry is 10, which differs from the live 12; that entry
is not consumed by the current EL1-only path.

Not obtained: the `CNTFRQ` read-back. The boot-time dmesg record had already wrapped in the ring
buffer when the capture ran, so `cntfrq_readback` stays unverified and the 19.2 MHz value remains
a live DTB property.

## 4. Memory

### `/memory` reg ranges (live FDT)

`ddr_size = 0xc` (12 GiB device).

| # | Base | Size |
| --- | --- | --- |
| 1 | 0x0000000080000000 | 0x0000000000e00000 |
| 2 | 0x00000000811d0000 | 0x0000000056e30000 |
| 3 | 0x00000000d8140000 | 0x0000000000020000 |
| 4 | 0x00000000d8800000 | 0x0000000000000000 |
| 5 | 0x00000000e7cb0000 | 0x0000000018350000 |
| 6 | 0x0000000880000000 | 0x0000000039d00000 |
| 7 | 0x00000008c0000000 | 0x00000000c0000000 |
| 8 | 0x0000000980000000 | 0x0000000180000000 |
| 9 | 0x00000008b9f00000 | 0x0000000001e00000 |

Ranges 7 and 8 are adjacent and together span `0x8c0000000..0xb00000000`, a contiguous 9 GiB.
That matches the board DTS geometry `0x8c0000000 + 0x240000000`.

### `reserved-memory` nodes seen (not exhaustive)

| Node | reg | Notes |
| --- | --- | --- |
| ramoops@0xa7000000 | 0xa7000000 + 0x400000 | no `no-map`; real node, not a placeholder |
| splash_region | 0xb8000000 + 0x2b00000 | labelled `cont_splash_region` |
| xbl_dt_log@81a00000 | 0x81a00000 + 0x40000 | `no-map` |
| smem | 0x81d00000 + 0x200000 | - |

### Recorded as observation only

The current firmware FD window `0xa7100000-0xa7400000` falls inside the ramoops range
`0xa7000000-0xa7400000`. This document does not conclude who owns that range today, and nothing
in `board.toml` or the DTS is changed because of it.

### Still missing

No evidence this round for the current firmware version's RAM Partition -> HOB -> EFI memory map
-> DarwinBoot window. That needs a UEFI log taken after `fastboot boot`-ing our own firmware, so
the memory ownership gate stays open.

## 5. pstore

`/dev/pmsg0` exists while `/sys/fs/pstore` is empty, so the Android kernel has a ramoops backend.
Whether ramoops contents survive a warm reboot was not tested. The ramoops address range is the
one whose overlap with the FD window is recorded above as an observation only.

## 6. Not collected

| Item | State |
| --- | --- |
| unique-chip-id | not read; the official profile only requires an 8-hex-digit device seed, the decision belongs to the user, and it is never committed |
| `[payload.adt].chip_id` | not obtainable from the live system; donor evidence still missing |
| root volume UUID | only exists after the userdata image is built |
| UEFI memory map for the current firmware cohort | missing; needs a boot of our firmware |
| pstore survival across a warm reboot | not tested |
| `CNTFRQ` read-back | not obtained (ring buffer had wrapped) |
| storage controller, clock, link and SMMU facts | not collected this round |
