#!/usr/bin/env python3
"""Audit the final Mach-O entry gate and all direct branches to draw."""
import re
import subprocess
import sys

kernel = sys.argv[1]
nm = subprocess.check_output(["/usr/bin/llvm-nm", "-n", kernel], text=True)
symbols = {}
for line in nm.splitlines():
    match = re.fullmatch(r"([0-9a-f]+) [A-Za-z] (_draw|_draw_thread_only)", line)
    if match:
        symbols[match[2]] = int(match[1], 16)
assert len(symbols) == 2, symbols
start = symbols["_draw_thread_only"]
guard = subprocess.check_output([
    "/usr/bin/llvm-objdump", "-d", "--no-show-raw-insn",
    f"--start-address={start:#x}", f"--stop-address={start + 0x34:#x}", kernel
], text=True)
rows = {}
for line in guard.splitlines():
    match = re.match(r"([0-9a-f]+):\s+(\S+)\s*(.*)", line)
    if match:
        rows[int(match[1], 16)] = (match[2], match[3])
checks = [(a, x) for a, x in rows.items() if x[0] == "bl" and "<_ml_at_interrupt_context>" in x[1]]
assert len(checks) == 1
check = checks[0][0]
cond = rows[check + 4]
match = re.match(r"w0, 0x([0-9a-f]+) ", cond[1])
assert cond[0] == "cbz" and match
thread_path = int(match[1], 16)
returns = [a for a, x in rows.items() if x[0] == "ret"]
assert len(returns) == 1 and check < returns[0] < thread_path
branches = [a for a, x in rows.items() if x[0] == "b" and "<_draw>" in x[1]]
assert len(branches) == 1 and thread_path <= branches[0]

proc = subprocess.Popen(["/usr/bin/llvm-objdump", "-d", "--no-show-raw-insn", kernel],
                        stdout=subprocess.PIPE, text=True)
direct, gates = [], []
for line in proc.stdout:
    match = re.match(r"([0-9a-f]+):\s+(?:b|bl)\s+0x[0-9a-f]+\s+<(_draw|_draw_thread_only)>$", line.rstrip())
    if match:
        (direct if match[2] == "_draw" else gates).append(int(match[1], 16))
assert proc.wait() == 0
assert direct == branches and len(gates) == 6, (direct, branches, gates)
print(f"IRQ guard: check={check:#x} cbz={check+4:#x} IRQ return={returns[0]:#x} draw branch={branches[0]:#x}; direct draw edges={len(direct)}, guarded callsites={len(gates)}")
