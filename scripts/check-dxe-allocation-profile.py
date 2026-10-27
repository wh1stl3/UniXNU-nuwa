"""Validate the R-010 profile against its reviewed R-009 base and pinned sources."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
MU = Path('D:/Code/PortingiOSLegacy/common/sources/mu-nuwa-firmware/Mu_Basecore')

def load(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))

def main():
    base = load('config/firmware-pil-no-auto-profile.json')
    profile = load('config/firmware-dxe-allocation-profile.json')
    preview = load('reports/dxe-allocation-audit/preview.json')
    expected = copy.deepcopy(base)
    for key in ('scope', 'source_evidence'):
        expected[key] = profile[key]
    expected['recipe']['approval'] = profile['recipe']['approval']
    raw_inputs = []
    for item in preview['inputs']:
        blob = subprocess.check_output(['git', '--no-optional-locks', '-C', str(MU),
                                       'show', preview['mu_commit'] + ':' + item['path']])
        path = 'Mu_Basecore/' + item['path']
        if hashlib.sha256(blob.replace(b'\r\n', b'\n')).hexdigest() != item['lf_sha256']:
            raise ValueError('Mu source object mismatch')
        expected['recipe']['inputs'].append(dict(root='firmware', path=path, lf_sha256=item['lf_sha256']))
        expected['candidate']['post_patch_inputs'].append(dict(root='firmware', path=path,
                                                              lf_sha256=item['proposed_lf_sha256']))
        raw_inputs.append(dict(path=path, raw_sha256=hashlib.sha256(blob).hexdigest()))
    expected['candidate']['patches'].append(dict(path=preview['patch'], root='firmware',
        sha256=preview['patch_sha256'], preserve_line_endings=True, raw_inputs=raw_inputs))
    if expected != profile or 'R-010 A' not in profile['recipe']['approval']:
        raise ValueError('Profile exceeds reviewed two-file scope')
    checked = []
    for item in profile['recipe']['inputs']:
        if item['root'] == 'unixnu':
            path = Path('D:/Code/PortingiOSLegacy/common/sources/UniXNU') / item['path']
        else:
            path = Path('D:/Code/PortingiOS/nuwa/uefi-nuwa') / item['path']
            if not path.is_file():
                path = Path('D:/Code/PortingiOSLegacy/common/sources/mu-nuwa-firmware') / item['path']
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
    result = dict(result='static profile checks passed', inputs=checked, raw_inputs=raw_inputs,
                  apply_check_argv=command, apply_check_exit_code=0,
                  same_firmware_and_unixnu_as_r009=profile['recipe']['sources']==base['recipe']['sources'],
                  board_feed_pins_retained=True, compiled=False, device_executed=False)
    (ROOT/'reports/dxe-allocation-audit/profile-check.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(result=result['result'], inputs=len(checked))))

if __name__ == '__main__':
    main()
