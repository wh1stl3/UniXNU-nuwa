"""Validate complete new firmware inputs and module pins without source writes."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
from virtual_patch import Tree

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('D:/Code/UniXNU-integration')


def main():
    p = json.loads((ROOT / 'config/firmware-upstream-merged-profile.json').read_text())
    spec = importlib.util.spec_from_file_location('ctor', ROOT / 'scripts/prepare-constructor-trace.py')
    ctor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ctor)
    sha = lambda data: hashlib.sha256(data).hexdigest()
    git = lambda path: subprocess.check_output(['git', '-C', str(path), 'rev-parse', 'HEAD']).decode().strip()
    assert git(BASE) == p['recipe']['sources']['unixnu']['commit']
    for relative, expected in p['recipe']['unixnu_submodules'].items():
        assert git(BASE / relative) == expected, relative
    assert sha((ROOT / 'board.toml').read_bytes().replace(b'\r\n', b'\n')) == p['recipe']['board_lf_sha256']
    trees = {key: Tree(ROOT / 'out/nonexistent-source') for key in ('firmware', 'unixnu')}
    for item in p['recipe']['inputs']:
        if item['root'] == 'unixnu':
            raw = (BASE / item['path']).read_bytes()
        elif item['path'].startswith('Mu_Basecore/'):
            raw = ctor.blob(ctor.MU, ctor.PIN, item['path'].split('/', 1)[1])
        else:
            raw = ctor.blob(ctor.FW, p['recipe']['sources']['firmware']['commit'], item['path'])
        raw = raw.replace(b'\r\n', b'\n')
        assert sha(raw) == item['lf_sha256'], item['path']
        trees[item['root']].files[item['path']] = raw.decode()
    for patch in p['candidate']['patches']:
        raw = (ROOT / patch['path']).read_bytes()
        assert sha(raw) == patch['sha256'], patch['path']
        trees[patch['root']].apply(raw.decode().replace('\r\n', '\n'))
    for item in p['candidate']['post_patch_inputs']:
        assert sha(trees[item['root']].read(item['path']).encode()) == item['lf_sha256'], item['path']
    old = json.loads((ROOT / 'config/firmware-hob-cache-handoff-profile.json').read_text())
    assert old['candidate']['patches'] == p['candidate']['patches']
    assert [i for i in old['candidate']['post_patch_inputs'] if i['root'] == 'firmware'] == [
        i for i in p['candidate']['post_patch_inputs'] if i['root'] == 'firmware']
    result = dict(scope='Static complete firmware patch chain, no EFI/device execution',
                  module_count=len(p['recipe']['unixnu_submodules']), inputs=len(p['recipe']['inputs']),
                  patches=len(p['candidate']['patches']), post_patch=len(p['candidate']['post_patch_inputs']),
                  heap_and_hob_protection_patch_chain_unchanged=True,
                  board_unchanged=True, device_accessed=False)
    target = ROOT / 'reports/upstream-integration/2026-10-24/firmware-profile-check.json'
    target.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
