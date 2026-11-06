"""Create a deterministic 4MiB FAT16 configuration probe for an FV RAW section."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

ROOT=Path(__file__).resolve().parents[1]
SIZE=4*1024*1024

def build(config):
    if len(config)>512:
        raise ValueError('Configuration-only probe must fit one cluster')
    image=bytearray(SIZE)
    image[:3]=b'\xeb\x3c\x90';image[3:11]=b'NUWAFV  '
    struct.pack_into('<HBHBHHBHHHII',image,11,512,1,1,2,512,SIZE//512,0xf8,32,32,64,0,0)
    image[36]=0x80;image[38]=0x29
    struct.pack_into('<I',image,39,0x4e555741)
    image[43:54]=b'NUWA PROBE ';image[54:62]=b'FAT16   ';image[510:512]=b'\x55\xaa'
    fat=bytearray(32*512)
    for index,value in enumerate((0xfff8,0xffff,0xffff,0xffff,0xffff)):
        struct.pack_into('<H',fat,index*2,value)
    image[512:33*512]=fat;image[33*512:65*512]=fat
    def entry(name,cluster,attr,size=0):
        row=bytearray(32);row[:11]=name;row[11]=attr
        # Fixed 1980-01-01 FAT date, no clock-dependent metadata.
        struct.pack_into('<H',row,24,33);struct.pack_into('<HI',row,26,cluster,size)
        return row
    root=65*512;data=97*512
    image[root:root+32]=entry(b'EFI        ',2,0x10)
    image[data:data+32]=entry(b'.          ',2,0x10)
    image[data+32:data+64]=entry(b'..         ',0,0x10)
    image[data+64:data+96]=entry(b'UNIXNU     ',3,0x10)
    image[data+512:data+544]=entry(b'.          ',3,0x10)
    image[data+544:data+576]=entry(b'..         ',2,0x10)
    # unixnu.toml needs VFAT: its four-character extension does not fit 8.3.
    short=b'UNIXNU  TOM'
    checksum=0
    for value in short:checksum=(((checksum&1)<<7)+(checksum>>1)+value)&255
    long=bytearray(b'\xff'*32);long[0]=0x41;long[11]=0x0f;long[12]=0;long[13]=checksum;long[26:28]=b'\0\0'
    units=[ord(c) for c in 'unixnu.toml']+[0,0xffff]
    for offset,value in zip((1,3,5,7,9,14,16,18,20,22,24,28,30),units):struct.pack_into('<H',long,offset,value)
    image[data+576:data+608]=long
    image[data+608:data+640]=entry(short,4,0x20,len(config))
    image[data+1024:data+1024+len(config)]=config
    return bytes(image)

def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--output',required=True,type=Path)
    args=cli.parse_args()
    if args.output.exists():raise ValueError('Fresh output required')
    config=(ROOT/'config/volume-probe/unixnu.toml').read_bytes().replace(b'\r\n',b'\n')
    image=build(config)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_bytes(image)
    print(json.dumps(dict(bytes=len(image),sha256=hashlib.sha256(image).hexdigest(),scope='Configuration-only FAT16; no XNU or ADT')))

if __name__=='__main__':main()
