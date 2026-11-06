"""Assemble fixed iOS16 OS/SystemOS file windows, never a device or flash target."""
import argparse, hashlib, json, shutil, struct, subprocess, types
from pathlib import Path
from desktop_root_contract import geometry
ROOT=Path(__file__).resolve().parents[1]
REV='0fc0fc1f9ddd0fbd4787738afef38667df5e0a95'
REFERENCE=Path('/mnt/d/Code/UniXNU-integration')
DECODER=Path('/mnt/d/Code/PortingiOSLegacy/common/tools/apfs-fuse-linux/bin/lzfse')
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        while b:=f.read(8<<20):h.update(b)
    return h.hexdigest()
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--work',type=Path,required=True);a=ap.parse_args();work=a.work.resolve()
    if work.exists() or not work.is_relative_to(ROOT/'out'):raise ValueError('Fresh local output required')
    evidence=ROOT/'reports/desktop-readiness/2026-10-27-contract-r1/audit-r2.json';parent=json.loads(evidence.read_bytes())
    plan=parent['root_window_preview'];total=plan['image_bytes']
    if shutil.disk_usage(work.parent).free<total+(1<<30):raise ValueError('Insufficient output space')
    original=subprocess.check_output(['git','-C',str(REFERENCE),'show',REV+':scripts/unixnu/udif.py'])
    text=original.decode();assert text.count('from .util import Error, lzfse')==1
    module=types.ModuleType('pinned_udif');module.Error=ValueError;module.lzfse=lambda:str(DECODER)
    exec(compile(text.replace('from .util import Error, lzfse',''),'pinned-udif','exec'),module.__dict__)
    work.mkdir();(work/'udif-reference.py').write_bytes(original)
    image=work/'fullroot-analysis.img';entries=[]
    with image.open('xb') as out:
        out.truncate(total)
        for window in plan['windows']:
            record=next(v for v in parent['inputs'] if v['component']==window['source_component']);source=Path(record['path'])
            if source.stat().st_size!=record['before']['bytes'] or sha(source)!=record['before']['sha256']:raise ValueError('Source changed')
            if geometry(source)!=record['geometry']:raise ValueError('Geometry changed')
            decoded=module.Image(source)
            if decoded.size!=window['raw_bytes']:raise ValueError('Decoded size mismatch')
            out.seek(window['offset']);h=hashlib.sha256();count=0
            for block in decoded.blocks():out.write(block);h.update(block);count+=len(block)
            if count!=decoded.size:raise ValueError('Decoded length mismatch')
            if sha(source)!=record['before']['sha256']:raise ValueError('Source changed during read')
            entries.append(dict(**window,raw_sha256=h.hexdigest(),source_path=str(source),source_sha256=record['before']['sha256']))
            print('Decoded and copied '+window['name'],flush=True)
        manifest=bytearray(4096);struct.pack_into('<8sIIQ',manifest,0,b'SHNGROOT',1,len(entries),total)
        for i,e in enumerate(entries):
            at=24+i*128;name=e['name'].encode('ascii');assert 0<len(name)<32
            manifest[at:at+len(name)]=name
            struct.pack_into('<QQII',manifest,at+32,e['offset'],e['raw_bytes'],512,1)
            manifest[at+56:at+88]=bytes.fromhex(e['raw_sha256'])
        manifest[4064:]=hashlib.sha256(manifest[:4064]).digest();out.seek(0);out.write(manifest)
    (work/'manifest.bin').write_bytes(manifest)
    with image.open('rb') as f:
        assert f.read(4096)==manifest
        for e in entries:
            f.seek(e['offset']);remaining=e['raw_bytes'];h=hashlib.sha256()
            while remaining:
                b=f.read(min(8<<20,remaining));assert b;h.update(b);remaining-=len(b)
            assert h.hexdigest()==e['raw_sha256']
    seed=json.loads((ROOT/'reports/desktop-readiness/2026-10-27-data-linux-r1/candidate.json').read_bytes())['candidate']
    data=ROOT/'out/linux-data-candidate-20261027-r1/build-a/data-linux.raw';packed=data.with_suffix('.dbr')
    assert sha(data)==seed['raw_sha256'] and sha(packed)==seed['packed_sha256']
    report=dict(passed=True,scope='Local file assembly and byte readback only',image=dict(path=image.relative_to(ROOT).as_posix(),bytes=total,sha256=sha(image)),
      windows=entries,manifest_sha256=sha(work/'manifest.bin'),parent_sha256=sha(evidence),
      decoder=dict(revision=REV,script_sha256=hashlib.sha256(original).hexdigest(),binary_sha256=sha(DECODER),adapter='Replace package utility import with ValueError and pinned local decoder path only'),
      data=dict(volume_uuid=seed['volume_uuid'],logical_bytes=seed['logical_bytes'],raw_sha256=seed['raw_sha256'],packed_sha256=seed['packed_sha256'],mode='volatile',delivery='one PackedRAMDisk; no simultaneous RAMDisk'),
      target_geometry=None,capacity_fit=None,root_authentication_integrated=False,mount_proven=False,deployable=False,device_accessed=False)
    (work/'audit.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report['image']))
if __name__=='__main__':main()
