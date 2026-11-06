"""Strict USB-v3 package containing a read-only EFI app and analytical data file.

The Mach-O file is data only. No xnu entry, ADT, or kernel execution is enabled.
"""
import argparse
import json
from pathlib import Path
import struct
import zlib
import usb_ramdisk_package as transport

ROOT=transport.ROOT
APPROVAL='USB-FILE-SHA-OFFLINE'
REPORT=ROOT/'reports/file-read-audit/package-02/package.json'
FAT=ROOT/'out/file-read-audit/fat-02/file-audit.fat.img'
FAT_SHA='b44d22bcf599414e29f940872506fc2215f359e4ff82228c0a010be3d0772166'
APP_SHA='def33a4add6f162a5726bba050a4c143c8ba38ea25f436f46ce4331811bb469f'
DATA_SHA='eb66542cc9b6c34f369c07229900408ab67288152f561be63fa6061efce9ffca'


def recipe():
    # Reuse all original FD/shim/SEC/HOB/profile validation, not just an FD hash.
    previous, baseline=transport.recipe(3)
    fat=FAT.read_bytes()
    if len(fat)!=67108864 or transport.sha(fat)!=FAT_SHA:
        raise ValueError('File audit FAT changed')
    build=json.loads((ROOT/'reports/file-read-audit/build-02.json').read_text())
    for item in build['own_sources']:
        if transport.sha((ROOT/item['path']).read_bytes())!=item['sha256']:
            raise ValueError('Audit app source changed since build')
    if transport.sha((ROOT/build['efi_path']).read_bytes())!=APP_SHA:
        raise ValueError('Fixed audit app changed')
    if build['read_fixture']['sha256']!=DATA_SHA or build['read_fixture']['bytes']!=58335232:
        raise ValueError('Read-only fixture identity changed')
    stock=transport.STOCK.read_bytes()
    kernel=previous[4096:4096+baseline['kernel_bytes']]
    ramdisk=transport.MAGIC+struct.pack('<IIQI28x',1,64,len(fat),zlib.crc32(fat))+fat
    image=transport.compose(stock[:4096],kernel,ramdisk,3)
    readback=transport.inspect_container(image,stock[:4096],kernel,ramdisk,3)
    report=dict(approval=APPROVAL,run_id=transport.RUN,source_profile='upstream-merged',
        device_commit=baseline['device_commit'],firmware_commit=baseline['firmware_commit'],
        original_boot_sha256=transport.STOCK_SHA,fd_sha256=baseline['fd_sha256'],shim_sha256=baseline['shim_sha256'],
        image_path='out/trial-boot/file-read-audit-02/boot-file-audit-v3.img',
        image_sha256=transport.sha(image),image_bytes=len(image),kernel_bytes=len(kernel),
        ramdisk_bytes=len(ramdisk),ramdisk_sha256=transport.sha(ramdisk),fat_sha256=FAT_SHA,fat_bytes=len(fat),
        header_version=3,header_size=1580,signature_bytes=0,fat_included=True,appended_dtb=False,
        xnu_included=True,analytical_macho_data_only=True,xnu_boot_entry=False,kernel_execution_enabled=False,adt_included=False,
        read_file='EFI/UniXNU/Payloads/READTEST.BIN',read_file_bytes=58335232,read_file_sha256=DATA_SHA,
        audit_efi_sha256=APP_SHA,audit_efi_bytes=6144,configuration_title='NUWA FILE SHA PROBE - NO XNU EXECUTION',
        embedded_configuration_fallback_present=True,
        success_requires='NUWA-FILE-SHA actual SHA256 eb66542c... plus PASS exact length, EOF and SHA256; menu alone is insufficient',
        container_readback=readback,device_executed=False,runtime_file_sha_verified=False)
    return image,report


def validate(path):
    path=Path(path).resolve()
    if path!=REPORT:
        raise ValueError('Unexpected file-audit package report location')
    saved=json.loads(path.read_text())
    image,expected=recipe()
    if saved!=expected or (ROOT/expected['image_path']).read_bytes()!=image:
        raise ValueError('File-audit metadata or complete container changed')
    return saved


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--validate',type=Path)
    args=cli.parse_args()
    if args.validate:
        report=validate(args.validate)
    else:
        image,report=recipe()
        path=ROOT/report['image_path']
        if path.parent.exists() or REPORT.exists():
            raise ValueError('Fresh image/report paths required')
        path.parent.mkdir(parents=True)
        REPORT.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(image)
        REPORT.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        validate(REPORT)
    print(json.dumps(dict(image_sha256=report['image_sha256'],bytes=report['image_bytes'],data_bytes=report['read_file_bytes'])))


if __name__=='__main__':main()
