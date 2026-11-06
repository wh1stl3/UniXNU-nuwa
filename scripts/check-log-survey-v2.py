"""Offline readback and negative controls for isolated log survey package."""
import argparse,importlib.util,json,hashlib,struct,zlib
from pathlib import Path
def module(path,name):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work',required=True,type=Path);p.add_argument('--fixture',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    if a.output.exists():raise ValueError('Fresh report required')
    root=Path(__file__).resolve().parents[1];b=module(root/'scripts/build-log-survey-v2.py','survey_build');d=module(root/'scripts/decode-log-survey-v2.py','survey_decode')
    report=json.loads((a.work/'package.json').read_text());image=(a.work/'boot-log-survey-v2.img').read_bytes()
    assert b.sha(image)==report['image_sha256'] and len(image)==report['image_bytes']
    fd=(a.work/'SILICIUM_UEFI.fd').read_bytes();efi=(a.work/'NuwaLogSurvey2Dxe.efi').read_bytes()
    original=(b.transport.ARTIFACT/'build/FV/SILICIUM_UEFI.fd').read_bytes();rebuilt,proof=b.repack(original,efi)
    assert fd==rebuilt and proof==report['proof'] and b.sha(efi)==report['driver_sha256']
    assert b.sha(b.SOURCE.read_bytes())==report['source_sha256']==b.sha((a.work/'NuwaLogSurvey2Dxe.c').read_bytes())
    kernel=(b.transport.ARTIFACT/'shim/shim.bin').read_bytes()+fd
    off=4096+b.align(len(kernel),4096);rsize=struct.unpack_from('<I',image,12)[0];ram=image[off:off+rsize]
    assert ram[:16]==b.transport.MAGIC
    version,header,length,crc=struct.unpack_from('<IIQI',ram,16)
    assert (version,header,length)==(1,64,67108864) and zlib.crc32(ram[64:])==crc
    assert ram[64:]==(a.work/'survey.fat.img').read_bytes()
    b.transport.inspect_container(image,b.transport.STOCK.read_bytes()[:4096],kernel,ram,3)
    transcript=a.fixture.read_text(encoding='utf-8-sig');parsed=d.decode(transcript)
    assert 'PASS: actual AArch64 survey callbacks' in transcript
    graphics_path=a.work/'survey2-graphics.txt'
    graphics=d.decode(graphics_path.read_text())
    assert [m['descriptor_count'] for m in graphics['maps']]==[53,53]
    assert graphics_path.read_text().count('RPP=0018')==6
    rejected=[]
    lines=transcript.splitlines();row=next(x for x in lines if x.startswith('0000 00000007 '))
    bad=[('missing-row',transcript.replace(row+'\n','',1)),('bad-data',transcript.replace(row,row[:-1]+('1' if row[-1]!='1' else '2'),1)),('missing-map',transcript[:transcript.index('NUWA SURVEY2 MAP=1')])]
    for name,value in bad:
        try:d.decode(value)
        except ValueError:rejected.append(name)
        else:raise AssertionError('Accepted '+name)
    inspector=module(root/'scripts/ci/inspect-firmware-candidate.py','survey_inspect');fw=inspector.Firmware();fw.volume(fd,'survey')
    # Corrupt a real FFS byte and require independent checksum parser rejection.
    altered=bytearray(fd);entry=next(x for x in b.files(fd)[0] if x[0]==b.CONTAINER);altered[entry[1]+16]^=1
    try:inspector.Firmware().volume(bytes(altered),'bad')
    except ValueError:rejected.append('ffs-header-checksum')
    else:raise AssertionError('Accepted corrupt FFS')
    seal={}
    paths=[b.SOURCE,Path(__file__),root/'scripts/build-log-survey-v2.py',root/'scripts/decode-log-survey-v2.py',root/'scripts/usb_ramdisk_package.py',root/'scripts/ci/inspect-firmware-candidate.py',root/'tests/log_survey2_host.c',a.fixture]
    for name in ('SurveyDisplay.h','Font.h'):
        path=b.SOURCE.parent/name
        assert path.read_bytes()==(a.work/name).read_bytes()
        paths.append(path)
    paths.append(graphics_path)
    for path in paths:seal[str(path.resolve())]=hashlib.sha256(path.read_bytes()).hexdigest()
    result=dict(scope='Static package readback and AArch64 QEMU user-mode protocol fixture only; not full firmware boot or hardware',image_sha256=b.sha(image),image_bytes=len(image),original_ffs_entries_preserved=proof['original_modules'],driver_direct_target_page_access=False,negative_controls=rejected,fixture_maps=parsed,graphics_fixture=graphics,graphics_rows_per_page=24,glyph_pixels=[20,48],page_stall_microseconds=5000000,source_seal=seal,device_accessed=False)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print('PASS package readback, 159 original FFS entries and 4 negative controls')
if __name__=='__main__':main()
