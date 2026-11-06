"""Inspect thin/universal service files; never substitute ARM64e for ARM64-all."""
import struct
from desktop_cache import macho_dependencies, need


def inspect(raw):
    need(len(raw) >= 4,'Short service file')
    if raw[:4] == bytes.fromhex('cffaedfe'):
        info = macho_dependencies(raw)
        return dict(format='thin_macho', selected=info if info['subtype'] & 0xffffff == 0 else None,
                    slices=[dict(offset=0,bytes=len(raw),**info)], scope='Header/dependencies; not signatures or runtime ABI')
    magic = struct.unpack_from('>I',raw)[0]
    if magic not in (0xcafebabe,0xcafebabf):
        return dict(format='unhandled',header_hex=raw[:32].hex(),selected=None,slices=[],scope='Presence only; file format pending')
    need(len(raw) >= 8,'Short universal header'); count = struct.unpack_from('>I',raw,4)[0]; width = 20 if magic == 0xcafebabe else 32
    need(0 < count <= 64 and 8+count*width <= len(raw),'Universal architecture table bounds'); slices = []; extents = []; keys = set()
    for i in range(count):
        if width == 20:
            cpu,sub,off,size,align = struct.unpack_from('>5I',raw,8+i*width)
        else:
            cpu,sub,off,size,align,reserved = struct.unpack_from('>IIQQII',raw,8+i*width); need(reserved == 0,'Universal reserved field')
        need(align <= 31 and off % (1 << align) == 0 and size >= 32 and off >= 8+count*width and off+size <= len(raw),'Universal slice extent/alignment')
        need((cpu,sub) not in keys,'Duplicate universal architecture'); keys.add((cpu,sub)); extents.append((off,off+size))
        item = dict(cpu=hex(cpu),subtype=sub,offset=off,bytes=size)
        if cpu == 0x100000c:
            info = macho_dependencies(raw[off:off+size]); need(info['subtype'] == sub,'Universal/inner subtype mismatch'); item.update(info)
        slices.append(item)
    extents.sort(); need(all(a[1] <= b[0] for a,b in zip(extents,extents[1:])),'Overlapping universal slices')
    compatible = [v for v in slices if v['cpu']=='0x100000c' and v['subtype'] & 0xffffff == 0]
    need(len(compatible) <= 1,'Ambiguous ARM64-all slice')
    return dict(format='universal_macho',slices=slices,selected=compatible[0] if compatible else None,
                scope='ARM64-all selection only; no ARM64e fallback, signatures or runtime ABI qualification')
