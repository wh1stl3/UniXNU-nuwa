#!/usr/bin/env python3
"""r9: the r8 packager (r7 kernel/args skeleton + two-module trust bundle) with the observation kernel.

Only the kernel and the package profile change against r8:
  * kernel: out/nuwa-observe-20261115-r1/kernel.macho (r7 baseline plus the
    cyan band-3 exec marker and the orange band-15 initproc first-system-call
    marker; the root-auth skip, the pre-lockdown trust_cache_runtime_init /
    load_static_trust_cache hook and the initproc exec skip stay as in r7),
  * profile: nuwa-ufs-apfs-root-chmh-20261115-r9,
  * everything else - two-module trust cache bundle, args, config, evidence,
    parent FAT/ADT - is r8's, so scripts/build-ufs-apfs-root-chmh-r8.py does
    the work: this file only pins the new kernel and rebinds the profile.
"""
import hashlib
import importlib.util
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
R8 = ROOT / 'scripts/build-ufs-apfs-root-chmh-r8.py'
R8_SHA = 'fcf864004e1a203a34edfe77b2aa7b23f7550ea53bfe7c18bfe3ce2c8be46c9f'
KERNEL = ROOT / 'out/nuwa-observe-20261115-r1/kernel.macho'
KERNEL_BYTES = 55545856
KERNEL_SHA = 'b1029f3d32d1db3ae0bca1b85a665a6758c608ee9f9a5aaffbc55589f83d3764'
PROFILE = 'nuwa-ufs-apfs-root-chmh-20261115-r9'

spec = importlib.util.spec_from_file_location('root_r8', R8)
X = importlib.util.module_from_spec(spec)
spec.loader.exec_module(X)
M = X.M
sha = lambda data: hashlib.sha256(data).hexdigest()

M.require(sha(R8.read_bytes()) == R8_SHA, 'r8 packager source changed')
data = KERNEL.read_bytes()
M.require(len(data) == KERNEL_BYTES and sha(data) == KERNEL_SHA, 'observation kernel differs')
M.KERNEL = KERNEL
M.KERNEL_BYTES = KERNEL_BYTES
M.KERNEL_SHA = KERNEL_SHA
M.PROFILE = PROFILE

if __name__ == '__main__':
    M.main()
