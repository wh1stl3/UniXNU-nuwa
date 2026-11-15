#!/usr/bin/env python3
"""r8: the r7 kernel and args with a two-module trust cache bundle (OS + SystemOS cryptex).

Against r7 the payload changes in one input only:
  * Payloads/kernel.macho.trustcache becomes the two-module bundle
    (StaticTrustCache + Cryptex1,SystemTrustCache of the same 20H392 donor),
  * the pinned 'trust' input follows that bundle, so the CHMH identity, the
    derived ADT and the FAT/outer hashes are re-derived,
  * kernel, args, config, evidence, root policies and the initproc exec skip
    (still the safety net) are r7's.

The packer chain, the audits and the official vendor_boot step are
scripts/build-ufs-apfs-root-chmh.py's and scripts/build-pmgr-mode2-chmh.py's;
this file replaces that flow's fixed-input step (the trust member) and the FAT
member replacement that carries it.
"""
import hashlib
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
TRUST = ROOT / 'out/ios16-system-trust-bundle-20261115-r1/kernel.macho.trustcache'
TRUST_SHA = 'eb1475f643f45a974ebd40596f6e2b1cdf40205d2ca3c6094d774886099399c3'
TRUST_BYTES = 67764
KERNEL = ROOT / 'out/nuwa-exec-skip-20261115-r6/kernel.macho'
KERNEL_BYTES = 55545856
KERNEL_SHA = '2561c0c527bfa85dda4de218f933eb17a14c821edd20573755aa7b6efdb7872b'
PROFILE = 'nuwa-ufs-apfs-root-chmh-20261115-r8'
ARGS = (b'-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid '
        b'boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7')
ARGS_SHA = 'd71b8f4a6c283f902374d9d6697e4d4f66616e135f3a3654f54c31ab79f6cb4a'
TRUST_MEMBER = '::/EFI/UniXNU/Payloads/kernel.macho.trustcache'
TRUST_SHORT_NAME = b'KERNEL~1TRU'

spec = importlib.util.spec_from_file_location('root_r7', ROOT / 'scripts/build-ufs-apfs-root-chmh.py')
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
M = R.M
sha = lambda data: hashlib.sha256(data).hexdigest()

parent_replace_members = M.replace_members


def bundle():
    data = TRUST.read_bytes()
    M.require(len(data) == TRUST_BYTES and sha(data) == TRUST_SHA, 'Trust bundle mismatch')
    return data


def fixed(work):
    """scripts/build-ufs-apfs-root-chmh.py fixed(), with the r8 trust bundle in the input set."""
    parent = M.C.extract(M.C.FAT, work / 'parent-readback')
    original = M.C.fixed_inputs(parent)
    M.C.check_inputs(original)
    M.require(parent['parent-adt'] == M.C.ADT.read_bytes(), 'Parent ADT mismatch')
    kernel = M.KERNEL.read_bytes()
    R.check_root(kernel)
    old = b'args = "-v serial=3"'
    M.require(original['config'].count(old) == 1, 'Parent config args mismatch')
    inputs = dict(original, kernel=kernel, args=M.ARGS, trust=bundle(),
                  config=original['config'].replace(old, b'args = "' + M.ARGS + b'"'),
                  **{'parent-config': original['config']})
    M.C.PINS['trust'] = TRUST_SHA
    _, M.DIGEST = M.C.digest_material(inputs)
    material = M.check_inputs(inputs)
    ev = M.evidence()
    reference = work / 'profile-reference'
    reference.mkdir()
    adt = R.derived(inputs['parent-adt'], M.DIGEST)
    R.check_adt(inputs['parent-adt'], adt, M.DIGEST)
    M.ADT_SHA = sha(adt)
    for name, data in [('kernel.macho', kernel), ('derived.adt', adt),
                       ('unixnu.toml', inputs['config']), ('payload.img', inputs['fat'])]:
        (reference / name).write_bytes(data)
    M.replace_members(reference / 'payload.img', reference / 'kernel.macho',
                      reference / 'derived.adt', reference / 'unixnu.toml', inputs['fat'])
    fat = (reference / 'payload.img').read_bytes()
    M.FAT_SHA = sha(fat)
    M.O.write_json(reference / 'record.json', M.expected_record(inputs, material, ev, adt, fat))
    M.RECORD_SHA = sha((reference / 'record.json').read_bytes())
    return parent, inputs, material, ev


def replace_members(fat, kernel, adt, config, parent_fat):
    """r7's member replacement plus the trust cache; directory times stay parent-pinned."""
    parent_replace_members(fat, kernel, adt, config, parent_fat)
    os.utime(TRUST, (946684800, 946684800))
    proc = subprocess.run(['mcopy', '-o', '-i', str(fat), str(TRUST), TRUST_MEMBER],
                          env=dict(os.environ, TZ='UTC'), capture_output=True, text=True)
    M.require(proc.returncode == 0, 'Trust FAT replacement failed: ' + proc.stderr)
    M.require(parent_fat.count(TRUST_SHORT_NAME) == 1, 'Trust short name not unique')
    at = parent_fat.index(TRUST_SHORT_NAME)
    raw = bytearray(fat.read_bytes())
    M.require(at % 32 == 0 and parent_fat[at + 11] == raw[at + 11] == 0x20 and
              raw[at:at + 11] == TRUST_SHORT_NAME, 'Trust directory entry moved')
    raw[at + 13:at + 20] = parent_fat[at + 13:at + 20]
    raw[at + 22:at + 26] = parent_fat[at + 22:at + 26]
    fat.write_bytes(raw)


M.require(sha(ARGS) == ARGS_SHA, 'r7 args differ')
M.require(len(bundle()) == TRUST_BYTES, 'Trust bundle length differs')
M.require(len(KERNEL.read_bytes()) == KERNEL_BYTES and sha(KERNEL.read_bytes()) == KERNEL_SHA, 'r7 kernel differs')
M.fixed = fixed
M.replace_members = replace_members
M.ARGS = ARGS
M.KERNEL = KERNEL
M.KERNEL_BYTES = KERNEL_BYTES
M.KERNEL_SHA = KERNEL_SHA
M.PROFILE = PROFILE

if __name__ == '__main__':
    M.main()
