#!/usr/bin/env python3
"""Host-only compact r35b profile using the pinned, FAT-corrected r35 packager."""
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent / 'UniXNU-nuwa/scripts/build-ufs-apfs-root-chmh-r35.py'
SOURCE_SHA = '16ed1a3b762152a0426701942224d5c7008edb01829c97bc8132a5262e7d3b96'


def load_profile():
    source = SOURCE.read_bytes()
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA:
        raise ValueError('Pinned r35 packager changed')
    text = source.decode()
    replacements = (
        ("KERNEL = ROOT / 'out/nuwa-r35-20261119/kernel.macho'",
         "KERNEL = ROOT / 'out/nuwa-r35b-compact-r3-20261120/kernel.macho'"),
        ("KERNEL_SHA = '787610183dc7f772e2d01aa183f72f2fcc52245fc44407e6c815ced614412464'",
         "KERNEL_SHA = '6262a25ab2211c8010a105d9456cdf46d38832c5edf3667f2b09a8262639deb8'"),
        ("KERNEL_BYTES = 55721984", "KERNEL_BYTES = 52006912"),
        ("PROFILE = 'nuwa-ufs-apfs-root-chmh-20261119-r35'",
         "PROFILE = 'nuwa-ufs-apfs-root-chmh-20261120-r35b-compact'"),
        ('(status or os_reason namespace non-zero)',
         '(signal = status & 127, or os_reason namespace non-zero)'),
    )
    for old, new in replacements:
        if text.count(old) != 1:
            raise ValueError('r35 packager anchor changed: ' + old)
        text = text.replace(old, new, 1)
    namespace = {'__file__': str(SOURCE), '__name__': 'r35b_packager'}
    exec(compile(text, str(SOURCE), 'exec'), namespace)
    return namespace


if __name__ == '__main__':
    sys.dont_write_bytecode = True
    load_profile()['M'].main()
