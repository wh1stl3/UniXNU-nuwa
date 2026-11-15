#!/usr/bin/env python3
"""Isolated HC-observation profile over the pinned PMGR CHMH packer."""
import importlib.util
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import owner_bnch as O

SOURCE = ROOT / 'scripts/build-pmgr-mode2-chmh.py'
SOURCE_SHA = '3173f69350086a562ffae20e4d1d4d9586c37bfd9a0b022bc3a1e8e6420f7774'
if O.sha(SOURCE.read_bytes()) != SOURCE_SHA:
    raise ValueError('Pinned PMGR packer source changed')
spec = importlib.util.spec_from_file_location('hc_parent', SOURCE)
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)
M.PROFILE = 'nuwa-ufs-hc-chmh-20261113-r1'
M.ARGS = b'-v serial=3 nuwa-pmgr=2 native-ufs-probe=2 native-ufs-root=0'
M.KERNEL = ROOT / 'out/nuwa-ufs-hc-observe-20261113/run-r7/kernel.macho'
M.KERNEL_SHA = '134d1a24ca32b91d3f41cfdf2d95831abdd4ec4c5be827e291970723d14ba0f5'
M.DIGEST = bytes.fromhex('c2b2aa90d7814beb884c17f9bd19727476b9fa3267bb82847e76419e96f15cbeefff1a8e5bed8120e02878d34a45ed29')
M.EVIDENCE = {
    'kernel_manifest': ('out/nuwa-ufs-hc-observe-20261113/run-r7/manifest.json', 'f6cc009bf5ea7d246e7f744fea5e8a7738470a9852e70fc3df0a83f5caf13553'),
    'two_findings': ('out/nuwa-ufs-hc-observe-20261113/run-r7/two-findings.json', '6cb1ddbe8496fb3bac9754b67f3335f81312ce86ac255a5551923f0119bed789'),
    'provenance': ('out/nuwa-ufs-hc-observe-20261113/run-r7/provenance.json', '7831a34223a46425163d32a2ab7d3c1d12b444b9db5d02ba7898d09e8da736ce'),
}


def fixed(work):
    parent = M.C.extract(M.C.FAT, work / 'parent-readback')
    original = M.C.fixed_inputs(parent)
    M.C.check_inputs(original)
    M.require(parent['parent-adt'] == M.C.ADT.read_bytes(), 'Parent ADT differs from parent FAT')
    kernel = M.KERNEL.read_bytes()
    M.require(len(kernel) == 55545856 and O.sha(kernel) == M.KERNEL_SHA, 'HC kernel mismatch')
    old = b'args = "-v serial=3"'
    M.require(original['config'].count(old) == 1, 'Parent config args mismatch')
    inputs = dict(original, kernel=kernel, args=M.ARGS,
                  config=original['config'].replace(old, b'args = "' + M.ARGS + b'"'),
                  **{'parent-config': original['config']})
    material = M.check_inputs(inputs)
    ev = M.evidence()
    # Derive audit pins independently from the immutable parent, not candidate bytes.
    reference = work / 'profile-reference'
    reference.mkdir()
    adt = M.C.derived(inputs['parent-adt'], M.DIGEST)
    M.C.check_adt(inputs['parent-adt'], adt, M.DIGEST)
    M.ADT_SHA = O.sha(adt)
    for name, data in [('kernel.macho', kernel), ('derived.adt', adt),
                       ('unixnu.toml', inputs['config']), ('payload.img', inputs['fat'])]:
        (reference / name).write_bytes(data)
    M.replace_members(reference / 'payload.img', reference / 'kernel.macho',
                      reference / 'derived.adt', reference / 'unixnu.toml', inputs['fat'])
    fat = (reference / 'payload.img').read_bytes()
    M.FAT_SHA = O.sha(fat)
    O.write_json(reference / 'record.json', M.expected_record(inputs, material, ev, adt, fat))
    M.RECORD_SHA = O.sha((reference / 'record.json').read_bytes())
    return parent, inputs, material, ev


M.fixed = fixed

if __name__ == '__main__':
    M.main()
