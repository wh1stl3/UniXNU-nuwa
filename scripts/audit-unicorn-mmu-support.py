"""Record whether this environment can translate an ARM64 fetch at all."""
import hashlib, json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
probe = ROOT/'scripts/probe-unicorn-mmu.py'
output = Path(sys.argv[1])


def run(argv, env=None):
    result = subprocess.run(argv, capture_output=True, text=True, cwd=ROOT, env=env)
    return {'argv': argv, 'exit_code': result.returncode,
            'stdout': result.stdout.strip()[-400:], 'stderr': result.stderr.strip()[-400:]}


import os
windows_env = {**os.environ, 'PYTHONPATH': str(ROOT/'out/python-tools')}
report = {
    'scope': ('Whether this host can execute an ARM64 instruction fetch through stage-1 '
              'translation; a negative answer blocks any real MMU-crossing test here'),
    'probe_script': {'path': str(probe.relative_to(ROOT)),
                     'sha256': hashlib.sha256(probe.read_bytes()).hexdigest()},
    'cases': [
        {'name': 'windows-unicorn-2.1.4-out/python-tools',
         'result': run([sys.executable, '-B', str(probe)], windows_env)},
        {'name': 'wsl-ubuntu-22.04-unicorn-2.1.4',
         'result': run(['wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
                        f'cd /mnt/d/Code/UniXNU-nuwa && python3 -B scripts/probe-unicorn-mmu.py'])},
    ],
}
refused = all(case['result']['exit_code'] == 1 for case in report['cases'])
report['conclusion'] = ('Every probed build refuses the textbook non-identity page table: this environment does '
                        'not translate ARM64 instruction fetches, so the post-MMU hooks can only be entered '
                        'directly. A real transition test needs another emulator or hardware.'
                        if refused else 'At least one build translated the fetch: a real transition test is possible')
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'refused_everywhere': refused, 'output': str(output)}))
