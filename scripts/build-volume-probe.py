"""Build and inspect an offline FAT discovery fixture; never package or boot it.

Uses the pinned UniXNU payload.py mformat/mcopy procedure through local WSL.
The fixture contains one action-only configuration, no kernel or Apple ADT.
"""
import datetime
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import tomllib

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path('D:/Code/PortingiOSLegacy/common/sources/UniXNU')
PIN = '75bc13dd34dc4e403826793739e316a264ce00dd'
GIT = 'C:/Program Files/Git/cmd/git.exe'
OUT = ROOT / 'out/volume-probe'
REPORT = ROOT / 'reports/system-volume-audit/volume-probe.json'


def main():
    if OUT.exists() or REPORT.exists():
        raise ValueError('Fresh fixture destination required')
    source_hashes = {}
    for name in ('scripts/unixnu/payload.py', 'package/UniXNUPkg/Library/UniXNULib/Config.c'):
        pinned = subprocess.check_output([GIT, '-c', f'safe.directory={SOURCE}', '-C', str(SOURCE),
                                          'show', f'{PIN}:{name}'])
        current = (SOURCE / name).read_bytes().replace(b'\r\n', b'\n')
        if current != pinned.replace(b'\r\n', b'\n'):
            raise ValueError('Local reference differs from pinned source')
        source_hashes[name] = hashlib.sha256(current).hexdigest()
    config = (ROOT / 'config/volume-probe/unixnu.toml').read_bytes().replace(b'\r\n', b'\n')
    parsed = tomllib.loads(config.decode())
    if parsed['entry'] != [dict(id='probe-exit', title='Volume config loaded - Return to firmware',
                                type='action', action='exit')]:
        raise ValueError('Only the safe exit action is allowed in this fixture')
    stage = OUT / 'stage/EFI/UniXNU'
    stage.mkdir(parents=True)
    (stage / 'unixnu.toml').write_bytes(config)
    # FAT timestamps are set by mcopy -m using the source timestamp.
    import os
    for path in (OUT / 'stage', *(OUT / 'stage').rglob('*')):
        os.utime(path, (315532800, 315532800))
    commands = []

    def wslpath(path):
        absolute = path.resolve().as_posix()
        if not absolute.startswith('D:/Code/PortingiOS/nuwa/UniXNU-nuwa/out/volume-probe/'):
            raise ValueError('Fixture path escaped its output directory')
        return '/mnt/d/' + absolute[3:]

    def run(*args):
        command = ['wsl', '-d', 'Ubuntu-22.04', '--', 'env', 'TZ=UTC', 'MTOOLS_SKIP_CHECK=1', *args]
        result = subprocess.run(command, capture_output=True, timeout=60)
        commands.append(dict(argv=command, exit_code=result.returncode,
                             stdout=result.stdout.decode(errors='replace'), stderr=result.stderr.decode(errors='replace')))
        result.check_returncode()
        return result.stdout

    image = OUT / 'volume-probe.fat.img'
    run('mformat', '-V')
    run('mformat', '-C', '-F', '-T', '131072', '-v', 'NUWAPROBE', '-N', '50524f42', '-i', wslpath(image), '::')
    run('mcopy', '-i', wslpath(image), '-s', '-Q', '-m', wslpath(OUT / 'stage/EFI'), '::/')
    run('mdir', '-i', wslpath(image), '-/','::/')
    extracted = run('mtype', '-i', wslpath(image), '::/EFI/UniXNU/unixnu.toml')
    if extracted != config:
        raise ValueError('Configuration round trip differs')
    run('fsck.fat', '-n', wslpath(image))
    with image.open('rb') as stream:
        header = stream.read(512)
        sha = hashlib.sha256(header)
        while block := stream.read(1024 * 1024):
            sha.update(block)
    sector, = struct.unpack_from('<H', header, 11)
    sectors, = struct.unpack_from('<I', header, 32)
    fat_sectors, = struct.unpack_from('<I', header, 36)
    reserved, = struct.unpack_from('<H', header, 14)
    cluster_count = (sectors - reserved - header[16] * fat_sectors) // header[13]
    if header[510:512] != b'\x55\xaa' or sector != 512 or sectors * sector != image.stat().st_size or cluster_count < 65525:
        raise ValueError('Unexpected FAT32 geometry')
    report = dict(at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  scope='Offline FAT tool execution and byte checks only; no firmware or device execution',
                  source=dict(repository='UniXNU/UniXNU', commit=PIN, license='BSD-2-Clause-Patent',
                              normalized_source_sha256=source_hashes), commands=commands,
                  image=dict(path=str(image.relative_to(ROOT)), bytes=image.stat().st_size, sha256=sha.hexdigest(),
                             sector_bytes=sector, clusters=cluster_count, label='NUWAPROBE'),
                  config_sha256=hashlib.sha256(config).hexdigest(), config_round_trip_equal=True,
                  boot_entries='One exit action; no OS entry', kernel_included=False, adt_included=False,
                  firmware_transport_integrated=False, hardware_tested=False, device_mode_changed=False,
                  limitations=['No candidate ABL chosen mapping', 'No UEFI BlockIo/FAT runtime proof',
                               'No DarwinBoot or XNU execution'])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(image=report['image'], config_round_trip_equal=True, hardware_tested=False), indent=2))


if __name__ == '__main__':
    main()
