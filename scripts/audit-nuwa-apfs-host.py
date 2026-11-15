#!/usr/bin/env python3
"""Final APFS binding/descriptor audit, reusing pinned native parser and UFS audit."""
import argparse
import json
import plistlib
from pathlib import Path
import struct
import subprocess
import sys

sys.dont_write_bytecode = True
from importlib.util import spec_from_file_location, module_from_spec

ROOT = Path(__file__).resolve().parents[1]


def load(path, name):
    spec = spec_from_file_location(name, path)
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def check_binding(B, raw, row):
    actual, = struct.unpack('<Q', B.read(raw, row['new_site'], 8))
    assert actual == row['new_target'], f"binding {row['new_site']:#x}"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build', type=Path, required=True)
    p.add_argument('--report', type=Path, required=True)
    a = p.parse_args()
    out = a.build.resolve()
    B = load(ROOT / 'scripts/build-nuwa-pmgr-kernel.py', 'apfs_audit_pmgr')
    prov = json.loads((out / 'provenance.json').read_text())
    # Legacy audit expects this basename. Copy only the immutable reviewed bytes;
    # do not transform new objects or modify the concurrent verifier's sources.
    late = Path(prov['ufs_late']['path']).read_bytes()
    destination = out / 'NativeUfs.late.o'
    if destination.exists():
        assert destination.read_bytes() == late
    else:
        destination.write_bytes(late)
    legacy = ROOT / 'out/nuwa-ufs-link-20261113-c1'
    audit_source = (legacy / 'audit.py').read_text()
    assert audit_source.count('vfs_bridge_added=False') == 1
    audit_source = audit_source.replace('vfs_bridge_added=False', 'vfs_bridge_added=True')
    # Preserve every inherited assertion, changing only the descriptive field.
    private = out / 'ufs-audit.py'
    private.write_text(audit_source)
    env = dict(__import__('os').environ, PYTHONPATH=str(legacy), PYTHONDONTWRITEBYTECODE='1')
    subprocess.run([sys.executable, '-B', str(private), '--build', str(out),
                    '--report', str(out / 'ufs-link-audit.json')], env=env, check=True)
    pmgr_source = (ROOT / 'scripts/audit-nuwa-pmgr-kernel.py').read_text()
    replacements = {
        "ROOT = Path(__file__).resolve().parents[1]": f'ROOT = Path({str(ROOT)!r})',
        "assert prelink['components'] == previous['components']":
        "assert set(prelink['components']) == set(previous['components']) | {'com.apple.filesystems.apfs'}",
    }
    for before, after in replacements.items():
        assert pmgr_source.count(before) == 1
        pmgr_source = pmgr_source.replace(before, after)
    pmgr = out / 'pmgr-audit.py'
    pmgr.write_text(pmgr_source)
    subprocess.run([sys.executable, '-B', str(pmgr),
                    '--build', str(out), '--python-tools', '/home/wh1stl3/.local/lib/python3.10/site-packages'],
                   env=env, check=True)
    raw = (out / 'kernel.macho').read_bytes()
    native = (out / 'native.macho').read_bytes()
    ns = B.names(raw)
    symbol_section, = [s for seg in B.macho(raw)['segments'] for s in seg['sections']
                       if s['name'] == '__symbolsets']
    metadata = plistlib.loads(B.read(raw, symbol_section['va'], symbol_section['size']))
    bsd, = [s for s in metadata['SymbolsSets'] if s['CFBundleIdentifier'] == 'com.apple.kpi.bsd']
    assert {'SymbolName': '_vfs_getvfs_with_vfsops'} in bsd['Symbols']
    plan = json.loads((out / 'prelink.json').read_text())
    for row in plan['bindings']:
        check_binding(B, raw, row)
    old_plan = json.loads((ROOT / 'out/nuwa-ufs-link-20261113-c1/run/prelink.json').read_text())
    added = sorted(set(plan['components']) - set(old_plan['components']))
    assert 'com.apple.filesystems.apfs' in added
    assert 'com.apple.kec.Libm' not in added
    assert 'com.apple.iokit.IOAVFamily' not in added
    assert 'com.apple.iokit.IOMobileGraphicsFamily' not in added
    apfs = [r for r in plan['bindings'] if r['module'] == 'com.apple.filesystems.apfs']
    bridge = [r for r in apfs if r['new_target'] == ns['_vfs_getvfs_with_vfsops']]
    assert bridge and all(r['kind'] == 'kernel' for r in bridge)
    # Descriptor offsets are assigned at vfs_op_init, not preinitialized in file.
    # Audit pointer identity against the actual native registration table instead.
    def qword(va):
        return struct.unpack('<Q', B.read(raw, va, 8))[0]
    registry = []
    cursor = ns['_vfs_op_descs']
    while qword(cursor):
        descriptor = qword(cursor)
        assert descriptor not in registry
        registry.append(descriptor)
        cursor += 8
    assert registry[0] == ns['_vnop_default_desc']
    active = [va for va in registry if not struct.unpack('<I', B.read(raw, va + 16, 4))[0] & 0x10000]
    names = {va: n for n, va in ns.items() if n.startswith('_vnop_') and n.endswith('_desc')}
    descriptor_rows = []
    _, am = B.module(raw, 'com.apple.filesystems.apfs')
    for row in apfs:
        if row['new_target'] not in names:
            continue
        name = names[row['new_target']]
        assert row['new_target'] in registry, name
        # vnodeopv_entry_desc is { descriptor*, implementation* }. Distinguish
        # entries from GOT references by verifying the following word is actual
        # APFS/native code (default entries import native vn_default_error).
        implementation = qword(row['new_site'] + 8)
        code = any(s['initprot'] & 4 and s['va'] <= implementation < s['va'] + s['filesize']
                   for s in [*am['segments'], *B.macho(native)['segments']])
        descriptor_rows.append(dict(symbol=name, site=hex(row['new_site']),
                                    descriptor=hex(row['new_target']),
                                    registry_index=active.index(row['new_target']) if row['new_target'] in active else None,
                                    entry_implementation=hex(implementation) if code else None))
    assert descriptor_rows
    entries = [r for r in descriptor_rows if r['entry_implementation'] is not None]
    assert entries and any(r['symbol'] == '_vnop_default_desc' for r in entries)
    # Recover contiguous vnodeopv_entry_desc arrays and their actual relocated
    # opv_desc_ops references. No hardcoded donor VAs or fileset fixture aliases.
    entries.sort(key=lambda r: int(r['site'], 16))
    groups = []
    for entry in entries:
        site = int(entry['site'], 16)
        if not groups or site != int(groups[-1][-1]['site'], 16) + 16:
            groups.append([])
        groups[-1].append(entry)
    vectors = []
    non_entry_references = []
    for group in groups:
        start = int(group[0]['site'], 16)
        end = int(group[-1]['site'], 16) + 16
        references = [r for r in apfs if r['new_target'] == start and r['kind'] == 'component']
        if not references:
            # A GOT descriptor import can be adjacent to an unrelated code
            # import. It is not an op array without an opv_desc_ops reference.
            assert not any(r['symbol'] == '_vnop_default_desc' for r in group)
            non_entry_references.extend(group)
            continue
        assert qword(end) == 0, 'unterminated vnode operation entry array'
        assert any(r['symbol'] == '_vnop_default_desc' for r in group)
        descriptors = []
        for ref in references:
            descriptor = ref['new_site'] - 8
            vector_pointer = qword(descriptor)
            assert any(s['initprot'] & 2 and s['va'] <= vector_pointer < s['va'] + s['size'] for s in am['segments'])
            registration = [r for r in apfs if r['new_target'] == descriptor and r['kind'] == 'component']
            assert registration, 'missing vnodeopv_desc registration pointer'
            descriptors.append(dict(va=hex(descriptor), vector_pointer=hex(vector_pointer), registration_slots=registration))
        vectors.append(dict(entries_va=hex(start), entries=len(group), descriptors=descriptors))
    donor = Path(prov['donor']['path']).read_bytes()
    _, original_apfs = B.module(donor, 'com.apple.filesystems.apfs')
    apfs_code_bytes = 0
    for oldseg in original_apfs['segments']:
        if not oldseg['initprot'] & 4 or not oldseg['filesize']:
            continue
        expected = bytearray(B.read(donor, oldseg['va'], oldseg['filesize']))
        for row in apfs:
            if oldseg['va'] <= row['site'] < oldseg['va'] + oldseg['filesize']:
                struct.pack_into('<Q', expected, row['site'] - oldseg['va'], row['new_target'])
        assert B.read(raw, oldseg['va'] + plan['slide'], len(expected)) == expected
        apfs_code_bytes += len(expected)
    mapped = sorted((s for s in B.macho(raw)['segments'] if s['size']), key=lambda s: s['va'])
    for seg in mapped:
        assert seg['filesize'] <= seg['size'] and seg['fileoff'] + seg['filesize'] <= len(raw)
    assert all(left['va'] + left['size'] <= right['va'] for left, right in zip(mapped, mapped[1:]))
    # The generic UFS/PMGR audits are separately rerun against the same bytes.
    for key in ('native', 'native_map', 'prelink', 'output', 'vfs_object', 'vfs_patch'):
        assert B.record(Path(prov[key]['path'])) == prov[key], key
    for r in prov['apfs_inputs']:
        assert B.record(Path(r['path'])) == r
    result = dict(status='self-checked', kernel=B.record(out / 'kernel.macho'),
                  added_components=added, apfs_bindings=len(apfs), all_donor_bindings=len(plan['bindings']),
                  vfs_bridge_import_slots=bridge, descriptors=descriptor_rows,
                  registry_entries=len(registry), active_registry_entries=len(active),
                  entry_pairs=sum(v['entries'] for v in vectors), non_entry_descriptor_refs=non_entry_references,
                  vnode_vectors=vectors, apfs_executable_bytes_preserved=apfs_code_bytes,
                  final_macho_ranges_checked=True, embedded_bsd_export=True,
                  descriptor_index_source='native vfs_op_descs; assigned by vfs_op_init at runtime',
                  runtime_registration_executed=False, runtime_abi_qualified=False,
                  ufs_inactive=True, deployable=False)
    a.report.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('status', 'added_components', 'apfs_bindings', 'entry_pairs')}, indent=2))


if __name__ == '__main__':
    main()
