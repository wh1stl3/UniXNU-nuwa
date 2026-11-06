"""Execute pinned ABL header/AVB size boundaries, without contacting a device.

Debug gates and the partition-size service are modeled. This is not a complete
ABL boot, a flash authorization, or evidence that the failed device used a path.
"""
import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'out/python-tools'))
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm64_const import UC_ARM64_REG_X0, UC_ARM64_REG_X22, UC_ARM64_REG_X23
from unicorn.arm64_const import UC_ARM64_REG_SP, UC_ARM64_REG_LR, UC_ARM64_REG_PC

PE = ROOT / 'out/abl-poweroff-audit/pe-0.bin'
PE_SHA = 'b489faff3f66a415af69b73fe23a59fb9469da0b70aeb4a1792201e22b5bb116'
BACKUPS = Path('D:/Code/PortingiOSLegacy/nuwa/backups/recovery-20261020T121245314787Z')


def header(path):
    with path.open('rb') as stream:
        return stream.read(4096)


def machine(data):
    u = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    u.mem_map(0, 0x200000)
    u.mem_write(0, data)
    u.mem_map(0x400000, 0x20000)
    u.mem_map(0x800000, 0x10000)
    u.reg_write(UC_ARM64_REG_SP, 0x80f000)
    u.reg_write(UC_ARM64_REG_LR, 0x1ff000)
    return u


def main():
    data = PE.read_bytes()
    assert hashlib.sha256(data).hexdigest() == PE_SHA
    stock = header(BACKUPS / 'boot_b.img')
    vendor = header(BACKUPS / 'vendor_boot_b.img')
    init = header(BACKUPS / 'init_boot_b.img')
    c1 = header(ROOT / 'out/persist-c1-r1/boot-persist-c1-r1.img')
    v4 = bytearray(c1)
    struct.pack_into('<I', v4, 20, 1584)
    struct.pack_into('<I', v4, 40, 4)
    cases = [('stock-v4', stock, vendor, 0, 40423424),
             ('persist-c1-v3', c1, vendor, 0, 187707392),
             ('persist-c1-v4-offline-control', bytes(v4), vendor, 0, 187707392),
             ('bad-boot-magic', b'BADMAGIC' + c1[8:], vendor, 0x800000000000000c, None),
             ('bad-vendor-magic', c1, b'BADMAGIC' + vendor[8:], 0x800000000000000c, None)]
    results = []
    for name, boot, vnd, expected, expected_size in cases:
        u = machine(data)
        for address, blob in [(0x400000, boot), (0x404000, vnd), (0x408000, init)]:
            u.mem_write(address, blob)
        for index, value in enumerate([0x400000, 4096, 0x404000, 4096,
                                       0x40c000, 0x40c008, 0, 0x408000]):
            u.reg_write(UC_ARM64_REG_X0 + index, value)

        def hook(uc, address, size, unused):
            if address == 0x18c0:  # Debug output disabled; validation remains native.
                uc.reg_write(UC_ARM64_REG_X0, 0)
                uc.reg_write(UC_ARM64_REG_PC, uc.reg_read(UC_ARM64_REG_LR))
            elif address == 0x119c:
                raise AssertionError('Stack canary failed')

        u.hook_add(UC_HOOK_CODE, hook)
        u.emu_start(0xd330, 0x1ff000, count=100000)
        assert u.reg_read(UC_ARM64_REG_PC) == 0x1ff000
        status = u.reg_read(UC_ARM64_REG_X0)
        actual_size, = struct.unpack('<I', u.mem_read(0x40c000, 4))
        assert status == expected, (name, hex(status))
        if expected_size is not None:
            assert actual_size == expected_size
        results.append(dict(case=name, status=hex(status), actual_size=actual_size))

    lengths = []
    for allow in [0, 1]:
        u = machine(data)
        sp = u.reg_read(UC_ARM64_REG_SP)
        u.mem_write(sp + 0x410, struct.pack('<Q', 47464448))
        u.mem_write(0x400058, struct.pack('<Q', 0x1fe000))
        u.reg_write(UC_ARM64_REG_X22, 0x400000)
        u.reg_write(UC_ARM64_REG_X23, allow)
        calls = []

        def size_hook(uc, address, size, unused):
            if address == 0x1fe000:
                calls.append('get_size_of_partition')
                out = uc.reg_read(UC_ARM64_REG_X0 + 2)
                uc.mem_write(out, struct.pack('<Q', 201326592))
                uc.reg_write(UC_ARM64_REG_X0, 0)
                uc.reg_write(UC_ARM64_REG_PC, uc.reg_read(UC_ARM64_REG_LR))
            elif address == 0x3c3a4:  # Skip only the debug formatting block.
                uc.reg_write(UC_ARM64_REG_PC, 0x3c3cc)

        u.hook_add(UC_HOOK_CODE, size_hook)
        u.emu_start(0x3c2bc, 0x3c3e0, count=1000)
        assert u.reg_read(UC_ARM64_REG_PC) == 0x3c3e0
        count = u.reg_read(UC_ARM64_REG_X0 + 2)
        assert count == (201326592 if allow else 47464448)
        assert len(calls) == allow
        lengths.append(dict(allow=allow, read_bytes=count, calls=calls))
    report = dict(pe_sha256=PE_SHA, header_cases=results, avb_size_cases=lengths,
                  scope='Native instruction boundaries with explicit service models; no full boot',
                  device_accessed=False, failure_cause_confirmed=False)
    output = ROOT / 'reports/persist-c1-r1/trial/partition-boundary-machine.json'
    output.write_text(json.dumps(report, indent=2) + '\n')
    print('PASS: five header cases and two actual AVB size branches; device cause remains unconfirmed')


if __name__ == '__main__':
    main()
