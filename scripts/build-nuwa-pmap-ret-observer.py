#!/usr/bin/env python3
"""Build only the explicitly enabled, unbound normal-RET diagnostic archive."""
import argparse
import os
from pathlib import Path
import re
import subprocess


def enabled(config):
    # Same last-assignment semantics as unixnu.config.parse_config, but only
    # this switch is consumed; unrelated options are not interpreted here.
    value = False
    for line in config.read_text().splitlines():
        line = line.strip()
        if re.fullmatch(r'#\s*CONFIG_XNU_NUWA_PMAP_RET_OBSERVER is not set', line):
            value = False
        elif line.startswith('CONFIG_XNU_NUWA_PMAP_RET_OBSERVER='):
            raw = line.split('=', 1)[1]
            if raw not in ('y', 'n'):
                raise ValueError('CONFIG_XNU_NUWA_PMAP_RET_OBSERVER must be y or n')
            value = raw == 'y'
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tree', type=Path, default=Path.cwd())
    parser.add_argument('--config', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--clang')
    parser.add_argument('--libtool')
    args = parser.parse_args()
    tree = args.tree.resolve()
    config = args.config or tree.parent / '.config'
    if not enabled(config):
        print('nuwa pmap RET observer disabled; no outputs touched')
        return
    source = tree / 'kits/nuwa/diagnostics/pmap-ret-observer.S'
    if not source.is_file():
        device = os.environ.get('UNIXNU_DEVICE')
        if not device:
            raise FileNotFoundError(f'{source}: missing; UNIXNU_DEVICE not provided')
        source = Path(device) / 'package/diagnostics/pmap-ret-observer.S'
    if not source.is_file():
        raise FileNotFoundError(source)
    toolchain = Path(os.environ.get('UNIXNU_TOOLCHAIN', '/opt/unixnu-linux'))
    clang = args.clang or os.environ.get('CROSS_CLANG') or str(toolchain / 'llvm/bin/clang')
    libtool = args.libtool or str(Path(os.environ.get(
        'CLT_PREFIX', str(toolchain / 'CommandLineTools/usr'))) / 'bin/libtool')
    out = args.out or tree / 'build/nuwa-pmap-ret-observer'
    out.mkdir(parents=True, exist_ok=True)
    obj = out / 'pmap-ret-observer.o'
    archive = out / 'libNuwaPmapRetObserver.a'
    for command in (
        [clang, '-target', 'arm64-apple-ios16.0', '-ffreestanding', '-fno-builtin',
         '-fno-stack-protector', '-Werror', '-c', str(source), '-o', str(obj)],
        [libtool, '-static', '-o', str(archive), str(obj)],
    ):
        print('+ ' + ' '.join(command), flush=True)
        subprocess.run(command, check=True)
    print(f'UNBOUND component only (not boot-approved): {archive}')


if __name__ == '__main__':
    main()
