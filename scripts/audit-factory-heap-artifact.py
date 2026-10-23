"""Compare old/new SEC memory descriptor bytes; only the approved Heap may change."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import struct
import subprocess

ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT/'out/firmware-ci/39829943950/nuwa-firmware-39829943950'

def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('artifact',type=Path)
    cli.add_argument('--output',type=Path,required=True)
    args=cli.parse_args()
    output=args.output.resolve()
    if not output.is_relative_to(ROOT):raise ValueError('Repo-local output required')
    spec=importlib.util.spec_from_file_location('fd_reader',ROOT/'scripts/ci/inspect-firmware-candidate.py')
    reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
    profile=json.loads((ROOT/'config/firmware-factory-heap-profile.json').read_text())
    path='Platforms/Xiaomi/nuwaPkg/Library/MemoryMapLib/MemoryMapLib.c'
    commit=profile['recipe']['sources']['firmware']['commit']
    source=subprocess.check_output(['git','--no-optional-locks','-C','D:/Code/uefi-nuwa','show',commit+':'+path]).decode()
    names=re.findall(r'^\s*\{"([^"]+)",\s*0x',source,re.M)
    if not names or names.count('DXE Heap')!=1:raise ValueError('Unexpected descriptor source layout')
    # MemoryMapLib.h fixed struct: Name[32], Address/Length, five UINT32 fields
    # (HobOption, ResourceType, ResourceAttribute, MemoryType, ArmAttributes),
    # then four padding bytes -> AARCH64 stride 72. PiHob.h defines the
    # resource attribute type as UINT32; never interpret padding as a field.
    stride=72;captured=[];original=reader.heap_descriptors
    def capture(data):
        captured.append(data)
        return original(data)
    reader.heap_descriptors=capture
    tables=[]
    for artifact in (OLD,args.artifact.resolve()):
        captured.clear();fw=reader.Firmware();fw.volume((artifact/'build/FV/SILICIUM_UEFI.fd').read_bytes(),'FD/FVMAIN_COMPACT')
        if len(captured)!=1:raise ValueError('Unique actual SEC image required')
        body=captured[0];prefix=names[0].encode().ljust(32,b'\0');at=body.find(prefix)
        if at<0:raise ValueError('Descriptor array absent in actual SEC')
        table=body[at:at+stride*len(names)]
        if len(table)!=stride*len(names):raise ValueError('Truncated descriptor table')
        for i,name in enumerate(names):
            if table[i*stride:i*stride+32]!=name.encode().ljust(32,b'\0'):raise ValueError('Actual descriptor order/stride differs')
        tables.append(table)
    index=names.index('DXE Heap');offset=index*stride+32
    old_values=struct.unpack_from('<QQ',tables[0],offset);new_values=struct.unpack_from('<QQ',tables[1],offset)
    if old_values!=(0xbae00000,0x04500000) or new_values!=(0xbab00000,0x0d1c0000):raise ValueError('Unexpected old/new Heap')
    masked=[]
    for table in tables:
        data=bytearray(table);data[offset:offset+16]=b'\0'*16;masked.append(data)
    if masked[0]!=masked[1]:raise ValueError('Other descriptor bytes changed')
    result=dict(result='actual old/new SEC descriptor comparison passed',descriptor_count=len(names),stride=stride,
        changed_row='DXE Heap',old=dict(base=hex(old_values[0]),bytes=old_values[1]),new=dict(base=hex(new_values[0]),bytes=new_values[1]),
        all_other_descriptor_bytes_identical=True,all_other_heap_fields_identical=True,
        old_table_sha256=hashlib.sha256(tables[0]).hexdigest(),new_table_sha256=hashlib.sha256(tables[1]).hexdigest(),
        source_commit=commit,device_executed=False,
        limitation='Binary descriptor consistency only; not runtime ownership, HOB/MMU or successful dispatch')
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
