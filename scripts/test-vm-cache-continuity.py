"""Run native UBC and VM prologues/epilogues with explicit object/lock fixtures.

This tests observer ancestry across nested native calls, not hardware VM locks.
The busy-page case supplies a wakeup and then a cache miss; it cannot establish
that a real page completion provider or scheduler exists on nuwa.
"""
import argparse
import importlib.util
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('vm_flow_model', ROOT / 'scripts/test-read-flow.py')
M = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = M
spec.loader.exec_module(M)
C, T, P = M.CLUSTER_CHECKS, M.T, M.CLUSTER_CHECKS.P


def run(raw, build, original, om, case, mode, native):
    point = next(p for p in P.points() if p['site'] == P.BASE + 0x438c34)
    u, m, sy, state, own = C.setup(M, raw, build, point, mode)
    fp = u.reg_read(T.UC_ARM64_REG_X29)
    uio, obj, page = T.STACK + 0xb000, T.STACK + 0xc000, T.STACK + 0xd000
    u.reg_write(T.UC_ARM64_REG_X1, uio)
    u.reg_write(T.UC_ARM64_REG_X2, fp - 0x60)
    u.reg_write(T.UC_ARM64_REG_X3, 0)
    u.reg_write(T.UC_ARM64_REG_X4, 1)
    u.reg_write(T.UC_ARM64_REG_X20, 8)
    u.mem_write(fp - 0x60, struct.pack('<I', 8))
    u.mem_write(uio + 0x18, struct.pack('<Q', 0))
    u.mem_write(uio + 0x20, struct.pack('<I', 2))
    u.mem_write(uio + 0x28, struct.pack('<Q', 8))
    u.mem_write(obj, bytes(0x100))
    u.mem_write(page, bytes(0x100))
    u.mem_write(page + 0x2c, struct.pack('<I', 1))  # busy bit in fixed instructions
    u.mem_write(P.BASE + 0x15d118, struct.pack('<I', 12))
    if native:
        for p in P.points():
            at = M.B.backed(om, p['site'])
            u.mem_write(p['site'], original[at:at + 4])
    trace, records, calls = [], [], []
    lookup_count = 0
    watched = {P.BASE + x for x in (0x438c34, 0x43cb58, 0x3005cc, 0x300c98, 0x43cc74, 0x438c38, 0x438c3c)}

    def hook(machine, pc, size, data):
        nonlocal lookup_count
        if pc in watched:
            trace.append(hex(pc))
        if not native and pc == P.BASE + 0x300c7c:
            records.append(list(struct.unpack('<8Q', machine.mem_read(sy['probe_result_state'], 64)))[4:6])
        result = None
        if pc == P.BASE + 0x6fa47c:  # explicit ubc_getobject boundary
            result = obj
        elif pc == P.BASE + 0x310f90:  # memory_object_control_to_vm_object
            result = 0 if case == 'null-object' else obj
        elif pc in (P.BASE + 0x34aa44, P.BASE + 0x34aa38):
            calls.append(hex(pc))  # supplied lock/unlock completion
            result = 0
        elif pc == P.BASE + 0x36ed78:
            lookup_count += 1
            result = page if case == 'busy-then-miss' and lookup_count == 1 else 0
        elif pc == P.BASE + 0x34d49c:
            calls.append(hex(pc))  # supplied PAGE_SLEEP return, not real wakeup
            result = 0
        if result is not None:
            machine.reg_write(T.UC_ARM64_REG_X0, result)
            machine.reg_write(T.UC_ARM64_REG_PC, machine.reg_read(T.UC_ARM64_REG_LR))
        if pc == P.BASE + 0x438c40:
            machine.emu_stop()

    u.hook_add(T.U.UC_HOOK_CODE, hook)
    u.emu_start(point['site'], 0, count=20000000)
    assert u.reg_read(T.UC_ARM64_REG_PC) == P.BASE + 0x438c40
    assert trace == [hex(P.BASE + x) for x in (0x438c34, 0x43cb58, 0x3005cc, 0x300c98, 0x43cc74, 0x438c38, 0x438c3c)]
    assert lookup_count == {'null-object': 0, 'cache-miss': 1, 'busy-then-miss': 2}[case]
    assert (hex(P.BASE + 0x34d49c) in calls) == (case == 'busy-then-miss')
    assert u.reg_read(T.UC_ARM64_REG_X0) == 0
    assert struct.unpack('<I', u.mem_read(fp - 0x60, 4))[0] == 8
    if not native:
        assert records == [[P.BASE + 0x300c78, 0]], records
        record = struct.unpack('<8Q', u.mem_read(sy['probe_result_state'], 64))
        assert record[4:6] == (P.BASE + 0x438c3c, (8 << 32) | 8)
        for group in ('ubccopy', 'vmcopy'):
            assert struct.unpack('<4Q', u.mem_read(sy[P.state_name(group)], 32))[1] == 0
    if not native and mode == 'normal':
        for offset,color in ((0x438c38,0xffffffff),(0x438c3c,0xff00ffff)):
            p=next(p for p in P.points() if p['offset']==offset)
            color=color if P.tile_selected(p) else 0
            x,y=P.geometry(p)
            for yy in range(y,y+6):
                assert bytes(u.mem_read(T.FB+yy*T.ROW+x*4,96))==struct.pack('<I',color)*24
    return M.D.snapshot(u), bytes(u.mem_read(uio, 48)), trace, calls


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists()
    build = json.loads(args.build.read_bytes())
    raw = (ROOT / build['candidate']['path']).read_bytes()
    assert M.B.sha(raw) == build['candidate']['sha256']
    if build.get('lean_observation'):
        import lean_probe_inputs as L
        L.verify_bytes(build,raw)
        assert build['read_flow']==L.read(L.BASE/'build.json')['read_flow']
    else:assert build['read_flow'] == M.P.plan()
    original = M.B.INPUT.read_bytes()
    assert M.B.sha(original) == M.B.EXPECTED
    om = M.B.macho(original)
    checks = []
    for case in ('null-object', 'cache-miss', 'busy-then-miss'):
        for mode in ('normal', 'no-video'):
            actual = run(raw, build, original, om, case, mode, False)
            reference = run(raw, build, original, om, case, mode, True)
            assert actual == reference, (case, mode)
            checks.append(dict(name=case + ':' + mode, passed=True, trace=actual[2], supplied_calls=actual[3]))
    args.output.write_bytes(json.dumps(dict(candidate_sha256=M.B.sha(raw), source_sha256=M.B.sha(Path(__file__).read_bytes()), checks=checks, limitations=['Object conversion, locks, lookup and sleep completion supplied by explicit fixtures', 'Native VM and UBC bodies, frame ancestry and caller continuation execute; not real VM, IO or hardware recovery']), indent=2).encode() + b'\n')
    print(json.dumps(dict(checks=len(checks), passed=True)))


if __name__ == '__main__':
    main()
