"""Read-only research: pinned boot pipeline, donor inventory and kernel providers.

Writes evidence only to this device repo; no source copying, image generation,
board edits, live devices, prelink emission or Git mutations.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import plistlib
import struct
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('D:/Code/PortingiOS/common/sources/UniXNU')
SHENG = Path('D:/Code/PortingiOS/common/sources/UniXNU-sheng')
DONOR = Path('D:/Code/PortingiOS/common/cache/donor-ios16')
PIN = '75bc13dd34dc4e403826793739e316a264ce00dd'
SHENG_PIN = 'a599a1a8a92093b5077543e071b72130769eb325'
OUT = ROOT / 'reports/ios16-payload-research'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git(root, *args):
    return subprocess.check_output(['git', '--no-optional-locks', '-c', f'safe.directory={root}', '-C', str(root), *args])


class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hidden = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden and data.strip():
            self.parts.append(data.strip())


def page(route):
    url = 'https://unixnu.com/zh/' + route + '/'
    name = 'zh__' + route.replace('/', '__')
    item = dict(url=url, at=datetime.now(timezone.utc).isoformat())
    try:
        request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(request, timeout=12) as response:
            raw = response.read()
            item.update(status=response.status, resolved_url=response.url)
        parser = Text()
        parser.feed(raw.decode('utf-8'))
        path = ROOT / 'out/ios16-payload-research' / (name + '.html')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        path.with_suffix('.txt').write_text('\n'.join(parser.parts), encoding='utf-8')
        item.update(source='live official page', path=path.relative_to(ROOT).as_posix(), sha256=sha(raw))
    except Exception as error:
        path = ROOT / 'out/official-site-audit' / (name + '.html')
        item.update(source='2026-10-22 cached official HTML; live fetch failed', live_error=str(error),
                    path=path.relative_to(ROOT).as_posix(), sha256=sha(path.read_bytes()))
    return item


def source(root, pin, path, patterns, license_name):
    raw = git(root, 'show', pin + ':' + path)
    lines = raw.decode('utf-8').splitlines()
    return dict(repository='UniXNU/' + ('UniXNU-sheng' if root == SHENG else 'UniXNU'),
                commit=pin, path=path, sha256=sha(raw), license=license_name,
                anchors=[dict(line=i, text=line.strip()) for i, line in enumerate(lines, 1)
                         if any(pattern in line for pattern in patterns)])


def der(data, at):
    tag, size = data[at:at + 2]
    at += 2
    if size & 128:
        count = size & 127
        if not 0 < count <= 4:
            raise ValueError('Unsupported DER length')
        size = int.from_bytes(data[at:at + count], 'big')
        at += count
    if at + size > len(data):
        raise ValueError('Truncated DER')
    return tag, data[at:at + size], at + size


def trust_payload(raw):
    tag, body, end = der(raw, 0)
    if tag != 0x30 or end != len(raw):
        raise ValueError('Not an exact DER sequence')
    fields, at = [], 0
    while at < len(body):
        kind, data, at = der(body, at)
        fields.append((kind, data))
    if len(fields) < 4 or fields[0] != (0x16, b'IM4P') or fields[3][0] != 4:
        raise ValueError('Unsupported IM4P')
    return fields[3][1]


def main():
    if OUT.exists():
        raise ValueError('Fresh research evidence directory required')
    OUT.mkdir(parents=True)
    patterns = ['payloads /', 'kernel.macho', 'PackedRAMDisk', 'RAMDisk', 'TrustCache',
                'check_native_root', 'native-ufs-root', 'sheng-pmgr', 'hdiutil', 'SHNGROOT',
                "spec['", 'BUILD, VERSION', 'iPad_Pro_HFR', 'refer/iPad', 'SIZE_256MB',
                'SIZE_2GB', 'DBRDISK1', 'native_ram_block_ready', 'native_ufs_probe_calls',
                'root-matching', 'early_security_init', "--slide", 'version !=', 'Version !=',
                '0x80000000', '0x10000000', 'XNU_NATIVE_UFS', 'XNU_NATIVE_RAM_BLOCK', 'SHENG_PMGR']
    paths = ['scripts/unixnu/payload.py', 'scripts/unixnu/kernel.py', 'scripts/unixnu/userdata.py',
             'scripts/unixnu/bootimg.py', 'scripts/unixnu/ipsw.py', 'scripts/seed-data-skip-setup.py',
             'scripts/build-original-system-trust.py', 'drivers/NativeUfs/NativeUfs.cpp',
             'drivers/NativeRamBlock/NativeRamBlock.cpp', 'drivers/NativeRamBlock/SparseDisk.h',
             'scripts/build-xnu-4k-baseline.sh',
             'drivers/DarwinBoot/DarwinBootPkg/Driver/PackedRamdisk.h',
             'drivers/DarwinBoot/DarwinBootPkg/Driver/DarwinBoot.c']
    sources = [source(BASE, PIN, path, patterns, 'SPDX BSD-2-Clause-Patent' if path.startswith('drivers/')
                      else 'BSD-2-Clause-Patent repository license; retain original notices') for path in paths]
    sources.append(source(SHENG, SHENG_PIN, 'board.toml',
                          ['tool =', 'component =', 'windows =', 'kernel_args', 'archives', 'packed_data_ramdisk'],
                          'BSD-2-Clause-Patent repository license; structure only, no board/prelink values adopted'))
    sources.extend(source(repo, pin, 'LICENSE', ['SPDX', 'Copyright'], 'BSD-2-Clause-Patent')
                   for repo, pin in ((BASE, PIN), (SHENG, SHENG_PIN)))
    sources.append(source(BASE, PIN, 'drivers/NativeUfs/LICENSE', ['BSD 2-Clause', 'Copyright'],
                          'BSD-2-Clause file; source SPDX says BSD-2-Clause-Patent, reconcile before redistribution'))
    (OUT / 'source-contracts.json').write_text(json.dumps(sources, indent=2) + '\n')
    manifests = {}
    for name in ('BuildManifest.plist', 'Restore.plist'):
        raw = (DONOR / name).read_bytes()
        manifests[name] = dict(sha256=sha(raw), data=plistlib.loads(raw))
    manifest = manifests['BuildManifest.plist']['data']
    identities = [i for i in manifest['BuildIdentities'] if i['Info']['DeviceClass'] == 'd22ap'
                  and i['Info']['RestoreBehavior'] == 'Erase']
    if len(identities) != 1 or manifest['ProductBuildVersion'] != '20H392' or manifest['ProductVersion'] != '16.7.16':
        raise ValueError('Donor identity differs')
    identity = identities[0]
    fetch = json.loads((DONOR / 'components/fetch-report.json').read_text())
    entries, modules = [], []
    for name in ('KernelCache', 'DeviceTree', 'OS', 'Cryptex1,SystemOS', 'Cryptex1,AppOS',
                 'StaticTrustCache', 'Cryptex1,SystemTrustCache'):
        info = identity['Manifest'][name]
        member = info['Info']['Path']
        path = DONOR / 'components' / Path(member).name
        previous = next(i for i in fetch['components'] if i['component'] == name)
        item = dict(component=name, member=member, path=str(path), present=path.is_file(),
                    bytes=path.stat().st_size, prior_fetch_sha256=previous['sha256'],
                    prior_fetch_report_sha256=sha((DONOR / 'components/fetch-report.json').read_bytes()),
                    file_hash_recomputed=False)
        if item['bytes'] != previous['bytes'] or previous['member'] != member:
            raise ValueError('Component metadata differs')
        if 'TrustCache' in name:
            raw = path.read_bytes()
            item.update(current_sha256=sha(raw), file_hash_recomputed=True)
            if sha(raw) != previous['sha256']:
                raise ValueError('Trust cache changed')
            data = trust_payload(raw)
            version, count = struct.unpack_from('<I16xI', data)
            if version != 2 or len(data) != 24 + count * 24:
                raise ValueError('Donor trust module does not match fixed loader v2 layout')
            hashes = [data[24 + i * 24:44 + i * 24] for i in range(count)]
            hash_types = sorted(set(data[44 + i * 24] for i in range(count)))
            if hashes != sorted(hashes) or any(not 1 <= t <= 4 for t in hash_types):
                raise ValueError('Donor trust cache sorting/hash type mismatch')
            modules.append(data)
            item.update(module_sha256=sha(data), module_bytes=len(data), version=version, entries=count,
                        hash_types=hash_types, static_layout_result='v2 size/hash-type/order checks passed')
        elif name in ('OS', 'Cryptex1,SystemOS', 'Cryptex1,AppOS'):
            with path.open('rb') as stream:
                stream.seek(-512, 2)
                item['trailer_signature'] = stream.read(4).decode('ascii', errors='replace')
            item['raw_disk_bytes'] = 'TODO: hdiutil decoded whole-disk extent, not compressed file size'
            item['apfs_volume_uuid'] = 'TODO: read actual decoded APFS metadata'
        entries.append(item)
    hypothetical = struct.pack('<3I', 2, 12, 12 + len(modules[0])) + b''.join(modules)
    donor = dict(version=manifest['ProductVersion'], build=manifest['ProductBuildVersion'],
                 product='iPhone10,3', device_class=identity['Info']['DeviceClass'],
                 chip_id=identity['ApChipID'], board_id=identity['ApBoardID'],
                 manifests={k: dict(sha256=v['sha256']) for k, v in manifests.items()}, components=entries,
                 trust_bundle_in_memory=dict(bytes=len(hypothetical), sha256=sha(hypothetical), emitted=False),
                 apple_signature_status='not assessed', board_modified=False)
    (OUT / 'donor-inventory.json').write_text(json.dumps(donor, indent=2) + '\n')
    ready = json.loads((ROOT / 'reports/darwin22-input-contracts/readiness.json').read_text())
    kernel = ROOT / ready['kernel']['path']
    raw = kernel.read_bytes()
    if sha(raw) != ready['kernel']['sha256']:
        raise ValueError('Current kernel changed')
    cursor, symbols = 32, None
    commands = struct.unpack_from('<I', raw, 16)[0]
    for _ in range(commands):
        cmd, size = struct.unpack_from('<II', raw, cursor)
        if cmd == 2:
            symbols = struct.unpack_from('<4I', raw, cursor + 8)
        cursor += size
    offset, count, strings, length = symbols
    defined = set()
    for i in range(count):
        name, typ, _, _, value = struct.unpack_from('<IBBHQ', raw, offset + i * 16)
        if typ & 0xe0 or not typ & 1 or not typ & 0x0e:
            continue
        end = raw.index(b'\0', strings + name, strings + length)
        defined.add(raw[strings + name:end].decode())
    required = ['_armcpu_registered', '_armdt_platform_configured', '_native_ufs_probe_calls',
                '_native_ram_block_ready', '_native_ram_block_volume_seed', '_sheng_pmgr_run']
    providers = dict(kernel=ready['kernel'], defined_exports={s: s in defined for s in required},
                     native_ufs_named_symbols=[s for s in sorted(defined) if 'NativeUfs' in s or 'native_ufs_' in s],
                     ram_block_named_symbols=[s for s in sorted(defined) if 'NativeRamBlock' in s or 'native_ram_block_' in s],
                     limitation='Export inventory; no driver runtime, full ABI or root-mount proof')
    (OUT / 'kernel-providers.json').write_text(json.dumps(providers, indent=2) + '\n')
    old_path = Path('D:/Code/PortingiOSWithUniXNU/.work/kernel-prelinked.json')
    old_raw = old_path.read_bytes()
    old = json.loads(old_raw)
    reference = dict(path=str(old_path), report_sha256=sha(old_raw), native_sha256=old['native_sha256'],
                     donor_sha256=old['original_sha256'], current_native_sha256=sha(raw),
                     same_native_input=old['native_sha256'] == sha(raw), values_adopted=False,
                     limitation='Existing reference report only; no prelink regeneration, relocation/ABI or execution qualification')
    (OUT / 'reference-prelink.json').write_text(json.dumps(reference, indent=2) + '\n')
    routes = ['concepts/payload', 'concepts/userdata', 'concepts/prelink', 'porting/device-tree',
              'reference/boot-configuration', 'guide/skip-setup', 'devices/sheng']
    with ThreadPoolExecutor(max_workers=4) as pool:
        pages = list(pool.map(page, routes))
    (OUT / 'official-pages.json').write_text(json.dumps(pages, indent=2) + '\n')
    print(json.dumps(dict(components=len(entries), trust_modules=[e for e in entries if 'TrustCache' in e['component']],
                         kernel_exports=providers['defined_exports'], live_pages=sum(p['source']=='live official page' for p in pages)), indent=2))


if __name__ == '__main__':
    main()
