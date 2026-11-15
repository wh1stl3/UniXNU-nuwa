#!/usr/bin/env python3
"""Small incremental checks; no signature, block image or APFS identity matrix."""
import argparse
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--build', type=Path, required=True)
    a = p.parse_args()
    for name in ('build-nuwa-apfs-host.py', 'audit-nuwa-apfs-host.py', 'test-nuwa-apfs-host.py'):
        ast.parse((ROOT / 'scripts' / name).read_text(), filename=name)
    B = load(ROOT / 'scripts/build-nuwa-pmgr-kernel.py', 'apfs_test_parser')
    A = load(ROOT / 'scripts/audit-nuwa-apfs-host.py', 'apfs_test_audit')
    out = a.build.resolve()
    raw = (out / 'kernel.macho').read_bytes()
    ns = B.names(raw)
    plan = json.loads((out / 'prelink.json').read_text())
    row = next(r for r in plan['bindings'] if r['module'] == 'com.apple.filesystems.apfs'
               and r['new_target'] == ns['_vfs_getvfs_with_vfsops'])
    A.check_binding(B, raw, row)
    bad = bytearray(raw)
    at = B.backed_offset(B.macho(raw)['segments'], row['new_site'], 8, len(raw))
    struct.pack_into('<Q', bad, at, row['new_target'] ^ 4)
    try:
        A.check_binding(B, bytes(bad), row)
    except AssertionError:
        pass
    else:
        raise AssertionError('corrupt VFS import slot was accepted')
    report = json.loads((out / 'apfs-audit.json').read_text())
    assert report['runtime_registration_executed'] is False
    assert report['runtime_abi_qualified'] is False
    assert report['ufs_inactive'] is True
    result = dict(status='self-checked', ast_files=3, valid_bridge_binding=True,
                  corrupt_bridge_slot_rejected=True, no_runtime_claim=True)
    (out / 'incremental-tests.json').write_text(json.dumps(result, indent=2) + '\n')
    # Manifest contains only small host artifacts, never the root block image.
    paths = [ROOT / 'scripts' / name for name in
             ('build-nuwa-apfs-host.py', 'audit-nuwa-apfs-host.py', 'test-nuwa-apfs-host.py')]
    paths += [ROOT / 'docs/nuwa-apfs-host-20261113.md']
    paths += [out / name for name in
              ('kernel.macho', 'native.macho', 'native-link.map', 'prelink.macho', 'prelink.json',
               'provenance.json', 'commands.json', 'apfs-audit.json', 'ufs-link-audit.json',
               'audit.json', 'startup-audit.json', 'renderer-manifest.json', 'incremental-tests.json',
               'ufs-audit.py', 'pmgr-audit.py', 'symbolsets.plist')]
    records = [dict(path=str(path), bytes=path.stat().st_size,
                    sha256=hashlib.sha256(path.read_bytes()).hexdigest()) for path in paths]
    (out / 'delivery.json').write_text(json.dumps(dict(status='self-checked', files=records), indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
