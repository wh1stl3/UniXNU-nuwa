"""Run actual EFI application file/protocol refusals under user AArch64 QEMU."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from native_prelink_inputs import ROOT


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--output',type=Path,required=True)
    args=cli.parse_args()
    target=args.output.resolve()
    if not target.is_relative_to(ROOT/'reports') or target.exists():
        raise ValueError('Fresh reports output required')
    prefix='/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/'
    fixture=ROOT/'out/file-read-audit/build-02'
    commands=[]
    def run(argv):
        result=subprocess.run(['wsl','-d','Ubuntu-22.04','--',*argv],capture_output=True,timeout=90)
        commands.append(dict(argv=argv,exit_code=result.returncode,stdout=result.stdout.decode(),stderr=result.stderr.decode()))
        result.check_returncode()
        return result.stdout.decode()
    run(['aarch64-linux-gnu-g++','-std=c++17','-static','-O2','-fshort-wchar','-Wall','-Wextra','-Werror','-Wno-unused-parameter',
         '-I',prefix+'out/file-read-audit/build-02',
         '-I','/mnt/d/Code/PortingiOSLegacy/common/sources/mu-nuwa-firmware/Mu_Basecore/MdePkg/Include',
         '-I','/mnt/d/Code/PortingiOSLegacy/common/sources/mu-nuwa-firmware/Mu_Basecore/MdePkg/Include/AArch64',
         prefix+'tests/file_audit_host.cpp',prefix+'package/NuwaFileAudit/FileAudit.cpp',
         prefix+'out/file-read-audit/build-02/NativeAdrenoSha256.cpp','-o',prefix+'out/file-read-audit/build-02/host-test-recorded'])
    result=run([prefix+'out/upstream-host-tests/qemu-runtime/usr/bin/qemu-aarch64',
                prefix+'out/file-read-audit/build-02/host-test-recorded',
                prefix+'out/native-prelink-merged/analysis/kernel-prelinked-analysis.macho'])
    if 'PASS actual EFI app: 13 file/protocol cases' not in result:
        raise ValueError('Expected fixture result absent')
    report=dict(scope='Actual app with software UEFI protocol callbacks under user QEMU; not real firmware protocol or device',
        commands=commands,cases=13,known_sha_vectors=3,
        harness_sha256=hashlib.sha256((ROOT/'tests/file_audit_host.cpp').read_bytes()).hexdigest(),
        all_allocations_freed_and_file_handles_closed=True,
        separately_exercised_freestanding_memory_helpers=False,
        limitation='Host fixture uses libc memory primitives; target freestanding helpers are exercised by full UEFI QEMU PE load instead',
        device_accessed=False)
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(result.strip())


if __name__=='__main__':main()
