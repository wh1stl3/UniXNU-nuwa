#!/usr/bin/env python3
"""Read-only observer native/prelink layout evidence. Never binds a branch."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import struct
import subprocess
import sys

sys.dont_write_bytecode = True
MESSAGE = b'DIAG: PMAP initializer normal epilogue reached; STOP\0'
PREFIX = '_nuwa_pmap_ret_observer'


def load(path):
    spec = importlib.util.spec_from_file_location('pmap_layout_reader', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def signed(value, bits):
    return value - (1 << bits) if value & (1 << (bits - 1)) else value


def checked_span(reader, raw, image, va, length, initprot, maxprot):
    """Require the entire span in one file-backed section with exact protections."""
    at = reader.backed_offset(image['segments'], va, length, len(raw))
    segment, = [s for s in image['segments'] if s['va'] <= va and va + length <= s['va'] + s['filesize']]
    section, = [s for s in segment['sections'] if s['va'] <= va and va + length <= s['va'] + s['size']]
    assert segment['initprot'] == initprot and segment['maxprot'] == maxprot
    assert at == section['fileoff'] + va - section['va']
    assert at + length <= len(raw)
    return dict(va=hex(va), fileoff=hex(at), length=length, segment=segment['name'],
                section=section['name'], initprot=segment['initprot'], maxprot=segment['maxprot'])


def checked_link_map(record):
    raw = Path(record['path']).read_bytes()
    assert len(raw) == record['bytes']
    assert hashlib.sha256(raw).hexdigest() == record['sha256'], 'link map hash mismatch'
    return raw.decode('latin-1')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-result', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    build = json.loads(args.build_result.read_text())
    assert build['stages']['kernel']['exit'] == build['stages']['prelink']['exit'] == 0
    work = Path(build['work'])
    tree = work / 'tree'
    reader_path = tree / 'kits/XnuPrelink/native_prelink.py'
    reader = load(reader_path)
    args.out.mkdir(parents=True, exist_ok=False)
    report = dict(status='self-checked', argv=sys.argv, cwd=str(Path.cwd()),
                  reader=dict(path=str(reader_path), sha256=hashlib.sha256(reader_path.read_bytes()).hexdigest()), images={})
    def inspect(path, recorded):
        raw = path.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == recorded['sha256']
        image = reader.macho(raw)
        symbols, undefined = {}, []
        for cmd, offset, length in image['commands']:
            if cmd != 2:
                continue
            symoff, count, stroff, size = struct.unpack_from('<4I', raw, offset + 8)
            for index in range(count):
                string, typ, sect, desc, value = struct.unpack_from('<IBBHQ', raw, symoff + index * 16)
                if typ & 0xe0:
                    continue
                name = raw[stroff + string:raw.index(b'\0', stroff + string)].decode()
                if typ & 0xe == 0 and name:
                    undefined.append(name)
                elif typ & 0xe == 0xe:
                    symbols[name] = value
        assert not undefined, undefined[:5]
        def offset(va, size=1):
            return reader.backed_offset(image['segments'], va, size, len(raw))
        def read(va, size):
            at = offset(va, size)
            return raw[at:at + size]
        addresses = {name: symbols[name] for name in (PREFIX, PREFIX + '_renderer_branch', PREFIX + '_message')}
        entry, slot, message = (addresses[name] for name in (PREFIX, PREFIX + '_renderer_branch', PREFIX + '_message'))
        assert slot == entry + 8
        adrp, add, branch = struct.unpack('<3I', read(entry, 12))
        assert adrp & 0x9f00001f == 0x90000000
        assert add & 0xffc003ff == 0x91000000
        assert branch == 0x14000000, 'pristine slot must remain unbound B .'
        page = (entry & ~0xfff) + (signed(((adrp >> 5) & 0x7ffff) << 2 | ((adrp >> 29) & 3), 21) << 12)
        resolved = page + ((add >> 10) & 0xfff)
        assert resolved == message
        assert read(message, len(MESSAGE)) == MESSAGE
        locations = {PREFIX: checked_span(reader, raw, image, entry, 12, 5, 5),
                     PREFIX + '_renderer_branch': checked_span(reader, raw, image, slot, 4, 5, 5),
                     PREFIX + '_message': checked_span(reader, raw, image, message, len(MESSAGE), 1, 1)}
        result = dict(path=str(path), bytes=len(raw), sha256=recorded['sha256'],
                      symbols=locations, observer_words=[hex(word) for word in (adrp, add, branch)],
                      resolved_message=hex(resolved), undefined=[],
                      segments=image['segments'])
        return result, raw, image, symbols, read, offset
    native = inspect(Path(build['native']['path']), build['native'])
    prelink = inspect(Path(build['pristine_prelink']['path']), build['pristine_prelink'])
    report['images'] = dict(native=native[0], pristine_prelink=prelink[0])
    assert native[0]['symbols'] == prelink[0]['symbols']
    assert native[0]['observer_words'] == prelink[0]['observer_words']
    # cctools maps may contain non-UTF8 bytes in unrelated object symbols.
    # Latin-1 preserves bytes; all observer ownership fields are ASCII.
    link_map = checked_link_map(build['link_map'])
    member_lines = [line for line in link_map.splitlines() if 'libNuwaPmapRetObserver.a(' in line]
    assert len(member_lines) == 1, member_lines
    index, = re.findall(r'^\[\s*(\d+)\]', member_lines[0])
    map_lines = [line for line in link_map.splitlines() if PREFIX in line]
    for name, location in native[0]['symbols'].items():
        if name == PREFIX + '_message':
            matches = [line for line in link_map.splitlines()
                       if line.endswith('literal string: ' + MESSAGE[:-1].decode('ascii'))]
            map_lines.extend(matches)
        else:
            matches = [line for line in map_lines if line.split()[-1] == name]
        assert len(matches) == 1
        assert int(matches[0].split()[0], 16) == int(location['va'], 16)
        assert re.search(r'\[\s*' + index + r'\]', matches[0])
    # The link map attributes all live member atoms to this object. No init
    # registration is inferred from a global absence of other kernel init data.
    owned_lines = [line for line in link_map.splitlines() if re.search(r'\[\s*' + index + r'\]', line)]
    assert len(owned_lines) == 4, owned_lines
    report['link_map'] = dict(member=member_lines, symbols=map_lines, owned_atoms=owned_lines)
    obj = tree / 'build/nuwa-pmap-ret-observer/pmap-ret-observer.o'
    test = load(Path(__file__).with_name('test-nuwa-pmap-ret-observer.py'))
    report['object'] = test.inspect_object(obj)
    report['component_provenance'] = {
        name: dict(path=str(path), bytes=path.stat().st_size,
                   sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        for name, path in [('object', obj), ('archive', obj.with_name('libNuwaPmapRetObserver.a')),
                           ('source', tree / 'kits/nuwa/diagnostics/pmap-ret-observer.S'),
                           ('builder', tree / 'scripts/build-nuwa-pmap-ret-observer.py')]}
    raw, image, symbols, read, offset = prelink[1:]
    info_section, = [s for seg in image['segments'] for s in seg['sections']
                     if seg['name'] == '__PRELINK_INFO' and s['name'] == '__info']
    info = reader.unserialize_xml(read(info_section['va'], info_section['size']))
    entries = info['_PrelinkInfoDictionary']
    apple, = [entry for entry in entries if entry.get('CFBundleIdentifier') == 'com.apple.security.AppleImage4']
    report['appleimage4_identity'] = apple
    module = reader.macho(raw, offset(apple['_PrelinkExecutableLoadAddr'], 32))
    report['appleimage4_segments'] = module['segments']
    runtime_candidates = []
    # Discover from this module's actual version/name/init layout; never use a
    # historical PMAP VA, initializer offset, or donor slide to guess a site.
    for seg in module['segments']:
        if seg['initprot'] & 2 or seg['name'] in ('__DATA_CONST', '__TEXT'):
            for va in range((seg['va'] + 7) & ~7, seg['va'] + seg['filesize'] - 0xa0 + 1, 8):
                if struct.unpack('<I', read(va, 4))[0] != 5:
                    continue
                name_ptr, init = struct.unpack('<QQ', read(va + 8, 16))
                try:
                    name = read(name_ptr, 64).split(b'\0')[0].decode('ascii')
                except (ValueError, UnicodeDecodeError):
                    continue
                if 'pmap' in name.lower() or name.lower() == 'darwin':
                    runtime_candidates.append(dict(va=hex(va), name=name, initializer=hex(init),
                                                   table_qwords=[hex(x) for x in struct.unpack('<20Q', read(va, 0xa0))]))
    report['runtime_candidates'] = runtime_candidates
    pmap_runtime, = [entry for entry in runtime_candidates if entry['name'] == 'pmap cs']
    runtime_set, = [section for seg in module['segments'] for section in seg['sections']
                   if section['name'] == '__img4_rt']
    runtime_pointers = struct.unpack('<' + 'Q' * (runtime_set['size'] // 8), read(runtime_set['va'], runtime_set['size']))
    assert int(pmap_runtime['va'], 16) in runtime_pointers
    report['runtime_linker_set'] = dict(section=runtime_set, pointers=[hex(value) for value in runtime_pointers])
    secondary_address = int(pmap_runtime['table_qwords'][11], 16)
    secondary_words = struct.unpack('<20Q', read(secondary_address, 0xa0))
    report['darwin_context_runtime'] = dict(va=hex(secondary_address), version=secondary_words[0],
                                     name=read(secondary_words[1], 64).split(b'\0')[0].decode('ascii'),
                                     initializer=hex(secondary_words[2]),
                                     table_qwords=[hex(value) for value in secondary_words])
    initializer = int(pmap_runtime['initializer'], 16)
    donor_raw = Path(build['kernelcache']['path']).read_bytes()
    assert hashlib.sha256(donor_raw).hexdigest() == build['kernelcache']['sha256']
    donor_image = reader.macho(donor_raw)
    def donor_read(va, size):
        at = reader.backed_offset(donor_image['segments'], va, size, len(donor_raw))
        return donor_raw[at:at + size]
    donor_info_section, = [s for seg in donor_image['segments'] for s in seg['sections']
                           if seg['name'] == '__PRELINK_INFO' and s['name'] == '__info']
    donor_entries = reader.unserialize_xml(donor_read(donor_info_section['va'], donor_info_section['size']))['_PrelinkInfoDictionary']
    donor_apple, = [entry for entry in donor_entries if entry.get('CFBundleIdentifier') == apple['CFBundleIdentifier']]
    donor_header = reader.backed_offset(donor_image['segments'], donor_apple['_PrelinkExecutableLoadAddr'], 32, len(donor_raw))
    donor_module = reader.macho(donor_raw, donor_header)
    assert [seg['name'] for seg in module['segments']] == [seg['name'] for seg in donor_module['segments']]
    # Module identity + segment correspondences, not a remembered address/slide.
    deltas = {new['va'] - old['va'] for new, old in zip(module['segments'], donor_module['segments'])
              if new['va'] and old['va'] and new['name'] != '__LINKEDIT'}
    assert len(deltas) == 1
    delta, = deltas
    # This donor module has no LC_FUNCTION_STARTS. Use the next positive
    # method address in the discovered runtime table as a bounded scan end,
    # explicitly not as a claim of compiler-provided function extent.
    assert not any(cmd == 0x26 for cmd, _, _ in donor_module['commands'])
    methods = [int(value, 16) for value in pmap_runtime['table_qwords'][3:]]
    function_end = min(address for address in methods if address > initializer
                       and any(seg['initprot'] & 4 and seg['va'] <= address < seg['va'] + seg['filesize']
                               for seg in module['segments']))
    assert read(initializer, function_end - initializer) == donor_read(initializer - delta, function_end - initializer)
    words = struct.unpack('<' + 'I' * ((function_end - initializer) // 4), read(initializer, function_end - initializer))
    returns = [initializer + i * 4 for i, word in enumerate(words) if word == 0xd65f03c0]
    assert len(returns) == 1, f'normal RET not unique: {returns}'
    reverse_symbols = {}
    for name, address in symbols.items():
        reverse_symbols.setdefault(address, []).append(name)
    calls = []
    for i, word in enumerate(words):
        if word & 0xfc000000 == 0x94000000:
            pc = initializer + i * 4
            target = pc + (signed(word & 0x3ffffff, 26) << 2)
            calls.append(dict(site=hex(pc), target=hex(target), native_names=reverse_symbols.get(target, [])))
    report['pmap_initializer'] = dict(runtime=pmap_runtime, entry=hex(initializer), end=hex(function_end),
                                    boundary_provenance='bounded runtime method window; manual CFG boundary remains required; not all-return isolation',
                                    module_segment_delta=delta, normal_ret=hex(returns[0]),
                                    ret_word=hex(struct.unpack('<I', read(returns[0], 4))[0]),
                                    ret_fileoff=hex(offset(returns[0], 4)), direct_calls=calls,
                                    bytes_sha256=hashlib.sha256(read(initializer, function_end - initializer)).hexdigest())
    report['native_img4_symbols'] = {name: hex(address) for name, address in symbols.items()
                                   if any(key in name.lower() for key in ('img4', 'image4', 'pmap_cs', 'pmap_in_ppl'))}
    def thunk(target):
        try:
            a, ldr, br = struct.unpack('<3I', read(target, 12))
        except ValueError:
            return None
        if a & 0x9f00001f != 0x90000010 or ldr & 0xffc003ff != 0xf9400210 or br != 0xd61f0200:
            return None
        page = (target & ~0xfff) + (signed(((a >> 5) & 0x7ffff) << 2 | ((a >> 29) & 3), 21) << 12)
        got = page + (((ldr >> 10) & 0xfff) * 8)
        value = struct.unpack('<Q', read(got, 8))[0]
        return dict(stub=hex(target), got=hex(got), target=hex(value), native_names=reverse_symbols.get(value, []))
    important = {'_pmap_in_ppl', '_kernel_image4_get_monitor_exports', '_img4_interface_register'}
    callsites = []
    for seg in module['segments']:
        if not seg['initprot'] & 4:
            continue
        for pc in range(seg['va'], seg['va'] + seg['filesize'] - 3, 4):
            word = struct.unpack('<I', read(pc, 4))[0]
            if word & 0xfc000000 != 0x94000000:
                continue
            target = pc + (signed(word & 0x3ffffff, 26) << 2)
            resolved = thunk(target)
            if resolved and important.intersection(resolved['native_names']):
                callsites.append(dict(site=hex(pc), **resolved))
    report['appleimage4_important_calls'] = callsites
    def address_pair(pc, register):
        a, add = struct.unpack('<II', read(pc, 8))
        assert a & 0x9f00001f == 0x90000000 | register
        assert add & 0xffc003ff == 0x91000000 | register | (register << 5)
        return (pc & ~0xfff) + (signed(((a >> 5) & 0x7ffff) << 2 | ((a >> 29) & 3), 21) << 12) + ((add >> 10) & 0xfff)
    registration, = [call for call in callsites if '_img4_interface_register' in call['native_names']]
    public_interface = address_pair(int(registration['site'], 16) - 8, 0)
    report['public_interface_registration'] = dict(call=registration, argument=hex(public_interface),
                                                  version=struct.unpack('<I', read(public_interface, 4))[0],
                                                  runtime_pmap_cs=hex(struct.unpack('<Q', read(public_interface + 0x198, 8))[0]))
    assert int(report['public_interface_registration']['runtime_pmap_cs'], 16) == int(pmap_runtime['va'], 16)
    public_site = int(registration['site'], 16)
    description_site = public_site - 12
    description_word = struct.unpack('<I', read(description_site, 4))[0]
    assert description_word & 0xfc000000 == 0x94000000
    report['pre_public_secondary_description'] = dict(
        callsite=hex(description_site),
        target=hex(description_site + (signed(description_word & 0x3ffffff, 26) << 2)),
        x0=hex(address_pair(description_site - 16, 0)),
        x1=hex(address_pair(description_site - 8, 1)),
        semantics='runtime/config description helper, not assumed to be an initializer')
    for call in calls:
        resolved = thunk(int(call['target'], 16))
        if resolved:
            call['resolved_thunk'] = resolved
    init_sections = []
    for seg in module['segments']:
        for section in seg['sections']:
            if section['name'] == '__mod_init_func':
                init_sections.append(dict(section=section, functions=[hex(x) for x in struct.unpack(
                    '<' + 'Q' * (section['size'] // 8), read(section['va'], section['size']))]))
    report['appleimage4_init_sections'] = init_sections
    prelink_record = json.loads((work / 'kernel/kernel.json').read_text())
    entrypoints = prelink_record['module_entrypoints']['com.apple.security.AppleImage4']
    report['appleimage4_entrypoints'] = {name: hex(value) for name, value in entrypoints.items()}
    windows = [('important-call-' + str(index), int(call['site'], 16) - 48, int(call['site'], 16) + 64)
               for index, call in enumerate(callsites)]
    windows += [('module-start', entrypoints['start_va'], entrypoints['stop_va'] + 4)]
    secondary_init = secondary_words[2]
    windows += [('secondary-runtime-init', secondary_init, secondary_init + 0x120),
                ('native-monitor', symbols['_xnu_image4_get_monitor_exports'], symbols['_xnu_image4_set_release_type'])]
    monitor_call, = [call for call in callsites if '_kernel_image4_get_monitor_exports' in call['native_names']]
    monitor_site = int(monitor_call['site'], 16)
    windows.append(('monitor-to-public-order', monitor_site - 0x40, public_site + 0x70))
    dispatch = []
    for pc in range(monitor_site + 4, public_site, 4):
        word = struct.unpack('<I', read(pc, 4))[0]
        if word & 0xfc000000 != 0x94000000:
            continue
        target = pc + (signed(word & 0x3ffffff, 26) << 2)
        for at in range(target, target + 0x40, 4):
            try:
                address = address_pair(at, 19)
            except (AssertionError, ValueError):
                continue
            if address == secondary_address:
                dispatch.append(dict(callsite=hex(pc), target=hex(target), default_runtime=hex(address)))
                windows.append(('runtime-initializer-dispatch', target, target + 0x1c0))
    assert len(dispatch) == 1, dispatch
    report['runtime_initializer_dispatch'] = dispatch[0]
    for name, start, stop in windows:
        result = subprocess.run(['/usr/bin/llvm-objdump', '-D', '--start-address=' + hex(start),
                                 '--stop-address=' + hex(stop), build['pristine_prelink']['path']],
                                text=True, capture_output=True, check=True)
        (args.out / (name + '.disasm.txt')).write_text(result.stdout)
    disassembly = subprocess.run(['/usr/bin/llvm-objdump', '-D', '--start-address=' + hex(initializer),
                                 '--stop-address=' + hex(function_end), build['pristine_prelink']['path']],
                                text=True, capture_output=True, check=True)
    (args.out / 'pmap-initializer.disasm.txt').write_text(disassembly.stdout)
    # Raw disassembly provides the review boundary; caller/monitor/secondary
    # semantics are not automatically promoted to success by symbol presence.
    for label, recorded in [('native', build['native']), ('pristine-prelink', build['pristine_prelink'])]:
        result = subprocess.run(['/usr/bin/llvm-objdump', '--macho', '--private-headers', recorded['path']],
                                text=True, capture_output=True, check=True)
        (args.out / (label + '-headers.txt')).write_text(result.stdout)
    (args.out / 'layout.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(status=report['status'], images={name: {key: value for key, value in result.items()
          if key in ('sha256', 'bytes', 'symbols', 'observer_words')} for name, result in report['images'].items()},
          runtime_candidates=runtime_candidates, link_map=report['link_map']), indent=2))


if __name__ == '__main__':
    main()
