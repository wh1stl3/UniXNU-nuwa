"""Bounded static donor initializer investigation; never invoke component code."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
from native_prelink_inputs import ROOT, inputs, tools, components, SELECTION

sys.path.insert(0, str(ROOT / 'out/python-tools'))
import capstone


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    target = args.output.resolve()
    if not target.is_relative_to(ROOT / 'reports') or target.exists():
        raise ValueError('Fresh report under reports/ required')
    profile_path = ROOT / 'config/native-prelink-merged-analysis-profile.json'
    profile, native, donor, selection = inputs(profile_path)
    reference = json.loads(SELECTION.read_text())
    if reference['original_sha256'] != hashlib.sha256(donor).hexdigest():
        raise ValueError('Reference donor changed')
    identifier = 'com.apple.driver.AppleMobileFileIntegrity'
    reference_address = reference['early_security_initializers'][identifier]
    original_address = reference_address - reference['slide']
    mask = (1 << 64) - 1
    engine = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_LITTLE_ENDIAN)
    engine.detail = True
    with tools(True, profile_path) as (parser, emitter):
        parent, metadata, modules = components(parser, donor, selection)
        module = modules[identifier]
        entry = next(e for e in metadata['_PrelinkInfoDictionary'] if e['CFBundleIdentifier'] == identifier)

        def read(address, size):
            offset = parser.backed_offset(parent, address, size, len(donor))
            return donor[offset:offset + size]

        original_exports = parser.exports(donor, parser.macho(donor))
        code = next(s for s in module['segments'] if s['name'] == '__TEXT_EXEC')
        if not code['va'] <= original_address < code['va'] + code['filesize']:
            raise ValueError('Inverse-slide candidate not backed by original AMFI executable code')

        def imported_stub(address):
            regs, slot = {}, None
            for instruction in engine.disasm(read(address, 12), address):
                operands = instruction.operands
                if instruction.mnemonic == 'adrp':
                    regs[instruction.reg_name(operands[0].reg)] = operands[1].imm & mask
                elif instruction.mnemonic == 'ldr' and operands[1].type == capstone.arm64.ARM64_OP_MEM:
                    memory = operands[1].mem
                    base = regs.get(instruction.reg_name(memory.base))
                    if base is not None:
                        slot = (base + memory.disp) & mask
            if slot is None:
                return None
            value, = struct.unpack('<Q', read(slot, 8))
            return dict(slot=hex(slot), original_pointer=hex(value), symbols=original_exports.get(value, []))

        incoming = []
        decoded = list(engine.disasm(read(code['va'], code['filesize']), code['va']))
        for instruction in decoded:
            if instruction.mnemonic in ('bl', 'b') and instruction.operands[0].type == capstone.arm64.ARM64_OP_IMM:
                if instruction.operands[0].imm & mask == original_address:
                    incoming.append(dict(address=hex(instruction.address), mnemonic=instruction.mnemonic))
        calls = []
        # A bounded exploratory slice, not a claimed complete function extent/CFG.
        instructions = []
        for instruction in engine.disasm(read(original_address, 0x400), original_address):
            instructions.append(dict(address=hex(instruction.address), mnemonic=instruction.mnemonic,
                                     operands=instruction.op_str))
            if instruction.mnemonic in ('bl', 'b') and instruction.operands[0].type == capstone.arm64.ARM64_OP_IMM:
                address = instruction.operands[0].imm & mask
                stub_section = next(s for s in code['sections'] if s['name'] == '__stubs')
                stub = imported_stub(address) if stub_section['va'] <= address < stub_section['va'] + stub_section['size'] else None
                calls.append(dict(address=hex(instruction.address), target=hex(address), imported_stub=stub))
        constructors = []
        for segment in module['segments']:
            for section in segment['sections']:
                if section['name'] == '__mod_init_func':
                    for offset in range(0, section['size'], 8):
                        slot = section['va'] + offset
                        value, = struct.unpack('<Q', read(slot, 8))
                        constructors.append(dict(slot=hex(slot), original_target=hex(value)))
        kmod = entry['_PrelinkKmodInfo']
        kmod_start, = struct.unpack('<Q', read(kmod + 180, 8))
        kmod_stop, = struct.unpack('<Q', read(kmod + 188, 8))
        result = dict(scope='Static original donor provenance and bounded disassembly only; no initializer adopted or called',
                      donor_sha256=hashlib.sha256(donor).hexdigest(), native_sha256=hashlib.sha256(native).hexdigest(),
                      reference_sha256=hashlib.sha256(SELECTION.read_bytes()).hexdigest(),
                      module=identifier, apple_security_extension=entry.get('AppleSecurityExtension') is True,
                      reference_output_address=hex(reference_address), reference_slide=reference['slide'],
                      inverse_slide_original_candidate=hex(original_address),
                      original_module_executable=dict(start=hex(code['va']), bytes=code['filesize']),
                      candidate_slice_sha256=hashlib.sha256(read(original_address, 0x400)).hexdigest(),
                      original_mod_init_func=constructors, original_kmod_start=hex(kmod_start), original_kmod_stop=hex(kmod_stop),
                      direct_incoming_branches=incoming, calls_in_bounded_slice=calls, instructions=instructions,
                      address_normalization='Capstone signed immediates normalized modulo2^64 before comparison',
                      limitations=['Candidate sourced from a historical analytical report; inverse-slide provenance alone is not initializer qualification',
                                   '0x400-byte slice is not a complete function/CFG or calling-convention proof',
                                   'No indirect incoming-call or policy-registration completeness proof',
                                   'No claim that a constructor/start wrapper can be skipped or a policy initializer may be called twice'],
                      early_initializer_mapping_adopted=False, device_accessed=False)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(original_candidate=hex(original_address), constructors=constructors,
                         incoming=incoming, imports=[c['imported_stub']['symbols'] for c in calls if c['imported_stub']])))


if __name__ == '__main__':
    main()
