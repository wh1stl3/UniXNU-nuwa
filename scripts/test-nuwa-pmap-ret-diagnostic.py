#!/usr/bin/env python3
"""Incremental frozen-image/renderer/two-B checks; no native build or packaging."""
import argparse
import copy
import json
from pathlib import Path
import struct
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import importlib.util


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


B = load(HERE / 'build-nuwa-pmap-ret-diagnostic.py', 'pmap_ret_diagnostic')


def elf_table(path):
    raw = path.read_bytes()
    assert raw[:6] == b'\x7fELF\x02\x01'
    shoff = struct.unpack_from('<Q', raw, 40)[0]
    entsize, count = struct.unpack_from('<HH', raw, 58)
    sections = [struct.unpack_from('<IIQQQQIIQQ', raw, shoff + index * entsize) for index in range(count)]
    result = {}
    for section in sections:
        if section[1] != 2:
            continue
        string_section = sections[section[6]]
        strings = raw[string_section[4]:string_section[4] + string_section[5]]
        for at in range(section[4], section[4] + section[5], section[9]):
            name, info, other, index, address, size = struct.unpack_from('<IBBHQQ', raw, at)
            if not name or not index:
                continue
            text = strings[name:strings.index(b'\0', name)].decode()
            result[text] = dict(address=address, size=size, type=info & 15)
    return result


def renderer_cfg(md, code, load_address, table):
    functions = {name: item for name, item in table.items() if item['type'] == 2 and item['size']}
    known = {item['address'] for item in functions.values()}
    park = functions['park']['address']
    disassembly = {}
    instructions = {}
    for name, item in functions.items():
        start, size = item['address'], item['size']
        assert load_address <= start < start + size <= load_address + len(code)
        decoded = list(md.disasm(code[start - load_address:start - load_address + size], start))
        assert sum(ins.size for ins in decoded) == size
        instructions[name] = {ins.address: ins for ins in decoded}
        disassembly[name] = ['%#x %s %s' % (ins.address, ins.mnemonic, ins.op_str) for ins in decoded]
        for ins in decoded:
            assert ins.mnemonic not in ('blr', 'br', 'smc', 'hvc'), (name, ins.mnemonic)
            if ins.mnemonic == 'bl':
                assert ins.operands[0].imm & ((1 << 64) - 1) in known, ins.op_str
    assert [ins.mnemonic for ins in instructions['park'].values()] == ['wfe', 'b']
    assert list(instructions['park'].values())[-1].operands[0].imm & ((1 << 64) - 1) == park
    terminal_edges = []
    # Helpers may RET to their BL callers. The ordinary/common/main renderer
    # entry CFGs must have no return/falloff/unknown exit, only park terminals.
    for name in ('panic_screen', 'panic_screen_common', 'panic_screen_main'):
        graph = instructions[name]
        pending, visited = [table[name]['address']], set()
        while pending:
            pc = pending.pop()
            if pc in visited:
                continue
            visited.add(pc)
            assert pc in graph, (name, hex(pc), 'falloff')
            ins = graph[pc]
            assert ins.mnemonic not in ('ret', 'eret'), name
            if ins.mnemonic in ('b', 'bl'):
                target = ins.operands[0].imm & ((1 << 64) - 1)
                if target == park:
                    terminal_edges.append(dict(function=name, site=hex(pc), target=hex(park)))
                    continue
                if ins.mnemonic == 'bl':
                    pending.append(pc + 4)
                elif target in graph:
                    pending.append(target)
                else:
                    assert name != 'panic_screen_main' and target == table['panic_screen_main']['address']
                    terminal_edges.append(dict(function=name, site=hex(pc), target='panic_screen_main'))
            elif ins.mnemonic.startswith('b.') or ins.mnemonic in ('cbz', 'cbnz', 'tbz', 'tbnz'):
                target = ins.operands[-1].imm & ((1 << 64) - 1)
                assert target in graph
                pending.extend([pc + 4, target])
            else:
                pending.append(pc + 4)
    assert any(item['function'] == 'panic_screen_main' and item['target'] == hex(park) for item in terminal_edges)
    return dict(functions=functions, terminal_edges=terminal_edges, disassembly=disassembly,
                scope='normal decoded CFG exits only; loops/fault behavior and whole-system stop not runtime verified')


def flow_windows(md, image, pmap, layout, out):
    report = {}
    def window(name, start, end):
        insns = list(md.disasm(image.read(start, end - start), start))
        assert sum(ins.size for ins in insns) == end - start
        (out / (name + '.capstone.txt')).write_text('\n'.join(
            '%#x %s %s %s' % (ins.address, ins.bytes.hex(), ins.mnemonic, ins.op_str) for ins in insns) + '\n')
        report[name] = dict(start=hex(start), end=hex(end))
        return insns
    def canonical(name):
        return 'x' + name[1:] if name.startswith('w') and name != 'wsp' else name
    def value(insns, before, reg, depth=0):
        assert depth < 40
        reg = canonical(reg)
        if reg == 'xzr':
            return 0
        for index in range(before - 1, -1, -1):
            ins = insns[index]
            if not ins.operands or ins.operands[0].type != 1:
                continue
            dest = canonical(ins.reg_name(ins.operands[0].reg))
            if dest != reg:
                continue
            if ins.mnemonic in ('adrp', 'adr'):
                return ins.operands[1].imm & ((1 << 64) - 1)
            if ins.mnemonic == 'mov':
                source = ins.operands[1]
                return (source.imm if source.type == 2 else value(insns, index, ins.reg_name(source.reg), depth + 1))
            if ins.mnemonic == 'add' and ins.operands[2].type == 2:
                if ins.reg_name(ins.operands[1].reg) == 'sp':
                    return ('stack', ins.operands[2].imm)
                base = value(insns, index, ins.reg_name(ins.operands[1].reg), depth + 1)
                if isinstance(base, int):
                    return base + ins.operands[2].imm
            if ins.mnemonic.startswith('ldr') and ins.operands[1].type == 3:
                mem = ins.operands[1].mem
                base = value(insns, index, ins.reg_name(mem.base), depth + 1)
                return ('load', base + mem.disp) if isinstance(base, int) else ('unknown-load',)
            # STR's first operand is read, not a register definition.
            if ins.mnemonic.startswith(('str', 'stur', 'stlr')) or ins.mnemonic in ('cmp', 'tst', 'cbz', 'cbnz', 'tbz', 'tbnz'):
                continue
            raise AssertionError('unhandled register definition: ' + ins.mnemonic + ' ' + ins.op_str)
        return ('entry-argument', reg)
    def memory(insns, index, operand):
        mem = operand.mem
        if insns[index].reg_name(mem.base) == 'sp':
            return ('stack', mem.disp)
        base = value(insns, index, insns[index].reg_name(mem.base))
        return base + mem.disp if isinstance(base, int) else (base, mem.disp)
    provider = image.symbols['_code_signing_configuration']
    provider_insns = window('code-signing-configuration', provider, image.symbols['_enable_developer_mode'])
    report['code_signing_symbols'] = {name: hex(image.symbols[name]) for name in ('_cs_monitor', '_cs_config', '_cs_config_set')}
    monitor = image.symbols['_cs_monitor']
    assert image.word(monitor) == 0
    zero_writers = []
    output_writers = []
    for index, ins in enumerate(provider_insns):
        if ins.mnemonic == 'str' and ins.operands[1].type == 3:
            target = memory(provider_insns, index, ins.operands[1])
            if target == monitor:
                assert ins.reg_name(ins.operands[0].reg) == 'wzr'
                zero_writers.append(ins.address)
            if target == (('entry-argument', 'x0'), 0):
                source = value(provider_insns, index, ins.reg_name(ins.operands[0].reg))
                assert source == ('load', monitor)
                output_writers.append(ins.address)
    assert len(zero_writers) == len(output_writers) == 1
    report['monitor_zero_provider'] = dict(symbol=hex(monitor), initial_value=0,
                                          zero_store=hex(zero_writers[0]), output_store=hex(output_writers[0]))
    module = image.reader.macho(image.raw, image.offset(pmap['module']['_PrelinkExecutableLoadAddr'], 32))
    calls = []
    cache = {}
    def resolve(target):
        if target not in cache:
            cache[target] = None
            try:
                a, ldr, br = struct.unpack('<III', image.read(target, 12))
            except ValueError:
                return None
            if a & 0x9f00001f == 0x90000010 and ldr & 0xffc003ff == 0xf9400210 and br == 0xd61f0200:
                page = (target & ~0xfff) + (B.A.signed(((a >> 5) & 0x7ffff) << 2 | ((a >> 29) & 3), 21) << 12)
                got = page + (((ldr >> 10) & 0xfff) * 8)
                cache[target] = struct.unpack('<Q', image.read(got, 8))[0]
        return cache[target]
    for seg in module['segments']:
        if not seg['initprot'] & 4:
            continue
        for pc in range(seg['va'], seg['va'] + seg['filesize'] - 3, 4):
            word = image.word(pc)
            if word & 0xfc000000 == 0x94000000:
                target = pc + (B.A.signed(word & 0x3ffffff, 26) << 2)
                if resolve(target) == provider:
                    calls.append((pc, target))
    assert len(calls) == 1
    callsite, stub = calls[0]
    call_insns = window('image4-configuration-call', callsite - 48, callsite + 64)
    call_index = next(index for index, ins in enumerate(call_insns) if ins.address == callsite)
    output_slot = value(call_insns, call_index, 'x0')
    assert isinstance(output_slot, int) and image.word(output_slot) == 0
    assert value(call_insns, call_index, 'x1') == 0
    report['configuration_provider_call'] = dict(site=hex(callsite), stub=hex(stub), target=hex(provider))
    decoded = list(md.disasm(image.read(pmap['initializer'], 64), pmap['initializer']))
    first_call = next(ins for ins in decoded if ins.mnemonic == 'bl')
    selector = first_call.operands[0].imm & ((1 << 64) - 1)
    selector_insns = window('pmap-configuration-selector', selector, selector + 0xb0)
    assert selector_insns[2].mnemonic == 'ret'
    config_base = value(selector_insns, 2, 'x0')
    assert isinstance(config_base, int)
    pmap_insns = window('pmap-monitor-bit1', pmap['initializer'], pmap['initializer'] + 0x100)
    bit_tests = [(index, ins) for index, ins in enumerate(pmap_insns) if ins.mnemonic == 'tbnz'
                 and ins.operands[1].imm == 1]
    bit_index, bit_test = bit_tests[0]
    assert len(bit_tests) == 1
    load_byte = pmap_insns[bit_index - 1]
    assert load_byte.mnemonic == 'ldrb' and load_byte.op_str == 'w8, [x0, #0x1a8]'
    assert config_base + load_byte.operands[1].mem.disp == output_slot
    tail = bit_test.operands[-1].imm & ((1 << 64) - 1)
    tail_insns = window('pmap-tail-log-original', tail, tail + 0x60)
    assert any(ins.mnemonic == 'br' and ins.op_str == 'x4' for ins in tail_insns)
    report['monitor_to_pmap_bit1'] = dict(configuration_base=hex(config_base), output_slot=hex(output_slot),
                                         bit_load=hex(load_byte.address), bit_test=hex(bit_test.address),
                                         bit=1, normal_provider_value=0, original_tail_log=hex(tail),
                                         scope='static software-provider dataflow, not monitor-exports NULL or runtime observation')
    window('pmap-canary-restore-ret', pmap['ret'] - 60, pmap['ret'] + 32)
    dispatcher = int(layout['runtime_initializer_dispatch']['target'], 16)
    dispatch_site = int(layout['runtime_initializer_dispatch']['callsite'], 16)
    dispatch_call, = list(md.disasm(image.read(dispatch_site, 4), dispatch_site))
    assert dispatch_call.mnemonic == 'bl' and dispatch_call.operands[0].imm & ((1 << 64) - 1) == dispatcher
    window('runtime-dispatcher', dispatcher, dispatcher + 0x180)
    public = int(layout['public_interface_registration']['call']['site'], 16)
    assert dispatch_site < public
    public_call, = list(md.disasm(image.read(public, 4), public))
    assert public_call.mnemonic == 'bl'
    assert public_call.operands[0].imm & ((1 << 64) - 1) == int(layout['public_interface_registration']['call']['stub'], 16)
    window('public-registration-order', public - 0x30, public + 8)
    report['pmap_selector'] = hex(selector)
    probe_name, = [name for name in image.symbols if 'ArmCpu5probe' in name]
    probe = image.symbols[probe_name]
    probe_end = min(address for address in image.symbols.values() if address > probe)
    probe_insns = window('armcpu-probe-smp', probe, probe_end)
    parse = image.symbols['_PE_parse_boot_argn']
    parse_calls = [(index, ins) for index, ins in enumerate(probe_insns) if ins.mnemonic == 'bl'
                   and ins.operands[0].imm & ((1 << 64) - 1) == parse]
    index, parse_call = parse_calls[0]
    assert len(parse_calls) == 1
    key = value(probe_insns, index, 'x0')
    assert image.read(key, 10) == b'sheng-smp\0'
    scratch = value(probe_insns, index, 'x1')
    assert scratch[0] == 'stack' and value(probe_insns, index, 'w2') == 4
    scratch_stores = [ins for before, ins in enumerate(probe_insns[:index]) if ins.mnemonic == 'str'
                      and ins.op_str.startswith('wzr, ') and ins.operands[1].type == 3
                      and memory(probe_insns, before, ins.operands[1]) == scratch]
    assert scratch_stores
    report['armcpu_smp'] = dict(probe=probe_name, parse_call=hex(parse_call.address), key='sheng-smp',
                               default_zero_store=hex(scratch_stores[-1].address), scratch=scratch)
    return report


def renderer_pointer_inputs(md, image, code, load_address, table):
    """Match compiled absolute loads to freshly parsed native diagnostic symbols."""
    accesses = set()
    for item in table.values():
        if item['type'] != 2 or not item['size']:
            continue
        state = {}
        start = item['address']
        for ins in md.disasm(code[start - load_address:start - load_address + item['size']], start):
            def regname(register):
                name = ins.reg_name(register)
                return 'x' + name[1:] if name.startswith('w') else name
            operands = ins.operands
            if ins.mnemonic.startswith('ldr') and len(operands) > 1 and operands[1].type == 3:
                mem = operands[1].mem
                base = state.get(regname(mem.base))
                if base is not None and not mem.index:
                    accesses.add(base + mem.disp)
            update = None
            if operands and operands[0].type == 1:
                dest = regname(operands[0].reg)
                if ins.mnemonic in ('mov', 'adr', 'adrp') and operands[1].type == 2:
                    update = (dest, operands[1].imm & ((1 << (32 if ins.reg_name(operands[0].reg).startswith('w') else 64)) - 1))
                elif ins.mnemonic == 'movk' and dest in state:
                    shift = operands[1].shift.value
                    update = (dest, (state[dest] & ~(0xffff << shift)) | (operands[1].imm << shift))
                elif ins.mnemonic == 'add' and operands[1].type == 1 and operands[2].type == 2:
                    source = state.get(regname(operands[1].reg))
                    if source is not None:
                        update = (dest, source + operands[2].imm)
            for register in ins.regs_access()[1]:
                state.pop(regname(register), None)
            if update:
                state[update[0]] = update[1]
            if ins.mnemonic == 'bl':
                for index in range(19):
                    state.pop('x' + str(index), None)
    vinfo = image.symbols.get('_boot_progress_panic_vinfo', image.symbols['_vinfo'])
    assert {vinfo + offset for offset in (0, 4, 8, 12, 16)} <= accesses
    for name in ('_vm_page_pages', '_vm_page_free_count'):
        assert image.symbols[name] in accesses, name
    return dict(vinfo=hex(vinfo), max_mem=hex(image.symbols['_max_mem']),
                page_total=hex(image.symbols['_vm_page_pages']), page_free=hex(image.symbols['_vm_page_free_count']),
                panic_text=hex(image.symbols.get('_boot_progress_panic_text', 0)),
                matched_absolute_load_addresses=[hex(value) for value in sorted(accesses)],
                note='MAX_MEM parsed but optimized away by unchanged renderer source; permissions are Mach-O, not runtime mapping proof')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--diagnostic', type=Path, required=True)
    parser.add_argument('--capstone-path', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.capstone_path))
    import capstone
    md = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)
    md.detail = True
    manifest = json.loads((args.diagnostic / 'diagnostic.json').read_text())
    build = json.loads(Path(manifest['build_result']['path']).read_text())
    reader = B.load(Path(build['work']) / 'tree/kits/XnuPrelink/native_prelink.py', 'pmap_test_reader')
    args.out.mkdir(parents=True, exist_ok=False)
    images = {}
    for stage, item in manifest['stages'].items():
        path = Path(item['path'])
        assert B.record(path) == item
        images[stage] = B.Image(reader, path.read_bytes())
    pristine, baseline, final = (images[name] for name in ('pristine', 'renderer_baseline', 'final'))
    assert B.digest(pristine.raw) == B.PRISTINE_SHA
    entry, slot, message = B.validate_observer(pristine)
    B.validate_observer(baseline)
    B.validate_observer(final)
    pmap = B.discover_pmap(pristine)
    ret = pmap['ret']
    renderer = manifest['renderer']
    renderer_entry = int(renderer['entry'], 16)
    code = (args.diagnostic / 'renderer/panic.bin').read_bytes()
    assert B.digest(code) == renderer['binary']['sha256']
    assert baseline.read(int(renderer['load'], 16), len(code)) == code
    table = elf_table(args.diagnostic / 'renderer/panic.elf')
    cfg = renderer_cfg(md, code, int(renderer['load'], 16), table)
    pointer_inputs = renderer_pointer_inputs(md, final, code, int(renderer['load'], 16), table)
    assert renderer_entry == table['panic_screen']['address'] == int(renderer['load'], 16)
    assert code[:8] == struct.pack('<II', 0x910003e1, B.branch(renderer_entry + 4, table['panic_screen_main']['address']))
    assert final.read(message, 53) == B.MESSAGE and b'%' not in B.MESSAGE
    assert final.read(entry, 8) == pristine.read(entry, 8)
    expected, patches, changed = B.bind_words(baseline.raw, baseline, ret, entry, slot, renderer_entry)
    assert expected == final.raw
    B.validate_bound(final, ret, entry, slot, renderer_entry)
    assert len(patches) == 2
    for site, original, replacement in patches:
        ins, = list(md.disasm(final.read(site, 4), site))
        target = entry if site == ret else renderer_entry
        assert ins.mnemonic == 'b' and ins.operands[0].imm & ((1 << 64) - 1) == target
        assert final.word(site) == replacement
    header_end = 32 + struct.unpack_from('<I', pristine.raw, 20)[0]
    assert final.raw[:header_end] == pristine.raw[:header_end]
    # Full bounded PMAP initializer preserved except sole RET; manual CFG
    # boundary remains a review gate, not proved by the single-RET count.
    body = bytearray(final.read(pmap['initializer'], pmap['end'] - pmap['initializer']))
    struct.pack_into('<I', body, ret - pmap['initializer'], 0xd65f03c0)
    assert bytes(body) == pristine.read(pmap['initializer'], len(body))
    epilogue = list(md.disasm(pristine.read(ret - 60, 64), ret - 60))
    assert any(ins.mnemonic == 'add' and ins.op_str == 'sp, sp, #0x190' for ins in epilogue)
    assert any(ins.mnemonic == 'b.ne' for ins in epilogue)
    assert any(ins.mnemonic == 'cmp' for ins in epilogue)
    labels = [item['label'] for item in manifest['renderer_allowed_differences']]
    assert set(labels) == {'entry-bar', 'entry-hook', 'MMU-bar', 'MMU-hook', 'renderer-blob', '_panic-hook', '_panic_trap_to_debugger-hook'}
    assert len(labels) == 7
    start = pristine.symbols['__start']
    bar1 = start + 0x78  # Existing entry-probe recipe's first slot relative to parsed entry.
    bar2 = bar1 + 0x60
    assert int(renderer['load'], 16) == bar2 + 0x60
    first_cpu = pristine.symbols['_start_first_cpu']
    mmu_matches = [pc for pc in range(first_cpu, first_cpu + 0x1000, 4)
                   if pristine.word(pc) == 0xd5181000 and pristine.word(pc + 4) == 0xd5033fdf
                   and pristine.word(pc + 0x20) == 0xd2a00600 and pristine.word(pc + 0x24) == 0xd5181040]
    mmu, = mmu_matches
    independent_changes = {
        'entry-bar': (bar1, (args.diagnostic / 'bar-1/cave.bin').read_bytes()),
        'entry-hook': (start, struct.pack('<I', B.branch(start, bar1))),
        'MMU-bar': (bar2, (args.diagnostic / 'bar-2/cave.bin').read_bytes()),
        'MMU-hook': (mmu, struct.pack('<I', B.branch(mmu, bar2))),
        'renderer-blob': (int(renderer['load'], 16), code),
        '_panic-hook': (pristine.symbols['_panic'], struct.pack('<I', B.branch(pristine.symbols['_panic'], renderer_entry))),
        '_panic_trap_to_debugger-hook': (pristine.symbols['_panic_trap_to_debugger'], struct.pack('<I', B.branch(
            pristine.symbols['_panic_trap_to_debugger'], table['panic_screen_common']['address']))),
    }
    reconstructed = bytearray(pristine.raw)
    for item in manifest['renderer_allowed_differences']:
        va, raw = independent_changes[item['label']]
        at = pristine.offset(va, len(raw))
        assert int(item['va'], 16) == va and int(item['fileoff'], 16) == at and item['size'] == len(raw)
        reconstructed[at:at + len(raw)] = raw
    assert bytes(reconstructed) == baseline.raw
    spans = [(int(item['fileoff'], 16), item['size']) for item in manifest['renderer_allowed_differences']]
    B.check_differences(pristine.raw, baseline.raw, spans)
    B.check_differences(baseline.raw, final.raw, [(baseline.offset(ret, 4), 4), (baseline.offset(slot, 4), 4)])
    negatives = []
    def reject(name, function):
        try:
            function()
        except (AssertionError, ValueError):
            negatives.append(name)
        else:
            raise AssertionError('negative accepted: ' + name)
    for name, address, size, protection in [('entry', entry, 12, 5), ('slot', slot, 4, 5), ('string', message, 53, 1)]:
        pristine.span(address, size, protection)
        for field in ('initprot', 'maxprot'):
            altered = copy.deepcopy(pristine.image)
            seg, = [s for s in altered['segments'] if s['va'] <= address < s['va'] + s['size']]
            seg[field] = 7 if protection == 5 else 5
            reject(name + '-' + field, lambda a=altered, v=address, n=size, p=protection:
                   B.A.checked_span(reader, pristine.raw, a, v, n, p, p))
        altered = copy.deepcopy(pristine.image)
        seg, = [s for s in altered['segments'] if s['va'] <= address < s['va'] + s['size']]
        section, = [s for s in seg['sections'] if s['va'] <= address < s['va'] + s['size']]
        section['size'] = address + size - section['va'] - 1
        reject(name + '-last-byte-section', lambda a=altered, v=address, n=size, p=protection:
               B.A.checked_span(reader, pristine.raw, a, v, n, p, p))
        short = pristine.raw[:pristine.offset(address, size) + size - 1]
        reject(name + '-last-byte-file', lambda r=short, v=address, n=size, p=protection:
               B.A.checked_span(reader, r, pristine.image, v, n, p, p))
    map_record = dict(build['link_map'])
    altered_map = bytearray(Path(map_record['path']).read_bytes())
    altered_map[-1] ^= 1
    bad_map = args.out / 'tampered-native-link.map'
    bad_map.write_bytes(altered_map)
    map_record['path'] = str(bad_map)
    reject('link-map-hash', lambda: B.A.checked_link_map(map_record))
    native_raw = Path(build['native']['path']).read_bytes()
    B.require_frozen(native_raw, pristine.raw)
    B.validate_observer(B.Image(reader, native_raw))
    reject('wrong-frozen-input-hash', lambda: B.require_frozen(native_raw, baseline.raw))
    reject('already-patched', lambda: B.bind_words(final.raw, final, ret, entry, slot, renderer_entry))
    altered = bytearray(baseline.raw)
    struct.pack_into('<I', altered, baseline.offset(slot, 4), B.branch(slot, entry))
    altered_image = B.Image(reader, bytes(altered))
    reject('already-bound-slot', lambda: B.bind_words(altered, altered_image, ret, entry, slot, renderer_entry))
    reject('renderer-self-loop', lambda: B.bind_words(baseline.raw, baseline, ret, entry, slot, slot))
    altered = bytearray(final.raw)
    struct.pack_into('<I', altered, final.offset(slot, 4), 0x14000000)
    unbound = B.Image(reader, bytes(altered))
    reject('unbound-final-slot', lambda: B.validate_bound(unbound, ret, entry, slot, renderer_entry))
    reject('unaligned-B', lambda: B.branch(ret, entry + 1))
    reject('out-of-range-B', lambda: B.branch(ret, ret + (1 << 27)))
    altered = bytearray(final.raw)
    altered[pristine.offset(pmap['initializer'], 4)] ^= 1
    reject('initializer-extra-byte', lambda: B.check_differences(baseline.raw, altered,
           [(baseline.offset(ret, 4), 4), (baseline.offset(slot, 4), 4)]))
    altered = bytearray(baseline.raw)
    altered[0] ^= 1
    reject('baseline-extra-byte', lambda: B.check_differences(pristine.raw, altered, spans))
    layout = json.loads(Path(manifest['layout']['path']).read_text())
    flow = flow_windows(md, final, pmap, layout, args.out)
    tree = Path(build['work']) / 'tree'
    armcpu = tree / 'drivers/ArmCpu'
    armcpu_source = (armcpu / 'ArmCpu.cpp').resolve()
    flow['armcpu_source'] = B.normal_source(armcpu_source, armcpu.resolve())
    xnu_work = tree / '.cache/xnu-work'
    flow['code_signing_source'] = B.normal_source(xnu_work / 'bsd/kern/kern_codesigning.c', xnu_work)
    assert 'unsigned smp = 0;' in armcpu_source.read_text()
    import tomllib
    board_path = HERE.parent / 'board.toml'
    board = tomllib.loads(board_path.read_text())
    boot_args = board['payload']['kernel_args']
    assert not any(arg.split('=', 1)[0] == 'sheng-smp' for arg in boot_args)
    flow['configured_boot_arguments'] = dict(board=B.record(board_path), args=boot_args,
                                            scope='configured inputs only; no device/runtime/CLI override claim')
    report = dict(status='self-checked', argv=sys.argv, cwd=str(Path.cwd()), capstone=capstone.__version__, flow=flow,
                  stages=manifest['stages'], negative_rejections=negatives,
                  renderer_cfg=cfg, renderer_pointer_inputs=pointer_inputs,
                  two_B_regions_bytes=8, two_B_actual_changed_bytes=changed)
    (args.out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    (args.out / 'renderer.disasm.txt').write_text('\n'.join('\n'.join([name + ':', *lines])
        for name, lines in cfg['disassembly'].items()) + '\n')
    print(json.dumps(dict(status=report['status'], negative_rejections=negatives,
                         terminal_edges=cfg['terminal_edges'], two_B_actual_changed_bytes=changed), indent=2))


if __name__ == '__main__':
    main()
