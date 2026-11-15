#!/usr/bin/env python3
"""Isolated queue-five profile using the pinned HC and PMGR host packers."""
import importlib.util
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import owner_bnch as O

SOURCE = ROOT / 'scripts/build-hc-observe-chmh.py'
if O.sha(SOURCE.read_bytes()) != 'c00342ea8657700b1d82040e07b0fc99fc4baee2e096bb1d07aa976b11ad1fd9':
    raise ValueError('Pinned HC packer source changed')
spec = importlib.util.spec_from_file_location('queue_five_parent', SOURCE)
parent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parent)
M = parent.M
M.PROFILE = 'nuwa-ufs-queue-five-chmh-20261114-r1'
M.KERNEL = ROOT / 'out/nuwa-ufs-queue-five-20261114/run/kernel.macho'
M.KERNEL_SHA = 'eff66a33a097568e3c44f84fb1a7f3365889613cdcb629583944f2c99022012b'
M.DIGEST = bytes.fromhex('903e2f042fd56440fa7da925a4efc32a755b70ebdbdd75c1c1841779e69a630a1c9b1e7c47299db71ddc03c5bea598fd')
# Kernel verifier inputs are deliberately not consumed while it is running.
M.EVIDENCE = {}

if __name__ == '__main__':
    M.main()
