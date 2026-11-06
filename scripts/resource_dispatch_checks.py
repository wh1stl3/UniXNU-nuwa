"""Unicorn differential checks for dispatch observers; handler bodies are fixtures."""
import hashlib, struct
from pathlib import Path
import resource_dispatch_sites as P

MODES = ('normal', 'no-video', 'foreign-thread', 'foreign-frame', 'wrong-target',
         'inactive', 'outer-unpaired', 'parent-unpaired', 'resource-inactive',
         'resource-frame', 'resource-lr', 'null-result', 'wrong-wrapper-lr',
         'vnop-unpaired', 'dispatch-inactive', 'dispatch-frame')


def required_names():
    return {f'dispatch:{p["site"]:#x}:{mode}' for p in P.points() for mode in MODES} | {
        'dispatch-header-reset', 'dispatch-missing-vnop-gate-negative',
        *(f'dispatch-wrapper-{target}-{errno}' for target in range(2) for errno in (0, 93))}


def setup(M, raw, b, p, mode):
    special = ('wrong-wrapper-lr', 'vnop-unpaired', 'dispatch-inactive', 'dispatch-frame')
    q = next(q for q in P.R.points() if q['site'] == P.R.ENTRY + 0x70)
    u, m, sy, state, own = M.resource_setup(raw, b, q, 'normal' if mode in special else mode)
    T = M.T; wrapper = T.STACK + 0x8800; resource = T.STACK + 0x9800
    u.mem_write(wrapper, struct.pack('<QQ', resource, P.HELPER_RETURN + (4 if mode == 'wrong-wrapper-lr' else 0)))
    u.reg_write(T.UC_ARM64_REG_X29, wrapper); u.reg_write(T.UC_ARM64_REG_SP, wrapper - 0x50)
    u.reg_write(T.UC_ARM64_REG_LR, P.HELPER_RETURN); u.reg_write(T.UC_ARM64_REG_X8, T.STOP)
    dispatch = [wrapper + (16 if mode == 'dispatch-frame' else 0), 0 if mode == 'dispatch-inactive' else 1]
    u.mem_write(sy['probe_resource_dispatch_state'], struct.pack('<2Q', *dispatch))
    if mode == 'vnop-unpaired':
        own[1] &= ~4; u.mem_write(sy['probe_resource_state'], struct.pack('<4Q', *own))
    return u, m, sy, state, own, dispatch


def execute(M, raw, b, p, mode, original, om):
    T, B, site = M.T, M.B, p['site']
    ref, _, _, _, _, _ = setup(M, raw, b, p, mode)
    at = B.backed(om, site); ref.mem_write(site, original[at:at+4]); ref.emu_start(site, 0, count=1)
    expected = M.D.snapshot(ref)
    u, _, sy, state, own, dispatch = setup(M, raw, b, p, mode); writes = []
    u.hook_add(T.U.UC_HOOK_MEM_WRITE, lambda u, a, pos, n, v, d: writes.append((pos, n)) if T.FB <= pos < T.FB+0x1200000 else None)
    u.hook_add(T.U.UC_HOOK_CODE, lambda u, pc, n, d: u.emu_stop() if pc == expected['pc'] else None)
    u.emu_start(site, 0, count=3000000)
    assert M.D.snapshot(u) == expected, (hex(site), mode, 'native state')
    hit = mode in ('normal', 'no-video') or site == P.CALL and mode in ('dispatch-inactive', 'dispatch-frame')
    if hit:
        state[4:6] = [site, T.STOP if site == P.CALL else 0x11223344]
        dispatch = [T.STACK+0x8800, 1] if site == P.CALL else [dispatch[0], 0]
    assert list(struct.unpack('<8Q', u.mem_read(sy['probe_result_state'], 64))) == state, (hex(site), mode, 'result')
    assert list(struct.unpack('<4Q', u.mem_read(sy['probe_resource_state'], 32))) == own
    assert list(struct.unpack('<2Q', u.mem_read(sy['probe_resource_dispatch_state'], 16))) == dispatch
    for pos, n in writes:
        y, x = divmod(pos-T.FB, T.ROW)
        assert (980 <= y < 1000 or 1008 <= y < 1028) and 1024 <= x and x+n <= 2944
    assert sum(n for _, n in writes) == (76800 if hit and mode != 'no-video' else 0)
    if hit and mode != 'no-video':
        assert T.field(u, 0xa03d) == state[4] and T.field(u, 0xa03e) == state[5]
    return dict(name=f'dispatch:{site:#x}:{mode}', passed=True)


def wrapper(M, raw, b, original, om, target_number, errno, native):
    T, B = M.T, M.B
    u, m, sy, _, _, _ = setup(M, raw, b, P.points()[0], 'normal')
    if native:
        for p in P.points():
            at = B.backed(om, p['site']); u.mem_write(p['site'], original[at:at+4])
    resource = T.STACK+0x9800
    u.reg_write(T.UC_ARM64_REG_X29, resource); u.reg_write(T.UC_ARM64_REG_SP, resource-0x70)
    vnode, ops, name, uio, sizep, context = (T.STACK+x for x in (0x1000, 0x2000, 0x3000, 0x4000, 0x5000, 0x6000))
    target = m['symbols'][('_uio_create', '_uio_free')[target_number]]
    desc = m['symbols']['_vnop_getxattr_desc']; index = 51
    u.mem_write(desc, struct.pack('<i', index)); u.mem_write(vnode+0xd0, struct.pack('<Q', ops))
    u.mem_write(ops+index*8, struct.pack('<Q', target)); captures=[]; returned=[]
    args = (vnode, name, uio, sizep, 0x20, context)
    for n, value in enumerate(args): u.reg_write(getattr(T, 'UC_ARM64_REG_X'+str(n)), value)
    u.reg_write(T.UC_ARM64_REG_LR, P.HELPER_RETURN)
    def watch(u, pc, n, d):
        if pc == target:
            assert u.reg_read(T.UC_ARM64_REG_LR) == P.AFTER
            arg = u.reg_read(T.UC_ARM64_REG_X0)
            expected = struct.pack('<5QI4xQ', desc, vnode, name, uio, sizep, 0x20, context)
            assert bytes(u.mem_read(arg, 0x38)) == expected
            if not native:
                assert struct.unpack('<2Q', u.mem_read(sy['probe_result_state']+32, 16)) == (P.CALL, target)
            captures.append(expected)
            u.reg_write(T.UC_ARM64_REG_X0, errno)
            u.reg_write(T.UC_ARM64_REG_PC, P.AFTER)
        if pc == P.HELPER_RETURN:
            returned.append(pc); u.emu_stop()
    u.hook_add(T.U.UC_HOOK_CODE, watch)
    u.emu_start(m['symbols']['_VNOP_GETXATTR'], 0, count=5000000)
    assert len(captures) == len(returned) == 1
    if not native:
        assert struct.unpack('<2Q', u.mem_read(sy['probe_result_state']+32, 16)) == (P.AFTER, errno)
        assert struct.unpack('<Q', u.mem_read(sy['probe_resource_dispatch_state']+8, 8))[0] == 0
    assert u.reg_read(T.UC_ARM64_REG_X0) == errno
    return M.D.snapshot(u), captures


def run(M, raw, b, original, om):
    checks = [execute(M, raw, b, p, mode, original, om) for p in P.points() for mode in MODES]
    for target in range(2):
        for errno in (0, 93):
            assert wrapper(M, raw, b, original, om, target, errno, False) == wrapper(M, raw, b, original, om, target, errno, True)
            checks.append(dict(name=f'dispatch-wrapper-{target}-{errno}', passed=True))
    T = M.T
    u, m, sy, _, _, _ = setup(M, raw, b, P.points()[0], 'normal')
    u.mem_write(sy['probe_resource_dispatch_state'], b'\xa5'*16)
    stop = m['symbols']['_vn_rdwr']
    u.hook_add(T.U.UC_HOOK_CODE, lambda u, pc, n, d: u.emu_stop() if pc == stop else None)
    u.emu_start(P.R.D.PREVIOUS.DECOMP.PREVIOUS.FIRST, 0, count=4000000)
    assert u.reg_read(T.UC_ARM64_REG_PC) == stop and bytes(u.mem_read(sy['probe_resource_dispatch_state'], 16)) == bytes(16)
    checks.append(dict(name='dispatch-header-reset', passed=True))
    symbols = {k:int(v,16) for k,v in b['probe']['symbols'].items()}
    start = symbols[f'probe_dense_{P.CALL&0xffffffff:x}']; end = symbols[f'probe_dense_{P.CALL&0xffffffff:x}_replay']
    ins = [i for i in T.A.disasm(raw, M.B.macho(raw), start, end-start) if i.mnemonic == 'tbz' and i.op_str.startswith('w10, #2,')][-1]
    bad = bytearray(raw); at=M.B.backed(M.B.macho(raw), ins.address); bad[at:at+4]=bytes.fromhex('1f2003d5')
    rejected=False
    try: execute(M, bytes(bad), b, P.points()[0], 'vnop-unpaired', original, om)
    except AssertionError: rejected=True
    assert rejected
    checks.append(dict(name='dispatch-missing-vnop-gate-negative', passed=True))
    assert {c['name'] for c in checks} == required_names()
    return checks


def source_sha256():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
