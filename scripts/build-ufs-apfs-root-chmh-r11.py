#!/usr/bin/env python3
"""r11: the r8 packager (r7 args skeleton + two-module trust bundle) with the boot
progress kernel.

Against r10 the payload changes in two inputs:

  * kernel: out/nuwa-bootprogress-20261115-r1/kernel.macho (r10's upstream
    trust-cache baseline plus the nine objects rebuilt from
    patches/xnu/8796-nuwa-boot-progress.patch and libBootProgress.a force-loaded;
    root-auth skip and initproc exec skip stay, no observation patches),
  * args: the r5/r7/r8/r9/r10 argument line plus boot-progress=2 (continuous: the
    30 s stall and 120 s deadline only warn, the OS and the screen keep running)
    and build-tag=nuwa-r11 (the tag the renderer prints in its title row),
  * profile: nuwa-ufs-apfs-root-chmh-20261115-r11.

So r8's fixed() is reused with a new args/trust input set, which re-derives the
args material, the CHMH digest, the ADT, the FAT and the outer hashes.  Everything
else - two-module trust cache bundle, config, evidence, configs, parent FAT/ADT -
is r8's.
"""
import hashlib
import importlib.util
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
R10 = ROOT / 'scripts/build-ufs-apfs-root-chmh-r10.py'
R10_SHA = '2815ca6a8be9ca3cc267176dd200bf9648a8eb6303f75845d71f1250c634375b'
KERNEL = ROOT / 'out/nuwa-bootprogress-20261115-r1/kernel.macho'
KERNEL_BYTES = 55595008
KERNEL_SHA = 'b2c5ed6017aa58a1f25a998e585f060a5ea28dbcf0a14e7faca1ee4687dae167'
PROFILE = 'nuwa-ufs-apfs-root-chmh-20261115-r11'
ARGS = (b'-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid '
        b'boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 build-tag=nuwa-r11')

spec = importlib.util.spec_from_file_location('root_r10', R10)
X = importlib.util.module_from_spec(spec)
spec.loader.exec_module(X)
M = X.M
sha = lambda data: hashlib.sha256(data).hexdigest()

M.require(sha(R10.read_bytes()) == R10_SHA, 'r10 packager source changed')
data = KERNEL.read_bytes()
M.require(len(data) == KERNEL_BYTES and sha(data) == KERNEL_SHA, 'boot progress kernel differs')
M.KERNEL = KERNEL
M.KERNEL_BYTES = KERNEL_BYTES
M.KERNEL_SHA = KERNEL_SHA
M.PROFILE = PROFILE
# The args material, the CHMH digest and every derived hash follow M.ARGS
# (r8's fixed() and the parent's check_inputs read it).  boot-progress=2 is the
# renderer's continuous mode; the tag is what the title row prints.
M.ARGS = ARGS

if __name__ == '__main__':
    M.main()
