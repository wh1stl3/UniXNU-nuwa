#!/usr/bin/env python3
"""r12fix: r11 kernel objects + the r12 renderer with the !display.bound guard."""
import hashlib
import importlib.util
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
R12 = ROOT / 'scripts/build-ufs-apfs-root-chmh-r12.py'
R12_SHA = '3b4984c7b9b590c6a8d06f3e82fce33b96f82cde5b5f8dc323bc23dd1fde63e3'
KERNEL = ROOT / 'out/nuwa-r12bisect-20261116/r12fix/kernel.macho'
KERNEL_BYTES = 55595008
KERNEL_SHA = 'c741464befbb57027636b2730b678f82bf224a98f13b802e4c07fcb452c1ae2c'
PROFILE = 'nuwa-ufs-apfs-root-chmh-20261116-r12fix'
ARGS = (b'-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid '
        b'boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 build-tag=nuwa-r12fix '
        b'boot-progress-scale=3')

spec = importlib.util.spec_from_file_location('root_r12', R12)
X = importlib.util.module_from_spec(spec)
spec.loader.exec_module(X)
M = X.M
sha = lambda data: hashlib.sha256(data).hexdigest()

M.require(sha(R12.read_bytes()) == R12_SHA, 'r12 packager source changed')
data = KERNEL.read_bytes()
M.require(len(data) == KERNEL_BYTES and sha(data) == KERNEL_SHA, 'r12fix kernel differs')
M.KERNEL = KERNEL
M.KERNEL_BYTES = KERNEL_BYTES
M.KERNEL_SHA = KERNEL_SHA
M.PROFILE = PROFILE
M.ARGS = ARGS

if __name__ == '__main__':
    M.main()
