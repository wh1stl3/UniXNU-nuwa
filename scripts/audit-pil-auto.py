"""Read actual PILDxe in RAM and audit AUTO-list control flow; emit text only."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'out/python-tools'))
import capstone


def load(name, path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    result=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--range',action='append',default=[],dest='ranges')
    args=cli.parse_args()
    fv=load('fv','scripts/ci/inspect-firmware-candidate.py')
    pe=load('pe','scripts/audit-abl-handoff.py')
    images=[]
    class Reader(fv.Firmware):
        def sections(self,data,owner,depth):
            if owner['guid']=='1d317734-4083-47c6-83ea-e3a42f2a6bff':
                at=0
                while at+4<=len(data):
                    size,kind,header=int.from_bytes(data[at:at+3],'little'),data[at+3],4
                    if size==0xffffff:size,header=struct.unpack_from('<I',data,at+4)[0],8
                    if not header<=size<=len(data)-at:raise ValueError('PIL section bounds')
                    if kind==0x10:images.append(data[at+header:at+size])
                    at=(at+size+3)&~3
            super().sections(data,owner,depth)
    fd=(ROOT/'out/firmware-ci/39809636575/nuwa-firmware-39809636575/build/FV/SILICIUM_UEFI.fd').read_bytes()
    if hashlib.sha256(fd).hexdigest()!='9ea347a49e51472adac987cf12e20f9e0d99453a23f2113ad24efcd0a07f2eaf':raise ValueError('FD changed')
    Reader().volume(fd,'Fixed R-007 FD')
    data,=images
    base,entry,sections=pe.pe_sections(data)
    strings={}
    for match in re.finditer(rb'[\x20-\x7e]{4,}',data):
        text=match.group().decode()
        if any(t in text.lower() for t in ('auto','uefipil','section','config','parse')):
            section=next((s for s in sections if s['raw_at']<=match.start()<s['raw_at']+s['raw_size']),None)
            if section:strings[base+section['rva']+match.start()-section['raw_at']]=text
    md=capstone.Cs(capstone.CS_ARCH_ARM64,capstone.CS_MODE_LITTLE_ENDIAN)
    md.detail=True;md.skipdata=True
    code=[]
    for s in sections:
        if s['flags']&0x20000000:code+=list(md.disasm(data[s['raw_at']:s['raw_at']+s['raw_size']],base+s['rva']))
    def lines(seq):return [dict(address=hex(i.address),bytes=i.bytes.hex(),mnemonic=i.mnemonic,operands=i.op_str) for i in seq]
    xrefs=[]
    for n,i in enumerate(code):
        if i.mnemonic not in ('adr','adrp'):continue
        target=i.operands[1].imm
        if i.mnemonic=='adrp':
            for j in code[n+1:n+7]:
                if j.id==0:break
                if j.mnemonic=='add' and j.operands[1].reg==i.operands[0].reg:
                    target+=j.operands[2].imm << j.operands[2].shift.value;break
                if j.mnemonic in ('b','ret','br'):break
        if target in strings:xrefs.append(dict(address=hex(i.address),text=strings[target],instructions=lines(code[max(0,n-35):n+40])))
    ranges=[]
    for span in args.ranges:
        a,b=(int(x,0) for x in span.split(':'))
        ranges.append(dict(start=hex(a),end=hex(b),instructions=lines([i for i in code if a<=i.address<b])))
    report=dict(scope='Static PILDxe AUTO parser review, not device/emulator execution',
        pe_sha256=hashlib.sha256(data).hexdigest(),preferred_entry=hex(base+entry),
        strings=[dict(address=hex(a),text=s) for a,s in strings.items()],string_xrefs=xrefs,requested_ranges=ranges)
    # These addresses are bound to this exact PE, not inferred runtime PCs.
    if report['pe_sha256']!='89e030af07847bdc596f0c213bdce0ac430be66e572db55b434d7ec66ad9afcb':
        raise ValueError('PILDxe baseline changed')
    section=next(s for s in sections if s['rva']<=0x18718<s['rva']+s['virtual_size'])
    delta=0x18718-section['rva']
    counter=(data[section['raw_at']+delta:section['raw_at']+delta+4]
             if delta+4<=section['raw_size'] else b'\0'*4)
    instructions={i.address:(i.mnemonic,i.op_str) for i in code}
    required={0x1600:('cbz','w8, #0x1650'),0x4364:('mov','x19, xzr'),
              0x437c:('mov','x0, x19'),0x117dc:('mov','x0, xzr'),
              0x11378:('mov','w8, #0x23')}
    if counter!=b'\0'*4 or any(instructions[a]!=value for a,value in required.items()):
        raise ValueError('Zero-count/parser control-flow assumptions changed')
    report['empty_auto_static_review']=dict(counter_initial_value=0,counter_preferred_address='0x18718',
        config_init='AUTO calls parser enumeration then returns EFI_SUCCESS at 4364/437c',
        enumeration='11764 filters section names; exhaustion returns zero at 117dc',
        comments='Default config parser initializes comment byte # (0x23) at 11378/11380',
        empty_list='1600 CBZ bypasses image load loop and panic branch to protocol installation at 1650',
        limitation='Static control-flow proof under successful config loading; no hardware execution claimed')
    out=ROOT/'reports/pil-no-auto';out.mkdir(parents=True,exist_ok=True)
    (out/'parser-disassembly.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PE',report['pe_sha256'],'entry',report['preferred_entry'])
    for x in xrefs:print(x['address'],x['text'])
    for rg in ranges:
        for i in rg['instructions']:print(i['address'],i['mnemonic'],i['operands'])


if __name__=='__main__':main()
