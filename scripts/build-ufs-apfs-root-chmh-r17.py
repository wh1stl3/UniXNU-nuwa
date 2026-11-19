#!/usr/bin/env python3
"""r17: r16's package with the SystemOS cryptex on the fixed dyld path.

Everything in the packaging chain is r16's (loaded, not edited): the fixed 8 GiB macOS
seed, the APSB volume UUID parsed out of the packed extents, the 16-byte PackedRAMDisk
ADT entry, the ramdisk-aware relative layout, the two-module trust bundle, the
root-policy bindings and the FAT budget/readback checks.

Only three inputs change against r16:

  * kernel: out/nuwa-r17-20261117/kernel.macho - r16's objects plus a rebuilt
    package/nuwa-systemos/nuwa_systemos.c (memory-backed devfs on /private/preboot,
    Cryptexes, cryptex mounted at /private/preboot/Cryptexes/OS, r16 mount as fallback).
  * args: build-tag=nuwa-r17 (every other token identical, including both sheng-data-*
    tokens and boot-progress/root).
  * profile: nuwa-ufs-apfs-root-chmh-20261117-r17.

The CHMH digest, the ADT, the FAT and the outer hashes are re-derived from the new
kernel and args.  Host only: no device I/O, no device write, no commit.
"""
import importlib.util
import sys
import hashlib
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
R16 = ROOT / 'scripts/build-ufs-apfs-root-chmh-r16.py'
R16_SHA = '3b8f3c1d7cfcf0da3c45c095e5a3515b74a5e4887c609a35733a7fc8b62619e8'
KERNEL = ROOT / 'out/nuwa-r17-20261117/kernel.macho'
KERNEL_BYTES = 55681024
KERNEL_SHA = '5632a383ecc2aa3330b543468544b445c46dc1258b391738cde1f6b916b84c1f'
PROFILE = 'nuwa-ufs-apfs-root-chmh-20261117-r17'
ARGS = (b'-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid '
        b'boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 build-tag=nuwa-r17 '
        b'boot-progress-scale=3 sheng-data-persist=2 sheng-data-reset=1 sheng-log-reserve=1024')

spec = importlib.util.spec_from_file_location('root_r16', R16)
X = importlib.util.module_from_spec(spec)
spec.loader.exec_module(X)
M = X.M
require = X.require
sha = lambda data: hashlib.sha256(data).hexdigest()

require(sha(R16.read_bytes()) == R16_SHA, 'r16 packager source changed')
data = KERNEL.read_bytes()
require(len(data) == KERNEL_BYTES and sha(data) == KERNEL_SHA, 'r17 kernel differs')
# r14's module globals drive fixed()/expected_record(), r16's drive its check_inputs and
# the packager module M both share.
for module in (X.X, X, M):
    module.KERNEL = KERNEL
    module.KERNEL_BYTES = KERNEL_BYTES
    module.KERNEL_SHA = KERNEL_SHA
    module.PROFILE = PROFILE
    module.ARGS = ARGS


# Same checks as r16's check_inputs; only the expected build tag moves (it is a literal
# in that function, so the wrapper carries the whole body).
def check_inputs(inputs):
    pins = dict(X.X.C.PINS, kernel=KERNEL_SHA)
    for key, pin in pins.items():
        require(sha(inputs['parent-config'] if key == 'config' else inputs[key]) == pin,
                'Fixed r17 input mismatch: ' + key)
    require(sha(inputs['seed']) == X.X.SEED_SHA, 'Fixed r17 seed mismatch')
    require(inputs['config'] == X.X.r14_config(inputs['parent-config']),
            'Fixed r17 config mismatch')
    config = M.tomllib.loads(inputs['config'].decode())
    entries = [e for e in config['entry'] if e.get('id') == 'xnu']
    require(len(entries) == 1 and entries[0].get('args') == ARGS.decode() and
            entries[0].get('initrd') == X.X.INITRD and inputs['args'] == ARGS,
            'Fixed r17 args/initrd mismatch')
    require(all(e.get('initrd') is None for e in config['entry'] if e.get('id') != 'xnu'),
            'Unexpected initrd on a non-xnu entry')
    text = ARGS.decode()
    for token in ('boot-uuid=' + X.X.ROOT_UUID, 'native-ufs-root=1', 'boot-progress=2',
                  'boot-progress-scale=3', 'sheng-data-persist=2', 'sheng-data-reset=1',
                  'sheng-log-reserve=1024', 'build-tag=nuwa-r17'):
        require(token in text.split(), 'args missing ' + token)
    require('amfi_get_out_of_my_way' not in text, 'AMFI opt-out must not be packed')
    material, digest = X.X.C.digest_material(inputs)
    require(digest == M.DIGEST, 'Fixed r17 CHMH material mismatch')
    return material


M.check_inputs = check_inputs

# r17: the package record must name the real SystemOS mount point.  r14's record carries
# '/private/preboot' (the r12/r16 shape), which would misdescribe this image.
_prev_expected_record = M.expected_record


def expected_record(inputs, material, ev, adt, fat):
    record = _prev_expected_record(inputs, material, ev, adt, fat)
    record['mounts']['systemos'] = {
        'volume_uuid': '96096B28-B6DC-4BC7-9D3A-2632A0FE53F1',
        'mount_point': '/private/preboot/Cryptexes/OS',
        'scratch_mount': '/private/preboot',
        'scratch_filesystem': 'devfs (memory-backed; xnu-8796 has no tmpfs)',
        'fallback_mount_point': '/private/preboot',
        'cache_env': 'DYLD_SHARED_CACHE_DIR=/System/Cryptexes/OS/System/Library/Caches/com.apple.dyld',
    }
    return record


M.expected_record = expected_record

if __name__ == '__main__':
    M.main()
