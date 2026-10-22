"""Validate the R-011 profile against its R-010 base and the approved factory row."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
MU = Path('D:/Code/PortingiOS/common/sources/mu-nuwa-firmware/Mu_Basecore')

def load(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))

def main():
    base = load('config/firmware-dxe-allocation-profile.json')
    profile = load('config/firmware-factory-heap-profile.json')
    proposal = load('reports/dxe-allocation-audit/factory-heap-proposal.json')
    publish = load('reports/factory-heap/source-publish.json')
    preview = load('reports/dxe-allocation-audit/preview.json')
    expected = copy.deepcopy(base)
    for key in ('scope', 'source_evidence'):
        expected[key] = profile[key]
    expected['recipe']['approval'] = profile['recipe']['approval']
    expected['recipe']['sources']['firmware']['commit'] = publish['commit']
    for item in expected['recipe']['inputs']:
        if item['root'] == 'firmware' and item['path'] == proposal['source']['path']:
            item['lf_sha256'] = proposal['source']['proposed_lf_sha256']
    if expected != profile or 'R-011 A' not in profile['recipe']['approval']:
        raise ValueError('Profile exceeds approved one-row factory Heap change')
    firmware = Path('D:/Code/uefi-nuwa')
    if subprocess.check_output(['git', '--no-optional-locks', '-C', str(firmware), 'log', '-1', '--format=%H'],text=True).strip() != publish['commit']:
        raise ValueError('Wrong firmware source commit')
    if subprocess.check_output(['git', '--no-optional-locks', '-C', str(firmware), 'status', '--porcelain']).strip():
        raise ValueError('Firmware source tree dirty')
    raw_inputs = profile['candidate']['patches'][-1]['raw_inputs']
    checked = []
    for item in profile['recipe']['inputs']:
        if item['root'] == 'unixnu':
            path = Path('D:/Code/PortingiOS/common/sources/UniXNU') / item['path']
        else:
            path = Path('D:/Code/uefi-nuwa') / item['path']
            if not path.is_file():
                path = Path('D:/Code/PortingiOS/common/sources/mu-nuwa-firmware') / item['path']
        actual = hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
        if actual != item['lf_sha256']:
            raise ValueError('Source input changed: ' + item['path'])
        checked.append(dict(**item, actual=actual))
    patch = ROOT / preview['patch']
    if hashlib.sha256(patch.read_bytes()).hexdigest() != preview['patch_sha256']:
        raise ValueError('Patch bytes changed')
    command = ['git', '--no-optional-locks', '-C', str(MU), 'apply', '--check', '-p2', str(patch)]
    subprocess.run(command, check=True)
    if hashlib.sha256((ROOT/'board.toml').read_bytes().replace(b'\r\n',b'\n')).hexdigest() != profile['recipe']['board_lf_sha256']:
        raise ValueError('Board changed')
    feed = Path('D:/Code/PortingiOS/common/sources/UniXNU/feeds.toml')
    if hashlib.sha256(feed.read_bytes().replace(b'\r\n', b'\n')).hexdigest() != profile['recipe']['feed_lf_sha256']:
        raise ValueError('Feed changed')
    result = dict(result='static profile checks passed', inputs=checked, raw_inputs=raw_inputs,
                  apply_check_argv=command, apply_check_exit_code=0,
                  only_approved_factory_heap_row_changed=True, firmware_commit=publish['commit'],
                  board_feed_pins_retained=True, compiled=False, device_executed=False)
    (ROOT/'reports/factory-heap/profile-check.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(result=result['result'], inputs=len(checked))))

if __name__ == '__main__':
    main()
