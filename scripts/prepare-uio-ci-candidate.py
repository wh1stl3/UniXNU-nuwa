"""Move stack-buffer alignment to declarations without changing buffer byte counts."""
import difflib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path('D:/Code/PortingiOS/common/sources/xnu-ios16-full')
definition = 'typedef char __attribute__((aligned(_Alignof(union iovecs)))) uio_stackbuf_t;'
macro = ('\n\n/* Keep byte-array size and apply alignment to the buffer declaration. */\n'
         '#define UIO_STACKBUF(name, niov) \\\n'
         '\tchar name[UIO_SIZEOF(niov)] __attribute__((aligned(_Alignof(union iovecs))))')
paths = subprocess.check_output(['rg', '-l', 'uio_stackbuf_t', str(SOURCE), '-g', '*.c', '-g', '*.h'], text=True).splitlines()
pattern = re.compile(r'uio_stackbuf_t[ \t]+([A-Za-z_][A-Za-z0-9_]*)\[UIO_SIZEOF\(([^\n]+)\)\]')
diffs = []
evidence = []
for name in sorted(paths):
    path = Path(name)
    before = path.read_text(encoding='utf-8')
    after, count = pattern.subn(lambda match: f'UIO_STACKBUF({match[1]}, {match[2]})', before)
    if path.relative_to(SOURCE).as_posix() == 'bsd/sys/uio_internal.h':
        if before.count(definition) != 1:
            raise ValueError('Unexpected aligned typedef context')
        after = after.replace(definition, definition + macro)
    if after != before:
        relative = path.relative_to(SOURCE).as_posix()
        diffs.extend(difflib.unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True),
                                          fromfile='a/' + relative, tofile='b/' + relative))
        evidence.append({'file': relative, 'converted_declarations': count})
if sum(item['converted_declarations'] for item in evidence) != 36:
    raise ValueError('Unexpected stack-buffer declaration inventory; review before proceeding')
destination = ROOT / 'patches/xnu-8796-ci-candidates/clang17-uio-stackbuf.patch'
destination.write_text(''.join(diffs), encoding='utf-8', newline='\n')
record = {'declarations': 36, 'files': evidence,
          'array_element': 'char (unchanged byte addressing)',
          'array_extent': 'UIO_SIZEOF(niov) unchanged for every callsite',
          'variable_alignment': '_Alignof(union iovecs), same as original typedef',
          'original_typedef': 'retained', 'source_written': False,
          'compile_validation': 'pending actual clang17 CI'}
(ROOT / 'reports/kernel-ci/39716728005/uio-candidate.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
print(json.dumps(record, indent=2))
