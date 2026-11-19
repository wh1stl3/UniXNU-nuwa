#!/usr/bin/env python3
"""r12afix: r12fix kernel objects + the r12a SystemOS mount (no VirtioMmioBlock).

Only three inputs change against r12fix:

  * kernel: out/nuwa-r12afix-20261116-r1/kernel.macho (r12fix's objects plus the r12
    kern_exec/vm_unix/nuwa_systemos builds, the r12a IOKit shim, the real pid1 sample),
  * args: r12fix's line with build-tag=nuwa-r12afix,
  * profile: nuwa-ufs-apfs-root-chmh-20261116-r12afix.

Everything else - the two-module trust bundle, the config, the evidence inputs, the parent
FAT/ADT, the 64 MiB payload - is r12fix's.  The CHMH digest, the ADT, the FAT and the
outer hashes are re-derived from the new kernel and args.
"""
import hashlib
import importlib.util
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
R12 = ROOT / 'scripts/build-ufs-apfs-root-chmh-r12.py'
R12_SHA = '3b4984c7b9b590c6a8d06f3e82fce33b96f82cde5b5f8dc323bc23dd1fde63e3'
KERNEL = ROOT / 'out/nuwa-r12afix-20261116-r1/kernel.macho'
KERNEL_BYTES = 55615488
KERNEL_SHA = 'fb05dd1884678ff100230f9091e01153f171cd841691ac4928412b43dc844125'
PROFILE = 'nuwa-ufs-apfs-root-chmh-20261116-r12afix'
ARGS = (b'-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid '
        b'boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 build-tag=nuwa-r12afix '
        b'boot-progress-scale=3')

spec = importlib.util.spec_from_file_location('root_r12', R12)
X = importlib.util.module_from_spec(spec)
spec.loader.exec_module(X)
M = X.M
sha = lambda data: hashlib.sha256(data).hexdigest()

M.require(sha(R12.read_bytes()) == R12_SHA, 'r12 packager source changed')
data = KERNEL.read_bytes()
M.require(len(data) == KERNEL_BYTES and sha(data) == KERNEL_SHA, 'r12afix kernel differs')
M.KERNEL = KERNEL
M.KERNEL_BYTES = KERNEL_BYTES
M.KERNEL_SHA = KERNEL_SHA
M.PROFILE = PROFILE
M.ARGS = ARGS

if __name__ == '__main__':
    M.main()
