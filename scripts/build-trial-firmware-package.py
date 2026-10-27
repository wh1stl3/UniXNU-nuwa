"""Prepare an authorized firmware-only v4 boot candidate; no device commands."""
import hashlib
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]
STOCK = Path('D:/Code/PortingiOSLegacy/nuwa/backups/recovery-20261020T121245314787Z/boot_a.img')
ARTIFACT = ROOT / 'out/firmware-ci/39764322744/nuwa-firmware-39764322744'
OUT = ROOT / 'out/trial-boot/firmware-v4'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    # Hash-pinned original nuwa boot was temporarily loaded on this device and
    # Android boot_completed=1 was observed. This does not validate this candidate.
    original = STOCK.read_bytes()
    if sha(original) != 'ef558db2a4fb021259d7af47a2398d7e56476d759162e7819959cd701a11ff31':
        raise ValueError('Original nuwa recovery input changed')
    header = bytearray(original[:4096])
    if (header[:8] != b'ANDROID!' or struct.unpack_from('<I', header, 40)[0] != 4
            or struct.unpack_from('<I', header, 20)[0] != 1584
            or struct.unpack_from('<I', header, 12)[0] != 0
            or struct.unpack_from('<I', header, 1580)[0] != 0):
        raise ValueError('Unsupported original v4 header/ramdisk/signature')
    fd = (ARTIFACT / 'build/FV/SILICIUM_UEFI.fd').read_bytes()
    shim = (ARTIFACT / 'shim/shim.bin').read_bytes()
    if sha(fd) != 'a0bbb9645f4af2de66e4e29e1b5deaf508e95c41f33de4fd9f811ab03bde1c83':
        raise ValueError('FD differs from inspected CI artifact')
    if sha(shim) != '9346a527441b242c69414fd7e3d6fa17813f281d562fef13d9ba8373d39007a9':
        raise ValueError('Shim differs from inspected CI artifact')
    payload = shim + fd
    if shim[56:60] != b'ARM\x64' or struct.unpack_from('<Q', shim, 16)[0] != len(payload):
        raise ValueError('ARM64 payload size/magic mismatch')
    struct.pack_into('<I', header, 8, len(payload))
    if header[:8] != original[:8] or header[12:] != original[12:4096]:
        raise ValueError('Only the kernel_size field may change in original header')
    image = bytes(header) + payload + b'\0' * (-len(payload) % 4096)
    if image[4096:4096 + len(shim)] != shim or image[4096 + len(shim):4096 + len(payload)] != fd:
        raise ValueError('Reparsed candidate content mismatch')
    OUT.mkdir(parents=True, exist_ok=False)
    (OUT / 'boot-firmware-v4.img').write_bytes(image)
    report = dict(scope='Firmware-only temporary boot container; static inspection only',
                  original_boot_sha256=sha(original), fd_sha256=sha(fd), shim_sha256=sha(shim),
                  image_bytes=len(image), image_sha256=sha(image), header_version=4,
                  page_bytes=4096, kernel_bytes=len(payload), ramdisk_bytes=0, signature_bytes=0,
                  changed_header_fields=['kernel_size'], kernel_compression='none',
                  dt_source='Installed original nuwa vendor_boot via ABL; no appended DTB',
                  additional_initrd=False, xnu_included=False, candidate_device_executed=False,
                  ready_to_execute=False, unverified=['Candidate ABL acceptance and actual placement',
                  'Shim placement/cache conditions and SEC x0 FDT mapping',
                  'DXE/BDS and original Android initrd lifetime',
                  'Hard-hang key recovery (H-001)'])
    (OUT / 'package.json').write_text(json.dumps(report, indent=2) + '\n')
    (OUT / 'SHA256SUMS').write_text(sha(image) + '  boot-firmware-v4.img\n')
    (OUT / 'README.txt').write_text(
        'nuwa firmware-only v4 candidate from CI39764322744.\n'
        'Static container checks passed; candidate has not been executed.\n'
        'No XNU payload, FAT initrd, appended DTB or automatic flashing script.\n'
        'Use only after verifying fastboot product=nuwa and reviewing package.json conditions.\n'
        'Original recovery source: D:/Code/PortingiOSLegacy/nuwa/backups/recovery-20261020T121245314787Z/boot_a.img\n'
        'Its temporary boot reached Android boot_completed=1; persistent slot-A boot is unresolved.\n')
    evidence = ROOT / 'reports/trial-boot-preflight/package.json'
    evidence.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
