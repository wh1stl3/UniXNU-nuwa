"""Check fixture evidence provenance/completeness; not donor authentication tests."""
import argparse
import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / 'scripts/research-current-image4-bnch.py'
spec = importlib.util.spec_from_file_location('bnch_fixture', HARNESS)
H = importlib.util.module_from_spec(spec)
spec.loader.exec_module(H)
CASES = {'missing': (2, 48), 'zero_length': (0, 0),
         'experimental_48': (0, 48), 'oversized_49': (84, 48)}
DEPENDENCIES = ('audit-image4-runtime-provider.py', 'build-kernel-entry-probe.py',
                'nuwa_launch_context.py')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(report):
    """Reject incomplete/stale/wrong-source evidence before inspecting results.

    Hashes bind local sources, not cryptographically attest an emulator run.
    """
    H.require(report.get('harness_sha256') == sha(HARNESS), 'Harness provenance mismatch')
    H.require(report.get('dependencies') == {n: sha(ROOT / 'scripts' / n) for n in DEPENDENCIES},
              'Dependency provenance mismatch')
    H.require(report.get('kernel_sha256') == H.KERNEL_SHA and report.get('adt_sha256') == H.ADT_SHA,
              'Input provenance mismatch')
    H.require(set(report.get('cases', {})) == set(CASES), 'Exact four-case matrix required')
    for name, (error, length) in CASES.items():
        case = report['cases'][name]
        reader, init = case['reader'], case['initialization']
        H.require(reader['errno'] == init['bnch_errno'] == error, 'Wrong errno: ' + name)
        H.require(reader['output_length'] == init['bnch_output_length'] == length, 'Wrong length: ' + name)
        H.require(reader['canaries_intact'] and init['bnch_canaries_intact'] and
                  not reader['invalid_memory'] and not init['invalid_memory'], 'Bad buffer evidence: ' + name)
        H.require(init['secure_boot_level'] == 0 and init['actual_pmap_in_ppl_result'] == 0,
                  'Wrong simulated initial-state result: ' + name)
        for run in (reader, init):
            H.require(bool(run['donor_pcs']) and hex(H.READER) in run['donor_pcs'], 'Missing reader coverage: ' + name)
        if error:
            H.require(init['stop'] == 'original panic edge' and init['terminal_pc'] == hex(H.PANIC) and
                      init.get('panic') == 'failed to read boot nonce hash: secure boot level = %#llx: %d' and
                      init.get('panic_stack_values') == [0, error], 'Wrong panic: ' + name)
            H.require(reader['output_hex'] == (b'\xa5' * 48).hex(), 'Error changed output: ' + name)
        else:
            H.require(init['stop'] == 'initializer return' and init['terminal_pc'] == hex(H.A.STOP) and
                      'panic' not in init, 'Wrong successful termination: ' + name)
            H.require(len(bytes.fromhex(reader['output_hex'])) == 48, 'Wrong output capacity: ' + name)
            if length == 0:
                H.require(reader['output_hex'] == bytes(48).hex(), 'Zero-length output not zeroed')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--matrix', type=Path, required=True)
    p.add_argument('--kernel', type=Path, required=True)
    p.add_argument('--adt', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    out = a.output.resolve()
    H.require(out.is_relative_to(ROOT / 'out') and not out.exists(), 'Fresh device out/ evidence required')
    report = json.loads(a.matrix.read_text())
    validate(report)
    checks = ['complete four-case evidence matches current harness/dependencies/input pins and expected outcomes']

    def rejects(label, fn):
        try:
            fn()
        except ValueError:
            checks.append(label)
        else:
            raise AssertionError('False-positive acceptance: ' + label)

    # Target the reviewed false positives: vacuous iteration, missing cases,
    # stale/copied provenance, and wrong lengths/panic accepted as success.
    def corrupt(label, change):
        mutated = copy.deepcopy(report)
        change(mutated)
        rejects(label, lambda: validate(mutated))

    corrupt('empty cases rejected', lambda r: r.update(cases={}))
    corrupt('missing case rejected', lambda r: r['cases'].pop('oversized_49'))
    corrupt('extra case rejected', lambda r: r['cases'].update(unexpected=r['cases']['missing']))
    corrupt('wrong harness rejected', lambda r: r.update(harness_sha256='0'*64))
    corrupt('wrong dependency rejected', lambda r: r['dependencies'].update({DEPENDENCIES[0]: '0'*64}))
    corrupt('missing dependency rejected', lambda r: r['dependencies'].pop(DEPENDENCIES[0]))
    corrupt('wrong input source rejected', lambda r: r.update(kernel_sha256='0'*64))
    for case in CASES:
        corrupt('wrong reader length rejected: ' + case,
                lambda r, c=case: r['cases'][c]['reader'].update(output_length=47))
        corrupt('wrong initializer length rejected: ' + case,
                lambda r, c=case: r['cases'][c]['initialization'].update(bnch_output_length=47))
    corrupt('wrong panic format rejected', lambda r: r['cases']['missing']['initialization'].update(panic='other panic'))
    corrupt('wrong panic errno rejected', lambda r: r['cases']['oversized_49']['initialization'].update(panic_stack_values=[0, 2]))
    corrupt('empty coverage rejected', lambda r: r['cases']['missing']['reader'].update(donor_pcs=[]))
    rejects('unsupported input pin rejected', lambda: H.bound_input(a.kernel, '0'*64, H.KERNEL_SHA))
    rejects('wrong actual content rejected', lambda: H.bound_input(a.adt, H.KERNEL_SHA, H.KERNEL_SHA))
    rejects('wrong byte count rejected', lambda: H.bound_input(a.kernel, H.KERNEL_SHA, H.KERNEL_SHA, 1))
    raw = H.bound_input(a.adt, H.ADT_SHA, H.ADT_SHA)
    original = H.A.parse_adt(raw)
    for value in (None, b'', b'x'*48, b'x'*49):
        expected = copy.deepcopy(original)
        props = expected['/chosen/manifest-properties']
        props.pop('BNCH', None)
        if value is not None:
            props['BNCH'] = value
        H.require(H.A.parse_adt(H.variant(raw, value)) == expected, 'Non-BNCH ADT change')
    checks.append('only BNCH changes in four in-memory ADT variants')
    rejects('truncated ADT rejected', lambda: H.A.parse_adt(raw[:100]))
    for path in (HARNESS, Path(__file__)):
        compile(path.read_text(), str(path), 'exec')
    checks.append('both source entrypoints compile without pyc')
    before = a.matrix.read_bytes()
    result = subprocess.run([sys.executable, '-B', str(HARNESS), '--kernel', str(a.kernel),
                             '--kernel-sha256', H.KERNEL_SHA, '--adt', str(a.adt),
                             '--adt-sha256', H.ADT_SHA, '--output', str(a.matrix)],
                            capture_output=True, text=True)
    H.require(result.returncode == 1 and 'Fresh output below device out/ required' in result.stderr
              and a.matrix.read_bytes() == before, 'CLI did not preserve existing evidence')
    checks.append('CLI rejects evidence overwrite without changing matrix')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dict(status='self-checked', scope=__doc__, checks=checks,
                                   matrix_sha256=sha(a.matrix), test_sha256=sha(Path(__file__)),
                                   cwd=str(Path.cwd()), exit_code=0), indent=2) + '\n')
    print('self-checked:', len(checks), 'fixture evidence robustness checks')


if __name__ == '__main__':
    main()
