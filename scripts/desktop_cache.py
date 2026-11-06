"""Bounded, read-only dyld 1066 cache metadata and dependency reader.

Format reference: apple-oss-distributions/dyld dyld-1066.8,
cache-builder/dyld_cache_format.h and common/DyldSharedCache.cpp (APSL).
This module implements metadata parsing, not dyld loading or signature checks.
"""
import hashlib, struct
from pathlib import Path


def need(ok, message):
    if not ok:
        raise ValueError(message)


class Reader:
    def __init__(self, path):
        self.path = Path(path); self.size = self.path.stat().st_size
        self.file = self.path.open('rb'); self.digest = hashlib.sha256(); self.reads = 0

    def read(self, off, length):
        need(0 <= off <= self.size and 0 <= length <= self.size-off and length <= 8*1024*1024, 'File read bounds')
        self.file.seek(off); raw = self.file.read(length)
        need(len(raw) == length, 'Short file read')
        self.digest.update(struct.pack('<QQ', off, length)); self.digest.update(raw); self.reads += 1
        return raw

    def cstring(self, off):
        raw = self.read(off, min(4096, self.size-off))
        need(b'\0' in raw, 'Unterminated cache string')
        return raw.split(b'\0', 1)[0].decode('utf-8')


def header(reader):
    raw = reader.read(0, min(reader.size, 0x200))
    need(len(raw) >= 0x1cc and raw[:7] == b'dyld_v1', 'Unsupported cache header')
    mapping, count = struct.unpack_from('<II', raw, 0x10)
    need(0x1cc <= mapping <= 0x10000 and 0 < count <= 64, 'Unsupported cache mapping table')
    entries = reader.read(mapping, count*32); maps = []
    for i in range(count):
        address, size, offset, maximum, initial = struct.unpack_from('<QQQII', entries, i*32)
        need(size > 0 and address+size <= 1 << 64 and offset+size <= reader.size, 'Cache mapping extent')
        need(initial & ~maximum == 0, 'Cache mapping protections')
        maps.append(dict(address=address, size=size, offset=offset, maxprot=maximum, initprot=initial))
    images, image_count = struct.unpack_from('<II', raw, 0x1c0)
    suboff, subcount = struct.unpack_from('<II', raw, 0x188)
    need(image_count <= 100000 and subcount <= 256, 'Cache table count')
    return dict(uuid=raw[0x58:0x68].hex(), magic=raw[:16].hex(), mapping_offset=mapping,
                mappings=maps, images_offset=images, images_count=image_count,
                subcache_offset=suboff, subcache_count=subcount, symbol_uuid=raw[0x190:0x1a0].hex(),
                region_start=struct.unpack_from('<Q', raw, 0xe0)[0])


def subentries(reader, info):
    # cacheSubType at 0x1c8 selects the suffix-bearing entries in dyld 1066.
    modern = info['mapping_offset'] > 0x1c8; width = 56 if modern else 24
    raw = reader.read(info['subcache_offset'], info['subcache_count']*width); result = []
    for i in range(info['subcache_count']):
        item = raw[i*width:(i+1)*width]
        if modern:
            need(b'\0' in item[24:56], 'Subcache suffix unterminated')
            suffix = item[24:56].split(b'\0', 1)[0].decode('ascii')
        else:
            suffix = '.' + str(i+1)
        need(suffix.startswith('.') and '/' not in suffix and '\\' not in suffix and '..' not in suffix, 'Invalid subcache suffix')
        result.append(dict(uuid=item[:16].hex(), vm_offset=struct.unpack_from('<Q', item, 16)[0], suffix=suffix))
    need(len({v['suffix'] for v in result}) == len(result), 'Duplicate subcache suffix')
    return result


def macho_dependencies(raw):
    need(len(raw) >= 32, 'Short Mach-O header')
    magic, cpu, subtype, kind, count, size, flags, reserved = struct.unpack_from('<8I', raw)
    need(magic == 0xfeedfacf and cpu == 0x100000c and count <= 4096 and size <= 1024*1024, 'Unsupported Mach-O')
    need(32+size <= len(raw), 'Mach-O commands truncated'); pos = 32; deps = []; rpaths = []
    for _ in range(count):
        need(pos+8 <= 32+size, 'Load command header')
        cmd, length = struct.unpack_from('<II', raw, pos)
        need(length >= 8 and length % 8 == 0 and pos+length <= 32+size, 'Load command bounds')
        if cmd in (0xc, 0x80000018, 0x8000001f, 0x80000023, 0x20, 0x8000001c):
            minimum = 12 if cmd == 0x8000001c else 24
            need(length >= minimum, 'Short path command')
            at = struct.unpack_from('<I', raw, pos+8)[0]
            need(minimum <= at < length, 'Path command offset'); text = raw[pos+at:pos+length]
            need(b'\0' in text, 'Path command unterminated'); path = text.split(b'\0', 1)[0].decode('utf-8')
            if cmd == 0x8000001c:
                rpaths.append(path)
            else:
                deps.append(dict(path=path, weak=cmd == 0x80000018, command=hex(cmd)))
        pos += length
    need(pos == 32+size, 'Trailing command bytes')
    return dict(dependencies=deps, rpaths=rpaths, cpu=hex(cpu), subtype=subtype, filetype=kind)


class CacheSet:
    def __init__(self, path):
        self.readers = []; self.files = []; self.mappings = []; self.images = {}
        try:
            self._load(Path(path))
        except BaseException:
            self.close(); raise

    def _file(self, path):
        r = Reader(path); self.readers.append(r); h = header(r)
        self.files.append(dict(name=path.name, bytes=r.size, **h))
        self.mappings.extend(dict(reader=r, **m) for m in h['mappings'])
        return r, h

    def _load(self, path):
        main, info = self._file(path); self.subcaches = subentries(main, info)
        for entry in self.subcaches:
            r, h = self._file(path.with_name(path.name+entry['suffix']))
            need(h['uuid'] == entry['uuid'], 'Subcache UUID mismatch')
            need(h['mappings'][0]['address'] == info['mappings'][0]['address']+entry['vm_offset'], 'Subcache VM offset mismatch')
        ordered = sorted(self.mappings, key=lambda v: v['address'])
        for left, right in zip(ordered, ordered[1:]):
            need(left['address']+left['size'] <= right['address'], 'Overlapping cache VM mappings')
        if info['symbol_uuid'] != '0'*32:
            r = Reader(path.with_name(path.name+'.symbols')); self.readers.append(r)
            head = r.read(0, 104); need(head[:7] == b'dyld_v1' and head[88:104].hex() == info['symbol_uuid'], 'Symbols UUID mismatch')
            self.symbols = dict(name=r.path.name, bytes=r.size, uuid=head[88:104].hex())
        else:
            self.symbols = None
        raw = main.read(info['images_offset'], info['images_count']*32)
        for i in range(info['images_count']):
            address, mtime, inode, pathoff, pad = struct.unpack_from('<QQQII', raw, i*32)
            name = main.cstring(pathoff); need(name.startswith('/') and name not in self.images, 'Invalid/duplicate cached image path')
            self.images[name] = address
            self.vmread(address, 4)  # Every indexed header must be backed by the selected set.

    def vmread(self, address, size):
        result = bytearray()
        while size:
            matches = [m for m in self.mappings if m['address'] <= address < m['address']+m['size']]
            need(len(matches) == 1, 'Unbacked/ambiguous cache VM address'); m = matches[0]
            length = min(size, m['address']+m['size']-address)
            result.extend(m['reader'].read(m['offset']+address-m['address'], length)); address += length; size -= length
        return bytes(result)

    def dependencies(self, path):
        address = self.images[path]; head = self.vmread(address, 32)
        commands = struct.unpack_from('<I', head, 20)[0]; need(commands <= 1024*1024, 'Mach-O command size')
        return macho_dependencies(self.vmread(address, 32+commands))

    def report(self):
        return dict(files=self.files, subcaches=self.subcaches, symbols=self.symbols,
                    images=[dict(path=p, address=hex(a)) for p, a in sorted(self.images.items())],
                    reads=[dict(name=r.path.name, reads=r.reads, ordered_read_sha256=r.digest.hexdigest()) for r in self.readers])

    def close(self):
        for r in self.readers:
            r.file.close()
