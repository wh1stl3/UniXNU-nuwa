"""Read-only disassembly of selected frozen carrier symbols or VA ranges."""
import argparse
from pathlib import Path
import capstone
import flush_trace_inputs as t

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--kernel', type=Path, required=True)
p.add_argument('ranges', nargs='+', help='symbol or hex-start:hex-size')
a = p.parse_args()
raw = a.kernel.read_bytes()
b = t.builder()
m = b.macho(raw)
md = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)
symbols = m['symbols']
for item in a.ranges:
    if ':' in item:
        start, size = (int(x, 16) for x in item.split(':'))
    else:
        start = symbols[item]
        end = min(v for v in symbols.values() if v > start)
        size = end - start
    print('\n', item, hex(start), hex(size))
    off = b.backed(m, start, size)
    for ins in md.disasm(raw[off:off+size], start):
        target = int(ins.op_str[1:], 16) if ins.mnemonic in ('bl', 'b') and ins.op_str.startswith('#0x') else None
        names = [k for k, v in symbols.items() if v == target] if target else []
        print(f'{ins.address:016x} {ins.bytes.hex()} {ins.mnemonic:8} {ins.op_str} {" ".join(names)}')
