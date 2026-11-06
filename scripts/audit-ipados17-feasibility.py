"""Read-only donor/profile and current root-observation audit; no device operations."""
import argparse, hashlib, json, plistlib, subprocess, sys, tomllib, urllib.request
from pathlib import Path

def digest(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda: f.read(8 << 20), b''):
            h.update(block)
    return h.hexdigest()

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--decoder-path', type=Path)
    args = ap.parse_args()
    if args.output.exists():
        raise SystemExit('Refusing to overwrite an existing report')
    root = Path(__file__).resolve().parents[1]
    base = Path('D:/Code/PortingiOSLegacy/common')
    pin = '066c8d8315f83749d28bcae2faf3595718646be5'
    url = f'https://raw.githubusercontent.com/UniXNU/UniXNU/{pin}/profiles/os/ipados-17.7.11-21H461/profile.toml'
    raw = urllib.request.urlopen(url, timeout=60).read()
    profile = tomllib.loads(raw.decode())
    donor = base/'cache/donor-ipados17'
    manifest = plistlib.loads((donor/'BuildManifest.plist').read_bytes())
    identities = [i for i in manifest['BuildIdentities'] if i.get('Info', {}).get('DeviceClass', '').lower() == 'j120ap']
    checks = []
    expected = dict(profile['ipsw']['sha256'])
    expected['kernelcache.release.ipad7'] = profile['kernel']['prelink']['kernelcache_sha256']
    for name, wanted in expected.items():
        p = donor/'components'/name
        actual = digest(p) if p.is_file() else None
        checks.append(dict(file=str(p), expected=wanted, actual=actual, passed=actual == wanted))
    if args.decoder_path:
        sys.path.insert(0, str(args.decoder_path.resolve()))
        import lzfse
        container = (donor/'components/kernelcache.release.ipad7').read_bytes()
        def tlv(data, at):
            tag, n = data[at], data[at+1]
            at += 2
            if n & 128:
                count = n & 127
                if not count or count > 8: raise ValueError('Invalid DER length')
                n = int.from_bytes(data[at:at+count], 'big'); at += count
            if at+n > len(data): raise ValueError('Truncated DER')
            return tag, data[at:at+n], at+n
        tag, seq, end = tlv(container, 0)
        if tag != 48 or end != len(container): raise ValueError('Expected IM4P sequence')
        fields, at = [], 0
        while at < len(seq):
            tag, val, at = tlv(seq, at); fields.append((tag, val))
        if fields[0][1] != b'IM4P' or fields[3][0] != 4: raise ValueError('Unexpected IM4P fields')
        decoded = lzfse.decompress(fields[3][1])
        if decoded[:4] == bytes.fromhex('cafebabe'):
            if int.from_bytes(decoded[4:8], 'big') != 1 or int.from_bytes(decoded[8:12], 'big') != 0x100000c:
                raise ValueError('Expected single ARM64 FAT slice')
            offset, size = int.from_bytes(decoded[16:20], 'big'), int.from_bytes(decoded[20:24], 'big')
            if offset < 28 or offset+size > len(decoded): raise ValueError('Invalid FAT slice')
            decoded = decoded[offset:offset+size]
        if decoded[:4] != bytes.fromhex('cffaedfe'): raise ValueError('Not ARM64 Mach-O')
        actual = hashlib.sha256(decoded).hexdigest()
        checks[2].update(container_sha256=checks[2]['actual'], actual=actual, representation='IM4P payload decompressed to Mach-O', passed=actual == checks[2]['expected'])
    source = base/'sources/xnu-ios17-full'
    rev = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    checks.append(dict(check='xnu_revision', actual=rev, expected=profile['os']['xnu_revision'], passed=rev == profile['os']['xnu_revision']))
    checks.append(dict(check='donor_identity', version=manifest.get('ProductVersion'), build=manifest.get('ProductBuildVersion'), matching_identities=len(identities), passed=manifest.get('ProductVersion') == '17.7.11' and manifest.get('ProductBuildVersion') == '21H461' and bool(identities)))
    build_path = root/'reports/kernel-entry-probe/2026-10-30-probe58-milestones-r1/build.json'
    b = json.loads(build_path.read_bytes())
    removed = [c for c in b['lean_observation']['changes'] if c.get('function') == 'probe_dense_76730e8']
    result = dict(scope='Offline input identity and observation audit only; not build/prelink/runtime qualification', profile_url=url, profile_sha256=hashlib.sha256(raw).hexdigest(), checks=checks, inputs_match=all(c['passed'] for c in checks), current_probe=dict(build_sha256=digest(build_path), root_mount_policy=b['root_mount_diagnostic'], suppressed_return_rendering=removed), remaining=['Verify all selected driver revisions and clean source state', 'Build isolated XNU10063/platform archives', 'Validate full donor import/ABI/prelink closure', 'Prepare nuwa-specific ADT and storage layout without copying sheng board values'], deployable=False)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    print(json.dumps(dict(inputs_match=result['inputs_match'], checks=len(checks), suppressed_return_rendering=len(removed), report=str(args.output))))

if __name__ == '__main__':
    main()
