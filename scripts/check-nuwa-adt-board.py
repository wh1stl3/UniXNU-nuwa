"""Drive the ADT generator from board.toml exactly as UniXNU's payload step does.

`scripts/unixnu/payload.py:149-170` builds the generator command line from
[payload] and [payload.adt], and the payload step cannot run while board.toml
still says `example = true` (`config.py:103` rejects it). This reproduces that
argument assembly offline so the board values can be exercised before the rest
of the board is filled in.

What this proves: the board's ADT configuration produces a structurally valid
tree. What it does not prove: that UniXNU's own payload step agrees, that
firmware can satisfy the owned window, or anything about a boot.
"""
import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# (board key, command line flag) in the same order payload.py emits them.
ADT_SCALARS = (('owned_memory_size', '--owned-memory-size'),
               ('root_match_volume_uuid', '--root-match-volume-uuid'),
               ('chip_id', '--chip-id'),
               ('cpu_regs', '--cpu-regs'),
               ('psci_method', '--psci-method'))


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_command(board, tool, output, seed=None, data=False, trust=False, addon=False, fixups=()):
    """Mirror payload.py:149-170. Anything the base does not pass stays absent."""
    payload = board.get('payload', {})
    adt = payload.get('adt', {})
    command = [sys.executable, str(tool), '--output', str(output),
               '--dram-size', str(payload['dram_size'])]
    for key, flag in ADT_SCALARS:
        if adt.get(key) is not None:
            command += [flag, str(adt[key])]
    if seed:
        command += ['--unique-chip-id', seed]
    if data:
        command.append('--packed-data-ramdisk' if adt.get('packed_data_ramdisk') else '--data-ramdisk')
    if trust:
        command.append('--trust-cache')
    if addon:
        command.append('--gpu-addon')
    if adt.get('ipad_identity'):
        command.append('--ipad-identity')
    if data and adt.get('persistent_data'):
        command.append('--persistent-data')
    for fixup in fixups:
        command += ['--text-fixup', fixup]
    return command


def main():
    cli = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    cli.add_argument('--board', type=Path, default=ROOT / 'board.toml')
    cli.add_argument('--output', type=Path, required=True, help='fresh report under reports/')
    cli.add_argument('--adt-dir', type=Path, default=ROOT / 'out/adt-nuwa/board',
                     help='where the generated ADT is written (git-ignored)')
    cli.add_argument('--seed', default=None, help='platform seed, as --unique-chip-id would carry')
    cli.add_argument('--sidecars', action='store_true',
                     help='also pass the ramdisk/trustcache/gpuaddon flags the base passes when those inputs exist')
    args = cli.parse_args()

    target = args.output.resolve()
    if not target.is_relative_to(ROOT / 'reports') or target.exists():
        raise ValueError('fresh report under reports/ required')

    board = tomllib.loads(args.board.read_text(encoding='utf-8'))
    adt = board.get('payload', {}).get('adt', {})
    problems = []
    if 'dram_size' not in board.get('payload', {}):
        problems.append('[payload] dram_size is missing; payload.py:149 reads it unconditionally')
    if 'tool' not in adt:
        problems.append('[payload.adt] tool is missing; the payload step would have no generator')
    if problems:
        raise SystemExit('; '.join(problems))

    tool = args.board.parent / adt['tool']
    if not tool.is_file():
        raise SystemExit('tool does not exist: %s' % tool)

    runs = []
    for label, sidecars in (('board-only', False), ('board-with-sidecars', True)):
        if sidecars and not args.sidecars:
            continue
        output = args.adt_dir / (label + '.adt')
        output.parent.mkdir(parents=True, exist_ok=True)
        command = build_command(board, tool, output, seed=args.seed,
                                data=sidecars, trust=sidecars, addon=sidecars)
        result = subprocess.run(command, capture_output=True, text=True)
        entry = {'case': label,
                 'argv': [str(part) for part in command[2:]],
                 'returncode': result.returncode,
                 'stdout': result.stdout.strip(),
                 'stderr': result.stderr.strip()}
        if result.returncode == 0:
            blob = output.read_bytes()
            checker = load(ROOT / 'scripts/check-nuwa-adt.py', 'check_nuwa_adt')
            nodes = checker.decode(blob)
            checks, failures, notes = checker.audit(nodes)
            entry.update({'adt_bytes': len(blob),
                          'adt_sha256': hashlib.sha256(blob).hexdigest(),
                          'node_count': len(nodes),
                          'node_paths': sorted(nodes),
                          'checks': len(checks),
                          'failures': failures,
                          'advisories': notes})
            if failures:
                problems.append('%s: %s' % (label, ', '.join(failures)))
        else:
            problems.append('%s: generator exit %d' % (label, result.returncode))
        runs.append(entry)

    report = {
        'scope': 'offline replay of the payload step argument assembly; no boot, no device, no QEMU',
        'board': str(args.board),
        'board_sha256': hashlib.sha256(args.board.read_bytes()).hexdigest(),
        'tool': adt['tool'],
        'tool_sha256': hashlib.sha256(tool.read_bytes()).hexdigest(),
        'checker_sha256': hashlib.sha256((ROOT / 'scripts/check-nuwa-adt.py').read_bytes()).hexdigest(),
        'board_example_flag': board.get('board', {}).get('example'),
        'board_values_used': {
            'dram_size': board['payload']['dram_size'],
            'owned_memory_size': adt.get('owned_memory_size'),
            'cpu_regs': adt.get('cpu_regs'),
            'psci_method': adt.get('psci_method'),
            'ipad_identity': adt.get('ipad_identity'),
            'tool': adt.get('tool'),
        },
        'runs': runs,
        'failures': problems,
        'status': 'board_adt_configuration_valid' if not problems else 'board_adt_configuration_invalid',
        'not_proven': [
            'that UniXNU\'s own payload step accepts this board (example = true still blocks it)',
            'that firmware can satisfy the requested contiguous window',
            'that XNU accepts the tree at boot',
        ],
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('runs: %d, failures: %d, status: %s' % (len(runs), len(problems), report['status']))
    for run in runs:
        print('  %-20s exit=%d nodes=%s checks=%s'
              % (run['case'], run['returncode'], run.get('node_count'), run.get('checks')))
    for problem in problems:
        print('  FAILED:', problem)
    if problems:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
