"""Static interface evidence only. No builds, images, imports of upstream code or Git writes."""
import codecs
import ctypes
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('D:/Code/PortingiOSLegacy/common/sources/UniXNU')
XNU = Path('D:/Code/PortingiOSLegacy/common/sources/xnu-ios16-full')
SHENG = Path('D:/Code/PortingiOSLegacy/common/sources/UniXNU-sheng')
OUT = ROOT / 'reports/darwin22-audit'
GIT = 'C:/Program Files/Git/cmd/git.exe'


def read_git(repo, *args):
    if not args or args[0] not in {'status', 'diff', 'log', 'show'}:
        raise ValueError('Git command outside user whitelist')
    command = [GIT, '-c', f'safe.directory={repo.as_posix()}', '--no-optional-locks', '-C', str(repo), *args]
    result = subprocess.run(command, capture_output=True, encoding='utf-8', errors='replace')
    return dict(command=command, exit_code=result.returncode, stdout=result.stdout, stderr=result.stderr)


def evidence(path, patterns):
    text = path.read_text(encoding='utf-8')
    return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                matches=[dict(line=i, text=line) for i, line in enumerate(text.splitlines(), 1)
                         if any(re.search(pattern, line) for pattern in patterns)])


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    snapshots = {name: dict(head=read_git(repo, 'log', '-1', '--format=%H'),
                           status=read_git(repo, 'status', '--porcelain', '--untracked-files=no'))
                 for name, repo in [('base', BASE), ('xnu', XNU), ('sheng_reference', SHENG)]}
    if any(item['head']['exit_code'] or item['status']['exit_code'] or item['status']['stdout'] for item in snapshots.values()):
        raise SystemExit('Source provenance is dirty or unreadable')
    files = [
        (BASE / 'scripts/build-xnu-4k-baseline.sh', ['unstripped', 'SDKROOT', 'ios.version.min', 'BOOT_PROGRESS', 'SHENG_PMGR', 'ARCHIVES', 'git clone', 'git .*apply', 'ditto']),
        (BASE / 'scripts/unixnu/kernel.py', ['xcodebuild', 'startup.o.json', r'spec\[', 'version_env']),
        (BASE / 'scripts/build-libpthread-kernel.py', ['REVISION', 'ios17', '0x110000', 'kernel_names', 'missing', 'report', 'clone']),
        (BASE / 'scripts/build-corecrypto-14.py', ['REVISION', 'ios17', 'unstripped', r'names\(', 'xcrun']),
        (BASE / 'scripts/build-native-aes-bindings.py', ['ios17', 'candidate', 'bindings', 'xcrun']),
        (BASE / 'scripts/build-native-virtio-bindings.py', ['ios17', 'candidate', 'bindings', 'xcrun']),
        (BASE / 'scripts/prepare-xnu-source.py', ['TAG', 'TRUST_TAG', 'restore', 'destination']),
        (XNU / 'makedefs/MakeInc.kernel', ['unstripped', 'do_build_kernel']),
        (XNU / 'makedefs/MakeInc.cmd', ['XCRUN', 'MIG', 'IIG', 'SDKROOT']),
        (XNU / 'makedefs/MakeInc.def', ['BUILD_JSON_COMPILATION_DATABASE', 'JSONCOMPILATIONDB', r'KCC\s*=']),
        (XNU / 'osfmk/kern/kalloc.h', ['__builtin_xnu_']),
        (XNU / 'osfmk/mach/kmod.h', ['pack', 'MAX_NAME', 'start', 'stop', 'kmod_info']),
        (XNU / 'bsd/kern/syscalls.master', [r'int (open|sys_close|mkdir|fsync|fchown|fchmod|sys_fstat64)\(', 'user_ssize_t write']),
        (SHENG / 'scripts/build-boot-progress.py', ['record', r'\.json', 'source =', 'fault_source', 'policy_source', 'xcrun', 'uefi-sheng']),
        (SHENG / 'scripts/build-sheng-platform-power.py', ['340', '0x110000', 'ios17', 'bindings', 'xcrun']),
        (SHENG / 'package/BootWatchdogPolicy.c', ['sheng_boot_watchdog_policy', 'scratch', r'policy\[', 'watchdogd', 'disabled', 'O_EXCL']),
        (BASE / 'kits/NativePrelink/emit_prelink.py', ['_version', '156', '164', '__macho_list', 'early_security_init']),
        (BASE / 'kits/NativePrelink/native_prelink.py', ['subtype', 'choices', 'unique_kernel_binding', 'MH_EXECUTE', 'slide %']),
    ]
    excerpts = [evidence(path, patterns) for path, patterns in files]
    names = ['init', 'start', 'active', 'bind', 'putc', 'stage', 'irq', 'poll',
             'user_breakpoint', 'user_abort', 'critical_exit', 'process_stage', 'exit']
    callback_rows = []
    nuwa_sources = [path for folder in ('drivers', 'kits', 'package') for path in (ROOT / folder).rglob('*')
                    if path.is_file() and path.suffix in {'.c', '.cpp', '.h'}]
    header = (ROOT / 'patches/xnu-8796-candidates/zzz-boot-progress.patch').read_text(encoding='utf-8')
    for short in names:
        name = 'boot_progress_' + short
        declaration = re.findall(r'^\+(?:void|int)\s+' + name + r'\([^;]*\);', header, flags=re.M)
        definitions = []
        for source in ['BootProgress.c', 'BootFaultProbe.c']:
            path = SHENG / 'package' / source
            text = path.read_text(encoding='utf-8')
            for match in re.finditer(r'^(?:void|int)\s+' + name + r'\([^)]*\)\s*\{', text, flags=re.M):
                definitions.append(dict(path=str(path), line=text[:match.start()].count('\n') + 1,
                                        text=match.group(0)))
        nuwa_matches = [str(path) for path in nuwa_sources if re.search(r'\b' + name + r'\s*\(', path.read_text(encoding='utf-8'))]
        callback_rows.append(dict(name=name, declaration=declaration, reference_definitions=definitions,
                                  nuwa_source_matches=nuwa_matches, abi_compiled=False))

    recipe = (BASE / 'scripts/build-xnu-4k-baseline.sh').read_text(encoding='utf-8')
    calls = sorted(set(re.findall(r'(?:python3|bash) (scripts/[\w.-]+)', recipe)))
    script_rows = [dict(path=p, base=(BASE / p).is_file(), sheng=(SHENG / p).is_file(),
                        nuwa=(ROOT / p).is_file()) for p in calls]
    archive_consumers = []
    for path in sorted((BASE / 'scripts/unixnu').glob('*.py')):
        if 'archives' in path.read_text(encoding='utf-8'):
            archive_consumers.append(str(path))

    watchdog = (SHENG / 'package/BootWatchdogPolicy.c').read_text(encoding='utf-8')
    def c_string(name):
        block = re.search(r'static const char ' + name + r'\[\]\s*=\s*(.*?);', watchdog, re.S).group(1)
        return ''.join(codecs.decode(s, 'unicode_escape') for s in re.findall(r'"((?:\\.|[^"\\])*)"', block))
    jobs = ','.join('com.apple.t' + str(i) for i in range(12))
    policy = c_string('policy_head') + c_string('policy_watchdogd')
    policy += ''.join('<key>' + label + '</key><true/>' for label in jobs.split(','))
    policy += c_string('policy_tail')
    overlap = dict(mode='Host string arithmetic only; no policy file written, no kernel run',
                   jobs=jobs, jobs_bytes=len(jobs), policy_bytes=len(policy),
                   fits_jobs_200=len(jobs) < 200, fits_policy_768=len(policy) < 768,
                   copyout_start='0x200', copyout_end_exclusive=hex(0x200 + len(policy)),
                   environment_string_start='0x400',
                   overlaps_environment=0x200 + len(policy) > 0x400)

    # Declarative 64-bit kmod_info layout under the source's pack(4), not a target compile.
    class Kmod64(ctypes.LittleEndianStructure):
        _pack_ = 4
        _fields_ = [('next', ctypes.c_uint64), ('info_version', ctypes.c_int32), ('id', ctypes.c_uint32),
                    ('name', ctypes.c_char * 64), ('version', ctypes.c_char * 64),
                    ('reference_count', ctypes.c_int32), ('reference_list', ctypes.c_uint64),
                    ('address', ctypes.c_uint64), ('size', ctypes.c_uint64), ('hdr_size', ctypes.c_uint64),
                    ('start', ctypes.c_uint64), ('stop', ctypes.c_uint64)]
    layout = dict(mode='Host model of source pack(4) and explicit 64-bit fields; not target ABI certification',
                  address=Kmod64.address.offset, start=Kmod64.start.offset, stop=Kmod64.stop.offset, sizeof=ctypes.sizeof(Kmod64))
    after = {name: read_git(repo, 'status', '--porcelain', '--untracked-files=no')
             for name, repo in [('base', BASE), ('xnu', XNU), ('sheng_reference', SHENG)]}
    report = dict(timestamp=datetime.now().astimezone().isoformat(), mode='Static interface audit; not compilation/link/runtime proof',
                  inputs=snapshots, after=after, evidence=excerpts, callback_matrix=callback_rows,
                  build_script_resolution=script_rows, kernel_archives_consumers=archive_consumers,
                  watchdog_scratch_case=overlap, kmod64_layout=layout,
                  board_sha256=hashlib.sha256((ROOT / 'board.toml').read_bytes()).hexdigest(),
                  base_feeds_sha256=hashlib.sha256((BASE / 'feeds.toml').read_bytes()).hexdigest())
    (OUT / 'interfaces.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if any(item['exit_code'] or item['stdout'] for item in after.values()):
        raise SystemExit('Read-only source status changed')
    print('Static interface audit recorded; no ABI/build pass claimed')
    print('Callbacks with reference definition:', sum(bool(row['reference_definitions']) for row in callback_rows), '/', len(names))
    print('Watchdog host-model scratch overlap:', overlap['overlaps_environment'], '; bytes=', len(policy))
    print('kmod64 model:', layout)


if __name__ == '__main__':
    main()
