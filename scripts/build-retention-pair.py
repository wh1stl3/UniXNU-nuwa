"""Build and qualify isolated UEFI RAM pattern writer/reader; never access devices."""
import argparse
import hashlib
import importlib.util
import json
import secrets
import re
import struct
import subprocess
import uuid
import zlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FW=ROOT.parent/'uefi-nuwa'
MU=Path('D:/Code/PortingiOSLegacy/common/sources/mu-nuwa-firmware/Mu_Basecore')
sha=lambda b:hashlib.sha256(b).hexdigest()
def module(path,name):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def linux(p):return '/mnt/d/'+p.resolve().as_posix()[3:]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work',required=True,type=Path)
    p.add_argument('--nonce',help='Reuse exact 32 hex digits only for offline reproduction')
    a=p.parse_args();work=a.work.resolve()
    if work.exists() or not work.is_relative_to(ROOT/'out'):p.error('Fresh out directory required')
    nonce=bytes.fromhex(a.nonce) if a.nonce else secrets.token_bytes(16)
    if len(nonce)!=16 or not any(nonce):p.error('Need nonzero 16-byte nonce')
    work.mkdir(parents=True);commands=[];wsl=['wsl','-d','Ubuntu-22.04','--']
    def run(argv):
        r=subprocess.run(argv,capture_output=True,timeout=180)
        commands.append(dict(argv=argv,exit_code=r.returncode,stdout=r.stdout.decode(errors='replace'),stderr=r.stderr.decode(errors='replace')))
        (work/'commands.json').write_text(json.dumps(commands,indent=2)+'\n',encoding='utf-8')
        if r.returncode:raise RuntimeError(commands[-1])
        return r.stdout
    survey=module(ROOT/'scripts/build-log-survey-v2.py','survey');transport=survey.transport
    inspector=module(ROOT/'scripts/ci/inspect-firmware-candidate.py','inspector')
    fd=(transport.ARTIFACT/'build/FV/SILICIUM_UEFI.fd').read_bytes();shim=(transport.ARTIFACT/'shim/shim.bin').read_bytes();stock=transport.STOCK.read_bytes()
    if (sha(fd),sha(shim),sha(stock))!=(transport.FD_SHA,transport.SHIM_SHA,transport.STOCK_SHA):raise ValueError('Fixed input mismatch')
    sources=[FW/'Platforms/Xiaomi/nuwaPkg/Drivers/NuwaRetentionDxe/NuwaRetentionDxe.c',ROOT/'tests/nuwa_retention_format.h',ROOT/'tests/retention_uefi_host.c',Path(__file__).resolve()]
    display=FW/'Platforms/Xiaomi/nuwaPkg/Drivers/NuwaLogSurvey2Dxe'
    sources += [display/'SurveyDisplay.h',display/'Font.h',ROOT/'scripts/build-log-survey-v2.py',ROOT/'scripts/usb_ramdisk_package.py',ROOT/'scripts/ci/inspect-firmware-candidate.py']
    seal=[dict(path=str(f),sha256=sha(f.read_bytes())) for f in sources]
    (work/'trial.json').write_text(json.dumps(dict(nonce=nonce.hex(),sequence_base=1,addresses=['0x880000000','0x8b9f00000'],window=65536,device_accessed=False),indent=2)+'\n')
    outputs=[]
    for role in ('reader','writer'):
        folder=work/role;folder.mkdir()
        for src in sources[:3]+[display/'SurveyDisplay.h',display/'Font.h']:(folder/src.name).write_bytes(src.read_bytes())
        config='#define NR_WRITER '+str(int(role=='writer'))+'\n#define NR_TRIAL_SEQUENCE 1ULL\n#define NR_TRIAL_NONCE {'+','.join('0x%02x'%b for b in nonce)+'}\n'
        (folder/'TrialConfig.h').write_bytes(config.encode())
        includes=['-I',linux(folder),'-I',linux(MU/'MdePkg/Include'),'-I',linux(MU/'MdePkg/Include/AArch64')]
        run(wsl+['aarch64-linux-gnu-gcc','-static','-O2','-fshort-wchar','-Wall','-Wextra','-Werror']+includes+[linux(folder/'retention_uefi_host.c'),'-o',linux(folder/'host-test')])
        qemu=ROOT/'out/upstream-host-tests/qemu-runtime/usr/bin/qemu-aarch64'
        test=run(wsl+[linux(qemu),linux(folder/'host-test')]);(folder/'host-test.txt').write_bytes(test)
        if b'PASS actual UEFI' not in test:raise ValueError('Missing callback test result')
        run(wsl+['/usr/bin/clang','--target=aarch64-pc-windows-msvc','-ffreestanding','-fno-builtin','-fno-stack-protector','-fshort-wchar','-O2','-Wall','-Wextra','-Werror','-MMD','-MF',linux(folder/'driver.d')]+includes+['-c',linux(folder/'NuwaRetentionDxe.c'),'-o',linux(folder/'driver.obj')])
        run(wsl+['lld-link','/subsystem:efi_boot_service_driver','/entry:NuwaRetentionEntry','/machine:arm64','/nodefaultlib','/timestamp:0','/out:'+linux(folder/'NuwaRetentionDxe.efi'),linux(folder/'driver.obj')])
        pe=run(wsl+['llvm-readobj','--file-headers','--coff-imports','--coff-basereloc',linux(folder/'NuwaRetentionDxe.efi')]);(folder/'pe.txt').write_bytes(pe)
        reloc=run(wsl+['llvm-readobj','--relocations',linux(folder/'driver.obj')]);(folder/'object-relocations.txt').write_bytes(reloc)
        types=set(re.findall(rb'IMAGE_REL_ARM64_[A-Z0-9_]+',reloc))
        relative={b'IMAGE_REL_ARM64_PAGEBASE_REL21',b'IMAGE_REL_ARM64_PAGEOFFSET_12A',b'IMAGE_REL_ARM64_PAGEOFFSET_12L',b'IMAGE_REL_ARM64_BRANCH26',b'IMAGE_REL_ARM64_REL21'}
        if b'IMAGE_SUBSYSTEM_EFI_BOOT_SERVICE_DRIVER' not in pe or b'Import {' in pe or b'IMAGE_FILE_RELOCS_STRIPPED' in pe:raise ValueError('Invalid PE')
        if b'Type: DIR64' not in pe and (not types or not types<=relative):raise ValueError('No base relocs but non-relative object references')
        guid=str(uuid.uuid5(uuid.NAMESPACE_URL,'nuwa-retention-v1/'+nonce.hex()+'/'+role));survey.GUID=guid
        efi=(folder/'NuwaRetentionDxe.efi').read_bytes();newfd,proof=survey.repack(fd,efi)
        (folder/'SILICIUM_UEFI.fd').write_bytes(newfd)
        parsed=inspector.Firmware();parsed.volume(newfd,role)
        if len([f for f in parsed.files if f['guid']==guid and f['type']==7])!=1:raise ValueError('Driver not found')
        # Exit-only menu: no XNU. Writer Reserved pages remain held after callback.
        config=('version = 1\n[boot]\ntimeout = 0\ndefault = "exit"\n[kits]\nautoload = false\n[ui]\ntitle = "NUWA RAM '+role.upper()+' - NO XNU"\n[[entry]]\nid = "exit"\ntitle = "RAM trial complete"\ntype = "action"\naction = "exit"\n').encode()
        fat=folder/'trial.fat.img';(folder/'unixnu.toml').write_bytes(config)
        run(wsl+['env','TZ=UTC','mformat','-C','-F','-T','131072','-v','NUWARETAIN','-N','52455431','-i',linux(fat),'::'])
        for d in ('::/EFI','::/EFI/UniXNU'):run(wsl+['mmd','-i',linux(fat),d])
        run(wsl+['mcopy','-i',linux(fat),linux(folder/'unixnu.toml'),'::/EFI/UniXNU/unixnu.toml'])
        run(wsl+['mcopy','-i',linux(fat),'::/EFI/UniXNU/unixnu.toml',linux(folder/'config-readback.toml')])
        if (folder/'config-readback.toml').read_bytes()!=config:raise ValueError('Config differs')
        raw=fat.read_bytes();ram=transport.MAGIC+struct.pack('<IIQI28x',1,64,len(raw),zlib.crc32(raw))+raw
        image=transport.compose(stock[:4096],shim+newfd,ram,3);checks=transport.inspect_container(image,stock[:4096],shim+newfd,ram,3)
        (folder/'boot-retention.img').write_bytes(image)
        deps=[]
        for token in (folder/'driver.d').read_text().replace('\\\n',' ').split():
            if token.startswith('/mnt/d/') and not token.endswith(':'):
                local=Path('D:/'+token[len('/mnt/d/'):]);deps.append(dict(path=str(local),sha256=sha(local.read_bytes())))
        report=dict(role=role,nonce=nonce.hex(),sequence_base=1,image_sha256=sha(image),image_bytes=len(image),driver_sha256=sha(efi),fd_sha256=sha(newfd),guid=guid,proof=proof,container=checks,dependencies=deps,scope='Offline PE/package and QEMU user-mode callback qualification only',device_accessed=False,reset_retention_proven=False)
        (folder/'package.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');outputs.append(report)
    (work/'qualification.json').write_text(json.dumps(dict(packages=outputs,source_seal=seal,scope='Offline paired pattern experiment, not production logs or hardware retention',device_accessed=False),indent=2)+'\n',encoding='utf-8')
    print(json.dumps([dict(role=x['role'],image_sha256=x['image_sha256']) for x in outputs]))

if __name__=='__main__':main()
