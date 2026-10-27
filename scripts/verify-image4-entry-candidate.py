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
    if (not build.is_relative_to(ROOT / 'reports') or report.get('probe_revision') not in (27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49)
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
        *([('pthread-startup', 'test-pthread-startup.py', [])] if report.get('probe_revision')>=28 else []),
        *([('root-stop', 'test-exec-release-boundary.py' if report.get('probe_revision')>=32 else 'test-pre-exec-stop.py' if report.get('probe_revision')>=31 else 'test-root-mount-stop.py', [])] if report.get('probe_revision')>=30 else []),
        *([('root-inputs', 'test-root-launch-context.py', [])] if report.get('probe_revision')>=30 else []),
        *([('fscompression-startup','test-fscompression-startup.py',[])] if report.get('probe_revision')>=35 else []),
        *([('read-boundaries','test-read-boundaries.py',[])] if report.get('probe_revision')>=36 else []),
        *([('read-boundary-source','audit-read-boundary-source.py',[])] if report.get('probe_revision')>=36 else []),
        *([('read-dispatch','test-read-dispatch-integrated.py',[])] if report.get('probe_revision')>=37 else []),
        *([('read-body','test-read-body.py',[])] if report.get('probe_revision')>=38 else []),
        *([('read-body-reset','test-read-body-reset.py',[])] if report.get('probe_revision')>=38 else []),
        *([('read-init','test-read-init.py',[])] if report.get('probe_revision')>=39 else []),
        *([('single-pass-hex','test-single-pass-hex.py',[])] if report.get('probe_revision')>=40 else []),
        *([('read-grid','test-read-grid.py',[])] if report.get('probe_revision')>=41 else []),
        *([('read-decmp','test-read-decmp.py',[])] if report.get('probe_revision')>=42 else []),
        *([('shared-hex','test-shared-hex.py',[])] if report.get('probe_revision')>=43 else []),
        *([('compact-decmp','test-compact-decmp.py',[])] if report.get('probe_revision')>=44 else []),
        *([('read-fetch','test-read-fetch.py',[])] if report.get('probe_revision')>=45 else []),
        *([('read-deep','test-read-deep.py',[])] if report.get('probe_revision')>=46 else []),
        *([('read-result','test-read-result.py',[])] if report.get('probe_revision')>=47 else []),
        *([('delta-hex','test-delta-hex.py',[])] if report.get('probe_revision')>=48 else []),
        *([('read-flow','test-read-flow.py',[])] if report.get('probe_revision')>=49 else []),
        ('binding', 'test-probe-evidence-binding.py', [])]
    records = []
    evidence = build.with_name('execution.json')
    for name, script, options in jobs:
        if name in ('read-body','read-flow') and build.with_name(name+'.json').exists():
            import hashlib
            path=build.with_name(name+'.json');payload=path.read_bytes();prior=json.loads(payload)
            if prior.get('candidate_sha256')!=report['candidate']['sha256'] or not prior.get('checks') or any(c.get('passed') is not True for c in prior['checks']):raise ValueError('Existing read-body evidence does not match candidate')
            records.append(dict(name=name,reused_exact_report=str(path),sha256=hashlib.sha256(payload).hexdigest(),exit_code=0,scope='Existing independent run; mandatory binding validates source, exact cases and sites'))
            continue
        if name=='binding' and report.get('probe_revision',0)>=36:
            # Git stores text evidence as LF. Bind those exact bytes so a clean
            # checkout retains the same hashes as the producing Windows tree.
            for evidence_path in build.parent.glob('*.json'):
                payload=evidence_path.read_bytes()
                evidence_path.write_bytes(payload.replace(b'\r\n',b'\n'))
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
