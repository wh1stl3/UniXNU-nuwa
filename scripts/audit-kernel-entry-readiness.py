"""Read the current kernel's actual symbol table and fixed ADT consumers.

No execution, prelink output, target ADT generation, flags or board changes.
"""
import datetime
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('D:/Code/PortingiOSLegacy/common/sources/UniXNU')
SHENG = Path('D:/Code/PortingiOSLegacy/common/sources/UniXNU-sheng')
OUT = ROOT / 'reports/darwin22-input-contracts/readiness.json'
GIT = 'C:/Program Files/Git/cmd/git.exe'
CALLBACKS = ['init', 'start', 'active', 'bind', 'putc', 'stage', 'irq', 'poll',
             'user_breakpoint', 'user_abort', 'critical_exit', 'process_stage', 'exit']


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    if OUT.exists():
        raise ValueError('Fresh evidence required')
    path = next((ROOT / 'out/kernel-ci/39793231214').glob('**/mach.development.bcm2837.unstripped'))
    data = path.read_bytes()
    if sha(data) != '77742999fc1c1b6a94c9603664d946553070f73c6eed83ce9fcca06d70d73ac8':
        raise ValueError('Unexpected source kernel')
    magic, cpu, subtype, kind, count, command_bytes = struct.unpack_from('<6I', data)
    if (magic, cpu, subtype, kind) != (0xfeedfacf, 0x100000c, 0, 2):
        raise ValueError('Unexpected Mach-O')
    cursor = 32
    symbols = None
    build_version = None
    debug_sections = []
    for _ in range(count):
        command, size = struct.unpack_from('<II', data, cursor)
        if size < 8 or cursor + size > 32 + command_bytes:
            raise ValueError('Invalid load command')
        if command == 2:
            if symbols is not None:
                raise ValueError('Duplicate symbol table')
            symbols = struct.unpack_from('<4I', data, cursor + 8)
        if command == 0x32:
            platform, minimum, sdk, tools = struct.unpack_from('<4I', data, cursor + 8)
            build_version = dict(platform=platform, minimum_os_raw=minimum, sdk_raw=sdk)
        if command == 0x19:
            nsects, = struct.unpack_from('<I', data, cursor + 64)
            if 72 + 80 * nsects > size:
                raise ValueError('Invalid section count')
            for index in range(nsects):
                name = data[cursor + 72 + 80 * index:cursor + 88 + 80 * index].split(b'\0')[0].decode()
                if name.startswith('__debug_'):
                    debug_sections.append(name)
        cursor += size
    if cursor != 32 + command_bytes or symbols is None:
        raise ValueError('Invalid command or symbol table')
    offset, length, strings, string_bytes = symbols
    if offset + 16 * length > len(data) or strings + string_bytes > len(data):
        raise ValueError('Symbol table bounds')
    defined, undefined = set(), set()
    for index in range(length):
        name_at, typ, section, desc, value = struct.unpack_from('<IBBHQ', data, offset + index * 16)
        if typ & 0xe0 or not typ & 1:
            continue  # STAB debug records are not external undefined symbols.
        if name_at >= string_bytes:
            raise ValueError('String index outside table')
        end = data.index(b'\0', strings + name_at, strings + string_bytes)
        name = data[strings + name_at:end].decode()
        if typ & 0x0e:
            defined.add(name)
        elif value == 0:
            undefined.add(name)
    required = ['_armcpu_registered', '_armcpu_gic_ready', '_armcpu_timer_interrupts',
                '_armdt_platform_configured', '_armdt_platform_nvram_proxy']
    if undefined or not all(name in defined for name in required):
        raise ValueError('Actual symbol closure differs from CI report')
    archives = json.loads((ROOT / 'reports/kernel-ci/39793231214/driver-archives/audit.json').read_text())
    driver_sources = []
    for component in archives['components']:
        name = component['component']
        source = BASE / 'drivers' / name / (name + '.cpp')
        if sha(source.read_bytes()) != component['source_sha256']:
            raise ValueError('Driver source differs from CI compilation: ' + name)
        driver_sources.append(dict(component=name, sha256=component['source_sha256'],
                                   linked_in_current_kernel=name in ('ArmCpu', 'ArmDTPlatform')))
    sources = []

    def pinned(root, commit, relative, license_name):
        raw = subprocess.check_output([GIT, '-c', f'safe.directory={root}', '-C', str(root), 'show', commit + ':' + relative])
        sources.append(dict(repository='UniXNU/UniXNU-sheng' if root == SHENG else 'UniXNU/UniXNU',
                            commit=commit, path=relative, sha256=sha(raw), license=license_name))
        return raw.decode()

    platform_source = pinned(BASE, '75bc13dd34dc4e403826793739e316a264ce00dd',
                             'drivers/ArmDTPlatform/ArmDTPlatform.cpp', 'BSD-2-Clause-Patent')
    references = {name: pinned(SHENG, 'a599a1a8a92093b5077543e071b72130769eb325',
                              'package/' + name, 'MIT')
                  for name in ('BootProgress.c', 'BootFaultProbe.c', 'BootWatchdogPolicy.c')}
    nuwa = [p for folder in ('drivers', 'kits', 'package') for p in (ROOT / folder).rglob('*')
            if p.is_file() and p.suffix in ('.c', '.cpp', '.h')]
    callbacks = []
    for short in CALLBACKS:
        name = 'boot_progress_' + short
        pattern = re.compile(r'\b' + name + r'\s*\([^;{}]*\)\s*\{', re.M)
        callbacks.append(dict(name=name, defined_in_actual_kernel='_' + name in defined,
                              nuwa_definition_files=[str(p.relative_to(ROOT)) for p in nuwa if pattern.search(p.read_text())],
                              same_soc_reference=[dict(path='package/' + p, line=s[:m.start()].count('\n') + 1)
                                                  for p, s in references.items() for m in pattern.finditer(s)],
                              enabled_in_current_build=False))
    flags = json.loads((ROOT / 'reports/kernel-ci/39793231214/platform-link/audit.json').read_text())['make_arguments']
    runtime_flags = [s for s in flags if 'XNU_NATIVE_ARCH_TIMER=' in s or 'XNU_BOOT_PROGRESS=' in s]
    if not any('XNU_BOOT_PROGRESS=0' in s for s in runtime_flags) or not any('XNU_NATIVE_ARCH_TIMER=0' in s for s in runtime_flags):
        raise ValueError('Runtime feature flags differ from the audited baseline')
    provider_requirements = [dict(path='/' + name, source_line=i + 1)
                             for i, line in enumerate(platform_source.splitlines())
                             for name in re.findall(r'childFromPath \("([^"]+)"', line)]
    report = dict(at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  scope='Actual kernel symbol and fixed consumer-source audit; not complete ABI or boot qualification',
                  kernel=dict(path=str(path.relative_to(ROOT)), sha256=sha(data), bytes=len(data), build_version=build_version,
                              undefined_external_symbols=sorted(undefined), required_driver_exports={n: n in defined for n in required},
                              inline_debug_sections=debug_sections,
                              downloaded_dsym_paths=[str(p.relative_to(ROOT)) for p in path.parents[5].glob('**/Resources/DWARF/mach.development.bcm2837')]),
                  compiled_driver_sources=driver_sources, sources=sources, runtime_flags=runtime_flags, callbacks=callbacks,
                  adt_platform_requirements=provider_requirements,
                  nvram_requirement=dict(path='/chosen', bank_size_bytes=4, proxy_data='nonempty; full CHRP semantics also require IODTNVRAM validation'),
                  watchdog=dict(reference_policy_defined_in_kernel='_sheng_boot_watchdog_policy' in defined,
                                reference_role='Writes launchd scratch-Data policy before launchd; not a hardware watchdog driver',
                                nuwa_hardware_backend='TODO: source selection, real resources and Darwin22 ABI/runtime evidence'),
                  blockers=['Real target Apple ADT and matching conditional sidecars are not supplied',
                            'Complete native prelink donor/component runtime ABI not qualified',
                            'Architectural timer and boot-progress hooks remain disabled; absence is not a current link failure',
                            'BootProgress reference is MIT same-SoC source, not an adopted nuwa hardware driver'],
                  unchanged=['board.toml', 'feeds.toml', 'bringup-plan.json', 'all verified flags'], device_accessed=False)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(required_exports=len(required), undefined_external_symbols=len(undefined),
                         missing_boot_progress_callbacks=sum(not x['defined_in_actual_kernel'] for x in callbacks),
                         compiled_driver_sources=driver_sources, device_accessed=False), indent=2))


if __name__ == '__main__':
    main()
