#!/usr/bin/env python3
"""Host-only UFS APFS root CHMH packaging, pending observation and userdata gates."""
import argparse
import hashlib
import importlib.util
import json
import os
import re
import struct
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import owner_bnch as O
import nuwa_launch_context as A

SOURCE = ROOT / 'scripts/build-pmgr-mode2-chmh.py'
if O.sha(SOURCE.read_bytes()) != '3173f69350086a562ffae20e4d1d4d9586c37bfd9a0b022bc3a1e8e6420f7774':
    raise ValueError('Pinned PMGR packer source changed')
spec = importlib.util.spec_from_file_location('root_packer_parent', SOURCE)
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)
# r6: the r5 boot reached exec of launchd and AMFI denied it
# (OS_REASON_EXEC / EXEC_EXIT_REASON_SECURITY_POLICY from
# kern_exec.c: imgp->ip_mac_return != 0), because the runtime trust cache is
# empty. NUWA_ROOT_ARGS allows packing a variant without editing this file:
#   NUWA_ROOT_ARGS='... amfi_get_out_of_my_way=1' ... -> CS_CONFIG_GET_OUT_OF_MY_WAY
# (parsed in bsd/kern/kern_codesigning.c under DEVELOPMENT || DEBUG). The args
# hash and the CHMH material still bind whatever is packed, so the variant is
# recorded in record.json like any other input.
M.ARGS = os.environ.get(
    'NUWA_ROOT_ARGS',
    '-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid '
    'boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7').encode()
M.EVIDENCE = {
    'root_inputs': ('out/nuwa-ufs-apfs-root-integration-20261114/run-r4/root-inputs.json', 'bc344eb1f00aacccb6c09b07b3100800fe26acda77fb216139fbae8f70935bc4'),
    'root_config': ('out/nuwa-ufs-apfs-root-integration-20261114/run-r4/root-config.json', 'ec3a2705e70342dccdbfd3cb4bef7eceab606d611370562ca0a574620a193556'),
}
UUID = 'DADD93F8-DBBF-4B17-A1DF-0F11E64172F7'
MATCH = ('<dict><key>IOProviderClass</key><string>IOMedia</string>'
         '<key>IOPropertyMatch</key><dict><key>UUID</key><string>' + UUID +
         '</string></dict></dict>\0').encode()
parent_derived = M.C.derived


def derived(parent, digest):
    tree = A.parse(parent_derived(parent, digest))
    chosen = A.find(tree, '/chosen')
    M.require('root-matching' not in A.properties(chosen), 'Parent already has root matching')
    chosen['properties'].append(('root-matching', 0, MATCH))
    return A.encode(tree)


def check_adt(parent, actual, digest):
    tree = A.parse(actual)
    M.C.reject_asmb(tree)
    chosen = A.properties(A.find(tree, '/chosen'))
    M.require(chosen.get('mix-n-match-prevention-status') == bytes(4), 'level mismatch')
    M.require(chosen.get('boot-manifest-hash') == digest, 'CHMH mismatch')
    M.require(chosen.get('root-matching') == MATCH, 'root UUID mismatch')
    M.require(actual == derived(parent, digest), 'Unexpected ADT change')


M.C.derived = derived
M.C.check_adt = check_adt


def check_root(kernel):
    M.require(len(kernel) == M.KERNEL_BYTES and O.sha(kernel) == M.KERNEL_SHA, 'Root kernel mismatch')
    external = ROOT / 'out/root-external-policies-20261113'
    archive = external / 'libNuwaRootInputs.a'
    M.require(O.sha(archive.read_bytes()) == 'dc975e12945ef567763d530a5aac427f58ad321e5ff3b223db7998bf82388c57', 'Root archive mismatch')
    members = subprocess.run(['llvm-ar', 't', str(archive)], check=True, capture_output=True, text=True).stdout.splitlines()
    M.require(members == ['RootAnchor.o', 'RootPolicies.o'], 'Unexpected root archive members')
    spec = importlib.util.spec_from_file_location('root_symbols', ROOT / 'scripts/build-nuwa-pmgr-kernel.py')
    b = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(b)
    names = b.names(kernel)
    M.require(struct.unpack('<Q', b.read(kernel, names['_verified_root_policy_count'], 8))[0] == 2, 'policy count')
    for index, (name, pin) in enumerate((
        ('OS', '58e556a380c066db50af9dbec3bbbdbeda47ed39e353c47d6c3ec85fe2f4af65'),
        ('SystemOS', '23637c901e6971f64c3596fa60f06b385c85ce401f739ade9ecfba19d20625a7'))):
        header = (external / (name + '.header.bin')).read_bytes()
        address, size = struct.unpack('<QQ', b.read(kernel, names['_verified_root_policies'] + index * 16, 16))
        M.require(O.sha(header) == pin and size == len(header) == 544 and b.read(kernel, address, size) == header,
                  'policy binding ' + name)
    for name in ('_vr_open', '_vr_verify_block', '_vr_xnu_crypto'):
        M.require(name in names, 'missing VerifiedRoot provider ' + name)


def fixed(work):
    parent = M.C.extract(M.C.FAT, work / 'parent-readback')
    original = M.C.fixed_inputs(parent)
    M.C.check_inputs(original)
    M.require(parent['parent-adt'] == M.C.ADT.read_bytes(), 'Parent ADT mismatch')
    kernel = M.KERNEL.read_bytes()
    check_root(kernel)
    old = b'args = "-v serial=3"'
    M.require(original['config'].count(old) == 1, 'Parent config args mismatch')
    inputs = dict(original, kernel=kernel, args=M.ARGS,
                  config=original['config'].replace(old, b'args = "' + M.ARGS + b'"'),
                  **{'parent-config': original['config']})
    _, M.DIGEST = M.C.digest_material(inputs)
    material = M.check_inputs(inputs)
    ev = M.evidence()
    reference = work / 'profile-reference'
    reference.mkdir()
    adt = derived(inputs['parent-adt'], M.DIGEST)
    check_adt(inputs['parent-adt'], adt, M.DIGEST)
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
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--kernel', type=Path, required=True)
    parser.add_argument('--kernel-bytes', type=int, required=True)
    parser.add_argument('--kernel-sha256', required=True)
    parser.add_argument('--profile', required=True)
    options, remaining = parser.parse_known_args()
    M.require(options.kernel_bytes > 0 and re.fullmatch(r'[0-9a-f]{64}', options.kernel_sha256),
              'Explicit kernel size/hash required')
    M.require(re.fullmatch(r'nuwa-ufs-apfs-root-chmh-[a-z0-9-]+', options.profile), 'Invalid profile')
    M.KERNEL = options.kernel.resolve(strict=True)
    M.require(M.KERNEL.is_relative_to((ROOT / 'out').resolve()) and not options.kernel.is_symlink(),
              'Kernel must be a regular output under out/')
    M.KERNEL_BYTES = options.kernel_bytes
    M.KERNEL_SHA = options.kernel_sha256
    M.PROFILE = options.profile
    sys.argv = [sys.argv[0], *remaining]
    M.main()
