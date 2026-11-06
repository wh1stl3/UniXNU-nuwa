"""Independent pattern reference and final pair readback. Offline only."""
import argparse,hashlib,importlib.util,json,re,struct,zlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def mod(p,n):
    s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
sha=lambda b:hashlib.sha256(b).hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work',required=True,type=Path);p.add_argument('--reproduce',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    if a.output.exists():p.error('Fresh output required')
    q=json.loads((a.work/'qualification.json').read_text());nonce=bytes.fromhex(q['packages'][0]['nonce'])
    expected=[]
    decoder=mod(ROOT/'scripts/decode-retention-record.py','decoder')
    for slot in range(2):
        payload=bytes(((i*37+11+slot*17)^nonce[i%16])&255 for i in range(65536-64))
        head=struct.pack('<8sHHIIIQ16sI',b'NUWARAM1',1,64,65536,len(payload),0,slot+1,nonce,zlib.crc32(payload))
        raw=head+struct.pack('<IQ',zlib.crc32(head),0x31444D435257554E^(slot+1))+payload
        decoder.decode(raw,nonce,slot+1)
        expected.append(dict(slot=slot,crc32=f'{zlib.crc32(raw):08X}',sha256=sha(raw)))
    survey=mod(ROOT/'scripts/build-log-survey-v2.py','survey');t=survey.transport
    original=(t.ARTIFACT/'build/FV/SILICIUM_UEFI.fd').read_bytes();shim=(t.ARTIFACT/'shim/shim.bin').read_bytes();stock=t.STOCK.read_bytes()
    assert (sha(original),sha(shim),sha(stock))==(t.FD_SHA,t.SHIM_SHA,t.STOCK_SHA)
    files=[]
    for entry in q['source_seal']:
        assert sha(Path(entry['path']).read_bytes())==entry['sha256']
    for package in q['packages']:
        role=package['role'];folder=a.work/role;other=a.reproduce/role
        for name in ('NuwaRetentionDxe.efi','SILICIUM_UEFI.fd','TrialConfig.h'):
            assert (folder/name).read_bytes()==(other/name).read_bytes(),(role,name)
        text=(folder/'host-test.txt').read_text()
        assert re.findall(r'SNAPSHOT CRC=([0-9A-F]{8})',text)==[e['crc32'] for e in expected]
        assert 'PASS actual UEFI '+role+' callbacks: 17 modes' in text
        survey.GUID=package['guid'];fd,proof=survey.repack(original,(folder/'NuwaRetentionDxe.efi').read_bytes())
        assert fd==(folder/'SILICIUM_UEFI.fd').read_bytes() and proof==package['proof'] and proof['original_modules']==159
        fat=(folder/'trial.fat.img').read_bytes();ram=t.MAGIC+struct.pack('<IIQI28x',1,64,len(fat),zlib.crc32(fat))+fat
        image=(folder/'boot-retention.img').read_bytes();assert image==t.compose(stock[:4096],shim+fd,ram,3)
        t.inspect_container(image,stock[:4096],shim+fd,ram,3)
        assert sha(image)==package['image_sha256'] and len(image)==package['image_bytes']
        for dependency in package['dependencies']:assert sha(Path(dependency['path']).read_bytes())==dependency['sha256']
        for path in folder.iterdir():
            if path.is_file():files.append(dict(path=str(path.resolve()),sha256=sha(path.read_bytes()),bytes=path.stat().st_size))
    result=dict(scope='Offline paired RAM pattern images: callbacks, independent pattern encoding, source hashes, original FFS preservation, driver/FD reproduction and final boot readback; no hardware/cache/reset retention claim',nonce=nonce.hex(),expected_snapshots=expected,packages=q['packages'],source_seal=q['source_seal'],files=files,device_accessed=False,boot_reproducibility_claim=False,remaining=['Hardware CPU cache execution and display','Actual manual reset and reader boot with same nonce','XBL/ABL/next-load overwrite attribution','XNU mapping and ownership integration'])
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x',encoding='utf-8') as f:f.write(json.dumps(result,indent=2)+'\n')
    print('PASS independent pattern CRCs, 34 callback scenarios, 159 FFS preservation, driver/FD reproduction and both final images')
if __name__=='__main__':main()
