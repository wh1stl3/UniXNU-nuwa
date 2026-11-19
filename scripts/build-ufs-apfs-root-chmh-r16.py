#!/usr/bin/env python3
"""r16: r14's SystemOS + Data mounts plus the r16 dyld/AMFI observation kernel.

Everything in the packaging chain is r14's (imported, not edited): the fixed 8 GiB
macOS seed, the APSB volume UUID parsed out of the packed extents, the 16-byte
PackedRAMDisk ADT entry, the ramdisk-aware relative layout, the two-module trust
bundle, the root-policy bindings and the FAT budget/readback checks.

Only three inputs change against r14:

  * kernel: out/nuwa-r16-20261117/kernel.macho - r14's kern_exec/iokit/NativeRamBlock
    inputs, r12's SystemOS and Data objects, plus the rebuilt vm_unix.c (cache-location
    skip + DYLD observation) and the dyld_flags write before the exec.
  * args: build-tag=nuwa-r16 (every other token identical, including both sheng-data-*
    tokens and boot-progress/root).
  * profile: nuwa-ufs-apfs-root-chmh-20261117-r16.

The CHMH digest, the ADT, the FAT and the outer hashes are re-derived from the new
kernel and args.  Host only: no device I/O, no device write, no commit.
"""
import importlib.util
import sys
import hashlib
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
R14 = ROOT / 'scripts/build-ufs-apfs-root-chmh-r14.py'
R14_SHA = 'a95d906159e0d8f1f9fa2ff3846890c6cd6ef63ae269129a12083af4c32a10cd'
KERNEL = ROOT / 'out/nuwa-r16-20261117/kernel.macho'
KERNEL_BYTES = 55681024
KERNEL_SHA = '078455211767759261106cada09046ff2238a70f70aee6f8e15f614af5a263c0'
PROFILE = 'nuwa-ufs-apfs-root-chmh-20261117-r16'
ARGS = (b'-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid '
        b'boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 build-tag=nuwa-r16 '
        b'boot-progress-scale=3 sheng-data-persist=2 sheng-data-reset=1 sheng-log-reserve=1024')

spec = importlib.util.spec_from_file_location('root_r14', R14)
X = importlib.util.module_from_spec(spec)
spec.loader.exec_module(X)
M = X.M
require = X.require
sha = lambda data: hashlib.sha256(data).hexdigest()

require(sha(R14.read_bytes()) == R14_SHA, 'r14 packager source changed')
data = KERNEL.read_bytes()
require(len(data) == KERNEL_BYTES and sha(data) == KERNEL_SHA, 'r16 kernel differs')
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
                'Fixed r16 input mismatch: ' + key)
    require(sha(inputs['seed']) == X.SEED_SHA, 'Fixed r16 seed mismatch')
    require(inputs['config'] == X.r14_config(inputs['parent-config']), 'Fixed r16 config mismatch')
    config = M.tomllib.loads(inputs['config'].decode())
    entries = [e for e in config['entry'] if e.get('id') == 'xnu']
    require(len(entries) == 1 and entries[0].get('args') == ARGS.decode() and
            entries[0].get('initrd') == X.INITRD and inputs['args'] == ARGS,
            'Fixed r16 args/initrd mismatch')
    require(all(e.get('initrd') is None for e in config['entry'] if e.get('id') != 'xnu'),
            'Unexpected initrd on a non-xnu entry')
    text = ARGS.decode()
    for token in ('boot-uuid=' + X.ROOT_UUID, 'native-ufs-root=1', 'boot-progress=2',
                  'boot-progress-scale=3', 'sheng-data-persist=2', 'sheng-data-reset=1',
                  'sheng-log-reserve=1024', 'build-tag=nuwa-r16'):
        require(token in text.split(), 'args missing ' + token)
    require('amfi_get_out_of_my_way' not in text, 'AMFI opt-out must not be packed')
    material, digest = X.C.digest_material(inputs)
    require(digest == M.DIGEST, 'Fixed r16 CHMH material mismatch')
    return material


M.check_inputs = check_inputs

if __name__ == '__main__':
    M.main()
