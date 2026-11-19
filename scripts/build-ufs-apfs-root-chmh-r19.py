#!/usr/bin/env python3
"""r19: r18's package with the dyld cache probe and the opt-in lookup trace.

Everything in the packaging chain is r14's (imported, not edited): the fixed 8 GiB macOS
seed, the APSB volume UUID parsed out of the packed extents, the 16-byte PackedRAMDisk ADT
entry, the ramdisk-aware relative layout, the two-module trust bundle, the root-policy
bindings and the FAT budget/readback checks.

Against r16 only three inputs change:

  * kernel: out/nuwa-r19-20261118/kernel.macho - r18's objects plus r19's
    package/nuwa-systemos/nuwa_systemos.c: four vnode_lookup probes of the dyld cache
    paths after the union mount verifies (SYSOS p1..p4/csz and the console line
    "nuwa: cache probe ...").  The mount shape (union on "/", r17c fallback), the Data
    mount and the observation are unchanged.
  * args: build-tag=nuwa-r19 (every other token identical, including both sheng-data-*
    tokens and boot-progress/root).
  * profile: nuwa-ufs-apfs-root-chmh-20261118-r19.

The CHMH digest, the ADT, the FAT and the outer hashes are re-derived from the new kernel
and args.  Host only: no device I/O, no device write, no commit.
"""
import importlib.util
import sys
import hashlib
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
R14 = ROOT / 'scripts/build-ufs-apfs-root-chmh-r14.py'
R14_SHA = 'a95d906159e0d8f1f9fa2ff3846890c6cd6ef63ae269129a12083af4c32a10cd'
KERNEL = ROOT / 'out/nuwa-r19-20261118/kernel.macho'
KERNEL_BYTES = 55681024
KERNEL_SHA = '19bd5d5b4a469024ac32492d6aa81748b0695edc5cdfe34b98c4ea7cede4246c'
PROFILE = 'nuwa-ufs-apfs-root-chmh-20261118-r19'
ARGS = (b'-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid '
        b'boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 build-tag=nuwa-r19 '
        b'boot-progress-scale=3 sheng-data-persist=2 sheng-data-reset=1 sheng-log-reserve=1024')

spec = importlib.util.spec_from_file_location('root_r14', R14)
X = importlib.util.module_from_spec(spec)
spec.loader.exec_module(X)
M = X.M
require = X.require
sha = lambda data: hashlib.sha256(data).hexdigest()

require(sha(R14.read_bytes()) == R14_SHA, 'r14 packager source changed')
data = KERNEL.read_bytes()
require(len(data) == KERNEL_BYTES and sha(data) == KERNEL_SHA, 'r19 kernel differs')
# r14's module globals drive its closures (check_root, fixed, expected_record).
X.KERNEL = KERNEL
X.KERNEL_BYTES = KERNEL_BYTES
X.KERNEL_SHA = KERNEL_SHA
X.PROFILE = PROFILE
X.ARGS = ARGS
M.KERNEL = KERNEL
M.KERNEL_BYTES = KERNEL_BYTES
M.KERNEL_SHA = KERNEL_SHA
M.PROFILE = PROFILE
M.ARGS = ARGS


# Same checks as r14's check_inputs; only the expected build tag moves (it is a literal
# in that function, so the wrapper carries the whole body).
def check_inputs(inputs):
    pins = dict(X.C.PINS, kernel=KERNEL_SHA)
    for key, pin in pins.items():
        require(sha(inputs['parent-config'] if key == 'config' else inputs[key]) == pin,
                'Fixed r19 input mismatch: ' + key)
    require(sha(inputs['seed']) == X.SEED_SHA, 'Fixed r19 seed mismatch')
    require(inputs['config'] == X.r14_config(inputs['parent-config']),
            'Fixed r19 config mismatch')
    config = M.tomllib.loads(inputs['config'].decode())
    entries = [e for e in config['entry'] if e.get('id') == 'xnu']
    require(len(entries) == 1 and entries[0].get('args') == ARGS.decode() and
            entries[0].get('initrd') == X.INITRD and inputs['args'] == ARGS,
            'Fixed r19 args/initrd mismatch')
    require(all(e.get('initrd') is None for e in config['entry'] if e.get('id') != 'xnu'),
            'Unexpected initrd on a non-xnu entry')
    text = ARGS.decode()
    for token in ('boot-uuid=' + X.ROOT_UUID, 'native-ufs-root=1', 'boot-progress=2',
                  'boot-progress-scale=3', 'sheng-data-persist=2', 'sheng-data-reset=1',
                  'sheng-log-reserve=1024', 'build-tag=nuwa-r19'):
        require(token in text.split(), 'args missing ' + token)
    require('amfi_get_out_of_my_way' not in text, 'AMFI opt-out must not be packed')
    material, digest = X.C.digest_material(inputs)
    require(digest == M.DIGEST, 'Fixed r19 CHMH material mismatch')
    return material


M.check_inputs = check_inputs

# r18: the package record must name the real SystemOS mount.  r14's record carries
# '/private/preboot' (the r12/r16 shape), which would misdescribe this image.
_prev_expected_record = M.expected_record


def expected_record(inputs, material, ev, adt, fat):
    record = _prev_expected_record(inputs, material, ev, adt, fat)
    record['mounts']['systemos'] = {
        'volume_uuid': '96096B28-B6DC-4BC7-9D3A-2632A0FE53F1',
        'mount_point': '/',
        'mount_flags': 'MNT_RDONLY|MNT_UNION',
        'union': 'boot volume visible underneath; rootvnode moves to the cryptex (checkdirs)',
        'cache_path': '/System/Library/Caches/com.apple.dyld',
        'fallback_mount_point': '/private/preboot/Cryptexes/OS',
        'fallback_scratch_mount': '/private/preboot',
        'cache_env': 'DYLD_SHARED_CACHE_DIR=/System/Cryptexes/OS/System/Library/Caches/com.apple.dyld',
        'probe': 'SYSOS p1..p4 = vnode_lookup errno of the four cache paths, csz = KiB of the '
                 'dyld_shared_cache_arm64 probe; console line "nuwa: cache probe ..."',
    }
    return record


M.expected_record = expected_record

if __name__ == '__main__':
    M.main()
