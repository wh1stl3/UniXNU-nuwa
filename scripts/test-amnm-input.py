#!/usr/bin/env python3
"""Execute Mach-O INPUT hook bytes with explicitly modelled LDADDAL only."""
import argparse
import struct
import subprocess

from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm64_const import UC_ARM64_REG_SP, UC_ARM64_REG_NZCV, UC_ARM64_REG_PC
import unicorn.arm64_const as arm

CODE, LOG, STACK = 0x100000, 0x200000, 0x300000
SP, END, REF = STACK + 0x2000, CODE + 0x1000, CODE + 0x1800
REGS = [getattr(arm, 'UC_ARM64_REG_X%d' % i) for i in range(31)]

def text_section(data):
    assert struct.unpack_from('<I', data, 0)[0] == 0xfeedfacf
    ncmds = struct.unpack_from('<I', data, 16)[0]
    p = 32
    for _ in range(ncmds):
        cmd, size = struct.unpack_from('<II', data, p)
        if cmd == 0x19:
            nsects = struct.unpack_from('<I', data, p + 64)[0]
            for i in range(nsects):
                s = p + 72 + i * 80
                if data[s:s+16].rstrip(b'\0') == b'__text':
                    length = struct.unpack_from('<Q', data, s + 40)[0]
                    offset = struct.unpack_from('<I', data, s + 48)[0]
                    return bytearray(data[offset:offset+length])
        p += size
    raise ValueError('missing text')

def u32(code, off):
    return struct.unpack_from('<I', code, off)[0]

def put32(code, off, word):
    struct.pack_into('<I', code, off, word)

def run(code, value, flags, ticket, seed, reference=False):
    uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    for address, size in ((CODE, 0x3000), (LOG, 0x1000), (STACK, 0x4000)):
        uc.mem_map(address, size)
    uc.mem_write(CODE, bytes(code))
    uc.mem_write(REF, struct.pack('<II', 0x7100011f, 0x14000000 | ((END - (REF + 4)) // 4 & 0x3ffffff)))
    uc.mem_write(STACK, bytes([0xa5]) * 0x4000)
    uc.mem_write(LOG, bytes([0x5a]) * 0x1000)
    uc.mem_write(LOG, struct.pack('<Q', ticket))
    caller_fp, caller_lr = 0x8123456789abcdef, 0xfedcba9876543210
    uc.mem_write(SP + 0x30, struct.pack('<QQ', caller_fp, caller_lr))
    values = [((seed + 1) << 56) | (0x1020304050600 + i * 0x111111111) for i in range(31)]
    values[8] = 0xabcdefff00000000 | value
    for reg, val in zip(REGS, values):
        uc.reg_write(reg, val)
    uc.reg_write(UC_ARM64_REG_SP, SP)
    uc.reg_write(UC_ARM64_REG_NZCV, flags)
    atomics = []
    def intercept(emu, address, size, unused):
        if address == CODE + 0x58:
            assert not reference
            assert emu.reg_read(REGS[9]) == LOG and emu.reg_read(REGS[10]) == 1
            old = struct.unpack('<Q', emu.mem_read(LOG, 8))[0]
            emu.mem_write(LOG, struct.pack('<Q', (old + 1) & 0xffffffffffffffff))
            emu.reg_write(REGS[11], old)
            emu.reg_write(UC_ARM64_REG_PC, address + 4)
            atomics.append(old)
    uc.hook_add(UC_HOOK_CODE, intercept)
    uc.emu_start(REF if reference else CODE, END, count=500)
    assert uc.reg_read(UC_ARM64_REG_PC) == END
    regs = [uc.reg_read(reg) for reg in REGS]
    assert regs == values and uc.reg_read(UC_ARM64_REG_SP) == SP
    assert bytes(uc.mem_read(STACK, 0x2000 - 272)) == bytes([0xa5]) * (0x2000 - 272)
    assert bytes(uc.mem_read(SP, 0x30)) == bytes([0xa5]) * 0x30
    assert bytes(uc.mem_read(SP + 0x40, 0x1fc0)) == bytes([0xa5]) * 0x1fc0
    assert bytes(uc.mem_read(SP + 0x30, 16)) == struct.pack('<QQ', caller_fp, caller_lr)
    if not reference:
        assert atomics == [ticket]
        log = bytes(uc.mem_read(LOG, 0x1000))
        assert struct.unpack_from('<Q', log)[0] == ticket + 1
        expected = bytearray([0x5a] * 0x1000)
        struct.pack_into('<Q', expected, 0, ticket + 1)
        if ticket < 16:
            off = 128 + 96 * ticket
            struct.pack_into('<9Q', expected, off, ticket + 1, 3, value, values[21], values[19], SP, values[29], caller_fp, caller_lr)
        assert log == expected
    return regs, uc.reg_read(UC_ARM64_REG_SP), uc.reg_read(UC_ARM64_REG_NZCV)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('object')
    args = parser.parse_args()
    dis = subprocess.check_output(['llvm-objdump', '-dr', '--mattr=+lse', args.object], text=True)
    for item in ('ldaddal\tx10, x11, [x9]', 'stlr\tx11, [x12]', 'ARM64_RELOC_PAGE21\t_amnm_observer_log', 'ARM64_RELOC_PAGEOFF12\t_amnm_observer_log', 'ARM64_RELOC_BRANCH26\t_amnm_input_continue'):
        assert item in dis, item
    code = text_section(open(args.object, 'rb').read())
    assert len(code) >= 0xf8
    assert u32(code, 0x4c) == 0x90000009 and u32(code, 0x50) == 0x91000129
    assert u32(code, 0x58) == 0xf8ea012b  # real LDADDAL encoding
    assert u32(code, 0xa0) == 0xc89ffd8b and u32(code, 0xf0) == 0x7100011f
    assert u32(code, 0xf4) == 0x14000000
    pages = (LOG - CODE) // 4096
    put32(code, 0x4c, 0x90000009 | ((pages & 3) << 29) | ((pages >> 2) << 5))
    put32(code, 0xf4, 0x14000000 | ((END - (CODE + 0xf4)) // 4 & 0x3ffffff))
    cases = 0
    for value in (0, 1, 0xffffffff):
        for flags in (0, 0x20000000, 0x60000000, 0xf0000000):
            for ticket in (0, 15, 16, 31):
                for seed in (0, 1):
                    assert run(code, value, flags, ticket, seed) == run(code, value, flags, ticket, seed, True)
                    cases += 1
    print('PASS %d cases; LDADDAL explicitly modelled, all other hook instructions executed by Unicorn' % cases)

if __name__ == '__main__':
    main()
