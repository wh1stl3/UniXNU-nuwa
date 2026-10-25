"""Produce and verify measured inputs for a non-Apple diagnostic launch.

This is a host-produced launch manifest, not an Apple IM4M, TSS ticket or
hardware-authenticated boot identity. Its nonce lasts for one candidate package.
"""
import argparse
import hashlib
import json
import secrets
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = 'Nuwa.DiagnosticLaunch.v1'
CONTEXT_KEY = 'nuwa-launch-manifest'
DOMAIN_KEY = 'nuwa-launch-domain'
POLICY_KEY = 'mix-n-match-prevention-status'
HASH_KEY = 'boot-manifest-hash'
CHOSEN_KEYS = (CONTEXT_KEY, DOMAIN_KEY, POLICY_KEY, HASH_KEY)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode() + b'\n'


def parse(raw):
    if not raw or len(raw) > 16 * 1024 * 1024:
        raise ValueError('Invalid ADT size')

    def read(at, depth):
        if depth > 64 or at + 8 > len(raw):
            raise ValueError('Invalid ADT depth/header')
        count, children = struct.unpack_from('<II', raw, at)
        if count > 4096 or children > 4096:
            raise ValueError('Unbounded ADT counts')
        at += 8
        props = []
        keys = set()
        for _ in range(count):
            if at + 36 > len(raw):
                raise ValueError('Truncated ADT property')
            key = raw[at:at + 32].split(b'\0')[0].decode('ascii')
            flags = struct.unpack_from('<I', raw, at + 32)[0]
            size = flags & 0x7fffffff
            at += 36
            end = at + ((size + 3) & ~3)
            if not key or key in keys or end > len(raw):
                raise ValueError('Invalid ADT property/duplicate')
            if any(raw[at + size:end]):
                raise ValueError('Nonzero ADT property padding')
            props.append((key, flags & 0x80000000, raw[at:at + size]))
            keys.add(key)
            at = end
        node = {'properties': props, 'children': []}
        child_names = set()
        for _ in range(children):
            child, at = read(at, depth + 1)
            child_name = name(child)
            if child_name in child_names:
                raise ValueError('Duplicate ADT child')
            node['children'].append(child)
            child_names.add(child_name)
        return node, at

    tree, end = read(0, 0)
    if end != len(raw):
        raise ValueError('ADT trailing bytes')
    return tree


def name(node):
    value = properties(node).get('name')
    if not value or not value.endswith(b'\0'):
        raise ValueError('ADT node lacks a terminated name')
    return value[:-1].decode('ascii')


def properties(node):
    return {key: value for key, flags, value in node['properties']}


def find(tree, path):
    node = tree
    for part in path.strip('/').split('/') if path != '/' else ():
        matches = [child for child in node['children'] if name(child) == part]
        if len(matches) != 1:
            raise ValueError('Missing/duplicate ADT node ' + path)
        node = matches[0]
    return node


def encode(tree):
    data = bytearray(struct.pack('<II', len(tree['properties']), len(tree['children'])))
    for key, flags, value in tree['properties']:
        key_raw = key.encode('ascii')
        if not 0 < len(key_raw) <= 31 or len(value) > 1024 * 1024:
            raise ValueError('Invalid ADT field extent')
        data += struct.pack('<32sI', key_raw, flags | len(value))
        data += value + bytes(-len(value) % 4)
    for child in tree['children']:
        data += encode(child)
    return bytes(data)


def measurement(path):
    raw = Path(path).read_bytes()
    return {'bytes': len(raw), 'sha256': sha256(raw)}


def create(base_adt, kernel, fd, shim, work):
    work = Path(work).resolve()
    if not work.is_relative_to(ROOT / 'out') or work.exists():
        raise ValueError('Fresh context directory under out/ required')
    base = Path(base_adt).read_bytes()
    tree = parse(base)
    chosen = find(tree, '/chosen')
    manifest_props = find(tree, '/chosen/manifest-properties')
    if any(k in properties(chosen) for k in CHOSEN_KEYS) or 'BNCH' in properties(manifest_props):
        raise ValueError('Refuse to replace an existing platform/firmware identity')
    if encode(tree) != base:
        raise ValueError('ADT round-trip differs')
    # Independent fresh nonce; do not reuse the kernel entropy/random-seed.
    nonce = secrets.token_bytes(32)
    nonce_hash = hashlib.sha384(nonce).digest()
    manifest = {
        'format': DOMAIN, 'platform': 'nuwa/SM8550/iOS16/8796 diagnostic',
        'components': {'kernel': measurement(kernel), 'firmware_fd': measurement(fd),
                       'boot_shim': measurement(shim),
                       'base_adt': {'bytes': len(base), 'sha256': sha256(base)}},
        'nonce': {'producer': 'Python secrets.token_bytes(32), host OS CSPRNG',
                  'bytes': 32, 'hash_algorithm': 'SHA-384', 'hash': nonce_hash.hex(),
                  'lifetime': 'one candidate package; not one hardware boot'},
        'mix_n_match_prevention_status': 1,
        'trust': {'manifest_authentication': 'none; host launch measurement',
                  'apple_im4m': False, 'tss_personalized': False,
                  'hardware_nonce_protection': False, 'anti_replay_enforced': False}}
    manifest_bytes = canonical(manifest)
    manifest_hash = hashlib.sha384(manifest_bytes).digest()
    chosen['properties'] += [(DOMAIN_KEY, 0, DOMAIN.encode() + b'\0'),
                             (CONTEXT_KEY, 0, manifest_bytes),
                             (POLICY_KEY, 0, struct.pack('<I', 1)),
                             (HASH_KEY, 0, manifest_hash)]
    manifest_props['properties'].append(('BNCH', 0, nonce_hash))
    adt = encode(tree)
    work.mkdir(parents=True)
    (work / 'base.adt').write_bytes(base)
    (work / 'nonce.bin').write_bytes(nonce)
    (work / 'launch-manifest.json').write_bytes(manifest_bytes)
    (work / 'kernel.macho.adt').write_bytes(adt)
    return validate(adt, kernel, fd, shim, nonce=nonce, manifest_bytes=manifest_bytes)


def validate(adt, kernel, fd, shim, nonce=None, manifest_bytes=None):
    tree = parse(adt)
    chosen = find(tree, '/chosen')
    values = properties(chosen)
    if values.get(DOMAIN_KEY) != DOMAIN.encode() + b'\0':
        raise ValueError('Unexpected/non-diagnostic platform context')
    embedded = values.get(CONTEXT_KEY, b'')
    manifest = json.loads(embedded)
    if embedded != canonical(manifest) or (manifest_bytes is not None and manifest_bytes != embedded):
        raise ValueError('Manifest bytes differ/noncanonical')
    if manifest.get('format') != DOMAIN or manifest.get('trust') != {
            'manifest_authentication': 'none; host launch measurement',
            'apple_im4m': False, 'tss_personalized': False,
            'hardware_nonce_protection': False, 'anti_replay_enforced': False}:
        raise ValueError('Diagnostic trust scope changed')
    if values.get(POLICY_KEY) != struct.pack('<I', 1) or manifest.get('mix_n_match_prevention_status') != 1:
        raise ValueError('Missing/relaxed mix-n-match prevention')
    if values.get(HASH_KEY) != hashlib.sha384(embedded).digest():
        raise ValueError('Manifest digest mismatch')
    nonce_data = manifest.get('nonce', {})
    if (nonce_data.get('bytes') != 32 or nonce_data.get('hash_algorithm') != 'SHA-384'
            or nonce_data.get('producer') != 'Python secrets.token_bytes(32), host OS CSPRNG'
            or nonce_data.get('lifetime') != 'one candidate package; not one hardware boot'):
        raise ValueError('Nonce source/lifetime contract changed')
    nonce_hash = bytes.fromhex(nonce_data['hash'])
    if len(nonce_hash) != 48 or not any(nonce_hash):
        raise ValueError('Invalid nonce hash')
    if nonce is not None and (len(nonce) != 32 or hashlib.sha384(nonce).digest() != nonce_hash):
        raise ValueError('Nonce does not produce BNCH')
    manifest_node = find(tree, '/chosen/manifest-properties')
    if properties(manifest_node).get('BNCH') != nonce_hash:
        raise ValueError('BNCH differs from the actual launch nonce hash')
    components = manifest['components']
    for key, path in (('kernel', kernel), ('firmware_fd', fd), ('boot_shim', shim)):
        if components.get(key) != measurement(path):
            raise ValueError('Manifest component mismatch: ' + key)
    chosen['properties'] = [(k, f, v) for k, f, v in chosen['properties'] if k not in CHOSEN_KEYS]
    manifest_node['properties'] = [(k, f, v) for k, f, v in manifest_node['properties'] if k != 'BNCH']
    base = encode(tree)
    if components.get('base_adt') != {'bytes': len(base), 'sha256': sha256(base)}:
        raise ValueError('Manifest base ADT projection mismatch')
    return {'format': DOMAIN, 'adt_sha256': sha256(adt),
            'manifest_sha384': hashlib.sha384(embedded).hexdigest(),
            'bnch_sha384': nonce_hash.hex(), 'nonce_preimage_checked': nonce is not None,
            'components': components, 'trust': manifest['trust'],
            'policy': '32-bit LE 1: prohibit mix-n-match; no default/empty property',
            'producer_sha256': sha256(Path(__file__).read_bytes())}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base-adt', type=Path, required=True)
    p.add_argument('--kernel', type=Path, required=True)
    p.add_argument('--fd', type=Path, required=True)
    p.add_argument('--shim', type=Path, required=True)
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    output = a.output.resolve()
    if output.suffix != '.json' or not any(output.is_relative_to(ROOT / d) for d in ('out', 'reports')):
        raise ValueError('JSON evidence output under out/ or reports/ required')
    result = create(a.base_adt, a.kernel, a.fd, a.shim, a.work)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(json.dumps(result, indent=2).encode() + b'\n')
    print(json.dumps({'adt_sha256': result['adt_sha256'], 'nonce_preimage_checked': True,
                      'manifest_sha384': result['manifest_sha384']}))


if __name__ == '__main__':
    main()
