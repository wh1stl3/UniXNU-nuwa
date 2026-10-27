"""Check pinned single-variable HOB cache handoff inputs and the complete diagnostic patch chain."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from virtual_patch import Tree


def main():
    spec = importlib.util.spec_from_file_location('ctor', ROOT / 'scripts/prepare-constructor-trace.py')
    ctor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ctor)
    profile = json.loads((ROOT/"config/firmware-hob-cache-handoff-profile.json").read_text())
    trees = {key: Tree(ROOT / 'out/nonexistent-source') for key in ('firmware', 'unixnu')}
    for item in profile['recipe']['inputs']:
        if item['root'] == 'unixnu':
            source = Path('D:/Code/PortingiOSLegacy/common/sources/UniXNU')
            pin, path = profile['recipe']['sources']['unixnu']['commit'], item['path']
        elif item['path'].startswith('Mu_Basecore/'):
            source, pin, path = ctor.MU, ctor.PIN, item['path'].split('/', 1)[1]
        else:
            source, pin, path = ctor.FW, profile['recipe']['sources']['firmware']['commit'], item['path']
        raw = ctor.blob(source, pin, path).replace(b'\r\n', b'\n')
        if hashlib.sha256(raw).hexdigest() != item['lf_sha256']:
            raise ValueError('Source pin mismatch: ' + item['path'])
        trees[item['root']].files[item['path']] = raw.decode()
    for patch in profile['candidate']['patches']:
        raw = (ROOT / patch['path']).read_bytes()
        if hashlib.sha256(raw).hexdigest() != patch['sha256']:
            raise ValueError('Patch hash mismatch')
        trees[patch['root']].apply(raw.decode().replace('\r\n', '\n'))
    for item in profile['candidate']['post_patch_inputs']:
        if hashlib.sha256(trees[item['root']].read(item['path']).encode()).hexdigest() != item['lf_sha256']:
            raise ValueError('Post patch mismatch: ' + item['path'])
    report = dict(inputs_checked=len(profile['recipe']['inputs']), patches_checked=len(profile['candidate']['patches']), post_patch_checked=len(profile['candidate']['post_patch_inputs']), scope='Static complete patch-chain validation; not device execution')
    (ROOT/'reports/hob-cache-handoff/profile-check.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report))

if __name__ == '__main__':
    main()
