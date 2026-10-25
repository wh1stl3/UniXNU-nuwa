"""Test complete native Image4 initialization and exact measured launch inputs.

Executes the real initializer prologue through RET; IOKit object boundaries and
runtime logging are modeled. This does not execute BSD or a physical device.
"""
import argparse
import copy
import gc
import importlib.util
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'out/python-tools')]
import nuwa_launch_context as C

spec = importlib.util.spec_from_file_location('provider', ROOT / 'scripts/audit-image4-runtime-provider.py')
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)


def full_init(raw, adt):
    macho = A.B.macho(raw)
    model = A.Model(raw, macho, A.parse_adt(adt))
    u = model.u
    tree = 0xe00000
    u.mem_map(tree, A.B.align(len(adt)))
    u.mem_write(tree, adt)
    model.call(macho['symbols']['_SecureDTInit'], (tree, len(adt)))
    outcome, trace = {}, []

    def watch(u, pc, size, data):
        if pc == 0xfffffff0046fa028:
            sp = u.reg_read(A.UC_ARM64_REG_SP)
            outcome.update(panic=model.cstr(u.reg_read(A.UC_ARM64_REG_X0)),
                           variadic_values=[model.get64(sp), model.get64(sp + 8)])
            u.emu_stop()
        if pc in (0xfffffff0046e99d8, 0xfffffff0046e9ad8):
            trace.append({'pc': hex(pc), 'consumer_runtime_x19': hex(u.reg_read(A.UC_ARM64_REG_X19))})

    u.hook_add(A.U.UC_HOOK_CODE, watch)
    saved = {getattr(A, f'UC_ARM64_REG_X{i}'): 0x11220000 + i * 0x100 for i in range(19, 30)}
    for reg, value in saved.items():
        u.reg_write(reg, value)
    u.reg_write(A.UC_ARM64_REG_X0, A.PMAP_RUNTIME)
    u.reg_write(A.UC_ARM64_REG_LR, A.STOP)
    u.reg_write(A.UC_ARM64_REG_SP, A.STACK + 0x8000)
    u.emu_start(0xfffffff0046e98cc, A.STOP, count=3000000)
    if model.bad:
        raise AssertionError(model.bad)
    returned = u.reg_read(A.UC_ARM64_REG_PC) == A.STOP
    if returned:
        if any(u.reg_read(reg) != value for reg, value in saved.items()) or u.reg_read(A.UC_ARM64_REG_SP) != A.STACK + 0x8000:
            raise AssertionError('Full initializer failed its native callee-saved/SP contract')
    elif not outcome:
        raise AssertionError('Initializer exhausted instructions without RET or original panic')
    if not trace or any(t['consumer_runtime_x19'] != hex(A.RUNTIME) for t in trace):
        raise AssertionError('Unexpected runtime loaded by the real initializer prologue')
    return model, {'returned': returned, **outcome, 'runtime_trace': trace,
                   'events': list(model.events), 'bad_memory': model.bad}


def mutate(adt, path, key, value):
    tree = C.parse(adt)
    node = C.find(tree, path)
    node['properties'] = [(k, f, v) for k, f, v in node['properties'] if k != key]
    if value is not None:
        node['properties'].append((key, 0, value))
    return C.encode(tree)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build', required=True, type=Path)
    p.add_argument('--adt', required=True, type=Path)
    p.add_argument('--nonce', required=True, type=Path)
    p.add_argument('--manifest', required=True, type=Path)
    p.add_argument('--baseline-adt', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args()
    build = json.loads(a.build.read_text())
    candidate = (ROOT / build['candidate']['path']).read_bytes()
    if C.sha256(candidate) != build['candidate']['sha256'] or build.get('probe_revision') not in (27,28,29,30,31):
        raise ValueError('Unexpected candidate/revision')
    original = A.B.INPUT.read_bytes()
    if C.sha256(original) != A.B.EXPECTED:
        raise ValueError('Original fixed input changed')
    adt, nonce = a.adt.read_bytes(), a.nonce.read_bytes()
    fd = ROOT / 'out/upstream-firmware-40014018074/nuwa-firmware-40014018074/build/FV/SILICIUM_UEFI.fd'
    shim = fd.parents[2] / 'shim/shim.bin'
    kernel = ROOT / build['candidate']['path']
    # FD: .../build/FV/SILICIUM_UEFI.fd -> artifact root is parents[2].
    context = C.validate(adt, kernel, fd, shim, nonce=nonce, manifest_bytes=a.manifest.read_bytes())
    checks, cases = [], {}

    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        checks.append({'name': name, 'passed': True})

    check('Actual nonce preimage and all four launch components match', context['nonce_preimage_checked'])
    baseline = a.baseline_adt.read_bytes()
    for name, data, panic in (
        ('shipped-baseline', baseline, 'failed to get mix-n-match policy: %d'),
        ('legal-amnm-only', mutate(baseline, '/chosen', C.POLICY_KEY, struct.pack('<I', 1)),
         'failed to read boot nonce hash: secure boot level = %#llx: %d')):
        model, result = full_init(original, data)
        check('Real prologue original ' + name, not result['returned'] and result.get('panic') == panic)
        cases[name] = result
        del model
        gc.collect()
    outer = {}
    for name, raw in (('unpatched', original), ('candidate', candidate)):
        model, result = full_init(raw, adt)
        check('Complete native Image4 initializer RET with measured inputs: ' + name, result['returned'])
        cases[name] = result
        bool_result = model.outer_identifier(12)
        out = A.STACK + 0x1000
        model.u.mem_write(out, b'\xa5' * 80)
        errno = model.call(0xfffffff0046ea358, (A.PMAP_RUNTIME, 0, 11, out))
        digest = bytes(model.u.mem_read(out, 80))
        outer[name] = {'amnm': bool_result, 'chmh_errno': errno,
                       'chmh_length': int.from_bytes(digest[8:16], 'little'),
                       'chmh_hex': digest[16:64].hex()}
        if name == 'unpatched':
            check('Unpatched subsequent dtless AMNM and CHMH queries reproduce ENOENT',
                  bool_result['errno'] == 2 and errno == 2)
            unrelated = {str(i): model.outer_identifier(i) for i in (5, 6, 7, 8, 9, 10, 13, 16)}
        else:
            check('Integrated AMNM preserves prevention-one as allow=false',
                  bool_result['errno'] == 0 and bool_result['output_hex'][:2] == '00')
            check('Integrated CHMH returns all 48 actual manifest digest bytes',
                  errno == 0 and int.from_bytes(digest[8:16], 'little') == 48
                  and digest[16:64].hex() == context['manifest_sha384'])
            check('Eight unrelated dtless queries retain native results',
                  unrelated == {str(i): model.outer_identifier(i) for i in (5, 6, 7, 8, 9, 10, 13, 16)})
            expected_hash = model.nodes['/chosen'][C.HASH_KEY]
            for label, value, wrong_type, expected_errno in (
                    ('missing', None, False, 2), ('oversized', bytes(49), False, 84),
                    ('wrong-type', bytes(48), C.HASH_KEY, 96)):
                if value is None:
                    model.nodes['/chosen'].pop(C.HASH_KEY, None)
                else:
                    model.nodes['/chosen'][C.HASH_KEY] = value
                model.wrong_type = wrong_type
                model.u.mem_write(out, b'\xa5' * 80)
                error = model.call(0xfffffff0046ea358, (A.PMAP_RUNTIME, 0, 11, out))
                check('Integrated CHMH preserves ' + label + ' error/output',
                      error == expected_errno and bytes(model.u.mem_read(out, 80)) == b'\xa5' * 80)
            model.nodes['/chosen'][C.HASH_KEY] = expected_hash
            model.wrong_type = False
        del model
        gc.collect()
    negative_inputs = [
        ('missing-amnm', mutate(adt, '/chosen', C.POLICY_KEY, None)),
        ('empty-amnm', mutate(adt, '/chosen', C.POLICY_KEY, b'')),
        ('relaxed-amnm', mutate(adt, '/chosen', C.POLICY_KEY, bytes(4))),
        ('missing-bnch', mutate(adt, '/chosen/manifest-properties', 'BNCH', None)),
        ('short-bnch', mutate(adt, '/chosen/manifest-properties', 'BNCH', bytes(47))),
        ('long-bnch', mutate(adt, '/chosen/manifest-properties', 'BNCH', bytes(49))),
        ('manifest-digest-corrupt', mutate(adt, '/chosen', C.HASH_KEY, bytes(48))),
        ('manifest-bytes-corrupt', mutate(adt, '/chosen', C.CONTEXT_KEY, b'{}\n')),
        ('board-value-corrupt', mutate(adt, '/chosen', 'dram-base', struct.pack('<Q', 1)))]
    for name, data in negative_inputs:
        try:
            C.validate(data, kernel, fd, shim, nonce=nonce)
        except (ValueError, KeyError):
            check('Context rejects ' + name, True)
        else:
            raise AssertionError(name)
    try:
        C.validate(adt, kernel, fd, shim, nonce=bytes(32))
    except ValueError:
        check('Wrong nonce preimage refused', True)
    else:
        raise AssertionError('Wrong nonce accepted')
    for name, data, panic in (
        ('missing-bnch', negative_inputs[3][1], 'failed to read boot nonce hash: secure boot level = %#llx: %d'),
        ('oversized-bnch', negative_inputs[5][1], 'failed to read boot nonce hash: secure boot level = %#llx: %d'),
        ('missing-chmh', mutate(adt, '/chosen', C.HASH_KEY, None), 'failed to get previous stage manifest hash: %d')):
        model, result = full_init(candidate, data)
        check('Native initialization error retained: ' + name, not result['returned'] and result.get('panic') == panic)
        cases[name] = result
        del model
        gc.collect()
    report = {'scope': __doc__, 'candidate_sha256': C.sha256(candidate),
              'adt_sha256': C.sha256(adt), 'context': context, 'checks': checks,
              'cases': cases, 'subsequent_queries': outer,
              'correction_to_v26': 'The real initializer prologue loads x19 from runtime+0x58, selecting Darwin IOKit, not the forced pmap runtime used in v26 slices. Missing AMNM explains the initial panic; cache incompatibility is reproduced for subsequent queries.',
              'modeled_boundaries': ['IORegistryEntry objects', 'OSData object methods/type casts', 'Darwin runtime logging'],
              'device_accessed': False, 'bsd_entered': False, 'runtime_qualified': False}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_bytes(json.dumps(report, indent=2).encode() + b'\n')
    print(json.dumps({'checks': len(checks), 'passed': True, 'native_initializer_returned': True,
                      'candidate_sha256': C.sha256(candidate), 'adt_sha256': C.sha256(adt)}))


if __name__ == '__main__':
    main()
