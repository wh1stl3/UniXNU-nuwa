"""Cross-compile actual FV driver and run bounded read/refusal software cases."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from native_prelink_inputs import ROOT


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--work',type=Path,required=True)
    cli.add_argument('--output',type=Path,required=True)
    args=cli.parse_args()
    work,out=args.work.resolve(),args.output.resolve()
    if not work.is_relative_to(ROOT/'out') or work.exists() or not out.is_relative_to(ROOT/'reports') or out.exists():
        raise ValueError('Fresh local out/reports paths required')
    work.mkdir(parents=True)
    driver=Path('D:/Code/uefi-nuwa/Platforms/Xiaomi/nuwaPkg/Drivers/NuwaFileAuditDxe/NuwaFileAuditDxe.c')
    def linux(path):
        return '/mnt/d/'+path.resolve().as_posix().split(':/',1)[1]
    adapter=work/'adapter.c'
    adapter.write_text('#include "'+linux(driver)+'"\nEFI_STATUS TestAuditVolumes(void) {return AuditVolumes();}\nvoid TestReady(void){Ready(NULL,NULL);}\n',encoding='utf-8')
    mu='/mnt/d/Code/PortingiOS/common/sources/mu-nuwa-firmware/Mu_Basecore/'
    common=['-fshort-wchar','-ffunction-sections','-Wall','-Wextra','-Werror','-Wno-unused-parameter',
            '-I',mu+'MdePkg/Include','-I',mu+'MdePkg/Include/AArch64','-I',mu+'CryptoPkg/Include']
    commands=[]
    def run(argv):
        full=['wsl','-d','Ubuntu-22.04','--',*argv]
        result=subprocess.run(full,capture_output=True,timeout=90)
        commands.append(dict(argv=full,exit_code=result.returncode,stdout=result.stdout.decode(),stderr=result.stderr.decode()))
        result.check_returncode();return result.stdout.decode()
    run(['aarch64-linux-gnu-gcc','-DMDEPKG_NDEBUG',*common,'-c',linux(adapter),'-o',linux(work/'driver.o')])
    run(['aarch64-linux-gnu-g++','-std=c++17','-static','-O2','-Wl,--gc-sections',*common,
         '-I',linux(ROOT/'out/file-read-audit/build-02'),linux(ROOT/'tests/fv_file_audit_host.cpp'),
         linux(work/'driver.o'),linux(ROOT/'out/file-read-audit/build-02/NativeAdrenoSha256.cpp'),'-o',linux(work/'test')])
    result=run([linux(ROOT/'out/upstream-host-tests/qemu-runtime/usr/bin/qemu-aarch64'),linux(work/'test'),
                linux(ROOT/'out/native-prelink-merged/analysis/kernel-prelinked-analysis.macho')])
    if 'PASS actual FV driver: 19 ' not in result:
        raise ValueError('Expected actual driver fixture output absent')
    report=dict(scope='Actual driver in AArch64 software UEFI protocol fixture; target BaseCryptLib is not linked here',
        driver_sha256=hashlib.sha256(driver.read_bytes()).hexdigest(),
        harness_sha256=hashlib.sha256((ROOT/'tests/fv_file_audit_host.cpp').read_bytes()).hexdigest(),
        cases=19,one_shot_callback_passed=True,pools_and_handles_balanced=True,commands=commands,
        crypto_callback='Pinned NativeAdreno hash for software fixture; real firmware library checked separately in CI',
        device_accessed=False)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(result.strip())


if __name__=='__main__':main()
