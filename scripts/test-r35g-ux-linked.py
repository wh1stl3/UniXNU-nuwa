#!/usr/bin/env python3
"""Check all direct final-kernel references to the exception producer."""
import re
import subprocess
import sys

owner = None
edges, handler = [], {}
with subprocess.Popen(["/usr/bin/llvm-objdump", "-d", "--no-show-raw-insn", sys.argv[1]],
                      stdout=subprocess.PIPE, text=True) as proc:
    for line in proc.stdout:
        label = re.match(r"[0-9a-f]+ <([^>]+)>:", line)
        if label:
            owner = label[1]
        branch = re.match(r"([0-9a-f]+):\s+(b|bl)\s+0x[0-9a-f]+\s+<([^>]+)>$", line.rstrip())
        if not branch:
            continue
        addr, op, target = int(branch[1], 16), branch[2], branch[3]
        if target == "_boot_progress_exception":
            edges.append((owner, op, addr))
        if owner == "_handle_ux_exception" and target in {
            "_proc_findthread", "_get_user_regs", "_threadsignal", "_machine_exception"
        }:
            assert target not in handler, target
            handler[target] = addr
    assert proc.wait() == 0
(owner, op, site), = edges
assert (owner, op) == ("_handle_ux_exception", "bl"), edges
assert (handler["_proc_findthread"] < handler["_machine_exception"] <
        handler["_get_user_regs"] < site < handler["_threadsignal"]), handler
print(f"sole exception-recorder edge={site:#x} from {owner}; no drawing callers")
print(" ".join(f"{target}={addr:#x}" for target, addr in handler.items()))
