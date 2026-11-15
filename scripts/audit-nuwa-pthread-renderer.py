#!/usr/bin/env python3
"""Read-only renderer, whole-image delta and pthread binding audit."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
INPUT_SHA = '8ffb9f381cebfbfc56dd210901a9b7533b51cc3b95fba0719f4cd2b3972e3f6d'
NAME = 'com.apple.kec.pthread'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--python-tools', type=Path, required=True)
    a = p.parse_args()
    assert not a.output.exists()
    sys.path.insert(0, str(a.python_tools))
    import capstone
    import unicorn as U
    from unicorn.arm64_const import UC_ARM64_REG_PC, UC_ARM64_REG_SP, UC_ARM64_REG_X0, UC_ARM64_REG_X1
    helper = HERE / 'build-nuwa-pmap-ret-diagnostic.py'
    test = HERE / 'test-nuwa-pmap-ret-diagnostic.py'
    assert sha(helper.read_bytes()) == '819a99e6da4796e45a25171b3f6b1e35535c7442d0e77c2ae915e28029bf0506'
    assert sha(test.read_bytes()) == 'cd398d4694ea5fc6f183bc0cd5793e85f994661b164fd3f77fa63b73e9808d96'
    B = load(helper, 'pthread_renderer_audit_helper')
    T = load(test, 'pthread_renderer_audit_test')
    manifest = json.loads((a.build / 'renderer-manifest.json').read_text())
    raw = Path(manifest['input']['path']).read_bytes()
    final = (a.build / 'renderer-baseline.macho').read_bytes()
    assert sha(raw) == INPUT_SHA and sha(final) == manifest['output']['sha256']
    build = json.loads(Path(manifest['build_record']['path']).read_text())
    reader = B.load(Path(build['work']) / 'tree/kits/XnuPrelink/native_prelink.py', 'pthread_audit_reader')
    old, image = B.Image(reader, raw), B.Image(reader, final)
    native = B.Image(reader, Path(build['native']['path']).read_bytes())
    padding = B.padding_provenance(build, native, old, B.A.checked_link_map(build['link_map']))
    pmap = B.discover_pmap(old)
    entry, slot, message = B.validate_observer(old)
    assert B.validate_observer(image) == (entry, slot, message)
    assert old.word(pmap['ret']) == image.word(pmap['ret']) == 0xd65f03c0
    assert old.word(slot) == image.word(slot) == 0x14000000
    assert image.read(pmap['initializer'], pmap['end'] - pmap['initializer']) == old.read(pmap['initializer'], pmap['end'] - pmap['initializer'])
    start = old.symbols['__start']
    first_cpu = old.symbols['_start_first_cpu']
    mmu, = [pc for pc in range(first_cpu, first_cpu + 0x1000, 4)
            if old.word(pc) == 0xd5181000 and old.word(pc + 4) == 0xd5033fdf
            and old.word(pc + 0x20) == 0xd2a00600 and old.word(pc + 0x24) == 0xd5181040]
    bar1, bar2 = start + 0x78, start + 0x78 + 0x60
    code = (a.build / 'renderer/panic.bin').read_bytes()
    table = T.elf_table(a.build / 'renderer/panic.elf')
    render = table['panic_screen']['address']
    common = table['panic_screen_common']['address']
    main_addr = table['panic_screen_main']['address']
    assert render == bar2 + 0x60 and render + len(code) <= int(padding['vector'], 16) - 16
    assert code[:8] == struct.pack('<II', 0x910003e1, B.branch(render + 4, main_addr))
    assert code[common-render:common-render+8] == struct.pack('<II', 0xf9400021, B.branch(common + 4, main_addr))
    changes = {
        'entry-bar': (bar1, (a.build / 'bar-1/cave.bin').read_bytes()),
        'entry-hook': (start, struct.pack('<I', B.branch(start, bar1))),
        'MMU-bar': (bar2, (a.build / 'bar-2/cave.bin').read_bytes()),
        'MMU-hook': (mmu, struct.pack('<I', B.branch(mmu, bar2))),
        'renderer-blob': (render, code),
        '_panic-hook': (old.symbols['_panic'], struct.pack('<I', B.branch(old.symbols['_panic'], render))),
        '_panic_trap_to_debugger-hook': (old.symbols['_panic_trap_to_debugger'], struct.pack('<I', B.branch(old.symbols['_panic_trap_to_debugger'], common))),
    }
    assert len(manifest['patches']) == len(changes) == len({x['label'] for x in manifest['patches']})
    rebuilt = bytearray(raw)
    for item in manifest['patches']:
        va, after = changes[item['label']]
        at = old.offset(va, len(after))
        old.span(va, len(after), 5)
        before = raw[at:at + len(after)]
        assert item['va'] == hex(va) and item['fileoff'] == hex(at) and item['size'] == len(after)
        assert item['before_hex'] == before.hex() and item['after_hex'] == after.hex()
        assert item['before_sha256'] == sha(before) and item['after_sha256'] == sha(after)
        rebuilt[at:at + len(after)] = after
    assert bytes(rebuilt) == final
    runs = []
    start_offset = None
    for pos, (before, after) in enumerate(zip(raw, final)):
        if before != after and start_offset is None:
            start_offset = pos
        if before == after and start_offset is not None:
            runs.append(dict(offset=hex(start_offset), before=raw[start_offset:pos].hex(), after=final[start_offset:pos].hex()))
            start_offset = None
    if start_offset is not None:
        runs.append(dict(offset=hex(start_offset), before=raw[start_offset:].hex(), after=final[start_offset:].hex()))
    assert sum(len(bytes.fromhex(x['before'])) for x in runs) == manifest['changed_bytes']
    md = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)
    md.detail = True
    cfg = T.renderer_cfg(md, code, render, table)
    pointers = T.renderer_pointer_inputs(md, image, code, render, table)
    abi = []
    for label, hook, expected_x1 in (('ordinary', old.symbols['_panic'], 0x200800),
                                      ('common', old.symbols['_panic_trap_to_debugger'], 0x200a00)):
        uc = U.Uc(U.UC_ARCH_ARM64, U.UC_MODE_ARM)
        pages = set()
        for va, size in ((hook, 4), (render, len(code))):
            for page in range(va & ~0xfff, (va + size + 0xfff) & ~0xfff, 0x1000):
                if page not in pages:
                    uc.mem_map(page, 0x1000)
                    pages.add(page)
        uc.mem_map(0x200000, 0x2000)
        uc.mem_write(hook, image.read(hook, 4))
        uc.mem_write(render, code)
        uc.mem_write(0x200900, struct.pack('<Q', 0x200a00))
        uc.reg_write(UC_ARM64_REG_SP, 0x200800)
        uc.reg_write(UC_ARM64_REG_X0, 0x201000)
        uc.reg_write(UC_ARM64_REG_X1, 0x200900)
        uc.emu_start(hook, main_addr, count=10)
        assert uc.reg_read(UC_ARM64_REG_PC) == main_addr
        assert uc.reg_read(UC_ARM64_REG_X0) == 0x201000 and uc.reg_read(UC_ARM64_REG_X1) == expected_x1
        abi.append(dict(hook=label, x0='0x201000', x1=hex(expected_x1), main=hex(main_addr)))
    def prelink_info(obj):
        section, = [s for seg in obj.image['segments'] for s in seg['sections'] if seg['name'] == '__PRELINK_INFO' and s['name'] == '__info']
        return reader.unserialize_xml(obj.read(section['va'], section['size']))['_PrelinkInfoDictionary']
    old_entry, = [x for x in prelink_info(old) if x.get('CFBundleIdentifier') == NAME]
    new_entry, = [x for x in prelink_info(image) if x.get('CFBundleIdentifier') == NAME]
    assert old_entry == new_entry and new_entry['AppleKernelExternalComponent'] is True
    prelink_manifest = json.loads(Path(manifest['input']['path']).with_suffix('.json').read_text())
    bindings = [b for b in prelink_manifest['bindings'] if b['module'] == NAME]
    assert len(bindings) == 95
    for b in bindings:
        va = b['new_site']
        assert struct.unpack('<Q', old.read(va, 8))[0] == struct.unpack('<Q', image.read(va, 8))[0] == b['new_target']
    kmod = new_entry['_PrelinkKmodInfo']
    assert old.read(kmod, 196) == image.read(kmod, 196)
    report = dict(status='self-checked', cwd=str(Path.cwd()), argv=sys.argv, input_sha256=sha(raw),
                  output_sha256=sha(final), output_bytes=len(final), exact_difference_runs=runs,
                  changed_bytes=manifest['changed_bytes'], pmap_ret=hex(pmap['ret']), observer_slot=hex(slot),
                  hook_abi=abi, renderer_cfg=cfg, renderer_pointer_inputs=pointers,
                  pthread_metadata_unchanged=True, pthread_bindings_checked=len(bindings),
                  pthread_kmod_start=hex(struct.unpack('<Q', image.read(kmod + 180, 8))[0]),
                  limits='Model executes only hook/entry instructions. Runtime framebuffer, full renderer, OSKext and device not executed.')
    a.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'status': report['status'], 'output_sha256': report['output_sha256'],
                      'changed_bytes': report['changed_bytes'], 'difference_runs': len(runs),
                      'pthread_bindings': len(bindings), 'abi': abi}, indent=2))


if __name__ == '__main__':
    main()
