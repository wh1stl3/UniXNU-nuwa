"""Create a data-only FAT for the ReadyToBoot FV driver; no external EFI app."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tomllib
from native_prelink_inputs import ROOT


def main():
    work=ROOT/'out/fv-file-audit/data-01'
    output=ROOT/'reports/fv-file-audit/data-01.json'
    if work.exists() or output.exists():
        raise ValueError('Fresh output paths required')
    data=ROOT/'out/native-prelink-merged/analysis/kernel-prelinked-analysis.macho'
    sha=lambda raw:hashlib.sha256(raw).hexdigest()
    data_sha=sha(data.read_bytes())
    if data_sha!='eb66542cc9b6c34f369c07229900408ab67288152f561be63fa6061efce9ffca' or data.stat().st_size!=58335232:
        raise ValueError('Fixed data fixture changed')
    config=(ROOT/'config/fv-file-audit/unixnu.toml').read_bytes().replace(b'\r\n',b'\n')
    parsed=tomllib.loads(config.decode())
    if parsed['entry']!=[dict(id='audit-exit',title='FV file audit completed - return to firmware',type='action',action='exit')]:
        raise ValueError('Only the exit action is permitted')
    work.mkdir(parents=True)
    commands=[]
    def linux(path):return '/mnt/d/'+path.resolve().as_posix().split(':/',1)[1]
    def run(*args):
        command=['wsl','-d','Ubuntu-22.04','--','env','TZ=UTC','MTOOLS_SKIP_CHECK=1',*args]
        result=subprocess.run(command,capture_output=True,timeout=90)
        commands.append(dict(argv=command,exit_code=result.returncode,stdout=result.stdout.decode(errors='replace'),stderr=result.stderr.decode(errors='replace')))
        result.check_returncode()
    image=work/'data.fat.img'
    run('mformat','-C','-F','-T','131072','-v','NUWAFVDATA','-N','46564441','-i',linux(image),'::')
    for name in ('::/EFI','::/EFI/UniXNU','::/EFI/UniXNU/Payloads'):
        run('mmd','-i',linux(image),name)
    for name,raw,dest in (('unixnu.toml',config,'::/EFI/UniXNU/unixnu.toml'),
                           ('READTEST.BIN',data.read_bytes(),'::/EFI/UniXNU/Payloads/READTEST.BIN')):
        stage=work/name;stage.write_bytes(raw);os.utime(stage,(315532800,315532800))
        run('mcopy','-m','-i',linux(image),linux(stage),dest)
        readback=work/('readback-'+name)
        run('mcopy','-i',linux(image),dest,linux(readback))
        if sha(readback.read_bytes())!=sha(raw):
            raise ValueError('FAT readback differs: '+name)
    run('mdir','-i',linux(image),'-/','::/')
    result=dict(scope='64MiB data-only FAT; no EFI application or XNU boot entry',
        path=image.relative_to(ROOT).as_posix(),bytes=image.stat().st_size,sha256=sha(image.read_bytes()),
        data_bytes=data.stat().st_size,data_sha256=data_sha,config=parsed,config_lf_sha256=sha(config),
        exact_files=['EFI/UniXNU/unixnu.toml','EFI/UniXNU/Payloads/READTEST.BIN'],
        full_file_readback=True,kernel_execution_enabled=False,commands=commands,device_accessed=False)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(bytes=result['bytes'],sha256=result['sha256'])))


if __name__=='__main__':main()
