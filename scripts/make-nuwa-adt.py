#!/usr/bin/env python3
"""Emit the nuwa (SM8550 / Xiaomi 13 Pro) Apple-format device tree.

This is the board script named by [payload.adt] tool in board.toml. UniXNU's
payload step calls it as ``python3 <tree>/<tool> --output ... --dram-size ...``
and passes every [payload.adt] option as a flag; see
UniXNU docs/zh/concepts/payload.md. The script is self-contained (stdlib only)
because it runs with the UniXNU base tree as the working directory, not from
this repository.

Every board value below is pinned to a nuwa observation, and the comment names
the observation. Values are NOT inherited from sheng, fuxi or any other board,
and NOT copied from the Android device tree wholesale: this tree is the Apple
node encoding XNU reads, and only the properties XNU/driver matching actually
consume are emitted.

Hardware evidence (captured on the actual phone, 2026-10-22):
  out/live-nuwa-dt/android-dt-after-r011/android-live.dtb   (live FDT)
  docs/inherited/nuwa-observed.json                          (iomem/partitions)
Decoded comparisons in docs/operations/2026-10-24-nuwa-adt.md.

This tree declares no memory ownership by itself. It advertises the one DRAM
bank XNU's single-window model can use and, only when asked, a contiguous
allocation request through /chosen/darwinboot-memory-size. Whether the firmware
can actually satisfy that request is a separate, unverified question.
"""
import argparse
import os
import struct
import sys
import zlib
from pathlib import Path

# --- Pinned nuwa SM8550 board values -------------------------------------
#
# DRAM: the observed main bank, /proc/iomem "System RAM" 0x8c0000000-0xaffffefff
# (docs/inherited/nuwa-observed.json memory.largest_bank_hex = 9216 MiB), and the
# live FDT /memory reg pair 0x8c0000000+0xc0000000 followed by 0x980000000+
# 0x180000000, which are adjacent and sum to the same 9 GiB. DRAM is NOT
# contiguous on this phone; XNU's arm64 physical memory is a single window
# (boot_args physBase+memSize), so only this bank has the room. See D-001/D-002.
DRAM_BASE = 0x8C0000000

# APSS peripheral block that contains the GIC. The live FDT puts
# interrupt-controller@17100000 directly under /soc, so the window is chosen to
# cover both GIC windows and is expressed as arm-io ranges.
ARMIO_BASE = 0x17000000
ARMIO_WINDOW = 0x08000000

# Live FDT /soc/interrupt-controller@17100000:
#   compatible = "arm,gic-v3"
#   reg = <0x17100000 0x10000 0x17180000 0x200000>
#   redistributor-stride = <0x00 0x40000>
GIC_DIST = 0x17100000
GIC_DIST_SIZE = 0x10000
GIC_REDIST = 0x17180000
GIC_REDIST_SIZE = 0x200000
GIC_REDIST_STRIDE = 0x40000

# Live FDT /soc/timer: compatible = "arm,armv8-timer", clock-frequency =
# <0x124f800> = 19200000 Hz (Qualcomm SM8xxx architectural counter).
TIMEBASE = 19200000

# Live FDT /soc/ufshc@1d84000: reg = <0x1d84000 0x3000 ...>, i.e. the first
# window matches /proc/iomem 0x1d84000-0x1d86fff. It lies BELOW ARMIO_BASE, so
# it cannot be a child with a small positive reg offset; NativeUfs matches the
# compatible string and takes its physical windows from board constants.
UFS_HC = 0x1D84000
UFS_HC_SIZE = 0x3000

# Live FDT /soc/ufsphy@1d80000, /proc/iomem 0x1d80000-0x1d81933.
UFS_PHY = 0x1D80000
UFS_PHY_SIZE = 0x2000

# Root compatible. Recorded as the live FDT actually reports it
# (model = "Qualcomm Technologies, Inc. 8550 nuwa"). ArmDTPlatform::configure()
# does not match this property -- it only requires /cpus, /arm-io, /defaults,
# /options and a usable CHARN NVRAM proxy -- so this value is an honest hardware
# label, not a driver-selection key. Driver matching happens on the arm-io
# children instead (e.g. NativeUfs looks for "qcom,sm8550-ufshc").
ROOT_MODEL = b'nuwa-first-boot\0'
ROOT_COMPATIBLE = b'qcom,kalama-mtp\0qcom,kalama\0qcom,mtp\0'

# nuwa has no Home button; 2 is the non-mechanical answer BSPlatform passes
# through. The button set is the phone's own (power/volume), not sheng's.
BUTTON_NAMES = b'hold\0voldown\0volup\0'

OWED_MIN = 0x10000000   # 256 MiB
OWED_MAX = 0x200000000  # 8 GiB
OWED_STEP = 0x200000    # 2 MiB


def node(name, properties=(), children=()):
    """Encode one Apple-format node: u32 prop count, u32 child count, then props."""
    properties = [('name', name.encode('ascii') + b'\0'), *properties]
    keys = [key for key, _ in properties]
    if len(set(keys)) != len(keys):
        raise ValueError('duplicate property in node %s' % name)
    for key, _ in properties:
        encoded = key.encode('ascii')
        if not encoded or len(encoded) > 31 or b'\0' in encoded:
            raise ValueError('invalid property name %r in node %s' % (key, name))
    result = struct.pack('<II', len(properties), len(children))
    for key, data in properties:
        if len(data) > 1024 * 1024:
            raise ValueError('oversized property %s in node %s' % (key, name))
        result += struct.pack('<32sI', key.encode('ascii'), len(data))
        result += data + bytes(-len(data) % 4)
    return result + b''.join(children)


def empty_nvram_proxy():
    """A fresh volatile CHRP bank for upstream IODTNVRAM, with no controller.

    ArmDTPlatform::configure() rejects the tree when /chosen has no usable proxy,
    so this is required even though nuwa has no persistent NVRAM controller.
    """
    def header(name, size):
        raw = bytearray(struct.pack('<BBH12s', 0x70, 0, size // 16, name))
        checksum = sum(raw)
        while checksum > 255:
            checksum = (checksum & 255) + (checksum >> 8)
        raw[1] = checksum
        return raw

    image = bytearray(8192)
    image[:16] = header(b'nvram', 32)
    image[32:48] = header(b'common', 16 + 2048)
    free_at = 32 + 16 + 2048
    image[free_at:free_at + 16] = header(b'free', len(image) - free_at)
    struct.pack_into('<I', image, 16, zlib.adler32(image[20:]))
    return [('nvram-bank-size', struct.pack('<I', len(image))),
            ('nvram-bank-count', struct.pack('<I', 1)),
            ('nvram-current-bank', struct.pack('<I', 0)),
            ('nvram-proxy-data', bytes(image))]


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--output', type=Path, required=True,
                        help='Payloads/kernel.macho.adt')
    parser.add_argument('--dram-size', type=lambda value: int(value, 0), required=True,
                        help='Advertised DRAM size of the main bank, e.g. 0x240000000 for the observed 9216 MiB; this does not certify allocation')
    parser.add_argument('--owned-memory-size', type=lambda value: int(value, 0), default=None,
                        help='Explicit DarwinBoot contiguous window request, 256 MiB..8 GiB in 2 MiB steps')
    parser.add_argument('--root-match-volume-uuid', default=None,
                        help='/chosen/root-matching: select the root by the UUID of an IOMedia')
    parser.add_argument('--unique-chip-id', type=lambda value: int(value, 16), default=None,
                        help='/chosen/unique-chip-id (8 bytes) seeds XNU IOPlatformUUID; a software identity seed, not an Apple silicon ID')
    parser.add_argument('--chip-id', type=lambda value: int(value, 16), default=None,
                        help='/chosen/chip-id (4 bytes); must be supplied together with --unique-chip-id')
    parser.add_argument('--cpu-regs', default='0',
                        help='Comma-separated MPIDR affinity values, boot CPU 0 first. sm8550 numbers its cores 0x000..0x700 in Affinity1; more than one core adds /psci')
    parser.add_argument('--psci-method', choices=['smc', 'hvc'], default='smc',
                        help='/psci method for secondary-CPU start (the live FDT declares smc)')
    parser.add_argument('--packed-data-ramdisk', action='store_true',
                        help='Hand validated packed bytes to the native sparse block driver without a dense alias')
    parser.add_argument('--data-ramdisk', action='store_true',
                        help='/chosen/memory-map RAMDisk placeholder for a scratch Data seed')
    parser.add_argument('--trust-cache', action='store_true',
                        help='Zeroed TrustCache sidecar handoff placeholder')
    parser.add_argument('--gpu-addon', action='store_true',
                        help='Zeroed GpuAddon sidecar handoff placeholder in /chosen/memory-map')
    parser.add_argument('--ipad-identity', action='store_true',
                        help='/product and /buttons describe an iPad-class device without a Home button; the donor identity stays iPhone10,3/d22ap (D-004)')
    parser.add_argument('--persistent-data', action='store_true',
                        help='The Data seed is persistent, so /chosen/ephemeral-storage is omitted')
    parser.add_argument('--text-fixup', action='append', default=[],
                        help='/chosen/text-fixups entry: SYMBOL,OFFSET,ORIGHEX,NEWHEX (repeatable)')
    args = parser.parse_args()

    # --- argument validation --------------------------------------------
    # The base passes these independently: --chip-id comes from [payload.adt]
    # and --unique-chip-id from the command line or UNIXNU_UNIQUE_CHIP_ID
    # (payload.py:150-155). Rejecting a half pair would block a board that has
    # only one of them configured, so warn instead: XNU needs both to publish
    # IOPlatformUUID, and a lone property simply will not produce one.
    if (args.unique_chip_id is None) != (args.chip_id is None):
        print('warning: --unique-chip-id and --chip-id should be supplied together; '
              'IOPlatformUUID needs both, so the tree will carry only one', file=sys.stderr)
    if args.unique_chip_id is not None and not 0 < args.unique_chip_id < 1 << 64:
        parser.error('--unique-chip-id must fit 8 bytes and be nonzero')
    if args.chip_id is not None and not 0 < args.chip_id < 1 << 32:
        parser.error('--chip-id must fit 4 bytes and be nonzero')
    if args.owned_memory_size is not None and (
            not OWED_MIN <= args.owned_memory_size <= OWED_MAX
            or args.owned_memory_size % OWED_STEP):
        parser.error('Owned memory must be 256 MiB to 8 GiB, aligned to 2 MiB')
    if args.owned_memory_size is not None and args.owned_memory_size > args.dram_size:
        parser.error('Owned memory window must not exceed the advertised DRAM size')
    if DRAM_BASE % OWED_STEP:
        parser.error('The DRAM base must be 2 MiB aligned for the owned window')
    if args.dram_size <= 0 or args.dram_size % 0x1000:
        parser.error('--dram-size must be a positive multiple of 4 KiB')
    if args.data_ramdisk and args.packed_data_ramdisk:
        parser.error('--data-ramdisk and --packed-data-ramdisk are mutually exclusive')
    if args.persistent_data and not (args.data_ramdisk or args.packed_data_ramdisk):
        parser.error('--persistent-data describes a Data seed; pass one of the ramdisk flags')

    try:
        cpu_regs = [int(value, 0) for value in args.cpu_regs.split(',')]
    except ValueError:
        parser.error('--cpu-regs must be integers')
    if (not cpu_regs or cpu_regs[0] != 0 or len(set(cpu_regs)) != len(cpu_regs)
            or len(cpu_regs) > 8 or any(reg < 0 or reg > 0xffff or reg & 0xff for reg in cpu_regs)):
        parser.error('--cpu-regs: up to eight distinct Affinity1-numbered cores, boot CPU 0 first')

    # XNU parse: SYMBOL,OFFSET,ORIGHEX,NEWHEX (patches/xnu/native-text-fixup.patch).
    import re
    for fixup in args.text_fixup:
        if not re.fullmatch(r'[A-Za-z0-9_.\-]{1,63},[0-9a-fA-F]{1,16},(?:[0-9a-fA-F]{2}){1,16},(?:[0-9a-fA-F]{2}){1,16}', fixup):
            parser.error('malformed --text-fixup %r' % fixup)

    u32 = lambda value: struct.pack('<I', value)
    u64 = lambda value: struct.pack('<Q', value)

    # --- nodes -----------------------------------------------------------
    cpus = [node('cpu%d' % index, [
        ('state', b'running\0' if index == 0 else b'waiting\0'),
        ('reg', u32(reg)),
        ('device_type', b'cpu\0'),
        # The live FDT reports compatible = "qcom,kryo"; the Apple-side tree
        # names the real microarchitecture so the CPU driver can match it.
        ('compatible', b'arm,cortex-a715\0'),
        ('timebase-frequency', u32(TIMEBASE)),
    ]) for index, reg in enumerate(cpu_regs)]

    memory_map = []
    if args.packed_data_ramdisk:
        memory_map.append(('PackedRAMDisk', bytes(16)))
    elif args.data_ramdisk:
        memory_map.append(('RAMDisk', bytes(16)))
    if args.trust_cache:
        memory_map.append(('TrustCache', bytes(16)))
    if args.gpu_addon:
        memory_map.append(('GpuAddon', bytes(16)))

    chosen = [
        # A fresh seed on every build: ADT output is intentionally non-reproducible.
        ('random-seed', os.urandom(64)),
        # Without both of these XNU never publishes IOPlatformUUID, and callers
        # that ask gethostuuid() with a zero timeout (configd) block forever.
        *([('unique-chip-id', u64(args.unique_chip_id))] if args.unique_chip_id is not None else []),
        *([('chip-id', u32(args.chip_id))] if args.chip_id is not None else []),
        ('osenvironment', b'main\0'),
        # Dev-fused, undemoted board tuple (0,0,1,1) as MobileGestalt reads it,
        # so mobileactivationd takes its native "Hactivation" branch. These are
        # software identity properties established by ios-sweet tools/mkadt.py,
        # not reads of nuwa fuses.
        *([('certificate-production-status', u32(0)), ('effective-production-status-ap', u32(0)),
           ('certificate-security-mode', u32(1)), ('effective-security-mode-sep', u32(1))]
          if args.ipad_identity else []),
        # The Data seed's actual lifetime: volatile unless declared persistent.
        *([('ephemeral-storage', u32(1))]
          if (args.data_ramdisk or args.packed_data_ramdisk) and not args.persistent_data else []),
        *([('darwinboot-memory-size', u64(args.owned_memory_size))]
          if args.owned_memory_size else []),
        # Advertised bank, not a certification that firmware can allocate it.
        ('dram-base', u64(DRAM_BASE)),
        ('dram-size', u64(args.dram_size)),
        # Image4 hash algorithm selection only; asserts nothing about Apple silicon.
        ('crypto-hash-method', b'sha2-384\0'),
        *([('root-matching', ('<dict><key>IOProviderClass</key><string>IOMedia</string>'
                              '<key>IOPropertyMatch</key><dict><key>UUID</key><string>' +
                              args.root_match_volume_uuid.upper() + '</string></dict></dict>\0').encode())]
          if args.root_match_volume_uuid else []),
        # Keeps original AMFI enforcing platform code only; it does not relax it.
        ('amfi-only-platform-code', u32(1)),
        # NUL-separated table read by patches/xnu/native-text-fixup.patch.
        *([('text-fixups', b'\0'.join(entry.encode('ascii') for entry in args.text_fixup) + b'\0')]
          if args.text_fixup else []),
        *empty_nvram_proxy(),
    ]

    tree = node('device-tree', [
        # hw.product/hw.machine/hw.target come from the root model/target-type;
        # libMobileGestalt prefix-matches hw.product, so the iPad identity needs both.
        ('model', b'iPad7,1\0' if args.ipad_identity else ROOT_MODEL),
        *([('target-type', b'J120\0')] if args.ipad_identity else []),
        ('compatible', ROOT_COMPATIBLE),
        ('#address-cells', u32(2)),
        ('#size-cells', u32(2)),
    ], [
        node('chosen', chosen, [
            node('memory-map', memory_map),
            # Read by the original AppleImage4 at start-up; present and empty here.
            node('manifest-properties'),
        ]),
        node('cpus', children=cpus),
        *([node('psci', [('compatible', b'arm,psci-1.0\0'),
                         ('method', args.psci_method.encode() + b'\0')])] if len(cpus) > 1 else []),
        # Suspend/resume is not implemented for this board; use the original
        # root-domain policy input instead of letting the CPU park forever.
        node('defaults', [('sleep-disabled', u32(1))]),
        node('options', []),
        *([node('buttons', [('compatible', b'buttons\0'), ('device_type', b'buttons\0'),
                            # No 'menu' entry: nuwa has no Home button.
                            ('button-names', BUTTON_NAMES),
                            ('home-button-type', u32(2))])] if args.ipad_identity else []),
        # The original AppleImage4 panics without a product node.
        node('product', [('product-name', b'iPad Pro (12.9-inch) (2nd generation)\0' if args.ipad_identity else b'Xiaomi 13 Pro\0'),
                         ('model', b'xiaomi,nuwa\0'),
                         *([('product-description', b'iPad Pro (12.9-inch) (2nd generation)\0'),
                            ('artwork-device-idiom', b'pad\0'),
                            ('artwork-device-subtype', u32(2732)),
                            ('artwork-scale-factor', u32(2)),
                            ('artwork-display-gamut', b'P3\0'),
                            ('compatible-device-fallback', b'iPad6,7\0'),
                            ('thin-bezel', u32(1))] if args.ipad_identity else [])]),
        node('arm-io', [
            ('device_type', b'arm-io\0'),
            ('#address-cells', u32(2)),
            ('#size-cells', u32(2)),
            ('ranges', struct.pack('<QQQ', 0, ARMIO_BASE, ARMIO_WINDOW)),
        ], [
            node('intc', [('compatible', b'arm,gic-v3\0'),
                          ('reg', struct.pack('<4Q',
                                              GIC_DIST - ARMIO_BASE, GIC_DIST_SIZE,
                                              GIC_REDIST - ARMIO_BASE, GIC_REDIST_SIZE)),
                          ('redistributor-stride', u64(GIC_REDIST_STRIDE))]),
            # Class matching only: the real windows (0x1d84000 / 0x1d80000) sit
            # below ARMIO_BASE, so a child reg offset would be negative.
            node('ufshc', [('compatible', b'qcom,sm8550-ufshc\0')]),
        ]),
    ])

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(tree)
    print('nuwa ADT: %d bytes, dram %#x @ %#x, %d cpu(s), timebase %d Hz'
          % (len(tree), args.dram_size, DRAM_BASE, len(cpus), TIMEBASE))


if __name__ == '__main__':
    main()
