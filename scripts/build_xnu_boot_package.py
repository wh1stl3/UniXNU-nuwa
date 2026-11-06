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
        if not probe or revision not in (30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,64,65,66,67,68,69,70,71,72):raise ValueError('Real root diagnostic requires a supported revision30..37 boundary')
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
        if revision>=35:
            UNIXNU_TOML=UNIXNU_TOML.replace('PROBE 26','PROBE 27').replace('NATIVE EXEC AND DYLD PATH ERROR TRACE','NATIVE TYPE4 COMPRESSION STARTUP AND CONTINUOUS EXEC')
        if revision>=36:
            UNIXNU_TOML=UNIXNU_TOML.replace('PROBE 27','PROBE 28').replace('NATIVE TYPE4 COMPRESSION STARTUP AND CONTINUOUS EXEC','SCOPED NATIVE MAC AND FILESYSTEM READ BOUNDARIES')
        if revision>=37:
            UNIXNU_TOML=UNIXNU_TOML.replace('PROBE 28','PROBE 29').replace('SCOPED NATIVE MAC AND FILESYSTEM READ BOUNDARIES','SCOPED READ TARGET AND CANDIDATE ENTRY')
        if revision>=38:
            UNIXNU_TOML=UNIXNU_TOML.replace('PROBE 29','PROBE 30').replace('SCOPED READ TARGET AND CANDIDATE ENTRY','NATIVE READ BODY CALLS AND RETURNS')
        if revision>=39:
            UNIXNU_TOML=UNIXNU_TOML.replace('PROBE 30','PROBE 31').replace('NATIVE READ BODY CALLS AND RETURNS','READ INITIALIZATION AND NATIVE BODY TRACE')
        if revision>=40:
            UNIXNU_TOML=UNIXNU_TOML.replace('PROBE 31','PROBE 32').replace('READ INITIALIZATION AND NATIVE BODY TRACE','SINGLE PASS DISPLAY AND NATIVE READ CONTINUATION')
        if revision>=41:
            UNIXNU_TOML=UNIXNU_TOML.replace('PROBE 32','PROBE 33').replace('SINGLE PASS DISPLAY AND NATIVE READ CONTINUATION','NATIVE READ GRID WITH DEFERRED BODY HEX')
        if revision>=42:
            UNIXNU_TOML=UNIXNU_TOML.replace('PROBE 33','PROBE 34').replace('NATIVE READ GRID WITH DEFERRED BODY HEX','NATIVE COMPRESSED READ CONTINUOUS PATH')
        if revision>=43:
            UNIXNU_TOML=UNIXNU_TOML.replace('PROBE 34','PROBE 35').replace('NATIVE COMPRESSED READ CONTINUOUS PATH','CONTINUOUS READ WITH SHARED HEX RENDERER')
        if revision>=44:
            UNIXNU_TOML=UNIXNU_TOML.replace('PROBE 35','PROBE 36').replace('CONTINUOUS READ WITH SHARED HEX RENDERER','CONTINUOUS READ WITH COMPACT STRIPS')
        if revision>=45:
            UNIXNU_TOML=UNIXNU_TOML.replace('PROBE 36','PROBE 37').replace('CONTINUOUS READ WITH COMPACT STRIPS','NATIVE FETCH AND TYPE4 CALLBACK CONTINUATION')
        if revision>=46:
            UNIXNU_TOML=UNIXNU_TOML.replace('PROBE 37','PROBE 38').replace('NATIVE FETCH AND TYPE4 CALLBACK CONTINUATION','NATIVE ALLOCATION VECTORS AND DECODE CONTINUATION')
        if revision>=47:
            UNIXNU_TOML=UNIXNU_TOML.replace('PROBE 38','PROBE 39').replace('NATIVE ALLOCATION VECTORS AND DECODE CONTINUATION','SECOND ALLOCATION RESULTS AND ERROR CONTINUATION')
        if revision>=48:
            UNIXNU_TOML=UNIXNU_TOML.replace('PROBE 39','PROBE 40').replace('SECOND ALLOCATION RESULTS AND ERROR CONTINUATION','CONTINUOUS MAINLINE WITH DELTA HEX')
        if revision>=49:
            UNIXNU_TOML=UNIXNU_TOML.replace('PROBE 40','PROBE 41').replace('CONTINUOUS MAINLINE WITH DELTA HEX','RESOURCEFORK LIVE DISPATCH R5')
            if json.loads(args.entry_probe.read_text()).get('delta_hex',{}).get('reserved_x18_live_state') is False:
                UNIXNU_TOML=UNIXNU_TOML.replace('PROBE 41','PROBE 42').replace('RESOURCEFORK LIVE DISPATCH R5','NATIVE CONTINUATION X18 SAFE HEX')
            if json.loads(args.entry_probe.read_text()).get('read_flow',{}).get('resource_handler'):
                UNIXNU_TOML=UNIXNU_TOML.replace('PROBE 42','PROBE 43').replace('NATIVE CONTINUATION X18 SAFE HEX','APFS RESOURCE HANDLER CALL AND RETURN')
            if json.loads(args.entry_probe.read_text()).get('read_flow',{}).get('resource_chain'):
                UNIXNU_TOML=UNIXNU_TOML.replace('PROBE 43','PROBE 44').replace('APFS RESOURCE HANDLER CALL AND RETURN','RESOURCE LOOKUP READ AND EXEC CONTINUATION')
            if json.loads(args.entry_probe.read_text()).get('read_flow',{}).get('resource_cluster'):
                UNIXNU_TOML=UNIXNU_TOML.replace('PROBE 44','PROBE 45').replace('RESOURCE LOOKUP READ AND EXEC CONTINUATION','UBC UPL IO AND NATIVE EXEC CONTINUATION')
                if json.loads(args.entry_probe.read_text())['read_flow']['resource_cluster'].get('cache_progress_revision',0)>=46:
                    UNIXNU_TOML=UNIXNU_TOML.replace('PROBE 45','PROBE 46').replace('UBC UPL IO AND NATIVE EXEC CONTINUATION','CACHE PROGRESS PREFETCH CLEANUP AND EXEC CONTINUATION')
                    if json.loads(args.entry_probe.read_text())['read_flow']['resource_cluster'].get('cache_progress_revision')>=47:
                        UNIXNU_TOML=UNIXNU_TOML.replace('PROBE 46','PROBE 47').replace('CACHE PROGRESS PREFETCH CLEANUP AND EXEC CONTINUATION','VM CACHE LOCK PAGE COPY AND EXEC CONTINUATION')
                    if json.loads(args.entry_probe.read_text())['read_flow']['resource_cluster'].get('cache_progress_revision',0)>=48:
                        UNIXNU_TOML=UNIXNU_TOML.replace('PROBE 47','PROBE 48').replace('VM CACHE LOCK PAGE COPY AND EXEC CONTINUATION','VM CACHE TILES AND EXEC CONTINUATION')
                    if json.loads(args.entry_probe.read_text())['read_flow']['resource_cluster'].get('cache_progress_revision',0)>=49:
                        UNIXNU_TOML=UNIXNU_TOML.replace('PROBE 48','PROBE 49').replace('VM CACHE TILES AND EXEC CONTINUATION','SCOPED GATE AND CONTROL DIAGNOSTICS')
                    if revision>=50:
                        UNIXNU_TOML=UNIXNU_TOML.replace('PROBE 49','PROBE 50').replace('SCOPED GATE AND CONTROL DIAGNOSTICS','UBC CALLER ATTRIBUTION AND GATES')
                    if revision>=51:
                        UNIXNU_TOML=UNIXNU_TOML.replace('PROBE 50','PROBE 51').replace('UBC CALLER ATTRIBUTION AND GATES','CACHE FALLBACK UPL IO CONTINUATION')
                    if revision>=53:
                        UNIXNU_TOML=UNIXNU_TOML.replace('PROBE 51','PROBE 72' if revision>=72 else 'PROBE 71' if revision>=71 else 'PROBE 70' if revision>=70 else 'PROBE 69' if revision>=69 else 'PROBE 68' if revision>=68 else 'PROBE 67' if revision>=67 else 'PROBE 66' if revision>=66 else 'PROBE 65' if revision>=65 else 'PROBE 64' if revision>=64 else 'PROBE 63' if revision>=63 else 'PROBE 62' if revision>=62 else 'PROBE 61' if revision>=61 else 'PROBE 60' if revision>=60 else 'PROBE 59' if revision>=59 else 'PROBE 58' if revision>=58 else 'PROBE 57' if revision>=57 else 'PROBE 56' if revision>=56 else 'PROBE 55' if revision>=55 else 'PROBE 54' if revision>=54 else 'PROBE 53').replace('CACHE FALLBACK UPL IO CONTINUATION','MINIMAL STAGE AND STRATEGY' if revision>=58 else 'LEAN STRATEGY OBSERVATION' if revision>=57 else 'STRATEGY DISPATCH TARGET' if revision>=54 else 'CLUSTER IO MAP SUBMIT WAIT')
                    if revision==52:
                        UNIXNU_TOML=UNIXNU_TOML.replace('PROBE 51','PROBE 52').replace('CACHE FALLBACK UPL IO CONTINUATION','CACHE RETURN GAP GATE DIAGNOSTICS')
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
        if revision>=35:
            report['fscompression_startup']=json.loads(args.entry_probe.read_text())['fscompression_startup']
            report['success_requires']=report['success_requires'].replace('PROBE26:', 'PROBE27:')+' Before real init exec, request normal Zlib OSKext lifecycle only when native type4 registration is absent; no direct kmod start or table writes. IDs264/265 observe loading; A02A=actual loader status, A033=actual native type4 registration pointer. All successful stages continue; restore userspace release guard remains.'
        if revision>=36:
            report['read_boundaries']=json.loads(args.entry_probe.read_text())['read_boundaries']
            report['success_requires']=report['success_requires'].replace('PROBE27:', 'PROBE28:')+' Header call 250 resets row y784 x832..1295. IDs266/267=vn_rdwr_64 call/return, 268/269=MAC read, 270/271=VNOP_READ, 272/273=actual filesystem dispatch, 274/275=swap-file read. Scope requires this exact header caller, TPIDR_EL1 and native frame; return markers require their paired call. A034=last read stage; A035=actual low32 return, all ones while call is pending. These overwrite prior A034/A035 after header entry. No marker proves APFS/decmpfs body completion unless its matching return was observed. Real errors and release guard retained.'
        if revision>=37:
            report['read_dispatch']=json.loads(args.entry_probe.read_text())['read_dispatch']
            report['success_requires']=report['success_requires'].replace('PROBE28:', 'PROBE29:')+' A036 is actual scoped dispatch x8 at y784; A037 at y812 and ID276 at x832/y808 record only the pinned candidate entry. Header entry clears both fields and ID276. Other targets require separate interpretation; an unlit entry tile does not prove they failed to enter. No filesystem body completion or deadlock is inferred; native errors and release guard remain.'
        if revision>=38:
            report['read_body']=json.loads(args.entry_probe.read_text())['read_body']
            report['success_requires']=report['success_requires'].replace('PROBE29:','PROBE30:')+' A038=last scoped native read body site, A039=last paired raw x0 return (not necessarily errno). IDs277..372 cover prologue continuation, all47 direct/indirect calls and continuations, and RET. No new halt or forced success. Unlit does not imply deadlock.'
        if revision>=39:
            report['read_init']=json.loads(args.entry_probe.read_text())['read_init']
            report['success_requires']=report['success_requires'].replace('PROBE30:','PROBE31:')+' Initialization temporarily uses A034 F901 before A037 reset, F902 before A036 reset, F903 before body state/tile reset, F904 before A038/A039 reset; returns to250 before native call. Minimum snapshot height1040. All47 call/return pairs retained; checkpoints are not CPU stop proofs or a claimed PROBE30 fix.'
        if revision>=40:
            report['single_pass_hex']=json.loads(args.entry_probe.read_text())['single_pass_hex']
            report['success_requires']=report['success_requires'].replace('PROBE31:','PROBE32:')+' HEX writes each pixel once, without a separate full-field black clear. Final labels/values and all native read/exec continuation observations retained. Reduced writes are not proof of a hardware fix.'
        if revision>=41:
            report['read_grid']=json.loads(args.entry_probe.read_text())['read_grid']
            report['success_requires']=report['success_requires'].replace('PROBE32:','PROBE33:')+' Revision41 overrides the immediate A038/A039 body display described above: all96 tiles remain immediate; last site/paired raw x0 are buffered and displayed only at native RET. While pending, A038=0 and A039=all ones are initialization values, not body progress. Use the actual lit tiles to identify pending calls. Native continuation/error/release policy unchanged.'
        if revision>=42:
            report['read_decmp']=json.loads(args.entry_probe.read_text())['read_decmp']
            report['success_requires']=report['success_requires'].replace('PROBE33:','PROBE34:')+' Center gutter IDs373..440 observe compressed-read entry,33 native call/return pairs and RET; two columns x736..815, y224..1031. Calls cyan, continuations green. No extra body HEX or native stop. Native return and outer APFS/read/exec observations remain required.'
        if revision>=43:
            report['shared_hex']=json.loads(args.entry_probe.read_text())['shared_hex']
            report['success_requires']=report['success_requires'].replace('PROBE34:','PROBE35:')+' Shared HEX code preserves pixel values and all observations; unchanged A035 skips redundant rendering, with cache reset before every header. No native lock/error/IRQ/release policy changed. Not a claimed root-cause fix.'
        if revision>=44:
            report['compact_decmp']=json.loads(args.entry_probe.read_text())['compact_decmp']
            report['success_requires']=report['success_requires'].replace('PROBE35:','PROBE36:')+' IDs373..440 use 32x2 strips, not full tiles. All native observations and release guard retained. No cache or lock fix claimed.'
        if revision>=45:
            report['read_fetch']=json.loads(args.entry_probe.read_text())['read_fetch']
            report['success_requires']=report['success_requires'].replace('PROBE36:','PROBE37:')+' New interleaved 32x2 strips: magenta entry, amber native call, white paired continuation/return; fetch and fixed type4 callback. Native behavior and release guard unchanged.'
        if revision>=46:
            report['read_deep']=json.loads(args.entry_probe.read_text())['read_deep']
            report['success_requires']=report['success_requires'].replace('PROBE37:','PROBE38:')+' New left-gutter checkpoints/allocation and third interleaved decode strips; native data/lock/error/cache/IRQ/release policies unchanged.'
        if revision>=47:
            report['read_result']=json.loads(args.entry_probe.read_text())['read_result']
            report['success_requires']=report['success_requires'].replace('PROBE38:','PROBE39:')+' A03A request, A03B allocator return, A03C caller result, A03D checkpoint, A03E metadata subtype; failure-print edges retained without skipping native behavior.'
        if revision>=48:
            report['delta_hex']=json.loads(args.entry_probe.read_text())['delta_hex']
            report['success_requires']=report['success_requires'].replace('PROBE39:','PROBE40:')+' Same-size same-pixel HEX; changed value glyphs only after initial complete draw. All mainline observers retained; no native cache/IRQ/allocator/release changes.'
        if revision>=49:
            report['read_flow']=json.loads(args.entry_probe.read_text())['read_flow']
            report['success_requires']=report['success_requires'].replace('PROBE40:','PROBE41:')+' A03A-C retain allocation facts; A03D is latest scoped post-allocation/decode/resource checkpoint, including UIO preparation, VNOP_GETXATTR and cleanup/error paths; A03E raw paired x0 or F pending, not uniformly errno. No stopped-PC inference or native policy change.'
        if revision>=49:
            report['success_requires']+=' Resource dispatch: A03D=FFFFFFF00746E1A4 with A03E=native x8 handler target; A03D=FFFFFFF00746E1A8 with A03E=raw returned x0. No target body completion inferred from the call marker.'
        if report.get('read_flow',{}).get('resource_cluster',{}).get('cache_progress_revision',0)>=48:
            report['success_requires']+=' PROBE48 overrides cluster HEX updates: IDs700..831 use independent 24x6 tiles, six columns at x8+36*column/y800+10*row. Entry magenta, call amber, paired continuation/RET white, sample cyan. Clear each header. Values remain buffered until clusterext/clustercopy RET; while pending A03D/E are not latest cluster progress. Cumulative tiles do not count calls or prove deadlock. Native policy and release239 unchanged.'
        if report.get('read_flow',{}).get('resource_cluster',{}).get('cache_progress_revision',0)>=49:
            report['success_requires']+=' PROBE49 keeps strict gates and native sites. Nine key sites add sticky reason bits (amber), arrival and strict-pass strips (white), separate wide-thread and strict NULL/non-NULL strips (red/cyan). Bits accumulate per header, not counts or order. Wide-thread control has no target-call attribution. Inactive/foreign calls write no diagnostic state or pixels; dark markers prove no visible observation, not no execution. No gate mismatch alone proves stack corruption or probe failure.'
        if revision>=50:
            report['success_requires']+=' PROBE50: only nine base tiles are drawn once per header; 123 other cluster sites omit base tiles (outer RET HEX remains), repeated same flags cause no redraw. UBC entry status cells 3..6 encode caller LR 7438C38, 74364A4, 743A080, or other (cyan), not NULL/non-NULL. Only 743CB90 retains control interpretation. Caller classes accumulate per header; last entry LR stored separately, no invocation ordering claim.'
        if revision>=56:
            report['success_requires']+=' PROBE56 bypasses only the 746E550 live tile drawing, retaining native hook/pairing and tile clearing; that coordinate is intentionally dark. All five-field 746E570 snapshots remain. Code layout must match PROBE55; this is not proof of no observer perturbation.'
        if revision>=55:
            report['success_requires']+=' PROBE55 retires all nine old gate-diagnostic record/render bodies; their inert 288-byte storage is retained. Earlier gate-strip interpretation is obsolete. PROBE55: when A03D=746E570, A03A=vnode x20, A03B=native v_op x9, A03C=signed strategy index, A03E=target x8. A03A-C supersede allocator meanings only at this dispatch snapshot. No target dereference, new hook, or native policy change.'
        if revision>=57:
            report['lean_observation']=json.loads(args.entry_probe.read_text())['lean_observation']
            report['success_requires']='PROBE57 lean observer profile supersedes all inherited normal-stage grid and HEX expectations. The sixteen cluster/strategy tiles, strategy provenance at 746E570, cluster outer return fields, failure/exception reporting and release239 guard remain. Old startup bands, calibration readback and ancestor HEX are intentionally absent. Native scope records remain for current observation dependencies. No claim of hardware transparency, EL0 or desktop success. PROBE56 single-tile suppression does not apply: PROBE57 derives from sealed PROBE55.'
        if revision>=54:
            report['success_requires']+=' PROBE54 removes 99 retired native cluster hooks and adds six strategy wrapper sites. Original instructions execute at removed sites. Six old wait tiles are replaced by strategy entry, buf_vnode call/return, indirect call/return and RET at y1030. A03E at 746E570 is actual x8, not errno. This selection supersedes prior descriptions; historical removed markers are invalid. Native policy remains unchanged.'
        if revision>=53:
            report['success_requires']+=' PROBE53 IO scope supersedes the prior tile selection: sixteen once-per-header tiles at caller/entry/return and paired BLOCKMAP, STRATEGY, buf_biowait and three cluster_wait_IO calls. Nine prior gate strips remain independent of selected base tiles. No new hook, state size, policy or release239 change. A call marker does not prove callee execution; cumulative paired returns do not prove all IO complete.'
        if revision>=52:
            report['success_requires']+=' PROBE52 return-gap diagnosis: the diagnostic slot from 743CB8C moves to 7438C3C. Sixteen base tiles and nine diagnostic slots retain their size; 743CB8C base tile remains. At 7438C3C, arrival is active-thread scoped, pass is strict, right stripes report gate rejection. Dark arrival cannot distinguish no execution from inactive thread/read or failed display. No native policy change.'
        if revision>=51:
            report['success_requires']+=' PROBE51 supersedes the PROBE50 tile count: sixteen once-per-header tiles, 116 unpainted sites. Seven added displays are existing native sites: 7438C3C residual sample, 7438CD0 error/residual fallback, 7438E74/7438E78 UPL call/continuation, 743914C/7439150 cluster IO call/continuation, 7439A80 cleanup. All strict gates, nine diagnostic strips and release239 retained. Cumulative hits are not invocation order, and a dark tile is not proof of nonexecution.'
        if revision==58:
            report['milestone_observation']=json.loads(args.entry_probe.read_text())['milestone_observation']
            report['success_requires']='PROBE58: nine restored coarse milestones: XNU entry, pre-MMU, post-MMU, arm_init, kernel_bootstrap, bootstrap thread, bsd_init, vfs_mountroot and load_init_program. Each proves only its own observation; green DarwinEnter bar is before XNU. The sixteen strict-scope cluster/strategy tiles and five-field strategy snapshot remain identical to PROBE57. Old grids, calibration and ancestor HEX remain retired. Dark downstream markers do not distinguish missing execution, scope or display. No native policy or release239 change. No EL0/desktop or hardware-transparency claim.'
        if revision in (59,60):
            report['success_requires']='PROBE59 retains all nine PROBE58 milestones and strict strategy observers; adds root-return ID167, zero/nonzero result ID212/213, IOSecureBSDRoot call/continuation ID168/169, bsd_utaskbootstrap call/continuation ID176/177 and bsdinit_task entry ID214. No errno HEX restored. Tiles are cumulative once-only and not a stopped PC or per-attempt pairing proof. Native policy unchanged.'
        if revision==60:
            report['success_requires']+=' PROBE60 adds three UNSCOPED once-only target marks at 5194248 entry, 5194278 after buf_vnode and 5194290 after vnode_fsnode. x0,y416 purple; y448 brown; y480 green. These may belong to different invocations and do not prove the scoped request completed. Native policies unchanged.'
        if revision==61:
            report['success_requires']='PROBE61 retains PROBE60 exact target markers and restores six init/exec tiles: IDs216,218,219,220,225,226. No HEX, policy, authentication or release239 change. Cumulative marks do not prove one request or EL0. Target markers are left x0 y416/448/480, not upper-right yellow tiles.'
        if revision==62:
            report['success_requires']='PROBE62: one first scoped APFS device submission. Six green tiles x128 y416..576 map submission, device target, filter entry, filter tail, mdev biodone return, APFS call return. B620 bp, B621 device vnode, B622 real bdevsw target, B623 dev_t, B624 raw x0 (errno low32). Missing stages and other backends remain partial. Existing cumulative tiles are not this trace. Native errors and release239 unchanged.'
        if revision==63:
            report['success_requires']='PROBE63 retains six scoped backend stages and adds green tiles 7..10 at x128,y608/640/672/704: mdev entry, before buf_map, buf_map returned (including error), copy path finished before unmap. B630 byte offset; B631 RAM base in 4KiB pages; B632 flags high32/size-pages low32; B633 raw buf flags high32/count low32; B634 buf_map errno low32; B635 mapped VA. A tile is a reached boundary, not a stopped PC or successful IO. Same-request and frame guards; native error, CBNZ, lock/refcount and release239 unchanged.'
        if revision==64:
            report['success_requires']='PROBE64 retains 63 trace with all B620-B643 HEX in x256..735,y200..667, each row cleared before drawing. New green stages11/12/13 x176 y608/640/672: unmap returned, mdev normal-path biodone entry, biodone before callback selection. B640 unmap errno; B641 raw flags; B642 actual iodone target; B643 iodone argument, all before callback. Prior stages retained; no successful completion or stopped-PC inference from missing tiles. Native policy and release239 unchanged.'
        if revision==72:
            report['success_requires']='PROBE72 x176 y544 intentionally blank; y576 point43 VA selection; y608 point46 after native DSB before replaying ISB; y640 point45 common return. Native TLBI through DSB kept intact. No pre-DSB drawing. Recovery RAMDisk mdev baseline.'
        if revision==71:
            report['success_requires']='PROBE71: x176 y544/576/608/640. 42 page-count w10: red zero, green one, amber 2..256, violet >=257. 43 short positive VA loop: green VALE1IS, amber VAALE1IS, red empty. 44 before native DSB ISH, 45 common return join after ISB or skip. First-hit only. Pre-barrier observer may perturb timing; absence is not a stopped PC.'
        if revision==70:
            report['success_requires']='PROBE70 four small tiles at x176 y544/576/608/640: positive removal count flush path, internal common return, first cursor result, wrapper epilogue. Cursor green=end, amber=forward partial, red=no forward progress, violet=overshoot. First-only stages can accumulate across iterations. Native TLBI/DSB/ISB sequence intact.'
        if revision==69:
            report['success_requires']='PROBE69: scope-matched compact tiles 34/35/36/37 at x176 y544/576/608/640 for pmap exclusive lock returned, range helper pre-call/return and unlock/preemption restored. Retired 27/30/32/33. Observe 28/29 and 23 for paired outer returns. No new HEX or renderer barrier.'
        if revision==68:
            report['success_requires']='PROBE68: retires 11/12/13/19/21/22/24/25; retains first-request completion,16/18/23. Adds26 delete entry,27 initial lookup return,28 pmap call,29 paired pmap return,30 entry unlink return,31 same-thread panic via existing observer replay,32 scoped sleep entry,33 unwire entry. New x176 y384..608 tiles. B680 entry, B681 raw entry+48 only on successful nonnull lookup, B682 lookup boolean; B683 panic LR/B684 format pointer; B685 sleep LR. Native locks/errors/refcounts unchanged. No loops or repeated draws. Missing marker is not stopped PC; host substitutes are not hardware proof.'
        if revision==67:
            report['success_requires']='PROBE67: native VM/map locking unchanged. Retires 7/10/14/17/20; retains completion chain and 16/18/19. New stages21 entry,22 map exclusive lock returned,23 vm_map_delete returned,24 unlock returned,25 zap dispose returned, x224 y544/576/608/640/672. B670 raw map+8 owner-high/data-low snapshot; B671 current ctid; B672 delete kern_return_t low32; B673 second return register. B660 UPL and B663/B664 range retained. Owner/frame/callsite scoped; no post-unlock UPL dereference. Missing markers do not prove stopped PC or deadlock. Offline emulation does not qualify real locks, VM deletion or hardware.'
        if revision==66:
            report['success_requires']='PROBE66: corrected READ|CLUSTER evidence; preserves native IO and locking. Retires points8/9/15; adds16 UPL argument,20 UPL internal entry,17 normal UPL lock return,18 VM remove call and19 VM remove return. Third column x224: stages16..20 at y384..512. B660 UPL, B661 map, B662 pre-lock refcount/flags, B663/B664 removal range. Missing stages do not prove stopped PC. No post-unlock UPL dereference. Point10 post-DSB cyan and unmap entry14 retained.'
        if revision==65:
            report['success_requires']='PROBE65 retains 64 scope and isolated HEX pane. Point10 right half turns cyan only after its existing DSB; cyan absence is not an exact stopped-PC proof. Adds unmap entry point14 (x176,y704) and non-cluster quick-return point15 (x176,y736). B650 at x256,y680 records current raw flags before unmap native load. Earlier B633 is not current flags. No change to native IO, references, errors, locks, authentication or release239. Missing points cannot identify a stopped PC; no UPL-unmap or read-direction claim solely from pre-unmap tile.'
        report['expected_screen_outcomes'] = [report['success_requires'], 'Any later XNU text or panic requires separate attribution; no band proves MMU enabled or iOS started']
        report['not_proven'] = ['Real nuwa execution of this candidate', 'MMU activation and arm_init', 'Native timer/interrupt driver readiness', 'Full donor/native ABI or iOS boot']
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'image_bytes': len(image), 'image_sha256': sha(image),
                      'kernel_sha256': sha(kernel), 'adt_sha256': sha(adt),
                      'fat_sha256': sha(fat)}))


if __name__ == '__main__':
    main()
