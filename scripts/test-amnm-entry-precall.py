#!/usr/bin/env python3
"""ENTRY/PRECALL Mach-O execution; LDADDAL is explicitly modelled only."""
import importlib.util
from pathlib import Path
import struct
import subprocess
import sys
from unicorn import Uc, UcError, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm64_const import UC_ARM64_REG_SP, UC_ARM64_REG_NZCV, UC_ARM64_REG_PC

spec = importlib.util.spec_from_file_location('input_test', Path(__file__).with_name('test-amnm-input.py'))
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
CODE, LOG, STACK, REGS = base.CODE, base.LOG, base.STACK, base.REGS
ENTRY, PRECALL = 0x2dc, 0x3c0
REF, RETURN, CONT = CODE+0x1800, CODE+0x1808, CODE+0x1900
CALLEES = (0x400000, 0x401000, 0x500000)  # last one intentionally unmapped

def branch(src, dst):
    return 0x14000000 | (((dst-src)//4)&0x3ffffff)

def page_reloc(code, off, reg, target):
    assert base.u32(code, off) == (0x90000000 | reg)
    pages = ((target & ~4095)-(CODE & ~4095))//4096
    base.put32(code, off, 0x90000000 | reg | ((pages&3)<<29) | (((pages>>2)&0x7ffff)<<5))
    add = base.u32(code, off+4)
    assert add == (0x91000000 | (reg<<5) | reg)
    base.put32(code, off+4, add | ((target&4095)<<10))

def prepare(path):
    dis = subprocess.check_output(['llvm-objdump', '-dr', '--mattr=+lse', path], text=True)
    assert 'ARM64_RELOC_BRANCH26\t_amnm_entry_continue' in dis
    assert dis.count('ARM64_RELOC_PAGE21\t_amnm_precall_return') == 1
    assert dis.count('ARM64_RELOC_PAGEOFF12\t_amnm_precall_return') == 1
    assert 'ARM64_RELOC_BRANCH26\t_amnm_precall_continue' in dis
    assert dis.count('ARM64_RELOC_PAGE21\t_amnm_observer_log') == 5
    code = base.text_section(Path(path).read_bytes())
    for off in (0x334, 0x418): assert base.u32(code, off) == 0xf8ea012b
    for off in (0x368, 0x464): assert base.u32(code, off) == 0xc89ffd8b
    assert base.u32(code, 0x3b8) == 0xd10643ff
    assert base.u32(code, 0x4b4) == 0xaa1503e1
    assert base.u32(code, 0x4b8) == 0x14000000
    page_reloc(code, 0x328, 9, LOG)
    page_reloc(code, 0x40c, 9, LOG)
    page_reloc(code, 0x454, 13, RETURN)
    base.put32(code, 0x4b8, branch(CODE+0x4b8, REF+4))
    assert base.u32(code, 0x3bc) == 0x14000000
    base.put32(code, 0x3bc, branch(CODE+0x3bc, CONT))
    return code

def run(code, mode, seed, flags, ticket, callee, reference=False):
    uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    for addr, size in ((CODE, 0x3000), (LOG, 0x1000), (STACK, 0x5000), (0x400000, 0x2000)):
        uc.mem_map(addr, size)
    uc.mem_write(CODE, bytes(code))
    # PRECALL reference and hook both execute the same real BLR at REF+4.
    ref = struct.pack('<II', 0xd10643ff, branch(REF+4, CONT)) if mode == 'entry' else struct.pack('<III', 0xaa1503e1, 0xd63f0100, 0xd503201f)
    uc.mem_write(REF, ref)
    uc.mem_write(0x400000, struct.pack('<I', 0xd65f03c0))
    uc.mem_write(0x401000, struct.pack('<I', 0xd65f03c0))
    uc.mem_write(STACK, b'\xa5'*0x5000)
    uc.mem_write(LOG, b'\x5a'*0x1000)
    uc.mem_write(LOG, struct.pack('<Q', ticket))
    sp = STACK + 0x2000 + seed*0x400
    vals = [((seed+1)<<56) | (0x1020304050600+i*0x111111111) for i in range(31)]
    vals[8] = callee
    vals[29] = sp + 0x80 + seed*0x10
    for r, v in zip(REGS, vals): uc.reg_write(r, v)
    uc.reg_write(UC_ARM64_REG_SP, sp)
    uc.reg_write(UC_ARM64_REG_NZCV, flags)
    seen, atomic = [], []
    def code_hook(emu, address, size, unused):
        if address in (CODE+0x334, CODE+0x418):
            assert not reference and address == CODE+(0x334 if mode == 'entry' else 0x418)
            assert emu.reg_read(REGS[9]) == LOG and emu.reg_read(REGS[10]) == 1
            old = struct.unpack('<Q', emu.mem_read(LOG, 8))[0]
            emu.mem_write(LOG, struct.pack('<Q', old+1))
            emu.reg_write(REGS[11], old)
            emu.reg_write(UC_ARM64_REG_PC, address+4)
            atomic.append(old)
        if address in CALLEES[:2]:
            seen.append(([emu.reg_read(r) for r in REGS], emu.reg_read(UC_ARM64_REG_SP), emu.reg_read(UC_ARM64_REG_NZCV)))
        if address == (CONT if mode == 'entry' else RETURN): emu.emu_stop()
    uc.hook_add(UC_HOOK_CODE, code_hook)
    failed = False
    try:
        uc.emu_start(REF if reference else CODE+(ENTRY if mode == 'entry' else PRECALL), CODE+0x3000, count=500)
    except UcError as exc:
        assert mode == 'precall' and callee == CALLEES[2] and 'unmapped' in str(exc).lower()
        assert uc.reg_read(UC_ARM64_REG_PC) == callee
        failed = True
    assert failed == (mode == 'precall' and callee == CALLEES[2])
    expected_regs = vals.copy()
    if mode == 'precall':
        expected_regs[1] = vals[21]
        expected_regs[30] = RETURN
    assert [uc.reg_read(r) for r in REGS] == expected_regs
    assert uc.reg_read(UC_ARM64_REG_SP) == sp - (400 if mode == 'entry' else 0)
    assert uc.reg_read(UC_ARM64_REG_NZCV) == flags
    if mode == 'precall' and not failed:
        assert seen == [(expected_regs, sp, flags)]
        assert uc.reg_read(UC_ARM64_REG_PC) == RETURN
    if mode == 'entry': assert uc.reg_read(UC_ARM64_REG_PC) == CONT
    assert bytes(uc.mem_read(STACK, sp-272-STACK)) == b'\xa5'*(sp-272-STACK)
    assert bytes(uc.mem_read(sp, STACK+0x5000-sp)) == b'\xa5'*(STACK+0x5000-sp)
    if not reference:
        assert atomic == [ticket]
        expected = bytearray(b'\x5a'*0x1000)
        struct.pack_into('<Q', expected, 0, ticket+1)
        if ticket < 16:
            off = 128+ticket*96
            if mode == 'entry':
                struct.pack_into('<5Q', expected, off, ticket+1, 1, sp, vals[29], vals[30])
            else:
                struct.pack_into('<9Q', expected, off, ticket+1, 2, callee, vals[0], vals[2], vals[3], sp, vals[29], RETURN)
        assert bytes(uc.mem_read(LOG, 0x1000)) == expected
    return expected_regs, uc.reg_read(UC_ARM64_REG_SP), uc.reg_read(UC_ARM64_REG_NZCV), failed

def main():
    code = prepare(sys.argv[1])
    count = 0
    for mode in ('entry', 'precall'):
        for seed in (0, 1):
            for flags in (0, 0x20000000, 0x60000000, 0xf0000000):
                for ticket in (0, 15, 16, 31):
                    for callee in CALLEES if mode == 'precall' else CALLEES[:1]:
                        assert run(code, mode, seed, flags, ticket, callee) == run(code, mode, seed, flags, ticket, callee, reference=True)
                        count += 1
    print('PASS %d ENTRY/PRECALL cases including unmapped callee; LDADDAL modelled only' % count)

if __name__ == '__main__': main()
