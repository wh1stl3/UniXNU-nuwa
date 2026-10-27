"""Execute real APFS prefix and native uio helpers; verify deferred trace policy.

Stops before vnode_mount. No full APFS, storage, IRQ or userland qualification.
"""
import argparse
import importlib.util
import json
import struct
import sys
from pathlib import Path
import read_grid_sites as P

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('grid_model', ROOT/'scripts/test-read-dispatch-observer.py')
T = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = T
spec.loader.exec_module(T)
B = T.B
MASK = (1 << 64)-1


def setup(raw, b, video=True, foreign=False):
    m = B.macho(raw)
    u = T.machine(raw, m, b'', 0, [], False)
    sy = {k: int(v, 16) for k, v in b['probe']['symbols'].items()}
    vp, uio, ap = T.STACK+0x5000, T.STACK+0x4000, T.SP+8
    u.mem_write(ap, struct.pack('<5Q', 0, vp, uio, 8, T.STACK+0x3000))
    u.reg_write(T.UC_ARM64_REG_X0, ap)
    u.reg_write(T.UC_ARM64_REG_LR, P.BODY.PREVIOUS.DISPATCH+4)
    u.reg_write(T.UC_ARM64_REG_TPIDR_EL1, 0x2222 if foreign else 0x1111)
    u.mem_write(sy['probe_read_state'], struct.pack('<14Q', 1, 0x1111, vp, 0, 0,
                T.STACK+0xf000, 272, P.BODY.ENTRY, 0, 0, 0, 0, 0, 8))
    u.mem_write(sy['probe_scratch'], struct.pack('<QQ', T.FB if video else 0, T.ROW))
    return u, m, sy, uio


def prefix(raw, b, offset=0, video=True, foreign=False, native=False):
    u, m, sy, uio = setup(raw, b, video, foreign)
    u.mem_write(uio+0x18, struct.pack('<Q', offset))
    u.mem_write(uio+0x28, struct.pack('<Q', 0x1000))
    if native:
        original = B.INPUT.read_bytes()
        om = B.macho(original)
        for pc in {P.BODY.ENTRY, *(p['site'] for p in P.BODY.points())}:
            at = B.backed(om, pc)
            u.mem_write(pc, original[at:at+4])
    visited, writes = [], []
    stop = m['symbols']['_vnode_mount']
    def code(u, pc, size, _):
        for name in ('_uio_resid','_uio_offset','_vnode_mount'):
            if pc == m['symbols'][name]:
                visited.append(name)
        if pc == stop:
            u.emu_stop()
    def write(u, access, address, size, value, _):
        if T.FB <= address < T.FB+0x1200000:
            writes.append((address, size))
    u.hook_add(T.U.UC_HOOK_CODE, code)
    u.hook_add(T.U.UC_HOOK_MEM_WRITE, write)
    u.emu_start(P.BODY.ENTRY, 0, count=2000000)
    assert u.reg_read(T.UC_ARM64_REG_PC) == stop
    assert visited == ['_uio_resid','_uio_offset','_vnode_mount']
    snapshot = dict(regs=[u.reg_read(getattr(T, f'UC_ARM64_REG_X{i}')) for i in range(31)],
                    sp=u.reg_read(T.UC_ARM64_REG_SP), nzcv=u.reg_read(T.UC_ARM64_REG_NZCV),
                    native_saved_frame=bytes(u.mem_read(T.SP-0x60, 0x60)).hex())
    assert u.reg_read(T.UC_ARM64_REG_X23) == 0x1000
    assert u.reg_read(T.UC_ARM64_REG_X25) == offset
    if b['probe_revision'] >= 41 and not native:
        trace = struct.unpack('<QQ', u.mem_read(sy['probe_read_trace_state'], 16))
        assert trace == ((0, MASK) if foreign else (P.BODY.ENTRY+0x48, offset)), trace
        assert T.field(u, 0xa038) is None and T.field(u, 0xa039) is None
        for idx in range(276, 283):
            x, y = 832+(idx-276)*48, 808
            actual = struct.unpack('<I', u.mem_read(T.FB+y*T.ROW+x*4, 4))[0]
            want = 0xff40c0ff if idx in (278,280,282) else 0xff40ff80
            assert actual == (want if video and not foreign else 0), (idx, actual)
    return snapshot, sum(size for _, size in writes)


def ret_case(raw, b, active=True):
    u, m, sy, _ = setup(raw, b)
    u.mem_write(sy['probe_read_trace_state'], struct.pack('<QQ', 0x1234, 0x1000))
    if not active:
        u.mem_write(sy['probe_read_state'], bytes(8))
    stop = P.BODY.PREVIOUS.DISPATCH+4
    u.hook_add(T.U.UC_HOOK_CODE, lambda u, pc, n, d: u.emu_stop() if pc == stop else None)
    u.emu_start(P.RET, 0, count=2000000)
    assert u.reg_read(T.UC_ARM64_REG_PC) == stop
    assert (T.field(u,0xa038),T.field(u,0xa039)) == ((P.RET,0x1000) if active else (None,None))


def reset(raw, b):
    u, m, sy, _ = setup(raw,b)
    u.mem_write(sy['probe_read_trace_state'], b'\xa5'*16)
    stop = m['symbols']['_vn_rdwr']
    u.hook_add(T.U.UC_HOOK_CODE, lambda u, pc, n, d: u.emu_stop() if pc == stop else None)
    u.emu_start(P.FIRST, 0, count=2000000)
    assert u.reg_read(T.UC_ARM64_REG_PC) == stop
    assert struct.unpack('<QQ',u.mem_read(sy['probe_read_trace_state'],16)) == (0,MASK)
    assert T.field(u,0xa038) == 0 and T.field(u,0xa039) == MASK


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    assert not a.output.exists()
    b=json.loads(a.build.read_bytes());raw=(ROOT/b['candidate']['path']).read_bytes()
    assert b['probe_revision'] in (41,42,43,44,45,46,47,48,49) and B.sha(raw)==b['candidate']['sha256'] and b['read_grid']==P.plan()
    checks=[]
    for name,offset,video,foreign in (('prefix-zero',0,True,False),('prefix-offset',0x123456789,True,False),
                                     ('prefix-no-video',0,False,False),('prefix-foreign-thread',0,True,True)):
        actual, writes=prefix(raw,b,offset,video,foreign)
        expected,_=prefix(raw,b,offset,video,foreign,True)
        assert actual==expected
        checks.append(dict(name=name,passed=True,framebuffer_bytes=writes))
    old=json.loads((ROOT/'reports/kernel-entry-probe/2026-10-26-v40/build-qualified.json').read_bytes())
    oldraw=(ROOT/old['candidate']['path']).read_bytes();assert B.sha(oldraw)==old['candidate']['sha256']
    oldstate,oldbytes=prefix(oldraw,old)
    newstate,newbytes=prefix(raw,b)
    assert oldstate==newstate and newbytes<oldbytes//4
    checks.append(dict(name='prefix-write-reduction',passed=True,old_bytes=oldbytes,new_bytes=newbytes))
    for active in (True,False):
        ret_case(raw,b,active);checks.append(dict(name='ret-flush' if active else 'ret-inactive',passed=True))
    reset(raw,b);checks.append(dict(name='header-reset',passed=True))
    m=B.macho(raw);sy=b['probe']['symbols'];start=int(sy['probe_dense_51a58a0'],16);end=int(sy['probe_dense_51a58a0_replay'],16)
    store=next(i for i in T.A.disasm(raw,m,start,end-start) if i.mnemonic=='str' and i.op_str=='x23, [x14]')
    changed=bytearray(raw);at=B.backed(m,store.address);changed[at:at+4]=bytes.fromhex('1f2003d5')
    rejected=False
    try:prefix(bytes(changed),b)
    except AssertionError:rejected=True
    assert rejected
    checks.append(dict(name='missing-buffer-store-negative',passed=True))
    out=dict(candidate_sha256=B.sha(raw),source_sha256=P.plan()['source_sha256'],test_sha256=B.sha(Path(__file__).read_bytes()),
             checks=checks,device_accessed=False,complete_filesystem_body_executed=False,
             native_helpers_executed=['uio_resid','uio_offset'],stop_before='vnode_mount',
             limitations=['Flat software model; no hardware IRQ, timing or scanout','Native RET flush is a separate fixture, not evidence of a completed real read'])
    a.output.write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(checks=len(checks),passed=True,old_prefix_bytes=oldbytes,new_prefix_bytes=newbytes)))


if __name__=='__main__':main()
