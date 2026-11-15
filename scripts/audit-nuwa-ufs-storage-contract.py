#!/usr/bin/env python3
"""Same-donor, layout-bound storage annotations only; never link a kernel."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import shlex
import struct
import subprocess
import sys
from types import SimpleNamespace

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
TREE = Path('/root/nuwa-pmap-ret-native-20261111/nuwa/ios-16.7.16-20H392/nuwa_pmap_ret/tree')
sys.path.insert(0, str(TREE / 'kits/XnuPrelink'))
sys.path.insert(0, '/home/wh1stl3/.local/lib/python3.10/site-packages')
import native_prelink as np
import capstone as C


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def names(raw):
    return {n: va for va, ns in np.exports(raw, np.macho(raw)).items() for n in ns}


def backed(image, va, size=1):
    return np.backed_offset(image['segments'], va, size, image['raw_size'])


def image(raw):
    result = np.macho(raw)
    result.update(symbols=names(raw), raw_size=len(raw))
    return result


def functions(path, wanted, namespace):
    """Reuse historical functions without executing their fixed legacy setup."""
    tree = ast.parse(path.read_text())
    tree.body = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in wanted]
    require({n.name for n in tree.body} == set(wanted), 'Historical helper missing')
    exec(compile(tree, str(path), 'exec'), namespace)
    return namespace


def object_table(path, classname):
    # Relocation annotation method from audit-ramblock-production-abi.py:19-43
    # and official audit-storage-interface.py:63-93, with actual iOS17 deployment.
    raw = path.read_bytes()
    obj = np.macho(raw)
    require(obj['kind'] == 1, 'Expected annotation/transport object')
    version = next(at for cmd, at, _ in obj['commands'] if cmd == 0x32)
    require(struct.unpack_from('<II', raw, version+8) == (2, 0x110000), 'Actual iOS17 deployment required')
    at = next(at for cmd, at, _ in obj['commands'] if cmd == 2)
    sy, count, st, _ = struct.unpack_from('<4I', raw, at+8)
    symbols = []
    for i in range(count):
        ix, kind, _, desc, value = struct.unpack_from('<IBBHQ', raw, sy+i*16)
        symbols.append(dict(name=raw[st+ix:raw.index(b'\0', st+ix)].decode(), value=value, kind=kind, desc=desc))
    v = next(s['value'] for s in symbols if s['name'] == '__ZTV'+str(len(classname))+classname)
    rel = {}
    for seg in obj['segments']:
        for sec in seg['sections']:
            if sec['va'] <= v < sec['va']+sec['size']:
                ro, rc = struct.unpack_from('<II', raw, sec['command_offset']+56)
                for i in range(rc):
                    addr, word = struct.unpack_from('<II', raw, ro+i*8)
                    if word >> 27 & 1 and word >> 28 == 0 and word >> 25 & 3 == 3:
                        rel[sec['va']+addr] = symbols[word & 0xffffff]['name']
    methods = []
    while v+16+len(methods)*8 in rel:
        methods.append(rel[v+16+len(methods)*8])
    require(len(methods) == 190, 'Expected exactly 190 slots')
    return methods, symbols


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    out = a.out.resolve()
    require(out.is_relative_to(ROOT/'out') and not out.exists(), 'Fresh out/ required')
    base = ROOT/'out/nuwa-pmgr-kernel-20261113-r5'
    inv = json.loads((ROOT/'out/ufs-symbol-audit-20261113-r2/symbols.json').read_text())
    objpath = ROOT/'out/ufs-host-20261113/NativeUfs.o'
    donorpath = Path('/mnt/d/Code/PortingiOS/UniXNU/out/ipsw/20H392/kernelcache.decompressed')
    raw, donor = (base/'prelink.macho').read_bytes(), donorpath.read_bytes()
    require(inv['donor_sha256'] == '2ec297bac95bcba01046fd0148e97e7e5885c05a6c18827f39f534ba375c1221', 'Pinned 20H392 donor')
    require(inv['object_sha256'] == 'f673df6258caa1e41f84526ba054ddf7241961f2c42e899683ce54b2c88cac01', 'Pinned NativeUfs')
    require(inv['prelink_sha256'] == '62d3efb13d8fcf59fd38c5095cb0a33ca1ba6d109ea2e6aab285ffaaeb6f581a', 'Pinned current r5 layout')
    require(sha(raw) == inv['prelink_sha256'] and sha(donor) == inv['donor_sha256'], 'Donor/prelink identity')
    require(sha(objpath.read_bytes()) == inv['object_sha256'], 'Preserved NativeUfs identity')
    plan = json.loads((base/'prelink.json').read_text())
    require(plan['original_sha256'] == sha(donor), 'Prelink provenance')
    source = TREE/'refer/IOStorageFamily'
    revision = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    require(revision == 'e45fbe30a7879e0b16e26dddb78538f1b00e0bff', 'Storage source pin')
    header_record = json.loads((TREE/'build/storage-abi/headers.json').read_text())
    for name, digest in header_record['headers'].items():
        require(sha((TREE/'build/storage-abi/include/IOKit/storage'/name).read_bytes()) == digest, 'Header drift: '+name)
    # No same-configuration reference exists in this build/storage-abi tree.
    # Replay the exact NativeUfs flags, changing ONLY input and output paths.
    lines = (ROOT/'out/ufs-host-20261113/command.txt').read_text().splitlines()
    cwd = shlex.split(lines[0])[1]
    command = shlex.split(lines[1])
    original_command = command.copy()
    source_index = command.index('-xc++')+1
    command[source_index] = str(source/'IOBlockStorageDevice.cpp')
    command[command.index('-o')+1] = str(out/'IOBlockStorageReference.o')
    out.mkdir()
    (out/'reference-command.json').write_text(json.dumps(dict(cwd=cwd, original=original_command, annotation=command), indent=2)+'\n')
    r = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    (out/'reference-compile.log').write_text(r.stdout+r.stderr)
    require(r.returncode == 0, 'Annotation compile failed: see reference-compile.log')
    reference, _ = object_table(out/'IOBlockStorageReference.o', 'IOBlockStorageDevice')
    transport, _ = object_table(objpath, 'NativeUfsBlock')
    md = C.Cs(C.CS_ARCH_ARM64, C.CS_MODE_ARM)
    md.detail = True
    B = SimpleNamespace(macho=image, backed=backed)
    helpers = functions(ROOT/'scripts/read_dispatch_audit.py', ['disasm', 'record', 'stub'], dict(B=B, CS=md, struct=struct))
    A = SimpleNamespace(B=B, CS=md, PLAN=base/'prelink.json', **{k: helpers[k] for k in ('record', 'stub')})
    audit = functions(ROOT/'scripts/audit-ios16-storage-class.py', ['audit'], dict(A=A, struct=struct, json=json, MASK=(1 << 64)-1, require=require))['audit']
    actual = audit(raw)
    require(actual['method_count'] == 190, 'Actual r5 dispatch length')
    allnames = list(dict.fromkeys(reference+transport))
    readable = dict(zip(allnames, subprocess.check_output(['c++filt'], input='\n'.join(n[1:] for n in allnames)+'\n', text=True).splitlines()))
    slots = []
    for i, (ref, trans, row) in enumerate(zip(reference, transport, actual['methods'])):
        if row['native_names']:
            require(ref in row['native_names'], 'Native/reference mismatch at slot '+str(i))
        own = trans.startswith(('__ZN14NativeUfsBlock', '__ZNK14NativeUfsBlock'))
        if ref == '___cxa_pure_virtual':
            require(own, 'Missing concrete implementation at '+str(i))
        elif ref != trans:
            require(own, 'Unexpected inherited target at '+str(i))
            if i not in (0, 1):
                require(readable[ref].split('::', 1)[1] == readable[trans].split('::', 1)[1], 'Override signature mismatch at '+str(i))
        slots.append(dict(slot=i, reference=ref, signature=readable[ref], transport=trans, transport_signature=readable[trans], native_target=row['target'], native_names=row['native_names'], override=own))
    require('___cxa_pure_virtual' not in transport, 'Abstract NativeUfsBlock')
    method_slots = (21, 33, 44, 185, 186, 187, 189)
    bindings = {reference[i]: actual['methods'][i]['target'] for i in method_slots}
    bindings.update({'__ZN20IOBlockStorageDevice10gMetaClassE': actual['metaclass'], '__ZTV20IOBlockStorageDevice': actual['vtable'], '__ZN20IOBlockStorageDeviceC2EPK11OSMetaClass': actual['protected_constructor']['pc'], '__ZN20IOBlockStorageDeviceD2Ev': actual['base_destructor']['pc']})
    expected = {r['symbol'] for r in inv['symbols'] if 'IOBlockStorageDevice' in r['symbol']}
    require(set(bindings) == expected and len(bindings) == 11, 'Exact eleven import contract')
    # Same segment-offset mapping used by the PMGR layout-bound alias builder.
    dm = np.macho(donor)
    info = next(s for s in dm['segments'] if s['name'] == '__PRELINK_INFO')
    at = np.backed_offset(dm['segments'], info['va'], info['filesize'], len(donor))
    entries = np.unserialize_xml(donor[at:at+info['filesize']])['_PrelinkInfoDictionary']
    entry, = [e for e in entries if e.get('CFBundleIdentifier') == 'com.apple.iokit.IOStorageFamily']
    module = np.macho(donor, np.backed_offset(dm['segments'], entry['_PrelinkExecutableLoadAddr'], 32, len(donor)))
    extents = {e['segment']: e for e in plan['extents'] if e['module'] == entry['CFBundleIdentifier']}
    donor_plan = dict(extents=[dict(module=entry['CFBundleIdentifier'], segment=s['name'], va=s['va'], size=s['filesize']) for s in module['segments'] if s['name'] in extents])
    A.PLAN = SimpleNamespace(read_bytes=lambda: json.dumps(donor_plan).encode())
    donor_class = audit(donor)
    A.PLAN = base/'prelink.json'
    require(donor_class['method_count'] == 190, 'Actual donor dispatch length')
    require(donor_class['instance_size'] == actual['instance_size'] == 0x90, 'Actual donor/r5 instance size')
    executable_checks = []
    for seg in module['segments']:
        if not seg['initprot'] & 4 or not seg['filesize']:
            continue
        at = np.backed_offset(dm['segments'], seg['va'], seg['filesize'], len(donor))
        expected_code = bytearray(donor[at:at+seg['filesize']])
        for binding in plan['bindings']:
            if seg['va'] <= binding['site'] < seg['va']+seg['filesize']:
                struct.pack_into('<Q', expected_code, binding['site']-seg['va'], binding['new_target'])
        at = backed(image(raw), extents[seg['name']]['va'], len(expected_code))
        require(raw[at:at+len(expected_code)] == bytes(expected_code), 'Storage executable changed beyond declared prelink bindings')
        executable_checks.append(dict(segment=seg['name'], bytes=len(expected_code), unchanged_except_declared_pointer_bindings=True))
    donor_names = names(donor)
    current_names = names(raw)
    for i, row in enumerate(slots):
        old = int(donor_class['methods'][i]['target'], 16)
        new = int(row['native_target'], 16)
        row['donor_target'] = hex(old)
        if reference[i] in donor_names:
            require(old == donor_names[reference[i]] and new == current_names[reference[i]], 'Inherited native rebinding at '+str(i))
            row['relocation'] = 'same reference symbol, donor kernel -> current native export'
        else:
            old_seg, = [s for s in module['segments'] if s['va'] <= old < s['va']+s['size']]
            require(new == extents[old_seg['name']]['va']+old-old_seg['va'], 'Owned slot segment-offset mapping at '+str(i))
            row['relocation'] = 'same IOStorageFamily segment offset'
    mapped = {}
    for name, value in bindings.items():
        va = int(value, 16)
        extent, = [e for e in extents.values() if e['va'] <= va < e['va']+e['size']]
        segment, = [s for s in module['segments'] if s['name'] == extent['segment']]
        offset = va-extent['va']
        mapped[name] = dict(donor_va=hex(segment['va']+offset), segment=segment['name'], segment_offset=hex(offset), current_r5_prelink_va=hex(va), rebind_on_layout_change=True)
    donor_bindings = {reference[i]: donor_class['methods'][i]['target'] for i in method_slots}
    donor_bindings.update({'__ZN20IOBlockStorageDevice10gMetaClassE': donor_class['metaclass'], '__ZTV20IOBlockStorageDevice': donor_class['vtable'], '__ZN20IOBlockStorageDeviceC2EPK11OSMetaClass': donor_class['protected_constructor']['pc'], '__ZN20IOBlockStorageDeviceD2Ev': donor_class['base_destructor']['pc']})
    require(all(mapped[n]['donor_va'] == va for n, va in donor_bindings.items()), 'Independently identified donor bindings')
    # Reuse the four historical mutations, not the old full transport matrix.
    im = image(raw)
    cases = [('parent', int(actual['metaclass_constructors'][0]['parent_slot'], 16), bytes(8)),
             ('size', int(actual['metaclass_constructors'][0]['pc'], 16)+16, bytes.fromhex('03208052')),
             ('destructor', int(actual['base_destructor']['pc'], 16), bytes.fromhex('c0035fd6')),
             ('slot-replacement', int(actual['vtable'], 16)+16+2*8, bytes(8))]
    negatives = []
    for name, va, replacement in cases:
        changed = bytearray(raw)
        at = backed(im, va, len(replacement))
        changed[at:at+len(replacement)] = replacement
        try:
            audit(bytes(changed))
        except ValueError as error:
            negatives.append(dict(name=name, rejected=True, reason=str(error)))
        else:
            raise ValueError('Mutation accepted: '+name)
    # Adapt build-ramblock-analysis-archive.py's absolute alias and nm check.
    assembly = out/'layout-bound-bindings.S'
    assembly.write_text('// Analysis only; MUST rebind after layout changes.\n'+''.join('.globl '+n+'\n.set '+n+', '+v+'\n' for n, v in sorted(bindings.items())))
    alias_cmd = [original_command[0], '--target=arm64-apple-ios17.0', '-c', str(assembly), '-o', str(out/'layout-bound-bindings.o')]
    subprocess.run(alias_cmd, check=True, capture_output=True)
    listing = subprocess.check_output(['/usr/bin/llvm-nm', '-g', '--defined-only', str(out/'layout-bound-bindings.o')], text=True)
    resolved = {words[2]: int(words[0], 16) for line in listing.splitlines() if len(words := line.split()) == 3 and words[1] == 'A'}
    require(resolved == {n: int(v, 16) for n, v in bindings.items()}, 'Alias value mismatch')
    (out/'aliases-nm.txt').write_text(listing)
    dwarf = subprocess.check_output(['/usr/bin/llvm-dwarfdump', '--name=IOBlockStorageDevice', str(out/'IOBlockStorageReference.o')], text=True)
    (out/'reference-dwarf.txt').write_text(dwarf)
    size = re.search(r'DW_AT_name\s+\("IOBlockStorageDevice"\)[\s\S]{0,200}?DW_AT_byte_size\s+\((0x[0-9a-f]+)\)', dwarf)
    require(size and int(size[1], 16) == actual['instance_size'], 'Reference/donor size mismatch')
    require(sha(objpath.read_bytes()) == inv['object_sha256'], 'NativeUfs must remain unchanged')
    result = dict(status='self-checked', scope='host annotation contract only; no final link, runtime, hardware or VerifiedRoot',
                  object_sha256=sha(objpath.read_bytes()), donor_sha256=sha(donor), prelink_sha256=sha(raw),
                  reference_sha256=sha((out/'IOBlockStorageReference.o').read_bytes()), deployment='iOS17.0 actual LC_BUILD_VERSION, 8796 source flags unchanged',
                  storage_source_revision=revision, bindings=mapped, slots=slots, actual_class=actual, donor_class=donor_class, negative_tests=negatives,
                  compiled_class_size=int(size[1], 16), kernel_resolved_slots=sum(bool(r['native_names']) for r in slots), concrete_overrides=sum(r['override'] for r in slots),
                  executable_checks=executable_checks,
                  sources=[dict(repository='UniXNU/UniXNU', commit='693f5d9cae8a408dd18b39f3f9fdc4228c934241', license='BSD-2-Clause-Patent', use='official audit-storage-interface.py identification method'),
                           dict(repository='UniXNU/XnuPrelink', commit='f1d80d37528a33e24643583787123c652b70a268', license='BSD-2-Clause-Patent', use='existing native_prelink.py parser'),
                           dict(repository='wh1stl3/UniXNU-nuwa', commit='378a27b24318cc34e9b67b034ceccff8496fe774', license='No repository LICENSE found; no external redistribution license asserted', use='historical class audit, production ABI relocation comparison, analysis alias check'),
                           dict(repository='UniXNU/ShengUfs', commit='99d8bcd3e43dd24fc3c8437c67b5d4cc71ab94d0', license='BSD-2-Clause', use='preserved NativeUfs.o input; no source changes'),
                           dict(repository='apple-oss-distributions/IOStorageFamily', commit=revision, license='APSL-2.0', use='local annotation-only IOBlockStorageDevice.cpp and headers; not donor symbol provenance')],
                  aliases_verified=11, alias_command=alias_cmd, final_linked=False, reference_linked=False,
                  evidence=[dict(path=str(f), sha256=sha(f.read_bytes())) for f in [Path(__file__), ROOT/'scripts/audit-ios16-storage-class.py', ROOT/'scripts/audit-ramblock-production-abi.py', ROOT/'scripts/build-ramblock-analysis-archive.py', TREE/'kits/XnuPrelink/native_prelink.py', source/'IOBlockStorageDevice.cpp', TREE/'build/storage-abi/include/TargetConditionals.h']])
    (out/'contract.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(bindings=mapped, slots=len(slots), instance_size=actual['instance_size'], negatives=negatives), indent=2))


if __name__ == '__main__':
    main()
