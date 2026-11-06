"""Serial existing r8 tests in fresh outputs; no boot or device integration."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--data-destination', type=Path, required=True)
    a = p.parse_args()
    out = a.output.resolve()
    if not out.is_relative_to(ROOT/'out') or out.exists():
        raise ValueError('Fresh integration output required')
    out.mkdir(parents=True)
    report = dict(passed=False, commands=[], sources={}, objects={}, device_accessed=False,
                  runtime_integrated=False, apfs_imported=False)
    def save():
        (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    def run(args, name):
        args = list(map(str, args))
        result = subprocess.run(args, capture_output=True, timeout=120)
        (out/(name+'.stdout')).write_bytes(result.stdout)
        (out/(name+'.stderr')).write_bytes(result.stderr)
        report['commands'].append(dict(argv=args, exit=result.returncode, log=name))
        save()
        if result.returncode:
            raise RuntimeError(name+': '+result.stderr.decode(errors='replace')[-2000:])
    flags = ['/usr/bin/clang', '-std=c11', '-Wall', '-Wextra', '-Werror',
             '-fsanitize=address,undefined', '-fno-pie', '-no-pie', '-g']
    suites = [('cpu-present', ['NuwaCpuPresent']), ('touch-hid', ['NuwaTouchHid','NuwaFtsEvents']),
              ('fts-events', ['NuwaFtsEvents'])]
    for name, modules in suites:
        files = [ROOT/'tests'/('nuwa-'+name+'.c')]
        files += [ROOT/'package/offline-desktop'/(n+'.c') for n in modules]
        for src in files:
            report['sources'][str(src.relative_to(ROOT))] = sha(src)
        run(flags+files+['-o',out/name], name+'-build')
        run([out/name], name+'-test')
    for name in ('NuwaCpuPresent','NuwaTouchHid','NuwaFtsEvents'):
        src=ROOT/'package/offline-desktop'/(name+'.c');obj=out/(name+'.o')
        run(['/usr/bin/clang','--target=aarch64-none-elf','-ffreestanding','-fno-builtin',
             '-O2','-Wall','-Wextra','-Werror','-c',src,'-o',obj],name+'-arm64')
        report['objects'][name]=sha(obj)
        header=src.with_suffix('.h');report['sources'][str(header.relative_to(ROOT))]=sha(header)
    run(['/usr/bin/python3','-B',ROOT/'scripts/test-data-stage-import-r8.py',
         '--destination',a.data_destination,'--output',out/'data-import.json'],'data-import')
    for name in ('data_stage_import.py','test-data-stage-import-r8.py'):
        report['sources']['scripts/'+name]=sha(ROOT/'scripts'/name)
    report['compiler']=subprocess.check_output(['/usr/bin/clang','--version'],text=True).splitlines()[0]
    report['limitations']=['Existing synthetic host vectors and sanitizer execution only',
        'No IOSurface/provider/physical refresh, IOHIDDevice/bus/IRQ, APFS writer or persistence validation',
        'Conditional Data sample is not a deployment selection; no boot package includes these modules']
    report['passed']=True;save();print('PASS isolated desktop: 3 sanitizer suites, 3 ARM64 objects, host Data import')

if __name__=='__main__':
    main()
