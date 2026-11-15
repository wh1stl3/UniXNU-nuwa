#!/usr/bin/env python3
"""Generate a bounded renderer baseline, then bind two B words in a new copy only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import importlib.util

PRISTINE_SHA = '3a38b6781c17f30efe2d49c946cf06c47cea5a52cfc58b69ab491c421917b6ef'
NATIVE_SHA = '4a5bf5cc4f6920409b09fdf11eea21389b52b490e247515ab07ffdd38a7f8aa2'
MESSAGE = b'DIAG: PMAP initializer normal epilogue reached; STOP\0'


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


A = load(HERE / 'audit-nuwa-pmap-ret-layout.py', 'pmap_ret_layout')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def record(path):
    return dict(path=str(path), bytes=path.stat().st_size, sha256=digest(path.read_bytes()))


def require_frozen(native, pristine):
    assert digest(native) == NATIVE_SHA, 'wrong frozen native hash'
    assert digest(pristine) == PRISTINE_SHA, 'wrong frozen pristine prelink hash'


class Image:
    def __init__(self, reader, raw):
        self.reader, self.raw = reader, raw
        self.image = reader.macho(raw)
        self.symbols = {}
        self.symbol_records = {}
        candidates = {}
        for cmd, at, length in self.image['commands']:
            if cmd != 2:
                continue
            symoff, count, stroff, size = struct.unpack_from('<4I', raw, at + 8)
            for index in range(count):
                string, typ, section, desc, value = struct.unpack_from('<IBBHQ', raw, symoff + index * 16)
                if typ & 0xe0 or typ & 0xe != 0xe:
                    continue
                name = raw[stroff + string:raw.index(b'\0', stroff + string)].decode()
                candidates.setdefault(name, set()).add(value)
                self.symbol_records[name] = dict(value=value, section=section)
        # Local compiler labels legitimately repeat across objects. Never use
        # an ambiguous spelling as a binding input; only unique names survive.
        self.symbols = {name: next(iter(values)) for name, values in candidates.items() if len(values) == 1}

    def offset(self, va, size=1):
        return self.reader.backed_offset(self.image['segments'], va, size, len(self.raw))

    def read(self, va, size):
        at = self.offset(va, size)
        return self.raw[at:at + size]

    def word(self, va):
        return struct.unpack('<I', self.read(va, 4))[0]

    def span(self, va, size, protection):
        return A.checked_span(self.reader, self.raw, self.image, va, size, protection, protection)


def normal_source(path, repo):
    """Record raw status honestly; accept only LF-normalized same-HEAD source."""
    raw = path.read_bytes()
    relative = path.resolve().relative_to(repo.resolve()).as_posix()
    blob = subprocess.check_output(['git', '-C', str(repo), 'show', 'HEAD:' + relative])
    assert raw.replace(b'\r\n', b'\n') == blob.replace(b'\r\n', b'\n'), path
    return dict(path=str(path), raw_sha256=digest(raw), head_blob_sha256=digest(blob),
                raw_equal_head=raw == blob, lf_normalized_equal_head=True)


def validate_observer(image):
    names = image.symbols
    entry = names['_nuwa_pmap_ret_observer']
    slot = names['_nuwa_pmap_ret_observer_renderer_branch']
    message = names['_nuwa_pmap_ret_observer_message']
    assert slot == entry + 8
    image.span(entry, 12, 5)
    image.span(slot, 4, 5)
    image.span(message, len(MESSAGE), 1)
    adrp, add, branch = struct.unpack('<3I', image.read(entry, 12))
    assert adrp & 0x9f00001f == 0x90000000
    assert add & 0xffc003ff == 0x91000000
    page = (entry & ~0xfff) + (A.signed(((adrp >> 5) & 0x7ffff) << 2 | ((adrp >> 29) & 3), 21) << 12)
    assert page + ((add >> 10) & 0xfff) == message
    assert image.read(message, len(MESSAGE)) == MESSAGE and b'%' not in MESSAGE
    return entry, slot, message


def discover_pmap(image):
    section, = [s for seg in image.image['segments'] for s in seg['sections']
                if seg['name'] == '__PRELINK_INFO' and s['name'] == '__info']
    info = image.reader.unserialize_xml(image.read(section['va'], section['size']))
    module_info, = [item for item in info['_PrelinkInfoDictionary']
                    if item.get('CFBundleIdentifier') == 'com.apple.security.AppleImage4']
    assert module_info['AppleSecurityExtension'] is True
    module = image.reader.macho(image.raw, image.offset(module_info['_PrelinkExecutableLoadAddr'], 32))
    matches = []
    for seg in module['segments']:
        if not (seg['initprot'] & 2 or seg['name'] in ('__DATA_CONST', '__TEXT')):
            continue
        for at in range((seg['va'] + 7) & ~7, seg['va'] + seg['filesize'] - 0xa0 + 1, 8):
            if image.word(at) != 5:
                continue
            name = struct.unpack('<Q', image.read(at + 8, 8))[0]
            try:
                if image.read(name, 8) == b'pmap cs\0':
                    matches.append(at)
            except ValueError:
                pass
    runtime, = matches
    words = struct.unpack('<20Q', image.read(runtime, 0xa0))
    init = words[2]
    end = min(address for address in words[3:] if address > init and any(
        seg['initprot'] & 4 and seg['va'] <= address < seg['va'] + seg['filesize'] for seg in module['segments']))
    returns = [at for at in range(init, end, 4) if image.word(at) == 0xd65f03c0]
    ret, = returns
    return dict(module=module_info, runtime=runtime, initializer=init, end=end, ret=ret)


def check_differences(before, after, spans):
    assert len(before) == len(after), 'image size changed'
    allowed = bytearray(len(before))
    for start, size in spans:
        assert 0 <= start <= start + size <= len(before)
        assert not any(allowed[start:start + size]), 'overlapping allowed ranges'
        allowed[start:start + size] = b'\1' * size
    changed = [index for index, (a, b) in enumerate(zip(before, after)) if a != b]
    assert all(allowed[index] for index in changed), 'difference outside allowed ranges'
    return len(changed)


def branch(site, target):
    assert site % 4 == target % 4 == 0
    delta = target - site
    assert -(1 << 27) <= delta < (1 << 27), 'B imm26 out of range'
    return 0x14000000 | ((delta // 4) & 0x3ffffff)


def bind_words(baseline, image, ret, entry, slot, renderer):
    assert image.word(ret) == 0xd65f03c0, 'normal RET already changed'
    assert image.word(slot) == 0x14000000, 'slot already bound/modified'
    assert renderer != slot and renderer != ret and entry != ret
    image.span(ret, 4, 5)
    result = bytearray(baseline)
    patches = [(ret, 0xd65f03c0, branch(ret, entry)), (slot, 0x14000000, branch(slot, renderer))]
    for site, original, new in patches:
        assert new != original and new != 0x14000000
        at = image.offset(site, 4)
        assert struct.unpack_from('<I', result, at)[0] == original
        struct.pack_into('<I', result, at, new)
    assert all(struct.unpack_from('<I', result, image.offset(site, 4))[0] == new for site, _, new in patches)
    changed = check_differences(baseline, result, [(image.offset(site, 4), 4) for site, _, _ in patches])
    return bytes(result), patches, changed


def validate_bound(image, ret, entry, slot, renderer):
    assert renderer != slot and entry != ret
    assert image.word(ret) == branch(ret, entry), 'PMAP B is missing or wrong'
    assert image.word(slot) == branch(slot, renderer), 'renderer B is missing or wrong'
    assert image.word(slot) != 0x14000000, 'unbound renderer self-loop'


def padding_provenance(build, native, pristine, link_map):
    tree = Path(build['work']) / 'tree'
    objpath = tree / 'build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/osfmk/DEVELOPMENT/start.o'
    source = tree / '.cache/xnu-work/osfmk/arm64/start.s'
    text = source.read_text()
    # Only this proven source region supplies the container. A cache stamp is
    # not proof that arbitrary other patches/source bytes match an old review.
    region = re.search(r'LEXT\(_start\)\s*\n\s*b\s+EXT\(start_first_cpu\)(.*?)\.align\s+12,\s*0\s*\n\s*\.global\s+EXT\(LowExceptionVectorBase\)\s*\nLEXT\(LowExceptionVectorBase\)', text, re.S)
    assert region is not None
    assert not re.sub(r'/\*.*?\*/|\s+', '', region.group(1), flags=re.S)
    start = native.symbols['__start']
    vector = native.symbols['_LowExceptionVectorBase']
    assert native.symbols['_LowResetVectorEnd'] == start
    assert pristine.symbols['__start'] == start and pristine.symbols['_LowExceptionVectorBase'] == vector
    assert vector == ((start + 4 + 0xfff) & ~0xfff)
    assert native.word(start) == branch(start, native.symbols['_start_first_cpu'])
    assert pristine.word(start) == native.word(start)
    size = vector - start - 4
    span = pristine.span(start + 4, size, 5)
    native.span(start + 4, size, 5)
    assert pristine.read(start + 4, size) == native.read(start + 4, size) == bytes(size)
    assert not any(start < address < vector for address in native.symbols.values())
    obj = Image(native.reader, objpath.read_bytes())
    object_start = obj.symbols['__start']
    object_vector = obj.symbols['_LowExceptionVectorBase']
    assert object_vector - object_start == vector - start
    obj_section = next(section for seg in obj.image['segments'] for section in seg['sections']
                       if section['va'] <= object_start < section['va'] + section['size'])
    object_at = obj_section['fileoff'] + object_start - obj_section['va'] + 4
    assert obj.raw[object_at:object_at + size] == bytes(size)
    relocoff, nreloc = struct.unpack_from('<II', obj.raw, obj_section['command_offset'] + 56)
    relocations = []
    for index in range(nreloc):
        offset, bits = struct.unpack_from('<II', obj.raw, relocoff + index * 8)
        assert not offset & 0x80000000, 'unexpected scattered relocation'
        length = 1 << ((bits >> 25) & 3)
        assert not (offset < object_vector and offset + length > object_start + 4), 'padding relocation'
        relocations.append(dict(offset=offset, length=length, info=hex(bits)))
    member, = [line for line in link_map.splitlines() if line.endswith('/osfmk/DEVELOPMENT/start.o')]
    index, = re.findall(r'^\[\s*(\d+)\]', member)
    entries = []
    for symbol in ('__start', '_LowResetVectorEnd', '_LowExceptionVectorBase'):
        line, = [line for line in link_map.splitlines() if line.split() and line.split()[-1] == symbol]
        assert re.search(r'\[\s*' + index + r'\]', line)
        assert int(line.split()[0], 16) == native.symbols[symbol]
        entries.append(line)
    return dict(source=record(source), source_region=region.group(0), object=record(objpath),
                object_start=hex(object_start), object_vector=hex(object_vector),
                text_relocations=relocations, map_member=member, map_symbols=entries,
                start=hex(start), vector=hex(vector), padding=span)


def elf_names(path):
    return {parts[2]: int(parts[0], 16) for line in subprocess.check_output(
        ['/usr/bin/llvm-nm', str(path)], text=True).splitlines()
        if len(parts := line.split()) == 3}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-result', type=Path, required=True)
    parser.add_argument('--layout', type=Path, required=True, help='independently checked pristine layout')
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--uefi', type=Path, required=True, help='explicit nuwa firmware checkout for font only')
    parser.add_argument('--capstone-path', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.capstone_path))
    import capstone
    build = json.loads(args.build_result.read_text())
    layout = json.loads(args.layout.read_text())
    assert build['native']['sha256'] == NATIVE_SHA and build['pristine_prelink']['sha256'] == PRISTINE_SHA
    assert layout['images']['native']['sha256'] == NATIVE_SHA
    assert layout['images']['pristine_prelink']['sha256'] == PRISTINE_SHA
    native_raw = Path(build['native']['path']).read_bytes()
    pristine_raw = Path(build['pristine_prelink']['path']).read_bytes()
    require_frozen(native_raw, pristine_raw)
    tree = Path(build['work']) / 'tree'
    reader = load(tree / 'kits/XnuPrelink/native_prelink.py', 'pmap_ret_macho')
    native, pristine = Image(reader, native_raw), Image(reader, pristine_raw)
    entry, slot, message = validate_observer(pristine)
    assert pristine.word(slot) == 0x14000000
    link_map = A.checked_link_map(build['link_map'])
    provenance = padding_provenance(build, native, pristine, link_map)
    pmap = discover_pmap(pristine)
    ret = pmap['ret']
    assert ret == int(layout['pmap_initializer']['normal_ret'], 16)
    assert pristine.word(ret) == 0xd65f03c0
    initializer = pmap['initializer']
    initializer_end = pmap['end']
    assert initializer == int(layout['pmap_initializer']['entry'], 16)
    assert initializer_end == int(layout['pmap_initializer']['end'], 16)
    assert initializer < ret < initializer_end
    assert digest(pristine.read(initializer, initializer_end - initializer)) == layout['pmap_initializer']['bytes_sha256']
    args.out.mkdir(parents=True, exist_ok=False)
    out = args.out.resolve()
    pristine_copy = out / 'pristine.macho'
    pristine_copy.write_bytes(pristine_raw)
    report = dict(status='self-checked', argv=sys.argv, cwd=str(Path.cwd()), capstone=capstone.__version__,
                  build_result=record(args.build_result), layout=record(args.layout),
                  padding=provenance, source_provenance={}, stages={'pristine': record(pristine_copy)})
    report['pmap'] = pmap
    for name in ('patch-xnu-entry-probe.py', 'xnu-panic-screen.c'):
        report['source_provenance'][name] = normal_source(args.base / 'scripts' / name, args.base)
    report['source_provenance']['native_prelink.py'] = normal_source(
        tree / 'kits/XnuPrelink/native_prelink.py', (tree / 'kits/XnuPrelink').resolve())
    font = args.uefi / 'Silicon/Silicium/SiliciumPkg/Library/FrameBufferSerialPortLib/Font.h'
    assert font.is_file()
    report['font'] = record(font)
    os.environ['UNIXNU_UEFI'] = str(args.uefi.resolve())
    os.environ['PATH'] = '/usr/bin:/bin'
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    patcher = load(args.base / 'scripts/patch-xnu-entry-probe.py', 'pmap_ret_existing_renderer')
    patcher.load_segments(pristine_raw)
    names = patcher.rebase(pristine_copy, pristine_raw)
    assert patcher.ENTRY_VA == pristine.symbols['__start']
    # Existing no-reset recipe: only entry/MMU bars, then the renderer.
    sites = [(patcher.ENTRY_VA, 1, {'target': patcher.START_FIRST_CPU}),
             (patcher.MMU_ENABLE_VA, 2, {'target': patcher.MMU_ENABLE_VA + 4})]
    start, vector = int(provenance['start'], 16), int(provenance['vector'], 16)
    renderer_start = max(patcher.CAVES[stage] for _, stage, _ in sites) + patcher.CAVE_SIZE
    assert patcher.PANIC_CAVE_END == vector - 16
    assert start + 4 <= patcher.CAVES[1] < patcher.CAVES[2] < renderer_start < patcher.PANIC_CAVE_END
    renderer_work = out / 'renderer'
    renderer_work.mkdir()
    code, load_address, renderer_entry = patcher.assemble_c(args.base / 'scripts/xnu-panic-screen.c',
                                                          renderer_start, renderer_work, names)
    common_entry = patcher.panic_common_entry(renderer_work, code, load_address)
    elf_symbols = elf_names(renderer_work / 'panic.elf')
    assert load_address + len(code) <= patcher.PANIC_CAVE_END, 'renderer exceeds approved container; STOP'
    assert len(code) and renderer_entry == load_address
    assert code[:8] == struct.pack('<II', 0x910003e1, branch(renderer_entry + 4, elf_symbols['panic_screen_main']))
    report['renderer'] = dict(load=hex(load_address), size=len(code), entry=hex(renderer_entry),
                              common_entry=hex(common_entry), limit=hex(patcher.PANIC_CAVE_END),
                              symbols={name: hex(value) for name, value in elf_symbols.items()},
                              binary=record(renderer_work / 'panic.bin'))
    baseline = bytearray(pristine_raw)
    changes = []
    def put(label, va, raw, expected):
        at = pristine.offset(va, len(raw))
        assert pristine.read(va, len(raw)) == expected, label
        baseline[at:at + len(raw)] = raw
        changes.append(dict(label=label, va=hex(va), fileoff=hex(at), size=len(raw),
                            before_sha256=digest(expected), after_sha256=digest(raw)))
    for site, stage, target in sites:
        work = out / ('bar-' + str(stage))
        work.mkdir()
        bar = patcher.assemble(patcher.SOURCES[stage], patcher.CAVES[stage], target, work)
        assert len(bar) <= patcher.CAVE_SIZE
        pristine.span(patcher.CAVES[stage], len(bar), 5)
        put('entry-bar' if stage == 1 else 'MMU-bar', patcher.CAVES[stage], bar, bytes(len(bar)))
        expected = branch(site, patcher.START_FIRST_CPU) if stage == 1 else 0xd5181000
        put('entry-hook' if stage == 1 else 'MMU-hook', site,
            struct.pack('<I', branch(site, patcher.CAVES[stage])), struct.pack('<I', expected))
    pristine.span(load_address, len(code), 5)
    put('renderer-blob', load_address, code, bytes(len(code)))
    for name, target in (('_panic', renderer_entry), ('_panic_trap_to_debugger', common_entry)):
        address = pristine.symbols[name]
        pristine.span(address, 4, 5)
        assert pristine.word(address) not in (0, 0xffffffff)
        put(name + '-hook', address, struct.pack('<I', branch(address, target)), pristine.read(address, 4))
    baseline_raw = bytes(baseline)
    changed = check_differences(pristine_raw, baseline_raw,
                                [(int(item['fileoff'], 16), item['size']) for item in changes])
    baseline_path = out / 'renderer-baseline.macho'
    baseline_path.write_bytes(baseline_raw)
    report['stages']['renderer_baseline'] = record(baseline_path)
    report['renderer_allowed_differences'] = changes
    report['renderer_changed_bytes'] = changed
    baseline_image = Image(reader, baseline_raw)
    assert validate_observer(baseline_image) == (entry, slot, message)
    assert baseline_image.read(initializer, initializer_end - initializer) == pristine.read(initializer, initializer_end - initializer)
    final, patches, count = bind_words(baseline_raw, baseline_image, ret, entry, slot, renderer_entry)
    final_image = Image(reader, final)
    validate_observer(final_image)
    validate_bound(final_image, ret, entry, slot, renderer_entry)
    assert final_image.read(entry, 8) == pristine.read(entry, 8)
    assert final_image.read(message, len(MESSAGE)) == MESSAGE
    ret_at = pristine.offset(ret, 4)
    init_at = pristine.offset(initializer, initializer_end - initializer)
    assert final[init_at:ret_at] == pristine_raw[init_at:ret_at]
    assert final[ret_at + 4:init_at + initializer_end - initializer] == pristine_raw[ret_at + 4:init_at + initializer_end - initializer]
    header_end = 32 + struct.unpack_from('<I', pristine_raw, 20)[0]
    assert final[:header_end] == pristine_raw[:header_end]
    assert final_image.word(ret) != 0xd65f03c0 and final_image.word(slot) != 0x14000000
    final_path = out / 'kernel-pmap-ret-stop.macho'
    final_path.write_bytes(final)
    report['stages']['final'] = record(final_path)
    report['two_branch_patches'] = [dict(site=hex(site), fileoff=hex(pristine.offset(site, 4)),
                                         original=hex(original), replacement=hex(new)) for site, original, new in patches]
    report['two_branch_changed_bytes'] = count
    report['renderer_tool_versions'] = {}
    for tool in ('clang', 'ld.lld', 'llvm-objcopy'):
        report['renderer_tool_versions'][tool] = subprocess.check_output(['/usr/bin/' + tool, '--version'], text=True).splitlines()[0]
    (out / 'diagnostic.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(status='self-checked', stages=report['stages'], renderer=report['renderer'],
                         allowed=changes, patches=report['two_branch_patches']), indent=2))


if __name__ == '__main__':
    main()
