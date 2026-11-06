"""Bounded arm64 dyld slide-v2 inspection; never mutates a source cache."""
import struct
from desktop_cache import need


def parse_v2(info, mapping_size):
    need(len(info) >= 40, 'Short slide info')
    version, page, starts, count, extras, extra_count, mask, add = struct.unpack_from('<6I2Q', info)
    need(version == 2 and page == 4096, 'Unsupported slide version/page size')
    need(count*page == mapping_size, 'Slide page count differs from mapping')
    need(40 <= starts <= len(info) and count*2 <= len(info)-starts, 'Starts bounds')
    need(not extra_count or (40 <= extras <= len(info) and extra_count*2 <= len(info)-extras), 'Extras bounds')
    need(not extra_count or starts+count*2 <= extras or extras+extra_count*2 <= starts, 'Overlapping slide tables')
    need(mask >> 32 != 0, 'Not a 64-bit delta mask')
    low=(mask & -mask).bit_length()-1; normalized=mask >> low
    need(low >= 2 and normalized & (normalized+1) == 0, 'Noncontiguous delta mask')
    return dict(page=page, count=count, mask=mask, add=add, shift=low-2,
        starts=struct.unpack_from('<'+str(count)+'H',info,starts),
        extras=struct.unpack_from('<'+str(extra_count)+'H',info,extras))


def rebase_page(page, index, info, slide):
    need(len(page)==4096 and 0 <= index < info['count'] and 0 <= slide <= 0xffffffff, 'Page/slide bounds')
    out=bytearray(page);entry=info['starts'][index];chains=[];locations=set();count=0;straddles=0
    if entry == 0x4000:return bytes(out),0,0
    if entry & 0x8000:
        at=entry & 0x3fff
        while True:
            need(at < len(info['extras']), 'Extras index out of bounds')
            value=info['extras'][at];chains.append((value & 0x3fff)*4);at+=1
            if value & 0x8000:break
    else:chains=[entry*4]
    for start in chains:
        at=start;delta=1
        while delta and at <= 4088:
            need(at not in locations, 'Overlapping rebase chains');locations.add(at)
            value=struct.unpack_from('<Q',out,at)[0]
            delta=((value & info['mask']) >> info['shift']) & 0xffffffff
            value &= (~info['mask']) & ((1<<64)-1)
            if value:value=(value+info['add']+slide)&((1<<64)-1)
            struct.pack_into('<Q',out,at,value);count+=1;at+=delta
        if at==4092:
            need(at not in locations, 'Overlapping boundary rebase');locations.add(at)
            value=struct.unpack_from('<I',out,at)[0]
            need(value+slide <= 0xffffffff, 'Boundary pointer low-word carry requires review')
            struct.pack_into('<I',out,at,value+slide);straddles+=1;count+=1
        else:need(at <= 4088, 'Rebase chain crossed page boundary')
    return bytes(out),count,straddles
