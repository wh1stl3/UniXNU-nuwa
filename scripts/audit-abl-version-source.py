"""Locate archived, hash-pinned ABL context header-version stores; read only."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
from native_prelink_inputs import ROOT

sys.path.insert(0, str(ROOT / 'out/python-tools'))
import capstone


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / 'reports') or output.exists():
        raise ValueError('Fresh reports path required')
    spec = importlib.util.spec_from_file_location('version_fv', ROOT / 'scripts/ci/inspect-firmware-candidate.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class Reader(module.Firmware):
        def __init__(self):
            super().__init__()
            self.images = []

        def sections(self, data, owner, depth):
            at = 0
            while at + 4 <= len(data):
                length, kind = int.from_bytes(data[at:at+3], 'little'), data[at+3]
                hsize = 4
                if length == 0xffffff:
                    length, hsize = struct.unpack_from('<I', data, at+4)[0], 8
                if not hsize <= length <= len(data)-at:
                    raise ValueError('ABL section bounds')
                if kind == 0x10:
                    self.images.append(data[at+hsize:at+length])
                at = (at+length+3) & ~3
            return super().sections(data, owner, depth)

    raw = Path('D:/Code/PortingiOS/nuwa/backups/recovery-20261020T121245314787Z/abl_a.img').read_bytes()
    if hashlib.sha256(raw).hexdigest() != '38a837fa917ff45e5be7cf6a421e0417015d875db503d1fb2dbc4d89080b0188':
        raise ValueError('Archived ABL changed')
    reader = Reader()
    reader.volume(raw[4096:], 'Pinned ABL')
    pe, = [image for image in reader.images if hashlib.sha256(image).hexdigest() ==
           'b489faff3f66a415af69b73fe23a59fb9469da0b70aeb4a1792201e22b5bb116']
    # Fixed PE sections independently bounded by the existing ABL audit.
    code = pe[4096:4096+937984]
    engine = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_LITTLE_ENDIAN)
    sites = []
    for address, size, mnemonic, operands in engine.disasm_lite(code, 4096):
        if (mnemonic == 'str' and operands.startswith('w') and '#0x458]' in operands
                and ', [sp,' not in operands):
            window = [dict(address=hex(a), bytes=pe[a:a+s].hex(), mnemonic=m, operands=o)
                      for a, s, m, o in engine.disasm_lite(pe[address-64:address+20], address-64)]
            sites.append(dict(address=hex(address), instructions=window))
    if not sites:
        raise ValueError('No direct context version stores found')
    result = dict(scope='Static preferred-VA store windows, not complete indirect dataflow or runtime context',
        abl_sha256=hashlib.sha256(raw).hexdigest(), pe_sha256=hashlib.sha256(pe).hexdigest(),
        context_offset='0x458', direct_32bit_non_stack_store_candidates=sites,
        limitation='Offset/width matches alone do not establish every base register identity; inspect each source window',
        device_accessed=False)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    for site in sites:
        print('\n'.join(i['address']+' '+i['mnemonic']+' '+i['operands'] for i in site['instructions']))


if __name__ == '__main__':
    main()
