"""Pack and revalidate only the pinned configuration-only embedded FV probe."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

ROOT=Path(__file__).resolve().parents[1]
STOCK=Path('D:/Code/PortingiOS/nuwa/backups/recovery-20261020T121245314787Z/boot_a.img')
STOCK_SHA='ef558db2a4fb021259d7af47a2398d7e56476d759162e7819959cd701a11ff31'

def sha(data):return hashlib.sha256(data).hexdigest()

PROFILES={'embedded-probe':'EMBEDDED-PROBE-OFFLINE','boot-input-audit':'BOOT-INPUT-AUDIT-OFFLINE','hob-stage-audit':'HOB-STAGE-AUDIT-OFFLINE','hob-cache-handoff':'HOB-CACHE-HANDOFF-OFFLINE'}

def recipe(run, profile_name='embedded-probe'):
    if profile_name not in PROFILES:raise ValueError('Unknown diagnostic profile')
    artifact=ROOT/f'out/firmware-ci/{run}/nuwa-firmware-{run}'
    profile=json.loads((ROOT/f'config/firmware-{profile_name}-profile.json').read_text())
    inputs=json.loads((artifact/'inputs.json').read_text())
    if inputs['profile']!=profile_name or inputs['recipe']!=profile['recipe'] or inputs['run_id']!=str(run):
        raise ValueError('Wrong embedded probe build source/run')
    spec=importlib.util.spec_from_file_location('fv_inspector',ROOT/'scripts/ci/inspect-firmware-candidate.py')
    inspector=importlib.util.module_from_spec(spec);spec.loader.exec_module(inspector)
    result=inspector.inspect(artifact,'NuwaBootMemoryDxe',True,True,True,profile_name)
    original=STOCK.read_bytes()
    if sha(original)!=STOCK_SHA:raise ValueError('Original recovery boot changed')
    header=bytearray(original[:4096])
    if (header[:8]!=b'ANDROID!' or struct.unpack_from('<I',header,40)[0]!=4 or
        struct.unpack_from('<I',header,20)[0]!=1584 or struct.unpack_from('<I',header,12)[0]!=0 or
        struct.unpack_from('<I',header,1580)[0]!=0):raise ValueError('Unsupported original boot header')
    shim=(artifact/'shim/shim.bin').read_bytes();fd=(artifact/'build/FV/SILICIUM_UEFI.fd').read_bytes()
    if sha(shim)!='8a3b54765c895a0366539130fdf6e4e4a01e364fe7de067a38d0193606f9d462':raise ValueError('Shim changed')
    kernel=shim+fd
    struct.pack_into('<I',header,8,len(kernel))
    image=bytes(header)+kernel+bytes(-len(kernel)%4096)
    metadata=dict(approval=PROFILES[profile_name],run_id=run,device_commit=inputs['device_commit'],
        firmware_commit=profile['recipe']['sources']['firmware']['commit'],original_boot_sha256=STOCK_SHA,
        image_sha256=sha(image),image_bytes=len(image),fd_sha256=sha(fd),shim_sha256=sha(shim),
        image_path=f'out/trial-boot/{profile_name}-{run}/boot-fv-probe-v4.img',kernel_bytes=len(kernel),
        ramdisk_bytes=0,header_version=4,signature_bytes=0,fat_included=True,fat_transport='firmware FV RAW resource',
        fat_bytes=profile['candidate']['embedded_probe']['bytes'],fat_sha256=profile['candidate']['embedded_probe']['sha256'],
        xnu_included=False,adt_included=False,appended_dtb=False,device_executed=False,
        inspection_fd_sha256=result['fd']['sha256'])
    return image,metadata

def validate(path):
    path=Path(path).resolve()
    profile_name=path.parent.parent.name
    if path.name!='package.json' or profile_name not in PROFILES or path.parent.parent!=ROOT/f'reports/{profile_name}':raise ValueError('Unexpected embedded report location')
    saved=json.loads(path.read_text());run=saved['run_id']
    if type(run) is not int or path.parent.name!=str(run):raise ValueError('Run mismatch')
    image,expected=recipe(run,profile_name)
    if saved!=expected or (ROOT/expected['image_path']).read_bytes()!=image:raise ValueError('Embedded package header, payload, padding or metadata changed')
    return saved

def main():
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('run',type=int);cli.add_argument('--profile',choices=tuple(PROFILES),default='embedded-probe');args=cli.parse_args()
    image,metadata=recipe(args.run,args.profile);out=ROOT/metadata['image_path'];report=ROOT/f'reports/{args.profile}/{args.run}/package.json'
    if out.parent.exists() or report.exists():raise ValueError('Fresh outputs required')
    out.parent.mkdir(parents=True);report.parent.mkdir(parents=True,exist_ok=True)
    out.write_bytes(image);report.write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8');validate(report)
    print(json.dumps(metadata))

if __name__=='__main__':main()
