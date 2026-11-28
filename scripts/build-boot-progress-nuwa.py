#!/usr/bin/env python3
"""Build libBootProgress.a for this board: package/boot-progress/BootProgress.c.

Port of UniXNU/UniXNU-sheng@998d0cc5023d4eff54a1ef40cce6ec89dc10083c
scripts/build-boot-progress.py (MIT).  Upstream builds six objects (the renderer
plus the fault/watchdog/diag/latency/Adsp helpers); this port builds only the
renderer and the nuwa symbol stubs, because the other five depend on sheng
components the nuwa base does not carry.

The compile line is the recorded kernel build's own (osfmk startup.o), with the
source, output and -o swapped and the renderer's own warning set, exactly as the
upstream script does.  Font.h comes from the uefi-nuwa checkout; kern/boot_progress.h
comes from the isolated tree that carries patches/xnu/8796-nuwa-boot-progress.patch.
Host only: no device I/O, no kernel tree mutation.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'package/boot-progress'
RENDERER = SOURCE / 'BootProgress.c'
STUBS = SOURCE / 'nuwa_boot_progress_stubs.c'
PINS = {
    'BootProgress.c': '31411c57a01917c19f97f91e67cd3b6c10c83c628a49bcbb96957d36f16c8972',
    'BootProgressCore.h': 'b336397b7aa1e903705ecc78f668f67dd31d7136e8a47acfc801322ada30ee04',
    'BootProgressDisplay.h': '231f580758e4e98592fd7f41203be00ca5670b912508a520bf83fb82d3af10d9',
    'BootProgressLifecycle.h': 'a885fceac1215b4d18ae4e96d141586a257b734bd6a88d8945786f00d8a6b272',
    'BootProgressPulse.h': '25700a256b60329dc297c85f36f2397d21062536342affa42568e4cfef1adcd4',
}
FONT = ROOT.parent / 'uefi-nuwa/Silicon/Silicium/SiliciumPkg/Library/FrameBufferSerialPortLib'
RECORD = 'osfmk/DEVELOPMENT/startup.o.json'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True, help='existing run directory under out/')
    ap.add_argument('--tree', type=Path, required=True,
                    help='isolated tree carrying osfmk/kern/boot_progress.h')
    args = ap.parse_args()
    out = args.out.resolve()
    tree = args.tree.resolve()
    assert out.is_relative_to((ROOT / 'out').resolve()) and out.is_dir(), 'require a run directory under out/'
    assert (tree / 'osfmk/kern/boot_progress.h').is_file(), 'isolated tree has no osfmk/kern/boot_progress.h'
    assert FONT.joinpath('Font.h').is_file(), 'Font.h missing from the uefi-nuwa checkout'
    for name, digest in PINS.items():
        assert sha((SOURCE / name).read_bytes()) == digest, 'upstream renderer changed: ' + name

    B = load(ROOT / 'scripts/build-nuwa-pmgr-kernel.py', 'boot_progress_records')
    record = json.loads((B.OBJ / RECORD).read_text().strip().rstrip(','))
    env = dict(os.environ, DARWIN_TRIPLE='arm64-apple-ios17.0',
               CROSS_CLANG='/opt/unixnu-linux/llvm/bin/clang',
               CROSS_EXTRA_FLAGS='-mllvm -disable-atexit-based-global-dtor-lowering',
               PYTHONDONTWRITEBYTECODE='1')
    env['PATH'] = '/opt/unixnu-linux/CommandLineTools/usr/bin:/opt/unixnu-linux/bin:' + env.get('PATH', '')

    def command_for(source, obj):
        """The recorded kernel compile line, retargeted like the upstream script."""
        argv = record['arguments']
        result, i = [], 0
        while i < len(argv):
            arg = argv[i]
            if arg == record['file']:
                result.append(str(source))
            elif arg in ('-o', '-MF', '-MT', '-MJ'):
                if arg == '-o':
                    result += ['-o', str(obj)]
                i += 1
            elif arg == '-Xclang' and i + 1 < len(argv) and argv[i + 1].startswith('-W'):
                i += 1
            elif arg == '-D' and i + 1 < len(argv) and argv[i + 1].startswith('XNU_BOOT_PROGRESS='):
                i += 1
            elif not arg.startswith(('-W', '-DXNU_BOOT_PROGRESS=')):
                result.append(arg)
            i += 1
        result += ['-DXNU_BOOT_PROGRESS=1', '-mgeneral-regs-only', '-Wall', '-Wextra', '-Werror',
                   '-I', str(B.TREE / '.cache/xnu-work/osfmk'),
                   '-I', str(tree / 'osfmk'),
                   '-I', str(FONT)]
        return result

    commands = []

    def run(label, argv):
        log = out / (label + '.log')
        import subprocess
        with log.open('wb') as stream:
            done = subprocess.run(argv, cwd=record['directory'], env=env,
                                  stdout=stream, stderr=subprocess.STDOUT)
        commands.append(dict(label=label, argv=[str(x) for x in argv], exit=done.returncode,
                             log=str(log), cwd=record['directory']))
        if done.returncode:
            errors = [line for line in log.read_text(errors='replace').splitlines() if 'error:' in line]
            raise SystemExit(f'{label}: exit {done.returncode}: '
                             + (errors[0] if errors else log.read_text(errors='replace')[-2000:]))

    renderer_obj = out / 'BootProgress.o'
    stubs_obj = out / 'nuwa_boot_progress_stubs.o'
    renderer_argv = command_for(RENDERER, renderer_obj)
    stubs_argv = command_for(STUBS, stubs_obj)
    run('compile-BootProgress', renderer_argv)
    run('compile-nuwa-boot-progress-stubs', stubs_argv)

    archive = out / 'libBootProgress.a'
    archive.unlink(missing_ok=True)
    run('archive', ['/usr/bin/llvm-ar', 'rcs', archive, renderer_obj, stubs_obj])
    members = os.popen(f'/usr/bin/llvm-ar t {archive}').read().split()
    assert members == ['BootProgress.o', 'nuwa_boot_progress_stubs.o'], members

    report = {
        'status': 'self-checked; host-only archive; no device approval',
        'source_commit': '998d0cc5023d4eff54a1ef40cce6ec89dc10083c',
        'source_repo': 'https://github.com/UniXNU/UniXNU-sheng',
        'renderer': dict(path=str(RENDERER), bytes=RENDERER.stat().st_size, sha256=sha(RENDERER.read_bytes())),
        'headers': {name: sha((SOURCE / name).read_bytes()) for name in PINS if name != 'BootProgress.c'},
        'stubs': dict(path=str(STUBS), bytes=STUBS.stat().st_size, sha256=sha(STUBS.read_bytes())),
        'font_header': dict(path=str(FONT / 'Font.h'), sha256=sha((FONT / 'Font.h').read_bytes())),
        'boot_progress_header': dict(path=str(tree / 'osfmk/kern/boot_progress.h'),
                                     sha256=sha((tree / 'osfmk/kern/boot_progress.h').read_bytes())),
        'compile_record': dict(path=str(B.OBJ / RECORD), sha256=sha((B.OBJ / RECORD).read_bytes())),
        'renderer_object': dict(path=str(renderer_obj), bytes=renderer_obj.stat().st_size,
                                sha256=sha(renderer_obj.read_bytes())),
        'stubs_object': dict(path=str(stubs_obj), bytes=stubs_obj.stat().st_size,
                             sha256=sha(stubs_obj.read_bytes())),
        'archive': dict(path=str(archive), bytes=archive.stat().st_size, sha256=sha(archive.read_bytes())),
        'members': members,
        'not_built': ['BootFaultProbe.c', 'BootWatchdogPolicy.c', 'BootDiagExport.c',
                      'BootLatencyTrace.c', 'AdspFirmware.c'],
        'hardware_execution': False,
    }
    (out / 'build-boot-progress-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'archive': report['archive'], 'renderer_object': report['renderer_object'],
                      'stubs_object': report['stubs_object']}, indent=2))


if __name__ == '__main__':
    main()
