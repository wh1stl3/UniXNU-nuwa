#!/usr/bin/env python3
"""Audit fresh prelink and emulate donor start/native registration, not OSKext lifecycle."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys

import unicorn as U
from unicorn.arm64_const import *

sys.dont_write_bytecode = True
NAME = 'com.apple.kec.pthread'
TREE = Path('/root/nuwa-pmap-ret-native-20261111/nuwa/ios-16.7.16-20H392/nuwa_pmap_ret/tree')
DONOR = Path('/mnt/d/Code/PortingiOS/UniXNU/out/ipsw/20H392/kernelcache.decompressed')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prelink', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    assert not a.output.exists()
    spec = importlib.util.spec_from_file_location('reader', TREE / 'kits/XnuPrelink/native_prelink.py')
    r = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(r)
    raw, donor = a.prelink.read_bytes(), DONOR.read_bytes()
    manifest = json.loads(a.prelink.with_suffix('.json').read_text())
    old = json.loads(Path('/root/nuwa-pmap-ret-native-20261111/nuwa/ios-16.7.16-20H392/nuwa_pmap_ret/kernel/kernel.json').read_text())
    assert sha(raw) == manifest['candidate_sha256'] and sha(donor) == manifest['original_sha256']
    assert set(manifest['components']) == set(old['components']) | {NAME}
    assert manifest['kernel_interfaces'] == old['kernel_interfaces']
    image, orig = r.macho(raw), r.macho(donor)

    def off(img, data, va, size):
        return r.backed_offset(img['segments'], va, size, len(data))

    def info(img, data):
        s, = [s for seg in img['segments'] for s in seg['sections']
              if seg['name'] == '__PRELINK_INFO' and s['name'] == '__info']
        at = off(img, data, s['va'], s['size'])
        return r.unserialize_xml(data[at:at + s['size']])['_PrelinkInfoDictionary']

    entries = info(image, raw)
    entry, = [x for x in entries if x.get('CFBundleIdentifier') == NAME]
    source, = [x for x in info(orig, donor) if x.get('CFBundleIdentifier') == NAME]
    assert entry['AppleKernelExternalComponent'] is True and entry['OSBundleRequired'] == 'Root'
    assert entry['OSBundleLibraries'] == source['OSBundleLibraries']
    assert set(entry['OSBundleLibraries']) <= set(manifest['components'] + manifest['kernel_interfaces'])
    mod = r.macho(raw, off(image, raw, entry['_PrelinkExecutableLoadAddr'], 32))
    origmod = r.macho(donor, off(orig, donor, source['_PrelinkExecutableLoadAddr'], 32))
    executable = []
    for seg in origmod['segments']:
        if seg['name'] == '__TEXT_EXEC' and seg['filesize']:
            va = seg['va'] + manifest['slide']
            assert donor[off(orig, donor, seg['va'], seg['filesize']):][:seg['filesize']] == raw[off(image, raw, va, seg['filesize']):][:seg['filesize']]
            executable.append((va, seg['filesize']))
    assert executable
    kmod = entry['_PrelinkKmodInfo']
    start = struct.unpack_from('<Q', raw, off(image, raw, kmod + 180, 8))[0]
    assert start == manifest['module_entrypoints'][NAME]['start_va']
    assert any(base <= start < base + size for base, size in executable)
    bindings = [b for b in manifest['bindings'] if b['module'] == NAME]
    assert bindings
    for b in bindings:
        value = struct.unpack_from('<Q', raw, off(image, raw, b['new_site'], 8))[0]
        assert value == b['new_target'], b
    symbols, undefined = {}, []
    for cmd, pos, _ in image['commands']:
        if cmd != 2:
            continue
        symoff, count, stroff, _ = struct.unpack_from('<4I', raw, pos + 8)
        for i in range(count):
            s, typ, _, _, val = struct.unpack_from('<IBBHQ', raw, symoff + i * 16)
            if typ & 0xe0:
                continue
            name = raw[stroff + s:raw.index(b'\0', stroff + s)].decode('utf-8')
            if typ & 0xe == 0 and name:
                undefined.append(name)
            elif typ & 0xe == 0xe:
                symbols[name] = val
    assert not undefined, undefined[:5]
    assert '_pthread_start' not in symbols and '_source_pthread_bootstrap' not in symbols

    u = U.Uc(U.UC_ARCH_ARM64, U.UC_MODE_ARM)
    base = min(s['va'] for s in image['segments'] if s['size']) & ~0xfff
    end = (max(s['va'] + s['size'] for s in image['segments']) + 0xfff) & ~0xfff
    u.mem_map(base, end - base)
    stack = 0xf00000
    u.mem_map(stack, 0x10000)
    for seg in image['segments']:
        if seg['filesize']:
            u.mem_write(seg['va'], raw[seg['fileoff']:seg['fileoff'] + seg['filesize']])
    u.reg_write(UC_ARM64_REG_CPACR_EL1, 3 << 20)
    panic, calls, invalid, target = [], [], [], [None]

    def read64(va):
        return int.from_bytes(u.mem_read(va, 8), 'little')

    def watch(uc, pc, size, data):
        if pc == symbols['_pthread_kext_register']:
            calls.append((uc.reg_read(UC_ARM64_REG_X0), uc.reg_read(UC_ARM64_REG_X1)))
        if pc == symbols['_panic']:
            ptr = uc.reg_read(UC_ARM64_REG_X0)
            panic.append(bytes(uc.mem_read(ptr, 160)).split(b'\0')[0].decode())
            uc.emu_stop()
        if pc == target[0]:
            uc.emu_stop()

    u.hook_add(U.UC_HOOK_CODE, watch)
    u.hook_add(U.UC_HOOK_MEM_INVALID, lambda uc, access, va, size, value, data: invalid.append(hex(va)) or False)

    def run(va, x0=0):
        u.reg_write(UC_ARM64_REG_SP, stack + 0x8000)
        u.reg_write(UC_ARM64_REG_LR, stack)
        u.reg_write(UC_ARM64_REG_X0, x0)
        u.reg_write(UC_ARM64_REG_X1, 0)
        u.emu_start(va, stack, count=1000000)

    assert read64(symbols['_pthread_functions']) == 0
    run(symbols['_pthread_init'])
    assert len(panic) == 1 and panic[0].startswith('pthread kernel extension not loaded (function table is NULL).')
    null_panic = panic.pop()
    run(start, kmod)
    table = read64(symbols['_pthread_functions'])
    assert u.reg_read(UC_ARM64_REG_PC) == stack and u.reg_read(UC_ARM64_REG_X0) == 0
    assert len(calls) == 1 and table and read64(calls[0][1]) == symbols['_pthread_callbacks'] and not panic and not invalid
    init = read64(table + 8)
    assert any(base <= init < base + size for base, size in executable)
    target[0] = init
    run(symbols['_pthread_init'])
    assert u.reg_read(UC_ARM64_REG_PC) == init and not panic and not invalid
    target[0] = None
    run(start, kmod)
    assert len(panic) == 1 and panic[0].startswith('Re-initialisation of pthread kext callbacks.')
    report = dict(status='self-checked', cwd=str(Path.cwd()), argv=sys.argv,
                  kernel_sha256=sha(raw), donor_sha256=sha(donor), unique_metadata_count=1,
                  metadata=entry, dependency_closure=True, native_undefined=undefined,
                  pthread_bindings=len(bindings), binding_values_match=True, executable_equal_donor=True,
                  kmod=hex(kmod), start=hex(start), table=hex(table), init_target=hex(init),
                  callbacks=hex(read64(calls[0][1])), null_panic=null_panic, duplicate_panic=panic[0],
                  invalid=invalid, instruction_relocation_complete=manifest['instruction_relocation_complete'],
                  abi_qualified=manifest['abi_qualified'],
                  limits='Direct module start only; OSKext lifecycle and pthread initializer body not executed; no device claim.')
    a.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'status': report['status'], 'bindings': len(bindings), 'start': hex(start)}))


if __name__ == '__main__':
    main()
