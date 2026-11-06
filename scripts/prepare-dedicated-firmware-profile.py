"""Wire the dedicated source repository into a checked firmware profile.

No clone, image generation or device access. --write updates the profile JSON;
without it the already written profile must match the verified source mapping.
"""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def digest(data):
    return hashlib.sha256(data.replace(b'\r\n', b'\n')).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    parser.add_argument('--firmware-checkout', type=Path, help='also verify the dedicated local checkout')
    args = parser.parse_args()
    result = json.loads((ROOT/'reports/uefi-nuwa/result.json').read_text())
    assert result['complete_tree_matches'] and result['actions_enabled'] is False
    scope = runpy.run_path(str(ROOT/'scripts/provision-uefi-nuwa.py'), run_name='prepare')
    files, _ = scope['prepare']()
    for path, raw in files.items():
        assert result['changed_paths'][path]['sha256'] == hashlib.sha256(raw).hexdigest()
    recipe = json.loads((ROOT/'config/firmware-ci-inputs.json').read_text())
    candidate = json.loads((ROOT/'config/loader-candidate.json').read_text())
    recipe['sources']['firmware'] = dict(repository=result['repository'], commit=result['commit'])
    del recipe['sources']['sheng']
    recipe['inputs'] = [i for i in recipe['inputs'] if i['root'] != 'sheng']
    for item in recipe['inputs']:
        if item['root'] == 'firmware' and item['path'] in files:
            item['lf_sha256'] = digest(files[item['path']])
    for ext in ('c', 'inf'):
        path = f'Platforms/Xiaomi/nuwaPkg/Drivers/NuwaBootMemoryDxe/NuwaBootMemoryDxe.{ext}'
        recipe['inputs'].append(dict(root='firmware', path=path, lf_sha256=digest(files[path])))
    # All firmware/sheng patches are already incorporated in the new repository.
    # Keep historical manifests and patch files for exact CI15/firmware replay.
    wired = dict(kernel=candidate['kernel'],
        modules=[m.replace('shengPkg/Drivers/ShengBootMemoryDxe/ShengBootMemoryDxe.inf',
                           'nuwaPkg/Drivers/NuwaBootMemoryDxe/NuwaBootMemoryDxe.inf') for m in candidate['modules']],
        package_links={k: v for k, v in candidate['package_links'].items() if k != '.unixnu-packages/shengPkg'},
        patches=[p for p in candidate['patches'] if p['root'] == 'unixnu'],
        post_patch_inputs=candidate['post_patch_inputs'])
    assert len(wired['patches']) == 1 and len(wired['modules']) == 4 and len(wired['package_links']) == 2
    profile = dict(scope='Dedicated firmware source profile; not built or device-verified',
        source_evidence='reports/uefi-nuwa/result.json', recipe=recipe, candidate=wired)
    path = ROOT/'config/firmware-dedicated-profile.json'
    if args.write:
        path.write_text(json.dumps(profile, indent=2)+'\n', encoding='utf-8')
    else:
        assert json.loads(path.read_text()) == profile
    checks = []
    if args.firmware_checkout:
        head = subprocess.check_output(['C:/Program Files/Git/cmd/git.exe', '-C',
            str(args.firmware_checkout), 'rev-parse', 'HEAD'], text=True).strip()
        assert head == result['commit'], 'Dedicated checkout is not the pinned source'
    for item in recipe['inputs']:
        source = 'verified source mapping'
        if item['root'] == 'firmware':
            if args.firmware_checkout:
                local = args.firmware_checkout/item['path']
                if local.exists():
                    raw, source = local.read_bytes(), 'dedicated local checkout'
                else:
                    module = item['path'].split('/')[0]
                    assert module in result['submodules']
                    record = subprocess.check_output(['C:/Program Files/Git/cmd/git.exe', '-C',
                        str(args.firmware_checkout), 'ls-tree', 'HEAD', '--', module], text=True)
                    assert record.split()[1:3] == ['commit', result['submodules'][module]]
                    raw = (scope['FW']/item['path']).read_bytes()
                    source = 'read-only cache of uninitialized pinned module '+module
            else:
                raw = files.get(item['path'])
            if raw is None:
                raw = (scope['FW']/item['path']).read_bytes()
        else:
            raw = (Path('D:/Code/PortingiOSLegacy/common/sources/UniXNU')/item['path']).read_bytes()
        assert digest(raw) == item['lf_sha256'], item['path']
        checks.append(dict(root=item['root'], path=item['path'], source=source, passed=True))
    dsc = files['Platforms/Xiaomi/nuwaPkg/nuwa.dsc'].decode()
    fdf = files['Platforms/Xiaomi/nuwaPkg/nuwa.fdf'].decode()
    for module in wired['modules']:
        assert dsc.split('[Components]', 1)[1].splitlines().count('  '+module) == 1
        assert fdf.split('[FV.FvMain]', 1)[1].split('[FV.FVMAIN_COMPACT]', 1)[0].splitlines().count('  INF '+module) == 1
    metadata = dict(profile=path.relative_to(ROOT).as_posix(), firmware_commit=result['commit'],
        source_inputs=checks, module_count=len(wired['modules']), external_package_count=len(wired['package_links']),
        remaining_patch_count=len(wired['patches']), double_application_avoided=True,
        original_board_and_feed_pins_retained=True, full_build=False, device_accessed=False)
    if args.firmware_checkout:
        metadata['local_firmware_checkout'] = str(args.firmware_checkout)
    (ROOT/'reports/uefi-nuwa/profile-check.json').write_text(json.dumps(metadata, indent=2)+'\n')
    print(json.dumps(metadata, indent=2))


if __name__ == '__main__':
    main()
