"""Execute revision39 initialization checkpoints and actual snapshot height guard."""
import argparse
import importlib.util
import json
import struct
import sys
from pathlib import Path
import read_init_sites as P

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('read_init_model', ROOT/'scripts/test-read-dispatch-observer.py')
T = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = T
spec.loader.exec_module(T)


def reset(raw, m, b, video=True):
    u = T.machine(raw, m, b'', 0, [], False)
    sy = {k: int(v, 16) for k, v in b['probe']['symbols'].items()}
    u.mem_write(sy['probe_scratch'], struct.pack('<QQ', T.FB if video else 0, T.ROW))
    u.mem_write(sy['probe_read_body_state'], b'\xff'*8)
    start, end = sy['probe_dense_769bf90'], sy['probe_dense_769bf90_replay']
    ins = T.A.disasm(raw, m, start, end-start)
    stages = {i.address: i.operands[1].imm for i in ins if i.mnemonic == 'mov'
              and i.op_str.startswith('x23, #0xf90')}
    assert list(stages.values()) == [int(k, 16) for k in P.CHECKPOINTS]
    seen = []

    def watch(u, pc, n, d):
        if pc in stages:
            stage = stages[pc]
            if video:
                assert T.field(u, 0xa034) == (250 if not seen else seen[-1])
                if stage >= 0xf902:
                    assert T.field(u, 0xa037) == 0
                if stage >= 0xf903:
                    assert T.field(u, 0xa036) == 0
            if stage == 0xf904:
                assert bytes(u.mem_read(sy['probe_read_body_state'], 8)) == bytes(8)
            seen.append(stage)
        if pc == m['symbols']['_vn_rdwr']:
            u.emu_stop()

    u.hook_add(T.U.UC_HOOK_CODE, watch)
    u.emu_start(P.PREVIOUS.PREVIOUS.PREVIOUS.FIRST, 0, count=2000000)
    assert u.reg_read(T.UC_ARM64_REG_PC) == m['symbols']['_vn_rdwr']
    assert seen == [int(k, 16) for k in P.CHECKPOINTS]
    if video:
        assert T.field(u, 0xa034) == 250
        assert T.field(u, 0xa036) == T.field(u, 0xa037) == T.field(u, 0xa038) == 0
        assert T.field(u, 0xa039) == (1 << 64)-1
    else:
        assert all(T.field(u, tag) is None for tag in range(0xa034, 0xa03a))
    return stages


def geometry(raw, m, b, height):
    u = T.machine(raw, m, b'', 0, [], False)
    sy = {k: int(v, 16) for k, v in b['probe']['symbols'].items()}
    args = T.STACK+0x2000
    video = struct.pack('<6Q', T.FB, 1, T.ROW, 1440, height, 32)
    u.mem_write(args+0x28, video)
    u.reg_write(T.UC_ARM64_REG_X20, args)
    u.reg_write(T.UC_ARM64_REG_TTBR0_EL1, T.STACK)
    resume = m['symbols']['_start_first_cpu']+0x30c
    u.hook_add(T.U.UC_HOOK_CODE, lambda u, pc, n, d: u.emu_stop() if pc == resume else None)
    u.emu_start(sy['probe_mmu'], 0, count=10000)
    assert u.reg_read(T.UC_ARM64_REG_PC) == resume
    return struct.unpack('<QQ', u.mem_read(sy['probe_scratch'], 16))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    assert not a.output.exists()
    b = json.loads(a.build.read_text())
    raw = (ROOT/b['candidate']['path']).read_bytes()
    assert b['probe_revision'] in (39,40,41,42,43,44,45,46,47,48,49) and T.B.sha(raw) == b['candidate']['sha256']
    m = T.B.macho(raw)
    checks = []
    for video in (True, False):
        stages = reset(raw, m, b, video)
        checks.append(dict(name='checkpoints-video' if video else 'checkpoints-no-video', passed=True))
    for height in (799, 800, 1039, 1040, 3200):
        actual = geometry(raw, m, b, height)
        assert actual == ((T.FB, T.ROW) if height >= P.MIN_HEIGHT else (0, 0)), (height, actual)
        checks.append(dict(name=f'height-{height}', passed=True))
    old = json.loads((ROOT/'reports/kernel-entry-probe/2026-10-26-v38/build.json').read_text())
    oldraw = (ROOT/old['candidate']['path']).read_bytes()
    assert T.B.sha(oldraw) == old['candidate']['sha256']
    assert geometry(oldraw, T.B.macho(oldraw), old, 800) == (T.FB, T.ROW)
    checks.append(dict(name='old-height-800-negative', passed=True))
    changed = bytearray(raw)
    pc = next(pc for pc, stage in stages.items() if stage == 0xf902)
    at = T.B.backed(m, pc)
    changed[at:at+4] = bytes.fromhex('1f2003d5')
    rejected = False
    try:
        reset(bytes(changed), m, b)
    except AssertionError:
        rejected = True
    assert rejected
    checks.append(dict(name='omitted-checkpoint-negative', passed=True))
    out = dict(candidate_sha256=T.B.sha(raw), source_sha256=T.B.sha((ROOT/'scripts/read_init_sites.py').read_bytes()),
               test_sha256=T.B.sha(Path(__file__).read_bytes()), checks=checks, checkpoints=P.CHECKPOINTS,
               minimum_height=P.MIN_HEIGHT, device_accessed=False,
               limitations=['Software execution; no hardware interrupts, timing or display scanout; not a PROBE30 root-cause proof'])
    a.output.write_text(json.dumps(out, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps(dict(checks=len(checks), passed=True)))


if __name__ == '__main__':
    main()
