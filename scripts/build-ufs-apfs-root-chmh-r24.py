#!/usr/bin/env python3
"""r24: r23's package with the root reference held across the union mount on "/", the
reboot requester log, and the Data seed path observations (packed ramdisk pair, seed
readiness/result, serr 1..5 from the forked RamBlock driver).

Everything in the packaging chain is r14's (imported, not edited): the fixed 8 GiB macOS
seed, the APSB volume UUID parsed out of the packed extents, the 16-byte PackedRAMDisk ADT
entry, the ramdisk-aware relative layout, the two-module trust bundle, the root-policy
bindings and the FAT budget/readback checks.

Against r16 only three inputs change:

  * kernel: out/nuwa-r24-20261118/kernel.macho - r23's kernel plus: one explicit
    vnode_ref(rootvnode) held across the union mount and released through a single site
    (nuwa_systemos_root_guard) unless the mount really moved the root, with the pair on the
    SYSOS row as uc=before/after; "nuwa: reboot requested by pid/comm" in reboot_kernel()
    behind -DXNU_NUWA_REBOOT_OBSERVE=1; and the Data seed observations in
    package/nuwa-data/nuwa_data_mount.c plus the diagnostics-only fork of the RamBlock
    driver in package/nuwa-ramblock (SOURCE.md: upstream pin, licence, reason).  The cache
    probe stays the one-lookup/one-put version of r23.  The probe used
    to read the cache header through a second lookup (vnode_open()/vnode_close()); because
    vnode_close() ends in vnode_rele_ext() - the call the device panicked in
    (vfs_subr.c:2691, usecount -1) once launchd ran - the header is now read with vn_rdwr()
    on the vnode the lookup already holds, so the probe is one vnode_lookup() and one
    vnode_put() per path and takes no usecount at all.  The magic compare is one memcmp of
    16 bytes against "dyld_v1   arm64" + NUL (r22 compared "arm64" at offset 8 and reported
    mg=bad on a cache dyld loaded); the 16 bytes read go to the console as hex.
  * args: build-tag=nuwa-r23 (every other token identical, including both sheng-data-*
    tokens and boot-progress/root).
  * profile: nuwa-ufs-apfs-root-chmh-20261118-r23.

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
KERNEL = ROOT / 'out/nuwa-r24-20261118/kernel.macho'
KERNEL_BYTES = 55685120
KERNEL_SHA = 'd8fc613a2e0a5749ab3708b40292a00ac9bd5c070579cc75857f04a113f738a7'
PROFILE = 'nuwa-ufs-apfs-root-chmh-20261118-r24'
ARGS = (b'-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid '
        b'boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 build-tag=nuwa-r24 '
        b'boot-progress-scale=3 sheng-data-persist=2 sheng-data-reset=1 sheng-log-reserve=1024')

spec = importlib.util.spec_from_file_location('root_r14', R14)
X = importlib.util.module_from_spec(spec)
spec.loader.exec_module(X)
M = X.M
require = X.require
sha = lambda data: hashlib.sha256(data).hexdigest()

require(sha(R14.read_bytes()) == R14_SHA, 'r14 packager source changed')
data = KERNEL.read_bytes()
require(len(data) == KERNEL_BYTES and sha(data) == KERNEL_SHA, 'r24 kernel differs')
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
                'Fixed r24 input mismatch: ' + key)
    require(sha(inputs['seed']) == X.SEED_SHA, 'Fixed r20 seed mismatch')
    require(inputs['config'] == X.r14_config(inputs['parent-config']),
            'Fixed r20 config mismatch')
    config = M.tomllib.loads(inputs['config'].decode())
    entries = [e for e in config['entry'] if e.get('id') == 'xnu']
    require(len(entries) == 1 and entries[0].get('args') == ARGS.decode() and
            entries[0].get('initrd') == X.INITRD and inputs['args'] == ARGS,
            'Fixed r20 args/initrd mismatch')
    require(all(e.get('initrd') is None for e in config['entry'] if e.get('id') != 'xnu'),
            'Unexpected initrd on a non-xnu entry')
    text = ARGS.decode()
    for token in ('boot-uuid=' + X.ROOT_UUID, 'native-ufs-root=1', 'boot-progress=2',
                  'boot-progress-scale=3', 'sheng-data-persist=2', 'sheng-data-reset=1',
                  'sheng-log-reserve=1024', 'build-tag=nuwa-r24'):
        require(token in text.split(), 'args missing ' + token)
    require('amfi_get_out_of_my_way' not in text, 'AMFI opt-out must not be packed')
    material, digest = X.C.digest_material(inputs)
    require(digest == M.DIGEST, 'Fixed r20 CHMH material mismatch')
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
        'cache_env': 'none (the initproc is exec\'d with USER_ADDR_NULL; dyld uses its default path)',
        'probe': 'SYSOS p1..p6 = vnode_lookup errno of six cache paths (dir, main cache, .01, .42, '
                 'cryptexes, preboot), csz = KiB of the main cache; one vnode_lookup and one '
                 'vnode_put per path, the header read with vn_rdwr on that vnode (no '
                 'open/close); console line "nuwa: cache probe p1=..."',
        'integrity': 'mg = the first 16 bytes are memcmp-equal to "dyld_v1   arm64" + NUL; the '
                     '16 bytes read are printed as "nuwa: cache magic=<hex>"',
        'data_seed': 'console "nuwa: packed ramdisk pa= bytes= found=" (what the loader put in '
                     '/chosen/memory-map/PackedRAMDisk), then "nuwa: data seed uuid= ready= ic=", then '
                     '"nuwa: data seed rc= dev= path= serr="; serr 1 driver not ready, 2 no matching '
                     'IOMedia, 3 match without UUID/BSD properties, 4 no NativeRamBlock provider, '
                     '5 no usable seed (fork of the RamBlock driver, diagnostics only)',
        'root_reference': 'one vnode_ref(rootvnode) across the mount, released through a single site '
                          'unless the mount moved the root; SYSOS row uc=before/after, console '
                          '"nuwa: root usecount before= after= ref_ok="',
        'reboot_observe': 'reboot_kernel() prints "nuwa: reboot requested by pid= comm=" behind '
                          '-DXNU_NUWA_REBOOT_OBSERVE=1',
        'code_signing': 'SYSOS amfi=<0|1> cs=0x<cs_config> flg=<written> rd=<read back>; console '
                        'lines "nuwa: cs ..." and "nuwa: dyld flags ..."; the 4K hash cache is '
                        'compiled in (cs_native4k_hash_cache_version)',
    }
    return record


M.expected_record = expected_record

if __name__ == '__main__':
    M.main()
