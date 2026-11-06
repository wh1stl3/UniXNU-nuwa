"""Package the firmware LU0 read baseline. Never opens a device."""
import argparse, hashlib, importlib.util, json, lzma, struct, subprocess, zlib
from pathlib import Path
import usb_ramdisk_package as transport

ROOT=Path(__file__).resolve().parents[1]
GUID='16fdf4d6-f518-4f55-a1c2-7a69ad09e300'
FAT_SHA='1902660a0d65a09f92cd5dd782dd0e97d16a1e5f7bca0e75a21c557a5c3af788'
sha=lambda b: hashlib.sha256(b).hexdigest()
def module(path):
    spec=importlib.util.spec_from_file_location(path.stem,path);obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj);return obj

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--work',required=True,type=Path);args=parser.parse_args();work=args.work.resolve()
    if not work.is_relative_to(ROOT/'out') or work.exists():raise ValueError('Fresh workspace output required')
    work.mkdir(parents=True); legacy=module(ROOT/'scripts/build-log-survey-v2.py');legacy.GUID=GUID
    lin=legacy.linux;inc=legacy.MU/'MdePkg/Include';display=legacy.SOURCE.parent; source=ROOT/'package/ufs-r0/UfsRead.c'
    ref=ROOT/'reports/ufs-r0-r1/android-lu0.json';q=json.loads(ref.read_bytes());assert q['block_bytes']==4096 and q['lun']==0 and q['lba']==1 and q['identical_reads']==2
    (work/'Reference.h').write_text(f"#define REF_LAST {q['blocks']-1}ULL\n#define REF_CRC 0x{q['full_block_crc32']}U\n#define REF_HEADER 0x{q['gpt_header_crc32']}U\n")
    def run(*argv):return subprocess.run(['wsl','-d','Ubuntu-22.04','--',*argv],capture_output=True,check=True).stdout
    obj=work/'ufs.obj';efi=work/'ufs.efi';dep=work/'headers.d'
    run('/usr/bin/clang','--target=aarch64-pc-windows-msvc','-ffreestanding','-fno-builtin','-fno-stack-protector','-fshort-wchar','-O2','-Wall','-Wextra','-Werror','-MMD','-MF',lin(dep),'-I',lin(work),'-I',lin(inc),'-I',lin(inc/'AArch64'),'-I',lin(display),'-c',lin(source),'-o',lin(obj))
    run('lld-link','/subsystem:efi_boot_service_driver','/entry:NuwaUfsR0Entry','/machine:arm64','/nodefaultlib','/timestamp:0','/out:'+lin(efi),lin(obj))
    pe=run('llvm-readobj','--file-headers','--coff-imports','--coff-basereloc',lin(efi)).decode();assert 'IMAGE_SUBSYSTEM_EFI_BOOT_SERVICE_DRIVER' in pe and 'Import {' not in pe and 'Type: DIR64' in pe
    fd=(transport.ARTIFACT/'build/FV/SILICIUM_UEFI.fd').read_bytes();shim=(transport.ARTIFACT/'shim/shim.bin').read_bytes();stock=transport.STOCK.read_bytes();assert (sha(fd),sha(shim),sha(stock))==(transport.FD_SHA,transport.SHIM_SHA,transport.STOCK_SHA)
    newfd,proof=legacy.repack(fd,efi.read_bytes());(work/'SILICIUM_UEFI.fd').write_bytes(newfd)
    outer,_=legacy.files(newfd);ff=next(v for guid,_,v in outer if guid==legacy.CONTAINER);guide=ff[24:];inner=lzma.decompress(guide[struct.unpack_from('<H',guide,20)[0]:int.from_bytes(guide[:3],'little')],format=lzma.FORMAT_ALONE);inner=inner[4:] if inner[:4]==bytes([4,0,0,25]) else inner;files,_=legacy.files(inner[4:]);drivers=[row for guid,_,row in files if guid==GUID];assert len(drivers)==1 and drivers[0].count(efi.read_bytes())==1
    fat=(ROOT/'out/log-survey-v2-build01/survey.fat.img').read_bytes();assert sha(fat)==FAT_SHA
    old=b'NUWA LOG SURVEY 2 - NO XNU';banner=b'NUWA UFS R0 R1 LU0 READ';assert fat.count(old)==1;fat=fat.replace(old,banner.ljust(len(old)));fp=work/'transport.fat';fp.write_bytes(fat)
    config=run('mtype','-i',lin(fp),'::/EFI/UniXNU/unixnu.toml');assert banner in config and b'action = "exit"' in config
    ram=transport.MAGIC+struct.pack('<IIQI28x',1,64,len(fat),zlib.crc32(fat))+fat;image=transport.compose(stock[:4096],shim+newfd,ram,3);check=transport.inspect_container(image,stock[:4096],shim+newfd,ram,3);out=work/'boot-ufs-r0-r1.img';out.write_bytes(image)
    inputs={}
    for token in dep.read_text().replace(chr(92)+chr(10),' ').split():
        if token.startswith('/mnt/d/') and not token.endswith(':'):
            file=Path('D:/'+token[7:]);inputs[str(file)]=sha(file.read_bytes())
    report=dict(scope='UEFI read-only UFS LU0 baseline, prior to XNU',image_path=out.relative_to(ROOT).as_posix(),image_sha256=sha(image),image_bytes=len(image),efi_sha256=sha(efi.read_bytes()),fd_sha256=sha(newfd),source_sha256=sha(source.read_bytes()),inputs=inputs,reference_sha256=sha(ref.read_bytes()),container=check,original_modules=proof['original_modules'],all_original_ffs_bytes_equal=proof['all_original_ffs_bytes_equal'],hardware_executed=False)
    (work/'package.json').write_text(json.dumps(report,indent=2));print(report['image_sha256'])
if __name__=='__main__':
    try:main()
    except subprocess.CalledProcessError as exc:
        print((exc.stderr or exc.output or b'').decode(errors='replace'));raise
