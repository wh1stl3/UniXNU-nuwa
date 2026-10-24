"""Build the first package that can actually enter the XNU kernel.

The verified USB-v3 transport (64 MiB FAT envelope in the boot image) already
proved that a 58 MB file can be carried and read. This script reuses that exact
container and swaps the payload: instead of a data blob plus an exit action, the
volume now carries a real kernel.macho, its Apple device tree, and a menu with
an `xnu` entry, so DarwinBoot's Boot() path runs for the first time.

What this changes relative to the fv-file-audit package:
  * firmware: the upstream-merged FD (2d606985) with no diagnostic driver, so
    nothing else touches the volume at ReadyToBoot
  * payload: kernel.macho (the early-security analysis prelink) plus
    kernel.macho.adt generated from the approved board values
  * menu: one `xnu` entry, no exit action

DarwinBoot allocates the kernel window from /chosen/darwinboot-memory-size
(DarwinBoot.c:559) and reports NO WINDOW with the largest free run when it
cannot (DarwinBoot.c:437-448). That failure path prints the UEFI memory map to
the screen, so a rejected window still yields the evidence this project needs.

Static packaging only. This script does not touch the device.
"""
import argparse
import hashlib
import json
import os
import struct
import subprocess
import sys
import tomllib
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import usb_ramdisk_package as transport  # noqa: E402

FIRMWARE = ROOT / 'out/upstream-firmware-40014018074/nuwa-firmware-40014018074'
FD_SHA = '2d606985ad768dcfaab66c2b28073c0a4c2820126b42b23286623fdc450e848f'
SHIM_SHA = '8a3b54765c895a0366539130fdf6e4e4a01e364fe7de067a38d0193606f9d462'
KERNEL_SHA = '1aeebf1352a86b0d'  # prefix; the full digest is recorded in the report
APPROVAL = 'XNU-FIRST-ENTRY-ANALYSIS'

UNIXNU_TOML = """version = 1

[boot]
timeout = 60
default = "xnu"

[kits]
autoload = false

[ui]
title = "NUWA XNU FIRST ENTRY - ANALYSIS BUILD"

[[entry]]
id = "xnu"
title = "Enter UniXNU iOS 16 kernel (analysis prelink)"
type = "xnu"
path = "Payloads/kernel.macho"
args = "-v"
"""


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def build_adt(output):
    """Generate the Apple device tree with the approved board values."""
    command = [sys.executable, str(ROOT / 'scripts/make-nuwa-adt.py'),
               '--output', str(output),
               '--dram-size', '0x240000000',
               '--owned-memory-size', '0x40000000',
               '--ipad-identity',
               '--cpu-regs', '0,256,512,768,1024,1280,1536,1792',
               '--psci-method', 'smc']
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise ValueError('ADT generation failed: %s' % result.stderr.strip())
    return command, result.stdout.strip()


def build_fat(work, image, adt, kernel):
    """Create the 64 MiB FAT with the loader configuration and the payload."""
    config = UNIXNU_TOML.encode()
    parsed = tomllib.loads(config.decode())
    if [entry['id'] for entry in parsed['entry']] != ['xnu']:
        raise ValueError('Unexpected menu configuration')
    commands = []

    def linux(path):
        return '/mnt/d/' + path.resolve().as_posix().split(':/', 1)[1]

    def run(*args):
        command = ['wsl', '-d', 'Ubuntu-22.04', '--', 'env', 'TZ=UTC', 'MTOOLS_SKIP_CHECK=1', *args]
        result = subprocess.run(command, capture_output=True, timeout=180)
        commands.append({'argv': command, 'exit_code': result.returncode,
                         'stdout': result.stdout.decode(errors='replace'),
                         'stderr': result.stderr.decode(errors='replace')})
        result.check_returncode()

    run('mformat', '-C', '-F', '-T', '131072', '-v', 'NUWAXNU', '-N', '584E5558', '-i', linux(image), '::')
    for name in ('::/EFI', '::/EFI/UniXNU', '::/EFI/UniXNU/Payloads'):
        run('mmd', '-i', linux(image), name)
    for name, raw, dest in (('unixnu.toml', config, '::/EFI/UniXNU/unixnu.toml'),
                            ('kernel.macho', kernel, '::/EFI/UniXNU/Payloads/kernel.macho'),
                            ('kernel.macho.adt', adt, '::/EFI/UniXNU/Payloads/kernel.macho.adt')):
        stage = work / name
        stage.write_bytes(raw)
        os.utime(stage, (315532800, 315532800))
        run('mcopy', '-m', '-i', linux(image), linux(stage), dest)
        readback = work / ('readback-' + name)
        run('mcopy', '-i', linux(image), dest, linux(readback))
        if sha(readback.read_bytes()) != sha(raw):
            raise ValueError('FAT readback differs: ' + name)
    run('mdir', '-i', linux(image), '-/', '::/')
    return parsed, commands


def validate(path):
    """Re-derive the package from the recorded image and re-read the payload.

    The image is parsed back into its header, kernel and ramdisk envelope, the
    FAT is checked against its recorded digest and CRC, and the two payload
    files are copied out of the FAT with mtools and hashed. That last step is
    what makes this a check of the shipped bytes rather than of the build
    script's own bookkeeping.
    """
    report = json.loads(path.read_text(encoding='utf-8'))
    if 'entry_probe' in report:
        from kernel_entry_probe_inputs import validate as validate_probe
        validate_probe(report['entry_probe'], report['kernel_sha256'])
    if report.get('approval') != APPROVAL:
        raise ValueError('Unexpected approval for the XNU entry package')
    if (report.get('header_version') != 3 or not report.get('xnu_included')
            or not report.get('fat_included') or report.get('appended_dtb')
            or report.get('original_boot_sha256') != transport.STOCK_SHA):
        raise ValueError('Package metadata outside the approved shape')
    image = (ROOT / report['image_path']).read_bytes()
    if sha(image) != report['image_sha256'] or len(image) != report['image_bytes']:
        raise ValueError('Image digest or length changed')
    kernel_size, ramdisk_size = struct.unpack_from('<II', image, 8)
    ramdisk_at = 4096 + ((kernel_size + 4095) // 4096) * 4096
    ramdisk = image[ramdisk_at:ramdisk_at + ramdisk_size]
    if ramdisk[:16] != transport.MAGIC:
        raise ValueError('Ramdisk envelope magic changed')
    version, sector_size, fat_bytes, crc = struct.unpack_from('<IIQI', ramdisk, 16)
    fat = ramdisk[64:64 + fat_bytes]
    if len(fat) != report['fat_bytes'] or sha(fat) != report['fat_sha256']:
        raise ValueError('FAT digest changed')
    if zlib.crc32(fat) != crc:
        raise ValueError('FAT CRC mismatch')
    if sha(image[4096:4096 + kernel_size]) != report['fd_sha256']:
        # the kernel field is shim+fd; compare the firmware digest separately
        fd_digest = sha(image[4096 + 112:4096 + kernel_size])
        if fd_digest != report['fd_sha256']:
            raise ValueError('Firmware digest changed')
    if sha(image[4096:4096 + 112]) != report['shim_sha256']:
        raise ValueError('Boot shim digest changed')
    # Re-read the payload files out of the shipped FAT.
    work = ROOT / 'out/xnu-first-entry-validate'
    if work.exists():
        raise ValueError('Fresh validation work directory required')
    work.mkdir(parents=True)
    fat_path = work / 'payload.fat.img'
    fat_path.write_bytes(fat)

    def linux(path):
        return '/mnt/d/' + path.resolve().as_posix().split(':/', 1)[1]

    for name, dest, expected in (('kernel.macho', '::/EFI/UniXNU/Payloads/kernel.macho',
                                  report['kernel_sha256']),
                                 ('kernel.macho.adt', '::/EFI/UniXNU/Payloads/kernel.macho.adt',
                                  report['read_file_sha256'])):
        target = work / name
        command = ['wsl', '-d', 'Ubuntu-22.04', '--', 'env', 'TZ=UTC', 'MTOOLS_SKIP_CHECK=1',
                   'mcopy', '-i', linux(fat_path), dest, linux(target)]
        result = subprocess.run(command, capture_output=True, timeout=180)
        if result.returncode != 0:
            raise ValueError('FAT readback failed for %s: %s' % (name, result.stderr.decode()))
        if sha(target.read_bytes()) != expected:
            raise ValueError('FAT readback digest differs for ' + name)
    for path in work.glob('*'):
        path.unlink()
    work.rmdir()
    return dict(image_sha256=report['image_sha256'], fat_sha256=report['fat_sha256'],
                kernel_sha256=report['kernel_sha256'], adt_sha256=report['read_file_sha256'])


def main():
    cli = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    cli.add_argument('--work', type=Path, help='fresh directory under out/')
    cli.add_argument('--output', type=Path, required=True, help='fresh report under reports/')
    cli.add_argument('--kernel', type=Path,
                     default=ROOT / 'out/earlysec-2026-10-24/kernel-prelinked-earlysec.macho')
    cli.add_argument('--validate', action='store_true',
                     help='Re-derive and re-read an existing package report instead of building')
    cli.add_argument('--entry-probe', type=Path,
                     help='Bind a diagnostic kernel to its static and software-execution reports')
    args = cli.parse_args()

    if args.validate:
        print(json.dumps(validate(args.output)))
        return

    work = args.work.resolve()
    output = args.output.resolve()
    if not work.is_relative_to(ROOT / 'out/trial-boot') or work.exists():
        # The trial driver only loads candidates from out/trial-boot, so the
        # image has to be produced there rather than in a private directory.
        raise ValueError('fresh work directory under out/trial-boot required')
    if not output.is_relative_to(ROOT / 'reports') or output.exists():
        raise ValueError('fresh report under reports/ required')

    fd = (FIRMWARE / 'build/FV/SILICIUM_UEFI.fd').read_bytes()
    shim = (FIRMWARE / 'shim/shim.bin').read_bytes()
    stock = transport.STOCK.read_bytes()
    kernel = args.kernel.read_bytes()
    probe = None
    if args.entry_probe:
        from kernel_entry_probe_inputs import metadata, validate as validate_probe
        probe = metadata(args.entry_probe)
        validate_probe(probe, sha(kernel))
        global UNIXNU_TOML
        # Bump this label whenever the band set changes so a recording cannot be
        # mistaken for an earlier package.
        UNIXNU_TOML = UNIXNU_TOML.replace('NUWA XNU FIRST ENTRY - ANALYSIS BUILD', 'NUWA XNU ENTRY PROBE 11')
        UNIXNU_TOML = UNIXNU_TOML.replace('Enter UniXNU iOS 16 kernel (analysis prelink)', 'XNU ENTRY PROBE 11 - DENSE LADDER GUARD IN PROBE PAGE')
    if sha(fd) != FD_SHA or len(fd) != 3145728:
        raise ValueError('Firmware FD changed')
    if sha(shim) != SHIM_SHA:
        raise ValueError('Boot shim changed')
    if sha(stock) != transport.STOCK_SHA:
        raise ValueError('Original recovery image changed')
    if not kernel.startswith(b'\xcf\xfa\xed\xfe'):
        raise ValueError('Kernel is not a little-endian Mach-O')

    work.mkdir(parents=True)
    adt_path = work / 'kernel.macho.adt'
    adt_command, adt_stdout = build_adt(adt_path)
    adt = adt_path.read_bytes()

    fat_path = work / 'payload.fat.img'
    parsed, commands = build_fat(work, fat_path, adt, kernel)
    fat = fat_path.read_bytes()
    if len(fat) != 67108864:
        raise ValueError('FAT must be 64 MiB')

    envelope = transport.MAGIC + struct.pack('<IIQI28x', 1, 64, len(fat), zlib.crc32(fat)) + fat
    image = transport.compose(stock[:4096], shim + fd, envelope, 3)
    readback = transport.inspect_container(image, stock[:4096], shim + fd, envelope, 3)
    image_path = work / 'boot-xnu-first-entry.img'
    image_path.write_bytes(image)

    report = {
        'scope': 'static packaging of the first XNU kernel entry candidate; no device action',
        'approval': APPROVAL,
        'run_id': None,
        # --- fields the trial driver reads -------------------------------
        'image_path': image_path.relative_to(ROOT).as_posix(),
        'image_sha256': sha(image),
        'image_bytes': len(image),
        'header_version': 3,
        'xnu_included': True,
        'fat_included': True,
        'appended_dtb': False,
        'adt_included': True,
        'original_boot_sha256': sha(stock),
        'fd_sha256': sha(fd),
        'shim_sha256': sha(shim),
        'kernel_bytes': len(kernel),
        'kernel_sha256': sha(kernel),
        'fat_bytes': len(fat),
        'fat_sha256': sha(fat),
        'read_file_bytes': len(adt),
        'read_file_sha256': sha(adt),
        'success_requires': 'menu shows the xnu entry and DarwinBoot either reports the window '
                            'outcome on screen or the kernel console appears; a fastboot ACK alone '
                            'is not a process log',
        # --- detail ------------------------------------------------------
        'firmware': {'source': 'CI 40014018074 upstream-merged profile (no diagnostic driver)',
                      'fd_bytes': len(fd), 'shim_bytes': len(shim)},
        'kernel_source': {'path': str(args.kernel),
                          'source': 'analysis prelink with early_security_initializers configured',
                          'loadable': False, 'runtime_qualified': False},
        'adt_detail': {'command': adt_command, 'stdout': adt_stdout,
                       'dram_size': '0x240000000', 'owned_memory_size': '0x40000000',
                       'cpu_regs': '0,256,512,768,1024,1280,1536,1792', 'psci_method': 'smc',
                       'sidecar_placeholders': False,
                       'note': 'no RAMDisk/TrustCache/GpuAddon placeholder, so the loader takes the '
                               'no-sidecar path in DarwinBoot.c:561-567'},
        'fat_detail': {'config': parsed,
                       'exact_files': ['EFI/UniXNU/unixnu.toml',
                                       'EFI/UniXNU/Payloads/kernel.macho',
                                       'EFI/UniXNU/Payloads/kernel.macho.adt']},
        'container_readback': readback,
        'expected_screen_outcomes': [
            'menu shows the xnu entry, then NO WINDOW <size> BIG RUN <bytes> @ <addr> plus FREE rows: '
            'the window request was rejected and the UEFI memory map is now known',
            'any other line from DarwinBoot before the handoff, e.g. unsupported inputs or exception level',
            'a kernel console or panic screen: the window was granted and the kernel was entered',
        ],
        'recovery': 'the original stock boot is preserved as the image header; after the trial the '
                    'stock boot is loaded back and Android must report boot_completed=1 with the '
                    'same boot_a/vendor_boot_a/init_boot_a digests',
        'not_proven': [
            'that the analysis prelink is loadable: it is explicitly loadable=false and runtime_qualified=false',
            'that the UEFI memory map can satisfy a 1 GiB contiguous window',
            'that the kernel reaches userspace or boots iOS',
        ],
        'device_executed': False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    if probe:
        report['entry_probe'] = probe
        report['scope'] = 'Diagnostic XNU entry probe with BCM-only MMIO suppressed and early exception display; no device action'
        report['kernel_source']['source'] = 'hash-pinned early-security prelink plus bounded native entry diagnostic patches'
        report['success_requires'] = 'Blue band at row 256 proves the XNU entry branch executed; yellow row 352 and magenta row 448 identify later pre-MMU stages. Red row 544 captures ESR/ELR/FAR. Green/menu/ACK alone do not prove XNU execution.'
        report['expected_screen_outcomes'] = [report['success_requires'], 'Any later XNU text or panic requires separate attribution; no band proves MMU enabled or iOS started']
        report['not_proven'] = ['Real nuwa execution of this candidate', 'MMU activation and arm_init', 'Native timer/interrupt driver readiness', 'Full donor/native ABI or iOS boot']
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'image_bytes': len(image), 'image_sha256': sha(image),
                      'kernel_sha256': sha(kernel), 'adt_sha256': sha(adt),
                      'fat_sha256': sha(fat)}))


if __name__ == '__main__':
    main()
