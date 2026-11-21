#!/usr/bin/env python3
"""Audit direct final-kernel calls in the diagnostic exception path."""
import re
import subprocess
import sys

kernel = sys.argv[1]
symbols = subprocess.check_output(["/usr/bin/llvm-nm", kernel], text=True)
for symbol in ("_handle_ux_exception", "_boot_progress_exception"):
    lines = [line for line in symbols.splitlines() if line.endswith(" " + symbol)]
    assert len(lines) == 1, (symbol, lines)
    print("nm:", lines[0])
    text = subprocess.check_output(
        ["/usr/bin/llvm-objdump", "-d", "--no-show-raw-insn",
         "--disassemble-symbols=" + symbol, kernel], text=True)
    assert "<" + symbol + ">:" in text
    branches = re.findall(r"^\s*([0-9a-f]+):\s+bl?\s+0x[0-9a-f]+\s+<([^>]+)>", text, re.M)
    forbidden = ("copyin", "copyout", "vm_map", "task_map", "map_switch", "backtrace")
    bad = [(addr, target) for addr, target in branches if any(s in target for s in forbidden)]
    assert not bad, bad
    print(symbol, "direct branches:", " ".join(f"{addr}:{target}" for addr, target in branches))
    if symbol == "_handle_ux_exception":
        assert any(target == "_boot_progress_exception" for _, target in branches)
print("no direct user-copy, map or backtrace calls in handler/recorder; inspect transitive calls in review")
