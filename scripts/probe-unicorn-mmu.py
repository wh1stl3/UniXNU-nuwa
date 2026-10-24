"""Can this Unicorn build translate an ARM64 instruction fetch at EL1?

Textbook 4 KiB granule: T0SZ=26, three levels, VA 0x500000 mapped to
PA 0x41000000 (non-identity).

Root cause of the earlier "refused" reading: Unicorn starts with SCR_EL3=0 and
HCR_EL2=0, so arm_el_is_aa64() is false (qemu/target/arm/cpu.h:2030) and the walk
takes the AArch32 branch (helper.c:9925), which reads only T0SZ & 7 = 2 -> 30-bit
input -> an L2 start. Setting SCR_EL3.NS|RW (and HCR_EL2.RW) puts the model in
the AArch64 execution state the kernel actually runs in.

Default state is kept as the negative control. Exit code 0 = translated,
1 = refused (expected without --aarch64-state).
"""
import struct
import sys

try:
    import unicorn as U
    from unicorn.arm64_const import *
except ImportError as error:  # pragma: no cover - environment probe
    print('unicorn unavailable:', error)
    sys.exit(2)

AARCH64_STATE = '--aarch64-state' in sys.argv[1:]

RAM, VA, TARGET = 0x40000000, 0x500000, 0x41000000
uc = U.Uc(U.UC_ARCH_ARM64, U.UC_MODE_ARM)
uc.mem_map(RAM, 0x8000000)
l1, l2, l3 = RAM, RAM + 0x1000, RAM + 0x2000
for table in (l1, l2, l3):
    uc.mem_write(table, bytes(0x1000))
uc.mem_write(l1 + ((VA >> 30) & 0xff) * 8, struct.pack('<Q', l2 | 3))
uc.mem_write(l2 + ((VA >> 21) & 0x1ff) * 8, struct.pack('<Q', l3 | 3))
uc.mem_write(l3 + ((VA >> 12) & 0x1ff) * 8, struct.pack('<Q', TARGET | 0x403))
uc.mem_write(TARGET, bytes([0x1f, 0x20, 0x03, 0xd5]) * 4)   # nops
uc.reg_write(UC_ARM64_REG_TTBR0_EL1, l1)
uc.reg_write(UC_ARM64_REG_TTBR1_EL1, l1)
uc.cpr_write(3, 0, 2, 0, 2, 26 | (26 << 16) | (2 << 32))    # T0SZ/T1SZ 26, IPS 40-bit
uc.cpr_write(3, 0, 10, 2, 0, 0xff)                          # MAIR attr0 = normal WB
uc.cpr_write(3, 0, 1, 0, 0, 0x30d00800 | 1)                 # SCTLR_EL1.M = 1
uc.reg_write(UC_ARM64_REG_PSTATE, 0x3c5)                    # EL1h
if AARCH64_STATE:
    uc.cpr_write(3, 6, 1, 1, 0, (1 << 10) | 1)   # SCR_EL3.NS|RW
    uc.cpr_write(3, 4, 1, 1, 0, 1 << 31)         # HCR_EL2.RW
try:
    uc.emu_start(VA, 0, count=4)
    print('OK translated; pc=', hex(uc.reg_read(UC_ARM64_REG_PC)), 'unicorn', U.__version__,
          'aarch64_state=', AARCH64_STATE)
    sys.exit(0)
except U.UcError as error:
    print('REFUSED', error, 'unicorn', U.__version__)
    sys.exit(1)
