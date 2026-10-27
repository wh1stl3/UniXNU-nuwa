"""Test integrated dispatch fields against native wrappers; callback body modeled."""
import argparse, importlib.util, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('dispatch_model', ROOT/'scripts/test-read-dispatch-observer.py')
T = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = T
spec.loader.exec_module(T)
B, A = T.B, T.A
TILE = ((832, 808, 32, 16),)
RENDER_RECTS = TILE + ((256,728,480,20),(256,756,480,20),(832,784,480,16))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or not args.output.resolve().is_relative_to(ROOT/'reports'):
        raise ValueError('Fresh report path required')
    build = json.loads(args.build.read_text())
    assert build['probe_revision'] in (37,38,39,40,41,42,43,44,45,46,47,48,49)
    raw = (ROOT/build['candidate']['path']).read_bytes()
    assert B.sha(raw) == build['candidate']['sha256']
    macho = B.macho(raw)
    original = B.INPUT.read_bytes()
    assert B.sha(original) == B.EXPECTED
    original_macho = B.macho(original)
    reference = bytearray(raw)
    for pc in (0xfffffff00769bf90, 0xfffffff00769bf94, A.DISPATCH, A.DISPATCH+4, A.ENTRY):
        offset = B.backed(macho, pc)
        old = B.backed(original_macho, pc)
        reference[offset:offset+4] = original[old:old+4]
    if build['probe_revision']>=38:
        from read_body_sites import points
        for point in points():
            pc=point['site'];offset=B.backed(macho,pc);old=B.backed(original_macho,pc)
            reference[offset:offset+4]=original[old:old+4]
    reference = bytes(reference)
    # Check stale display state before other scenarios; retaining a prior entry
    # tile must fail even when all new target/entry values happen to be correct.
    actual = T.header_reset(raw, macho, build, b'', 0x600000, [], True, TILE)
    expected = T.header_reset(reference, macho, build, b'', 0x600000, [], False, TILE)
    assert actual == expected
    cases = [dict(name='matched candidate', index=17), dict(name='assigned index1', index=1),
             dict(name='assigned index73', index=73), dict(name='error return preserved', errno=5),
             dict(name='candidate body pending', pending=True),
             dict(name='different target', target=0xfffffff00519041c),
             dict(name='unmapped target', target=0x500000, invalid_target=True),
             dict(name='foreign thread', foreign_thread=True), dict(name='foreign frame', foreign_frame=True),
             dict(name='no video', no_video=True), dict(name='null context', null_context=True)]
    checks = []
    for case in cases:
        actual, fields, bounds = T.execute(raw, macho, build, b'', 0x600000, [], case, True, RENDER_RECTS)
        expected, _, _ = T.execute(reference, macho, build, b'', 0x600000, [], case, False, RENDER_RECTS)
        # Diagnostic state may differ. Native registers, flags, caller stack,
        # native writes, errors and API behavior must match exactly.
        actual.pop('read_state')
        expected.pop('read_state')
        assert actual == expected, (case, {k: (actual[k], expected[k]) for k in actual if actual[k] != expected[k]})
        if case['name']=='matched candidate':assert bounds['writes']>0 and bounds['max_row']==831
        checks.append(dict(name=case['name'], passed=True, fields=fields, snapshot=actual,renderer=bounds))
    symbols = {k: int(v, 16) for k, v in build['probe']['symbols'].items()}
    start = symbols['probe_dense_746c688']
    end = symbols['probe_dense_746c688_replay']
    target_moves = [i for i in A.disasm(raw, macho, start, end-start)
                    if i.mnemonic == 'mov' and i.op_str == 'x23, x8']
    assert len(target_moves) == 1
    mutated = bytearray(raw)
    offset = B.backed(macho, target_moves[0].address)
    mutated[offset:offset+4] = bytes.fromhex('f70307aa')  # MOV x23,x7; display must fail
    rejected = False
    try:
        T.execute(bytes(mutated), macho, build, b'', 0x600000, [], cases[0], True, RENDER_RECTS)
    except AssertionError:
        rejected = True
    assert rejected, 'Wrong runtime-target display was not rejected'
    report = dict(scope=__doc__, candidate_sha256=build['candidate']['sha256'],
                  source_sha256=B.sha((ROOT/'scripts/read_dispatch_sites.py').read_bytes()),
                  checks=checks, header_stale_fields_and_entry_tile_cleared=True,
                  wrong_target_register_negative_rejected=True,
                  sources=[dict(path=p.relative_to(ROOT).as_posix(), sha256=B.sha(p.read_bytes()))
                           for p in (Path(__file__), ROOT/'scripts/test-read-dispatch-observer.py',
                                     ROOT/'scripts/read_dispatch_sites.py', ROOT/'scripts/read_boundary_sites.py')],
                  observation_state_excluded_from_native_transparency=True,
                  real_filesystem_body_executed=False, device_accessed=False,
                  boot_package_emitted=False)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+chr(10), encoding='utf-8', newline=chr(10))
    print(json.dumps(dict(checks=len(checks), stale_cleared=True, passed=True)))


if __name__ == '__main__':
    main()
