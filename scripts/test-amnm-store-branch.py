#!/usr/bin/env python3
"""Execute real STORE/BRANCH Mach-O text; model only the LSE fetch-add."""
import importlib.util
import struct
import subprocess
import sys
from pathlib import Path
from unicorn import Uc, UcError, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.arm64_const import UC_ARM64_REG_SP, UC_ARM64_REG_NZCV, UC_ARM64_REG_PC

spec = importlib.util.spec_from_file_location('input_test', Path(__file__).with_name('test-amnm-input.py'))
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
CODE, LOG, STACK, SP, REGS = base.CODE, base.LOG, base.STACK, base.SP, base.REGS
STORE, BRANCH, ATOMIC_STORE, ATOMIC_BRANCH = 0xf8, 0x1f0, 0x150, 0x248
TARGET, ZERO, NONZERO, CONT, REF = 0x400080, CODE+0x1000, CODE+0x1100, CODE+0x1200, CODE+0x1800

def branch(src, dst):
    return 0x14000000 | (((dst-src)//4) & 0x3ffffff)

def prepare(path):
    dis = subprocess.check_output(['llvm-objdump', '-dr', '--mattr=+lse', path], text=True)
    for symbol in ('_amnm_store_continue', '_amnm_branch_zero', '_amnm_branch_nonzero'):
        assert 'ARM64_RELOC_BRANCH26\t' + symbol in dis
    assert dis.count('ARM64_RELOC_PAGE21\t_amnm_observer_log') == 5
    assert dis.count('ARM64_RELOC_PAGEOFF12\t_amnm_observer_log') == 5
    code = base.text_section(Path(path).read_bytes())
    for off in (ATOMIC_STORE, ATOMIC_BRANCH):
        assert base.u32(code, off) == 0xf8ea012b
    assert base.u32(code, 0x154) == 0x39000268
    assert base.u32(code, 0x19c) == base.u32(code, 0x280) == 0xc89ffd8b
    assert base.u32(code, 0x2d0) == 0x34000048
    for off in (0x144, 0x23c):
        assert base.u32(code, off) == 0x90000009
        pages = (LOG-CODE)//4096
        base.put32(code, off, 0x90000009 | ((pages & 3)<<29) | ((pages>>2)<<5))
    for off, dst in ((0x1ec, CONT), (0x2d4, NONZERO), (0x2d8, ZERO)):
        assert base.u32(code, off) == 0x14000000
        base.put32(code, off, branch(CODE+off, dst))
    return code

def run(code, mode, value, flags, ticket, seed, reference=False, fault=False):
    uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    for addr, size in ((CODE, 0x3000), (LOG, 0x1000), (STACK, 0x4000)):
        uc.mem_map(addr, size)
    if not fault:
        uc.mem_map(0x400000, 0x1000)
        uc.mem_write(0x400000, b'\xa5'*0x1000)
    uc.mem_write(CODE, bytes(code))
    if mode == 'store':
        ref = struct.pack('<II', 0x39000268, branch(REF+4, CONT))
    else:
        # Original CBZ w8 to ZERO; fallthrough B to NONZERO.
        ref = struct.pack('<II', 0x34000008 | ((((ZERO-REF)//4)&0x7ffff)<<5), branch(REF+4, NONZERO))
    uc.mem_write(REF, ref)
    uc.mem_write(STACK, b'\xa5'*0x4000)
    uc.mem_write(LOG, b'\x5a'*0x1000)
    uc.mem_write(LOG, struct.pack('<Q', ticket))
    caller_fp, caller_lr = 0x8123456789abcdef, 0xfedcba9876543210
    uc.mem_write(SP+48, struct.pack('<QQ', caller_fp, caller_lr))
    vals = [((seed+1)<<56) | (0x1020304050600+i*0x111111111) for i in range(31)]
    vals[8] = value
    vals[19] = TARGET
    for r, v in zip(REGS, vals): uc.reg_write(r, v)
    uc.reg_write(UC_ARM64_REG_SP, SP)
    uc.reg_write(UC_ARM64_REG_NZCV, flags)
    events = []
    def hook_code(emu, address, size, unused):
        if address in (CODE+ATOMIC_STORE, CODE+ATOMIC_BRANCH):
            assert not reference and address == CODE+(ATOMIC_STORE if mode == 'store' else ATOMIC_BRANCH)
            assert emu.reg_read(REGS[9]) == LOG and emu.reg_read(REGS[10]) == 1
            old = struct.unpack('<Q', emu.mem_read(LOG, 8))[0]
            emu.mem_write(LOG, struct.pack('<Q', old+1))
            emu.reg_write(REGS[11], old)
            emu.reg_write(UC_ARM64_REG_PC, address+4)
            events.append('atomic-model')
        if address in (ZERO, NONZERO, CONT): emu.emu_stop()
    def hook_write(emu, access, addr, size, val, unused):
        if addr == TARGET: events.append('store')
        if LOG+128 <= addr < LOG+128+16*96 and (addr-LOG-128)%96 == 0:
            events.append('commit')
    uc.hook_add(UC_HOOK_CODE, hook_code)
    uc.hook_add(UC_HOOK_MEM_WRITE, hook_write)
    try:
        uc.emu_start(REF if reference else CODE+(STORE if mode == 'store' else BRANCH), CODE+0x3000, count=500)
        assert not fault
    except UcError as exc:
        assert fault and mode == 'store' and 'unmapped' in str(exc).lower(), str(exc)
        assert uc.reg_read(UC_ARM64_REG_PC) == (REF if reference else CODE+0x154)
        assert events == (['store'] if reference else ['atomic-model', 'store'])
        expected = bytearray(b'\x5a'*0x1000)
        struct.pack_into('<Q', expected, 0, ticket if reference else ticket+1)
        assert bytes(uc.mem_read(LOG, 0x1000)) == expected
        return 'fault'
    pc = uc.reg_read(UC_ARM64_REG_PC)
    expected_pc = CONT if mode == 'store' else (ZERO if (value & 0xffffffff) == 0 else NONZERO)
    assert pc == expected_pc
    regs = [uc.reg_read(r) for r in REGS]
    assert regs == vals and uc.reg_read(UC_ARM64_REG_SP) == SP
    assert uc.reg_read(UC_ARM64_REG_NZCV) == flags
    assert bytes(uc.mem_read(STACK, 0x2000-272)) == b'\xa5'*(0x2000-272)
    assert bytes(uc.mem_read(SP, 48)) == b'\xa5'*48
    assert bytes(uc.mem_read(SP+48, 16)) == struct.pack('<QQ', caller_fp, caller_lr)
    assert bytes(uc.mem_read(SP+64, 0x1fc0)) == b'\xa5'*0x1fc0
    if mode == 'store':
        memory = bytearray(b'\xa5'*0x1000)
        memory[0x80] = value & 255
        assert bytes(uc.mem_read(0x400000, 0x1000)) == memory
    else:
        assert bytes(uc.mem_read(0x400000, 0x1000)) == b'\xa5'*0x1000
    if not reference:
        expected = bytearray(b'\x5a'*0x1000)
        struct.pack_into('<Q', expected, 0, ticket+1)
        if ticket < 16:
            off = 128+ticket*96
            if mode == 'store':
                struct.pack_into('<9Q', expected, off, ticket+1, 4, value&255, TARGET, vals[21], SP, vals[29], caller_fp, caller_lr)
            else:
                struct.pack_into('<5Q', expected, off, ticket+1, 5, value&0xffffffff, SP, vals[29])
        assert bytes(uc.mem_read(LOG, 0x1000)) == expected
        assert events == (['atomic-model'] + (['store'] if mode == 'store' else []) + (['commit'] if ticket < 16 else []))
    return regs, pc, uc.reg_read(UC_ARM64_REG_NZCV)

def main():
    code = prepare(sys.argv[1])
    cases = 0
    for mode in ('store', 'branch'):
        for value in (0, 1, 0xffffffff, 0x100000000, 0xfedcba9800000001):
            for flags in (0, 0x20000000, 0x60000000, 0xf0000000):
                for ticket in (0, 15, 16, 31):
                    for seed in (0, 1):
                        assert run(code, mode, value, flags, ticket, seed) == run(code, mode, value, flags, ticket, seed, reference=True)
                        cases += 1
    for ticket in (0, 15, 16, 31):
        assert run(code, 'store', 0xff, 0xf0000000, ticket, 0, fault=True) == run(code, 'store', 0xff, 0xf0000000, ticket, 0, reference=True, fault=True) == 'fault'
    print('PASS %d equivalence cases, 4 unmapped-store fault cases; LDADDAL modelled only' % cases)

if __name__ == '__main__': main()
