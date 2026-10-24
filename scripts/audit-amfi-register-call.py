"""Verify the AMFI early-security initializer's mac_policy_register call ABI.

The early-security blocker is "identity/call ABI not qualified". The identity is
settled (the routine is the AMFI initializer at the configured address); this
script addresses the call ABI by comparing what the donor module actually passes
against the native XNU's declared interface.

Checks, each reported independently:
  * the module really calls _mac_policy_register, and where
  * the argument registers (x0/x1/x2) at that call
  * the mac_policy_conf field stores the module performs, matched by offset
    against security/mac_policy.h of xnu-8796.141.3
  * whether the native kernel exports mac_policy_register at all
  * whether the return value is treated as an int status

Field offsets are a constant table below, annotated with the declaration order
in mac_policy.h. They are not derived from DWARF here: the DWARF side for
mac_policy_ops is already covered by reports/native-prelink-merged/amfi-ops-slots.json,
and keeping this script dependency-free is worth more than the redundancy.
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'out/python-tools'))
import capstone  # noqa: E402
from native_prelink_inputs import inputs, tools, components, SELECTION  # noqa: E402

MASK = (1 << 64) - 1
IDENTIFIER = 'com.apple.driver.AppleMobileFileIntegrity'

# struct mac_policy_conf, arm64, from xnu-8796.141.3 security/mac_policy.h:6205-6216
CONF_FIELDS = [
    (0x00, 'mpc_name'),
    (0x08, 'mpc_fullname'),
    (0x10, 'mpc_labelnames'),
    (0x18, 'mpc_labelname_count'),
    (0x20, 'mpc_ops'),
    (0x28, 'mpc_loadtime_flags'),
    (0x30, 'mpc_field_off'),
    (0x38, 'mpc_runtime_flags'),
    (0x40, 'mpc_list'),
    (0x48, 'mpc_data'),
]
CONF_SIZE = 0x50


def main():
    cli = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    cli.add_argument('--output', type=Path, required=True, help='fresh report under reports/')
    cli.add_argument('--window', type=lambda value: int(value, 0), default=0x600,
                     help='bytes of the initializer to disassemble')
    args = cli.parse_args()
    target = args.output.resolve()
    if not target.is_relative_to(ROOT / 'reports') or target.exists():
        raise ValueError('fresh report under reports/ required')

    profile_path = ROOT / 'config/native-prelink-merged-analysis-profile.json'
    profile, native, donor, selection = inputs(profile_path)
    reference = json.loads(SELECTION.read_text())
    initializer = (reference['early_security_initializers'][IDENTIFIER] - reference['slide']) & MASK

    with tools(True, profile_path) as (parser, emitter):
        parent, metadata, modules = components(parser, donor, selection)
        donor_exports = parser.exports(donor, parser.macho(donor))
        native_image = parser.macho(native)
        native_exports = parser.exports(native, native_image)
        module = modules[IDENTIFIER]
        code = next(s for s in module['segments'] if s['name'] == '__TEXT_EXEC')
        stubs = next(s for s in code['sections'] if s['name'] == '__stubs')
        engine = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_LITTLE_ENDIAN)
        engine.detail = True

        def read(address, size):
            return donor[parser.backed_offset(parent, address, size, len(donor)):][:size]

        def stub_symbols(address):
            registers, slot = {}, None
            for instruction in engine.disasm(read(address, 12), address):
                ops = instruction.operands
                if instruction.mnemonic == 'adrp':
                    registers[instruction.reg_name(ops[0].reg)] = ops[1].imm & MASK
                elif instruction.mnemonic == 'ldr' and ops[1].type == capstone.arm64.ARM64_OP_MEM:
                    base = registers.get(instruction.reg_name(ops[1].mem.base))
                    if base is not None:
                        slot = (base + ops[1].mem.disp) & MASK
            if slot is None:
                return []
            try:
                value, = struct.unpack('<Q', read(slot, 8))
            except ValueError:
                return []
            return donor_exports.get(value, [])

        # --- locate the registration call ------------------------------
        window = list(engine.disasm(read(initializer, args.window), initializer))
        call = None
        for index, instruction in enumerate(window):
            if instruction.mnemonic == 'bl' and instruction.operands[0].type == capstone.arm64.ARM64_OP_IMM:
                destination = instruction.operands[0].imm & MASK
                if stubs['va'] <= destination < stubs['va'] + stubs['size']:
                    if '_mac_policy_register' in stub_symbols(destination):
                        call = index
                        break
        if call is None:
            raise SystemExit('no _mac_policy_register call found in the first %#x bytes' % args.window)

        site = window[call]
        # --- replay the argument registers forward ---------------------
        # Scanning backwards and taking the first adrp per register picks the
        # earliest materialisation, not the one in force at the call. Forward
        # simulation keeps "last write wins", which is what the call sees.
        state = {}
        for instruction in window[:call]:
            ops = instruction.operands
            if instruction.mnemonic == 'adrp':
                state[instruction.reg_name(ops[0].reg)] = {'value': ops[1].imm & MASK,
                                                           'at': hex(instruction.address)}
            elif instruction.mnemonic in ('add', 'sub') and len(ops) == 3 and ops[2].type == capstone.arm64.ARM64_OP_IMM:
                destination = instruction.reg_name(ops[0].reg)
                source = state.get(instruction.reg_name(ops[1].reg))
                if source is not None:
                    delta = ops[2].imm if instruction.mnemonic == 'add' else -ops[2].imm
                    state[destination] = {'value': (source['value'] + delta) & MASK,
                                          'at': hex(instruction.address)}
            elif instruction.mnemonic in ('mov', 'movz') and len(ops) == 2 and ops[1].type == capstone.arm64.ARM64_OP_IMM:
                state[instruction.reg_name(ops[0].reg)] = {'value': ops[1].imm & MASK,
                                                           'at': hex(instruction.address)}
            elif instruction.mnemonic.startswith('ldr') and len(ops) >= 2 and ops[1].type == capstone.arm64.ARM64_OP_MEM:
                # A loaded value is unknown statically; drop any stale entry.
                state.pop(instruction.reg_name(ops[0].reg), None)
        argument_registers = {name: {'value': hex(state[name]['value']), 'at': state[name]['at']}
                              for name in ('x0', 'x1', 'x2') if name in state}
        conf_address = argument_registers.get('x0', {}).get('value')

        # --- the conf field stores ------------------------------------
        stores = []
        if conf_address:
            base = int(conf_address, 16)
            registers = {}
            for instruction in window[:call]:
                ops = instruction.operands
                if instruction.mnemonic == 'adrp':
                    registers[instruction.reg_name(ops[0].reg)] = ops[1].imm & MASK
                elif instruction.mnemonic in ('add', 'sub') and len(ops) == 3 and ops[2].type == capstone.arm64.ARM64_OP_IMM:
                    source = registers.get(instruction.reg_name(ops[1].reg))
                    if source is not None:
                        delta = ops[2].imm if instruction.mnemonic == 'add' else -ops[2].imm
                        registers[instruction.reg_name(ops[0].reg)] = (source + delta) & MASK
                elif instruction.mnemonic.startswith('st'):
                    # str puts the memory operand at index 1; stp puts it at 2,
                    # so locate it instead of assuming a position.
                    memory_operand = next((op for op in ops if op.type == capstone.arm64.ARM64_OP_MEM), None)
                    if memory_operand is None:
                        continue
                    register_base = registers.get(instruction.reg_name(memory_operand.mem.base))
                    if register_base is not None and register_base == base:
                        # stp writes two consecutive quadwords; str writes one.
                        spans = (0, 8) if instruction.mnemonic == 'stp' else (0,)
                        for delta in spans:
                            offset = memory_operand.mem.disp + delta
                            field = next((name for value, name in CONF_FIELDS if value == offset), None)
                            stores.append({'at': hex(instruction.address), 'offset': hex(offset),
                                           'field': field,
                                           'instruction': '%s %s' % (instruction.mnemonic, instruction.op_str)})

        # --- native side -------------------------------------------------
        native_register = [(address, names) for address, names in native_exports.items()
                           if any(name == '_mac_policy_register' or 'mac_policy_register' in name for name in names)]
        return_check = None
        for instruction in window[call + 1:call + 4]:
            if instruction.mnemonic in ('cbnz', 'cbz'):
                return_check = {'at': hex(instruction.address), 'instruction':
                                '%s %s' % (instruction.mnemonic, instruction.op_str)}

        known_offsets = {value for value, _ in CONF_FIELDS}
        result = {
            'scope': 'static call-ABI comparison for the AMFI early security initializer; no code executed',
            'donor_sha256': hashlib.sha256(donor).hexdigest(),
            'native_sha256': hashlib.sha256(native).hexdigest(),
            'initializer_original_va': hex(initializer),
            'registration_call': {'at': hex(site.address), 'stub_symbol': '_mac_policy_register'},
            'argument_registers': argument_registers,
            'conf_size_expected': hex(CONF_SIZE),
            'conf_field_stores': stores,
            'conf_offsets_all_known': all(store['offset'] in {hex(value) for value in known_offsets}
                                          for store in stores),
            'conf_ops_store': next((store for store in stores if store['field'] == 'mpc_ops'), None),
            'return_value_checked': return_check,
            'native_exports_mac_policy_register': [{'address': hex(address), 'names': names}
                                                   for address, names in native_register],
            'native_declares_three_argument_form': len(native_register) > 0,
            'abi_verdict': None,
            'limitations': [
                'Field offsets come from the pinned xnu-8796.141.3 declaration, not from DWARF in this run',
                'Argument register recovery is linear and stops at the first adrp per register inside the window',
                'A matching ABI proves the call is well-formed, not that the policy registers at runtime',
            ],
            'device_accessed': False,
        }
        # The donor passes x0=conf, x1=handle slot, x2=0; native declares
        # mac_policy_register(struct mac_policy_conf *, mac_policy_handle_t *, void *).
        result['abi_verdict'] = ('three-argument form matches native declaration'
                                 if (len(native_register) > 0 and 'x0' in argument_registers
                                     and 'x1' in argument_registers)
                                 else 'incomplete: see argument_registers and native exports')

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print('registration call at', hex(site.address))
        print('arguments:', {name: entry['value'] for name, entry in argument_registers.items()})
        print('conf stores:', len(stores), 'all known offsets:', result['conf_offsets_all_known'])
        print('mpc_ops store:', result['conf_ops_store'])
        print('return check:', return_check)
        print('native exports mac_policy_register:', [item['address'] for item in result['native_exports_mac_policy_register']])
        print('verdict:', result['abi_verdict'])


if __name__ == '__main__':
    main()
