"""Build isolated FV-resident survey; preserves all original firmware modules."""
import argparse, hashlib, importlib.util, json, lzma, struct, subprocess, uuid, zlib
from pathlib import Path
import usb_ramdisk_package as transport

ROOT=Path(__file__).resolve().parents[1]
FW=ROOT.parent/'uefi-nuwa'
SOURCE=FW/'Platforms/Xiaomi/nuwaPkg/Drivers/NuwaLogSurveyDxe/NuwaLogSurveyDxe.c'
MU=Path('D:/Code/PortingiOSLegacy/common/sources/mu-nuwa-firmware/Mu_Basecore')
GUID='9b7056cb-02b9-47be-bd85-9bbf8a306d01'
CONTAINER='9e21fd93-9c72-4c15-8c4b-e77f1db2d792'
sha=lambda b:hashlib.sha256(b).hexdigest()
align=lambda n,a:(n+a-1)&~(a-1)
def linux(p):return '/mnt/d/'+p.resolve().as_posix()[3:]
def files(raw):
    raw=bytes(raw)
    end=struct.unpack_from('<Q',raw,32)[0];at=align(struct.unpack_from('<H',raw,48)[0],8);out=[]
    while at+24<=end and raw[at:at+24]!=b'\xff'*24:
        size=int.from_bytes(raw[at+20:at+23],'little')
        if raw[at+19]&1:raise ValueError('Extended FFS unsupported')
        if size<24 or at+size>end:raise ValueError('Invalid FFS')
        out.append((str(uuid.UUID(bytes_le=raw[at:at+16])),at,raw[at:at+size]))
        at=align(at+size,8)
    return out,at
def section(kind,body):
    size=len(body)+4
    if size>=0xffffff:raise ValueError('Extended section unsupported')
    return size.to_bytes(3,'little')+bytes([kind])+body
def ffs(guid,kind,body,template=None):
    h=bytearray(template[:24] if template else uuid.UUID(guid).bytes_le+bytes(8))
    h[16]=0;h[17]=(-sum(body))&255;h[18]=kind;h[19]=0x40 if template is None else template[19]
    h[20:23]=(len(body)+24).to_bytes(3,'little');h[23]=0xf8
    if not h[19]&0x40:h[17]=0xaa
    h[16]=(-(sum(h)-h[17]-h[23]))&255
    return bytes(h)+body
def checksum_fv(raw):
    n=struct.unpack_from('<H',raw,48)[0];struct.pack_into('<H',raw,50,0)
    struct.pack_into('<H',raw,50,(-sum(struct.unpack_from('<'+'H'*(n//2),raw)))&65535)
def extend_volume(raw,addition):
    rows,end=files(raw);size=align(end+len(addition),4096)
    if struct.unpack_from('<II',raw,56)[1]!=4096 or any(raw[64:72]):raise ValueError('Unexpected FV block map')
    out=bytearray(raw[:end]+addition+b'\xff'*(size-end-len(addition)))
    struct.pack_into('<Q',out,32,size);struct.pack_into('<I',out,56,size//4096)
    # This fixed input has no used-size extension; refuse unknown metadata.
    ext=struct.unpack_from('<H',raw,52)[0]
    if ext:
        extsize=struct.unpack_from('<I',raw,ext+16)[0]
        if extsize!=20:raise ValueError('Unreviewed FV extension entries')
    checksum_fv(out)
    after,_=files(out)
    if [r[2] for r in rows]!=[r[2] for r in after[:-1]]:raise ValueError('Original FFS changed')
    return bytes(out),len(rows)
def repack(fd,efi):
    entries,_=files(fd);entry=next(r for r in entries if r[0]==CONTAINER)
    original=entry[2];guided=original[24:];offset=struct.unpack_from('<H',guided,20)[0]
    if guided[3]!=2 or guided[4:20]!=uuid.UUID('ee4e5898-3914-4259-9d6e-dc7bd79403cf').bytes_le:raise ValueError('Unexpected compression')
    compressed=guided[offset:int.from_bytes(guided[:3],'little')]
    decoded=lzma.decompress(compressed,format=lzma.FORMAT_ALONE)
    prefix=b''
    if decoded[:4]==b'\x04\x00\x00\x19':prefix=decoded[:4];decoded=decoded[4:]
    if decoded[3]!=0x17 or len(decoded)!=int.from_bytes(decoded[:3],'little'):raise ValueError('Unexpected inner section')
    depex=section(0x13,b'\x06\x08')
    body=depex+bytes(-len(depex)%4)+section(0x10,efi)
    added=ffs(GUID,7,body)
    inner,count=extend_volume(decoded[4:],added)
    expanded=prefix+section(0x17,inner)
    prop=compressed[0];lc=prop%9;v=prop//9;lp=v%5;pb=v//5
    dictionary=struct.unpack_from('<I',compressed,1)[0]
    encoded=lzma.compress(expanded,format=lzma.FORMAT_ALONE,filters=[dict(id=lzma.FILTER_LZMA1,dict_size=dictionary,lc=lc,lp=lp,pb=pb)])
    encoded=encoded[:5]+struct.pack('<Q',len(expanded))+encoded[13:]
    if lzma.decompress(encoded,format=lzma.FORMAT_ALONE)!=expanded:raise ValueError('LZMA mismatch')
    g=bytearray(guided[:offset]);g[:3]=(len(g)+len(encoded)).to_bytes(3,'little')
    updated=ffs(CONTAINER,original[18],bytes(g)+encoded,original)
    if entries[-1][0]!=CONTAINER:raise ValueError('Container is not last outer file')
    at=entry[1]
    if at+len(updated)>len(fd):raise ValueError('FD capacity exceeded')
    result=fd[:at]+updated+b'\xff'*(len(fd)-at-len(updated))
    original_rows,_=files(decoded[4:]);new_rows,_=files(inner)
    if [r[2] for r in new_rows[:-1]]!=[r[2] for r in original_rows]:raise ValueError('Module changed')
    return result,dict(original_modules=count,all_original_ffs_bytes_equal=True,sec_and_outer_prefix_equal=result[:at]==fd[:at],
                       inner_before=len(decoded)-4,inner_after=len(inner),lzma_dictionary=dictionary,driver_guid=GUID,
                       modules=[dict(guid=r[0],sha256=sha(r[2])) for r in original_rows])
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work',required=True,type=Path);args=p.parse_args()
    work=args.work.resolve()
    if not work.is_relative_to(ROOT/'out') or work.exists():raise ValueError('Fresh out directory required')
    work.mkdir(parents=True);commands=[]
    def run(argv):
        r=subprocess.run(argv,capture_output=True,timeout=180);commands.append(dict(argv=argv,exit_code=r.returncode,stdout=r.stdout.decode(errors='replace'),stderr=r.stderr.decode(errors='replace')))
        (work/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
        if r.returncode:raise RuntimeError(commands[-1]['stderr'])
        return r.stdout
    (work/'NuwaLogSurveyDxe.c').write_bytes(SOURCE.read_bytes())
    run(['wsl','-d','Ubuntu-22.04','--','/usr/bin/clang','--target=aarch64-pc-windows-msvc','-ffreestanding','-fno-builtin','-fno-stack-protector','-fshort-wchar','-O2','-Wall','-Wextra','-Werror','-MMD','-MF',linux(work/'driver.d'),'-I',linux(MU/'MdePkg/Include'),'-I',linux(MU/'MdePkg/Include/AArch64'),'-c',linux(work/'NuwaLogSurveyDxe.c'),'-o',linux(work/'driver.obj')])
    pin='cfb93724a06ff86ff5ba971413368a7809ee42a5'
    headers=[]
    for token in (work/'driver.d').read_text().replace('\\\n',' ').split():
        prefix=linux(MU)+'/'
        if token.startswith(prefix):
            rel=token[len(prefix):];raw=(MU/rel).read_bytes().replace(b'\r\n',b'\n')
            pinned=run(['git','-c',f'safe.directory={MU}','-C',str(MU),'show',pin+':'+rel]).replace(b'\r\n',b'\n')
            if raw!=pinned:raise ValueError('UEFI header differs from pin: '+rel)
            headers.append(dict(path=rel,sha256=sha(raw)))
    if not headers:raise ValueError('No header dependencies')
    (work/'headers.json').write_text(json.dumps(dict(commit=pin,headers=headers),indent=2)+'\n')
    run(['wsl','-d','Ubuntu-22.04','--','lld-link','/subsystem:efi_boot_service_driver','/entry:NuwaLogSurveyDxeEntry','/machine:arm64','/nodefaultlib','/timestamp:0','/out:'+linux(work/'NuwaLogSurveyDxe.efi'),linux(work/'driver.obj')])
    pe=run(['wsl','-d','Ubuntu-22.04','--','llvm-readobj','--file-headers','--coff-imports','--coff-basereloc',linux(work/'NuwaLogSurveyDxe.efi')]).decode()
    if 'IMAGE_SUBSYSTEM_EFI_BOOT_SERVICE_DRIVER' not in pe or 'Import {' in pe or 'Type: DIR64' not in pe:raise ValueError('PE ABI/relocation check failed')
    (work/'pe.txt').write_text(pe)
    artifact=transport.ARTIFACT
    fd=(artifact/'build/FV/SILICIUM_UEFI.fd').read_bytes();shim=(artifact/'shim/shim.bin').read_bytes();stock=transport.STOCK.read_bytes()
    if (sha(fd),sha(shim),sha(stock))!=(transport.FD_SHA,transport.SHIM_SHA,transport.STOCK_SHA):raise ValueError('Pinned input mismatch')
    efi=(work/'NuwaLogSurveyDxe.efi').read_bytes();newfd,proof=repack(fd,efi)
    (work/'SILICIUM_UEFI.fd').write_bytes(newfd)
    spec=importlib.util.spec_from_file_location('inspect_fw',ROOT/'scripts/ci/inspect-firmware-candidate.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    parsed=mod.Firmware();parsed.volume(newfd,'survey')
    drivers=[f for f in parsed.files if f['guid']==GUID]
    if len(drivers)!=1 or drivers[0]['type']!=7:raise ValueError('Survey driver missing')
    (work/'firmware-inspection.json').write_text(json.dumps(dict(volumes=parsed.volumes,files=parsed.files,guided=parsed.guided),indent=2)+'\n')
    # No XNU or external EFI: exit-only menu triggers the existing ReadyToBoot path.
    config=b'version = 1\n[boot]\ntimeout = 0\ndefault = "exit"\n[kits]\nautoload = false\n[ui]\ntitle = "NUWA LOG SURVEY 1 - NO XNU"\n[[entry]]\nid = "exit"\ntitle = "Survey complete"\ntype = "action"\naction = "exit"\n'
    fat=work/'survey.fat.img'
    run(['wsl','-d','Ubuntu-22.04','--','env','TZ=UTC','mformat','-C','-F','-T','131072','-v','NUWASURVEY','-N','53555231','-i',linux(fat),'::'])
    for d in ('::/EFI','::/EFI/UniXNU'):run(['wsl','-d','Ubuntu-22.04','--','mmd','-i',linux(fat),d])
    (work/'unixnu.toml').write_bytes(config)
    run(['wsl','-d','Ubuntu-22.04','--','mcopy','-i',linux(fat),linux(work/'unixnu.toml'),'::/EFI/UniXNU/unixnu.toml'])
    run(['wsl','-d','Ubuntu-22.04','--','mcopy','-i',linux(fat),'::/EFI/UniXNU/unixnu.toml',linux(work/'config-readback.toml')])
    if (work/'config-readback.toml').read_bytes()!=config:raise ValueError('FAT readback differs')
    raw=fat.read_bytes();ramdisk=transport.MAGIC+struct.pack('<IIQI28x',1,64,len(raw),zlib.crc32(raw))+raw
    image=transport.compose(stock[:4096],shim+newfd,ramdisk,3)
    checks=transport.inspect_container(image,stock[:4096],shim+newfd,ramdisk,3)
    (work/'boot-log-survey-v1.img').write_bytes(image)
    report=dict(scope='Offline survey candidate; no XNU and no cross-reset writer/reader',source_sha256=sha(SOURCE.read_bytes()),driver_sha256=sha(efi),fd_sha256=sha(newfd),original_fd_sha256=sha(fd),shim_sha256=sha(shim),image_sha256=sha(image),image_bytes=len(image),proof=proof,container=checks,device_accessed=False,hardware_qualified=False)
    (work/'package.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ('image_sha256','image_bytes','driver_sha256','fd_sha256')}))
if __name__=='__main__':main()
