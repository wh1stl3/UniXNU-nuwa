"""Pin the source of photographed nuwa vendor-driver errors without changing firmware."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
BINARY=Path('D:/Code/PortingiOS/common/sources/mu-nuwa-firmware/Binaries')
PIN='a1501e0c2e642d6ac0d8f52c85af2a67b75a7799'

def blob(path):
    return subprocess.check_output(['git','-C',str(BINARY),'show',PIN+':'+path])

def main():
    output=ROOT/'reports/volume-status/39985245383/vendor-error-sources.json'
    if output.exists():
        raise ValueError('Fresh evidence required')
    items=[]
    for path,terms in (
        ('nuwa/QcomPkg/Drivers/EnvDxe/EnvDxe.efi',('CPU Vectors','ERROR: CPU Vectors region not present in cfg file !')),
        ('nuwa/QcomPkg/Drivers/SPSSDxe/SPSSDxe.efi',('MDT','metadata','SPSS')),
        ('nuwa/QcomPkg/Drivers/FeatureEnablerDxe/FeatureEnablerDxe.efi',('featenabler','Qsee','TA')),
        ('nuwa/QcomPkg/Drivers/RscDxe/RscDxe.efi',('RSC','Rsc')),
    ):
        raw=blob(path)
        items.append(dict(repository='Project-Silicium/Device-Binaries',commit=PIN,path=path,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),term_presence={s:s.encode() in raw for s in terms},limitation='Pinned binary/strings only; no source-level failure-path attribution'))
    raw=blob('nuwa/RawFiles/uefiplat.cfg')
    vector=[line for line in raw.decode().splitlines() if 'CPU Vectors' in line]
    assert len(vector)==1
    source=(Path('D:/Code/uefi-nuwa')/'Platforms/Xiaomi/nuwaPkg/Library/MemoryMapLib/MemoryMapLib.c').read_bytes().replace(b'\r\n',b'\n')
    assert b'"CPU Vectors"' not in source
    output.write_text(json.dumps(dict(scope='Offline attribution of user photographs, not runtime causality',vendor_inputs=items,config=dict(path='nuwa/RawFiles/uefiplat.cfg',commit=PIN,sha256=hashlib.sha256(raw).hexdigest(),vector_row=vector[0]),current_map=dict(sha256=hashlib.sha256(source).hexdigest(),cpu_vectors_row_present=False),device_changed=False,map_changed=False,conclusion='Real vector-name contract gap exists; do not dismiss as harmless, do not borrow another board address. Its effect on current boot and whether this archived raw config matches installed xbl_config require separate validation.'),indent=2)+'\n',encoding='utf-8')
    print(output.relative_to(ROOT))

if __name__=='__main__':
    main()
