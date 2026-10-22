"""Retain bounded diagnostics and hashes; leave large CI logs under ignored out/."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('run_id', type=int)
args = parser.parse_args()
artifact = ROOT / f'out/kernel-ci/{args.run_id}/nuwa-8796-source-{args.run_id}'
report = ROOT / f'reports/kernel-ci/{args.run_id}'
report.mkdir(parents=True, exist_ok=True)
log = artifact / 'nuwa-host/kernel-console.log'
raw = log.read_bytes()
lines = raw.decode('utf-8', errors='replace').split('\n')
if lines[-1] == '':
    lines.pop()
lines = [line.removesuffix('\r') for line in lines]
diagnostics = [i for i, line in enumerate(lines)
               if re.search(r':\d+:\d+: (?:fatal )?error:', line)
               or '*** No rule to make target' in line]
selected = set()
for index in diagnostics:
    selected.update(range(max(0, index - 4), min(len(lines), index + 10)))
excerpt = '\n'.join(f'{i+1}: {lines[i].rstrip()}' for i in sorted(selected)) + '\n'
(report / 'diagnostics.txt').write_text(excerpt, encoding='utf-8')
for source, destination in ((artifact / 'nuwa-host/toolchain.log', report / 'toolchain.log'),
                            (artifact / 'nuwa-8796-source/reports/build.json', report / 'build.json')):
    shutil.copyfile(source, destination)
build = json.loads((report / 'build.json').read_text())
summary = {'run_id': args.run_id, 'command': f'gh run download {args.run_id} --repo wh1stl3/UniXNU --dir out/kernel-ci/{args.run_id}',
           'console_path': str(log.relative_to(ROOT)), 'console_bytes': len(raw),
           'console_sha256': hashlib.sha256(raw).hexdigest(), 'console_lines': len(lines),
           'excerpt_trailing_whitespace_trimmed': True,
           'diagnostics': [{'original_line': i+1, 'text': lines[i]} for i in diagnostics],
           'iorpc_header_unchanged': build.get('iorpc_header_unchanged'),
           'generated_kernel_content_files': len(build.get('iig_kernel_content_references', [])),
           'object_count_all_builds': build.get('object_count'),
           'kernel_built': build['kernel_built'], 'device_verified': False,
           'uio_alignment_errors_observed': 'size of array element of type' in '\n'.join(lines)}
(report / 'failure-analysis.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
print(json.dumps(summary, indent=2))
