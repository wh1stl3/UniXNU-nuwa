"""Exercise the shipped overlay mapper and observer with explicit synthetic inputs."""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

import flush_trace_inputs as trace
ROOT = trace.R
sys.path.insert(0, str(ROOT/'out/python-tools'))
import unicorn as U
from unicorn.arm64_const import *

BIAS = 0xfffffff000000000
parser = argparse.ArgumentParser()
parser.add_argument('--work', type=Path, required=True)
args = parser.parse_args()
work = args.work.resolve()
proof = json.loads((work/'kernel-proof.json').read_bytes())
raw = (work/'kernel.macho').read_bytes()
assert hashlib.sha256(raw).hexdigest() == proof['kernel_sha256']
B = trace.builder()
m = B.macho(raw)
segment = m['segments'][-1]
targets = {k: v-BIAS for k, v in proof['targets'].items()}
local = {k: v-BIAS for k, v in proof['symbols'].items()}
start = segment['va']-BIAS
end = proof['mapped_end']-BIAS
tests = []


def machine():
    u = U.Uc(U.UC_ARCH_ARM64, U.UC_MODE_ARM)
    u.mem_map(start, end-start)
    u.mem_write(start, raw[segment['fileoff']:segment['fileoff']+segment['filesize']])
    return u


def mapping(case):
    u = machine()
    table = 0x30000000
    u.mem_map(table, 0x3000)
    u.mem_write(table+((start >> 30) & 255)*8, struct.pack('<Q', table+0x1003))
    middle = table+0x1000+((start >> 21) & 511)*8
    u.mem_write(middle, struct.pack('<Q', table+0x2003))
    leaf = table+0x2000+((targets['driver_text'] >> 12) & 511)*8
    if case == 'occupied-extension':
        u.mem_write(leaf, struct.pack('<Q', 0x12345003))
    if case == 'missing-table':
        u.mem_write(middle, bytes(8))
    before = bytes(u.mem_read(table, 0x3000))
    u.reg_write(UC_ARM64_REG_X0, table)
    u.reg_write(UC_ARM64_REG_X19, start)
    u.reg_write(UC_ARM64_REG_X20, end)
    u.reg_write(UC_ARM64_REG_X21, 0x40000000-start)
    stop = []

    def boundary(u, pc, size, _):
        if pc in (0x84e5774, 0x84e5790):
            stop.append(pc)
            u.emu_stop()

    u.hook_add(U.UC_HOOK_CODE, boundary)
    u.emu_start(0x84e56d0, 0, count=20000)
    if case != 'normal':
        assert stop == [0x84e5790] and before == bytes(u.mem_read(table, 0x3000))
    else:
        assert stop == [0x84e5774]
        for va in range(start, end, 4096):
            value = struct.unpack('<Q', u.mem_read(table+0x2000+((va >> 12) & 511)*8, 8))[0]
            if targets['old_end'] <= va < targets['driver_text']:
                assert value == 0
                continue
            permissions = 0x0040000000000783
            if targets['old_data'] <= va < targets['old_end'] or va >= targets['driver_data']:
                permissions = 0x0060000000000703
            elif targets['driver_const'] <= va < targets['driver_data']:
                permissions = 0x0060000000000783
            assert value == (va+0x40000000-start) | permissions, (hex(va), hex(value))
    tests.append('mapper '+case)


def observer(case, register_result=0, install_result=0, stage=8, expected=0x10, storage_result=0):
    u = machine()
    site = int(proof['site'], 16)-BIAS
    u.mem_map(site & ~4095, 4096)
    at = B.backed(m, int(proof['site'], 16))
    u.mem_write(site, raw[at:at+4])
    sleep = targets['_IOSleep']
    u.mem_map(sleep & ~4095, 4096)
    u.mem_map(targets['storage_load'] & ~4095, 4096)
    stack = 0x20000000
    u.mem_map(stack-4096, 8192)
    registers = [getattr(U.arm64_const, 'UC_ARM64_REG_X'+str(i)) for i in range(31)]
    values = [0x10000+i*16 for i in range(31)]
    for reg, value in zip(registers, values):
        u.reg_write(reg, value)
    u.reg_write(UC_ARM64_REG_SP, stack)
    u.reg_write(UC_ARM64_REG_NZCV, 0xa0000000)
    rows = {}
    calls = []
    stopped = []

    def hook(u, pc, size, _):
        result = None
        if pc == targets['storage_load']:
            assert [u.reg_read(reg) for reg in registers[1:6]] == [0]*5
            address = u.reg_read(UC_ARM64_REG_X0)
            identifier = b'com.apple.iokit.IOStorageFamily\0'
            assert bytes(u.mem_read(address, len(identifier))) == identifier
            result = storage_result
            calls.append('storage')
        elif pc == targets['_native_ufs_register_late']:
            result = register_result
            calls.append('register')
        elif pc == targets['_nuwa_ufs_metadata_install']:
            result = install_result
            calls.append('install')
        elif pc == targets['_nuwa_ufs_metadata_observe']:
            u.mem_write(targets['_nuwa_metadata_stage'], struct.pack('<I', stage))
            result = 0
            calls.append('observe')
        elif pc == sleep:
            result = 0
            calls.append('sleep')
        elif pc == local['draw']:
            rows[u.reg_read(UC_ARM64_REG_X0)] = u.reg_read(UC_ARM64_REG_X1) & 0xffffffff
            result = 0
        elif pc in (local['halt'], site+4):
            stopped.append(pc)
            u.emu_stop()
        if result is not None:
            u.reg_write(UC_ARM64_REG_X0, result)
            u.reg_write(UC_ARM64_REG_PC, u.reg_read(UC_ARM64_REG_LR))

    u.hook_add(U.UC_HOOK_CODE, hook)
    u.emu_start(site, 0, count=200000)
    assert rows[0] == expected, rows
    assert stopped == [site+4 if expected == 0x10 else local['halt']]
    if expected == 0x10:
        assert [u.reg_read(reg) for reg in registers] == values
        assert u.reg_read(UC_ARM64_REG_SP) == stack-0xb0
        assert u.reg_read(UC_ARM64_REG_NZCV) == 0xa0000000
    if expected == 0x53:
        assert calls.count('observe') == calls.count('sleep') == 1500
    tests.append('observer '+case)


def renderer():
    u = machine()
    framebuffer, stride = 0x60000000, 5760
    u.mem_map(framebuffer, 0x600000)
    u.mem_write(targets['scratch'], struct.pack('<QQ', framebuffer, stride))
    font = struct.unpack('<16I', u.mem_read(local['font'], 64))
    for row, value in enumerate((0x10, 0, 0xe00002bc, 8, 0, 2, 4096, 0xe7514394)):
        u.reg_write(UC_ARM64_REG_X0, row)
        u.reg_write(UC_ARM64_REG_X1, value)
        u.reg_write(UC_ARM64_REG_LR, local['halt'])
        u.emu_start(local['draw'], local['halt'], count=100000)
        assert u.reg_read(UC_ARM64_REG_PC) == local['halt']
        digits = f'{0xfb00+row:04x}{value:08x}'
        for column, digit in enumerate(digits):
            glyph = font[int(digit, 16)]
            for y in range(20):
                address = framebuffer+(576+row*32+y)*stride+384+column*96
                pixels = struct.unpack('<16I', u.mem_read(address, 64))
                expected = [0xffffffff if glyph & (1 << (19-(y//4)*4-x//4)) else 0 for x in range(16)]
                assert list(pixels) == expected, (row, column, y)
    tests.append('actual FB00-FB07 pixels')


for case in ('normal', 'occupied-extension', 'missing-table'):
    mapping(case)
observer('success-resumes-native')
observer('storage-error', storage_result=0xe00002be, expected=0x50)
observer('class-error', register_result=0xe00002d8, expected=0x51)
observer('personality-error', install_result=0xe00002bc, expected=0x52)
observer('bounded-match-timeout', stage=3, expected=0x53)
observer('read-error', stage=7, expected=0x54)
renderer()
(work/'machine-tests.json').write_text(json.dumps(dict(passed=True, kernel_sha256=hashlib.sha256(raw).hexdigest(),
    tests=tests, scope='Synthetic mapper and callback-status harness. No physical UFS or IOKit execution.'), indent=2)+'\n')
print('PASS', len(tests), 'mapper/observer cases')
