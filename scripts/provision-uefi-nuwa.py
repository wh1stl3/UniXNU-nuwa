"""Create the dedicated firmware fork from pinned sources, without images.

Cloud Git objects only: no upstream checkout copies or read-only tree writes.
Actions are disabled before any branch creation or source commit. The upstream
main ref is retained; a new codex branch starts at our tested baseline.
"""
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

from virtual_patch import Tree

ROOT = Path(__file__).resolve().parents[1]
FW = Path('D:/Code/PortingiOSLegacy/common/sources/mu-nuwa-firmware')
SHENG = Path('D:/Code/PortingiOSLegacy/common/sources/uefi-sheng')
PARENT = 'Project-Silicium/Mu-Silicium'
BASE = '6c6755012728c9f7de748228758bad94d1e9a660'
REPO = 'wh1stl3/uefi-nuwa'
BRANCH = 'codex/nuwa-bringup'
OUT = ROOT / 'reports/uefi-nuwa'


def api(path, method='GET', body=None):
    command = ['C:/Program Files/GitHub CLI/gh.exe', 'api', path]
    if method != 'GET':
        command += ['--method', method, '--input', '-']
    output = subprocess.check_output(command, input=json.dumps(body).encode() if body is not None else None,
        env={**os.environ, 'GODEBUG': 'http2client=0'})
    return json.loads(output) if output.strip() else None


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def git_blob(raw):
    return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()


def save(name, data):
    (OUT/name).write_text(json.dumps(data, indent=2)+'\n', encoding='utf-8')


def prepare():
    config = json.loads((ROOT/'config/loader-candidate.json').read_text())
    assert config['firmware_commit'] == BASE
    fw, sheng = Tree(FW), Tree(SHENG)
    patches = []
    for patch in config['patches']:
        if patch['root'] == 'unixnu':
            continue
        raw = (ROOT/patch['path']).read_bytes()
        assert sha(raw) == patch['sha256']
        {'firmware': fw, 'sheng': sheng}[patch['root']].apply(raw.decode())
        patches.append(patch)
    files = {path: text.encode() for path, text in fw.files.items()}
    for ext in ('c', 'inf'):
        old = f'Platforms/Xiaomi/shengPkg/Drivers/ShengBootMemoryDxe/ShengBootMemoryDxe.{ext}'
        text = sheng.read(old)
        if ext == 'inf':
            text = '# SPDX-License-Identifier: BSD-2-Clause\n'+text.replace('ShengBootMemoryDxe', 'NuwaBootMemoryDxe')
        else:
            text = '// SPDX-License-Identifier: BSD-2-Clause\n'+text.replace('ShengBootMemoryDxeEntry', 'NuwaBootMemoryDxeEntry')
        files[f'Platforms/Xiaomi/nuwaPkg/Drivers/NuwaBootMemoryDxe/NuwaBootMemoryDxe.{ext}'] = text.encode()
    for ext in ('dsc', 'fdf'):
        path = f'Platforms/Xiaomi/nuwaPkg/nuwa.{ext}'
        old = 'shengPkg/Drivers/ShengBootMemoryDxe/ShengBootMemoryDxe.inf'
        assert files[path].decode().count(old) == 1
        files[path] = files[path].decode().replace(old,
            'nuwaPkg/Drivers/NuwaBootMemoryDxe/NuwaBootMemoryDxe.inf').encode()
    driver = files['Platforms/Xiaomi/nuwaPkg/Drivers/NuwaBootMemoryDxe/NuwaBootMemoryDxe.c'].decode()
    assert all(s not in driver for s in ('AddMemory (', 'AddMemorySpace', 'gDS->'))
    assert all(s in driver for s in ('mMedia.ReadOnly         = TRUE', 'return EFI_WRITE_PROTECTED;',
                                     'GET_GUID_HOB_DATA_SIZE (Hob) < sizeof (UINT64)'))
    files['Platforms/Xiaomi/nuwaPkg/Drivers/NuwaBootMemoryDxe/ORIGIN.md'] = (
        '# NuwaBootMemoryDxe provenance\n\n'
        'Source: UniXNU/uefi-sheng@329b473df1e53a3bfa64b2b39b79670c4c02279b, '
        'Platforms/Xiaomi/shengPkg/Drivers/ShengBootMemoryDxe/.\n\n'
        'The [pinned README](https://github.com/UniXNU/uefi-sheng/blob/'
        '329b473df1e53a3bfa64b2b39b79670c4c02279b/README.md#license) declares '
        'BSD-2-Clause for code outside the GPL directories, including these files. '
        'The upstream files contain no file-level copyright notice.\n\n'
        'Applied the device repository 0003-initrd-publisher-only.patch first: '
        'retain read-only initrd BlockIo, remove DRAM discovery/GCD extension. '
        'Then rename the INF base/source/entry to NuwaBootMemoryDxe; retain the '
        'existing module GUID and protocol behavior. Source attribution comments '
        'and inherited SHENGMEM diagnostic strings remain. Runtime mapping and '
        'reservation lifetime on nuwa are unverified.\n').encode()
    files['docs/nuwa-unixnu.md'] = (
        '# UniXNU nuwa firmware source\n\n'
        f'Tested source baseline: {PARENT}@{BASE}. The inherited main branch is '
        f'preserved; {BRANCH} is the device development branch.\n\n'
        'Device integration lives at https://github.com/wh1stl3/UniXNU-nuwa. '
        'This fork owns the BootShim size correction, nuwa DSC/FDF/package wiring, '
        'SEC x0/HOB handoff, and the read-only NuwaBootMemoryDxe initrd publisher. '
        'UniXNUPkg and DarwinBootPkg remain external packages, staged under '
        '.unixnu-packages by the device build driver. No full UniXNU tree is vendored.\n\n'
        'Source migration only: the dedicated fork has not been built or tested '
        'on hardware. Historical CI39764322744 used equivalent source patches '
        'before the publisher rename; v4 boot acceptance/black screen did not '
        'prove SEC/DXE/BDS execution. Keep memory/config maps and all submodule '
        'pins at the tested baseline. Do not import sheng DRAM policy.\n\n'
        'Inherited Actions are disabled to prevent image generation during source '
        'provisioning. Firmware builds remain explicitly dispatched from the '
        'device repository, subject to its AGENTS.md and approved scope.\n').encode()
    return files, patches


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT/'result.json').exists():
        raise SystemExit('Already provisioned: inspect result.json; do not recreate or rewrite refs')
    files, patches = prepare()
    tree = api(f'repos/{PARENT}/git/trees/{BASE}?recursive=1')
    assert not tree['truncated']
    original = {e['path']: e for e in tree['tree'] if e['type'] != 'tree'}
    # Every modified inherited source must match the pinned upstream blob before
    # publishing. CRLF normalization was already explicit in the build recipe.
    for path in files:
        if path not in original:
            continue
        raw = (FW/path).read_bytes()
        assert original[path]['sha'] in (git_blob(raw), git_blob(raw.replace(b'\r\n', b'\n'))), path
    preflight = dict(parent=PARENT, base=BASE, repository=REPO, branch=BRANCH,
        patches=patches, files={p: dict(sha256=sha(raw), git_blob=git_blob(raw), bytes=len(raw))
                                for p, raw in files.items()})
    save('preflight.json', preflight)
    # This account already has uefi-enuma in the same fork network. GitHub
    # returned that repository instead of creating a second fork. A dedicated
    # independent repository is imported by the source-only cloud workflow;
    # it preserves the original commits without modifying uefi-enuma.
    info = api(f'repos/{REPO}')
    ref = api(f'repos/{REPO}/git/ref/heads/main')
    assert info['full_name'] == REPO and info['private'] is False
    api(f'repos/{REPO}/actions/permissions', 'PUT', dict(enabled=False))
    assert not api(f'repos/{REPO}/actions/permissions')['enabled']
    saved_main = ref['object']['sha']
    assert api(f'repos/{REPO}/git/ref/heads/{BRANCH}')['object']['sha'] == BASE
    entries = []
    for path, raw in files.items():
        created = api(f'repos/{REPO}/git/blobs', 'POST', dict(encoding='base64', content=base64.b64encode(raw).decode()))
        assert created['sha'] == git_blob(raw)
        entries.append(dict(path=path, mode='100644', type='blob', sha=created['sha']))
    base_commit = api(f'repos/{REPO}/git/commits/{BASE}')
    new_tree = api(f'repos/{REPO}/git/trees', 'POST', dict(base_tree=base_commit['tree']['sha'], tree=entries))
    commit = api(f'repos/{REPO}/git/commits', 'POST', dict(tree=new_tree['sha'], parents=[BASE],
        message='[unixnu-nuwa][firmware] Own the pinned nuwa UniXNU firmware integration\n\n'
        '[Change] Apply reviewed shim, loader wiring and SEC HOB changes; import the read-only initrd publisher.\n'
        '[Evidence] Device patch hashes and upstream blobs checked; memory maps and module GUID retained.\n'
        '[Risk] Source migration only; no firmware build, boot image or hardware execution.'))
    save('created-commit.json', dict(sha=commit['sha'], tree=new_tree['sha'], parent=BASE, inherited_main=saved_main))
    assert api(f'repos/{REPO}/git/ref/heads/{BRANCH}')['object']['sha'] == BASE
    api(f'repos/{REPO}/git/refs/heads/{BRANCH}', 'PATCH', dict(sha=commit['sha'], force=False))
    api(f'repos/{REPO}', 'PATCH', dict(default_branch=BRANCH,
        description='Xiaomi 13 Pro (nuwa) UniXNU firmware source; hardware bring-up unverified'))
    actual = api(f'repos/{REPO}/git/trees/{commit["sha"]}?recursive=1')
    assert not actual['truncated']
    current = {e['path']: e for e in actual['tree'] if e['type'] != 'tree'}
    expected = {p: (e['mode'], e['type'], e['sha']) for p, e in original.items()}
    expected.update({p: ('100644', 'blob', git_blob(raw)) for p, raw in files.items()})
    assert {p: (e['mode'], e['type'], e['sha']) for p, e in current.items()} == expected
    assert api(f'repos/{REPO}/git/ref/heads/main')['object']['sha'] == saved_main
    assert not api(f'repos/{REPO}/actions/permissions')['enabled']
    protected = ('Resources/Configs/nuwa.toml',
        'Platforms/Xiaomi/nuwaPkg/Library/MemoryMapLib/MemoryMapLib.c',
        'Platforms/Xiaomi/nuwaPkg/Library/ConfigurationMapLib/ConfigurationMapLib.c', '.gitmodules')
    assert all(original[p]['sha'] == current[p]['sha'] for p in protected)
    result = dict(repository=REPO, url='https://github.com/'+REPO, parent=PARENT,
        baseline=BASE, branch=BRANCH, commit=commit['sha'], inherited_main=saved_main,
        complete_tree_matches=True, source_entries=len(current), actions_enabled=False,
        protected_blobs={p: current[p]['sha'] for p in protected},
        changed_paths=preflight['files'], submodules={p: e['sha'] for p, e in current.items() if e['mode']=='160000'},
        firmware_generated=False, device_accessed=False, observed_at=datetime.now(timezone.utc).isoformat())
    save('result.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
