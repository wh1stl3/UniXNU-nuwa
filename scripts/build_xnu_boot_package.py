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

def root_context(revision):
    if revision>=33:
        from nuwa_exec_detail_launch_context import API
        return API
    if revision>=32:
        from nuwa_exec_launch_context import API
        return API
    if revision>=31:
        from nuwa_bsd_launch_context import API
        return API
    import nuwa_root_launch_context
    return nuwa_root_launch_context


def build_adt(output,root_ramdisk=False):
    """Generate the Apple device tree with the approved board values."""
    command = [sys.executable, str(ROOT / 'scripts/make-nuwa-adt.py'),
               '--output', str(output),
               '--dram-size', '0x240000000',
               '--owned-memory-size', '0x40000000',
               '--ipad-identity',
               '--cpu-regs', '0,256,512,768,1024,1280,1536,1792',
               '--psci-method', 'smc']
    if root_ramdisk:command.append('--data-ramdisk')
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise ValueError('ADT generation failed: %s' % result.stderr.strip())
    return command, result.stdout.strip()


def build_fat(work, image, adt, kernel, ramdisk=None):
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

    run('mformat', '-C', '-F', '-T', '393216' if ramdisk is not None else '131072', '-v', 'NUWAXNU', '-N', '584E5558', '-i', linux(image), '::')
    for name in ('::/EFI', '::/EFI/UniXNU', '::/EFI/UniXNU/Payloads'):
        run('mmd', '-i', linux(image), name)
    files=[('unixnu.toml', config, '::/EFI/UniXNU/unixnu.toml'),
                            ('kernel.macho', kernel, '::/EFI/UniXNU/Payloads/kernel.macho'),
                            ('kernel.macho.adt', adt, '::/EFI/UniXNU/Payloads/kernel.macho.adt')]
    if ramdisk is not None:files.append(('root-restore.apfs',ramdisk,'::/EFI/UniXNU/Payloads/root-restore.apfs'))
    for name, raw, dest in files:
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
        build=json.loads((ROOT/report['entry_probe']['build']['path']).read_text())
        if build.get('probe_revision',0)>=27 and 'image4_launch_context' not in report:
            raise ValueError('Measured launch context cannot be removed from revision 27')
        if build.get('probe_revision',0)>=30:
            if 'root_ramdisk' not in report or report.get('root_mount_diagnostic')!=build.get('root_mount_diagnostic'):raise ValueError('Real root image/endpoint removed')
            ctx=root_context(build['probe_revision']);POLICY,ARGS,PAYLOAD_SHA=ctx.POLICY,ctx.ARGS,ctx.PAYLOAD_SHA
            if report['root_ramdisk'].get('policy')!=POLICY or report['root_ramdisk'].get('sha256')!=PAYLOAD_SHA or report['fat_bytes']!=201326592:raise ValueError('Root transport/policy differs')
        for case in ('normal','occupied-probe','bad-topology','occupied-fb'):
            name='transition-'+case
            if name in report['entry_probe']:
                transition=json.loads((ROOT/report['entry_probe'][name]['path']).read_text())
                if transition['input']['adt_sha256']!=report['read_file_sha256']:
                    raise ValueError('Transition tests must use the exact shipped ADT')
    if 'console-policy' in report.get('entry_probe',{}):
        policy=json.loads((ROOT/report['entry_probe']['console-policy']['path']).read_text())
        if policy['adt_sha256']!=report['read_file_sha256']:raise ValueError('Console policy requires exact shipped ADT')
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

    payloads=[('kernel.macho', '::/EFI/UniXNU/Payloads/kernel.macho',
                                  report['kernel_sha256']),
                                 ('kernel.macho.adt', '::/EFI/UniXNU/Payloads/kernel.macho.adt',
                                  report['read_file_sha256'])]
    if 'root_ramdisk' in report:payloads.append(('root-restore.apfs','::/EFI/UniXNU/Payloads/root-restore.apfs',report['root_ramdisk']['sha256']))
    for name, dest, expected in payloads:
        target = work / name
        command = ['wsl', '-d', 'Ubuntu-22.04', '--', 'env', 'TZ=UTC', 'MTOOLS_SKIP_CHECK=1',
                   'mcopy', '-i', linux(fat_path), dest, linux(target)]
        result = subprocess.run(command, capture_output=True, timeout=180)
        if result.returncode != 0:
            raise ValueError('FAT readback failed for %s: %s' % (name, result.stderr.decode()))
        if sha(target.read_bytes()) != expected:
            raise ValueError('FAT readback digest differs for ' + name)
    if 'image4_launch_context' in report:
        from nuwa_launch_context import validate as validate_context
        fd_path=work/'firmware.fd';shim_path=work/'boot-shim.bin'
        fd_path.write_bytes(image[4096+112:4096+kernel_size])
        shim_path.write_bytes(image[4096:4096+112])
        proof=validate_context((work/'kernel.macho.adt').read_bytes(),work/'kernel.macho',fd_path,shim_path)
        if proof!=report['image4_launch_context']:
            raise ValueError('Shipped launch context/component proof changed')
        if 'root_ramdisk' in report:
            ctx=root_context(build['probe_revision']);validate_root,ARGS=ctx.validate,ctx.ARGS
            root_proof=validate_root((work/'kernel.macho.adt').read_bytes(),work/'kernel.macho',fd_path,shim_path,work/'root-restore.apfs')
            if root_proof['policy']!=report['root_ramdisk']['policy']:raise ValueError('Shipped root policy differs')
            menu=work/'unixnu.toml'
            cmd=['wsl','-d','Ubuntu-22.04','--','env','TZ=UTC','MTOOLS_SKIP_CHECK=1','mcopy','-i',linux(fat_path),'::/EFI/UniXNU/unixnu.toml',linux(menu)]
            subprocess.run(cmd,capture_output=True,timeout=180,check=True)
            parsed=tomllib.loads(menu.read_text());entry=parsed['entry']
            if len(entry)!=1 or entry[0].get('args')!=ARGS or entry[0].get('initrd')!='Payloads/root-restore.apfs':raise ValueError('Actual menu does not bind measured root/arguments')
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
    cli.add_argument('--adt', type=Path, help='Reuse an already tested exact ADT, rather than generate new entropy')
    cli.add_argument('--root-ramdisk',type=Path,help='Pinned real APFS mount-only diagnostic; requires revision30')
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
        revision=json.loads(args.entry_probe.read_text()).get('probe_revision',0)
        UNIXNU_TOML = UNIXNU_TOML.replace('NUWA XNU FIRST ENTRY - ANALYSIS BUILD', 'NUWA XNU ENTRY PROBE 14')
        UNIXNU_TOML = UNIXNU_TOML.replace('Enter UniXNU iOS 16 kernel (analysis prelink)', 'XNU ENTRY PROBE 14 - RELOCATED HOOKS AND FIELD IDS')
    if probe and revision>=22:
        UNIXNU_TOML=UNIXNU_TOML.replace('PROBE 14','PROBE 15').replace('RELOCATED HOOKS AND FIELD IDS','PMAP TRANSITION MAPPING')
    if probe and revision>=23:
        UNIXNU_TOML=UNIXNU_TOML.replace('PROBE 15','PROBE 16').replace('PMAP TRANSITION MAPPING','DT PANIC POLICY AND CONSOLE')
    if probe and revision>=24:
        UNIXNU_TOML=UNIXNU_TOML.replace('PROBE 16','PROBE 17').replace('DT PANIC POLICY AND CONSOLE','DENSE BOOTSTRAP CALL AND RETURN')
    if probe and revision>=25:
        UNIXNU_TOML=UNIXNU_TOML.replace('PROBE 17','PROBE 18').replace('DENSE BOOTSTRAP CALL AND RETURN','FIRST THREAD IOKIT BSD AND DISPLAY')
    if probe and revision>=27:
        UNIXNU_TOML=UNIXNU_TOML.replace('PROBE 18','PROBE 19').replace('FIRST THREAD IOKIT BSD AND DISPLAY','IMAGE4 INPUTS TO BSD ROOT')
    if probe and revision>=28:
        UNIXNU_TOML=UNIXNU_TOML.replace('PROBE 19','PROBE 20').replace('IMAGE4 INPUTS TO BSD ROOT','NATIVE PTHREAD OSKEXT TO BSD ROOT')
    if probe and revision>=29:
        UNIXNU_TOML=UNIXNU_TOML.replace('PROBE 20','PROBE 21').replace('NATIVE PTHREAD OSKEXT TO BSD ROOT','ROOT RESOURCE AND MEDIA WAIT TRACE')
    root_ramdisk=None
    if args.root_ramdisk:
        if not probe or revision not in (30,31,32,33,34):raise ValueError('Real root diagnostic requires revision30..32 boundary')
        ctx=root_context(revision);PAYLOAD_SHA,ARGS,validate_report=ctx.PAYLOAD_SHA,ctx.ARGS,ctx.validate_report
        root_proof=json.loads((ROOT/probe['root-launch']['path']).read_text());validate_report(root_proof)
        root_ramdisk=args.root_ramdisk.read_bytes()
        if sha(root_ramdisk)!=PAYLOAD_SHA:raise ValueError('Pinned real root image changed')
        UNIXNU_TOML=UNIXNU_TOML.replace('PROBE 21','PROBE 22').replace('ROOT RESOURCE AND MEDIA WAIT TRACE','REAL APFS RAMDISK MOUNT THEN HALT')
        UNIXNU_TOML=UNIXNU_TOML.replace('args = "-v"','args = "'+ARGS+'"\ninitrd = "Payloads/root-restore.apfs"')
        if revision>=31:
            UNIXNU_TOML=UNIXNU_TOML.replace('PROBE 22','PROBE 23').replace('REAL APFS RAMDISK MOUNT THEN HALT','CONTINUOUS BSD TO FIRST INIT EXEC')
        if revision>=32:
            UNIXNU_TOML=UNIXNU_TOML.replace('PROBE 23','PROBE 24').replace('CONTINUOUS BSD TO FIRST INIT EXEC','NATIVE EXEC ACTIVATION AND SIGNATURE TRACE')
        if revision>=33:
            UNIXNU_TOML=UNIXNU_TOML.replace('PROBE 24','PROBE 25').replace('NATIVE EXEC ACTIVATION AND SIGNATURE TRACE','CONTINUOUS EXEC WITH PERSISTENT NATIVE ERRORS')
        if revision>=34:
            UNIXNU_TOML=UNIXNU_TOML.replace('PROBE 25','PROBE 26').replace('CONTINUOUS EXEC WITH PERSISTENT NATIVE ERRORS','NATIVE EXEC AND DYLD PATH ERROR TRACE')
    elif probe and revision>=30:raise ValueError('Mount-only candidate must bind the real RAMDisk')
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
    if args.adt:
        if not args.adt.resolve().is_relative_to(ROOT/'out'):raise ValueError('External ADT must be under out/')
        adt_path.write_bytes(args.adt.read_bytes())
        adt_command=['reuse-exact-tested-adt',str(args.adt.resolve())];adt_stdout='Exact ADT bytes retained'
    else:
        adt_command, adt_stdout = build_adt(adt_path)
    adt = adt_path.read_bytes()
    launch_context=None
    if probe and revision>=27:
        if not args.adt:raise ValueError('Revision 27 requires exact measured launch ADT')
        from nuwa_launch_context import validate as validate_context
        launch_context=validate_context(adt,args.kernel,FIRMWARE/'build/FV/SILICIUM_UEFI.fd',FIRMWARE/'shim/shim.bin')
        bound_context=json.loads((ROOT/probe['launch-context']['path']).read_text())
        if bound_context['adt_sha256']!=sha(adt) or bound_context['manifest_sha384']!=launch_context['manifest_sha384']:
            raise ValueError('Launch context evidence does not bind the shipped ADT')

    fat_path = work / 'payload.fat.img'
    parsed, commands = build_fat(work, fat_path, adt, kernel,root_ramdisk)
    fat = fat_path.read_bytes()
    if len(fat) != (201326592 if root_ramdisk is not None else 67108864):
        raise ValueError('Unexpected bounded FAT capacity')

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
        if root_ramdisk is not None:
            report['root_ramdisk']=dict(path=args.root_ramdisk.resolve().relative_to(ROOT).as_posix(),sha256=sha(root_ramdisk),bytes=len(root_ramdisk),policy=root_proof['policy'])
        report['scope'] = 'Diagnostic XNU entry probe with BCM-only MMIO suppressed and early exception display; no device action'
        report['kernel_source']['source'] = 'hash-pinned early-security prelink plus bounded native entry diagnostic patches'
        report['success_requires'] = 'Revision 21: left stage tiles at y256/288/320/352/384 show entry/tables/pre-MMU/cyan/white. Tagged data at x256,y224..775 includes A032=init eventi and A033=its intended address. Panic/fault records require the bound build screen layout; ACK alone is not execution evidence.'
        report['probe_screen'] = json.loads(args.entry_probe.read_text())['screen']
        if revision>=24:
            report['probe_screen']['dense_bootstrap']=json.loads(args.entry_probe.read_text())['dense_bootstrap']
            report['success_requires']='PROBE17: power-key Enter starts XNU; capture original left tiles, A-fields, and right grid x832..1295/y256..759. Blue grid cell=call edge reached; green=continuation reached. Decode IDs using bound dense_bootstrap.edges. Unlit cells do not prove the kernel stopped there.'
        if revision>=25:
            report['probe_screen']['native_vector_handoff']=json.loads(args.entry_probe.read_text())['native_vector_handoff']
            report['probe_screen']['display_readback']=json.loads(args.entry_probe.read_text())['display_readback']
            report['success_requires']='PROBE18: power-key Enter; yellow entry / magenta context checkpoints / blue call / green continuation. Grid uses 24-pixel row pitch. A02A=mismatched pixels of the white/cyan band at y224, A02B=last checking stage, A02C=1 native vectors restored (2=rejected). CPU readback is not physical scanout proof.'
        if revision>=27:
            report['image4_launch_context']=launch_context
            report['success_requires']=report['success_requires'].replace('PROBE18:','PROBE19:')+' Image4 native initializer RET is modeled only; ID89 is MAC continuation, ID6 is BSD entry, ID7/8 are root discovery/mount entry. Non-Apple host-measured launch inputs; no hardware replay protection or Apple trusted-boot claim.'
        if revision>=28:
            report['pthread_startup']=json.loads(args.entry_probe.read_text())['pthread_startup']
            report['success_requires']=report['success_requires'].replace('PROBE19:','PROBE20:')+' IDs178/179=before/after native OSKext load; ID180=function table non-NULL; ID181=already registered. Loader lifecycle and initializer body require physical observation.'
        if revision>=29:
            report['success_requires']=report['success_requires'].replace('PROBE20:','PROBE21:')+' IDs182..211 trace native root calls and continuations. 184/185=IOBSD resource wait, 200/201=root matching wait. Blue without green is reachability only; wait implementation and IRQ/timer require separate evidence.'
        if revision>=30:
            report['root_mount_diagnostic']=json.loads(args.entry_probe.read_text())['root_mount_diagnostic']
            report['success_requires']=report['success_requires'].replace('PROBE21:','PROBE22:')+' Real APFS on RAMDisk, rd=md0. A035=actual native vfs_mountroot return, ID212 green=zero return, ID213 red=error; deliberate halt before restore userspace. Enlarged transport is not yet nuwa-qualified.'
        if revision>=31:
            report['success_requires']='PROBE23: continue native root, secure root, BSD completion and init preparation without intermediate halts. A035 records native mount return, IDs212/213 observe success/error and continue. IDs214/215/216=bsdinit_task/load_init_program/load_init_program_at_path entries; ID217=before first ___mac_execve, ID218 magenta=sole intentional endpoint, A02B=217. No restore userspace executed; all native errors preserved.'
        if revision>=32:
            report['exec_trace']=json.loads(args.entry_probe.read_text())['exec_trace']
            report['success_requires']='PROBE24: mount and first exec continue; side panel IDs220..238 observe native activation/task switch/signature/cleanup. A02D activation errno, A02E signature errno, A02F task switch observed, A030 actual exec return, A032 MAC entry errno; stage-specific fields overwrite old WFE data. ID239 magenta/A02B239 means unreviewed restore task release held, not execution success. Original errors/panic/fallback retained; zero activation alone is not success.'
        if revision>=33:
            report['success_requires']=report['success_requires'].replace('PROBE24:', 'PROBE25:')+' Revision33 always renders actual activation/exec/signature post-call values, retains last completed error across fallback; A02C counts init exec attempts. No new endpoint.'
        if revision>=34:
            report['success_requires']=report['success_requires'].replace('PROBE25:', 'PROBE26:')+' IDs240..263=exec and dyld calls/continuations. A02E=first nonzero stage call ID per attempt, A032=its raw native return (errno or Mach loader status according to callee), A02C=attempt count. Aggregate activation/exec remain A02D/A030. No forced success or path substitution.'
        report['expected_screen_outcomes'] = [report['success_requires'], 'Any later XNU text or panic requires separate attribution; no band proves MMU enabled or iOS started']
        report['not_proven'] = ['Real nuwa execution of this candidate', 'MMU activation and arm_init', 'Native timer/interrupt driver readiness', 'Full donor/native ABI or iOS boot']
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'image_bytes': len(image), 'image_sha256': sha(image),
                      'kernel_sha256': sha(kernel), 'adt_sha256': sha(adt),
                      'fat_sha256': sha(fat)}))


if __name__ == '__main__':
    main()
