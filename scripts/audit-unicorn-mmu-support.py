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
        lambda script, flags=(): [sys.executable, '-B', str(script), *flags]
    yield 'wsl-ubuntu-22.04-unicorn-2.1.4', None, \
        lambda script, flags=(): ['wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
                                  'cd /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa && python3 -B '
                                  + script.relative_to(ROOT).as_posix() + ' ' + ' '.join(flags)]


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
        single_aarch64 = run(argv(PROBES['single'], ['--aarch64-state']), env)
        matrix = run(argv(PROBES['matrix']), env)
        try:
            # Unicorn prints a deprecation warning before our JSON on one host.
            tail = [line for line in matrix['stdout_full'].splitlines() if line.startswith('{')]
            matrix_json = json.loads(tail[-1]) if tail else None
        except json.JSONDecodeError:
            matrix_json = None
        report['hosts'].append({'host': name, 'single_default_state': single,
                                'single_aarch64_state': single_aarch64,
                                'matrix_run': matrix, 'matrix': matrix_json})
    matrices = [h['matrix'] for h in report['hosts'] if h['matrix']]
    report['summary'] = {
        'default_state': sorted({h['single_default_state']['classification'] for h in report['hosts']}),
        'aarch64_state': sorted({h['single_aarch64_state']['classification'] for h in report['hosts']}),
        'l2_root_works_only_for_t0sz26': all(m['l2_root_works_only_for_t0sz26'] for m in matrices) if matrices else None,
        'high_va_translatable_with_t0sz26': any(m['high_va_translatable_with_t0sz26'] for m in matrices) if matrices else None,
    }
    report['conclusion'] = (
        'AArch64 instruction translation works once the model is put into the execution state the '
        'kernel runs in: SCR_EL3.NS|RW (and HCR_EL2.RW) make arm_el_is_aa64() true. With Unicorn\'s '
        'default SCR_EL3=0/HCR_EL2=0 the walk takes the AArch32 branch, reads T0SZ & 7 = 2 and starts '
        'at L2, which is why the real T0SZ=26 tables looked untranslatable. The earlier "no fetch '
        'translation" reading was a harness initialisation error, not an engine limitation; the '
        'default-state failure stays as the negative control.'
        if report['summary']['aarch64_state'] == ['translated'] else
        'The AArch64 high-EL state did not translate either: investigate further before claiming a crossing')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'summary': report['summary'], 'output': str(output)}))


if __name__ == '__main__':
    main()
