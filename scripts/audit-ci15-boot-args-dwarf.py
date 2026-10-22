"""Read CI15 Mach-O dSYM types; no source, binary or device changes.

Dependency: pyelftools 0.33 (can be installed under ignored out/python-tools).
"""
import hashlib
import inspect
import io
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'out/python-tools'))
from elftools.dwarf.dwarfinfo import DWARFInfo, DebugSectionDescriptor, DwarfConfig


def macho(path):
    data = path.read_bytes()
    magic, cpu, _, _, count, size = struct.unpack_from('<6I', data)
    assert magic == 0xfeedfacf and cpu == 0x100000c
    cursor, sections, uuid = 32, {}, None
    for _ in range(count):
        command, length = struct.unpack_from('<II', data, cursor)
        assert length >= 8 and cursor + length <= 32 + size
        if command == 0x1b:
            uuid = data[cursor+8:cursor+24].hex()
        if command == 0x19:
            nsects = struct.unpack_from('<I', data, cursor+64)[0]
            for i in range(nsects):
                pos = cursor + 72 + i*80
                name = data[pos:pos+16].split(b'\0')[0].decode()
                address, nbytes, offset = struct.unpack_from('<QQI', data, pos+32)
                if name.startswith('__debug_'):
                    assert offset+nbytes <= len(data)
                    sections[name] = DebugSectionDescriptor(io.BytesIO(data[offset:offset+nbytes]),
                                                           name, offset, nbytes, address)
        cursor += length
    assert cursor == 32 + size and uuid
    return data, uuid, sections


def main():
    paths = list((ROOT/'out/kernel-ci/39755850870').glob('**/Resources/DWARF/mach.development.bcm2837'))
    assert len(paths) == 1
    path = paths[0]
    data, uuid, sections = macho(path)
    kernel_path = path.parents[4] / 'mach.development.bcm2837.unstripped'
    kernel, kuuid, _ = macho(kernel_path)
    assert uuid == kuuid, 'dSYM/kernel UUID mismatch'
    assert hashlib.sha256(kernel).hexdigest() == 'a9e08c693fec4034f613cd554ea94e5855b25b727b4bfb4af46a4103f565bc7a'
    kwargs = {key: sections.get('__'+key[:-4]) for key in inspect.signature(DWARFInfo).parameters
              if key != 'config'}
    dwarf = DWARFInfo(config=DwarfConfig(True, 'AArch64', 8), **kwargs)
    found = []
    for cu in dwarf.iter_CUs():
        top = cu.get_top_DIE()
        unit = top.attributes.get('DW_AT_name')
        unit = unit.value.decode(errors='replace') if unit else ''
        # The pexpert initialization CU owns the consumer. Scan only these CUs,
        # recording their names; never infer the type from a source-header name.
        if not any(name in unit for name in ('pe_init', 'arm_init', 'machine_routines')):
            continue
        for die in cu.iter_DIEs():
            attr = die.attributes.get('DW_AT_name')
            if die.tag != 'DW_TAG_structure_type' or not attr or attr.value != b'boot_args':
                continue
            size = die.attributes.get('DW_AT_byte_size')
            if not size:
                continue
            members = {}
            for child in die.iter_children():
                if child.tag != 'DW_TAG_member':
                    continue
                name = child.attributes['DW_AT_name'].value.decode()
                offset = child.attributes['DW_AT_data_member_location']
                assert isinstance(offset.value, int), 'Unexpected location expression'
                item = dict(offset=offset.value)
                typed = child.get_DIE_from_attribute('DW_AT_type')
                if typed.tag == 'DW_TAG_array_type':
                    item['subranges'] = [{key: attr.value for key, attr in d.attributes.items()
                        if key in ('DW_AT_count', 'DW_AT_upper_bound')} for d in typed.iter_children()]
                members[name] = item
            found.append(dict(compilation_unit=unit, die_offset=die.offset,
                              byte_size=size.value, members=members))
    assert found, 'No complete boot_args definition found in consumer CUs'
    for record in found:
        members = record['members']
        assert record['byte_size'] == 0x2e0
        assert members['CommandLine']['offset'] == 0x6c
        assert members['bootFlags']['offset'] == 0x2d0
        assert members['memSizeActual']['offset'] == 0x2d8
        assert members['CommandLine']['subranges'] == [{'DW_AT_count': 608}]
    report = dict(scope='Compiled CI15 type evidence; runtime ABI remains unverified',
        dsym=str(path.relative_to(ROOT)).replace('\\', '/'),
        dsym_sha256=hashlib.sha256(data).hexdigest(), uuid=uuid,
        kernel_sha256=hashlib.sha256(kernel).hexdigest(),
        kernel_dsym_uuid_matches=True, definitions=found,
        compiled_type_checked=True, device_accessed=False)
    target = ROOT / 'reports/official-site-audit/ci15-boot-args-dwarf.json'
    target.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
