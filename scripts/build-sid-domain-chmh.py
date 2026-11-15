#!/usr/bin/env python3
"""Fixed SID domain profile over the pinned queue-five host packer."""
import importlib.util
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import owner_bnch as O

SOURCE = ROOT / 'scripts/build-queue-five-chmh.py'
if O.sha(SOURCE.read_bytes()) != '579f2f9d8928a27bce53b84d0e3881b19e957a87b9f0cf81cc13024b4b887eef':
    raise ValueError('Pinned queue-five packer source changed')
spec = importlib.util.spec_from_file_location('sid_domain_parent', SOURCE)
parent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parent)
M = parent.M
M.PROFILE = 'nuwa-ufs-sid-domain-chmh-20261114-r1'
M.KERNEL = ROOT / 'out/nuwa-ufs-sid-domain-20261114/run/kernel.macho'
M.KERNEL_SHA = '8610b862b2801b5e5730c227b518f76b3969bde351b2416acf786f84f946d0e4'
M.DIGEST = bytes.fromhex('a0c6190eef9cacd72b7b9e17e172681759f0fc6126493a9b094c6a8f9d910bedb576ffbf3fabd4e15e294515317a444e')
M.EVIDENCE = {}

if __name__ == '__main__':
    M.main()
