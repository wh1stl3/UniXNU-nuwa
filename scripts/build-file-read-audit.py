"""Build a standalone read-only EFI audit app; leave firmware and phone untouched."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from native_prelink_inputs import ROOT, inputs

SOURCE = Path('D:/Code/UniXNU-integration/drivers/NativeAdreno')
PIN = 'b686b9054f57d393c80195b82568a09f8ca106a2'
MU = Path('D:/Code/PortingiOS/common/sources/mu-nuwa-firmware/Mu_Basecore')
MU_PIN = 'cfb93724a06ff86ff5ba971413368a7809ee42a5'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def git(repo, *args):
    return subprocess.check_output(['git', '--no-optional-locks', '-c', f'safe.directory={repo}', '-C', str(repo), *args])


def linux(path):
    text = path.resolve().as_posix()
    if not text.startswith('D:/Code/'):
        raise ValueError('Expected a local D:/Code path')
    return '/mnt/d/' + text[3:]


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--work', type=Path, required=True)
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    work, output = args.work.resolve(), args.output.resolve()
    if not work.is_relative_to(ROOT/'out') or work.exists():
        raise ValueError('Fresh out/ workspace required')
    if not output.is_relative_to(ROOT/'reports') or output.exists():
        raise ValueError('Fresh reports/ output required')
    if git(SOURCE, 'rev-parse', 'HEAD').decode().strip()!=PIN or git(MU, 'rev-parse', 'HEAD').decode().strip()!=MU_PIN:
        raise ValueError('Fixed source HEAD changed')
    profile_path=ROOT/'config/native-prelink-merged-analysis-profile.json'
    # The analytical file is treated only as bytes. Never use its code entry.
    profile, _, _, _ = inputs(profile_path)
    fixture=ROOT/'out/native-prelink-merged/analysis/kernel-prelinked-analysis.macho'
    data=fixture.read_bytes()
    if sha(data)!='eb66542cc9b6c34f369c07229900408ab67288152f561be63fa6061efce9ffca' or len(data)!=58335232:
        raise ValueError('Pinned read-only fixture changed')
    work.mkdir(parents=True)
    upstream=[]
    for name in ('NativeAdrenoSha256.h','NativeAdrenoSha256.cpp','LICENSE'):
        raw=git(SOURCE,'show',PIN+':'+name)
        (work/name).write_bytes(raw)
        upstream.append(dict(path=name,sha256=sha(raw),commit=PIN,repository='https://github.com/UniXNU/NativeAdreno',license='MIT'))
    expected='// Generated fixed data identity, not an OS entry point.\n#define NUWA_FILE_BYTES 58335232u\nstatic const UINT8 NuwaExpectedSha[32]={'+','.join('0x'+sha(data)[i:i+2] for i in range(0,64,2))+'};\n'
    (work/'ExpectedFile.h').write_text(expected,encoding='utf-8')
    commands=[]
    def run(argv):
        result=subprocess.run(argv,capture_output=True,timeout=120)
        commands.append(dict(argv=argv,exit_code=result.returncode,stdout=result.stdout.decode(errors='replace'),stderr=result.stderr.decode(errors='replace')))
        if result.returncode:
            print(commands[-1]['stderr'])
        result.check_returncode()
        return result.stdout.decode()
    includes=[ROOT/'package/NuwaFileAudit/include',work,MU/'MdePkg/Include',MU/'MdePkg/Include/AArch64']
    sources=[ROOT/'package/NuwaFileAudit/FileAudit.cpp',ROOT/'package/NuwaFileAudit/Memory.cpp',work/'NativeAdrenoSha256.cpp']
    for index, source in enumerate(sources):
        run(['wsl','-d','Ubuntu-22.04','--','clang++','--target=aarch64-pc-windows-msvc','-std=c++17',
             '-ffreestanding','-fno-builtin','-fno-exceptions','-fno-rtti','-fno-stack-protector','-O2',
             '-Wall','-Wextra','-Werror','-Wno-unused-parameter','-MMD','-MF',linux(work/f'{index}.d'),
             *[item for path in includes for item in ('-I',linux(path))],'-c',linux(source),'-o',linux(work/f'{index}.obj')])
    run(['wsl','-d','Ubuntu-22.04','--','lld-link','/subsystem:efi_application','/entry:EfiMain','/machine:arm64',
         '/nodefaultlib','/timestamp:0','/opt:ref','/out:'+linux(work/'FILEAUDIT.EFI'),
         *[linux(work/f'{i}.obj') for i in range(len(sources))]])
    # Audit each actually consumed Mu header against its immutable Git blob.
    dependencies=set()
    for index in range(len(sources)):
        dep=(work/f'{index}.d').read_text().replace('\\\n',' ')
        for token in dep.split():
            prefix=linux(MU)+'/'
            if token.startswith(prefix):
                dependencies.add(token[len(prefix):])
    if not dependencies:
        raise ValueError('No actual UEFI header dependencies captured')
    headers=[]
    for path in sorted(dependencies):
        raw=(MU/path).read_bytes().replace(b'\r\n',b'\n')
        pinned=git(MU,'show',MU_PIN+':'+path).replace(b'\r\n',b'\n')
        if raw!=pinned:
            raise ValueError('Consumed UEFI header differs from pin: '+path)
        headers.append(dict(path=path,lf_sha256=sha(raw)))
    pe=run(['wsl','-d','Ubuntu-22.04','--','llvm-readobj','--file-headers','--coff-imports','--coff-basereloc',linux(work/'FILEAUDIT.EFI')])
    if 'IMAGE_SUBSYSTEM_EFI_APPLICATION' not in pe or 'IMAGE_FILE_MACHINE_ARM64' not in pe or 'Import {' in pe:
        raise ValueError('Wrong PE machine/subsystem or dynamic imports')
    (work/'pe-inspection.txt').write_text(pe,encoding='utf-8')
    artifact=work/'FILEAUDIT.EFI'
    result=dict(scope='Standalone EFI application built offline; no firmware or device modification',
        efi_path=artifact.relative_to(ROOT).as_posix(),efi_sha256=sha(artifact.read_bytes()),efi_bytes=artifact.stat().st_size,
        read_fixture=dict(path=fixture.relative_to(ROOT).as_posix(),sha256=sha(data),bytes=len(data),role='Read-only bytes; never execute or infer OS qualification'),
        upstream_sha256_source=upstream,uefi_headers=dict(repository='https://github.com/microsoft/mu_basecore',commit=MU_PIN,consumed=headers),
        own_sources=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p.read_bytes())) for p in sources[:2]],
        commands=commands,system_pool_allocation_bytes=len(data),read_chunk_bytes=1048576,max_read_calls=4096,
        payload_packaged=False,device_accessed=False,runtime_verified=False,
        limitations=['Real EFI image load policy, file read and AllocatePool need a separately captured trial',
                     'No early initializer mapping, Apple ADT, OS window or kernel execution',
                     'SHA256 implementation is unchanged upstream, not a FIPS validated cryptographic module'])
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(efi_sha256=result['efi_sha256'],bytes=result['efi_bytes'],headers=len(headers))))


if __name__=='__main__':
    main()
