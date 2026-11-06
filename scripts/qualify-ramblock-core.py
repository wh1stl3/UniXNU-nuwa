"""Serial host qualification of the configured RamBlock core, not its IOKit ABI."""
import argparse
import hashlib
import json
from pathlib import Path
import resource
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REV = 'd4d22d9819b0162eda49f6402235dddc2279410d'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source', type=Path, required=True)
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    src, out = args.source.resolve(), args.output.resolve()
    if not out.is_relative_to(ROOT / 'reports') or out.exists():
        raise ValueError('Fresh repository reports directory required')
    profile = json.loads((ROOT / 'config/kernel-merged-profile.json').read_text())
    if profile['modules']['drivers/NativeRamBlock'] != REV:
        raise ValueError('Review changed component revision')
    prior = json.loads((ROOT / 'reports/desktop-readiness/2026-10-27-data-linux-r1/public-ramblock.json').read_text())
    for row in prior:
        if sha(src / row['url'].rsplit('/', 1)[1]) != row['sha256']:
            raise ValueError('Previously pinned public source mismatch')
    out.mkdir(parents=True)
    (out / 'runner.py').write_bytes(Path(__file__).read_bytes())
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    files = {str(p.relative_to(src)): sha(p) for p in sorted(src.rglob('*')) if p.is_file()}
    report = dict(revision=REV, source_files=files, runs=[], hardware_executed=False,
                  iokit_abi_qualified=False, kernel_linked=False, deployable=False)
    report['compiler'] = dict(path='/usr/bin/clang++', sha256=sha(Path('/usr/bin/clang++')),
        version=subprocess.check_output(['/usr/bin/clang++', '--version'], text=True))
    report['download_manifest'] = json.loads((src.parent / 'download.json').read_text())
    if sha(src.parent / 'source.tar.gz') != report['download_manifest']['sha256']:
        raise ValueError('Downloaded source archive changed')

    def run(label, command):
        result = subprocess.run([str(x) for x in command], capture_output=True, text=True, timeout=180)
        (out / (label + '.log')).write_text(result.stdout + result.stderr)
        report['runs'].append(dict(label=label, command=[str(x) for x in command],
                                   exit_code=result.returncode, log_sha256=sha(out / (label + '.log'))))
        print(label, result.returncode, (result.stdout + result.stderr)[-240:], flush=True)
        return result

    flags = ['/usr/bin/clang++', '-std=c++17', '-O1', '-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-fno-pie', '-no-pie']
    for name in ('sparse', 'persist', 'direct', 'seeddisk'):
        binary = out / name
        if run(name + '-compile', flags + [src / 'Test' / (name + '.cpp'), '-o', binary]).returncode == 0:
            run(name + '-original', [binary])
    # The upstream sparse fixture predates the 1 TiB parser limit. Preserve it
    # verbatim above; change only that negative input in a separately saved fixture.
    text = (src / 'Test/sparse.cpp').read_text()
    old = 'if(which==3)put64(bad,16,0x80001000);'
    if text.count(old) != 1:
        raise ValueError('Review upstream sparse fixture change')
    adjusted = out / 'sparse-current-limit.cpp'
    adjusted.write_text(text.replace('#include "../SparseDisk.h"', '#include "SparseDisk.h"')
                       .replace(old, 'if(which==3)put64(bad,16,(1ULL<<40)+4096);'))
    report['fixture_adjustment'] = dict(source_sha256=files['Test/sparse.cpp'],
        adjusted_sha256=sha(adjusted), reason='Negative size must exceed current 1 TiB limit; driver unchanged')
    binary = out / 'sparse-current-limit'
    if run('sparse-current-compile', flags + ['-I', src, adjusted, '-o', binary]).returncode == 0:
        run('sparse-current-limit', [binary])
    seed = ROOT / 'out/linux-data-candidate-20261027-r1/build-a/data-linux.dbr'
    if sha(seed) != '1e00210d8fb17f13736efe8d6ca9f6b72eb424c223fa1bf03168b808bf2f7598':
        raise ValueError('Data candidate changed')
    binary = out / 'seed-readback'
    command = flags + ['-I', src, ROOT / 'scripts/data-seed-readback/main.cpp', '-lcrypto', '-o', binary]
    if run('seed-readback-compile', command).returncode == 0:
        result = run('seed-readback', [binary, seed])
        if result.returncode == 0:
            report['seed_readback'] = json.loads(result.stdout)
            report['seed_matches'] = report['seed_readback']['sha256'] == '1a97ed81a7d9cc8866b4b7c3edc8c462797d92a9dce1560a0a2122eaf17b85d9'
    report['source_unchanged'] = files == {str(p.relative_to(src)): sha(p) for p in sorted(src.rglob('*')) if p.is_file()}
    required = ('sparse-current-compile', 'sparse-current-limit', 'persist-compile', 'persist-original',
                'direct-compile', 'direct-original', 'seed-readback-compile', 'seed-readback')
    report['small_volatile_core_passed'] = (report.get('seed_matches', False) and report['source_unchanged']
        and all(any(r['label'] == label and r['exit_code'] == 0 for r in report['runs']) for label in required))
    report['large_seed_fixture_qualified'] = False
    report['scope'] = 'Host real core/parser/importer and supplied Data bytes; no IOKit, mount, target ABI or hardware proof'
    report['script_sha256'] = sha(Path(__file__))
    (out / 'qualification.json').write_text(json.dumps(report, indent=2) + '\n')
    if not report['small_volatile_core_passed']:
        raise SystemExit('Core qualification failed; evidence retained')


if __name__ == '__main__':
    main()
