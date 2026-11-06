"""Build a fixed 64MiB FAT file-audit fixture with complete file readback."""
import hashlib
import json
from pathlib import Path
import os
import subprocess
import tomllib
from native_prelink_inputs import ROOT

OUT=ROOT/'out/file-read-audit/fat-02'
REPORT=ROOT/'reports/file-read-audit/fat-02.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def linux(path):
    text=path.resolve().as_posix()
    if not text.startswith('D:/Code/PortingiOS/nuwa/UniXNU-nuwa/'):
        raise ValueError('Local device workspace path required')
    return '/mnt/d/'+text[3:]


def main():
    if OUT.exists() or REPORT.exists():
        raise ValueError('Fresh FAT fixture required')
    build=json.loads((ROOT/'reports/file-read-audit/build-02.json').read_text())
    app=ROOT/build['efi_path']
    data=ROOT/build['read_fixture']['path']
    if sha(app)!='def33a4add6f162a5726bba050a4c143c8ba38ea25f436f46ce4331811bb469f' or sha(data)!=build['read_fixture']['sha256']:
        raise ValueError('Fixed app or data changed')
    config=(ROOT/'config/file-read-audit/unixnu.toml').read_bytes().replace(b'\r\n',b'\n')
    parsed=tomllib.loads(config.decode())
    if parsed['entry']!=[dict(id='file-audit',title='Read 58 MB data and verify SHA256',type='efi',path='Payloads/FILEAUDIT.EFI')]:
        raise ValueError('Unexpected EFI-only audit menu')
    OUT.mkdir(parents=True)
    (OUT/'unixnu.toml').write_bytes(config)
    os.utime(OUT/'unixnu.toml',(315532800,315532800))
    commands=[]
    def run(*argv):
        command=['wsl','-d','Ubuntu-22.04','--','env','TZ=UTC','MTOOLS_SKIP_CHECK=1',*argv]
        result=subprocess.run(command,capture_output=True,timeout=90)
        commands.append(dict(argv=command,exit_code=result.returncode,stdout=result.stdout.decode(errors='replace'),stderr=result.stderr.decode(errors='replace')))
        result.check_returncode()
        return result.stdout
    image=OUT/'file-audit.fat.img'
    run('mformat','-C','-F','-T','131072','-v','NUWAFILE','-N','46494c45','-i',linux(image),'::')
    for directory in ('::/EFI','::/EFI/BOOT','::/EFI/UniXNU','::/EFI/UniXNU/Payloads'):
        run('mmd','-i',linux(image),directory)
    # Fixed file timestamps without changing read-only input files.
    for source,dest in ((OUT/'unixnu.toml','::/EFI/UniXNU/unixnu.toml'),
                        (app,'::/EFI/UniXNU/Payloads/FILEAUDIT.EFI'),
                        (app,'::/EFI/BOOT/BOOTAA64.EFI'),
                        (data,'::/EFI/UniXNU/Payloads/READTEST.BIN'),
                        (app.parent/'LICENSE','::/EFI/UniXNU/Payloads/SHA256-LICENSE.TXT')):
        # Source payloads stay untouched; stage exact copies with fixed timestamp.
        stage=OUT/('stage-'+Path(dest).name)
        stage.write_bytes(source.read_bytes())
        os.utime(stage,(315532800,315532800))
        run('mcopy','-m','-i',linux(image),linux(stage),dest)
        extracted=OUT/('readback-'+Path(dest).name)
        run('mcopy','-i',linux(image),dest,linux(extracted))
        if sha(source)!=sha(extracted):
            raise ValueError('FAT file readback differs: '+dest)
    run('mdir','-i',linux(image),'-/','::/')
    result=dict(scope='Offline FAT fixture; data file is never an executable menu entry',
        image_path=image.relative_to(ROOT).as_posix(),bytes=image.stat().st_size,sha256=sha(image),
        app_sha256=sha(app),data_sha256=sha(data),data_bytes=data.stat().st_size,
        config_lf_sha256=hashlib.sha256(config).hexdigest(),config=parsed,
        fallback_boot_path='EFI/BOOT/BOOTAA64.EFI is the same read-only audit application',
        full_fat_file_readback=True,commands=commands,device_accessed=False)
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    REPORT.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(sha256=result['sha256'],bytes=result['bytes'],data_bytes=result['data_bytes'])))


if __name__=='__main__':main()
