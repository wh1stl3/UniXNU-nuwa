"""Read-only CodeDirectory page integrity and original trust-cache membership.

Formats: XNU8796 cs_blobs.h and dyld-1066.8 dyld_cache_format.h.
This does not validate CMS, external special slots, AMFI policy or execution.
"""
import hashlib
import struct


def need(ok, message):
    if not ok:
        raise ValueError(message)


def trust_entries(bundle):
    need(len(bundle) >= 12, 'Short trust bundle')
    count, first, second = struct.unpack_from('<3I', bundle)
    need(count == 2 and first == 12 and first < second < len(bundle), 'Trust bundle layout')
    result = {}
    for name, begin, end in [('OS', first, second), ('SystemOS', second, len(bundle))]:
        data = bundle[begin:end]
        need(len(data) >= 24, 'Short trust module')
        version, entries = struct.unpack_from('<I16xI', data)
        need(version == 2 and len(data) == 24 + 24*entries, 'Trust module extent/version')
        for i in range(entries):
            entry = data[24+i*24:48+i*24]
            result.setdefault((entry[:20].hex(), entry[20]), []).append(
                dict(module=name, attributes=entry[21:].hex()))
    return result


def signature_extent(stream, size):
    stream.seek(0); head = stream.read(64)
    if head[:7] == b'dyld_v1':
        offset, length = struct.unpack_from('<QQ', head, 0x28)
        return offset, length or size-offset, 'dyld-cache'
    need(len(head) >= 32 and struct.unpack_from('<I', head)[0] == 0xfeedfacf, 'Thin Mach-O required')
    count, extent = struct.unpack_from('<II', head, 16)
    need(count <= 4096 and 32+extent <= size and extent <= 1048576, 'Command bounds')
    stream.seek(32); commands = stream.read(extent); pos = 0; found = []
    for _ in range(count):
        need(pos+8 <= extent, 'Short command')
        cmd, length = struct.unpack_from('<II', commands, pos)
        need(length >= 8 and length % 8 == 0 and pos+length <= extent, 'Command extent')
        if cmd == 0x1d:
            need(length == 16, 'Signature command size')
            found.append(struct.unpack_from('<II', commands, pos+8))
        pos += length
    need(pos == extent and len(found) == 1, 'Unique signature required')
    return *found[0], 'mach-o'


def inspect(stream, size, entries):
    offset, length, kind = signature_extent(stream, size)
    need(0 < offset < size and 12 <= length <= min(size-offset, 64*1024*1024), 'Signature bounds')
    stream.seek(offset); blob = stream.read(length)
    need(len(blob) == length, 'Short signature read')
    magic, total, count = struct.unpack_from('>III', blob)
    need(magic == 0xfade0cc0 and 12 <= total <= length and count <= (total-12)//8, 'Superblob extent')
    children = {}; ranges = []
    for i in range(count):
        slot, at = struct.unpack_from('>II', blob, 12+8*i)
        need(slot not in children and 12+8*count <= at <= total-8, 'Child slot/offset')
        tag, n = struct.unpack_from('>II', blob, at)
        need(8 <= n <= total-at, 'Child extent')
        ranges.append((at, at+n)); children[slot] = (tag, blob[at:at+n])
    for left, right in zip(sorted(ranges), sorted(ranges)[1:]):
        need(left[1] <= right[0], 'Overlapping signature children')
    directories = []
    for slot, (tag, cd) in children.items():
        if tag != 0xfade0c02:
            continue
        need(slot == 0 or 0x1000 <= slot < 0x1005, 'Unexpected CodeDirectory slot')
        need(len(cd) >= 44, 'Short CodeDirectory')
        version, flags, hashes, ident, special, slots, limit = struct.unpack_from('>7I', cd, 8)
        width, algorithm, platform, shift = struct.unpack_from('4B', cd, 36)
        need(0x20000 <= version <= 0x20600 and algorithm in (1, 2, 3, 4), 'Unsupported CodeDirectory')
        need(44 <= ident < len(cd) and b'\0' in cd[ident:], 'Identifier bounds')
        if version >= 0x20100:
            need(len(cd) >= 48 and struct.unpack_from('>I', cd, 44)[0] == 0, 'Unsupported scatter')
        if version >= 0x20300:
            need(len(cd) >= 64, 'Short codeLimit64')
            if limit == 0xffffffff:
                limit = struct.unpack_from('>Q', cd, 56)[0]
        need(shift <= 20 and 0 < limit <= offset, 'Code limit/page size')
        need(width == {1:20, 2:32, 3:20, 4:48}[algorithm], 'Digest width')
        need(hashes-special*width >= 44 and hashes+slots*width <= len(cd), 'Hash table bounds')
        method = {1:'sha1', 2:'sha256', 3:'sha256', 4:'sha384'}[algorithm]
        page = 1 << shift if shift else limit
        need(slots == (limit+page-1)//page, 'Code slot count')
        stream.seek(0)
        for j in range(slots):
            expected = min(page, limit-j*page); data = stream.read(expected)
            need(len(data) == expected, 'Short code read')
            need(hashlib.new(method, data).digest()[:width] == cd[hashes+j*width:hashes+(j+1)*width], f'Code page mismatch {j}')
        embedded = []
        for index in range(1, special+1):
            if index in children:
                need(hashlib.new(method, children[index][1]).digest()[:width] == cd[hashes-index*width:hashes-(index-1)*width], f'Special slot mismatch {index}')
                embedded.append(index)
        cdhash = hashlib.new(method, cd).digest()[:20].hex()
        directories.append(dict(slot=slot, identifier=cd[ident:].split(b'\0', 1)[0].decode(),
            hash_type=algorithm, cdhash=cdhash, flags=hex(flags), platform=platform,
            code_pages=slots, code_limit=limit, page_integrity=True,
            embedded_special_slots_checked=embedded, original_trust_matches=entries.get((cdhash, algorithm), [])))
    need(bool(directories), 'No CodeDirectory')
    return dict(kind=kind, bytes=size, signature_offset=offset, directories=directories,
        original_trust_covered=any(d['original_trust_matches'] for d in directories),
        cms_verified=False, kernel_acceptance=False)
