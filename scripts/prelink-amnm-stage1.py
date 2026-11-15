#!/usr/bin/env python3
"""Prelink the immutable stage-one native into a fresh, non-runnable output."""
import hashlib
import argparse
import json
from pathlib import Path
import sys

BASE = Path('/mnt/d/Code/PortingiOS/UniXNU')
DEVICE = Path('/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa')
SOC = Path('/mnt/d/Code/PortingiOS/nuwa/UniXNU-sm8550-common')
CACHE = BASE / 'out/ipsw/20H392/kernelcache.decompressed'
SOURCE = Path('/root/nuwa-amnm-stage1-20261111/native/build-result.json')
OUT = Path('/root/nuwa-amnm-binding-stage1-prelink-20261111')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--out', type=Path, default=OUT)
    options = parser.parse_args()
    source_record = options.source.resolve()
    out = options.out.resolve()
    record = json.loads(source_record.read_text())
    native = Path(record['native']['path'])
    assert hashlib.sha256(native.read_bytes()).hexdigest() == record['native']['sha256']
    assert record['stages']['kernel']['exit'] == 0
    out.mkdir(exist_ok=False)
    config_file = out / 'build-input.toml'
    config_file.write_text('[build]\n')
    sys.path.insert(0, str(BASE / 'scripts'))
    from unixnu import cli, config, kernel
    args = cli.parser().parse_args(['defconfig', 'nuwa_amnm_defconfig', '-D', str(DEVICE),
        '--out', str(out), '--config', str(config_file), '--local-module', f'soc:sm8550={SOC}',
        '--kernelcache', str(CACHE), '-j', '8'])
    ctx = config.Context(args)
    ctx.tree = Path(record['work']) / 'tree'
    ctx.work = out / 'work'
    ctx.logs = out / 'logs'
    ctx.logs.mkdir()
    result = kernel.prelink(ctx)
    raw = result.read_bytes()
    report = {'stage': 'self-checked; uninstrumented prelink; not device approved', 'cwd': str(Path.cwd()),
              'argv': sys.argv, 'source_record': str(source_record), 'native': record['native'],
              'prelink': {'path': str(result), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()},
              'exit': 0}
    (out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    main()
