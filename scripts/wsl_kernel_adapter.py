"""WSL first-stage input gate and non-executable 8796 build plan.

Never runs make/Git, prepares a source view, imports upstream code or emits images.
Compiler probes emit text IR to stdout; MIG probes emit C/header files in out/ only.
"""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ('cc', 'cxx', 'host_cc', 'host_cxx', 'mig', 'migcom', 'ld', 'ar', 'nm', 'libtool', 'iig')
EXPECTED_SIG = {'ptr': '1', 'data': '2', 'mixed': '12', 'overlap': '3', 'annotated': '1', 'array': '11'}
EXPECTED_SUM = {'ptr': 2, 'data': 4, 'mixed': 6, 'overlap': 8, 'annotated': 2, 'array': 2}
EXPECTED_CMP = {'same': 1, 'layout': 1, 'different': 0, 'wildcard': 1}


def output_path(path):
    path = Path(path).resolve()
    if not any(path.is_relative_to((ROOT / folder).resolve()) for folder in ('out', 'reports')):
        raise ValueError('Output must stay in this workspace out/ or reports/')
    return path


def run(argv, *, text=None, timeout=15):
    try:
        result = subprocess.run(list(map(str, argv)), input=text, capture_output=True,
                                encoding='utf-8', errors='replace', timeout=timeout,
                                env={**os.environ, 'LC_ALL': 'C', 'PYTHONDONTWRITEBYTECODE': '1'})
        return dict(command=list(map(str, argv)), exit_code=result.returncode,
                    stdout=result.stdout, stderr=result.stderr)
    except (OSError, subprocess.TimeoutExpired) as error:
        return dict(command=list(map(str, argv)), exit_code=None, stdout='', stderr=str(error))


def identity(spec, *, require_elf=True):
    value = spec.get('path')
    if not value:
        return dict(state='missing', reason='TODO path')
    path = Path(value)
    if not path.is_absolute() or not path.is_file():
        return dict(state='missing', path=value, reason='Absolute executable path required')
    raw = path.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    result = dict(path=str(path), resolved=str(path.resolve()), sha256=actual,
                  elf=raw.startswith(b'\x7fELF'), executable=os.access(path, os.X_OK))
    expected = spec.get('sha256')
    if not result['executable'] or (require_elf and not result['elf']):
        result.update(state='rejected', reason='Native ELF executable required')
    elif expected is None:
        result.update(state='unlocked', reason='TODO expected SHA-256; observed identity only')
    elif not re.fullmatch('[0-9a-f]{64}', expected) or expected != actual:
        result.update(state='rejected', reason='Expected SHA-256 mismatch')
    else:
        result['state'] = 'identity-match'
    return result


def fixture():
    lines = ['struct ptr { void *p; };', 'struct ptr2 { void *q; };',
             'struct data { unsigned long x; };', 'struct mixed { void *p; unsigned long x; };',
             'union overlap { void *p; unsigned long x; };',
             'struct annotated { unsigned long x __attribute__((xnu_usage_semantics("pointer"))); };',
             'struct array { void *p[2]; };',
             'typedef char arm64_layout[(sizeof(void *) == 8 && sizeof(unsigned long) == 8) ? 1 : -1];']
    for name in EXPECTED_SIG:
        kind = 'union' if name == 'overlap' else 'struct'
        lines += [f'const char *nuwa_sig_{name} = __builtin_xnu_type_signature({kind} {name});',
                  f'unsigned nuwa_sum_{name} = __builtin_xnu_type_summary({kind} {name});']
    for name, types in {'same': 'struct mixed, struct mixed', 'layout': 'struct ptr, struct ptr2',
                        'different': 'struct ptr, struct data', 'wildcard': 'struct mixed, void'}.items():
        lines.append(f'unsigned nuwa_cmp_{name} = __builtin_xnu_types_compatible({types});')
    return '\n'.join(lines) + '\n'


def inspect_ir(ir):
    strings = {}
    for match in re.finditer(r'^@([\w.$]+)\s*=.*?\bc"((?:[^"\\]|\\[0-9a-fA-F]{2})*)"', ir, re.M):
        strings[match[1]] = re.sub(r'\\([0-9a-fA-F]{2})', lambda m: chr(int(m[1], 16)), match[2]).rstrip('\0')
    observed = {'signature': {}, 'summary': {}, 'compatible': {}}
    for name in EXPECTED_SIG:
        line = re.search(r'^@nuwa_sig_' + name + r'\s*=([^\n]*)', ir, re.M)
        refs = re.findall(r'@([\w.$]+)', line[1]) if line else []
        observed['signature'][name] = next((strings[ref] for ref in refs if ref in strings), None)
    for category, prefix, expected in [('summary', 'sum', EXPECTED_SUM), ('compatible', 'cmp', EXPECTED_CMP)]:
        for name in expected:
            value = re.search(r'^@nuwa_' + prefix + '_' + name + r'\s*=.*?\bi32 (-?\d+)', ir, re.M)
            actual = int(value[1]) if value else None
            observed[category][name] = (actual & 0xffff) if category == 'summary' and actual is not None else actual
    expected = dict(signature=EXPECTED_SIG, summary=EXPECTED_SUM, compatible=EXPECTED_CMP)
    checks = [dict(category=category, case=name, expected=value, observed=observed[category][name],
                   matches=observed[category][name] == value)
              for category, values in expected.items() for name, value in values.items()]
    return dict(state='sample-match' if all(row['matches'] for row in checks) else 'sample-mismatch', checks=checks)


def compiler_probe(path, language, target):
    flags = [path, '-target', target, '-ffreestanding', '-nostdinc', '-x', language]
    expressions = dict(signature='__has_builtin(__builtin_xnu_type_signature)',
                       summary='__has_builtin(__builtin_xnu_type_summary)',
                       compatible='__has_builtin(__builtin_xnu_types_compatible)',
                       usage='__has_attribute(xnu_usage_semantics)')
    text = '\n'.join(f'#if {expr}\nNUWA_{key}=1\n#else\nNUWA_{key}=0\n#endif' for key, expr in expressions.items())
    feature = run(flags + ['-E', '-P', '-'], text=text)
    supported = {key: bool(re.search(r'^NUWA_' + key + '=1$', feature['stdout'], re.M)) for key in expressions}
    result = dict(version=run([path, '--version']), features=supported, feature_command=feature,
                  state='features-missing', semantics=None)
    if feature['exit_code'] != 0 or not all(supported.values()):
        return result
    # C linkage keeps emitted global names comparable across C and C++ probes.
    code = fixture()
    if language == 'c++':
        code = 'extern "C" {\n' + code + '}\n'
    compiled = run(flags + ['-Werror=unknown-attributes', '-S', '-emit-llvm', '-o', '-', '-'], text=code, timeout=30)
    result['ir_command'] = compiled
    if compiled['exit_code'] != 0:
        result['state'] = 'sample-compilation-failed'
        return result
    result['semantics'] = inspect_ir(compiled['stdout'])
    result['state'] = result['semantics']['state']
    return result


def sysroot_probe(spec):
    if not spec.get('path') or not spec.get('file_manifest'):
        return dict(state='missing', reason='TODO sysroot path and file_manifest')
    root, manifest = Path(spec['path']).resolve(), Path(spec['file_manifest'])
    if not root.is_dir() or not manifest.is_file():
        return dict(state='missing', reason='Sysroot or manifest not present')
    entries = json.loads(manifest.read_text(encoding='utf-8')).get('files', {})
    if not entries:
        return dict(state='rejected', reason='Empty sysroot manifest')
    for name, digest in entries.items():
        path = (root / name).resolve()
        if Path(name).is_absolute() or not path.is_relative_to(root) or not path.is_file():
            return dict(state='rejected', reason='Manifest path escapes root or is absent', entry=name)
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            return dict(state='rejected', reason='Manifest file hash mismatch', entry=name)
    return dict(state='manifest-match', path=str(root), files=len(entries),
                manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
                limitation='Integrity only; SDK/header completeness not certified')


def preflight(config, directory):
    if platform.system() != 'Linux':
        raise ValueError('Run preflight inside WSL/Linux')
    if config.get('schema_version') != 1 or config.get('target') != 'arm64-apple-ios16.0':
        raise ValueError('Unsupported host manifest schema or target')
    tools = {name: identity(config.get('tools', {}).get(name, {}), require_elf=name != 'mig') for name in TOOLS}
    compilers = {}
    for name, language in [('cc', 'c'), ('cxx', 'c++')]:
        if tools[name]['state'] in {'identity-match', 'unlocked'}:
            compilers[name] = compiler_probe(config['tools'][name]['path'], language, config['target'])
    generated = output_path(ROOT / 'out/wsl-toolchain/mig-smoke')
    generated.mkdir(parents=True, exist_ok=True)
    mig = dict(state='not-run', reason='MIGCOM identity not pinned/matched')
    if tools['migcom']['state'] == 'identity-match':
        header, user, server = [generated / name for name in ('probe.h', 'probe-user.c', 'probe-server.c')]
        for path in (header, user, server):
            if path.exists():
                path.unlink()  # Fixed, resolved workspace outputs; stale successes must not survive.
        result = run([config['tools']['migcom']['path'], '-header', header, '-user', user, '-server', server],
                     text='subsystem unixnu_toolchain 42000;\ntype audit_port_t = MACH_MSG_TYPE_COPY_SEND;\nroutine ping(server: audit_port_t);\n')
        valid = result['exit_code'] == 0 and all(path.is_file() and path.stat().st_size > 0 for path in (header, user, server))
        valid = valid and 'ping' in header.read_text(encoding='utf-8', errors='replace')
        mig = dict(state='codegen-smoke-match' if valid else 'codegen-smoke-failed', command=result,
                   outputs=[dict(path=str(path.relative_to(ROOT)), bytes=path.stat().st_size,
                                 sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                            for path in (header, user, server) if path.is_file()],
                   limitation='MIG backend generation only; no SDK compile, target execution or IIG proof')
    host_samples = {}
    for name, language, code in [('host_cc', 'c', '#include <stdio.h>\n#include <stdlib.h>\n#include <stdint.h>\nint main(void) { return sizeof(uint64_t) != 8; }\n'),
                                 ('host_cxx', 'c++', '#include <new>\n#include <type_traits>\nstatic_assert(std::is_integral<int>::value, "host C++ headers");\n')]:
        if tools[name]['state'] == 'identity-match':
            checked = run([config['tools'][name]['path'], '-x', language, '-fsyntax-only', '-'], text=code)
            host_samples[name] = dict(state='syntax-sample-match' if checked['exit_code'] == 0 else 'syntax-sample-failed',
                                      command=checked, limitation='Host syntax/headers only; not a linked host SETUP tool')
    source_path = Path(config['source']['path'])
    source = dict(path=str(source_path), expected_head=config['source']['head_reference'])
    master = source_path / 'config/MasterVersion'
    source.update(master_version=master.read_text(encoding='utf-8').splitlines()[0] if master.is_file() else None)
    source['state'] = 'master-match' if source['master_version'] == config['source']['expected_master_version'] else 'master-mismatch'
    source['limitation'] = 'MasterVersion check only; no Git access or patched-view provenance claim'
    roots = {name: sysroot_probe(config.get('sysroots', {}).get(name, {})) for name in ('target', 'host', 'kernel_exported')}
    blockers = [f'tool:{name}:{item["state"]}' for name, item in tools.items() if item['state'] != 'identity-match']
    blockers += [f'compiler:{name}:{compilers.get(name, {}).get("state", "not-run")}'
                 for name in ('cc', 'cxx') if compilers.get(name, {}).get('state') != 'sample-match']
    blockers += [f'host:{name}:{host_samples.get(name, {}).get("state", "not-run")}'
                 for name in ('host_cc', 'host_cxx') if host_samples.get(name, {}).get('state') != 'syntax-sample-match']
    blockers += [f'sysroot:{name}:{item["state"]}' for name, item in roots.items() if item['state'] != 'manifest-match']
    if mig['state'] != 'codegen-smoke-match':
        blockers.append('mig:backend-smoke-not-passed')
    if source['state'] != 'master-match':
        blockers.append('source:master-version-mismatch')
    if not config.get('sdk_version'):
        blockers.append('sdk_version:TODO')
    # This first-stage gate never authorizes a full build, even if tools later pass.
    return dict(timestamp=datetime.now().astimezone().isoformat(),
                state='inputs-incomplete' if blockers else 'input-samples-match', blockers=blockers,
                tools=tools, compilers=compilers, host_samples=host_samples, sysroots=roots, source=source, mig_backend=mig,
                may_execute_kernel_build=False, kernel_built=False,
                pending_build_gates=['approved writable source view', 'complete host-tool adaptation',
                                     '8796 archive/compile-record production', 'independent compile/link evidence'])


def plan(config, report):
    paths = {name: value.get('path') for name, value in config['tools'].items()}
    roots = config['sysroots']
    return dict(executable=False, reason='First-stage plan only; no make execution mode is implemented',
                preflight_state=report['state'], blockers=report['blockers'],
                expected_raw_kernel='build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/mach.development.bcm2837.unstripped',
                feed_changed=False, board_changed=False,
                make_variables={'CC': paths['cc'], 'CXX': paths['cxx'], 'HOST_CC': paths['host_cc'],
                                'HOST_CXX': paths['host_cxx'], 'MIG': paths['mig'], 'MIGCOM': paths['migcom'],
                                'MIGCC': paths['cc'], 'IIG': paths['iig'], 'AR': paths['ar'],
                                'NM': paths['nm'], 'LIBTOOL': paths['libtool'],
                                'SDKROOT_RESOLVED': roots['target']['path'], 'HOST_SDKROOT_RESOLVED': roots['host']['path'],
                                'SDKVERSION': config['sdk_version'], 'PLATFORM': 'iPhoneOS',
                                'RC_DARWIN_KERNEL_VERSION': '22.6.0', 'RC_ProjectSourceVersion': '8796.141.3',
                                'ARCH_CONFIGS': 'ARM64', 'MACHINE_CONFIGS': 'BCM2837', 'KERNEL_CONFIGS': 'DEVELOPMENT',
                                'DEPLOYMENT_TARGET_FLAGS': '-miphoneos-version-min=16.0 -DXNU_TARGET_OS_IOS',
                                'DEPLOYMENT_LINKER_FLAGS': '-Wl,-ios_version_min,16.0'},
                adaptation_tasks=['replace all .unstripped.noctf consumers with verified 8796 artifact mapping',
                                  'record actual successful CC/CXX arguments per object; database-only mode is insufficient',
                                  'schedule archives from explicit device-owned implementation; baseline does not consume archives',
                                  'replace remaining Darwin host SETUP/tool calls with proven Linux equivalents',
                                  'leave watchdog/PGZ/board-specific code disabled until its own interface gates pass'],
                link_driver={'source_contract': 'makedefs/MakeInc.def:619: LD = $(KC++) -nostdlib',
                             'candidate_backend': paths['ld'],
                             'state': 'TODO prove CXX driver selects this backend; do not pass -Wl options directly to ld'})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('preflight', 'plan'))
    parser.add_argument('--config', type=Path, default=ROOT / 'config/toolchains/wsl-8796.example.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'reports/wsl-firststage')
    args = parser.parse_args()
    output = output_path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    config = json.loads(args.config.read_text(encoding='utf-8'))
    report = preflight(config, output)
    report['manifest_sha256'] = hashlib.sha256(args.config.read_bytes()).hexdigest()
    output_path(output / 'preflight.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    if args.mode == 'plan':
        output_path(output / 'adapter-plan.json').write_text(json.dumps(plan(config, report), indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(report['state'])
    for blocker in report['blockers']:
        print('BLOCK:', blocker)
    print('Kernel build execution: disabled; reports:', output)
    return 2 if report['blockers'] else 0


if __name__ == '__main__':
    sys.exit(main())
