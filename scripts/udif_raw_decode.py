"""Bounded UDIF chunk decoding to fresh host files; no root manifest or device IO."""
import bz2, ctypes, hashlib, os, plistlib, struct, zlib
from pathlib import Path
import desktop_root_contract as D
MAX_CHUNK = 64*1024*1024
BUFFER = 4*1024*1024


def evidence_path(value):
    D.need(isinstance(value,str),'Evidence path type')
    value = value.replace('\\','/')
    D.need(value and all(part not in ('','.','..') and ':' not in part for part in value.split('/')),'Relative evidence path required')
    return value


class Lzfse:
    def __init__(self, path):
        self.path = Path(path); self.lib = ctypes.CDLL(str(self.path))
        for name in ('lzfse_decode_buffer','lzfse_encode_buffer'):
            call = getattr(self.lib,name); call.argtypes = [ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p]; call.restype = ctypes.c_size_t
        self.lib.lzfse_decode_scratch_size.restype = ctypes.c_size_t
        size = self.lib.lzfse_decode_scratch_size(); D.need(size <= 16*1024*1024,'LZFSE scratch limit')
        self.scratch = ctypes.create_string_buffer(max(size,1))

    def decode(self, data, expected):
        D.need(data and len(data) <= MAX_CHUNK and 0 < expected <= MAX_CHUNK,'LZFSE chunk bound')
        source = ctypes.create_string_buffer(data); output = ctypes.create_string_buffer(expected+1)
        count = self.lib.lzfse_decode_buffer(output,expected+1,source,len(data),self.scratch)
        D.need(count == expected,'LZFSE decoded length/error')
        return output.raw[:count]

    def encode_fixture(self, data):
        D.need(0 < len(data) <= MAX_CHUNK,'Fixture bound')
        source = ctypes.create_string_buffer(data); output = ctypes.create_string_buffer(len(data)*2+4096)
        count = self.lib.lzfse_encode_buffer(output,len(output),source,len(data),None)
        D.need(count > 0,'Fixture encoding failed'); return output.raw[:count]


def plan(path):
    info = D.geometry(path); D.need(info['format'] == 'UDIF','UDIF source required')
    with path.open('rb') as source:
        source.seek(-512,2); trailer = source.read(512)
        fork, = struct.unpack_from('>Q',trailer,24); at,n = struct.unpack_from('>QQ',trailer,216)
        source.seek(at); meta = plistlib.loads(source.read(n))
    result = []
    for table in meta['resource-fork']['blkx']:
        raw = table['Data']; first, = struct.unpack_from('>Q',raw,8); base, = struct.unpack_from('>Q',raw,24); count, = struct.unpack_from('>I',raw,200)
        for i in range(count):
            kind,reserved,sector,length,offset,stored = struct.unpack_from('>IIQQQQ',raw,204+i*40)
            if kind in (0x7ffffffe,0xffffffff):
                continue
            if kind in (0x80000005,0x80000006,0x80000007):
                D.need(length*512 <= MAX_CHUNK and stored <= MAX_CHUNK,'Compressed chunk resource limit')
            result.append(dict(start=(first+sector)*512,bytes=length*512,kind=kind,source_offset=fork+base+offset,stored_bytes=stored))
    result.sort(key=lambda v:v['start']); D.need(len(result) == info['chunks'],'Chunk inventory differs')
    return info,result


def compressed(kind, payload, expected, decoder):
    D.need(0 < expected <= MAX_CHUNK and len(payload) <= MAX_CHUNK,'Compressed resource bound')
    if kind == 0x80000007:
        return decoder.decode(payload,expected)
    if kind == 0x80000005:
        obj = zlib.decompressobj(); data = obj.decompress(payload,expected+1)
        D.need(obj.eof and not obj.unused_data and not obj.unconsumed_tail,'Zlib stream boundary')
    elif kind == 0x80000006:
        obj = bz2.BZ2Decompressor(); data = obj.decompress(payload,max_length=expected+1)
        D.need(obj.eof and not obj.unused_data,'Bzip2 stream boundary')
    else:
        raise ValueError('Unsupported compressed kind')
    D.need(len(data) == expected,'Decoded chunk length differs'); return data


def decode_to_file(source_path, destination, decoder, progress=None):
    D.need(not destination.exists(),'Fresh raw file required')
    info,chunks = plan(source_path); records = []; stream = hashlib.sha256(); zeros = bytes(BUFFER)
    with source_path.open('rb') as source, destination.open('xb') as output:
        for i,chunk in enumerate(chunks):
            D.need(output.tell() == chunk['start'],'Output position differs'); digest = hashlib.sha256(); stored_digest = hashlib.sha256()
            def write(data):
                D.need(output.write(data) == len(data),'Short output write'); digest.update(data); stream.update(data)
            kind = chunk['kind']; remaining = chunk['bytes']
            if kind in (0,2):
                while remaining:
                    data = zeros[:min(remaining,BUFFER)]; write(data); remaining -= len(data)
            elif kind == 1:
                source.seek(chunk['source_offset'])
                while remaining:
                    data = source.read(min(remaining,BUFFER)); D.need(data,'Truncated raw chunk')
                    stored_digest.update(data); write(data); remaining -= len(data)
            else:
                source.seek(chunk['source_offset']); payload = source.read(chunk['stored_bytes'])
                D.need(len(payload) == chunk['stored_bytes'],'Truncated compressed chunk'); stored_digest.update(payload)
                write(compressed(kind,payload,chunk['bytes'],decoder))
            records.append(dict(**chunk,raw_sha256=digest.hexdigest(),stored_sha256=stored_digest.hexdigest() if kind not in (0,2) else None))
            if progress and (i % 256 == 0 or i+1 == len(chunks)):
                progress(dict(chunks_done=i+1,chunks_total=len(chunks),raw_bytes_written=output.tell()))
        D.need(output.tell() == info['raw_bytes'],'Raw disk size differs'); output.flush(); os.fsync(output.fileno())
    reread = hashlib.sha256()
    with destination.open('rb') as raw:
        for record in records:
            digest = hashlib.sha256(); remaining = record['bytes']
            while remaining:
                data = raw.read(min(remaining,BUFFER)); D.need(data,'Raw readback truncated')
                digest.update(data); reread.update(data); remaining -= len(data)
            D.need(digest.hexdigest() == record['raw_sha256'],'Raw chunk readback differs')
        D.need(not raw.read(1),'Unexpected raw suffix')
    D.need(reread.hexdigest() == stream.hexdigest(),'Raw disk digest differs')
    return dict(geometry=info,chunks=records,raw_bytes=destination.stat().st_size,raw_sha256=reread.hexdigest(),chunk_readback_passed=True,
                decode_library_sha256=hashlib.sha256(decoder.path.read_bytes()).hexdigest(),device_accessed=False,
                limitations=['Host decode/readback only; not APFS mount, authentication, target storage or native execution'])
