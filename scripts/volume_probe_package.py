"""Build and revalidate only the pinned configuration-only volume probe."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import zlib

ROOT = Path(__file__).resolve().parents[1]
MAGIC = bytes.fromhex('4e5557412d564f4ca3719c4e82d650b9')
FAT_SHA = 'bc0b3eae88e0dd8a528b3469d0fa9c3fa21c99097af842cab42c28cfa5068ff2'
STOCK = Path('D:/Code/PortingiOSLegacy/nuwa/backups/recovery-20261020T121245314787Z/boot_a.img')
STOCK_SHA = 'ef558db2a4fb021259d7af47a2398d7e56476d759162e7819959cd701a11ff31'


def sha(data):
    return hashlib.sha256(data).hexdigest()


PROFILES = {"VOLUME-PROBE-OFFLINE": "volume-envelope", "HOB-INTEGRITY-OFFLINE": "hob-integrity", "VOLUME-STATUS-OFFLINE": "volume-status"}


def recipe(run, profile_name="volume-envelope"):
    if profile_name not in PROFILES.values():
        raise ValueError("Unsupported profile")
    artifact = ROOT / f'out/firmware-ci/{run}/nuwa-firmware-{run}'
    profile = json.loads((ROOT/f'config/firmware-{profile_name}-profile.json').read_text())
    inputs = json.loads((artifact/'inputs.json').read_text())
    if inputs['recipe'] != profile['recipe'] or inputs['run_id'] != str(run):
        raise ValueError('Wrong build source or run')
    spec = importlib.util.spec_from_file_location('volume_inspector', ROOT/'scripts/ci/inspect-firmware-candidate.py')
    inspector = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(inspector)
    inspected = inspector.inspect(artifact, 'NuwaBootMemoryDxe', True, True, True, profile_name)
    stock = STOCK.read_bytes()
    fat = (ROOT/'out/volume-probe/volume-probe.fat.img').read_bytes()
    if sha(stock) != STOCK_SHA or sha(fat) != FAT_SHA or len(fat) != 67108864:
        raise ValueError('Pinned stock or probe changed')
    if fat[510:512] != b'\x55\xaa' or struct.unpack_from('<H', fat, 11)[0] != 512:
        raise ValueError('Unexpected FAT sector geometry')
    header = bytearray(stock[:4096])
    if (header[:8] != b'ANDROID!' or struct.unpack_from('<I', header, 40)[0] != 4
            or struct.unpack_from('<I', header, 20)[0] != 1584
            or struct.unpack_from('<I', header, 12)[0] != 0
            or struct.unpack_from('<I', header, 1580)[0] != 0):
        raise ValueError('Unexpected original v4 header')
    fd = (artifact/'build/FV/SILICIUM_UEFI.fd').read_bytes()
    shim = (artifact/'shim/shim.bin').read_bytes()
    if sha(shim) != '8a3b54765c895a0366539130fdf6e4e4a01e364fe7de067a38d0193606f9d462':
        raise ValueError('Shim changed')
    kernel = shim + fd
    ramdisk = MAGIC + struct.pack('<IIQI28x', 1, 64, len(fat), zlib.crc32(fat)) + fat
    struct.pack_into('<II', header, 8, len(kernel), len(ramdisk))
    image = bytes(header) + kernel + bytes(-len(kernel) % 4096) + ramdisk + bytes(-len(ramdisk) % 4096)
    metadata = dict(approval=next(key for key, value in PROFILES.items() if value == profile_name), run_id=run,
        device_commit=inputs['device_commit'], firmware_commit=profile['recipe']['sources']['firmware']['commit'],
        original_boot_sha256=STOCK_SHA, image_sha256=sha(image), image_bytes=len(image),
        fd_sha256=sha(fd), shim_sha256=sha(shim), fat_sha256=sha(fat), fat_bytes=len(fat),
        ramdisk_sha256=sha(ramdisk), ramdisk_bytes=len(ramdisk), kernel_bytes=len(kernel),
        image_path=f'out/trial-boot/{profile_name}-{run}/boot-volume-probe-v4.img',
        header_version=4, signature_bytes=0, fat_included=True, appended_dtb=False, xnu_included=False, adt_included=False,
        probe_title='NUWA VOLUME PROBE - NO XNU', device_executed=False,
        inspection_fd_sha256=inspected['fd']['sha256'])
    return image, metadata


def validate(path):
    path = Path(path).resolve()
    if path.name != 'package.json' or path.parent.parent.name not in PROFILES.values() or path.parent.parent.parent != ROOT/'reports':
        raise ValueError('Unexpected package report location')
    report = json.loads(path.read_text())
    run = report['run_id']
    if type(run) is not int or path.parent.name != str(run):
        raise ValueError('Run mismatch')
    profile_name = PROFILES.get(report.get("approval"))
    if profile_name != path.parent.parent.name:
        raise ValueError("Profile scope mismatch")
    image, expected = recipe(run, profile_name)
    if report != expected or (ROOT/expected['image_path']).read_bytes() != image:
        raise ValueError('Package metadata, header, payload or padding changed')
    return report


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('run', type=int)
    cli.add_argument("--profile", choices=tuple(PROFILES.values()), default="volume-envelope")
    args = cli.parse_args()
    image, report = recipe(args.run, args.profile)
    dest = ROOT/report['image_path']
    evidence = ROOT/f'reports/{args.profile}/{args.run}/package.json'
    if dest.parent.exists() or evidence.exists():
        raise ValueError('Fresh output required')
    dest.parent.mkdir(parents=True)
    evidence.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(image)
    evidence.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    validate(evidence)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
