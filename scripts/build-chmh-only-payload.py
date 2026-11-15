"""Derive one experimental unauthenticated CHMH-only FAT; never boot it."""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import tomllib
from pathlib import Path

import nuwa_launch_context as C

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT / 'out/owner-pmap-ret-continuation-verifier-final-20261111'
FAT = PARENT / 'build/nuwa/ios-16.7.16-20H392/nuwa/payload/payload.img'
ADT = PARENT / 'adt-generation/final.adt'
RECORD = PARENT / 'adt-generation/record.json'
LOADER = ROOT / '.cache/boot-stage12-v4-r4.img'
PINS = {'fat': '9ff5c2720a1af341b66e8417a3308fc0a3be9e561c3406e7db157d05e523d04c',
        'kernel': '7fd3d933aae66d8e34a0d3ebfa142137978976d7521e04cef20321109750b6f4',
        'parent-adt': '885094de4597fb2d1734ba4092c805968097d021c8f482653b238436586d27a4',
        'parent-record': 'a7ca5cc8a15353a9dee8882a1f89e0633a44ff950514ebe6ad58c4567ac20b57',
        'loader': '692cfcca51af81230fecbba15425cf598182fbe53abb362b6046dec0f24dc2e5',
        'trust': '367e051548f9f0407fa9fe9d40007fa4e7c5ff27c45f5a7a30cedf344e24d98e',
        'config': '7b2ac4be356c5b6070b887057aa734219e45b70767a6d6faf1307b712576e931'}
EXPECTED_DIGEST = bytes.fromhex('ee2ea17b52b5ddd93962546e2e0824e5eac51f6570ef3f39e937d20684e9fc1d6c23895f3b9ac7e086619ffd416b474d')
MEMBERS = {'kernel': 'Payloads/kernel.macho', 'parent-adt': 'Payloads/kernel.macho.adt',
           'trust': 'Payloads/kernel.macho.trustcache', 'config': 'unixnu.toml'}
sha = lambda data: hashlib.sha256(data).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest_material(inputs):
    out = bytearray(b'Nuwa.HostBootSetIdentity.v1\0')
    for key in ('kernel', 'loader', 'trust', 'args', 'parent-adt'):
        label = key.encode('ascii')
        out.extend(bytes([len(label)]) + label + hashlib.sha256(inputs[key]).digest())
    raw = bytes(out)
    return raw, hashlib.sha384(raw).digest()


def check_inputs(inputs):
    for key, pin in PINS.items():
        require(sha(inputs[key]) == pin, 'Fixed input mismatch: ' + key)
    config = tomllib.loads(inputs['config'].decode())
    entries = [e for e in config['entry'] if e.get('id') == 'xnu']
    require(len(entries) == 1 and entries[0].get('args') == '-v serial=3', 'XNU args mismatch')
    require(inputs['args'] == b'-v serial=3', 'Material args mismatch')
    preimage, digest = digest_material(inputs)
    require(digest == EXPECTED_DIGEST, 'Experiment digest mismatch')
    return preimage, digest


def reject_asmb(tree):
    def walk(node):
        require(C.name(node).lower() != 'asmb', 'ASMB node forbidden')
        for key, _, _ in node['properties']:
            require('smb' not in key.lower() and key.lower() != 'asmb', 'SMB property forbidden')
        for child in node['children']:
            walk(child)
    walk(tree)


def derived(parent, digest):
    tree = C.parse(parent)
    reject_asmb(tree)
    require(C.encode(tree) == parent, 'Parent ADT roundtrip mismatch')
    chosen = C.find(tree, '/chosen')
    require('boot-manifest-hash' not in C.properties(chosen), 'Parent CHMH exists')
    require(C.properties(chosen).get('mix-n-match-prevention-status') == bytes(4), 'AMNM changed')
    require(len(C.properties(C.find(tree, '/chosen/manifest-properties')).get('BNCH', b'')) == 48, 'BNCH mismatch')
    chosen['properties'].append(('boot-manifest-hash', 0, digest))
    return C.encode(tree)


def check_adt(parent, actual, digest):
    tree = C.parse(actual)  # rejects duplicate keys/nodes
    reject_asmb(tree)
    chosen = C.find(tree, '/chosen')
    fields = [p for p in chosen['properties'] if p[0] == 'boot-manifest-hash']
    require(len(fields) == 1 and fields[0] == ('boot-manifest-hash', 0, digest), 'CHMH type/value mismatch')
    require(actual == derived(parent, digest), 'Non-CHMH tree/order/flags changed')


def extract(image, destination):
    destination.mkdir()
    result = subprocess.run(['mcopy', '-s', '-i', str(image), '::/EFI', str(destination)], capture_output=True, text=True)
    require(result.returncode == 0, 'mcopy extraction failed: ' + result.stderr)
    root = destination / 'EFI/UniXNU'
    return {k: (root / path).read_bytes() for k, path in MEMBERS.items()}


def fixed_inputs(members):
    return {'fat': FAT.read_bytes(), 'parent-record': RECORD.read_bytes(), 'loader': LOADER.read_bytes(),
            'args': b'-v serial=3', **members}


def normalize_directory_time(image, parent):
    # Pinned FAT contains one short-name ADT directory entry. Preserve its old
    # creation/access/modification timestamps so mcopy is deterministic.
    name = b'KERNEL~1ADT'
    require(parent.count(name) == 1, 'Parent ADT short directory name not unique')
    offset = parent.index(name)
    require(offset % 32 == 0 and parent[offset + 11] == 0x20, 'Parent ADT directory entry shape')
    raw = bytearray(image.read_bytes())
    require(raw[offset:offset + 11] == name and raw[offset + 11] == 0x20, 'New ADT directory entry moved')
    raw[offset + 13:offset + 20] = parent[offset + 13:offset + 20]
    raw[offset + 22:offset + 26] = parent[offset + 22:offset + 26]
    image.write_bytes(raw)


def measure_layout(inputs, adt):
    spec = importlib.util.spec_from_file_location('layout', ROOT / 'scripts/audit-owner-pmap-ret-package.py')
    layout = importlib.util.module_from_spec(spec); spec.loader.exec_module(layout)
    base, end, _ = layout.vm_layout(inputs['kernel'])
    chosen = C.properties(C.find(C.parse(adt), '/chosen'))
    window = int.from_bytes(chosen['darwinboot-memory-size'], 'little')
    return layout.relative_layout(base, end, len(adt), len(inputs['trust']), window)


def audit(output, parent_members, inputs, readback=None):
    preimage, digest = check_inputs(inputs)
    readback = readback or output / 'readback'
    extracted = extract(output / 'payload.img', readback)
    for key in ('kernel', 'trust', 'config'):
        require(parent_members[key] == inputs[key] and extracted[key] == inputs[key], 'FAT member changed: ' + key)
    require(parent_members['parent-adt'] == inputs['parent-adt'], 'Parent member changed')
    require(extracted['parent-adt'] == (output / 'derived.adt').read_bytes(), 'FAT ADT mismatch')
    check_adt(inputs['parent-adt'], extracted['parent-adt'], digest)
    # Reconstruct from pinned parent rather than trusting synchronized metadata.
    reference_adt = readback / 'expected.adt'
    reference_adt.write_bytes(derived(inputs['parent-adt'], digest))
    os.utime(reference_adt, (946684800, 946684800))
    reference_fat = readback / 'expected-fat.img'
    reference_fat.write_bytes(inputs['fat'])
    command = ['mcopy', '-o', '-i', str(reference_fat), str(reference_adt), '::/EFI/UniXNU/Payloads/kernel.macho.adt']
    result = subprocess.run(command, capture_output=True, text=True)
    require(result.returncode == 0, 'Reference mcopy failed: ' + result.stderr)
    normalize_directory_time(reference_fat, inputs['fat'])
    require(reference_fat.read_bytes() == (output / 'payload.img').read_bytes(), 'FAT differs from fixed-parent reconstruction')
    report = json.loads((output / 'record.json').read_text())
    require(report.get('type') == 'experimental-unauthenticated-boot-set-identity' and
            report.get('profile') == 'chmh-only-20261112-r1' and report.get('device_release') is False and
            report.get('authentication') == 'NOT REACHED', 'Record scope mismatch')
    require(report.get('inputs_sha256') == {k: sha(v) for k, v in inputs.items()}, 'Record input binding mismatch')
    require(report.get('layout') == measure_layout(inputs, extracted['parent-adt']), 'Record layout mismatch')
    require(report['material_hex'] == preimage.hex() and report['chmh_hex'] == digest.hex(), 'Record material mismatch')
    require(report['derived_adt_bytes'] == len(extracted['parent-adt']) and
            report['derived_adt_sha256'] == sha(extracted['parent-adt']) and
            report['payload_sha256'] == sha((output / 'payload.img').read_bytes()), 'Record image hash mismatch')
    return {k: sha(v) for k, v in extracted.items()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    require(out.is_relative_to((ROOT / 'out').resolve()), 'Output outside out/')
    out.mkdir(parents=True, exist_ok=False)
    parent_members = extract(FAT, out / 'parent-readback')
    inputs = fixed_inputs(parent_members)
    require(parent_members['parent-adt'] == ADT.read_bytes(), 'Parent ADT differs from FAT')
    preimage, digest = check_inputs(inputs)
    adt = derived(inputs['parent-adt'], digest)
    check_adt(inputs['parent-adt'], adt, digest)
    (out / 'derived.adt').write_bytes(adt)
    os.utime(out / 'derived.adt', (946684800, 946684800))
    shutil.copyfile(FAT, out / 'payload.img')
    command = ['mcopy', '-o', '-i', str(out / 'payload.img'), str(out / 'derived.adt'), '::/EFI/UniXNU/Payloads/kernel.macho.adt']
    p = subprocess.run(command, capture_output=True, text=True)
    require(p.returncode == 0, 'mcopy replacement failed: ' + p.stderr)
    normalize_directory_time(out / 'payload.img', inputs['fat'])
    positions = measure_layout(inputs, adt)
    record = {'type': 'experimental-unauthenticated-boot-set-identity', 'profile': 'chmh-only-20261112-r1',
              'inputs_sha256': {k: sha(v) for k, v in inputs.items()}, 'material_hex': preimage.hex(),
              'chmh_hex': digest.hex(), 'derived_adt_sha256': sha(adt), 'derived_adt_bytes': len(adt),
              'payload_sha256': sha((out / 'payload.img').read_bytes()), 'layout': positions,
              'authentication': 'NOT REACHED', 'device_release': False, 'mcopy_command': command,
              'mcopy_exit': p.returncode}
    (out / 'record.json').write_text(json.dumps(record, indent=2) + '\n')
    result = audit(out, parent_members, inputs)
    (out / 'readback.json').write_text(json.dumps({'members_sha256': result, 'status': 'self-checked'}, indent=2) + '\n')
    print('self-checked', out, record['payload_sha256'], record['derived_adt_sha256'])


if __name__ == '__main__':
    main()
