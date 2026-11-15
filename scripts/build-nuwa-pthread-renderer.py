#!/usr/bin/env python3
"""Render-only profile for the independently verified pthread prelink."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BASE = Path('/mnt/d/Code/PortingiOS/UniXNU')
UEFI = ROOT.parent / 'uefi-nuwa'
OLD = Path('/root/nuwa-pmap-ret-native-20261111/build-result.json')
NATIVE_SHA = '4a5bf5cc4f6920409b09fdf11eea21389b52b490e247515ab07ffdd38a7f8aa2'
INPUT_SHA = '8ffb9f381cebfbfc56dd210901a9b7533b51cc3b95fba0719f4cd2b3972e3f6d'
FONT_SHA = '7749b211129f6f669f53fd9ee16b8e8dc9464aad41ba1bb6f7ce9b45c4eb2f1d'
SOURCE_HASHES = {'patch-xnu-entry-probe.py': '159eb1ea8d6c1da30f26913a281f46e21d940a1ae7886656529907ec3edf96ad',
                 'xnu-panic-screen.c': '54b950a7d83c30f7720d30551c6d5f10cea5e40dcccc5adb2b4c70a98240a68b'}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prelink', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    out = a.out.resolve()
    if not out.is_relative_to(ROOT / 'out') or out.exists():
        raise ValueError('output must be a fresh directory under device out/')
    assert subprocess.check_output(['git', '-C', str(BASE), 'rev-parse', 'HEAD'], text=True).strip() == '693f5d9cae8a408dd18b39f3f9fdc4228c934241'
    sys.path.insert(0, str(HERE))
    import importlib.util
    def load(path, name):
        spec = importlib.util.spec_from_file_location(name, path)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m
    helper = HERE / 'build-nuwa-pmap-ret-diagnostic.py'
    assert sha(helper.read_bytes()) == '819a99e6da4796e45a25171b3f6b1e35535c7442d0e77c2ae915e28029bf0506'
    B = load(helper, 'pthread_renderer_old_helpers')
    build = json.loads(OLD.read_text())
    assert build['native']['sha256'] == NATIVE_SHA
    native_raw = Path(build['native']['path']).read_bytes()
    raw = a.prelink.read_bytes()
    assert sha(native_raw) == NATIVE_SHA and sha(raw) == INPUT_SHA and len(raw) == 55390208
    tree = Path(build['work']) / 'tree'
    reader_path = tree / 'kits/XnuPrelink/native_prelink.py'
    reader = B.load(reader_path, 'pthread_renderer_reader')
    native, image = B.Image(reader, native_raw), B.Image(reader, raw)
    entry, slot, message = B.validate_observer(image)
    assert image.word(slot) == 0x14000000
    link_map = B.A.checked_link_map(build['link_map'])
    padding = B.padding_provenance(build, native, image, link_map)
    pmap = B.discover_pmap(image)
    assert image.word(pmap['ret']) == 0xd65f03c0
    source_records = {}
    for name, expected in SOURCE_HASHES.items():
        source_records[name] = B.normal_source(BASE / 'scripts' / name, BASE)
        assert source_records[name]['raw_sha256'] == expected
    source_records['native_prelink.py'] = B.normal_source(reader_path, reader_path.parent.resolve())
    font = UEFI / 'Silicon/Silicium/SiliciumPkg/Library/FrameBufferSerialPortLib/Font.h'
    assert sha(font.read_bytes()) == FONT_SHA
    out.mkdir(parents=True)
    os.environ['UNIXNU_UEFI'] = str(UEFI)
    os.environ['PATH'] = '/usr/bin:/bin'
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    patcher = B.load(BASE / 'scripts/patch-xnu-entry-probe.py', 'pthread_renderer_patcher')
    patcher.load_segments(raw)
    names = patcher.rebase(a.prelink, raw)
    assert patcher.ENTRY_VA == image.symbols['__start'] == native.symbols['__start']
    sites = [(patcher.ENTRY_VA, 1, {'target': patcher.START_FIRST_CPU}),
             (patcher.MMU_ENABLE_VA, 2, {'target': patcher.MMU_ENABLE_VA + 4})]
    start, vector = int(padding['start'], 16), int(padding['vector'], 16)
    renderer_start = max(patcher.CAVES[stage] for _, stage, _ in sites) + patcher.CAVE_SIZE
    assert patcher.PANIC_CAVE_END == vector - 16
    assert start + 4 <= patcher.CAVES[1] < patcher.CAVES[2] < renderer_start < patcher.PANIC_CAVE_END
    work = out / 'renderer'
    work.mkdir()
    code, load_address, renderer_entry = patcher.assemble_c(BASE / 'scripts/xnu-panic-screen.c', renderer_start, work, names)
    common_entry = patcher.panic_common_entry(work, code, load_address)
    elf = B.elf_names(work / 'panic.elf')
    assert load_address == renderer_start == renderer_entry and len(code) and load_address + len(code) <= patcher.PANIC_CAVE_END
    assert code[:8] == struct.pack('<II', 0x910003e1, B.branch(renderer_entry + 4, elf['panic_screen_main']))
    candidate = bytearray(raw)
    changes = []
    def put(label, va, data, expected):
        image.span(va, len(data), 5)
        offset = image.offset(va, len(data))
        assert image.read(va, len(data)) == expected, label
        candidate[offset:offset + len(data)] = data
        changes.append(dict(label=label, va=hex(va), fileoff=hex(offset), size=len(data),
                            before_sha256=sha(expected), after_sha256=sha(data),
                            before_hex=expected.hex(), after_hex=data.hex()))
    for site, stage, target in sites:
        bar_dir = out / ('bar-' + str(stage))
        bar_dir.mkdir()
        bar = patcher.assemble(patcher.SOURCES[stage], patcher.CAVES[stage], target, bar_dir)
        assert len(bar) <= patcher.CAVE_SIZE
        put('entry-bar' if stage == 1 else 'MMU-bar', patcher.CAVES[stage], bar, bytes(len(bar)))
        expected = B.branch(site, patcher.START_FIRST_CPU) if stage == 1 else 0xd5181000
        assert native.read(site, 4) == struct.pack('<I', expected)
        put('entry-hook' if stage == 1 else 'MMU-hook', site, struct.pack('<I', B.branch(site, patcher.CAVES[stage])), struct.pack('<I', expected))
    put('renderer-blob', load_address, code, bytes(len(code)))
    for name, target in (('_panic', renderer_entry), ('_panic_trap_to_debugger', common_entry)):
        address = image.symbols[name]
        assert native.symbols[name] == address and image.read(address, 4) == native.read(address, 4)
        assert image.word(address) not in (0, 0xffffffff)
        put(name + '-hook', address, struct.pack('<I', B.branch(address, target)), image.read(address, 4))
    final = bytes(candidate)
    changed = B.check_differences(raw, final, [(int(c['fileoff'], 16), c['size']) for c in changes])
    final_image = B.Image(reader, final)
    assert B.validate_observer(final_image) == (entry, slot, message)
    assert final_image.read(pmap['initializer'], pmap['end'] - pmap['initializer']) == image.read(pmap['initializer'], pmap['end'] - pmap['initializer'])
    target = out / 'renderer-baseline.macho'
    target.write_bytes(final)
    report = dict(status='self-checked; not device approved', cwd=str(Path.cwd()), argv=sys.argv,
                  input=B.record(a.prelink.resolve()), native=build['native'], native_map=build['link_map'],
                  build_record=B.record(OLD), source_provenance=source_records, font=B.record(font),
                  padding=padding, pmap=pmap, observer=dict(entry=hex(entry), slot=hex(slot), message=hex(message)),
                  renderer=dict(load=hex(load_address), entry=hex(renderer_entry), common_entry=hex(common_entry),
                                limit=hex(patcher.PANIC_CAVE_END), size=len(code), symbols={k:hex(v) for k,v in elf.items()}, binary=B.record(work / 'panic.bin')),
                  patches=changes, changed_bytes=changed, output=B.record(target),
                  tool_versions={tool: subprocess.check_output(['/usr/bin/' + tool, '--version'], text=True).splitlines()[0] for tool in ('clang', 'ld.lld', 'llvm-objcopy')})
    (out / 'renderer-manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'output': report['output'], 'changed_bytes': changed, 'renderer': report['renderer']}, indent=2))


if __name__ == '__main__':
    main()
