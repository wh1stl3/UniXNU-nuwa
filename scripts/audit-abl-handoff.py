"""Read the hash-matched archived ABL in RAM; disassemble, never emit firmware.

Addresses in this report are preferred PE addresses, not observed runtime PCs.
"""
import hashlib
import argparse
import importlib.util
import json
from pathlib import Path
import re
import struct
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'out/python-tools'))
import capstone
from capstone.arm64 import ARM64_OP_IMM, ARM64_OP_REG

ABL = Path('D:/Code/PortingiOSLegacy/nuwa/backups/recovery-20261020T121245314787Z/abl_a.img')
ABL_SHA = '38a837fa917ff45e5be7cf6a421e0417015d875db503d1fb2dbc4d89080b0188'


def pe_sections(data):
    at, = struct.unpack_from('<I', data, 60)
    if data[at:at+4] != b'PE\0\0':
        raise ValueError('Bad PE header')
    machine, count = struct.unpack_from('<HH', data, at+4)
    optsize, = struct.unpack_from('<H', data, at+20)
    opt = at+24
    if machine != 0xaa64 or struct.unpack_from('<H', data, opt)[0] != 0x20b:
        raise ValueError('Not AARCH64 PE32+')
    imagebase, = struct.unpack_from('<Q', data, opt+24)
    entry, = struct.unpack_from('<I', data, opt+16)
    sections = []
    for index in range(count):
        header = opt+optsize+40*index
        name = data[header:header+8].rstrip(b'\0').decode()
        size, rva, rawsize, rawat = struct.unpack_from('<4I', data, header+8)
        flags, = struct.unpack_from('<I', data, header+36)
        if rawat+rawsize > len(data):
            raise ValueError('PE section bounds')
        sections.append(dict(name=name, rva=rva, virtual_size=size, raw_at=rawat, raw_size=rawsize, flags=flags))
    return imagebase, entry, sections


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--range', action='append', default=[], dest='ranges', help='Preferred VA start:end')
    cli.add_argument('--quiet', action='store_true')
    cli.add_argument('--output', type=Path, help='New report path under reports/; existing evidence is never overwritten')
    cli.add_argument('--focus-ranges', action='store_true', help='Keep only xrefs inside requested code ranges')
    cli.add_argument('--value', action='append', default=[], help='Preferred VA:type, type u32/u64/utf16/ascii/guid')
    cli.add_argument('--calls-to', action='append', default=[], type=lambda value: int(value,0))
    args = cli.parse_args()
    destination = ROOT / 'reports/abl-handoff/disassembly.json'
    if args.output is not None:
        destination = args.output.resolve()
        if not destination.is_relative_to((ROOT / 'reports').resolve()):
            raise ValueError('Additional evidence must stay under reports/')
        if destination.exists():
            raise ValueError('Refusing to overwrite existing evidence')
    ranges = [tuple(int(value, 0) for value in pair.split(':')) for pair in args.ranges]
    if args.focus_ranges and not ranges:
        raise ValueError('Focused evidence requires code ranges')
    raw = ABL.read_bytes()
    if hashlib.sha256(raw).hexdigest() != ABL_SHA:
        raise ValueError('Archived ABL changed')
    live = json.loads((ROOT / 'reports/abl-handoff/live-inputs.json').read_text())
    hashes = next(c for c in live['commands'] if 'sha256sum' in c['argv'][-1])
    if hashes['exit_code'] or hashes['stdout'].count(ABL_SHA) != 2:
        raise ValueError('Installed A/B ABL do not match archive')
    spec = importlib.util.spec_from_file_location('fv_reader', ROOT / 'scripts/ci/inspect-firmware-candidate.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class Reader(module.Firmware):
        def __init__(self):
            super().__init__()
            self.images = []

        def sections(self, data, owner, depth):
            at = 0
            while at+4 <= len(data):
                length, kind, hsize = int.from_bytes(data[at:at+3], 'little'), data[at+3], 4
                if length == 0xffffff:
                    length, hsize = struct.unpack_from('<I', data, at+4)[0], 8
                if not hsize <= length <= len(data)-at:
                    raise ValueError('Invalid ABL section')
                body = data[at+hsize:at+length]
                if kind == 0x10:
                    self.images.append((owner, body))
                if kind == 0x15:
                    owner['ui_name'] = body.decode('utf-16-le').rstrip('\0')
                at = (at+length+3) & ~3
            return super().sections(data, owner, depth)

    reader = Reader()
    reader.volume(raw[4096:], 'Archived ABL')
    engine = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_LITTLE_ENDIAN)
    engine.detail = True
    engine.skipdata = True
    reports = []
    for owner, data in reader.images:
        base, entry, sections = pe_sections(data)
        reads = []
        for expression in args.value:
            address_text, kind = expression.split(':')
            address = int(address_text, 0)
            section = next((s for s in sections if base+s['rva'] <= address < base+s['rva']+s['raw_size']), None)
            if not section:
                continue
            offset = section['raw_at']+address-base-section['rva']
            if kind in ('u32', 'u64'):
                count = 4 if kind == 'u32' else 8
                value = hex(int.from_bytes(data[offset:offset+count], 'little'))
            elif kind == 'guid':
                count = 16
                value = str(uuid.UUID(bytes_le=data[offset:offset+count]))
            elif kind == 'ascii':
                end = data.index(b'\0', offset, offset+512)
                count, value = end-offset+1, data[offset:end].decode('ascii')
            elif kind == 'utf16':
                end = next(n for n in range(offset,offset+512,2) if data[n:n+2] == b'\0\0')
                count, value = end-offset+2, data[offset:end].decode('utf-16-le')
            else:
                raise ValueError('Unknown PE read type')
            if offset+count > section['raw_at']+section['raw_size']:
                raise ValueError('PE data read crosses section')
            reads.append(dict(address=hex(address), type=kind, raw_hex=data[offset:offset+count].hex(), value=value))
        wanted = {}
        for match in re.finditer(rb'[\x20-\x7e]{6,}', data):
            value = match.group().decode()
            if value.startswith('/home/'):
                continue
            if any(term.lower() in value.lower() for term in (
                    'BootLinux', 'Kernel mode check', 'kernel load', 'kernel entry', 'kernel size',
                    'text_offset', 'text offset', 'Jumping', 'StartLinux', 'LoadImage', 'StartImage',
                    'boot.img', 'Failed to load/authenticate', 'Fastboot mode', 'DeviceTree Load',
                    'ExitBoot', 'shutdown', 'handoff', 'Launching', 'Entry Point', 'HLOS',
                    'ramdisk', 'dtb', 'kernel', 'offset', 'init_boot', 'InitBoot')):
                section = next((s for s in sections if s['raw_at'] <= match.start() < s['raw_at']+s['raw_size']), None)
                if section:
                    wanted[base+section['rva']+match.start()-section['raw_at']] = value
        xrefs = []
        slices = []
        callers = []
        for section in sections:
            if not section['flags'] & 0x20000000:
                continue
            instructions = list(engine.disasm(data[section['raw_at']:section['raw_at']+section['raw_size']], base+section['rva']))
            for start, end in ranges:
                selected = [dict(address=hex(i.address), bytes=i.bytes.hex(), mnemonic=i.mnemonic, operands=i.op_str)
                            for i in instructions if start <= i.address < end]
                if selected:
                    slices.append(dict(start=hex(start), end=hex(end), instructions=selected))
            for index, instruction in enumerate(instructions):
                if (instruction.mnemonic == 'bl' and instruction.operands[0].imm in args.calls_to):
                    callers.append(dict(target=hex(instruction.operands[0].imm),
                        call_address=hex(instruction.address), instructions=[dict(address=hex(i.address),
                        bytes=i.bytes.hex(),mnemonic=i.mnemonic,operands=i.op_str)
                        for i in instructions[max(0,index-18):min(len(instructions),index+24)]]))
                if instruction.mnemonic not in ('adrp', 'adr') or len(instruction.operands) != 2:
                    continue
                register, value = instruction.operands
                if register.type != ARM64_OP_REG or value.type != ARM64_OP_IMM:
                    continue
                targets = [(value.imm, index)] if instruction.mnemonic == 'adr' else []
                for offset in range(index+1, min(index+7, len(instructions))):
                    follow = instructions[offset]
                    if follow.id == 0:
                        break
                    operands = follow.operands
                    if (follow.mnemonic == 'add' and len(operands) == 3
                            and operands[1].type == ARM64_OP_REG and operands[1].reg == register.reg
                            and operands[2].type == ARM64_OP_IMM):
                        targets.append((value.imm+(operands[2].imm << operands[2].shift.value), offset))
                        break
                    if follow.mnemonic in ('b', 'ret', 'br'):
                        break
                for target, position in targets:
                    if target in wanted:
                        nearby = instructions[max(0,index-8):min(len(instructions),position+17)]
                        xrefs.append(dict(address=hex(instruction.address), string_address=hex(target),
                                          text=wanted[target], instructions=[dict(address=hex(i.address),
                                          bytes=i.bytes.hex(), mnemonic=i.mnemonic, operands=i.op_str) for i in nearby]))
        if args.focus_ranges:
            xrefs = [x for x in xrefs if any(start <= int(x['address'], 16) < end for start, end in ranges)]
            referenced = {int(x['string_address'], 16) for x in xrefs}
            wanted = {a: t for a, t in wanted.items() if a in referenced}
        reports.append(dict(guid=owner['guid'], name=owner.get('ui_name'), bytes=len(data),
                            sha256=hashlib.sha256(data).hexdigest(), preferred_base=hex(base), entry_rva=hex(entry),
                            sections=sections, selected_strings=[dict(address=hex(a),text=t) for a,t in wanted.items()],
                            string_xrefs=xrefs, requested_code_ranges=slices, selected_constants=reads,
                            requested_callers=callers))
    report = dict(scope='Static disassembly of hash-matched installed ABL; no runtime trace',
                  requested_ranges=args.ranges, focused_ranges=args.focus_ranges,
                  abl_sha256=ABL_SHA, capstone_version=capstone.__version__, volumes=reader.volumes,
                  pe_images=reports, image_generated=False, device_mode_changed=False,
                  limitation='String xrefs are local code evidence; not a proof that the branch ran')
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps([{'guid':i['guid'],'name':i['name'],'bytes':i['bytes'],
                       'strings':len(i['selected_strings']),'xrefs':len(i['string_xrefs'])} for i in reports]))
    for item in reports:
        for value in item['selected_constants']:
            print(json.dumps(value))
    if args.quiet:
        return
    for item in reports:
        if not ranges:
            for xref in item['string_xrefs']:
                print(xref['address'], xref['text'])
        for selected in item['requested_code_ranges']:
            for i in selected['instructions']:
                print(i['address'],i['mnemonic'],i['operands'])


if __name__ == '__main__':
    main()
