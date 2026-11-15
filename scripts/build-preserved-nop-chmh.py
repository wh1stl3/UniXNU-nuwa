#!/usr/bin/env python3
"""Fixed preserved-NOP host-only CHMH profile over the pinned PMGR packer."""
import importlib.util
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import owner_bnch as O

SOURCE = ROOT / 'scripts/build-pmgr-mode2-chmh.py'
if O.sha(SOURCE.read_bytes()) != '3173f69350086a562ffae20e4d1d4d9586c37bfd9a0b022bc3a1e8e6420f7774':
    raise ValueError('Pinned PMGR packer source changed')
spec = importlib.util.spec_from_file_location('preserved_nop_parent', SOURCE)
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)
M.PROFILE = 'nuwa-ufs-preserved-nop-chmh-20261114-r1'
M.ARGS = b'-v serial=3 nuwa-pmgr=2 native-ufs-probe=2 native-ufs-root=0'
M.KERNEL = ROOT / 'out/nuwa-ufs-preserved-nop-exec-20261114/run-r2/kernel.macho'
M.KERNEL_SHA = '05ebb53baf0d98aa0f189b8c1569e7375f6403c20b3df2c739734ba459488944'
M.DIGEST = bytes.fromhex('9c536cf3983cc039106c5a438184a505f577bd2cd0c30eb28bb05a44e490ead563df77af3f2dcea8e976b97983740a9b')
M.EVIDENCE = {}


def fixed(work):
    parent = M.C.extract(M.C.FAT, work / 'parent-readback')
    original = M.C.fixed_inputs(parent)
    M.C.check_inputs(original)
    M.require(parent['parent-adt'] == M.C.ADT.read_bytes(), 'Parent ADT differs from parent FAT')
    kernel = M.KERNEL.read_bytes()
    M.require(len(kernel) == 55549952 and O.sha(kernel) == M.KERNEL_SHA, 'Preserved NOP kernel mismatch')
    old = b'args = "-v serial=3"'
    M.require(original['config'].count(old) == 1, 'Parent config args mismatch')
    inputs = dict(original, kernel=kernel, args=M.ARGS,
                  config=original['config'].replace(old, b'args = "' + M.ARGS + b'"'),
                  **{'parent-config': original['config']})
    material = M.check_inputs(inputs)
    ev = M.evidence()
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
