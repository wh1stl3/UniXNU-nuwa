#!/usr/bin/env python3
"""Inventory the existing NativeUfs object's imports against pinned local inputs."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
TREE = Path('/root/nuwa-pmap-ret-native-20261111/nuwa/ios-16.7.16-20H392/nuwa_pmap_ret/tree')
sys.path.insert(0, str(TREE / 'kits/XnuPrelink'))
import native_prelink as np

OBJECT = ROOT / 'out/ufs-host-20261113/NativeUfs.o'
NATIVE = ROOT / 'out/nuwa-pmgr-kernel-20261113-r5/native.macho'
PRELINK = ROOT / 'out/nuwa-pmgr-kernel-20261113-r5/prelink.macho'
LINKMAP = ROOT / 'out/nuwa-pmgr-kernel-20261113-r5/native-link.map'
DONOR = Path('/mnt/d/Code/PortingiOS/UniXNU/out/ipsw/20H392/kernelcache.decompressed')
NM = '/usr/bin/llvm-nm'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def by_name(raw):
    return {name: address for address, names in np.exports(raw, np.macho(raw)).items() for name in names}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    if not out.is_relative_to((ROOT / 'out').resolve()) or out.exists():
        raise SystemExit('Require a fresh output directory inside out/')
    obj, native, prelink, donor = OBJECT.read_bytes(), NATIVE.read_bytes(), PRELINK.read_bytes(), DONOR.read_bytes()
    if sha(obj) != 'f673df6258caa1e41f84526ba054ddf7241961f2c42e899683ce54b2c88cac01':
        raise SystemExit('Unexpected NativeUfs object')
    imports = subprocess.check_output([NM, '-u', str(OBJECT)], text=True).splitlines()
    if len(imports) != 269 or len(set(imports)) != 269:
        raise SystemExit('Unexpected object import list')
    native_exports = by_name(native)
    prelink_exports = by_name(prelink)
    donor_exports = by_name(donor)
    objects, symbols = {}, {}
    for line in LINKMAP.read_text(errors='surrogateescape').splitlines():
        match = re.match(r'^\[\s*(\d+)\] (.+)$', line)
        if match:
            objects[int(match[1])] = match[2]
            continue
        match = re.match(r'^0x([0-9A-Fa-f]+)\s+0x[0-9A-Fa-f]+\s+\[\s*(\d+)\] (\S+)$', line)
        if match and match[3] in imports:
            symbols.setdefault(match[3], []).append((int(match[1], 16), int(match[2])))
    img = np.macho(donor)
    info = next(s for s in img['segments'] if s['name'] == '__PRELINK_INFO')
    at = np.backed_offset(img['segments'], info['va'], info['filesize'], len(donor))
    entries = np.unserialize_xml(donor[at:at + info['filesize']])['_PrelinkInfoDictionary']
    storage, = [e for e in entries if e.get('CFBundleIdentifier') == 'com.apple.iokit.IOStorageFamily']
    module = np.macho(donor, np.backed_offset(img['segments'], storage['_PrelinkExecutableLoadAddr'], 32, len(donor)))
    storage_exports = {name: address for address, names in np.exports(donor, module).items() for name in names}
    verified = {
        '_vr_open': 'kits/VerifiedRoot/src/verified_root.c',
        '_vr_verify_block': 'kits/VerifiedRoot/src/verified_root.c',
        '_vr_xnu_crypto': 'kits/VerifiedRoot/adapters/xnu_crypto.c',
        '_verified_root_key': 'generated RootAnchor.c: build-sheng-source-storage.py:160-166',
        '_verified_root_policies': 'policy table input: build-verified-root-probe.py:95-118',
        '_verified_root_policy_count': 'policy table input: build-verified-root-probe.py:95-118',
    }
    rows = []
    for name in imports:
        matches = symbols.get(name, [])
        locations = [{'address': hex(address), 'object': objects[index]} for address, index in matches]
        row = {'symbol': name, 'native_final_export': hex(native_exports[name]) if name in native_exports else None,
               'current_prelink_export': hex(prelink_exports[name]) if name in prelink_exports else None,
               'native_link_map_definitions': locations,
               'donor_parent_export': hex(donor_exports[name]) if name in donor_exports else None,
               'donor_storage_export': hex(storage_exports[name]) if name in storage_exports else None}
        if name in native_exports:
            if not any(address == native_exports[name] for address, _ in matches):
                raise SystemExit('Export lacks matching link-map definition: ' + name)
            if prelink_exports.get(name) != native_exports[name]:
                raise SystemExit('Current prelink export changed or missing: ' + name)
            row.update(provider='8796 final native exported definition', linkable='yes, for static-link provider; ABI not tested', gap='final integration not linked')
        elif name in verified:
            row.update(provider=verified[name], linkable='conditional: provider not in current native kernel', gap='build provider and validate its own dependencies and policy inputs')
        elif 'IOBlockStorageDevice' in name:
            row.update(provider='com.apple.iokit.IOStorageFamily, donor metadata only; individual symbol not exposed', linkable='no identified definition', gap='derive exact symbol/address and qualify same-donor class ABI')
        elif name == '_boot_progress_poll':
            row.update(provider='optional weak import: NativeUfs.cpp:46-55,1894-1896', linkable='no current definition; linker behavior not tested', gap='provide a reviewed weak nonblocking no-op if final kernel linker requires one')
        elif matches:
            for _, index in matches:
                path = Path(objects[index])
                defined = subprocess.check_output([NM, '-g', '--defined-only', str(path)], text=True)
                if not any(line.split()[-1:] == [name] for line in defined.splitlines()):
                    raise SystemExit('Map provider object does not define global ' + name)
            row.update(provider='8796 linked native object, hidden from final exports', linkable='yes when linking same native object; not a final export', gap='must resolve in final static kernel link')
        else:
            row.update(provider='not located in examined inputs', linkable='no identified definition', gap='locate actual provider')
        rows.append(row)
    result = {'scope': 'host-only symbol inventory; no linker run or ABI/runtime qualification',
              'object_sha256': sha(obj), 'native_sha256': sha(native), 'prelink_sha256': sha(prelink), 'donor_sha256': sha(donor),
              'link_map_sha256': sha(LINKMAP.read_bytes()), 'storage_metadata': {
                  key: storage.get(key) for key in ('CFBundleIdentifier', 'CFBundleVersion', 'OSBundleRequired',
                      'OSBundleLibraries', '_PrelinkBundlePath', '_PrelinkExecutableLoadAddr', '_PrelinkExecutableSize')},
              'storage_module_external_symbol_count': len(storage_exports),
              'counts': dict(Counter(r['provider'] for r in rows)), 'symbols': rows}
    out.mkdir(parents=True)
    (out / 'symbols.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'imports': len(rows), 'counts': result['counts'], 'output': str(out / 'symbols.json')}, indent=2))


if __name__ == '__main__':
    main()
