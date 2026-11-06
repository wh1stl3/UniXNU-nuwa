"""Read existing nuwa UEFI into RAM and inspect kernel-variable producers.

No raw firmware, decompressed PE, diagnostic image or device write is emitted.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
import uuid
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'out/python-tools'))
import capstone
from capstone.arm64 import ARM64_OP_IMM, ARM64_OP_REG


def main():
    matches = []
    for line in subprocess.check_output(['adb', 'devices'], text=True).splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1] == 'device':
            product = subprocess.check_output(['adb', '-s', parts[0], 'shell', 'getprop', 'ro.product.device'], text=True).strip()
            if product == 'nuwa':
                matches.append(parts[0])
    if len(matches) != 1:
        raise ValueError('No unique nuwa')
    serial = matches[0]
    command = "su -c 'cat /dev/block/by-name/uefi_a'"
    metadata = subprocess.check_output(['adb', '-s', serial, 'exec-out',
        "su -c 'sha256sum /dev/block/by-name/uefi_a /dev/block/by-name/uefi_b; blockdev --getsize64 /dev/block/by-name/uefi_a'"], text=True, timeout=30)
    raw = subprocess.check_output(['adb', '-s', serial, 'exec-out', command], timeout=60)
    digest = hashlib.sha256(raw).hexdigest()
    if (len(raw) != int(metadata.splitlines()[-1]) or len(raw) > 64*1024*1024
            or metadata.count(digest) != 2):
        raise ValueError('UEFI A/B or raw-read hash mismatch')
    spec = importlib.util.spec_from_file_location('fv_reader', ROOT / 'scripts/ci/inspect-firmware-candidate.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    spec = importlib.util.spec_from_file_location('abl_reader', ROOT / 'scripts/audit-abl-handoff.py')
    abl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(abl)

    class Reader(module.Firmware):
        def __init__(self):
            super().__init__()
            self.images = []

        def sections(self, data, owner, depth):
            if depth >= 12:
                raise ValueError('Excessive UEFI nesting')
            at = 0
            while at+4 <= len(data):
                length, kind, header = int.from_bytes(data[at:at+3], 'little'), data[at+3], 4
                if length == 0xffffff:
                    length, header = struct.unpack_from('<I', data, at+4)[0], 8
                if not header <= length <= len(data)-at:
                    raise ValueError('UEFI section bounds')
                section = data[at:at+length]
                body = section[header:]
                if kind == 0x10:
                    self.images.append((owner, body))
                if kind == 0x15:
                    owner['ui_name'] = body.decode('utf-16-le').rstrip('\0')
                if kind == 2 and str(uuid.UUID(bytes_le=body[:16])) == '1d301fe9-be79-4353-91c2-d23bc959ae0c':
                    offset, attributes = struct.unpack_from('<HH', body, 16)
                    if not header+20 <= offset < length or section[offset:offset+3] != b'\x1f\x8b\x08':
                        raise ValueError('Invalid Qualcomm gzip-guided section')
                    decoder = zlib.decompressobj(31)
                    decoded = decoder.decompress(section[offset:], 64*1024*1024+1)
                    if len(decoded) > 64*1024*1024 or not decoder.eof or decoder.unused_data:
                        raise ValueError('Gzip bounds/trailer validation failed')
                    self.guided.append(dict(guid='1d301fe9-be79-4353-91c2-d23bc959ae0c', attributes=attributes,
                                            encoded_bytes=length-offset, decoded_bytes=len(decoded),
                                            decoded_sha256=hashlib.sha256(decoded).hexdigest()))
                    self.sections(decoded, owner, depth+1)
                else:
                    super().sections(section, owner, depth)
                at = (at+length+3) & ~3

    reader = Reader()
    for match in re.finditer(b'_FVH', raw):
        at = match.start()-40
        if at < 0:
            continue
        size, = struct.unpack_from('<Q', raw, at+32)
        hsize, = struct.unpack_from('<H', raw, at+48)
        if 56 <= hsize <= size <= len(raw)-at:
            reader.volume(raw[at:at+size], f'Installed UEFI@{at:#x}')
    engine = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_LITTLE_ENDIAN)
    engine.detail = True
    engine.skipdata = True
    images = []
    for owner, data in reader.images:
        wanted = {}
        base, entry, sections = abl.pe_sections(data)
        for text in ('KernelBaseAddr', 'KernelSize'):
            needle = (text+'\0').encode('utf-16-le')
            for match in re.finditer(re.escape(needle), data):
                section = next(s for s in sections if s['raw_at'] <= match.start() < s['raw_at']+s['raw_size'])
                wanted[base+section['rva']+match.start()-section['raw_at']] = text
        xrefs = []
        if wanted:
            for section in sections:
                if not section['flags'] & 0x20000000:
                    continue
                code = list(engine.disasm(data[section['raw_at']:section['raw_at']+section['raw_size']], base+section['rva']))
                for index, ins in enumerate(code):
                    if ins.mnemonic not in ('adrp', 'adr') or len(ins.operands) != 2:
                        continue
                    reg, value = ins.operands
                    if reg.type != ARM64_OP_REG or value.type != ARM64_OP_IMM:
                        continue
                    if ins.mnemonic == 'adr':
                        if value.imm in wanted:
                            xrefs.append(dict(address=hex(ins.address), variable=wanted[value.imm],
                                instructions=[dict(address=hex(i.address),bytes=i.bytes.hex(),mnemonic=i.mnemonic,operands=i.op_str)
                                for i in code[max(0,index-80):min(len(code),index+32)]]))
                        continue
                    for position in range(index+1,min(index+7,len(code))):
                        follow = code[position]
                        if follow.id == 0:
                            break
                        ops = follow.operands
                        if (follow.mnemonic == 'add' and len(ops) == 3 and ops[1].type == ARM64_OP_REG
                                and ops[1].reg == reg.reg and ops[2].type == ARM64_OP_IMM):
                            target = value.imm+(ops[2].imm << ops[2].shift.value)
                            if target in wanted:
                                xrefs.append(dict(address=hex(ins.address), variable=wanted[target],
                                    instructions=[dict(address=hex(i.address),bytes=i.bytes.hex(),mnemonic=i.mnemonic,operands=i.op_str)
                                    for i in code[max(0,index-80):min(len(code),position+32)]]))
                            break
                        if follow.mnemonic in ('b','ret','br'):
                            break
        pdbs = [m.group().decode(errors='replace') for m in re.finditer(rb'[\x20-\x7e]{1,250}\.pdb',data)]
        literals = []
        if owner.get('ui_name') == 'QcomBds' and wanted:
            for address, kind in ((0x18136,'ascii'),(0x17c8c,'ascii'),(0x1d068,'guid')):
                section = next(s for s in sections if base+s['rva'] <= address < base+s['rva']+s['raw_size'])
                offset = section['raw_at']+address-base-section['rva']
                value = (str(uuid.UUID(bytes_le=data[offset:offset+16])) if kind == 'guid' else
                         data[offset:data.index(b'\0',offset,offset+256)].decode('ascii'))
                literals.append(dict(address=hex(address),type=kind,value=value))
        images.append(dict(name=owner.get('ui_name'),guid=owner['guid'],bytes=len(data),
                           sha256=hashlib.sha256(data).hexdigest(),pdb_paths=pdbs,
                           kernel_variable_names=sorted(set(wanted.values())),string_xrefs=xrefs,
                           selected_literals=literals))
    result = dict(scope='Static analysis of installed UEFI read into RAM; not runtime variable values',
                  argv=['adb','-s','<selected-nuwa>','exec-out',command], bytes=len(raw),sha256=digest,
                  hash_query_stdout=metadata.strip(),volumes=reader.volumes,compression=reader.guided,
                  pe_images=images,raw_image_written=False,
                  gzip_guid_source='https://github.com/LongSoft/UEFITool/blob/new_engine/common/ffs.h')
    (ROOT / 'reports/abl-handoff/live-uefi-variables.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'bytes':len(raw),'sha256':digest,'pe_images':len(images),
                      'variable_modules':[{k:v for k,v in i.items() if k!='string_xrefs'} for i in images if i['kernel_variable_names']]}))


if __name__ == '__main__':
    main()
