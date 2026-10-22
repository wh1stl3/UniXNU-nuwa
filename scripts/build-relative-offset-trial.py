"""R-008 A: build only BootShim, reuse the exact R-007 FD, emit one v4 trial.

This is an approved image generator. No device commands are performed.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]
FIRMWARE = Path('D:/Code/uefi-nuwa')
COMMIT = '910ee079fbaef736c49c14fd24501b132e98bb90'
SOURCE_SHA = '985a68764e965903b5b0b0b6958164db2861dfb981a28e468484f35cbdb3a2dd'
FD_SHA = '9ea347a49e51472adac987cf12e20f9e0d99453a23f2113ad24efcd0a07f2eaf'
SHIM_SHA = '9346a527441b242c69414fd7e3d6fa17813f281d562fef13d9ba8373d39007a9'
OLD_PACKAGE_SHA = 'fbb7940a8ee8cb5f2577a30bc2e5fb5bc31e1b84930c05b40c6304dfe970bcde'
STOCK = Path('D:/Code/PortingiOS/nuwa/backups/recovery-20261020T121245314787Z/boot_a.img')
STOCK_SHA = 'ef558db2a4fb021259d7af47a2398d7e56476d759162e7819959cd701a11ff31'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    output = ROOT / 'out/trial-boot/relative-offset-R008'
    reports = ROOT / 'reports/relative-offset'
    if output.exists() or (reports / 'package.json').exists():
        raise ValueError('Refusing to overwrite this trial')
    def git(*args):
        return subprocess.check_output(['git', '-C', str(FIRMWARE), *args]).decode().strip()
    if git('log', '-1', '--format=%H') != COMMIT or git('status', '--porcelain'):
        raise ValueError('Firmware checkout changed')
    source = FIRMWARE / 'BootShim/BootShim.S'
    if sha(source.read_text().replace('\r\n', '\n').encode()) != SOURCE_SHA:
        raise ValueError('Approved source hash mismatch')
    artifact = ROOT / 'out/firmware-ci/39809636575/nuwa-firmware-39809636575'
    fd = (artifact / 'build/FV/SILICIUM_UEFI.fd').read_bytes()
    old_shim = (artifact / 'shim/shim.bin').read_bytes()
    old_package = (ROOT / 'out/trial-boot/sec-trace-39809636575/boot-sec-trace-v4.img').read_bytes()
    original = STOCK.read_bytes()
    if (sha(fd) != FD_SHA or len(fd) != 0x300000 or sha(old_shim) != SHIM_SHA
            or sha(old_package) != OLD_PACKAGE_SHA or sha(original) != STOCK_SHA):
        raise ValueError('Pinned binary input changed')
    spec = importlib.util.spec_from_file_location('inspector', ROOT / 'scripts/ci/inspect-firmware-candidate.py')
    inspector = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(inspector)
    # Historical inspector intentionally checks the old, immutable CI artifact.
    # New shim is checked independently below; never feed it the old profile.
    inspection = inspector.inspect(artifact, 'NuwaBootMemoryDxe', require_sec_trace=True)
    output.mkdir(parents=True)
    reports.mkdir(parents=True, exist_ok=True)
    commands = []
    def run(*argv):
        result = subprocess.run(argv, capture_output=True, text=True, timeout=45)
        commands.append(dict(argv=list(argv), exit_code=result.returncode,
                             stdout=result.stdout, stderr=result.stderr))
        (reports / 'build-commands.json').write_text(json.dumps(commands, indent=2)+'\n')
        result.check_returncode()
        return result.stdout
    run('wsl', '-d', 'Ubuntu-22.04', '--', 'clang', '--version')
    run('wsl', '-d', 'Ubuntu-22.04', '--', 'llvm-objcopy', '--version')
    unix_output = '/mnt/d/Code/UniXNU-nuwa/out/trial-boot/relative-offset-R008'
    elf = unix_output + '/BootShim.elf'
    run('wsl', '-d', 'Ubuntu-22.04', '--', 'clang', '--target=aarch64-linux-gnu',
        '-c', '/mnt/d/Code/uefi-nuwa/BootShim/BootShim.S', '-o', elf,
        '-DREQUIRES_KERNEL_HEADER=1', '-DFD_BASE=0xa7100000', '-DFD_SIZE=0x300000')
    run('wsl', '-d', 'Ubuntu-22.04', '--', 'llvm-objcopy', '-O', 'binary', elf, unix_output+'/shim.bin')
    symbols = run('wsl', '-d', 'Ubuntu-22.04', '--', 'llvm-nm', '-n', elf)
    assembly = run('wsl', '-d', 'Ubuntu-22.04', '--', 'llvm-objdump', '-d', elf)
    (reports / 'symbols.txt').write_text(symbols)
    (reports / 'disassembly.txt').write_text(assembly)
    shim = (output / 'shim.bin').read_bytes()
    differences = [i for i, (a, b) in enumerate(zip(old_shim, shim)) if a != b]
    labels = {line.split()[-1]: int(line.split()[0], 16)
              for line in symbols.splitlines() if len(line.split()) == 3}
    if (len(shim) != len(old_shim) or len(shim) != 112 or not differences
            or any(not 8 <= i < 16 for i in differences)
            or struct.unpack_from('<Q', shim, 8)[0] != 0
            or struct.unpack_from('<Q', shim, 16)[0] != len(shim)+len(fd)
            or shim[56:60] != b'ARM\x64' or labels['_Payload'] != len(shim)
            or inspector.shim_copy_count(shim, symbols) != len(fd)):
        raise ValueError('New shim is not the approved header-only change')
    header = bytearray(original[:4096])
    if (header[:8] != b'ANDROID!' or struct.unpack_from('<I', header, 40)[0] != 4
            or struct.unpack_from('<I', header, 20)[0] != 1584
            or struct.unpack_from('<I', header, 12)[0] != 0
            or struct.unpack_from('<I', header, 1580)[0] != 0):
        raise ValueError('Unsupported stock container')
    payload = shim+fd
    struct.pack_into('<I', header, 8, len(payload))
    image = bytes(header)+payload+b'\0'*(-len(payload) % 4096)
    image_differences = [i for i, (a,b) in enumerate(zip(old_package,image)) if a != b]
    if (len(image) != len(old_package) or image_differences != [4096+i for i in differences]
            or image[4096+len(shim):4096+len(payload)] != fd
            or image[:8] != original[:8] or image[12:4096] != original[12:4096]):
        raise ValueError('New package changes more than the shim header')
    destination = output / 'boot-relative-offset-v4.img'
    destination.write_bytes(image)
    if sha(destination.read_bytes()) != sha(image):
        raise ValueError('Written image hash mismatch')
    package = dict(approval='R-008 A', scope='Header-only relative text_offset correction; exact R-007 FD reused',
        run_id=39809636575, firmware_commit=COMMIT,
        fd_firmware_commit='5e4a8c814b89f62a4ba2bc145249314fed5db787',
        source_sha256=SOURCE_SHA, image_path=destination.relative_to(ROOT).as_posix(),
        image_bytes=len(image), image_sha256=sha(image), original_boot_sha256=STOCK_SHA,
        fd_sha256=sha(fd), shim_sha256=sha(shim), shim_bytes=len(shim),
        shim_text_offset=0, fd_copy_destination='0xa7100000', image_size=len(payload),
        copy_bytes=inspector.shim_copy_count(shim, symbols), payload_offset=labels['_Payload'],
        shim_changed_byte_offsets=differences, package_changed_byte_offsets=image_differences,
        previous_image_sha256=OLD_PACKAGE_SHA, header_version=4, page_bytes=4096,
        kernel_bytes=len(payload), changed_header_fields=['kernel_size'],
        ramdisk_bytes=0, signature_bytes=0, appended_dtb=False, fat_included=False, xnu_included=False,
        dt_source='Installed vendor_boot through ABL; actual handoff unverified',
        candidate_device_executed=False, recovery_required=True)
    (reports / 'reused-ci-artifact-inspection.json').write_text(json.dumps(inspection, indent=2)+'\n')
    for dest in (reports / 'package.json', output / 'package.json'):
        dest.write_text(json.dumps(package, indent=2)+'\n')
    (output / 'SHA256SUMS').write_text(sha(image)+'  '+destination.name+'\n')
    print(json.dumps(package, indent=2))


if __name__ == '__main__':
    main()
