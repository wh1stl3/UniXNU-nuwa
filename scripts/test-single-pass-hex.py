"""Compare actual candidate HEX instructions with the shipped revision39 pixels.

Flat software execution: no interrupt, cache, scanout or hardware timing claim.
"""
import argparse
import importlib.util
import json
import struct
import sys
from pathlib import Path
import probe_single_pass_hex as P

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('single_hex_model', ROOT/'scripts/test-read-init.py')
M = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = M
spec.loader.exec_module(M)
T = M.T
VALUES = (0, 0xffffffffffffffff, 0x0123456789abcdef, 0xfedcba9876543210, 0x8000000000000001)


def load(path):
    b = json.loads(path.read_bytes())
    raw = (ROOT/b['candidate']['path']).read_bytes()
    assert T.B.sha(raw) == b['candidate']['sha256']
    m = T.B.macho(raw)
    sy = {k: int(v, 16) for k, v in b['probe']['symbols'].items()}
    start, end = sy['probe_dense_769bf90'], sy['probe_dense_769bf90_replay']
    ins = T.A.disasm(raw, m, start, end-start)
    wanted='x24, #0x6e0' if b['probe_revision']>=43 else 'x23, #0xa037'
    label = next(n for n, i in enumerate(ins) if i.mnemonic == 'mov' and i.op_str == wanted)
    entry = next(i.address for i in reversed(ins[:label]) if i.mnemonic == 'adr' and i.op_str.startswith('x15, '))
    stop = next(i.address for i in ins[label:] if i.mnemonic == 'mov' and i.op_str == 'x23, #0xf902')
    if b['probe_revision']>=43:
        ins+=T.A.disasm(raw,m,sy['probe_hex_shared'],sy['probe_hex_shared_end']-sy['probe_hex_shared'])
    return b, raw, m, sy, entry, stop, ins


def run(data, value, video=True):
    b, raw, m, sy, entry, stop, ins = data
    u = T.machine(raw, m, b'', 0, [], False)
    u.mem_write(sy['probe_scratch'], struct.pack('<QQ', T.FB if video else 0, T.ROW))
    # Nonzero stale pixels include character spacing and every border pixel.
    base = T.FB + 811*T.ROW
    sentinel = b'\xa5'*(22*T.ROW)
    u.mem_write(base, sentinel)
    u.reg_write(T.UC_ARM64_REG_X23, value)
    writes, count = [], [0]
    state_writes = []
    slot = sy.get('probe_hex_delta_cache', 0) + ((1760-1088)//32)*16
    preserved={reg:u.reg_read(reg) for reg in (T.UC_ARM64_REG_SP,T.UC_ARM64_REG_LR,T.UC_ARM64_REG_X20)}
    def watch(u, pc, size, _):
        if pc == stop:
            u.emu_stop()
        else:
            count[0] += 1
    def write(u, access, address, size, value, _):
        if T.STACK<=address<T.STACK+0x20000:return
        if b['probe_revision']>=48 and slot<=address<slot+16:
            assert size==8 and address in (slot,slot+8)
            state_writes.append((address,value & ((1<<64)-1)))
            return
        y, x = divmod(address-T.FB, T.ROW)
        assert 812 <= y < 832 and 1024 <= x and x+size <= 2944, (hex(address), size)
        writes.append((address, size))
    u.hook_add(T.U.UC_HOOK_CODE, watch)
    u.hook_add(T.U.UC_HOOK_MEM_WRITE, write)
    u.emu_start(entry, 0, count=100000)
    assert u.reg_read(T.UC_ARM64_REG_PC) == stop
    assert all(u.reg_read(reg)==value for reg,value in preserved.items())
    image = bytes(u.mem_read(base, len(sentinel)))
    if b['probe_revision']>=48:
        assert state_writes == ([(slot,value),(slot+8,1)] if video else []), state_writes
        assert bytes(u.mem_read(slot,16)) == (struct.pack('<QQ',value,1) if video else bytes(16))
    if not video:
        assert not writes and image == sentinel
    else:
        assert T.field(u, 0xa037) == value
    return image, writes, count[0]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    assert not a.output.exists()
    new = load(a.build)
    old = load(ROOT/'reports/kernel-entry-probe/2026-10-26-v39/build.json')
    assert new[0]['probe_revision'] in (40,41,42,43,44,45,46,47,48,49) and new[0]['single_pass_hex'] == P.plan()
    checks = []
    for value in VALUES:
        old_image, ow, oi = run(old, value)
        new_image, nw, ni = run(new, value)
        assert new_image == old_image
        assert sum(s for _, s in ow) == 64000 and sum(s for _, s in nw) == 38400
        assert len({address+offset for address, size in nw for offset in range(size)}) == 38400
        assert ni < oi
        checks.append(dict(name=f'pixels-{value:016x}', passed=True,
                           old_bytes=64000, new_bytes=38400, old_instructions=oi, new_instructions=ni))
    assert run(new, 0, False)[0] == run(old, 0, False)[0]
    checks.append(dict(name='no-video', passed=True))
    b, raw, m, sy, entry, stop, ins = new
    gap = next(i for i in ins if (b['probe_revision']>=43 or entry < i.address < stop) and i.mnemonic == 'stp'
               and i.op_str == 'wzr, wzr, [x13, #0x18]')
    broken = bytearray(raw)
    at = T.B.backed(m, gap.address)
    broken[at:at+4] = bytes.fromhex('1f2003d5')
    broken_data = (b, bytes(broken), m, sy, entry, stop, ins)
    assert run(broken_data, 0)[0] != run(old, 0)[0]
    checks.append(dict(name='missing-spacing-store-negative', passed=True))
    result = dict(candidate_sha256=T.B.sha(raw), source_sha256=P.plan()['source_sha256'],
                  test_sha256=T.B.sha(Path(__file__).read_bytes()), checks=checks,
                  reference_candidate_sha256=old[0]['candidate']['sha256'],
                  device_accessed=False, hardware_timing_measured=False,
                  limitations=['Flat software memory, no real interrupt delivery or display scanout',
                               'Pixel equivalence and reduced writes do not establish the PROBE31 root cause'])
    a.output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps(dict(checks=len(checks), passed=True)))


if __name__ == '__main__':
    main()
