"""Offline USB ramdisk v3 candidate and v4 control; never contact a device.

Uses the already inspected upstream-merged firmware unchanged. Only v3 is
eligible for the separately gated trial scope. Neither image contains XNU.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import zlib

ROOT = Path(__file__).resolve().parents[1]
RUN = 40014018074
ARTIFACT = ROOT / f'out/upstream-firmware-{RUN}/nuwa-firmware-{RUN}'
STOCK = Path('D:/Code/PortingiOS/nuwa/backups/recovery-20261020T121245314787Z/boot_a.img')
STOCK_SHA = 'ef558db2a4fb021259d7af47a2398d7e56476d759162e7819959cd701a11ff31'
FD_SHA = '2d606985ad768dcfaab66c2b28073c0a4c2820126b42b23286623fdc450e848f'
SHIM_SHA = '8a3b54765c895a0366539130fdf6e4e4a01e364fe7de067a38d0193606f9d462'
FAT_SHA = 'bc0b3eae88e0dd8a528b3469d0fa9c3fa21c99097af842cab42c28cfa5068ff2'
APPROVAL = 'USB-RAMDISK-V3-OFFLINE'
MAGIC = bytes.fromhex('4e5557412d564f4ca3719c4e82d650b9')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def compose(stock_header, kernel, ramdisk, version):
    if version not in (3, 4) or len(stock_header) != 4096:
        raise ValueError('Only canonical v3/v4 headers are allowed')
    if (stock_header[:8] != b'ANDROID!' or
        struct.unpack_from('<I', stock_header, 40)[0] != 4 or
        struct.unpack_from('<I', stock_header, 20)[0] != 1584 or
        struct.unpack_from('<I', stock_header, 12)[0] != 0 or
        any(stock_header[24:40]) or any(stock_header[1580:])):
        raise ValueError('Unsupported original v4 header or signature/padding')
    if not kernel or not ramdisk or max(len(kernel), len(ramdisk)) >= 2**32:
        raise ValueError('Invalid bounded kernel/ramdisk size')
    header = bytearray(stock_header)
    struct.pack_into('<II', header, 8, len(kernel), len(ramdisk))
    struct.pack_into('<I', header, 20, 1580 if version == 3 else 1584)
    struct.pack_into('<I', header, 40, version)
    return (bytes(header) + kernel + bytes(-len(kernel) % 4096)
            + ramdisk + bytes(-len(ramdisk) % 4096))


def inspect_container(image, stock_header, kernel, ramdisk, version):
    """Separate field/boundary readback, including exact original cmdline."""
    if len(image) < 4096 or image[:8] != b'ANDROID!':
        raise ValueError('Invalid container magic/length')
    ksize, rsize = struct.unpack_from('<II', image, 8)
    hsize, = struct.unpack_from('<I', image, 20)
    actual_version, = struct.unpack_from('<I', image, 40)
    if (actual_version != version or version not in (3, 4)
        or hsize != (1580 if version == 3 else 1584)
        or ksize != len(kernel) or rsize != len(ramdisk)):
        raise ValueError('Container version/header/size mismatch')
    allowed = set(range(8, 16)) | set(range(20, 24)) | set(range(40, 44))
    differences = [i for i in range(4096) if image[i] != stock_header[i]]
    if any(i not in allowed for i in differences):
        raise ValueError('Original header, cmdline or zero signature changed')
    ramdisk_at = 4096 + ((ksize + 4095) // 4096) * 4096
    end = ramdisk_at + rsize
    if (len(image) != (end + 4095) // 4096 * 4096 or
        image[4096:4096+ksize] != kernel or image[ramdisk_at:end] != ramdisk or
        any(image[4096+ksize:ramdisk_at]) or any(image[end:])):
        raise ValueError('Container payload, padding, or exact length mismatch')
    return dict(kernel_offset=4096, ramdisk_offset=ramdisk_at,
                header_changed_offsets=differences, original_cmdline_preserved=True)


def recipe(version):
    if version not in (3, 4):
        raise ValueError('Unsupported USB diagnostic version')
    profile = json.loads((ROOT / 'config/firmware-upstream-merged-profile.json').read_text())
    provenance = json.loads((ARTIFACT / 'inputs.json').read_text())
    if (provenance['profile'] != 'upstream-merged' or
        provenance['recipe'] != profile['recipe'] or provenance['run_id'] != str(RUN)):
        raise ValueError('Wrong merged firmware source/run')
    spec = importlib.util.spec_from_file_location('usb_firmware_inspector', ROOT / 'scripts/ci/inspect-firmware-candidate.py')
    inspector = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(inspector)
    inspection = inspector.inspect(ARTIFACT, 'NuwaBootMemoryDxe', True, True, True, 'upstream-merged')
    stock = STOCK.read_bytes()
    fd = (ARTIFACT / 'build/FV/SILICIUM_UEFI.fd').read_bytes()
    shim = (ARTIFACT / 'shim/shim.bin').read_bytes()
    fat = (ROOT / 'out/volume-probe/volume-probe.fat.img').read_bytes()
    for raw, expected in ((stock, STOCK_SHA), (fd, FD_SHA), (shim, SHIM_SHA), (fat, FAT_SHA)):
        if sha(raw) != expected:
            raise ValueError('Pinned USB diagnostic input changed')
    if len(fat) != 67108864 or len(fd) != 3145728 or len(shim) != 112:
        raise ValueError('Unexpected pinned geometry')
    kernel = shim + fd
    envelope = MAGIC + struct.pack('<IIQI28x', 1, 64, len(fat), zlib.crc32(fat))
    ramdisk = envelope + fat
    image = compose(stock[:4096], kernel, ramdisk, version)
    fields = inspect_container(image, stock[:4096], kernel, ramdisk, version)
    report = dict(approval=APPROVAL if version == 3 else 'USB-RAMDISK-V4-CONTROL-OFFLINE',
        run_id=RUN, source_profile='upstream-merged', device_commit=provenance['device_commit'],
        firmware_commit=profile['recipe']['sources']['firmware']['commit'],
        original_boot_sha256=STOCK_SHA, image_sha256=sha(image), image_bytes=len(image),
        image_path=f'out/trial-boot/usb-ramdisk-{RUN}/boot-ramdisk-v{version}.img',
        fd_sha256=FD_SHA, shim_sha256=SHIM_SHA, kernel_bytes=len(kernel), kernel_sha256=sha(kernel),
        ramdisk_bytes=len(ramdisk), ramdisk_sha256=sha(ramdisk),
        fat_sha256=FAT_SHA, fat_bytes=len(fat), envelope_crc32=hex(zlib.crc32(fat)),
        header_version=version, header_size=1580 if version == 3 else 1584, signature_bytes=0,
        fat_included=True, xnu_included=False, adt_included=False, appended_dtb=False,
        embedded_configuration_fallback_present=True,
        success_requires='NUWA-VOLUME envelope result=1 and block device Success with 64MiB; menu alone is insufficient',
        inspection_fd_sha256=inspection['fd']['sha256'], container_readback=fields,
        device_executed=False, runtime_transport_verified=False)
    return image, report


def validate(path):
    path = Path(path).resolve()
    if path.parent != ROOT / f'reports/usb-ramdisk/{RUN}' or path.name not in ('package-v3.json', 'package-v4.json'):
        raise ValueError('Unexpected USB diagnostic package location')
    version = 3 if path.name == 'package-v3.json' else 4
    report = json.loads(path.read_text())
    image, expected = recipe(version)
    if report != expected or (ROOT / expected['image_path']).read_bytes() != image:
        raise ValueError('USB package metadata or complete image changed')
    return report


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--validate', type=Path)
    args = cli.parse_args()
    if args.validate:
        print(json.dumps(validate(args.validate)))
        return
    destination = ROOT / f'out/trial-boot/usb-ramdisk-{RUN}'
    reports = ROOT / f'reports/usb-ramdisk/{RUN}'
    if destination.exists() or reports.exists():
        raise ValueError('Fresh image/report destinations required')
    v3, r3 = recipe(3)
    v4, r4 = recipe(4)
    differences = [i for i in range(4096) if v3[i] != v4[i]]
    if differences != [20, 40] or v3[4096:] != v4[4096:]:
        raise ValueError('Pair differs outside canonical version/header-size bytes')
    destination.mkdir(parents=True)
    reports.mkdir(parents=True)
    for image, report in ((v3, r3), (v4, r4)):
        version = report['header_version']
        (ROOT / report['image_path']).write_bytes(image)
        evidence = reports / f'package-v{version}.json'
        evidence.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        validate(evidence)
    (reports / 'pair.json').write_text(json.dumps(dict(
        v3_sha256=sha(v3), v4_sha256=sha(v4), image_bytes=len(v3),
        changed_byte_offsets=differences, all_bytes_after_header_identical=True,
        scope='Offline matched container pair; v4 control not enabled for device launch',
        device_accessed=False), indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(v3=r3['image_sha256'], v4=r4['image_sha256'], bytes=len(v3), differences=differences)))


if __name__ == '__main__':
    main()
