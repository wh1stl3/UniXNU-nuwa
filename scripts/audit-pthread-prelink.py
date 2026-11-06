"""Audit the real iOS16 donor pthread component missing from the current selection.

Emit only an offline analysis prelink. A direct module-start test establishes
native function-table registration and dispatch, not OSKext lifecycle readiness.
"""
import argparse
import importlib.util
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'out/python-tools')]
import native_prelink_inputs as N
import unicorn as U
from unicorn.arm64_const import *

spec = importlib.util.spec_from_file_location('probe', ROOT / 'scripts/build-kernel-entry-probe.py')
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)
NAME = 'com.apple.kec.pthread'
STACK = 0xf00000


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--work', type=Path, required=True)
    cli.add_argument('--output', type=Path, required=True)
    a = cli.parse_args()
    work, output = a.work.resolve(), a.output.resolve()
    if not work.is_relative_to(ROOT / 'out') or work.exists() or not output.is_relative_to(ROOT / 'reports') or output.exists():
        raise ValueError('Fresh local analysis outputs required')
    profile_path = ROOT / 'config/native-prelink-merged-analysis-profile.json'
    profile, native, donor, selection = N.inputs(profile_path)
    slide = profile['slide']
    old_emission = json.loads((ROOT / 'out/earlysec-2026-10-24/emission.json').read_text())
    early = {k: v - slide for k, v in old_emission['early_security_initializers'].items()}
    checks = []

    def check(name, passed):
        if not passed:
            raise AssertionError(name)
        checks.append({'name': name, 'passed': True})

    with N.tools(True, profile_path) as (parser, emitter):
        parent, metadata, _ = N.components(parser, donor, selection)
        entry = next(e for e in metadata['_PrelinkInfoDictionary'] if e['CFBundleIdentifier'] == NAME)
        check('Real iOS16 pthread bundle exists in the pinned donor but is not selected',
              NAME not in selection['components'] and entry.get('DTPlatformVersion', '').startswith('16.'))
        roots = selection['components'] + selection['codeless_components']
        old, _ = emitter.emit(native, donor, roots, slide, early)
        check('Emitter reproduces the exact current early-security baseline', B.sha(old) == B.EXPECTED)
        plan = parser.plan(native, donor, roots + [NAME], slide)
        image, full = emitter.emit(native, donor, roots + [NAME], slide, early)
        check('Adding only pthread closes all kernel/component bindings',
              set(plan['components']) == set(selection['components']) | {NAME})
        macho = B.macho(image)
        original_module = parser.macho(donor, parser.backed_offset(parent, entry['_PrelinkExecutableLoadAddr'], 32, len(donor)))
        executable = []
        for seg in original_module['segments']:
            if seg['name'] == '__TEXT_EXEC' and seg['filesize']:
                before = parser.backed_offset(parent, seg['va'], seg['filesize'], len(donor))
                after = B.backed(macho, seg['va'] + slide, seg['filesize'])
                check('pthread executable bytes preserved from donor',
                      donor[before:before + seg['filesize']] == image[after:after + seg['filesize']])
                executable.append((seg['va'] + slide, seg['filesize']))
        # kmod.h explicitly uses #pragma pack(4); the 64-bit start member is at
        # byte 180, not the naturally aligned offset 184.
        kmod = entry['_PrelinkKmodInfo'] + slide
        start = struct.unpack_from('<Q', image, B.backed(macho, kmod + 180, 8))[0]
        check('Real packed-4 kmod start points inside pthread executable text',
              any(base <= start < base + size for base, size in executable))
        u = U.Uc(U.UC_ARCH_ARM64, U.UC_MODE_ARM)
        base = min(s['va'] for s in macho['segments'] if s['size'])
        end = max(s['va'] + s['size'] for s in macho['segments'])
        u.mem_map(base, B.align(end - base))
        u.mem_map(STACK, 0x10000)
        for seg in macho['segments']:
            if seg['filesize']:
                u.mem_write(seg['va'], image[seg['fileoff']:seg['fileoff'] + seg['filesize']])
        u.reg_write(UC_ARM64_REG_CPACR_EL1, 3 << 20)
        syms = macho['symbols']
        bad, calls, panic = [], [], []
        stop_dispatch = [None]

        def read64(address):
            return int.from_bytes(u.mem_read(address, 8), 'little')

        def watch(u, pc, size, data):
            if pc == syms['_pthread_kext_register']:
                calls.append({'functions': hex(u.reg_read(UC_ARM64_REG_X0)),
                              'callbacks_out': hex(u.reg_read(UC_ARM64_REG_X1))})
            if pc == syms['_panic']:
                address = u.reg_read(UC_ARM64_REG_X0)
                panic.append(bytes(u.mem_read(address, 160)).split(b'\0')[0].decode())
                u.emu_stop()
            if pc == stop_dispatch[0]:
                u.emu_stop()

        u.hook_add(U.UC_HOOK_CODE, watch)
        u.hook_add(U.UC_HOOK_MEM_INVALID, lambda u, access, address, size, value, data: bad.append([access, hex(address)]) or False)

        def run(address, x0=0, x1=0):
            u.reg_write(UC_ARM64_REG_SP, STACK + 0x8000)
            u.reg_write(UC_ARM64_REG_LR, STACK)
            u.reg_write(UC_ARM64_REG_X0, x0)
            u.reg_write(UC_ARM64_REG_X1, x1)
            u.emu_start(address, STACK, count=1000000)

        check('Native pthread function table starts NULL', read64(syms['_pthread_functions']) == 0)
        run(syms['_pthread_init'])
        check('Unregistered native pthread_init reproduces the physical panic format',
              len(panic) == 1 and panic[0].startswith('pthread kernel extension not loaded (function table is NULL).'))
        original_panic = panic[0]
        panic.clear()
        run(start, kmod)
        table = read64(syms['_pthread_functions'])
        check('Real donor kmod start registers through native pthread_kext_register',
              u.reg_read(UC_ARM64_REG_PC) == STACK and u.reg_read(UC_ARM64_REG_X0) == 0 and len(calls) == 1 and table != 0 and not panic and not bad)
        callbacks = read64(int(calls[0]['callbacks_out'], 16))
        init = read64(table + 8)
        check('Registration returns native callback table and real donor pthread_init target',
              callbacks == syms['_pthread_callbacks'] and any(base <= init < base + size for base, size in executable))
        stop_dispatch[0] = init
        run(syms['_pthread_init'])
        check('Native wrapper dispatches to the actual donor initializer after registration',
              u.reg_read(UC_ARM64_REG_PC) == init and not panic and not bad)
        stop_dispatch[0] = None
        run(start, kmod)
        check('Duplicate registration retains the native rejection',
              len(panic) == 1 and panic[0].startswith('Re-initialisation of pthread kext callbacks.'))
        work.mkdir(parents=True)
        target = work / 'kernel-pthread-analysis.macho'
        target.write_bytes(image)
        (work / 'full-plan.json').write_bytes(json.dumps(plan, indent=2).encode() + b'\n')
        (work / 'full-emission.json').write_bytes(json.dumps(full, indent=2).encode() + b'\n')
        report = {'scope': __doc__, 'checks': checks, 'native_sha256': N.sha(native),
                  'donor_sha256': N.sha(donor), 'old_baseline_sha256': B.EXPECTED,
                  'bundle': NAME, 'bundle_metadata': {k: entry[k] for k in ('DTPlatformVersion', 'DTSDKName', 'MinimumOSVersion', 'CFBundleVersion', 'OSBundleRequired', 'OSBundleLibraries')},
                  'selected_before': len(selection['components']), 'selected_after': len(plan['components']),
                  'pointer_counts': plan['pointer_counts'], 'module_start': hex(start),
                  'original_panic_format': original_panic, 'duplicate_panic_format': panic[0],
                  'functions_table': hex(table), 'native_callbacks': hex(callbacks), 'pthread_init_target': hex(init),
                  'candidate': {'path': target.relative_to(ROOT).as_posix(), 'sha256': N.sha(image), 'bytes': len(image)},
                  'model': {'registration_calls': calls, 'bad_memory': bad,
                            'pthread_initializer_body_executed': False, 'os_kext_lifecycle_executed': False},
                  'next': 'Integrate selection and request the genuine OSKext start before BSD pthread_init; validate lifecycle and body. Do not bypass the native NULL-table check or call a fake table.',
                  'loadable': False, 'runtime_qualified': False, 'device_accessed': False}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(json.dumps(report, indent=2).encode() + b'\n')
    print(json.dumps({'checks': len(checks), 'passed': True, 'components': len(plan['components']), 'registered_real_table': True}))


if __name__ == '__main__':
    main()
