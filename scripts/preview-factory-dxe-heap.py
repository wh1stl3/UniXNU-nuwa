"""Prepare a read-only one-row factory heap proposal; never apply or build it."""
import difflib
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess

ROOT=Path(__file__).resolve().parents[1]
FW=Path('D:/Code/uefi-nuwa')
PATH='Platforms/Xiaomi/nuwaPkg/Library/MemoryMapLib/MemoryMapLib.c'
PIN='2ab6827d77dfe15010534b52e1abb76a26464a7d'

def sha(data):return hashlib.sha256(data).hexdigest()

def main():
    original=subprocess.check_output(['git','--no-optional-locks','-C',str(FW),'show',PIN+':'+PATH]).decode().replace('\r\n','\n')
    if (FW/PATH).read_text().replace('\r\n','\n')!=original:raise ValueError('Firmware map differs from pinned source')
    factory_path=ROOT/'reports/loader-integration/factory-uefiplatLA-original.txt'
    factory=factory_path.read_text()
    match=re.search(r'^(0x[0-9A-Fa-f]+),\s*(0x[0-9A-Fa-f]+),\s*"DXE Heap".*$',factory,re.M)
    if not match:raise ValueError('Same-device factory heap row absent')
    base,size=[int(v,16) for v in match.groups()];end=base+size
    row=re.search(r'^.*\{"DXE Heap",\s*(0x[0-9A-Fa-f]+),\s*(0x[0-9A-Fa-f]+),.*$',original,re.M)
    if not row:raise ValueError('Pinned heap row absent')
    revised=original[:row.start()]+row[0].replace(row[1],match[1]).replace(row[2],match[2])+original[row.end():]
    overlaps=[]
    for line in original.splitlines():
        m=re.search(r'\{"([^"]+)",\s*(0x[0-9A-Fa-f]+),\s*(0x[0-9A-Fa-f]+),',line)
        if not m or m[1]=='DXE Heap':continue
        start,length=int(m[2],16),int(m[3],16)
        if length and max(base,start)<min(end,start+length):overlaps.append(dict(name=m[1],base=hex(start),bytes=length))
    dt_path=ROOT/'reports/firmware-ci/39802617878/live-dt-map-comparison.json'
    dt=json.loads(dt_path.read_text());reserved=[];banks=[];skipped=[];initrd={}
    for node in dt['selected_nodes']:
        props=node['properties']
        if node['node']=='/chosen':
            for key in ('linux,initrd-start','linux,initrd-end'):
                if key in props:initrd[key]=int(props[key]['hex'],16)
        if node['node'].startswith('/memory') and 'reg' in props:
            data=bytes.fromhex(props['reg']['hex'])
            if len(data)%16:skipped.append(node['node']);continue
            banks += [struct.unpack_from('>QQ',data,i) for i in range(0,len(data),16)]
        if not node['node'].startswith('/reserved-memory/') or 'reg' not in props:continue
        data=bytes.fromhex(props['reg']['hex'])
        if len(data)%16:skipped.append(node['node']);continue
        for i in range(0,len(data),16):
            start,length=struct.unpack_from('>QQ',data,i)
            if length and max(base,start)<min(end,start+length):reserved.append(dict(node=node['node'],base=hex(start),bytes=length))
    covers=any(start<=base and end<=start+length for start,length in banks)
    initrd_overlap=bool(initrd and max(base,initrd['linux,initrd-start'])<min(end,initrd['linux,initrd-end']))
    patch=''.join(difflib.unified_diff(original.splitlines(True),revised.splitlines(True),fromfile='a/'+PATH,tofile='b/'+PATH))
    patch_path=ROOT/'patches/firmware-candidates/0009-nuwa-factory-dxe-heap-proposal.patch'
    patch_path.write_bytes(patch.encode())
    # Only a dry run. The independent firmware checkout is not changed.
    command=['git','--no-optional-locks','-C',str(FW),'apply','--check',str(patch_path)]
    check=subprocess.run(command,capture_output=True,text=True);check.check_returncode()
    report=dict(scope='R-011 A source proposal only; not applied, built or device tested',firmware_commit=PIN,
        source=dict(path=PATH,lf_sha256=sha(original.encode()),proposed_lf_sha256=sha(revised.encode())),
        factory_source=dict(path=factory_path.relative_to(ROOT).as_posix(),sha256=sha(factory_path.read_bytes()),row=match[0]),
        old=dict(base=row[1],bytes=int(row[2],16),mib=int(row[2],16)/1048576),
        proposed=dict(base=hex(base),bytes=size,end_exclusive=hex(end),mib=size/1048576),
        patch=dict(path=patch_path.relative_to(ROOT).as_posix(),sha256=sha(patch.encode())),
        static_checks=dict(other_current_firmware_row_overlaps=overlaps,android_reserved_reg_overlaps=reserved,
            android_memory_bank_covers_proposal=covers,android_initrd_overlap=initrd_overlap,unparsed_reg_nodes=skipped,
            dt_source=dt_path.relative_to(ROOT).as_posix(),dt_snapshot_sha256=dt['sha256'],
            apply_check_argv=command,apply_check_exit_code=check.returncode),
        unchanged=['All other memory-map rows and attributes','FD destination and size','BootShim and loader layout',
                   'board.toml/bringup-plan/feed','XNU ADT window and 4KiB policy'],
        limitations=['Android FDT is historical and is not the actual candidate ABL x0 DT',
                     'Static non-overlap does not establish runtime ownership or successful MMU/HOB/dispatch',
                     'Root source of every allocation/protocol/storage failure not determined',
                     'R-010 explicitly excluded memory-map changes; R-011 remains a proposal'])
    (ROOT/'reports/dxe-allocation-audit/factory-heap-proposal.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(old_mib=report['old']['mib'],proposed_mib=report['proposed']['mib'],checks=report['static_checks']),indent=2))

if __name__=='__main__':main()
