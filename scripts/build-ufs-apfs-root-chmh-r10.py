#!/usr/bin/env python3
"""r10: the r8 packager (r7 args skeleton + two-module trust cache bundle) with
the upstream-trust-cache kernel.

Only the kernel and the package profile change against r8:
  * kernel: out/nuwa-native-trust-cache-20261115-r1/kernel.macho (r7 baseline
    whose osfmk/kern/startup.o now comes from the upstream
    patches/xnu/native-trust-cache-runtime.patch with -DXNU_NATIVE_TRUST_CACHE=1
    instead of the local 8796-nuwa-trust-cache-init.patch; root-auth skip and
    initproc exec skip stay, no observation patches),
  * profile: nuwa-ufs-apfs-root-chmh-20261115-r10,
  * everything else - two-module trust cache bundle, args, config, evidence,
    parent FAT/ADT - is r8's, so scripts/build-ufs-apfs-root-chmh-r8.py does the
    work: this file only pins the new kernel and rebinds the profile.  The args
    string is unchanged, so the args material keeps the r5/r7/r8/r9 hash; the
    build identity still has to be rebound because the kernel digest changed.
"""
import hashlib
import importlib.util
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
R8 = ROOT / 'scripts/build-ufs-apfs-root-chmh-r8.py'
R8_SHA = 'fcf864004e1a203a34edfe77b2aa7b23f7550ea53bfe7c18bfe3ce2c8be46c9f'
KERNEL = ROOT / 'out/nuwa-native-trust-cache-20261115-r1/kernel.macho'
KERNEL_BYTES = 55545856
KERNEL_SHA = 'c015d041220e13cdf4173b075b4b2c4a91a5e80f9c80d4449d8ae5173bde136e'
PROFILE = 'nuwa-ufs-apfs-root-chmh-20261115-r10'

spec = importlib.util.spec_from_file_location('root_r8', R8)
X = importlib.util.module_from_spec(spec)
spec.loader.exec_module(X)
M = X.M
sha = lambda data: hashlib.sha256(data).hexdigest()

M.require(sha(R8.read_bytes()) == R8_SHA, 'r8 packager source changed')
data = KERNEL.read_bytes()
M.require(len(data) == KERNEL_BYTES and sha(data) == KERNEL_SHA, 'upstream-trust-cache kernel differs')
M.KERNEL = KERNEL
M.KERNEL_BYTES = KERNEL_BYTES
M.KERNEL_SHA = KERNEL_SHA
M.PROFILE = PROFILE

if __name__ == '__main__':
    M.main()
