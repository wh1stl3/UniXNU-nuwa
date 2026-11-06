"""Map the AMFI registration block's constant stores to actual native DWARF slots.

This proves byte offsets and executable backing, not callback signature compatibility.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
from native_prelink_inputs import ROOT, inputs, tools, components

sys.path.insert(0, str(ROOT / 'out/python-tools'))
import capstone

ARTIFACT = ROOT / 'out/upstream-kernel-40015845083-final/nuwa-8796-merged-40015845083/nuwa-8796-source'
DWARF = ARTIFACT / 'build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/mach.development.bcm2837.dSYM/Contents/Resources/DWARF/mach.development.bcm2837'


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--output', required=True, type=Path)
    args = cli.parse_args()
    target = args.output.resolve()
    if not target.is_relative_to(ROOT / 'reports') or target.exists():
        raise ValueError('Fresh report under reports/ required')
    profile_path = ROOT / 'config/native-prelink-merged-analysis-profile.json'
    _, native, donor, selection = inputs(profile_path)
    command = ['wsl', '-d', 'Ubuntu-22.04', '--', 'llvm-dwarfdump',
               '--debug-info=0x01015cf8', '--show-children',
               '/mnt/d/' + DWARF.as_posix().split(':/', 1)[1]]
    dump = subprocess.check_output(command).decode('utf-8')
    if 'DW_AT_name\t("mac_policy_ops")' not in dump:
        raise ValueError('Wrong DWARF type')
    size = int(re.search(r'DW_AT_byte_size\s+\((0x[0-9a-f]+)\)', dump)[1], 16)
    fields = {}
    for block in re.split(r'0x[0-9a-f]+:\s+DW_TAG_member', dump)[1:]:
        name = re.search(r'DW_AT_name\s+\("([^"]+)"\)', block)[1]
        offset = int(re.search(r'DW_AT_data_member_location\s+\((0x[0-9a-f]+)\)', block)[1], 16)
        kind = re.search(r'DW_AT_type\s+\(0x[0-9a-f]+ "([^"]+)"\)', block)[1]
        if offset in fields:
            raise ValueError('Duplicate DWARF field offset')
        fields[offset] = dict(name=name, type=kind)
    if sorted(fields) != list(range(0, size, 8)):
        raise ValueError('Unexpected native policy slot geometry')
    base, conf = 0xfffffff006cb6e28, 0xfffffff006cb78a0
    start, end = 0xfffffff005703e4c, 0xfffffff005703f5c
    engine = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_LITTLE_ENDIAN)
    engine.detail = True
    mask = (1 << 64) - 1
    stores = []
    with tools(True, profile_path) as (parser, _):
        parent, _, modules = components(parser, donor, selection)
        module = modules['com.apple.driver.AppleMobileFileIntegrity']

        def read(va, length):
            offset = parser.backed_offset(parent, va, length, len(donor))
            return donor[offset:offset + length]

        def executable(va):
            return any(s['initprot'] == 5 and s['va'] <= va < s['va'] + s['filesize']
                       for s in module['segments'])

        registers = {}
        decoded = list(engine.disasm(read(start, end - start), start))
        if len(decoded) * 4 != end - start:
            raise ValueError('Incomplete instruction decoding')
        for ins in decoded:
            op = ins.operands
            reg = lambda operand: ins.reg_name(operand.reg)
            if ins.mnemonic == 'adrp':
                registers[reg(op[0])] = op[1].imm & mask
            elif ins.mnemonic == 'add' and op[2].type == capstone.arm64.ARM64_OP_IMM:
                registers[reg(op[0])] = (registers[reg(op[1])] + op[2].imm) & mask
            elif ins.mnemonic in ('str', 'stp'):
                count = 2 if ins.mnemonic == 'stp' else 1
                mem = op[count].mem
                address = registers[ins.reg_name(mem.base)] + mem.disp
                for index in range(count):
                    slot = address + 8 * index - base
                    value = registers[reg(op[index])]
                    if slot not in fields or not executable(value):
                        raise ValueError('Store outside native slot table or original AMFI executable')
                    stores.append(dict(instruction=hex(ins.address), offset=slot,
                                       **fields[slot], original_target=hex(value)))
            else:
                raise ValueError('Nonconstant or control-flow instruction in selected store block')
        if len({s['offset'] for s in stores}) != len(stores):
            raise ValueError('Unexpected overwritten slot in registration block')
        original = read(base, size)
        result = dict(scope='Straight-line constant-store and actual native DWARF slot correspondence only',
            donor_sha256=hashlib.sha256(donor).hexdigest(),
            native_sha256=hashlib.sha256(native).hexdigest(),
            native_dwarf_sha256=hashlib.sha256(DWARF.read_bytes()).hexdigest(),
            command=command, dwarf_dump_sha256=hashlib.sha256(dump.encode()).hexdigest(),
            native_ops_size=size, native_ops_slots=len(fields),
            original_ops_address=hex(base), next_conf_address=hex(conf),
            gap_to_conf=conf-base, gap_matches_native_ops_size=(conf-base == size),
            original_nonzero_slots=[i for i in range(0, size, 8) if struct.unpack_from('<Q', original, i)[0]],
            analyzed_block=dict(start=hex(start), end=hex(end), instructions=len(decoded),
                                sha256=hashlib.sha256(read(start, end-start)).hexdigest()),
            constant_stores=stores, all_store_offsets_are_native_slots=True,
            all_stored_targets_in_original_amfi_executable=True,
            limitations=['Native slot names do not prove donor intended semantics or callback parameter layouts',
                         'Not a complete constructor/start/registration CFG or all callback body audit',
                         'No initializer adopted, invoked, or code/data rewritten'],
            device_accessed=False)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(native_slots=len(fields), stores=len(stores), size=size,
                         original_nonzero_slots=len(result['original_nonzero_slots']))))


if __name__ == '__main__':
    main()
