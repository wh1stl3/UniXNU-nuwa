#!/usr/bin/env python3
"""r18: r16's package with the SystemOS cryptex union-mounted on "/".

Everything in the packaging chain is r14's (imported, not edited): the fixed 8 GiB macOS
seed, the APSB volume UUID parsed out of the packed extents, the 16-byte PackedRAMDisk ADT
entry, the ramdisk-aware relative layout, the two-module trust bundle, the root-policy
bindings and the FAT budget/readback checks.

Against r16 only three inputs change:

  * kernel: out/nuwa-r18-20261117/kernel.macho - r16's objects with v17c/v18's
    package/nuwa-systemos/nuwa_systemos.c: the SystemOS cryptex is mounted on "/" with
    MNT_RDONLY|MNT_UNION (the official shape; dyld's only usable fixed cache location is
    /System/Library/Caches/com.apple.dyld on the root), and the r17c devfs + Cryptexes/OS
    mount stays as the recorded fallback.  package/nuwa-data/nuwa_data_mount.c adds the
    Data-row triage fields (devpath/pub/serr).
  * args: build-tag=nuwa-r18 (every other token identical, including both sheng-data-*
    tokens and boot-progress/root).
  * profile: nuwa-ufs-apfs-root-chmh-20261117-r18.

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
KERNEL = ROOT / 'out/nuwa-r18-20261117/kernel.macho'
KERNEL_BYTES = 55681024
KERNEL_SHA = '8d608d5484e4729a0cd897ed37fa8d4d9f181cba8cf84bc3b09db0829a07566b'
PROFILE = 'nuwa-ufs-apfs-root-chmh-20261117-r18'
ARGS = (b'-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid '
        b'boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 build-tag=nuwa-r18 '
        b'boot-progress-scale=3 sheng-data-persist=2 sheng-data-reset=1 sheng-log-reserve=1024')

spec = importlib.util.spec_from_file_location('root_r14', R14)
X = importlib.util.module_from_spec(spec)
spec.loader.exec_module(X)
M = X.M
require = X.require
sha = lambda data: hashlib.sha256(data).hexdigest()

require(sha(R14.read_bytes()) == R14_SHA, 'r14 packager source changed')
data = KERNEL.read_bytes()
require(len(data) == KERNEL_BYTES and sha(data) == KERNEL_SHA, 'r18 kernel differs')
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
                'Fixed r18 input mismatch: ' + key)
    require(sha(inputs['seed']) == X.SEED_SHA, 'Fixed r18 seed mismatch')
    require(inputs['config'] == X.r14_config(inputs['parent-config']),
            'Fixed r18 config mismatch')
    config = M.tomllib.loads(inputs['config'].decode())
    entries = [e for e in config['entry'] if e.get('id') == 'xnu']
    require(len(entries) == 1 and entries[0].get('args') == ARGS.decode() and
            entries[0].get('initrd') == X.INITRD and inputs['args'] == ARGS,
            'Fixed r18 args/initrd mismatch')
    require(all(e.get('initrd') is None for e in config['entry'] if e.get('id') != 'xnu'),
            'Unexpected initrd on a non-xnu entry')
    text = ARGS.decode()
    for token in ('boot-uuid=' + X.ROOT_UUID, 'native-ufs-root=1', 'boot-progress=2',
                  'boot-progress-scale=3', 'sheng-data-persist=2', 'sheng-data-reset=1',
                  'sheng-log-reserve=1024', 'build-tag=nuwa-r18'):
        require(token in text.split(), 'args missing ' + token)
    require('amfi_get_out_of_my_way' not in text, 'AMFI opt-out must not be packed')
    material, digest = X.C.digest_material(inputs)
    require(digest == M.DIGEST, 'Fixed r18 CHMH material mismatch')
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
    }
    return record


M.expected_record = expected_record

if __name__ == '__main__':
    M.main()
