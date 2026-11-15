#!/usr/bin/env python3
"""Re-prelink the recorded nuwa native with the selected donor pthread root."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tomllib

sys.dont_write_bytecode = True
BASE = Path('/mnt/d/Code/PortingiOS/UniXNU')
DEVICE = Path(__file__).resolve().parents[1]
SOC = DEVICE.parent / 'UniXNU-sm8550-common'
OLD = Path('/root/nuwa-pmap-ret-native-20261111/build-result.json')
NAME = 'com.apple.kec.pthread'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    out = args.out.resolve()
    if not out.is_relative_to(DEVICE / 'out') or out.exists():
        raise ValueError('output must be a fresh directory in device out/')
    rec = json.loads(OLD.read_text())
    assert rec['base_revision'] == subprocess.check_output(['git', '-C', str(BASE), 'rev-parse', 'HEAD'], text=True).strip()
    for key in ('native', 'link_map', 'config', 'kernelcache', 'pristine_prelink'):
        assert digest(Path(rec[key]['path'])) == rec[key]['sha256'], key
    # Reconstruct the original board: only the observer archive was added at
    # native build time; comments are irrelevant to TOML semantics.
    original = tomllib.loads(subprocess.check_output(
        ['git', '-C', str(DEVICE), 'show', rec['device_revision'] + ':board.toml'], text=True))
    current = tomllib.loads((DEVICE / 'board.toml').read_text(encoding='utf-8'))
    original['kernel']['archives'].append('build-nuwa-pmap-ret-observer.py')
    roots = current['os_overrides']['ios-16.7.16-20H392']['kernel']['prelink']['roots']
    assert roots.count(NAME) == 1
    roots.remove(NAME)
    assert original == current, 'board differs from recorded native build beyond pthread root'
    assert subprocess.check_output(['git', '-C', str(DEVICE), 'show',
                                    rec['device_revision'] + ':configs/nuwa_defconfig']) == (DEVICE / 'configs/nuwa_defconfig').read_bytes(), 'defconfig changed since native build'
    source_inputs = Path(rec['work']) / 'xnu-inputs.json'
    source = json.loads(source_inputs.read_text())
    assert source['commit'] == '1b191cb58250d0705d8a51287127505aa4bc0789'
    assert subprocess.check_output(['git', '-C', source['source'], 'rev-parse', 'HEAD'], text=True).strip() == source['commit']
    for patch in source['patches']:
        assert digest(Path(patch['path'])) == patch['sha256'], patch['path']
    for device_path, tree_path in [('package/diagnostics/pmap-ret-observer.S', 'kits/nuwa/diagnostics/pmap-ret-observer.S'),
                                   ('scripts/build-nuwa-pmap-ret-observer.py', 'scripts/build-nuwa-pmap-ret-observer.py')]:
        assert digest(DEVICE / device_path) == digest(Path(rec['work']) / 'tree' / tree_path), device_path
    effective = {}
    for line in Path(rec['config']['path']).read_text().splitlines():
        if line.startswith('CONFIG_') and '=' in line:
            key, value = line.split('=', 1)
            effective[key] = value
    assert effective['CONFIG_XNU_SOURCE_PTHREAD'] == 'n'
    assert effective['CONFIG_XNU_CRYPTO_BOOTSTRAP'] == '"prelinked"'
    out.mkdir(parents=True)
    (out / 'build-input.toml').write_text('[build]\n')
    sys.path.insert(0, str(BASE / 'scripts'))
    from unixnu import cli, config, kernel
    cli_args = cli.parser().parse_args(['defconfig', 'nuwa_pmap_ret_defconfig', '-D', str(DEVICE),
        '--out', str(out), '--config', str(out / 'build-input.toml'),
        '--local-module', f'soc:sm8550={SOC}', '--kernelcache', rec['kernelcache']['path'], '-j', '8'])
    ctx = config.Context(cli_args)
    ctx.tree = Path(rec['work']) / 'tree'
    ctx.work = out / 'work'
    ctx.logs = out / 'logs'
    ctx.logs.mkdir()
    result = kernel.prelink(ctx)
    manifest = json.loads(result.with_suffix('.json').read_text())
    binding_map = out / 'prelink-bindings.json'
    binding_map.write_text(json.dumps({'native_sha256': manifest['native_sha256'],
        'donor_sha256': manifest['original_sha256'], 'candidate_sha256': manifest['candidate_sha256'],
        'bindings': manifest['bindings']}, indent=2) + '\n')
    report = {'status': 'self-checked; not device approved', 'cwd': str(Path.cwd()),
              'argv': sys.argv, 'source_record': str(OLD), 'native': rec['native'],
              'native_map': rec['link_map'], 'old_config': rec['config'],
              'kernelcache': rec['kernelcache'], 'board_sha256': digest(DEVICE / 'board.toml'),
              'source_inputs_sha256': digest(source_inputs), 'patch_count': len(source['patches']),
              'output': {'path': str(result), 'bytes': result.stat().st_size, 'sha256': digest(result)},
              'kernel_manifest_sha256': digest(result.with_suffix('.json')),
              'binding_map_sha256': digest(binding_map),
              'exit': 0}
    map_path = result.with_suffix('.map.json')
    if map_path.exists():
        report['prelink_map_sha256'] = digest(map_path)
    (out / 'provenance.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
