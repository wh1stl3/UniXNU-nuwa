"""Execute fixed native UIO/VFS instructions with explicit allocator/handler fixtures.

Allocators and filesystem handler bodies do not execute. No runtime health,
filesystem IO, lock progress or hardware qualification follows from this test.
"""
import argparse, importlib.util, json, struct, sys
from pathlib import Path
import read_dispatch_audit as A

spec = importlib.util.spec_from_file_location('dispatch_fixture', Path(__file__).with_name('test-read-dispatch-observer.py'))
T = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = T
spec.loader.exec_module(T)


def run(raw, m, offset, length):
    u = T.machine(raw, m, b'', 0, [], False)
    sy = m['symbols']; obj = T.STACK + 0x2000; iov = T.STACK + 0x3000
    buffer = T.STACK + 0x4000; calls = []; reached = []
    def watch(u, pc, size, data):
        if pc == T.STOP:
            reached.append('return'); u.emu_stop(); return
        if pc in (sy['_kalloc_type_impl_internal'], sy['_kalloc_ext']):
            args = [u.reg_read(getattr(T, 'UC_ARM64_REG_X' + str(n))) for n in range(4)]
            calls.append(dict(target=hex(pc), args=[hex(x) for x in args]))
            address = obj if pc == sy['_kalloc_type_impl_internal'] else iov
            # Explicit zeroed allocation fixtures, not execution of allocator bodies.
            u.mem_write(address, bytes(0x100))
            u.reg_write(T.UC_ARM64_REG_X0, address)
            u.reg_write(T.UC_ARM64_REG_PC, u.reg_read(T.UC_ARM64_REG_LR))
    u.hook_add(T.U.UC_HOOK_CODE, watch)
    for n, value in enumerate((1, offset, 2, 0)):
        u.reg_write(getattr(T, 'UC_ARM64_REG_X' + str(n)), value)
    u.emu_start(sy['_uio_create'], 0, count=10000)
    assert reached == ['return'] and len(calls) == 2
    assert int(calls[0]['args'][1], 16) == 0x8004
    assert int(calls[1]['args'][1], 16) == 16
    assert int(calls[1]['args'][2], 16) & 0xffff == 4
    assert u.reg_read(T.UC_ARM64_REG_X0) == obj
    assert struct.unpack('<QQ', u.mem_read(obj, 16)) == (iov, iov)
    assert struct.unpack('<I', u.mem_read(obj + 0x10, 4))[0] == 1
    assert struct.unpack('<Q', u.mem_read(obj + 0x18, 8))[0] == offset
    assert struct.unpack('<II', u.mem_read(obj + 0x20, 8)) == (2, 0)
    assert struct.unpack('<I', u.mem_read(obj + 0x30, 4))[0] == 3
    reached.clear(); u.reg_write(T.UC_ARM64_REG_LR, T.STOP)
    for n, value in enumerate((obj, buffer, length)):
        u.reg_write(getattr(T, 'UC_ARM64_REG_X' + str(n)), value)
    u.emu_start(sy['_uio_addiov'], 0, count=10000)
    assert reached == ['return'] and u.reg_read(T.UC_ARM64_REG_X0) == 0
    assert struct.unpack('<QQ', u.mem_read(iov, 16)) == (buffer, length)
    assert struct.unpack('<Q', u.mem_read(obj + 0x28, 8))[0] == length
    assert u.reg_read(T.UC_ARM64_REG_SP) == T.SP
    before = bytes(u.mem_read(obj, 0x38)) + bytes(u.mem_read(iov, 16))
    reached.clear(); u.reg_write(T.UC_ARM64_REG_LR, T.STOP)
    for n, value in enumerate((obj, buffer + 16, 1)):
        u.reg_write(getattr(T, 'UC_ARM64_REG_X' + str(n)), value)
    u.emu_start(sy['_uio_addiov'], 0, count=10000)
    assert reached == ['return'] and u.reg_read(T.UC_ARM64_REG_W0) == 0xffffffff
    assert bytes(u.mem_read(obj, 0x38)) + bytes(u.mem_read(iov, 16)) == before
    reached.clear(); u.reg_write(T.UC_ARM64_REG_LR, T.STOP); u.reg_write(T.UC_ARM64_REG_X0, 0)
    u.emu_start(sy['_uio_addiov'], 0, count=10000)
    assert reached == ['return'] and u.reg_read(T.UC_ARM64_REG_W0) == 0xffffffff
    return dict(offset=offset, length=length, allocator_calls=calls,
                uio=bytes(u.mem_read(obj, 0x38)).hex(), iovec=bytes(u.mem_read(iov, 16)).hex(),
                full_iovec_rejected_without_mutation=True, null_uio_rejected=True, passed=True)


def vfs(raw, m):
    u = T.machine(raw, m, b'', 0, [], False); sy = m['symbols']; reached = []
    def stop(u, pc, size, data):
        if pc == T.STOP:
            reached.append('return'); u.emu_stop()
    u.hook_add(T.U.UC_HOOK_CODE, stop)
    u.emu_start(sy['_vfs_op_init'], 0, count=100000)
    assert reached == ['return']
    index = struct.unpack('<i', u.mem_read(sy['_vnop_getxattr_desc'], 4))[0]
    assert 0 < index < 256
    vp = T.STACK + 0x1000; ops = T.STACK + 0x2000; handler = T.STACK + 0x3000
    name = T.STACK + 0x4000; uio = T.STACK + 0x5000; sizep = T.STACK + 0x6000; context = T.STACK + 0x7000
    u.mem_write(vp + 0xd0, struct.pack('<Q', ops)); u.mem_write(ops + index * 8, struct.pack('<Q', handler))
    u.mem_write(name, b'com.apple.ResourceFork\0'); captured = []
    def dispatch(u, pc, size, data):
        if pc == handler:
            arg = u.reg_read(T.UC_ARM64_REG_X0)
            observed = bytes(u.mem_read(arg, 0x38))
            expected = struct.pack('<5QI4xQ', sy['_vnop_getxattr_desc'], vp, name, uio, sizep, 0x20, context)
            assert observed == expected
            captured.append(observed.hex())
            # Return an explicit errno fixture; no APFS body executed.
            u.reg_write(T.UC_ARM64_REG_X0, 0x5d)
            u.reg_write(T.UC_ARM64_REG_PC, u.reg_read(T.UC_ARM64_REG_LR))
    u.hook_add(T.U.UC_HOOK_CODE, dispatch); reached.clear(); u.reg_write(T.UC_ARM64_REG_LR, T.STOP)
    for n, value in enumerate((vp, name, uio, sizep, 0x20, context)):
        u.reg_write(getattr(T, 'UC_ARM64_REG_X' + str(n)), value)
    u.emu_start(sy['_VNOP_GETXATTR'], 0, count=10000)
    assert reached == ['return'] and len(captured) == 1
    assert u.reg_read(T.UC_ARM64_REG_X0) == 0x5d and u.reg_read(T.UC_ARM64_REG_SP) == T.SP
    return dict(simulated_descriptor_index=index, runtime_index_known=False, handler_arguments=captured[0], fixture_errno=0x5d, passed=True)


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output', type=Path, required=True); a = p.parse_args()
    dest = a.output.resolve()
    if dest.exists() or not dest.is_relative_to(A.ROOT / 'reports'):
        raise ValueError('Fresh reports output required')
    raw, m, origin = A.audit()
    result = dict(input_sha256=A.B.sha(raw), script_sha256=A.B.sha(Path(__file__).read_bytes()),
                  cases=[run(raw, m, off, length) for off, length in ((264, 8), (336, 23707), (384, 33021))],
                  vfs=vfs(raw, m), device_accessed=False, kernel_modified=False,
                  limitations=['Allocator returns and filesystem handler are fixtures; bodies do not execute',
                               'VFS initialization executes only in Unicorn; live descriptor index and v_op unknown',
                               'Not QEMU, hardware, timer, memory-pressure, lock, DMA or filesystem qualification'])
    dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(json.dumps(result, indent=2).encode() + b'\n')
    print(json.dumps(dict(cases=len(result['cases']), vfs=result['vfs'], passed=True)))


if __name__ == '__main__':
    main()
