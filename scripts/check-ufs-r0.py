"""Check the released UFS-R0 image, execute the read-only fixture, compare reproducible builds."""
import argparse, hashlib, json, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SHA=lambda data:hashlib.sha256(data).hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--first',type=Path,required=True);parser.add_argument('--second',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);a=parser.parse_args()
    if a.output.exists():raise ValueError('Fresh report required')
    first=json.loads((a.first/'package.json').read_bytes());second=json.loads((a.second/'package.json').read_bytes());assert a.first.resolve()!=a.second.resolve()
    for key in ('efi_sha256','fd_sha256','source_sha256','reference_sha256','image_sha256','original_modules'):
        assert first[key]==second[key],key
    assert first['all_original_ffs_bytes_equal'] and SHA((ROOT/first['image_path']).read_bytes())==first['image_sha256']==SHA((ROOT/second['image_path']).read_bytes())
    for path,digest in first['inputs'].items():assert SHA(Path(path).read_bytes())==digest,path
    assert SHA((ROOT/'reports/ufs-r0-r1/android-lu0.json').read_bytes())==first['reference_sha256']
    inc='/mnt/d/Code/PortingiOSLegacy/common/sources/mu-nuwa-firmware/Mu_Basecore/MdePkg/Include';work=ROOT/'out/ufs-r0-r1-host';work.mkdir(exist_ok=True);exe='out/ufs-r0-r1-host/test-nopie'
    def run(*cmd):return subprocess.run(['wsl','-d','Ubuntu-22.04','--',*cmd],cwd=ROOT,capture_output=True,check=True).stdout
    run('/usr/bin/clang','-std=c11','-O1','-g','-no-pie','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fshort-wchar','-Itests/ufs_r0_fixture','-I../uefi-nuwa/Platforms/Xiaomi/nuwaPkg/Drivers/NuwaLogSurvey2Dxe','-I'+inc,'-I'+inc+'/X64','tests/ufs_r0_host.c','-o',exe)
    output=run(exe).decode().strip();assert output.startswith('PASS ')
    a.output.parent.mkdir(exist_ok=True,parents=True);a.output.write_text(json.dumps(dict(passed=True,reference=first['reference_sha256'],host_result=output,host_test_sha256=SHA((ROOT/'tests/ufs_r0_host.c').read_bytes()),reproduced=True,containers=[first['image_path'],second['image_path']],boot_sha256=first['image_sha256'],efi_sha256=first['efi_sha256'],original_modules_preserved=first['original_modules'],firmware_executed=False,xnu_executed=False),indent=2));print(output,first['image_sha256'])
if __name__=='__main__':main()
