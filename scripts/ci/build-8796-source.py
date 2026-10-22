"""Compile the reviewed 8796 source on macOS CI, without donor prelink or images.

The real build tree lives in RUNNER_TEMP, outside the device repository. Local
--check only validates inputs and adapts text in memory; it never copies sources.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import struct
import subprocess

DEVICE = Path(__file__).resolve().parents[2]
BASE_COMMIT = '75bc13dd34dc4e403826793739e316a264ce00dd'
XNU_COMMIT = '1b191cb58250d0705d8a51287127505aa4bc0789'
BASELINE_HASH = '3486867d8c639eb10d31be16e875dbbdbb1d27afd97aedbb8ba930f0093c6852'
FIREHOSE_HASH = 'e30d44b2633fb509fefbb316cb2824abb394e3e5779d4b6d86f8ed2b4f91c057'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_exact(text, before, after, count):
    if text.count(before) != count:
        raise ValueError(f'Unexpected upstream context count for {before!r}')
    return text.replace(before, after)


def inputs(base):
    evidence = json.loads((DEVICE / 'reports/xnu-8796-sequence/results.json').read_text(encoding='utf-8'))
    if evidence['base_head'] != BASE_COMMIT or evidence['source_head'] != XNU_COMMIT:
        raise ValueError('Review evidence pins differ')
    selection = [item for item in evidence['selection'] if item['status'] == 'virtual-pass']
    if not evidence['complete_sequence'] or len(selection) != 48:
        raise ValueError('Need the complete reviewed 48-patch selection')
    patches = []
    for item in selection:
        name = item['patch']
        if Path(name).name != name or not name.endswith('.patch'):
            raise ValueError('Unsafe patch name')
        candidate = DEVICE / 'patches/xnu-8796-candidates' / name
        if not candidate.exists():
            directory = 'kits/NativePrelink/patches' if name.startswith('xnu-10063.') else 'patches/xnu'
            candidate = base / directory / name
        if sha(candidate) != item['sha256']:
            raise ValueError(f'Reviewed patch changed: {name}')
        patches.append(candidate)
    baseline = base / 'scripts/build-xnu-4k-baseline.sh'
    firehose = base / 'scripts/build-firehose.sh'
    if sha(baseline) != BASELINE_HASH or sha(firehose) != FIREHOSE_HASH:
        raise ValueError('Unexpected upstream build scripts')
    script = baseline.read_text(encoding='utf-8')
    script = replace_exact(script, '.unstripped.noctf', '.unstripped', 3)
    script = replace_exact(script, '-miphoneos-version-min=17.0', '-miphoneos-version-min=16.0', 1)
    script = replace_exact(script, '-Wl,-ios_version_min,17.0', '-Wl,-ios_version_min,16.0', 1)
    firehose_script = replace_exact(firehose.read_text(encoding='utf-8'),
                                   'IPHONEOS_DEPLOYMENT_TARGET=17.0',
                                   'IPHONEOS_DEPLOYMENT_TARGET=16.0', 1)
    compatibility = DEVICE / 'patches/xnu-8796-ci-candidates/clang17-zero-init.patch'
    if not compatibility.is_file():
        raise ValueError('Missing reviewed clang17 compatibility patch')
    patches.append(compatibility)
    return patches, script, firehose_script


def run(command, **kwargs):
    print('+', ' '.join(map(str, command)), flush=True)
    return subprocess.run(list(map(str, command)), check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', required=True, type=Path)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    base = args.base.resolve()
    patches, script, firehose_script = inputs(base)
    summary = {'base_commit': BASE_COMMIT, 'xnu_commit': XNU_COMMIT,
               'patches': [{'name': p.name, 'sha256': sha(p)} for p in patches],
               'baseline_adapter_sha256': hashlib.sha256(script.encode()).hexdigest(),
               'firehose_adapter_sha256': hashlib.sha256(firehose_script.encode()).hexdigest(),
               'reviewed_base_patch_count': 48,
               'ci_compatibility_patch_count': len(patches) - 48,
               'scope': 'source compile/link only; optional device archives disabled',
               'kernel_built': False, 'prelinked': False, 'device_verified': False}
    if args.check:
        shell = ('C:/Program Files/Git/bin/bash.exe' if platform.system() == 'Windows'
                 else shutil.which('bash'))
        if not shell:
            raise ValueError('bash is required to syntax-check the adapted recipes')
        for content in (script, firehose_script):
            subprocess.run([shell, '-n'], input=content, text=True, encoding='utf-8', check=True)
        summary['adapted_shell_syntax'] = 'passed; no build commands executed'
        print(json.dumps(summary, indent=2))
        return
    if platform.system() != 'Darwin' or os.environ.get('GITHUB_ACTIONS') != 'true':
        raise SystemExit('Build mode requires the macOS Actions runner; use --check locally')
    temporary = Path(os.environ['RUNNER_TEMP']).resolve()
    if temporary == DEVICE or temporary.is_relative_to(DEVICE):
        raise ValueError('RUNNER_TEMP must be outside the device repository')
    work = temporary / 'nuwa-8796-source'
    work.mkdir(exist_ok=False)
    (work / 'refer').mkdir()
    (work / 'reports').mkdir()
    report = work / 'reports/build.json'
    report.write_text(json.dumps(summary, indent=2) + '\n')
    shutil.copytree(base / 'scripts', work / 'scripts')
    for path in patches:
        folder = 'kits/NativePrelink/patches' if path.name.startswith('xnu-10063.') else 'patches/xnu'
        target = work / folder / path.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    (work / 'scripts/build-xnu-4k-baseline.sh').write_text(script, newline='\n')
    (work / 'scripts/build-firehose.sh').write_text(firehose_script, newline='\n')
    env = {k: v for k, v in os.environ.items() if not k.startswith(('XNU_', 'UNIXNU_'))}
    env.update(UNIXNU_XNU_TAG='xnu-8796.141.3', UNIXNU_XNU_COMMIT=XNU_COMMIT,
               UNIXNU_XNU_DARWIN='22.6.0', UNIXNU_XNU_VERSION='8796.141.3',
               UNIXNU_DRIVERKIT_TAG='xnu-8796.141.3', UNIXNU_TRUSTCACHE_TAG='xnu-8796.141.3',
               XNU_BOOT_PROGRESS='0', XNU_ZONE_PGZ_ALIGNMENT_PROBE='0', JOBS='3')
    try:
        # Reuse the base recipe: real source checkout, ordered patches, installhdrs,
        # real libfirehose archive and XNU build. No stubs or suppressed link errors.
        run(['bash', work / 'scripts/build-xnu-4k-baseline.sh'], cwd=work, env=env)
        kernel = work / 'build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/mach.development.bcm2837.unstripped'
        magic, cpu, subtype, filetype = struct.unpack('<IIII', kernel.read_bytes()[:16])
        if (magic, cpu, subtype, filetype) != (0xfeedfacf, 0x100000c, 0, 2):
            raise ValueError('Expected ordinary ARM64 MH_EXECUTE kernel')
        summary.update(kernel_built=True, kernel_sha256=sha(kernel),
                       kernel_path=str(kernel.relative_to(work)))
        run(['file', kernel])
        run(['xcrun', 'otool', '-l', kernel])
    finally:
        source = work / '.cache/xnu-work'
        if source.is_dir():
            summary['source_status'] = subprocess.run(
                ['git', '-C', str(source), 'status', '--short'], text=True,
                capture_output=True, check=False).stdout
        summary['object_count'] = len(list((work / 'build').rglob('*.o')))
        report.write_text(json.dumps(summary, indent=2) + '\n')


if __name__ == '__main__':
    main()
