#!/usr/bin/env python3
"""Host-only r35b profile using the pinned, otherwise unchanged r35 packager."""
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent / 'UniXNU-nuwa/scripts/build-ufs-apfs-root-chmh-r35.py'
SOURCE_SHA = 'cbdaff922bd2e335cf73268e55a56c98b74dffd36e5a3b5c5a1759b3d088a9b5'


def main():
    source = SOURCE.read_bytes()
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA:
        raise ValueError('Pinned r35 packager changed')
    text = source.decode()
    replacements = (
        ("KERNEL = ROOT / 'out/nuwa-r35-20261119/kernel.macho'",
         "KERNEL = ROOT / 'out/nuwa-r35b-exit-selection-20261120/kernel.macho'"),
        ("KERNEL_SHA = '787610183dc7f772e2d01aa183f72f2fcc52245fc44407e6c815ced614412464'",
         "KERNEL_SHA = 'ad7e70f7e615494c6162cec1a72610e119e897414bb89e4e038075244442da2f'"),
        ("PROFILE = 'nuwa-ufs-apfs-root-chmh-20261119-r35'",
         "PROFILE = 'nuwa-ufs-apfs-root-chmh-20261120-r35b'"),
    )
    for old, new in replacements:
        if text.count(old) != 1:
            raise ValueError('r35 packager anchor changed: ' + old)
        text = text.replace(old, new, 1)
    namespace = {'__file__': str(SOURCE), '__name__': 'r35b_packager'}
    exec(compile(text, str(SOURCE), 'exec'), namespace)
    namespace['M'].main()


if __name__ == '__main__':
    sys.dont_write_bytecode = True
    main()
