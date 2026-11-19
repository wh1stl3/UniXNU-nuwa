#!/usr/bin/env python3
"""r12: the r11 packager with the SystemOS-mount kernel and the new args.

Only three inputs change against r11:

  * kernel: out/nuwa-systemos-mount-20261115-r1/kernel.macho (r11 plus the
    SystemOS cryptex mount, the cache-location exception and the pid1/SYSOS row),
  * args: r11's line plus boot-progress-scale=3 (default in the renderer too, but
    pinned here so a photograph says which geometry was asked for); build-tag moves
    to nuwa-r12,
  * profile: nuwa-ufs-apfs-root-chmh-20261115-r12.

Everything else - the two-module trust bundle, the config, the evidence inputs, the
parent FAT/ADT - is r11's.  The CHMH digest, the ADT, the FAT and the outer hashes are
re-derived from the new kernel and args.
"""
import hashlib
import importlib.util
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
R11 = ROOT / 'scripts/build-ufs-apfs-root-chmh-r11.py'
R11_SHA = '6bbaaf2ce884507d6b41c4e9f44e40316a52a5d52ab218b9943e3014ca7552d3'
KERNEL = ROOT / 'out/nuwa-systemos-mount-20261115-r1/kernel.macho'
KERNEL_BYTES = 55623680
KERNEL_SHA = 'ce2cd4666eb7afa1f9d3d805f76a0636ad239b0c2708a90f5798fa3700e01dd2'
PROFILE = 'nuwa-ufs-apfs-root-chmh-20261115-r12'
ARGS = (b'-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid '
        b'boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 build-tag=nuwa-r12 '
        b'boot-progress-scale=3')

spec = importlib.util.spec_from_file_location('root_r11', R11)
X = importlib.util.module_from_spec(spec)
spec.loader.exec_module(X)
M = X.M
sha = lambda data: hashlib.sha256(data).hexdigest()

M.require(sha(R11.read_bytes()) == R11_SHA, 'r11 packager source changed')
data = KERNEL.read_bytes()
M.require(len(data) == KERNEL_BYTES and sha(data) == KERNEL_SHA, 'r12 kernel differs')
M.KERNEL = KERNEL
M.KERNEL_BYTES = KERNEL_BYTES
M.KERNEL_SHA = KERNEL_SHA
M.PROFILE = PROFILE
M.ARGS = ARGS

if __name__ == '__main__':
    M.main()
