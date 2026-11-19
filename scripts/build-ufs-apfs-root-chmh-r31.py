#!/usr/bin/env python3
"""r31: r30's package with the UniXNU AppleKeyStoreState component linked into the kernel and
the boot argument aks=1 (the keybagd restart in r30 is the keychain having no keystore).

Everything in the packaging chain is r14's (imported, not edited): the fixed 8 GiB macOS
seed, the APSB volume UUID parsed out of the packed extents, the 16-byte PackedRAMDisk ADT
entry, the ramdisk-aware relative layout, the two-module trust bundle, the root-policy
bindings and the FAT budget/readback checks.

Against r16 only three inputs change:

  * kernel: out/nuwa-r31-20261119/kernel.macho - r30's kernel plus the unchanged UniXNU
    AppleKeyStoreState component (BSD-2-Clause-Patent, revision 8c70daf8): an IOKit service
    plus user client that answers the AppleKeyStore selector ABI with software key wrapping
    keyed from the ADT /chosen/unique-chip-id, registered inside OSMetaClass::preModLoad()/
    postModLoad() and created from the Data mount after bsd_autoconf(), gated by aks=1.  It
    offers no hardware data protection; keybag, passcode and reference-key operations stay
    unsupported.  The r30 content stays: the
    reboot requester also records its howto flag word (page boot=<pid>/<comm>/<howto hex>,
    console src=/howto=), the three keybag directories are checked after the Data mount
    verified (kb=<keybags><db><tmp>, lookup+getattr only), and bsd_init -> first keybagd
    sighting is published in milliseconds (page t=).  The r29 content stays:
    set_rootvnode() gives kernproc's fd_cdir its own vnode_ref and drops that hold when the
    cdir moves (XNU_NUWA_ROOT_CDIR_REF), so the teardown's three releases - kernproc cdir,
    initproc cdir and rootvnode - each match a hold and the last one no longer runs the
    usecount negative during apfs vflush -> vclean -> vnode_update_identity (the r28 panic in
    vnode_rele_ext); and the reboot requester is recorded at reboot(2), reboot_kernel() and
    host_reboot() and painted on the page immediately (r28 recorded it after the
    system_inshutdown CAS and never repainted, so the page kept boot=-1/-).  r28's RamBlock
    registration bracket, the data-mount creation and the Data observations stay:
    nuwa_ram_block_init() only registers the class again, and nuwa_data_mount_prepare() calls
    nuwa_ram_block_create() before its seed lookup - the bootstrap thread reaches that after
    bsd_init()/bsd_autoconf(), so IOBSD is published and IOResources is in the registry (the
    r26 call from startIOServiceMatching() ran before IService::setPlatform(), was not a
    registry member, and faulted in registerService()'s diagnostic on a bogus metaclass
    pointer).  The create waits up to 2 s (100 x 20 ms) for the IOMedia/APFS media, and
    start()'s static claim still refuses a second disk.  r26's
    nuwa_ram_block_init() registers the class and then calls the forked driver's
    native_ram_block_start_service(), which allocates, attaches to
    IOService::getResourceService() and starts the one disk (the same sequence
    IOService::startCandidate() would run); start() keeps a static claim so a late persona
    match cannot create a second disk over the same boot memory.  The page's reject field
    is now one hex digit (1..9 start() refusals, a..d creation path, e second instance,
    f missing entry point).  r25's page side of the
    Data/RamBlock/reboot observations (the board's progress page does not capture the
    console): row 3 gains "rb=ready:ic:reject", row 8 gains "boot=<pid>/<comm6>", row 9
    becomes "DATA st/e/ro/sd/serr/rc/d/dev | RD <pa>M/<size>K f=<0|1>".  r24's own changes
    stay: one explicit
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
KERNEL = ROOT / 'out/nuwa-r31-20261119/kernel.macho'
KERNEL_BYTES = 55717888
KERNEL_SHA = '626543a02f1a9d79e404ad588416e4f810ed1d7bb106ed9759c3b460a4227afd'
PROFILE = 'nuwa-ufs-apfs-root-chmh-20261119-r31'
ARGS = (b'-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid '
        b'boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 aks=1 build-tag=nuwa-r31 '
        b'boot-progress-scale=3 sheng-data-persist=2 sheng-data-reset=1 sheng-log-reserve=1024')

spec = importlib.util.spec_from_file_location('root_r14', R14)
X = importlib.util.module_from_spec(spec)
spec.loader.exec_module(X)
M = X.M
require = X.require
sha = lambda data: hashlib.sha256(data).hexdigest()

require(sha(R14.read_bytes()) == R14_SHA, 'r14 packager source changed')
data = KERNEL.read_bytes()
require(len(data) == KERNEL_BYTES and sha(data) == KERNEL_SHA, 'r31 kernel differs')
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
                'Fixed r31 input mismatch: ' + key)
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
                  'sheng-log-reserve=1024', 'aks=1', 'build-tag=nuwa-r31'):
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
        'ramblock_create': 'nuwa_ram_block_init() only registers the class; nuwa_data_mount_prepare() '
                           'calls nuwa_ram_block_create() before its seed lookup, which runs the fork entry '
                           '(alloc, attach(IOService::getResourceService()), start) and waits up to 2 s for '
                           'the media - the post-bsd_autoconf point where the registry is connected (r26 '
                           'created it inside startIOServiceMatching and crashed); start() keeps one static '
                           'claim so a late persona match starts no second disk',
        'page_fields': 'row 3 "<PID1/SYSOS> rb=<ready>:<init-calls>:<reject hex>" (reject 1..9 = start() '
                       'refusals, a..d = 10..13 creation path, e = a second instance was refused, f = the '
                       'creation entry point was not linked; the last '
                       'NativeRamBlock::start() code, 0 = none), row 8 "<last IRQ> boot=<pid>/<comm6>" '
                       '(who asked for the reboot), row 9 "DATA st/e/ro/sd/serr/rc/d/dev=<devfs prefix> '
                       '| RD <packed-pa MiB>/<size KiB> f=<0|1>"; every value is a kernel global the '
                       'renderer reads, because this board does not capture the console',
        'root_reference': 'removed in r28 (attempted in r24, ineffective: uc=10/8); r29 instead '
                          'gives kernproc p_fd.fd_cdir its own vnode_ref in set_rootvnode() '
                          '(XNU_NUWA_ROOT_CDIR_REF), so kernproc cdir + initproc cdir + rootvnode '
                          'holds match the teardown releases',
        'reboot_observe': 'reboot(2) (src=1), reboot_kernel() (src=2) and host_reboot() (src=3) '
                          'record the requester with a first-wins latch (nuwa_reboot_src) and repaint '
                          'the page immediately; r30 adds the howto flag word, drawn as the third '
                          'boot= field and printed as src=/howto= on the console',
        'keybag_dirs': 'after the Data mount verified: one vnode_lookup + vnode_getattr per '
                       '/private/var/{keybags,db,tmp}, no create and no write; page kb=<keybags><db>'
                       '<tmp> with o = writable directory, r = no write bit, m = missing, '
                       'e = other error',
        'apple_keystore': 'UniXNU AppleKeyStoreState (vendored unchanged, BSD-2-Clause-Patent, '
                          'revision 8c70daf8) answers the AppleKeyStore selector ABI with software key '
                          'wrapping keyed from the ADT /chosen/unique-chip-id; registered inside '
                          'OSMetaClass::preModLoad()/postModLoad() and created from the Data mount '
                          'after bsd_autoconf(); gated by aks=1; page ak=<state>/<opens>, console '
                          '"nuwa: aks class registered" / "nuwa: aks started identity_bytes="',
        'keybagd_time': 'mach_absolute_time() at the top of bsd_init() to the first keybagd '
                        'sighting in the 2 s process probe (absolutetime_to_nanoseconds), page '
                        't=<ms> and console "nuwa: keybagd pid= exec_ms="',
        'ramblock_register': 'OSMetaClass::preModLoad("__kernel__") -> static initializer -> '
                             'postModLoad() around the class registration; "__kernel__" is '
                             'kOSKextKernelIdentifier, the kext OSRuntimeInitializeCPP() uses for the '
                             'kernel classes',
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
