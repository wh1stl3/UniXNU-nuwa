"""Execute the carrier's LP64 VFS/APFS copyin boundaries, not a mount."""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'out/python-tools'))
import flush_trace_inputs as trace
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm64_const import *

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--work',type=Path,required=True)
parser.add_argument('--payload',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
assert not args.output.exists()
raw=(args.work/'kernel.macho').read_bytes()
proof=json.loads((args.work/'kernel-proof.json').read_bytes())
assert hashlib.sha256(raw).hexdigest()==proof['kernel_sha256']
serialized=args.payload.read_bytes()
assert len(serialized)==0x150 and struct.unpack_from('<Q',serialized)[0]==0x10160

B = trace.builder()
m = B.macho(raw)
bias = 0xfffffff000000000
stack, user = 0x1000000, 0x10200
cases = []

def check(vfs_error=0, apfs_error=0):
    u = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    pages = set()
    def region(va, size):
        off = B.backed(m, va, size)
        address = va-bias
        for page in range(address & ~4095, (address+size+4095) & ~4095, 4096):
            if page not in pages:
                u.mem_map(page, 4096)
                pages.add(page)
        u.mem_write(address, raw[off:off+size])
    region(0xfffffff007450d9c, 0x30)
    region(0xfffffff007450f74, 0x10)
    region(0xfffffff0051d133c, 0x18)
    for target in (0xfffffff00797217c, 0xfffffff00525e700, 0xfffffff0074692c4):
        region(target, 4)
    u.mem_map(stack, 4096)
    u.mem_map(user & ~4095, 4096)
    payload = bytearray(serialized)
    u.mem_write(user, bytes(payload))
    u.mem_write(stack, bytes([0xa5])*4096)
    u.mem_write(stack+0x58, struct.pack('<Q', user))
    u.reg_write(UC_ARM64_REG_SP, stack)
    calls = []
    def hook(uc, address, size, data):
        if address == 0xfffffff0074692c4-bias:
            assert uc.reg_read(UC_ARM64_REG_X2) == user+8
            uc.emu_stop()
        elif address in (0xfffffff00797217c-bias, 0xfffffff00525e700-bias):
            src, dst, n = (uc.reg_read(r) for r in (UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X2))
            first = address == 0xfffffff00797217c-bias
            assert (src, n) == ((user, 8) if first else (user+8, 0x144))
            error = vfs_error if first else apfs_error
            calls.append(dict(source_offset=src-user, bytes=n, error=error))
            if not error:
                uc.mem_write(dst, bytes(uc.mem_read(src, n)))
            uc.reg_write(UC_ARM64_REG_X0, error)
            uc.reg_write(UC_ARM64_REG_PC, uc.reg_read(UC_ARM64_REG_LR))
    u.hook_add(UC_HOOK_CODE, hook)
    stop = 0xfffffff0074513ac if vfs_error else 0xfffffff007450dc4
    u.emu_start(0xfffffff007450d9c-bias, stop-bias, count=30)
    forwarded = struct.unpack('<Q', u.mem_read(stack+0x58, 8))[0]
    assert forwarded == user+(0 if vfs_error else 8)
    if not vfs_error:
        assert struct.unpack('<Q', u.mem_read(stack+0x60, 8))[0] == 0x10160
        u.emu_start(0xfffffff007450f74-bias, 0xfffffff007450f84-bias, count=12)
        u.reg_write(UC_ARM64_REG_X23, forwarded)
        u.emu_start(0xfffffff0051d133c-bias, 0xfffffff0051d1350-bias, count=15)
        assert struct.unpack('<I', u.mem_read(stack+0xd4, 4))[0] == apfs_error
        expected = bytes([0xa5])*0x144 if apfs_error else bytes(payload[8:0x14c])
        assert bytes(u.mem_read(stack+0x340, 0x144)) == expected
        assert bytes(u.mem_read(stack+0x484, 4)) == bytes([0xa5])*4
    cases.append(dict(vfs_error=vfs_error, apfs_error=apfs_error, calls=calls))

check()
check(vfs_error=14)
check(apfs_error=14)
report = dict(passed=True, kernel_sha256=hashlib.sha256(raw).hexdigest(), cases=cases,
              vfs_prefix_bytes=8, apfs_prefix_bytes=0x144, total_consumed_bytes=0x14c,
              allocation_bytes=0x150, physical_io=False, mount_executed=False,
              scope='Actual instruction snippets; synthetic copyin and VFS dispatch. No complete filesystem execution.')
report['payload_sha256']=hashlib.sha256(serialized).hexdigest()
report['source_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
output=args.output
output.parent.mkdir(parents=True,exist_ok=True)
output.write_text(json.dumps(report, indent=2)+'\n')
print('PASS', len(cases), 'actual VFS/APFS argument boundary cases; no mount execution')
