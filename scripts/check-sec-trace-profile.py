"""Check the approved SEC diagnostic profile without building images."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
FIRMWARE = Path('D:/Code/PortingiOS/nuwa/uefi-nuwa')
GIT = 'C:/Program Files/Git/cmd/git.exe'


def main():
    base = json.loads((ROOT / 'config/firmware-dedicated-profile.json').read_text())
    diagnostic = json.loads((ROOT / 'config/firmware-sec-trace-profile.json').read_text())
    publish = json.loads((ROOT / 'reports/sec-trace/source-publish.json').read_text())
    expected = copy.deepcopy(base)
    expected['scope'] = diagnostic['scope']
    expected['source_evidence'] = 'reports/sec-trace/source-publish.json'
    expected['recipe']['approval'] = diagnostic['recipe']['approval']
    expected['recipe']['sources']['firmware']['commit'] = publish['commit']
    changed = 'Silicon/Silicium/SiliciumPkg/Sec/Sec.c'
    for item in expected['recipe']['inputs']:
        if item['root'] == 'firmware' and item['path'] == changed:
            item['lf_sha256'] = '6af8dd4d45476fb3b0a387b8d85913765c6d6b1bcdab99f3c6275cc9a5b1efaa'
    if expected != diagnostic or 'R-007 A' not in diagnostic['recipe']['approval']:
        raise ValueError('Diagnostic profile changes exceed approved scope')
    if subprocess.check_output([GIT, '-C', str(FIRMWARE), 'log', '-1', '--format=%H'], text=True).strip() != publish['commit']:
        raise ValueError('Wrong local firmware commit')
    if subprocess.check_output([GIT, '-C', str(FIRMWARE), 'status', '--porcelain']).strip():
        raise ValueError('Dirty diagnostic firmware checkout')
    checks = []
    for item in diagnostic['recipe']['inputs']:
        if item['root'] == 'firmware':
            path = FIRMWARE / item['path']
            kind = 'dedicated diagnostic checkout'
            if not path.is_file():
                # Local submodules are not initialized; use the same pinned
                # read-only cache as the dedicated profile checker.
                module = item['path'].split('/')[0]
                gitlink = subprocess.check_output([GIT, '-C', str(FIRMWARE), 'ls-tree', 'HEAD', '--', module], text=True)
                original = json.loads((ROOT / 'reports/uefi-nuwa/result.json').read_text())
                if gitlink.split()[1:3] != ['commit', original['submodules'][module]]:
                    raise ValueError('Unexpected uninitialized module')
                path = Path('D:/Code/PortingiOSLegacy/common/sources/mu-nuwa-firmware') / item['path']
                kind = 'read-only cache of pinned uninitialized ' + module
        else:
            path = Path('D:/Code/PortingiOSLegacy/common/sources/UniXNU') / item['path']
            kind = 'read-only pinned UniXNU cache'
        actual = hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
        if actual != item['lf_sha256']:
            raise ValueError('Input hash mismatch: ' + item['path'])
        checks.append({'root': item['root'], 'path': item['path'], 'source': kind, 'sha256': actual})
    if hashlib.sha256((ROOT / 'board.toml').read_bytes().replace(b'\r\n', b'\n')).hexdigest() != diagnostic['recipe']['board_lf_sha256']:
        raise ValueError('Board changed')
    result = {'approval': 'R-007 A', 'firmware_commit': publish['commit'], 'checks': checks,
              'only_sec_source_changed': True, 'board_feed_pins_retained': True,
              'full_local_build': False, 'device_executed': False}
    (ROOT / 'reports/sec-trace/profile-check.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'source_inputs': len(checks), 'firmware_commit': publish['commit'], 'scope': 'static profile checks passed'}))


if __name__ == '__main__':
    main()
