"""Trace the AMFI module init chain: constructors, kmod start stub, registration.

Answers one question the handoff left open: does anything in the pinned donor
actually reach the AMFI policy-registration routine, and through what path?

Method, and why it is split this way:
  * Cross references are found by decoding raw instruction words (array module),
    not by feeding whole segments to capstone -- capstone's disasm generator
    stops at the first undecodable byte, which silently truncates a 23 MB scan
    and would turn "found nothing" into a false conclusion.
  * capstone is used only on small windows, for the register tracking that raw
    decoding cannot do (adrp/add pairs feeding a store).
  * A decode-coverage figure is reported for every region; low coverage
    invalidates any negative result in that region.

Static only. No component code is invoked, no device is touched.
"""
import argparse
import hashlib
import json
import struct
import sys
from array import array
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'out/python-tools'))
import capstone  # noqa: E402
from native_prelink_inputs import inputs, tools, components, SELECTION  # noqa: E402

MASK = (1 << 64) - 1
IDENTIFIER = 'com.apple.driver.AppleMobileFileIntegrity'
EXECUTABLE_REGIONS = ('__TEXT_EXEC', '__PLK_TEXT_EXEC', '__PRELINK_TEXT')


def sign_extend(value, bits):
    if value & (1 << (bits - 1)):
        return value - (1 << bits)
    return value


def decode_words(blob):
    words = array('I')
    words.frombytes(blob)
    if sys.byteorder == 'big':
        words.byteswap()
    return words


def branch_targets(words, base):
    """Yield (pc, target, kind) for every b/bl with an immediate target."""
    for index, word in enumerate(words):
        opcode = word >> 26
        if opcode != 0x25 and opcode != 0x05:  # BL / B
            continue
        immediate = sign_extend(word & 0x3FFFFFF, 26) << 2
        pc = base + index * 4
        yield pc, (pc + immediate) & MASK, 'bl' if opcode == 0x25 else 'b'


def adrp_words(words, base):
    """Yield (pc, target_page, rd) for every adrp."""
    for index, word in enumerate(words):
        if (word & 0x9F000000) != 0x90000000:
            continue
        immlo = (word >> 29) & 0x3
        immhi = (word >> 5) & 0x7FFFF
        page = (base + index * 4) & ~0xFFF
        yield base + index * 4, (page + (sign_extend((immhi << 2) | immlo, 21) << 12)) & MASK, word & 0x1F


def main():
    cli = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    cli.add_argument('--output', type=Path, required=True, help='fresh report under reports/')
    args = cli.parse_args()
    target_path = args.output.resolve()
    if not target_path.is_relative_to(ROOT / 'reports') or target_path.exists():
        raise ValueError('fresh report under reports/ required')

    profile_path = ROOT / 'config/native-prelink-merged-analysis-profile.json'
    profile, native, donor, selection = inputs(profile_path)
    reference = json.loads(SELECTION.read_text())
    if reference['original_sha256'] != hashlib.sha256(donor).hexdigest():
        raise ValueError('Reference donor changed')

    with tools(True, profile_path) as (parser, emitter):
        parent, metadata, modules = components(parser, donor, selection)
        exports = parser.exports(donor, parser.macho(donor))
        module = modules[IDENTIFIER]
        entry = next(e for e in metadata['_PrelinkInfoDictionary'] if e['CFBundleIdentifier'] == IDENTIFIER)
        engine = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_LITTLE_ENDIAN)
        engine.detail = True

        def read(address, size):
            return donor[parser.backed_offset(parent, address, size, len(donor)):][:size]

        def section_of(address):
            for segment in module['segments']:
                for section in segment['sections']:
                    if section['va'] <= address < section['va'] + section['size']:
                        return '%s/%s' % (segment['name'], section['name'])
                if segment['va'] <= address < segment['va'] + segment['size']:
                    return segment['name']
            for segment in parent:
                if segment['va'] <= address < segment['va'] + segment['size']:
                    return 'kernel/%s' % segment['name']
            return '(unmapped)'

        def file_value(address, size=8):
            """Value at a VA, treating zero-fill (bss) as zeros."""
            try:
                return struct.unpack('<Q', read(address, size))[0]
            except ValueError:
                return 0

        # --- ground truth anchors, all derived rather than typed ---------
        registration = (reference['early_security_initializers'][IDENTIFIER] - reference['slide']) & MASK
        code = next(s for s in module['segments'] if s['name'] == '__TEXT_EXEC')
        init_section = next(s for seg in module['segments'] for s in seg['sections']
                            if s['name'] == '__mod_init_func')
        constructors = []
        for offset in range(0, init_section['size'], 8):
            slot = init_section['va'] + offset
            constructors.append({'slot': hex(slot), 'target': file_value(slot)})
        kmod = entry['_PrelinkKmodInfo']
        kmod_start = file_value(kmod + 0xB4)
        kmod_stop = file_value(kmod + 0xBC)

        # --- whole-kernel cross references -------------------------------
        regions = [s for s in parent if s['filesize'] and s['name'] in EXECUTABLE_REGIONS]
        coverage, callers_of = {}, {}
        adrp_to_page = {}
        for region in regions:
            blob = donor[parser.backed_offset(parent, region['va'], region['filesize'], len(donor)):][:region['filesize']]
            words = decode_words(blob)
            decoded = 0
            for pc, destination, kind in branch_targets(words, region['va']):
                decoded += 1
                callers_of.setdefault(destination, []).append({'from': hex(pc), 'kind': kind})
            for pc, page, rd in adrp_words(words, region['va']):
                decoded += 1
                adrp_to_page.setdefault(page, []).append(hex(pc))
            coverage[region['name']] = {
                'base': hex(region['va']), 'bytes': region['filesize'],
                'branch_and_adrp_instructions': decoded,
                'note': 'every 4-byte word is examined by bit pattern; no disasm truncation possible',
            }

        # --- function extents (heuristic, labeled as such) ---------------
        prologues = set()
        for region in regions:
            blob = donor[parser.backed_offset(parent, region['va'], region['filesize'], len(donor)):][:region['filesize']]
            words = decode_words(blob)
            for index, word in enumerate(words):
                # stp x29, x30, [sp, #imm]  -- frame pointer + link register save
                if (word & 0xFFC07FFF) in (0xA9807BFD, 0xA9007BFD):
                    prologues.add(region['va'] + index * 4)
                # sub sp, sp, #imm that is followed by an x29/x30 save within the
                # next two instructions: the frame allocation is the real entry.
                # Compilers often save x20/x19 before x29/x30, so one lookahead
                # slot is not enough.
                elif (word & 0xFFC003FF) == 0xD10003FF:
                    following = words[index + 1:index + 3]
                    if any((word2 & 0xFFC07FFF) in (0xA9807BFD, 0xA9007BFD) for word2 in following):
                        prologues.add(region['va'] + index * 4)
        starts = sorted(prologues | {int(c['target']) for c in constructors} |
                        {destination for destination, entries in callers_of.items()
                         if any(e['kind'] == 'bl' for e in entries)})
        # A frame allocation (sub sp) and the x29/x30 save that follows it are the
        # same entry. Collapse starts closer than one instruction pair so the
        # reported function does not begin at the second instruction.
        collapsed = []
        for address in starts:
            if collapsed and address - collapsed[-1] < 0x10:
                continue
            collapsed.append(address)
        starts = collapsed

        def enclosing(address):
            low, high, best = 0, len(starts) - 1, None
            while low <= high:
                middle = (low + high) // 2
                if starts[middle] <= address:
                    best = starts[middle]
                    low = middle + 1
                else:
                    high = middle - 1
            return best

        def find_stores(address):
            """Find str-family instructions whose computed address is `address`.

            Only sites with an adrp to that page are examined, so this stays a
            small capstone workload regardless of kernel size.
            """
            found = []
            for pc_hex in adrp_to_page.get(address & ~0xFFF, []):
                pc = int(pc_hex, 16)
                try:
                    window = list(engine.disasm(read(pc, 0x28), pc))
                except ValueError:
                    continue
                registers = {}
                for instruction in window:
                    ops = instruction.operands
                    if instruction.mnemonic == 'adrp':
                        registers[instruction.reg_name(ops[0].reg)] = ops[1].imm & MASK
                    elif instruction.mnemonic in ('add', 'sub') and len(ops) == 3 and ops[2].type == capstone.arm64.ARM64_OP_IMM:
                        base = registers.get(instruction.reg_name(ops[1].reg))
                        if base is not None:
                            delta = ops[2].imm if instruction.mnemonic == 'add' else -ops[2].imm
                            registers[instruction.reg_name(ops[0].reg)] = (base + delta) & MASK
                    elif instruction.mnemonic.startswith('str') and len(ops) >= 2 and ops[1].type == capstone.arm64.ARM64_OP_MEM:
                        base = registers.get(instruction.reg_name(ops[1].mem.base))
                        if base is None:
                            continue
                        if ((base + ops[1].mem.disp) & MASK) == address:
                            found.append({'at': hex(instruction.address), 'instruction': '%s %s' % (instruction.mnemonic, instruction.op_str),
                                          'function': hex(enclosing(instruction.address) or 0)})
            return found

        # --- what the kmod start stub reads ------------------------------
        stub = {'address': hex(kmod_start), 'section': section_of(kmod_start)}
        stub_window = list(engine.disasm(read(kmod_start, 0x20), kmod_start))
        stub['instructions'] = [(hex(i.address), i.mnemonic, i.op_str) for i in stub_window]
        page, displacement = None, None
        for instruction in stub_window:
            if instruction.mnemonic == 'adrp':
                page = instruction.operands[1].imm & MASK
            elif instruction.mnemonic == 'add' and page is not None and instruction.operands[2].type == capstone.arm64.ARM64_OP_IMM:
                displacement = instruction.operands[2].imm
        slot = (page + displacement) & MASK if page is not None and displacement is not None else None
        if slot is not None:
            stub.update({'global_slot': hex(slot), 'slot_section': section_of(slot),
                         'static_value': hex(file_value(slot)),
                         'slot_writers': find_stores(slot),
                         'adrp_to_slot_page': len(adrp_to_page.get(slot & ~0xFFF, []))})
        stub['callers'] = callers_of.get(kmod_start, [])
        stub['stop_stub'] = hex(kmod_stop)
        stub['stop_callers'] = callers_of.get(kmod_stop, [])

        # --- constructors -------------------------------------------------
        ctor_report = []
        for item in constructors:
            address = item['target']
            window = list(engine.disasm(read(address, 0x40), address))
            imports, calls = [], []
            for instruction in window:
                if instruction.mnemonic == 'bl' and instruction.operands[0].type == capstone.arm64.ARM64_OP_IMM:
                    destination = instruction.operands[0].imm & MASK
                    calls.append(hex(destination))
                    if code['va'] <= destination < code['va'] + code['filesize']:
                        stub_section = next((s for s in code['sections'] if s['name'] == '__stubs'), None)
                        if stub_section and stub_section['va'] <= destination < stub_section['va'] + stub_section['size']:
                            regs = {}
                            for inner in engine.disasm(read(destination, 12), destination):
                                if inner.mnemonic == 'adrp':
                                    regs[inner.reg_name(inner.operands[0].reg)] = inner.operands[1].imm & MASK
                                elif inner.mnemonic == 'ldr' and inner.operands[1].type == capstone.arm64.ARM64_OP_MEM:
                                    base = regs.get(inner.reg_name(inner.operands[1].mem.base))
                                    if base is not None:
                                        value = file_value((base + inner.operands[1].mem.disp) & MASK)
                                        imports.extend(exports.get(value, []))
            ctor_report.append({'slot': item['slot'], 'entry': hex(address),
                                'section': section_of(address), 'calls': calls,
                                'imports': sorted(set(imports)),
                                'calls_registration': hex(registration) in calls,
                                'first_instructions': [(i.mnemonic, i.op_str) for i in window[:6]]})

        # --- registration reachability ------------------------------------
        reg_callers = callers_of.get(registration, [])
        chains = []
        for caller in reg_callers:
            address = int(caller['from'], 16)
            owner = enclosing(address)
            branch = callers_of.get(owner, []) if owner else []
            chains.append({'site': caller['from'], 'kind': caller['kind'],
                           'enclosing_function': hex(owner) if owner else None,
                           'enclosing_section': section_of(owner) if owner else None,
                           'callers_of_enclosing': branch})

        def reachable(entry, start, limit=5):
            frontier, seen = [start], {start}
            for _ in range(limit):
                if entry in frontier:
                    return True
                nxt = []
                for node in frontier:
                    for caller in callers_of.get(node, []):
                        owner = enclosing(int(caller['from'], 16))
                        if owner and owner not in seen:
                            seen.add(owner)
                            nxt.append(owner)
                if not nxt:
                    return False
                frontier = nxt
            return entry in frontier

        result = {
            'scope': 'static provenance and call-graph trace of the pinned donor AMFI module; no component code invoked',
            'donor_sha256': hashlib.sha256(donor).hexdigest(),
            'native_sha256': hashlib.sha256(native).hexdigest(),
            'module': IDENTIFIER,
            'registration_candidate': hex(registration),
            'constructors': ctor_report,
            'kmod': {'start': hex(kmod_start), 'stop': hex(kmod_stop), 'stub': stub},
            'registration_callers': chains,
            'registration_reachable_from_kmod_start_stub': reachable(kmod_start, registration),
            'coverage': coverage,
            'limitations': [
                'Function extents are a prologue/BL-target heuristic, not a CFG or debug-info proof',
                'Indirect calls through vtables or function pointers are not followed',
                'The kmod start stub only forwards through a global slot; whether XNU fills that slot at load time is outside this scan',
                'A found path proves reachability in code, not that the path executes on nuwa',
            ],
            'device_accessed': False,
        }
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

        print('registration candidate:', hex(registration))
        print('kmod start stub:', hex(kmod_start), 'slot:', stub.get('global_slot'),
              'static value:', stub.get('static_value'), 'section:', stub.get('slot_section'))
        print('slot writers found:', len(stub.get('slot_writers') or []))
        print('stub callers:', len(stub['callers']))
        print('registration callers:', [c['site'] for c in chains])
        for ctor in ctor_report:
            print('  ctor %s -> %s calls_registration=%s imports=%s'
                  % (ctor['slot'], ctor['entry'], ctor['calls_registration'], ctor['imports']))


if __name__ == '__main__':
    main()
