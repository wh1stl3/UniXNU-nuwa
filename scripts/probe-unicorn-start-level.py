"""Which TCR shapes can this Unicorn translate, and does it keep the high VA bits?

Same page-table content, four root layouts. A: T0SZ=25 with an L1 root (the ARM
layout). B: T0SZ=26 with an L1 root (XNU's layout). C: T0SZ=26 with the root read
as an L2 table. D: T0SZ=25 with an L2 root as a control. Then high-VA probes.
Exit code 0 always: the JSON is the result, not the exit status.
"""
import json
import struct
import sys

import unicorn as U
from unicorn.arm64_const import *

RAM, TPA = 0x40000000, 0x41000000
LOW, HIGH = 0x500000, 0x8c37c7378


def fetch(va, tcr, root_is_l1):
    uc = U.Uc(U.UC_ARCH_ARM64, U.UC_MODE_ARM)
    uc.mem_map(RAM, 0x8000000)
    root, mid, leaf = RAM, RAM + 0x1000, RAM + 0x2000
    for table in (root, mid, leaf):
        uc.mem_write(table, bytes(0x1000))
    uc.mem_write(leaf + ((va >> 12) & 0x1ff) * 8, struct.pack('<Q', TPA | 0x403))
    if root_is_l1:
        uc.mem_write(root + ((va >> 30) & 0xff) * 8, struct.pack('<Q', mid | 3))
        uc.mem_write(mid + ((va >> 21) & 0x1ff) * 8, struct.pack('<Q', leaf | 3))
    else:
        uc.mem_write(root + ((va >> 21) & 0x1ff) * 8, struct.pack('<Q', leaf | 3))
    uc.mem_write(TPA, bytes([0x1f, 0x20, 0x03, 0xd5]) * 4)
    uc.reg_write(UC_ARM64_REG_TTBR0_EL1, root)
    uc.reg_write(UC_ARM64_REG_TTBR1_EL1, root)
    uc.cpr_write(3, 0, 2, 0, 2, tcr)
    uc.cpr_write(3, 0, 10, 2, 0, 0xff)
    uc.cpr_write(3, 0, 1, 0, 0, 0x30d00800 | 1)
    uc.reg_write(UC_ARM64_REG_PSTATE, 0x3c5)
    try:
        uc.emu_start(va, 0, count=4)
        return {'ok': True, 'pc': hex(uc.reg_read(UC_ARM64_REG_PC))}
    except U.UcError as error:
        return {'ok': False, 'error': str(error)}


def main():
    cases = []
    for label, va, tcr, l1 in (
            ('A t0sz25-l1root-lowva', LOW, 0x280993519, True),
            ('B t0sz26-l1root-lowva', LOW, 0x28099351a, True),
            ('C t0sz26-l2root-lowva', LOW, 0x28099351a, False),
            ('D t0sz25-l2root-control', LOW, 0x280993519, False),
            ('E xnu-tcr-l1root', LOW, 0x22a51a251a, True),
            ('F xnu-tcr-l2root', LOW, 0x22a51a251a, False),
            ('G t0sz26-l2root-highva', HIGH, 0x28099351a, False),
            ('H t0sz26-l2root-1gib', 0x40000000, 0x28099351a, False)):
        cases.append({'case': label, 'va': hex(va), 'tcr': hex(tcr), 'root': 'L1' if l1 else 'L2',
                      **fetch(va, tcr, l1)})
    result = {
        'scope': ('TCR shape compatibility of this Unicorn build; the page-table content is '
                  'identical between cases, only the root layout and TCR differ'),
        'unicorn_version': U.__version__,
        'cases': cases,
        'l2_root_works_only_for_t0sz26': (next(c for c in cases if c['case'].startswith('C'))['ok']
                                          and not next(c for c in cases if c['case'].startswith('B'))['ok']
                                          and not next(c for c in cases if c['case'].startswith('D'))['ok']),
        'high_va_translatable_with_t0sz26': next(c for c in cases if c['case'].startswith('G'))['ok'],
    }
    print(json.dumps(result))


if __name__ == '__main__':
    main()
