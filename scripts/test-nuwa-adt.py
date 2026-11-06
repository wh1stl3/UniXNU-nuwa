"""End-to-end tests for the nuwa ADT generator and the independent checker.

Positive cases call scripts/make-nuwa-adt.py the way the UniXNU payload step
does and require the checker to pass. Negative cases build deliberately broken
trees and require the checker to reject them on the exact constraint that
DarwinBoot or ArmDTPlatform enforces -- a checker that only ever passes proves
nothing.

Fixtures are written under out/ (git-ignored). Only the JSON report is
committed.
"""
import argparse
import hashlib
import importlib.util
import json
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'out/adt-nuwa/test-fixtures'


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


checker = load(ROOT / 'scripts/check-nuwa-adt.py', 'check_nuwa_adt')
generator = load(ROOT / 'scripts/make-nuwa-adt.py', 'make_nuwa_adt')

u32 = lambda value: struct.pack('<I', value)


def run_generator(args, name):
    output = FIXTURES / (name + '.adt')
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, str(ROOT / 'scripts/make-nuwa-adt.py'),
               '--output', str(output), *args]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise AssertionError('generator failed for %s: %s' % (name, result.stderr.strip()))
    return output.read_bytes()


def broken(chosen_extra=(), memory_map_props=(), with_options=True, dram_size=0x240000000):
    """A tree that is valid except for the one thing the caller breaks."""
    node = generator.node
    return node('device-tree', [
        ('model', b'test\0'),
        ('#address-cells', u32(2)),
        ('#size-cells', u32(2)),
    ], [
        node('chosen', [('random-seed', bytes(64)), ('osenvironment', b'main\0'),
                        ('dram-base', struct.pack('<Q', 0x8C0000000)),
                        ('dram-size', struct.pack('<Q', dram_size)),
                        *chosen_extra, *generator.empty_nvram_proxy()],
             [node('memory-map', list(memory_map_props))]),
        node('cpus', children=[node('cpu0', [('state', b'running\0'), ('reg', u32(0)),
                                             ('timebase-frequency', u32(19200000))])]),
        node('defaults', [('sleep-disabled', u32(1))]),
        *([node('options')] if with_options else []),
        node('arm-io', [('ranges', struct.pack('<QQQ', 0, 0x17000000, 0x08000000))], [
            node('intc', [('compatible', b'arm,gic-v3\0'),
                          ('reg', struct.pack('<4Q', 0x100000, 0x10000, 0x180000, 0x200000))]),
        ]),
    ])


def audit(blob):
    nodes = checker.decode(blob)
    return checker.audit(nodes)


def main():
    cli = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    cli.add_argument('--output', type=Path, required=True, help='fresh report under reports/')
    args = cli.parse_args()
    target = args.output.resolve()
    if not target.is_relative_to(ROOT / 'reports') or target.exists():
        raise ValueError('fresh report under reports/ required')

    results = []

    def record(name, expect, blob, expect_failure=None):
        checks, failures, notes = audit(blob)
        passed = not failures if expect == 'pass' else bool(failures)
        detail = {'case': name, 'expect': expect, 'checks': len(checks),
                  'failures': failures, 'advisories': notes,
                  'outcome': 'ok' if passed else 'unexpected'}
        if expect == 'fail' and expect_failure is not None:
            named = any(expect_failure in failure for failure in failures)
            detail['expected_failure'] = expect_failure
            detail['matched_expected_failure'] = named
            passed = passed and named
            detail['outcome'] = 'ok' if passed else 'unexpected'
        results.append(detail)
        return passed

    # --- positive: real generator output through the real checker --------
    record('minimal-tree', 'pass', run_generator(['--dram-size', '0x240000000'], 'minimal'))
    record('full-tree', 'pass', run_generator([
        '--dram-size', '0x240000000', '--owned-memory-size', '0x40000000',
        '--ipad-identity', '--data-ramdisk', '--trust-cache', '--gpu-addon',
        '--unique-chip-id', '0x0123456789abcdef', '--chip-id', '0x8550',
        '--cpu-regs', '0,256,512,768,1024,1280,1536,1792', '--psci-method', 'smc',
        '--text-fixup', 'test_symbol,10,aabb,ccdd'], 'full'))
    record('packed-ramdisk', 'pass', run_generator([
        '--dram-size', '0x240000000', '--packed-data-ramdisk'], 'packed'))

    # The base passes --unique-chip-id and --chip-id independently (payload.py:150-155),
    # so a lone seed must still yield a valid tree carrying just that property. A hard
    # pairing requirement here would stall any board whose chip_id is still TODO.
    seed_only = run_generator(['--dram-size', '0x240000000',
                               '--unique-chip-id', '0x0123456789abcdef'], 'seed-only')
    record('seed-without-chip-id', 'pass', seed_only)
    seed_props = checker.decode(seed_only)['/device-tree/chosen']['properties']
    results.append({'case': 'seed-without-chip-id-carries-one-property', 'expect': 'one property',
                    'has_unique_chip_id': 'unique-chip-id' in seed_props,
                    'has_chip_id': 'chip-id' in seed_props,
                    'outcome': 'ok' if ('unique-chip-id' in seed_props and 'chip-id' not in seed_props)
                                          else 'unexpected'})

    # --- negative: each breaks exactly one enforced constraint -----------
    record('missing-options', 'fail', broken(with_options=False),
           expect_failure='required node /device-tree/options')
    record('both-ramdisks', 'fail',
           broken(memory_map_props=(('RAMDisk', bytes(16)), ('PackedRAMDisk', bytes(16)))),
           expect_failure='RAMDisk and PackedRAMDisk are not both present')
    record('window-below-floor', 'fail',
           broken(chosen_extra=(('darwinboot-memory-size', struct.pack('<Q', 0x1000000)),)),
           expect_failure='owned window is 256 MiB..8 GiB in 2 MiB steps')
    record('window-above-dram', 'fail',
           broken(chosen_extra=(('darwinboot-memory-size', struct.pack('<Q', 0x40000000)),),
                   dram_size=0x20000000),
           expect_failure='owned window fits the advertised DRAM size')

    # Generator argument refusal, not a tree check.
    refused = subprocess.run([sys.executable, str(ROOT / 'scripts/make-nuwa-adt.py'),
                              '--output', str(FIXTURES / 'refused.adt'),
                              '--dram-size', '0x240000000',
                              '--owned-memory-size', '0x1000000'],
                             capture_output=True, text=True)
    results.append({'case': 'generator-refuses-small-window', 'expect': 'refuse',
                    'returncode': refused.returncode,
                    'outcome': 'ok' if refused.returncode != 0 else 'unexpected'})

    unexpected = [result for result in results if result['outcome'] != 'ok']
    report = {
        'scope': 'offline generator/checker tests; no device, no boot, no QEMU',
        'generator_sha256': hashlib.sha256((ROOT / 'scripts/make-nuwa-adt.py').read_bytes()).hexdigest(),
        'checker_sha256': hashlib.sha256((ROOT / 'scripts/check-nuwa-adt.py').read_bytes()).hexdigest(),
        'cases': results,
        'unexpected': [result['case'] for result in unexpected],
        'status': 'all_cases_expected' if not unexpected else 'unexpected_outcomes',
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('cases: %d, unexpected: %d, status: %s'
          % (len(results), len(unexpected), report['status']))
    for result in unexpected:
        print('  UNEXPECTED:', result['case'], result.get('failures'))
    if unexpected:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
