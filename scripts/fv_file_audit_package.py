"""Strict USB-v3 data-only package for the opt-in FV ReadyToBoot file audit."""
import argparse
import importlib.util
import json
from pathlib import Path
import struct
import zlib
import usb_ramdisk_package as transport

ROOT=transport.ROOT
APPROVAL='FV-FILE-SHA-OFFLINE'
DATA_SHA='eb66542cc9b6c34f369c07229900408ab67288152f561be63fa6061efce9ffca'
FAT_SHA='5ea19e90fa1b44d0f79041663e1b91a9d9e274c34a8beda594ac009d762fb9ed'


def recipe(run):
    if type(run) is not int or run<=0:
        raise ValueError('Actual CI run ID required')
    artifact=ROOT/f'out/firmware-ci/{run}/nuwa-firmware-{run}'
    profile=json.loads((ROOT/'config/firmware-fv-file-audit-profile.json').read_text())
    provenance=json.loads((artifact/'inputs.json').read_text())
    if provenance['profile']!='fv-file-audit' or provenance['recipe']!=profile['recipe'] or provenance['run_id']!=str(run):
        raise ValueError('Wrong actual FV diagnostic source/profile')
    spec=importlib.util.spec_from_file_location('fv_file_inspector',ROOT/'scripts/ci/inspect-firmware-candidate.py')
    inspector=importlib.util.module_from_spec(spec);spec.loader.exec_module(inspector)
    inspected=inspector.inspect(artifact,'NuwaBootMemoryDxe',True,True,True,'fv-file-audit')
    fat=(ROOT/'out/fv-file-audit/data-01/data.fat.img').read_bytes()
    if len(fat)!=67108864 or transport.sha(fat)!=FAT_SHA:
        raise ValueError('Data-only audit FAT changed')
    stock=transport.STOCK.read_bytes()
    if transport.sha(stock)!=transport.STOCK_SHA:
        raise ValueError('Original recovery input changed')
    shim=(artifact/'shim/shim.bin').read_bytes()
    fd=(artifact/'build/FV/SILICIUM_UEFI.fd').read_bytes()
    if transport.sha(shim)!=transport.SHIM_SHA or len(fd)!=3145728:
        raise ValueError('Unreviewed shim/FD geometry')
    kernel=shim+fd
    ramdisk=transport.MAGIC+struct.pack('<IIQI28x',1,64,len(fat),zlib.crc32(fat))+fat
    image=transport.compose(stock[:4096],kernel,ramdisk,3)
    readback=transport.inspect_container(image,stock[:4096],kernel,ramdisk,3)
    driver=next(m for m in inspected['modules'] if m['name']=='NuwaFileAuditDxe')
    report=dict(approval=APPROVAL,run_id=run,device_commit=provenance['device_commit'],
        firmware_commit=profile['recipe']['sources']['firmware']['commit'],source_profile='fv-file-audit',
        original_boot_sha256=transport.STOCK_SHA,image_path=f'out/trial-boot/fv-file-audit-{run}/boot-fv-file-audit-v3.img',
        image_sha256=transport.sha(image),image_bytes=len(image),fd_sha256=transport.sha(fd),shim_sha256=transport.sha(shim),
        header_version=3,header_size=1580,kernel_bytes=len(kernel),ramdisk_bytes=len(ramdisk),ramdisk_sha256=transport.sha(ramdisk),
        fat_bytes=len(fat),fat_sha256=FAT_SHA,signature_bytes=0,appended_dtb=False,fat_included=True,
        xnu_included=True,analytical_macho_data_only=True,xnu_boot_entry=False,kernel_execution_enabled=False,
        external_efi_application_in_payload=False,adt_included=False,read_file_bytes=58335232,read_file_sha256=DATA_SHA,
        diagnostic_driver_guid='45b28639-79a9-456d-afc5-edcfe78cdae1',diagnostic_driver=driver,
        sec_sha256=inspected['sec_entry_hob_producer']['sha256'],image_verification_policy_changes=False,
        success_requires='NUWA-FV-FILE actual SHA256 eb66542c... and PASS exact length EOF SHA256 with final bytes 0x37a2000',
        container_readback=readback,device_executed=False,runtime_file_sha_verified=False)
    return image,report


def validate(path):
    path=Path(path).resolve()
    if path.name!='package.json' or path.parent.parent!=ROOT/'reports/fv-file-audit':
        raise ValueError('Unexpected FV audit report location')
    saved=json.loads(path.read_text())
    if type(saved.get('run_id')) is not int or path.parent.name!=str(saved['run_id']):
        raise ValueError('FV audit run mismatch')
    image,expected=recipe(saved['run_id'])
    if saved!=expected or (ROOT/expected['image_path']).read_bytes()!=image:
        raise ValueError('FV audit package or data-only metadata changed')
    return saved


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--run',type=int)
    cli.add_argument('--validate',type=Path)
    args=cli.parse_args()
    if args.validate:
        report=validate(args.validate)
    else:
        image,report=recipe(args.run)
        destination=ROOT/report['image_path']
        target=ROOT/f'reports/fv-file-audit/{args.run}/package.json'
        if destination.parent.exists() or target.exists():
            raise ValueError('Fresh package outputs required')
        destination.parent.mkdir(parents=True)
        target.parent.mkdir(parents=True,exist_ok=True)
        destination.write_bytes(image)
        target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        validate(target)
    print(json.dumps(dict(image_sha256=report['image_sha256'],bytes=report['image_bytes'],fd_sha256=report['fd_sha256'])))


if __name__=='__main__':main()
