"""Disassemble the actual R-011 SEC and correlate the observed handoff gap.

Reads fixed artifacts only; does not generate firmware or access a device.
Preferred RVAs in the output are not observed runtime PCs or board settings.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'out/python-tools'))
import capstone
from capstone.arm64 import ARM64_OP_REG, ARM64_OP_IMM


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--artifact', type=Path, default=ROOT / 'out/firmware-ci/39835052901/nuwa-firmware-39835052901')
    cli.add_argument('--output', type=Path, default=ROOT / 'reports/sec-handoff/actual-path.json')
    cli.add_argument('--fd-sha256', default='aca853390666e48dfd3901bdfca2a9deab0d7978a02152c4ad497564f0b8b4d6')
    args = cli.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / 'reports'):
        raise ValueError('Repo report output required')
    if output.exists():
        raise ValueError('Fresh evidence required')
    spec = importlib.util.spec_from_file_location('actual_sec_reader', ROOT / 'scripts/ci/inspect-firmware-candidate.py')
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    images = []
    original = reader.heap_descriptors
    reader.heap_descriptors = lambda data: (images.append(data), original(data))[1]
    artifact = args.artifact.resolve()
    raw = (artifact / 'build/FV/SILICIUM_UEFI.fd').read_bytes()
    if hashlib.sha256(raw).hexdigest() != args.fd_sha256:
        raise ValueError('Unexpected actual FD')
    fw = reader.Firmware()
    fw.volume(raw, 'Pinned R-011 FD')
    if len(images) != 1:
        raise ValueError('Unique actual SEC required')
    data = images[0]
    if data[:2] != b'VZ' or struct.unpack_from('<H', data, 2)[0] != 0xaa64:
        raise ValueError('Expected AARCH64 TE')
    sections, stripped = data[4], struct.unpack_from('<H', data, 6)[0]
    adjustment = stripped - 40
    base, = struct.unpack_from('<Q', data, 16)
    ranges = []
    for index in range(sections):
        at = 40 + index * 40
        size, rva, raw_size, raw_at = struct.unpack_from('<4I', data, at + 8)
        flags, = struct.unpack_from('<I', data, at + 36)
        start = raw_at - adjustment
        if raw_size and not 0 <= start <= start + raw_size <= len(data):
            raise ValueError('TE section raw bounds')
        ranges.append(dict(rva=rva, raw_at=start, raw_size=raw_size, flags=flags))
    strings = {}
    for match in re.finditer(rb'[ -~]{6,}', data):
        if any(term in match.group() for term in (b'platform-hobs status=', b'before-fv-decompress',
                                                  b'before-platform-hobs', b'before-library-constructors',
                                                  b'after-library-constructors', b'[NUWA-CTOR]')):
            section = next(s for s in ranges if s['raw_at'] <= match.start() < s['raw_at'] + s['raw_size'])
            strings[base + section['rva'] + match.start() - section['raw_at']] = match.group().decode()
    map_path = artifact / 'build/FV/Ffs/9AFFB503-E643-4141-8B90-17E8588B1D35Sec/9AFFB503-E643-4141-8B90-17E8588B1D35.map'
    map_data = map_path.read_bytes()
    symbols = {}
    for match in re.finditer(r'^([0-9a-fA-F]{8,16})\s+0+\s+0\s+(\S+)\s*$', map_data.decode(), re.M):
        symbols.setdefault(base + int(match[1], 16), []).append(match[2])
    engine = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_LITTLE_ENDIAN)
    engine.detail = True
    xrefs, calls = [], []
    for section in ranges:
        if not section['flags'] & 0x20000000:
            continue
        ins = list(engine.disasm(data[section['raw_at']:section['raw_at'] + section['raw_size']], base + section['rva']))
        for i, inst in enumerate(ins):
            if inst.mnemonic not in ('adrp', 'adr'):
                continue
            reg, val = inst.operands
            if reg.type != ARM64_OP_REG or val.type != ARM64_OP_IMM:
                continue
            targets = [val.imm] if inst.mnemonic == 'adr' else []
            for following in ins[i + 1:i + 7]:
                op = following.operands
                if following.mnemonic == 'add' and len(op) == 3 and op[1].type == ARM64_OP_REG and op[1].reg == reg.reg and op[2].type == ARM64_OP_IMM:
                    targets.append(val.imm + (op[2].imm << op[2].shift.value))
                    break
                if following.mnemonic in ('b', 'br', 'ret'):
                    break
            for target in targets:
                if target not in strings:
                    continue
                selected = ins[max(0, i - 8):i + 110]
                rows = []
                for item in selected:
                    row = dict(address=hex(item.address), bytes=item.bytes.hex(), mnemonic=item.mnemonic, operands=item.op_str)
                    if item.mnemonic in ('bl', 'b') and item.operands[0].type == ARM64_OP_IMM:
                        row['target_symbols'] = symbols.get(item.operands[0].imm, [])
                    rows.append(row)
                xrefs.append(dict(address=hex(inst.address), text=strings[target], instructions=rows))
    report_text = (artifact / 'BUILD_REPORT.txt').read_text()
    start = report_text.index('Module Name:          Sec\n')
    end = report_text.find('Module Name:', start + 20)
    sec_report = report_text[start:end]
    constructors = re.findall(r'\{([^:]+):\s+C\s*=\s*(\w+)', sec_report)
    report = dict(scope='Actual TE preferred-address static disassembly; not runtime PCs',
                  fd_sha256=hashlib.sha256(raw).hexdigest(), sec_sha256=hashlib.sha256(data).hexdigest(),
                  link_map_sha256=hashlib.sha256(map_data).hexdigest(), te_image_base=hex(base),
                  te_stripped_size=stripped, constructors=[dict(library=k, constructor=v) for k, v in constructors],
                  string_xrefs=xrefs, hob_library='EmbeddedPkg/Library/PrePiHobLib/PrePiHobLib.inf; no constructor listed',
                  limitation='Last visible status does not identify a unique failing instruction; logger state is also unverified',
                  firmware_generated=False, device_accessed=False)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(constructors=report['constructors'], xrefs=[dict(address=x['address'], text=x['text']) for x in xrefs]), indent=2))
    for x in xrefs:
        if 'platform-hobs status=' in x['text']:
            for row in x['instructions']:
                if row['mnemonic'] in ('bl', 'blr'):
                    print(row['address'], row['mnemonic'], row['operands'], row.get('target_symbols', []))


if __name__ == '__main__':
    main()
