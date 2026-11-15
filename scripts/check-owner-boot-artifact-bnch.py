"""Consume a final ADT unchanged with the original bounded Image4 initializer."""
import argparse
import importlib.util
from pathlib import Path

from owner_bnch import (KERNEL_SHA, ROOT, binding, inspect_adt, load_record, read_json,
                        require, reserve, sha, write_json)


def fixture():
    spec = importlib.util.spec_from_file_location('owner_bnch_original_fixture',
                                                 ROOT / 'scripts/research-current-image4-bnch.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check(kernel, adt, record_path, expected_sha, output, failure_controls=False):
    raw, final = Path(kernel).read_bytes(), Path(adt).read_bytes()
    require(sha(raw) == KERNEL_SHA and len(raw) == 55357440, 'Fixed kernel hash/size mismatch')
    require(sha(final) == expected_sha, 'Final ADT SHA mismatch')
    candidate = Path(adt).resolve().parent
    require(Path(record_path).resolve().parent == candidate, 'Record must belong to final ADT candidate')
    inputs = binding((candidate / 'input.dtb').read_bytes(), read_json(candidate / 'config.json'),
                     read_json(candidate / 'keywords.json'))
    record, token = load_record(record_path, inputs)
    require(record['status'] == 'generated' and record['final_adt_sha256'] == expected_sha,
            'Final ADT/record binding mismatch')
    inspect_adt(final, token)
    out = reserve(output)
    f = fixture()
    macho = f.A.B.macho(raw)
    bindings = f.binding(raw, macho)

    class Observed(f.Run):
        def watch(self, u, pc, size, data):
            super().watch(u, pc, size, data)
            if pc == f.BNCH_RETURN:
                address, length, before, after = self.init_guard
                self.outcome['bnch_output_hex'] = bytes(u.mem_read(address, 48)).hex()
                self.outcome['bnch_capacity'] = 48
                self.outcome['bnch_adjacent_before_hex'] = before.hex()
                self.outcome['bnch_adjacent_after_hex'] = after.hex()
                self.outcome['bnch_return_pc'] = hex(pc)

    run = Observed(raw, macho, final)
    observation = run.initialize()
    require(observation.get('bnch_errno') == 0 and observation.get('bnch_output_length') == 48 and
            observation.get('bnch_output_hex') == token.hex() and observation.get('bnch_canaries_intact') and
            observation['stop'] == 'initializer return', 'Original final initializer observation mismatch')
    # Observe, do not assign success semantics to the initializer's raw return register.
    # Run.initialize returns at the original sentinel after the untouched initializer RET.
    observation['initializer_return_x0'] = hex(run.u.reg_read(f.UC_ARM64_REG_X0))
    controls = {}
    if failure_controls:
        # Separate generated failure controls; never transform final ADT or call variant().
        disabled = Path(adt).parent / 'disabled.adt'
        missing = disabled.read_bytes()
        inspect_adt(missing)
        # The formal adapter is the only generator; oversized control uses the original fixture's
        # encoder exclusively as a negative test fixture, not as a candidate generation path.
        oversized = f.variant(missing, token + b'x')
        for label, blob, error in [('missing', missing, 2), ('oversized49', oversized, 84)]:
            result = Observed(raw, macho, blob).initialize()
            require(result['bnch_errno'] == error and result['bnch_output_length'] == 48 and
                    result['stop'] == 'original panic edge' and
                    result['panic'] == 'failed to read boot nonce hash: secure boot level = %#llx: %d' and
                    result['panic_stack_values'] == [0, error] and result['bnch_canaries_intact'],
                    'Original failure path changed: ' + label)
            controls[label] = result
    report = {'status': 'self-checked', 'kernel_sha256': sha(raw), 'final_adt_sha256': sha(final),
              'final_input_unmodified': True, 'binding': bindings, 'initialization': observation,
              'failure_controls': controls, 'authentication': 'NOT REACHED',
              'scope': 'constructed-state initializer only; not runtime/device release'}
    write_json(out / 'initializer.json', report)
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kernel', type=Path, required=True)
    p.add_argument('--adt', type=Path, required=True)
    p.add_argument('--record', type=Path, required=True)
    p.add_argument('--adt-sha256', required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--failure-controls', action='store_true')
    a = p.parse_args()
    check(a.kernel, a.adt, a.record, a.adt_sha256, a.output, a.failure_controls)
    print('self-checked: original final-input initializer and requested failure controls')


if __name__ == '__main__':
    main()
