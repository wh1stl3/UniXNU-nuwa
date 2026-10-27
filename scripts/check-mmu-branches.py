"""Validate MMU profile pins and exact logging-only patch semantics offline."""
import copy
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
    base = json.loads((ROOT / 'config/firmware-constructor-trace-profile.json').read_text())
    profile = json.loads((ROOT / 'config/firmware-mmu-branches-profile.json').read_text())
    patch_path = 'patches/firmware-candidates/0012-mmu-constructor-branches.patch'
    patch = (ROOT / patch_path).read_bytes()
    expected = copy.deepcopy(base)
    for key in ('scope', 'source_evidence'):
        expected[key] = profile[key]
    expected['recipe']['approval'] = profile['recipe']['approval']
    expected['candidate']['patches'].append(dict(path=patch_path, root='firmware', sha256=hashlib.sha256(patch).hexdigest()))
    path = 'UefiCpuPkg/Library/ArmMmuLib/AArch64/ArmMmuLibCore.c'
    tree = Tree(ctor.MU)
    parent_patch = ROOT / base['candidate']['patches'][-1]['path']
    def apply(raw):
        tree.apply(raw.decode().replace('a/Mu_Basecore/', 'a/').replace('b/Mu_Basecore/', 'b/'))
    apply(parent_patch.read_bytes())
    before = tree.read(path)
    apply(patch)
    after = tree.read(path)
    removed = [line for line in after.splitlines(True) if '[NUWA-MMU]' in line]
    if len(removed) != 5 or ''.join(line for line in after.splitlines(True) if '[NUWA-MMU]' not in line) != before:
        raise ValueError('Patch changes more than five logging statements')
    targets = [i for i in expected['candidate']['post_patch_inputs'] if i['path'] == 'Mu_Basecore/' + path]
    if len(targets) != 1 or targets[0]['lf_sha256'] != hashlib.sha256(before.encode()).hexdigest():
        raise ValueError('Ambiguous or incorrect parent pin')
    targets[0]['lf_sha256'] = hashlib.sha256(after.encode()).hexdigest()
    if expected != profile:
        raise ValueError('Profile changes unrelated inputs or patch order')
    checked = []
    for item in profile['recipe']['inputs']:
        if item['root'] == 'unixnu':
            root = Path('D:/Code/PortingiOSLegacy/common/sources/UniXNU')
            pin, source_path = profile['recipe']['sources']['unixnu']['commit'], item['path']
        elif item['path'].startswith('Mu_Basecore/'):
            root, pin, source_path = ctor.MU, ctor.PIN, item['path'].split('/', 1)[1]
        else:
            root, pin, source_path = ctor.FW, ctor.FW_PIN, item['path']
        raw = ctor.blob(root, pin, source_path).replace(b'\r\n', b'\n')
        if hashlib.sha256(raw).hexdigest() != item['lf_sha256']:
            raise ValueError('Source pin mismatch: ' + item['path'])
        checked.append(item)
    for item in profile['candidate']['patches']:
        if hashlib.sha256((ROOT / item['path']).read_bytes()).hexdigest() != item['sha256']:
            raise ValueError('Patch pin mismatch')
    if hashlib.sha256((ROOT / 'board.toml').read_bytes().replace(b'\r\n', b'\n')).hexdigest() != profile['recipe']['board_lf_sha256']:
        raise ValueError('Board changed')
    result = dict(result='static checks passed', inputs=checked, input_count=len(checked),
                  patch_sha256=hashlib.sha256(patch).hexdigest(),
                  parent_sha256=hashlib.sha256(before.encode()).hexdigest(),
                  post_sha256=hashlib.sha256(after.encode()).hexdigest(),
                  logging_only_exact_restoration=True, markers=[line.strip() for line in removed],
                  compiled=False, device_accessed=False,
                  limitation='Logging can affect timing and shared library consumers; runtime behavior unverified')
    output = ROOT / 'reports/mmu-branches/profile-check.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('result', 'input_count', 'patch_sha256', 'post_sha256')}))


if __name__ == '__main__':
    main()
