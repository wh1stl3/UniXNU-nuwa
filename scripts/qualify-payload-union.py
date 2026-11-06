"""Execute iOS16 native union lookup boundaries for future SystemOS composition.

Does not mount a filesystem. Vnode services use explicit model responses.
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
import flush_trace_inputs as trace

sys.path.insert(0, str(trace.R/'out/python-tools'))
import unicorn as U
from unicorn.arm64_const import *

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--work', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
assert not a.output.exists()
raw = (a.work/'kernel.macho').read_bytes()
proof = json.loads((a.work/'kernel-proof.json').read_bytes())
digest = hashlib.sha256(raw).hexdigest()
assert digest == proof['kernel_sha256']
b = trace.builder()
m = b.macho(raw)
bias = 0xfffffff000000000
assert m['symbols']['_lookup_traverse_union'] == bias+0x7441784
assert m['symbols']['_vnode_getwithref'] == bias+0x7443ebc
assert m['symbols']['_vnode_put'] == bias+0x74430e0


def machine():
    u = U.Uc(U.UC_ARCH_ARM64, U.UC_MODE_ARM)
    for page in (0x7441000, 0x7443000):
        u.mem_map(page, 4096)
        off = b.backed(m, page+bias)
        u.mem_write(page, raw[off:off+4096])
    # Runtime BSS canary is an explicit fixture, not file-backed bytes.
    u.mem_map(0x7abd000, 4096)
    u.mem_write(0x7abd760, struct.pack("<Q", 0x12345678))
    u.mem_map(0x1000000, 0x10000)
    u.reg_write(UC_ARM64_REG_SP, 0x1008000)
    return u


upper, mount, lower, nd = 0x1001000, 0x1002000, 0x1003000, 0x1004000
tests = []
for name, errno, has_mount, union, traversal_error, directory, stop in [
    ('other-error', 5, True, True, 0, True, 0x74414fc),
    ('no-mount', 2, False, True, 0, True, 0x7441628),
    ('non-union', 2, True, False, 0, True, 0x7441628),
    ('traverse-error', 2, True, True, 2, True, 0x7441578),
    ('fallback-directory', 2, True, True, 0, True, 0x74412cc),
    ('fallback-nondirectory', 2, True, True, 0, False, 0x7441570),
]:
    u = machine()
    u.mem_write(upper+0xd8, struct.pack('<Q', mount if has_mount else 0))
    u.mem_write(mount+0x70, bytes([0x20 if union else 0]))
    u.mem_write(lower+0x70, struct.pack('<H', 2 if directory else 1))
    for reg, val in [(UC_ARM64_REG_X0, errno), (UC_ARM64_REG_X25, upper),
                     (UC_ARM64_REG_X19, nd), (UC_ARM64_REG_X23, 0x1234)]:
        u.reg_write(reg, val)
    calls = []

    def hook(u, pc, size, _):
        if pc == 0x7441784:
            assert u.reg_read(UC_ARM64_REG_X0) == upper
            assert u.reg_read(UC_ARM64_REG_X2) == 0x1234
            calls.append('traverse')
            u.mem_write(u.reg_read(UC_ARM64_REG_X1), struct.pack('<Q', lower))
            u.reg_write(UC_ARM64_REG_X0, traversal_error)
            u.reg_write(UC_ARM64_REG_PC, u.reg_read(UC_ARM64_REG_LR))
        elif pc == 0x74430e0:
            assert u.reg_read(UC_ARM64_REG_X0) == upper
            calls.append('put-upper')
            u.reg_write(UC_ARM64_REG_PC, u.reg_read(UC_ARM64_REG_LR))
    u.hook_add(U.UC_HOOK_CODE, hook)
    u.emu_start(0x7441330, stop, count=200)
    assert u.reg_read(UC_ARM64_REG_PC) == stop
    expected = ['traverse', 'put-upper'] if errno == 2 and has_mount and union else []
    assert calls == expected
    if expected and not traversal_error:
        assert struct.unpack('<QQ', u.mem_read(nd+0x28, 16)) == (0, lower)
    tests.append(dict(name=name, passed=True, stop=hex(stop+bias), services_modeled=calls))

for failure in (False, True):
    u = machine()
    u.mem_write(upper+0x54, b'\x01')  # VROOT, from actual byte test.
    u.mem_write(upper+0xd8, struct.pack('<Q', mount))
    u.mem_write(mount+0x38, struct.pack('<Q', lower))
    u.mem_write(nd, bytes(8))
    preserved = {getattr(U.arm64_const, 'UC_ARM64_REG_X'+str(i)): i*0x100 for i in range(19, 30)}
    for reg, value in preserved.items():
        u.reg_write(reg, value)
    for reg, value in [(UC_ARM64_REG_X0, upper), (UC_ARM64_REG_X1, nd),
                       (UC_ARM64_REG_X2, 0x1234), (UC_ARM64_REG_LR, 0x100f000)]:
        u.reg_write(reg, value)
    calls = []

    def reference(u, pc, size, _):
        if pc == 0x7443ebc:
            assert u.reg_read(UC_ARM64_REG_X0) == lower
            calls.append('getwithref-lower')
            u.reg_write(UC_ARM64_REG_X0, 5 if failure else 0)
            u.reg_write(UC_ARM64_REG_PC, u.reg_read(UC_ARM64_REG_LR))
    u.hook_add(U.UC_HOOK_CODE, reference)
    u.emu_start(0x7441784, 0x100f000, count=500)
    assert u.reg_read(UC_ARM64_REG_PC) == 0x100f000
    assert u.reg_read(UC_ARM64_REG_X0) == (2 if failure else 0)
    assert u.reg_read(UC_ARM64_REG_SP) == 0x1008000
    assert all(u.reg_read(reg) == value for reg, value in preserved.items())
    assert calls == ['getwithref-lower']
    assert struct.unpack('<Q', u.mem_read(nd, 8))[0] == lower
    tests.append(dict(name='root-reference-failure' if failure else 'root-reference-success', passed=True,
                      services_modeled=calls, output_pointer_requires_success_check=True))

a.output.parent.mkdir(parents=True, exist_ok=True)
a.output.write_text(json.dumps(dict(kernel_sha256=digest, tests=tests, passed=True,
    script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    scope='Native lookup error routing and union root reference handling only; no mount, nonroot traversal, directory enumeration or hardware execution',
    device_accessed=False), indent=2)+'\n')
print('PASS', len(tests), 'native iOS16 union routing/reference cases')
