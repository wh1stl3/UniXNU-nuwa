#!/usr/bin/env python3
import re
import subprocess
import sys

text = subprocess.check_output(['llvm-objdump', '-dr', '--mattr=+lse', sys.argv[1]], text=True)
for symbol, instruction in (('_panic_screen', 'mov\tx1, sp'),
                            ('_panic_screen_common', r'ldr\tx1, \[x1\]')):
    match = re.search(r'<'+symbol+r'>:\n(.*?)(?=\n\s*\n|\Z)', text, re.S)
    assert match and re.search(instruction, match.group(1)), symbol
    assert 'ARM64_RELOC_BRANCH26\t_panic_screen_main' in match.group(1)
assert re.search(r'\bcasa\s+w\d+, w\d+, \[x\d+\]', text)
assert not re.search(r'\b(?:ldxr|ldaxr|stxr|stlxr)\b', text)
print('PASS ARM64 ordinary/common entry relocations and bounded winner CASA opcode')
