"""Bind current diagnostic bytes to the offline root/Data integration gaps."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import read_dispatch_audit as A

ROOT = A.ROOT


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source', type=Path, required=True)
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    out = args.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT / 'reports'):
        raise ValueError('Fresh reports output required')
    src = args.source.resolve()
    package = ROOT / 'reports/xnu-first-entry/entry-probe-54-strategy.json'
    info = json.loads(package.read_bytes())
    kernel = ROOT / 'out/trial-boot/xnu-entry-probe-54-strategy-r4/readback-kernel.macho'
    adt = kernel.with_name('readback-kernel.macho.adt')
    if sha(kernel) != info['kernel_sha256'] or sha(adt) != info['read_file_sha256']:
        raise ValueError('Current readback identity mismatch')
    raw = kernel.read_bytes()
    image = A.B.macho(raw)
    spec = importlib.util.spec_from_file_location('adt', ROOT / 'scripts/check-nuwa-adt.py')
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    memory = reader.decode(adt.read_bytes())['/device-tree/chosen/memory-map']['properties']
    planpath = ROOT / 'out/earlysec-2026-10-24/emission.json'
    if sha(planpath) != A.PLAN_SHA:
        raise ValueError('Prelink provenance changed')
    plan = json.loads(planpath.read_bytes())
    parser_path = Path('D:/Code/PortingiOSLegacy/common/sources/UniXNU/kits/NativePrelink/native_prelink.py')
    parser_spec = importlib.util.spec_from_file_location('storage_prelink', parser_path)
    parser = importlib.util.module_from_spec(parser_spec)
    parser_spec.loader.exec_module(parser)
    donor_path = Path('D:/Code/PortingiOSLegacy/nuwa/artifacts/ios16-donor-inspection/20261020T115253317035Z/original-iphone-kernelcache.macho')
    donor = donor_path.read_bytes()
    if hashlib.sha256(donor).hexdigest() != plan['original_sha256']:
        raise ValueError('Donor identity changed')
    donor_image = parser.macho(donor)
    info_seg = next(s for s in donor_image['segments'] if s['name'] == '__PRELINK_INFO')
    info_at = parser.backed_offset(donor_image['segments'], info_seg['va'], info_seg['filesize'], len(donor))
    metadata = parser.unserialize_xml(donor[info_at:info_at + info_seg['filesize']])
    storage_metadata = next(e for e in metadata['_PrelinkInfoDictionary'] if e['CFBundleIdentifier'] == 'com.apple.iokit.IOStorageFamily')
    ext = next(e for e in plan['extents'] if e['module'] == 'com.apple.iokit.IOStorageFamily' and e['segment'] == '__TEXT_EXEC')
    start = A.B.backed(image, ext['va'], ext['size'])
    storage_sha = hashlib.sha256(raw[start:start + ext['size']]).hexdigest()
    files = [src / name for name in ('NativeRamBlock.cpp', 'SparseDisk.h', 'SeedDisk.h', 'DirectDisk.h', 'PersistOverlay.h', 'LICENSE')]
    paths = [ROOT / 'patches/xnu-8796-candidates/native-aes-personality.patch',
             ROOT / 'patches/xnu-8796-candidates/offline-owner-systemos-mount.patch',
             Path('D:/Code/PortingiOSLegacy/common/sources/UniXNU/scripts/build-native-virtio-bindings.py'),
             Path('D:/Code/PortingiOSLegacy/common/sources/UniXNU/scripts/audit-storage-interface.py')]
    corepath = ROOT / 'reports/desktop-readiness/2026-10-29-ramblock-core-r3/qualification.json'
    core = json.loads(corepath.read_bytes())
    if not core['small_volatile_core_passed']:
        raise ValueError('Core qualification not passed')
    for name, digest in core['source_files'].items():
        if sha(src / name) != digest:
            raise ValueError('Core input changed: ' + name)
    raw_os = json.loads((ROOT / 'reports/desktop-readiness/2026-10-27-raw-os-r1/qualification.json').read_bytes())
    report = dict(scope='Current readback and source integration evidence; no native ABI/link/mount qualification',
        current_kernel_sha256=sha(kernel), current_adt_sha256=sha(adt),
        donor_storage_metadata=storage_metadata, donor_sha256=plan['original_sha256'],
        named_provider_symbols={k:hex(v) for k,v in image['symbols'].items()
            if any(t in k for t in ('NativeRamBlock', 'native_ram_block', 'native_ufs_store'))},
        named_storage_class_symbols={k:hex(v) for k,v in image['symbols'].items() if 'IOBlockStorageDevice' in k},
        original_storage_text=dict(sha256=storage_sha, expected=plan['original_executable_sha256']['com.apple.iokit.IOStorageFamily'],
            unchanged=storage_sha == plan['original_executable_sha256']['com.apple.iokit.IOStorageFamily']),
        loader_ranges={k:dict(bytes=len(memory[k]), zero_placeholder=not any(memory[k]))
            for k in ('RAMDisk','PackedRAMDisk') if k in memory},
        core_qualification=dict(path=str(corepath.relative_to(ROOT)), sha256=sha(corepath)),
        root_reference=dict(path=raw_os['raw_os']['path'], bytes=raw_os['raw_os']['bytes'],
            uuid=raw_os['system_volume_uuid'], scope='Prior qualified input, not rehashed or deployed in this audit'),
        proposed_route=dict(root='Separate OS/SystemOS read-only block windows and IOMedia UUID matching',
            data='Existing 1 GiB logical packed seed, volatile small-disk path; sole PackedRAMDisk',
            exclusions=['Do not append PackedRAMDisk to existing RestoreRAMDisk handoff',
                        'Do not load 5635081728-byte raw OS through the dense 2 GiB RAMDisk path',
                        'No persistence or board-memory changes implied']),
        pending=['Target iOS16 IOStorageFamily vtable/constructor/destructor/metaclass ABI qualification',
                 'Real target headers/compiler and NativeRamBlock object/archive; no fake declarations or iOS17 alias transfer',
                 'Final link imports, metaclass initialization and enabled IOResources/IOBSD personality',
                 'Qualified root block transport; UFS runtime not accepted by this offline work',
                 'Loader-owned Data range/reservation plus writable-page memory budget',
                 'iOS16 APFS mount argument ABI, UUID consumer and /private/var mount result',
                 'Data file/ACL/protection/initialization closure beyond the existing empty directories'],
        files=[dict(path=str(p), sha256=sha(p)) for p in files + paths + [package, planpath, parser_path, Path(__file__)]],
        deployable=False, hardware_executed=False, kernel_modified=False, release_guard_changed=False)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('named_provider_symbols','original_storage_text','loader_ranges','deployable')}))


if __name__ == '__main__':
    main()
