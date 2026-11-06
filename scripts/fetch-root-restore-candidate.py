"""Fetch only the pinned iOS16 RestoreRamDisk to local out; never boot/install it."""
import argparse,hashlib,json,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REF=Path('D:/Code/PortingiOSLegacy')
def sha(data):return hashlib.sha256(data).hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    work=a.work.resolve();output=a.output.resolve()
    if not work.is_relative_to(ROOT/'out') or work.exists() or not output.is_relative_to(ROOT/'reports') or output.exists():raise ValueError('Fresh out and reports required')
    source=REF/'scripts/fetch_donor_manifest.py'
    if sha(source.read_bytes())!='a49525079424ade008c3fb0d1e8245c13ff7153a55ec77b73467a9cf6980066e':raise ValueError('Read-only range reader changed')
    sys.path.insert(0,str(REF/'scripts'))
    from fetch_donor_manifest import RangeFile
    class Ranges(RangeFile):
        MAX_TOTAL=160*1024**2
        MAX_REQUESTS=128
    lock_path=REF/'config/donor-ios16.lock.json';lock_bytes=lock_path.read_bytes();lock=json.loads(lock_bytes)
    if (lock['product_type'],lock['version'],lock['build'])!=('iPhone10,3','16.7.16','20H392'):raise ValueError('Pinned identity differs')
    if lock['manifest_sha256']!='2d1452103a2f5ad71cb78d94454977fc70632472201980a468c247fba14b10b7' or lock['archive_size']!=6171035648:raise ValueError('Pinned archive manifest differs')
    entries=[i for i in lock['build_identities'] if i['device_class']=='d22ap' and i['restore_behavior']=='Erase' and int(i['ap_chip_id'],16)==0x8015 and int(i['ap_board_id'],16)==6]
    if len(entries)!=1:raise ValueError('Ambiguous identity')
    entry=entries[0]['components']['RestoreRamDisk']
    if entry['path']!='087-86719-047.dmg' or entry['size']!=106954779 or entry['manifest_digest_hex']!='c3db39239ff755c9832112722da386879ec0b04067f2720d3a6a3397276ea5480863fb5d39f3286603b90fcae4e3afba':raise ValueError('Restore component differs')
    work.mkdir(parents=True);target=work/'restore.im4p';record=dict(scope=__doc__,device_accessed=False,installed=False,reference_source_sha256=sha(source.read_bytes()),lock_sha256=sha(lock_bytes),component=entry,status='in-progress')
    output.parent.mkdir(parents=True,exist_ok=True)
    try:
        with Ranges(lock['ipsw_url']) as remote:
            if remote.length!=lock['archive_size'] or remote.etag!=lock['archive_etag']:raise ValueError('Apple archive identity changed')
            with zipfile.ZipFile(remote) as archive:
                if sha(archive.read('BuildManifest.plist'))!=lock['manifest_sha256']:raise ValueError('BuildManifest changed')
                info=archive.getinfo(entry['path'])
                if info.file_size!=entry['size'] or f'{info.CRC:08x}'!=entry['zip_crc32']:raise ValueError('ZIP metadata differs')
                with archive.open(info) as stream,target.open('xb') as dest:
                    count=0
                    while chunk:=stream.read(8*1024**2):
                        count+=len(chunk)
                        if count>entry['size']:raise ValueError('Restore image exceeds manifest extent')
                        dest.write(chunk)
                        print(json.dumps(dict(downloaded=count,total=entry['size'])),flush=True)
            record['range_requests']=remote.requests;record['transferred_bytes']=remote.transferred
        raw=target.read_bytes()
        if len(raw)!=entry['size'] or hashlib.sha384(raw).hexdigest()!=entry['manifest_digest_hex']:raise ValueError('Manifest SHA384 mismatch')
        from apple_donor_formats import im4p_payload
        kind,payload=im4p_payload(raw);payload_path=work/'restore-payload.bin';payload_path.write_bytes(payload)
        record.update(status='downloaded-and-inspected',im4p_type=kind,container_sha256=sha(raw),container_bytes=len(raw),payload_sha256=sha(payload),payload_bytes=len(payload),payload_prefix_hex=payload[:32].hex(),filesystem_signature_at_1024=payload[1024:1026].hex(),payload_path=payload_path.relative_to(ROOT).as_posix(),apple_signature_checked=False,nuwa_mounted=False)
        print(json.dumps({k:v for k,v in record.items() if k in ('status','im4p_type','payload_bytes','filesystem_signature_at_1024')}))
    except Exception as e:
        record.update(status='failed',error=str(e));raise
    finally:output.write_bytes(json.dumps(record,indent=2).encode()+b'\n')
if __name__=='__main__':main()
