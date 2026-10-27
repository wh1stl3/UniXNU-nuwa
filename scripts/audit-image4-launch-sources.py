"""Pin read-only reference implementations used for the launch-input design."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = [
    ('DarwinBoot', 'D:/Code/UniXNU-integration/drivers/DarwinBoot',
     'd099354d0eab34df5088ca1ba89c9c88bc3260bb',
     ['DarwinBootPkg/Driver/DarwinBoot.c', 'DarwinBootPkg/Driver/DarwinBoot.inf', 'LICENSE'],
     'BSD-2-Clause-Patent',
     'Structure/size checks and payload loading before XNU; no nonce or Apple IM4M producer found in this Boot path. Current module source is a reference, not a claim that the fixed CI40014018074 FD was built at this commit.'),
    ('VerifiedRoot', 'D:/Code/UniXNU-integration/kits/VerifiedRoot',
     '2854c61f6c4dfda870ac3d93e1f03d9181edb041',
     ['tools/manifest.py', 'src/verified_root.c', 'adapters/xnu_crypto.c', 'include/verified_root.h', 'LICENSE'],
     'BSD-2-Clause-Patent',
     'Owner RSA3072/PKCS1v1.5/SHA256 signatures and ordered block hashes require an owner key anchor, crypto provider and authenticated image set. Not transplanted as an early Apple manifest or replaced with a synthetic hash.'),
    ('ios-sweet', 'D:/Code/PortingiOSLegacy/common/sources/ios-sweet',
     'fdad0de8dc0e75c5ea84762adc03f7232dc91f19', ['tools/mkadt.py'],
     'No source code copied; license not relied on',
     'SHA384 of the fixed string sweet boot manifest is compatibility reference only, never used as the nuwa manifest.'),
    ('ios-topaz', 'D:/Code/PortingiOSLegacy/common/sources/ios-topaz',
     'd5dfb3b6003a1b691e11b742362ca16ff4c2d989', ['tools/mkadt.py'],
     'No source code copied; license not relied on',
     'SHA384 of the fixed string topaz boot manifest is compatibility reference only, never used as the nuwa manifest.'),
    ('uefi-nuwa RNG consumer', 'D:/Code/PortingiOS/nuwa/uefi-nuwa',
     'a155c495c863e06d400b515315e3b8f7791dc308',
     ['Silicon/Silicium/SiliciumPkg/Library/DxeRngLib/DxeRng.c'],
     'BSD-2-Clause-Patent (source header)',
     'Consumes EFI_RNG_PROTOCOL; this is not evidence of an active nuwa RNG provider or hardware-protected boot nonce. Not claimed as the source of the host-produced candidate nonce.')]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    output = a.output.resolve()
    if not output.is_relative_to(ROOT / 'reports') or output.suffix != '.json':
        raise ValueError('JSON evidence under reports/ required')
    sources, checks = [], []
    for name, path, commit, files, license, conclusion in SOURCES:
        prefix = ['git', '-c', 'safe.directory=' + path, '-C', path]
        actual = subprocess.check_output(prefix + ['rev-parse', 'HEAD'], text=True).strip()
        if actual != commit:
            raise ValueError('Reference commit changed: ' + name)
        records = []
        for file in files:
            blob = subprocess.check_output(prefix + ['show', commit + ':' + file])
            disk = (Path(path) / file).read_bytes()
            if blob.replace(b'\r\n', b'\n') != disk.replace(b'\r\n', b'\n'):
                raise ValueError('Reference working file differs from pinned commit: ' + file)
            records.append({'path': file, 'git_blob_sha256': sha(blob), 'local_sha256': sha(disk)})
        sources.append({'name': name, 'repository_path': path, 'commit': commit,
                        'files': records, 'license': license, 'conclusion': conclusion})
        checks.append({'name': name + ' fixed commit and source bytes match', 'passed': True})
    result = {'scope': __doc__, 'sources': sources, 'checks': checks,
              'reuse': 'Measurement/domain separation and refusal-on-conflict design only. No upstream implementation copied or changed; local launch-input producer uses Python stdlib.',
              'actual_nonce_producer': 'scripts/nuwa_launch_context.py; host OS CSPRNG, candidate-package lifetime',
              'actual_manifest_producer': 'scripts/nuwa_launch_context.py; canonical measurement of actual candidate kernel, FD, shim and base ADT',
              'firmware_rebuilt': False, 'apple_chain_claimed': False, 'device_accessed': False}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(json.dumps(result, indent=2).encode() + b'\n')
    print(json.dumps({'sources': len(sources), 'passed': True}))


if __name__ == '__main__':
    main()
