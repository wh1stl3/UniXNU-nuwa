"""Build the partition-sized nuwa cold-boot carrier control from the exact R10 package."""
import argparse
import hashlib
import json
import struct
import subprocess
import tomllib
import zlib
from pathlib import Path

import usb_ramdisk_package as transport
from ufs_layout_context import API

ROOT = Path(__file__).resolve().parents[1]
R10 = 'bb2b972fbdd9342ed018362121cf84604e0e74a928e23ef5a56355af8d7a3b6c'
FAT_BYTES = 176 << 20
sha = lambda data: hashlib.sha256(data).hexdigest()


def compact(original, old_menu):
    """Drop free tail clusters only. Preserve the FAT, directory trees and payload extents."""
    new = bytearray(original[:FAT_BYTES])
    u16 = lambda offset: struct.unpack_from('<H', original, offset)[0]
    u32 = lambda offset: struct.unpack_from('<I', original, offset)[0]
    sector, spc, reserved, tables = u16(11), original[13], u16(14), original[16]
    fat_sectors, info, backup = u32(36), u16(48), u16(50)
    assert (sector, spc, reserved, tables, fat_sectors, info, backup)==(512,4,32,2,765,1,6)
    assert len(original)==u32(32)*sector and not u16(19) and len(new)==FAT_BYTES
    assert original[:sector]==original[backup*sector:(backup+1)*sector]
    start = reserved + tables*fat_sectors
    old_count = (len(original)//sector-start)//spc
    new_count = (len(new)//sector-start)//spc
    copies = [original[(reserved+i*fat_sectors)*sector:(reserved+(i+1)*fat_sectors)*sector] for i in range(tables)]
    assert copies[0]==copies[1] and new_count>=65525
    entries = struct.unpack('<%dI'%(len(copies[0])//4),copies[0])
    used = [i for i in range(2,old_count+2) if entries[i] & 0x0fffffff]
    assert max(used)<new_count+2
    assert all((entries[i]&0x0fffffff)>=0x0ffffff8 or 2<=(entries[i]&0x0fffffff)<new_count+2 for i in used)
    assert u32(info*sector)==0x41615252 and u32(info*sector+484)==0x61417272
    assert u32(info*sector+488)==old_count-len(used)
    assert u32(info*sector+492)<new_count+2
    for offset in (0,backup*sector):
        struct.pack_into('<I',new,offset+32,FAT_BYTES//sector)
    struct.pack_into('<I',new,info*sector+488,new_count-len(used))
    menu = old_menu.replace(b'NUWA UFS-R10 r1',b'NUWA PERSIST-C1 r1').replace(b'XNU UFS physical root-window layout',b'iOS16 UFS layout control')
    assert len(menu)<=len(old_menu) and new.count(old_menu)==1
    menu=menu.ljust(len(old_menu),b' ')
    before=tomllib.loads(old_menu.decode()); after=tomllib.loads(menu.decode())
    assert after['ui']['title']=='NUWA PERSIST-C1 r1'
    after['ui']['title']=before['ui']['title']
    after['entry'][0]['title']=before['entry'][0]['title']
    assert before==after
    at=new.index(old_menu)
    cluster=(at//sector-start)//spc+2
    assert cluster in used and at+len(menu)<=(start+(cluster-1)*spc)*sector
    new[at:at+len(menu)]=menu
    return bytes(new),menu,dict(used_clusters=len(used),highest_used_cluster=max(used),new_clusters=new_count,free_clusters=new_count-len(used))


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--work',type=Path,required=True)
    work=cli.parse_args().work.resolve()
    assert work.is_relative_to(ROOT/'out')
    work.mkdir(exist_ok=False)
    parent=ROOT/'out/ufs-r10-r1'
    source=(parent/'boot-ufs-r10-r1.img').read_bytes()
    report=json.loads((ROOT/'reports/ufs-r10-r1/build.json').read_bytes())
    assert sha(source)==R10==report['image_sha256']
    stock=transport.STOCK.read_bytes()
    assert sha(stock)==transport.STOCK_SHA
    k,r=struct.unpack_from('<II',source,8)
    offset=4096+((k+4095)//4096)*4096
    firmware=source[4096:4096+k]; envelope=source[offset:offset+r]
    transport.inspect_container(source,stock[:4096],firmware,envelope,3)
    original=envelope[64:]
    assert envelope[:16]==transport.MAGIC and sha(original)==report['fat_sha256']
    fat,menu,proof=compact(original,(parent/'fat/readback-unixnu.toml').read_bytes())
    envelope=transport.MAGIC+struct.pack('<IIQI28x',1,64,len(fat),zlib.crc32(fat))+fat
    image=transport.compose(stock[:4096],firmware,envelope,3)
    path=work/'boot-persist-c1-r1.img';path.write_bytes(image)
    shipped=path.read_bytes()
    transport.inspect_container(shipped,stock[:4096],firmware,envelope,3)
    fp=work/'shipped.fat';fp.write_bytes(shipped[offset+64:offset+64+len(fat)])
    def linux(p):
        return '/mnt/d/'+p.resolve().as_posix()[3:]
    def run(*args):
        return subprocess.run(['wsl','-d','Ubuntu-22.04','--',*args],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE).stdout
    fsck=run('/usr/sbin/fsck.fat','-n',linux(fp)).decode()
    paths={'unixnu.toml':'::/EFI/UniXNU/unixnu.toml'}
    for name in ('kernel.macho','kernel.macho.adt','root-restore.apfs'):
        paths[name]='::/EFI/UniXNU/Payloads/'+name
    for name,dest in paths.items():
        run('mcopy','-i',linux(fp),dest,linux(work/name))
        expected=menu if name=='unixnu.toml' else (parent/'fat'/('readback-'+name)).read_bytes()
        assert (work/name).read_bytes()==expected
    policy=json.loads((ROOT/'reports/ufs-r10-r1/root-policy.json').read_bytes())
    API.validate((work/'kernel.macho.adt').read_bytes(),work/'kernel.macho',ROOT/policy['fd_path'],ROOT/policy['shim_path'],work/'root-restore.apfs',(parent/'launch/nonce.bin').read_bytes())
    geometry=json.loads((ROOT/'reports/ufs-r10-r1/trial/carrier-geometry.json').read_bytes())
    capacity=min(geometry[key]['bytes'] for key in ('boot_a','boot_b'))
    assert len(shipped)<capacity<len(source)
    proof.update(candidate='PERSIST-C1 r1',image_path=path.relative_to(ROOT).as_posix(),image_sha256=sha(shipped),image_bytes=len(shipped),parent_sha256=R10,parent_bytes=len(source),boot_partition_bytes=capacity,headroom_bytes=capacity-len(shipped),fat_sha256=sha(fat),fat_bytes=len(fat),fsck=fsck,files={n:sha((work/n).read_bytes()) for n in paths},shipped_envelope_crc32=f'{zlib.crc32(fat):08x}',hardware_executed=False)
    (work/'build.json').write_text(json.dumps(proof,indent=2))
    print(proof['image_sha256'],len(shipped),proof['headroom_bytes'])

if __name__=='__main__':main()
