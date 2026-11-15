#!/usr/bin/env python3
"""Bounded APFS host closure; replay immutable inactive-UFS inputs, never enable UFS.

Reuse: UniXNU/XnuPrelink f1d80d37528a33e24643583787123c652b70a268,
BSD-2-Clause-Patent; local Nuwa PMGR/c1 mechanisms (no repository LICENSE).
"""
import argparse
import copy
import importlib.util
import json
import os
import plistlib
from pathlib import Path
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
C1 = ROOT / 'out/nuwa-ufs-link-20261113-c1/run'


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    assert out.is_relative_to(ROOT / 'out') and not out.exists()
    out.mkdir(parents=True)
    B = load(ROOT / 'scripts/build-nuwa-pmgr-kernel.py', 'apfs_pmgr')
    provenance = json.loads((C1 / 'provenance.json').read_text())
    assert B.record(C1 / 'kernel.macho')['sha256'] == 'd67051dcc1c2a1767a7890e22e8d62cd2f0292e0da670661473ed74c283b933b'
    assert (C1 / 'kernel.macho').stat().st_size == 55517184
    inputs = []
    for key in ('native', 'native_map', 'prelink', 'archive', 'output', 'source', 'patch',
                'isolated_source', 'platform_object', 'provider_object', 'provider_report', 'donor',
                'ufs_late', 'ufs_archive'):
        r = provenance[key]
        assert B.record(Path(r['path'])) == r, key
        inputs.append(r)
    for r in provenance['reused_link_inputs'] + provenance['ufs_inputs']:
        assert B.record(Path(r['path'])) == r
        inputs.append(r)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
               DARWIN_TRIPLE='arm64-apple-ios17.0',
               CROSS_CLANG='/opt/unixnu-linux/llvm/bin/clang',
               CROSS_EXTRA_FLAGS='-mllvm -disable-atexit-based-global-dtor-lowering')
    env['PATH'] = '/opt/unixnu-linux/CommandLineTools/usr/bin:/opt/unixnu-linux/bin:' + env.get('PATH', '')
    commands = []

    def run(label, command, cwd=ROOT):
        command = list(map(str, command))
        log = out / (label + '.log')
        with log.open('wb') as stream:
            result = subprocess.run(command, cwd=cwd, env=env, stdout=stream, stderr=subprocess.STDOUT)
        commands.append(dict(label=label, argv=command, cwd=str(cwd), exit=result.returncode, log=str(log)))
        (out / 'commands.json').write_text(json.dumps(commands, indent=2) + '\n')
        if result.returncode:
            raise RuntimeError(f'{label}: exit {result.returncode}; {log}\n' + log.read_text(errors='replace')[-3000:])

    source = out / 'xnu-work'
    shutil.copytree(B.TREE / '.cache/xnu-work', source, symlinks=True)
    patch = ROOT / 'patches/xnu/8796-vfs-getvfs-with-vfsops.patch'
    assert B.sha(patch.read_bytes()) == '19fcb0a37a806db0a537cd059d604d7e8b1924379dea30bd0f9c9d8309311cf9'
    run('vfs-patch', ['patch', '--batch', '--forward', '-p1', '-i', patch], source)
    rec = json.loads((B.OBJ / 'bsd/DEVELOPMENT/vfs_subr.o.json').read_text().strip().rstrip(','))
    argv = [s.replace(str(B.TREE / '.cache/xnu-work'), str(source)) for s in rec['arguments']]
    argv[argv.index('-o') + 1] = str(out / 'vfs_subr.o')
    run('vfs-compile', argv, Path(rec['directory']))
    assert '_vfs_getvfs_with_vfsops\n' in (source / 'config/BSDKernel.exports').read_text()
    # Reuse XNU's generators, including the actual embedded KPI export metadata.
    config = B.OBJ / 'config'
    run('bsd-symbolset', ['sh', source / 'config/generate_symbolset_plist.sh',
                         out / 'BSDKernel.symbolset.plist',
                         config / 'System.kext/PlugIns/BSDKernel.kext/Info.plist',
                         source / 'config/BSDKernel.exports', source / 'config/BSDKernel.arm64.exports'])
    sets = ['BSDKernel', 'IOKit', 'Libkern', 'Mach', 'MACFramework', 'Unsupported', 'Private', 'Kasan', 'Kcov']
    run('combined-symbolsets', ['sh', source / 'config/generate_combined_symbolsets_plist.sh',
                               out / 'symbolsets.xml.plist'] +
        [out / 'BSDKernel.symbolset.plist' if n == 'BSDKernel' else config / (n + '.symbolset.plist') for n in sets])
    symbolsets = plistlib.loads((out / 'symbolsets.xml.plist').read_bytes())
    expected = plistlib.loads((B.OBJ / 'symbolsets.plist').read_bytes())
    bsd, = [s for s in expected['SymbolsSets'] if s['CFBundleIdentifier'] == 'com.apple.kpi.bsd']
    bsd['Symbols'].append({'SymbolName': '_vfs_getvfs_with_vfsops'})
    bsd['Symbols'].sort(key=lambda r: r.get('SymbolName', r.get('SymbolPrefix')))
    assert symbolsets == expected, 'symbolset change must be exactly the new BSD export'
    (out / 'symbolsets.plist').write_bytes(plistlib.dumps(symbolsets, fmt=plistlib.FMT_BINARY, sort_keys=False))
    donor = Path(provenance['donor']['path']).read_bytes()
    slide = -0x1000000
    cc = '/opt/unixnu-linux/CommandLineTools/usr/bin/clang'
    # Re-derive all aliases from donor geometry; no old final address is used.
    contracts = json.loads((ROOT / 'out/ufs-storage-contract-20261113-r3/contract.json').read_text())['bindings']
    groups = [('storage', contracts, 'com.apple.iokit.IOStorageFamily'),
              ('original', provenance['bindings'], 'com.apple.driver.ApplePMGR')]
    derived = {}
    for label, contract, identifier in groups:
        _, module = B.module(donor, identifier)
        bindings = {}
        for name, row in contract.items():
            seg, = [s for s in module['segments'] if s['name'] == row['segment']]
            offset = int(row.get('segment_offset', row.get('offset')), 16)
            assert 0 <= offset < seg['size']
            bindings[name] = dict(module=identifier, segment=seg['name'], offset=hex(offset),
                                  donor_va=hex(seg['va'] + offset), slide=slide,
                                  final_va=hex(seg['va'] + offset + slide))
        assert len(bindings) == (11 if label == 'storage' else 8)
        (out / (label + '-bindings.json')).write_text(json.dumps(bindings, indent=2) + '\n')
        asm = out / (label + '-bindings.S')
        asm.write_text(''.join(f'.globl {n}\n.set {n}, {r["final_va"]}\n' for n, r in sorted(bindings.items())))
        run(label + '-bindings', [cc, '-target', 'arm64-apple-ios17.0', '-c', asm, '-o', out / (label + '-bindings.o')])
        derived[label] = bindings
    # No new late transform: preserve the already reviewed dormant object bytes.
    run('ufs-archive', ['/usr/bin/llvm-ar', 'rcs', out / 'libDormantNativeUfs.a',
                        provenance['ufs_late']['path'], out / 'storage-bindings.o', provenance['observer']['path']])
    run('pmgr-archive', ['/usr/bin/llvm-ar', 'rcs', out / 'libNuwaPlatformPower.a',
                         provenance['provider_object']['path'], out / 'original-bindings.o'])
    previous = next(c for c in json.loads((C1 / 'commands.json').read_text()) if c['label'] == 'native-link')
    command = previous['argv'].copy()
    filelist = Path(command[command.index('-filelist') + 1])
    files = filelist.read_text().splitlines()
    original_vfs = str(B.OBJ / 'bsd/DEVELOPMENT/vfs_subr.o')
    assert files.count(original_vfs) == 1
    (out / 'link.filelist').write_text('\n'.join(str(out / 'vfs_subr.o') if f == original_vfs else f for f in files) + '\n')
    command[command.index('-filelist') + 1] = str(out / 'link.filelist')
    command[command.index('-o') + 1] = str(out / 'native.macho')
    replacements = {provenance['archive']['path']: str(out / 'libNuwaPlatformPower.a'),
                    provenance['ufs_archive']['path']: str(out / 'libDormantNativeUfs.a')}
    command = [f'-Wl,-map,{out}/native-link.map' if x.startswith('-Wl,-map,') else
               '-Wl,-force_load,' + replacements.get(x.removeprefix('-Wl,-force_load,'), x.removeprefix('-Wl,-force_load,'))
               if x.startswith('-Wl,-force_load,') else x for x in command]
    command = [f'-Wl,-sectcreate,__LINKINFO,__symbolsets,{out}/symbolsets.plist'
               if x.startswith('-Wl,-sectcreate,__LINKINFO,__symbolsets,') else x for x in command]
    run('native-link', command, Path(previous['cwd']))
    native = (out / 'native.macho').read_bytes()
    ns = B.names(native)
    assert '_vfs_getvfs_with_vfsops' in ns
    for bindings in derived.values():
        for name, row in bindings.items():
            assert ns[name] == int(row['final_va'], 16), name
    roots = B.tomllib.loads((ROOT / 'board.toml').read_text())['os_overrides']['ios-16.7.16-20H392']['kernel']['prelink']['roots']
    roots = roots + ['com.apple.filesystems.apfs']
    (out / 'roots.json').write_text(json.dumps(roots, indent=2) + '\n')
    # Write planner errors unchanged. No stubs, validation suppression or extra roots.
    prelinked, manifest = B.emit(native, donor, roots, slide)
    (out / 'prelink.macho').write_bytes(prelinked)
    (out / 'prelink.json').write_text(json.dumps(manifest, indent=2) + '\n')
    final = B.renderer(out, out / 'prelink.macho', out / 'native.macho', out / 'native-link.map', run)
    result = copy.deepcopy(provenance)
    result.update(status='self-checked; host only; UFS inactive; runtime ABI unqualified',
                  native=B.record(out / 'native.macho'), native_map=B.record(out / 'native-link.map'),
                  prelink=B.record(out / 'prelink.macho'), output=B.record(final),
                  archive=B.record(out / 'libNuwaPlatformPower.a'), bindings=derived['original'],
                  storage_bindings=derived['storage'], ufs_archive=B.record(out / 'libDormantNativeUfs.a'),
                  apfs_inputs=inputs, vfs_object=B.record(out / 'vfs_subr.o'), vfs_patch=B.record(patch),
                  commands=commands, vfs_bridge_added=True, roots=roots)
    for r in inputs:
        assert B.record(Path(r['path'])) == r, r['path']
    (out / 'provenance.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result['output'], indent=2))


if __name__ == '__main__':
    main()
