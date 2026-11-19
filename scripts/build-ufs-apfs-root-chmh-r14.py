#!/usr/bin/env python3
"""r14: r12afix's SystemOS mount + r13's Data mount in one payload.

Deltas against the r13 packager (all overrides, no edits to the inherited scripts):

  1. kernel: out/nuwa-r14-kernel-20261117/kernel.macho - the merged build (r11 kern_exec
     with the r12 SystemOS patch and the r14 rebased Data patch, the r12 vm_unix /
     nuwa_systemos objects, the r13 iokit persona/init, NativeRamBlock, the r13 stubs
     with the real nuwa_pid1_sample).
  2. seed: out/nuwa-data-seed-macos-20261116-r2/data-8g-fixed.dbr (DBRDISK1 v1,
     8 GiB logical, 1,609,888 B encoded, identity 689fd890..., Data UUID
     B0E0F71F-A265-4038-8F5C-6D3632859DEF) replaces the Linux seed.  The APSB UUID is
     parsed out of the packed extents here and must equal the UUID the kernel was
     compiled with.
  3. args: both namespaces on one line (boot-progress/root + sheng-data-*).
  4. ADT: root-matching (r12) + the 16-byte PackedRAMDisk entry (r13), re-derived.
  5. layout: Ramdisk_bytes is the aligned seed size, and the whole relative window
     (Ramdisk -> TrustCache -> addon -> policy -> Used) must fit.
  6. CHMH: the digest is re-derived from kernel/loader/trust/args/parent-adt; the seed
     is not part of the material.
  7. record: kernel, seed identity/size, Data volume UUID, args and both mount points.
"""
import hashlib
import importlib.util
import os
import struct
import subprocess
import sys
import uuid
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
R12 = ROOT / 'scripts/build-ufs-apfs-root-chmh-r12.py'
R12_SHA = '3b4984c7b9b590c6a8d06f3e82fce33b96f82cde5b5f8dc323bc23dd1fde63e3'
KERNEL = ROOT / 'out/nuwa-r14-kernel-20261117/kernel.macho'
KERNEL_BYTES = 55681024
KERNEL_SHA = 'bd40fa3cdde9f32470bb802f91fe279cd1698fc76f2f7bc517798fcf4533f238'
PROFILE = 'nuwa-ufs-apfs-root-chmh-20261116-r14'
SEED = ROOT / 'out/nuwa-data-seed-macos-20261116-r2/data-8g-fixed.dbr'
SEED_SHA = '6a6db153603b9a4a424711f0fa21c06a3d2b5ffb96a5001864be62d051ed40d9'
SEED_ENCODED_BYTES = 1609888
SEED_IDENTITY = '689fd8901505d177fc33c3ae07a342caaf201b42a14a0330928536121a5a08bd'
SEED_UUID = 'B0E0F71F-A265-4038-8F5C-6D3632859DEF'
INITRD = 'Payloads/scratch-data.img'
ROOT_UUID = 'DADD93F8-DBBF-4B17-A1DF-0F11E64172F7'
TRUST = ROOT / 'out/ios16-system-trust-bundle-20261115-r1/kernel.macho.trustcache'
TRUST_SHA = 'eb1475f643f45a974ebd40596f6e2b1cdf40205d2ca3c6094d774886099399c3'
TRUST_BYTES = 67764
MATCH = ('<dict><key>IOProviderClass</key><string>IOMedia</string>'
         '<key>IOPropertyMatch</key><dict><key>UUID</key><string>' + ROOT_UUID +
         '</string></dict></dict>\0').encode()
ARGS = (b'-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid '
        b'boot-uuid=' + ROOT_UUID.encode() + b' boot-progress=2 build-tag=nuwa-r14 '
        b'boot-progress-scale=3 sheng-data-persist=2 sheng-data-reset=1 sheng-log-reserve=1024')

spec = importlib.util.spec_from_file_location('root_r12', R12)
X = importlib.util.module_from_spec(spec)
spec.loader.exec_module(X)
M = X.M
C = M.C
A = C.C
O = M.O
sha = lambda data: hashlib.sha256(data).hexdigest()
require = M.require

require(sha(R12.read_bytes()) == R12_SHA, 'r12 packager source changed')
KERNEL_BYTES_ON_DISK = KERNEL.read_bytes()
require(len(KERNEL_BYTES_ON_DISK) == KERNEL_BYTES and sha(KERNEL_BYTES_ON_DISK) == KERNEL_SHA,
        'r14 kernel differs')
DELTA_SEED = SEED.read_bytes()
require(len(DELTA_SEED) == SEED_ENCODED_BYTES and sha(DELTA_SEED) == SEED_SHA, 'seed differs')
BUNDLE = TRUST.read_bytes()
require(len(BUNDLE) == TRUST_BYTES and sha(BUNDLE) == TRUST_SHA, 'r8 trust bundle differs')
M.KERNEL = KERNEL
M.KERNEL_BYTES = KERNEL_BYTES
M.KERNEL_SHA = KERNEL_SHA
M.PROFILE = PROFILE
M.ARGS = ARGS

# --- 0. seed identity and APFS volume UUID, read from the packed seed itself -----
PACKED = Path(ROOT.parents[1] / 'UniXNU/drivers/DarwinBoot/Test/packed_ramdisk.py')
spec_pk = importlib.util.spec_from_file_location('packed_ramdisk', PACKED)
PK = importlib.util.module_from_spec(spec_pk)
spec_pk.loader.exec_module(PK)


def seed_volume_uuid(blob):
    """Newest APSB vol_uuid inside the packed seed's nonzero extents (read-only)."""
    logical, extents = PK.regions(blob)
    require(logical == 8589934592, 'Seed is not the 8 GiB logical image')
    newest = None
    for offset, data in extents:
        view = bytes(data)
        for at in range(0, len(view) - 4096 + 1, 4096):
            block = view[at:at + 4096]
            if struct.unpack_from('<I', block, 0x20)[0] != 0x42535041:   # 'APSB'
                continue
            xid = struct.unpack_from('<Q', block, 0x10)[0]
            raw = block[0xF0:0x100]
            value = str(uuid.UUID(bytes=raw)).upper()
            if newest is None or xid > newest[0]:
                newest = (xid, value)
    require(newest is not None, 'No APSB in the seed')
    return newest[0], newest[1]


SEED_XID, SEED_APSB_UUID = seed_volume_uuid(DELTA_SEED)
require(SEED_APSB_UUID == SEED_UUID, 'Seed APSB UUID differs from the pinned one: ' + SEED_APSB_UUID)
META = PK.inspect(SEED)[0]
require(META['bytes'] == 8589934592 and META['encoded_bytes'] == SEED_ENCODED_BYTES and
        META['packed'] is True, 'Seed packing metadata mismatch')
require(META['sha256'] == SEED_IDENTITY, 'Seed identity differs from the pinned one: ' + META['sha256'])

# --- 1. ADT: root-matching (r12) + 16-byte PackedRAMDisk -------------------
prev_derived = C.derived
prev_check_adt = C.check_adt
PACKED_ENTRY = ('PackedRAMDisk', 0, bytes(16))


def derived(parent, digest):
    tree = A.parse(prev_derived(parent, digest))
    memory_map = A.find(tree, '/chosen/memory-map')
    properties = A.properties(memory_map)
    require('RAMDisk' not in properties and 'PackedRAMDisk' not in properties,
            'Parent already has a RAMDisk property')
    memory_map['properties'].append(PACKED_ENTRY)
    return A.encode(tree)


def check_adt(parent, actual, digest):
    tree = A.parse(actual)
    C.reject_asmb(tree)
    chosen = A.properties(A.find(tree, '/chosen'))
    require(chosen.get('mix-n-match-prevention-status') == bytes(4), 'level mismatch')
    require(chosen.get('boot-manifest-hash') == digest, 'CHMH mismatch')
    require(chosen.get('root-matching') == MATCH, 'root UUID mismatch')
    memory_map = A.properties(A.find(tree, '/chosen/memory-map'))
    require(memory_map.get('PackedRAMDisk') == bytes(16), 'PackedRAMDisk missing or not 16 bytes')
    require('RAMDisk' not in memory_map, 'RAMDisk must not be present')
    require(actual == derived(parent, digest), 'Unexpected ADT change')


C.derived = derived
C.check_adt = check_adt


# --- 2. root policy bindings (same checks the r8..r13 chain ran) -----------
def check_root(kernel):
    require(len(kernel) == KERNEL_BYTES and sha(kernel) == KERNEL_SHA, 'Root kernel mismatch')
    external = ROOT / 'out/root-external-policies-20261113'
    archive = external / 'libNuwaRootInputs.a'
    require(sha(archive.read_bytes()) ==
            'dc975e12945ef567763d530a5aac427f58ad321e5ff3b223db7998bf82388c57', 'Root archive mismatch')
    members = subprocess.run(['llvm-ar', 't', str(archive)], check=True, capture_output=True,
                             text=True).stdout.splitlines()
    require(members == ['RootAnchor.o', 'RootPolicies.o'], 'Unexpected root archive members')
    spec_root = importlib.util.spec_from_file_location('root_symbols',
                                                       ROOT / 'scripts/build-nuwa-pmgr-kernel.py')
    b = importlib.util.module_from_spec(spec_root)
    spec_root.loader.exec_module(b)
    names = b.names(kernel)
    require(struct.unpack('<Q', b.read(kernel, names['_verified_root_policy_count'], 8))[0] == 2,
            'policy count')
    for index, (name, pin) in enumerate((
            ('OS', '58e556a380c066db50af9dbec3bbbdbeda47ed39e353c47d6c3ec85fe2f4af65'),
            ('SystemOS', '23637c901e6971f64c3596fa60f06b385c85ce401f739ade9ecfba19d20625a7'))):
        header = (external / (name + '.header.bin')).read_bytes()
        address, size = struct.unpack('<QQ', b.read(kernel, names['_verified_root_policies'] + index * 16, 16))
        require(sha(header) == pin and size == len(header) == 544 and b.read(kernel, address, size) == header,
                'policy binding ' + name)
    for name in ('_vr_open', '_vr_verify_block', '_vr_xnu_crypto'):
        require(name in names, 'missing VerifiedRoot provider ' + name)


# --- 3. layout: ramdisk-aware ---------------------------------------------
def relative_layout(base, end, tree_bytes, trust_bytes, window, ramdisk_bytes):
    require(base % 4096 == 0 and end > base and tree_bytes > 0 and trust_bytes >= 0 and
            0x10000000 <= window <= 0x200000000 and window % 0x200000 == 0 and ramdisk_bytes >= 0,
            'Layout input bounds')
    residue = base & 0x1fffff

    def up(value, size):
        return (value + size - 1) & ~(size - 1)

    args = up(residue + end - base, 16384) - residue
    tree = args + 4096
    ramdisk = up(residue + tree + tree_bytes, 4096) - residue
    # DarwinBoot: RamdiskBytes = ALIGN(seed, 4K) and TrustCache = Ramdisk + RamdiskBytes
    # (no extra alignment); only the addon/policy start land on 16 KiB boundaries.
    ramdisk_span = up(ramdisk_bytes, 4096) if ramdisk_bytes else 0
    trust = ramdisk + ramdisk_span
    addon = up(residue + trust + trust_bytes, 16384) - residue
    policy = up(residue + addon, 16384) - residue
    used = up(residue + policy, 16384) - residue
    require(used <= window - 0x200000, 'Used exceeds window minus loader 2MiB guard')
    intervals = [('kernel_vm_span', 0, end - base), ('boot_args_page', args, args + 4096),
                 ('adt', tree, tree + tree_bytes),
                 ('ramdisk', ramdisk, ramdisk + ramdisk_span),
                 ('trustcache', trust, trust + trust_bytes)]
    require(all(a[2] <= b[1] for a, b in zip(intervals, intervals[1:])), 'Relative layout overlap')
    if ramdisk_bytes % 4096 == 0:
        require(ramdisk_span == ramdisk_bytes, 'Seed is not 4 KiB aligned')
    return {'window_base_physical': None, 'window_base_symbol': 'W (actual allocator result not captured)',
            'window_base_mod_2MiB': residue, 'window_bytes': window,
            'kernel_vm_span': end - base, 'Args_offset': args, 'Tree_offset': tree,
            'Ramdisk_offset': ramdisk, 'Ramdisk_bytes': ramdisk_span,
            'TrustCache_offset': trust, 'Addon_offset': addon, 'Policy_offset': policy,
            'Top_offset': used, 'Used': used, 'limit': window - 0x200000,
            'remaining_window_bytes': window - used, 'loader_guard_bytes': 0x200000,
            'guard_is_proven_stack_reservation': False, 'boot_args_VA': base + args,
            'DeviceTree_VA': base + tree,
            'intervals_relative_to_W': [{'name': n, 'start': lo, 'end': hi} for n, lo, hi in intervals]}


def measure_layout(inputs, adt):
    spec_layout = importlib.util.spec_from_file_location('layout', ROOT / 'scripts/audit-owner-pmap-ret-package.py')
    layout = importlib.util.module_from_spec(spec_layout)
    spec_layout.loader.exec_module(layout)
    base, end, _ = layout.vm_layout(inputs['kernel'])
    chosen = A.properties(A.find(A.parse(adt), '/chosen'))
    window = int.from_bytes(chosen['darwinboot-memory-size'], 'little')
    return relative_layout(base, end, len(adt), len(inputs['trust']), window, len(inputs['seed']))


C.measure_layout = measure_layout


# --- 4. config, inputs, FAT ----------------------------------------------
def r14_config(parent_config):
    old = b'args = "-v serial=3"'
    require(parent_config.count(old) == 1, 'Parent config args not unique')
    return parent_config.replace(old, b'initrd = "' + INITRD.encode() + b'"\nargs = "' + ARGS + b'"')


def check_inputs(inputs):
    pins = dict(C.PINS, kernel=KERNEL_SHA)
    for key, pin in pins.items():
        require(sha(inputs['parent-config'] if key == 'config' else inputs[key]) == pin,
                'Fixed r14 input mismatch: ' + key)
    require(sha(inputs['seed']) == SEED_SHA, 'Fixed r14 seed mismatch')
    require(inputs['config'] == r14_config(inputs['parent-config']), 'Fixed r14 config mismatch')
    config = M.tomllib.loads(inputs['config'].decode())
    entries = [e for e in config['entry'] if e.get('id') == 'xnu']
    require(len(entries) == 1 and entries[0].get('args') == ARGS.decode() and
            entries[0].get('initrd') == INITRD and inputs['args'] == ARGS, 'Fixed r14 args/initrd mismatch')
    require(all(e.get('initrd') is None for e in config['entry'] if e.get('id') != 'xnu'),
            'Unexpected initrd on a non-xnu entry')
    # Both namespaces must be on the one args string, and nothing may smuggle an
    # AMFI opt-out into it.
    text = ARGS.decode()
    for token in ('boot-uuid=' + ROOT_UUID, 'native-ufs-root=1', 'boot-progress=2',
                  'boot-progress-scale=3', 'sheng-data-persist=2', 'sheng-data-reset=1',
                  'sheng-log-reserve=1024', 'build-tag=nuwa-r14'):
        require(token in text.split(), 'args missing ' + token)
    require('amfi_get_out_of_my_way' not in text, 'AMFI opt-out must not be packed')
    material, digest = C.digest_material(inputs)
    require(digest == M.DIGEST, 'Fixed r14 CHMH material mismatch')
    return material


prev_replace = M.replace_members
SEED_SHORT = b'SCRATC~1IMG'
SEED_LONG = INITRD.rsplit('/', 1)[1]


def fat_clusters(fat_bytes):
    """(bytes_per_cluster, total_clusters, free_clusters) of the FAT32 payload volume."""
    require(fat_bytes[0x52:0x57] == b'FAT32', 'Payload volume is not FAT32')
    bytes_per_sector = struct.unpack_from('<H', fat_bytes, 0x0b)[0]
    sectors_per_cluster = fat_bytes[0x0d]
    reserved = struct.unpack_from('<H', fat_bytes, 0x0e)[0]
    fats = fat_bytes[0x10]
    fat_sectors = struct.unpack_from('<I', fat_bytes, 0x24)[0]
    total_sectors = struct.unpack_from('<I', fat_bytes, 0x20)[0]
    require(bytes_per_sector in (512, 4096) and sectors_per_cluster and fats and fat_sectors,
            'FAT BPB geometry')
    cluster_bytes = bytes_per_sector * sectors_per_cluster
    total_clusters = total_sectors // sectors_per_cluster
    at = reserved * bytes_per_sector
    used = 0
    for index in range(2, total_clusters):
        if struct.unpack_from('<I', fat_bytes, at + index * 4)[0] & 0x0fffffff:
            used += 1
    return cluster_bytes, total_clusters, total_clusters - 2 - used


def seed_entry(fat_bytes):
    require(fat_bytes.count(SEED_SHORT) == 1, 'Seed short-name directory entry not unique')
    at = fat_bytes.index(SEED_SHORT)
    require(at % 32 == 0 and fat_bytes[at + 11] == 0x20, 'Seed directory entry shape')
    return at, struct.unpack_from('<I', fat_bytes, at + 28)[0]


def replace_members(fat, kernel_path, adt, config, parent_fat):
    prev_replace(fat, kernel_path, adt, config, parent_fat)
    os.utime(SEED, (946684800, 946684800))
    proc = subprocess.run(['mcopy', '-o', '-i', str(fat), str(SEED), '::/EFI/UniXNU/' + INITRD],
                          env=dict(os.environ, TZ='UTC'), capture_output=True, text=True)
    require(proc.returncode == 0, 'FAT seed insertion failed: ' + proc.stderr)
    raw = bytearray(fat.read_bytes())
    at_seed, size = seed_entry(bytes(raw))
    require(size == len(DELTA_SEED), 'Seed directory entry size')
    require(raw.count(b'UNIXNU~1TOM') == 1, 'Config short name not unique')
    at_config = bytes(raw).index(b'UNIXNU~1TOM')
    raw[at_seed + 13:at_seed + 20] = raw[at_config + 13:at_config + 20]
    raw[at_seed + 22:at_seed + 26] = raw[at_config + 22:at_config + 26]
    fat.write_bytes(bytes(raw))


def verify_fat(fat_path, inputs, work):
    raw = fat_path.read_bytes()
    require(len(raw) == 67108864, 'Payload FAT is not 64 MiB')
    cluster_bytes, total, free = fat_clusters(raw)
    at, size = seed_entry(raw)
    require(size == len(DELTA_SEED), 'Seed size in the FAT directory')
    used = sum(len(inputs[key]) for key in ('kernel', 'trust', 'config', 'seed'))
    require(used <= 63753420, 'FAT 0.95 budget exceeded')
    require(total * cluster_bytes > used, 'FAT capacity')
    require(free * cluster_bytes >= 8388608, 'FAT free space below 8 MiB')
    check = work / 'seed-readback'
    check.mkdir(exist_ok=True)
    destination = check / 'scratch-data.img'
    proc = subprocess.run(['mcopy', '-o', '-i', str(fat_path), '::/EFI/UniXNU/' + INITRD, str(destination)],
                          env=dict(os.environ, TZ='UTC'), capture_output=True, text=True)
    require(proc.returncode == 0, 'Seed readback failed: ' + proc.stderr)
    require(destination.read_bytes() == DELTA_SEED, 'Seed readback differs from the pinned input')
    return {'cluster_bytes': cluster_bytes, 'clusters': total, 'free_clusters': free,
            'free_bytes': free * cluster_bytes, 'seed_entry_offset': at,
            'budget_bytes': 63753420, 'used_bytes': used,
            'budget_headroom_bytes': 63753420 - used}


M.replace_members = replace_members
M.check_inputs = check_inputs

# --- 5. record and audit --------------------------------------------------
prev_record = M.expected_record


def expected_record(inputs, material, ev, adt, fat):
    record = prev_record(inputs, material, ev, adt, fat)
    record['seed_sha256'] = SEED_SHA
    record['seed_encoded_bytes'] = len(DELTA_SEED)
    record['seed_identity'] = SEED_IDENTITY
    record['data_volume_uuid'] = SEED_UUID
    record['apsb_xid'] = SEED_XID
    record['initrd'] = INITRD
    record['kernel_args'] = ARGS.decode()
    record['mounts'] = {'root': {'volume_uuid': ROOT_UUID, 'boot_arg': 'boot-uuid'},
                        'systemos': {'volume_uuid': '96096B28-B6DC-4BC7-9D3A-2632A0FE53F1',
                                     'mount_point': '/private/preboot'},
                        'data': {'volume_uuid': SEED_UUID, 'mount_point': '/private/var'}}
    return record


M.expected_record = expected_record


def fixed(work):
    parent = C.extract(C.FAT, work / 'parent-readback')
    original = C.fixed_inputs(parent)
    C.check_inputs(original)                       # parent pins, before the trust pin moves
    require(parent['parent-adt'] == C.ADT.read_bytes(), 'Parent ADT mismatch')
    kernel_bytes = KERNEL.read_bytes()
    check_root(kernel_bytes)
    inputs = dict(original, kernel=kernel_bytes, args=ARGS, trust=BUNDLE,
                  config=r14_config(original['config']), seed=DELTA_SEED,
                  **{'parent-config': original['config']})
    C.PINS['trust'] = TRUST_SHA                    # the r8 two-module bundle is the input
    _, M.DIGEST = C.digest_material(inputs)
    material = M.check_inputs(inputs)
    ev = M.evidence()
    reference = work / 'profile-reference'
    reference.mkdir()
    adt = derived(inputs['parent-adt'], M.DIGEST)
    check_adt(inputs['parent-adt'], adt, M.DIGEST)
    M.ADT_SHA = sha(adt)
    for name, data in [('kernel.macho', kernel_bytes), ('derived.adt', adt),
                       ('unixnu.toml', inputs['config']), ('payload.img', inputs['fat'])]:
        (reference / name).write_bytes(data)
    M.replace_members(reference / 'payload.img', reference / 'kernel.macho',
                      reference / 'derived.adt', reference / 'unixnu.toml', inputs['fat'])
    fat = (reference / 'payload.img').read_bytes()
    M.FAT_SHA = sha(fat)
    M.FAT_CHECK = verify_fat(reference / 'payload.img', inputs, work)
    layout = M.expected_record(inputs, material, ev, adt, fat)['layout']
    require(layout['Ramdisk_bytes'] == ((len(DELTA_SEED) + 4095) & ~4095), 'Ramdisk_bytes mismatch')
    require(layout['Used'] <= layout['limit'], 'Tail window arithmetic')
    require(layout['remaining_window_bytes'] > 0, 'Window exhausted')
    O.write_json(reference / 'record.json', M.expected_record(inputs, material, ev, adt, fat))
    M.RECORD_SHA = sha((reference / 'record.json').read_bytes())
    return parent, inputs, material, ev


M.fixed = fixed

if __name__ == '__main__':
    M.main()
