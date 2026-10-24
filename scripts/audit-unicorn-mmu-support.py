"""Record what this environment can and cannot translate, with an explicit tri-state.

Two independent probes:
  * probe-unicorn-mmu.py        one fetch with XNU's own TCR and an L1 root
  * probe-unicorn-start-level.py A-H matrix over TCR shape / root layout / VA size

Exit codes are classified, never guessed: 0 translated, 1 refused, anything else is
an environment error and must not be counted as success.
"""
import hashlib, json, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBES = {'single': ROOT/'scripts/probe-unicorn-mmu.py',
          'matrix': ROOT/'scripts/probe-unicorn-start-level.py'}


def classify(exit_code):
    return {0: 'translated', 1: 'refused'}.get(exit_code, 'environment-error')


def run(argv, env=None):
    result = subprocess.run(argv, capture_output=True, text=True, cwd=ROOT, env=env)
    return {'argv': argv, 'exit_code': result.returncode, 'classification': classify(result.returncode),
            'stdout': result.stdout.strip()[-400:], 'stdout_full': result.stdout,
            'stderr': result.stderr.strip()[-400:]}


def hosts():
    yield 'windows-unicorn-2.1.4', {**os.environ, 'PYTHONPATH': str(ROOT/'out/python-tools')}, \
        lambda script: [sys.executable, '-B', str(script)]
    yield 'wsl-ubuntu-22.04-unicorn-2.1.4', None, \
        lambda script: ['wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
                        f'cd /mnt/d/Code/UniXNU-nuwa && python3 -B {script.relative_to(ROOT).as_posix()}']


def main():
    output = Path(sys.argv[1])
    report = {'scope': ('What this host can translate, and why the real XNU cold path still cannot '
                        'cross the MMU here; not hardware behaviour'),
              'probes': {name: {'path': str(p.relative_to(ROOT)),
                                'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                         for name, p in PROBES.items()},
              'hosts': []}
    for name, env, argv in hosts():
        single = run(argv(PROBES['single']), env)
        matrix = run(argv(PROBES['matrix']), env)
        try:
            # Unicorn prints a deprecation warning before our JSON on one host.
            tail = [line for line in matrix['stdout_full'].splitlines() if line.startswith('{')]
            matrix_json = json.loads(tail[-1]) if tail else None
        except json.JSONDecodeError:
            matrix_json = None
        report['hosts'].append({'host': name, 'single': single, 'matrix_run': matrix, 'matrix': matrix_json})
    matrices = [h['matrix'] for h in report['hosts'] if h['matrix']]
    report['summary'] = {
        'single_case': sorted({h['single']['classification'] for h in report['hosts']}),
        'l2_root_works_only_for_t0sz26': all(m['l2_root_works_only_for_t0sz26'] for m in matrices) if matrices else None,
        'high_va_translatable_with_t0sz26': any(m['high_va_translatable_with_t0sz26'] for m in matrices) if matrices else None,
    }
    report['conclusion'] = (
        'Translation itself works, but this build starts the T0SZ=26 walk at level 2 and therefore '
        'cannot address the kernel VA: low VAs translate with an L2 root while 0x40000000 and '
        '0x8c37c7378 do not. XNU uses T0SZ=26 with an L1 root, so the real cold path cannot cross '
        'here and no harness-side re-rooting can fix it; a transition test needs another engine or hardware.'
        if matrices and not report['summary']['high_va_translatable_with_t0sz26']
        else 'High VAs translated on at least one host: a real transition test may be possible')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'summary': report['summary'], 'output': str(output)}))


if __name__ == '__main__':
    main()
