"""Run the mandatory entry diagnostics and Image4 launch checks serially.

All output names are derived from the explicitly selected fresh build report;
historical PROBE17/18 reports are never selected as output destinations.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build', type=Path, required=True)
    p.add_argument('--adt', type=Path, required=True)
    p.add_argument('--nonce', type=Path, required=True)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--work', type=Path, required=True)
    a = p.parse_args()
    build = a.build.resolve()
    report = json.loads(build.read_text())
    work = a.work.resolve()
    if (not build.is_relative_to(ROOT / 'reports') or report.get('probe_revision') not in (27,28)
            or not work.is_relative_to(ROOT / 'out') or work.exists()):
        raise ValueError('Explicit revision-27 build and fresh out/ work directory required')
    work.mkdir(parents=True)
    old = 'reports/kernel-entry-probe/2026-10-25-v24/build.json'
    jobs = [
        ('software', 'test-kernel-entry-probe.py', []),
        ('read-sites', 'test-probe-read-sites.py', []),
        ('wfe', 'test-probe-wfe.py', ['--negative-build', 'reports/kernel-entry-probe/2026-10-25-v20/build.json']),
        ('mapping', 'audit-entry-probe-post-mmu-mapping.py', []),
        ('loader', 'audit-entry-probe-loader.py', ['--work', str(work / 'loader')]),
        ('post-arm-init', 'test-post-arm-init-markers.py', ['--adt', str(a.adt.resolve())]),
        ('exception', 'test-post-arm-init-markers.py', ['--handler']),
        *[('transition-' + case, 'test-probe-transition.py', ['--adt', str(a.adt.resolve()), '--case', case])
          for case in ('normal', 'occupied-probe', 'bad-topology', 'occupied-fb')],
        ('console-policy', 'test-probe-console-policy.py', ['--adt', str(a.adt.resolve()), '--negative-build', 'reports/kernel-entry-probe/2026-10-25-v22c/build.json']),
        ('renderer-bounds', 'test-probe-renderer-bounds.py', ['--negative-build', old]),
        ('context-display', 'test-probe-context-display.py', []),
        ('vectors', 'test-probe-vectors.py', ['--negative-build', old]),
        ('transparency', 'test-probe-transparency.py', []),
        ('image4-launch', 'test-image4-launch.py', ['--adt', str(a.adt.resolve()),
         '--nonce', str(a.nonce.resolve()), '--manifest', str(a.manifest.resolve()),
         '--baseline-adt', 'out/trial-boot/xnu-entry-probe-18-vectors/kernel.macho.adt']),
        *([('pthread-startup', 'test-pthread-startup.py', [])] if report.get('probe_revision')==28 else []),
        ('binding', 'test-probe-evidence-binding.py', [])]
    records = []
    evidence = build.with_name('execution.json')
    for name, script, options in jobs:
        command = [sys.executable, '-B', str(ROOT / 'scripts' / script), '--build', str(build),
                   '--output', str(build.with_name(name + '.json')), *options]
        print(json.dumps({'starting': name}), flush=True)
        start = time.monotonic()
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=1200)
        records.append({'name': name, 'argv': command, 'exit_code': result.returncode,
                        'elapsed_seconds': time.monotonic() - start,
                        'stdout': result.stdout, 'stderr': result.stderr})
        evidence.write_bytes(json.dumps({'candidate_sha256': report['candidate']['sha256'],
                              'serial_execution': True, 'device_accessed': False,
                              'commands': records}, indent=2).encode() + b'\n')
        print(json.dumps({'finished': name, 'exit_code': result.returncode,
                          'stdout_tail': result.stdout[-800:], 'stderr_tail': result.stderr[-1000:]}), flush=True)
        result.check_returncode()
    print(json.dumps({'jobs': len(records), 'passed': True}), flush=True)


if __name__ == '__main__':
    main()
