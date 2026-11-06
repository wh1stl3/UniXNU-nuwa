"""Mixed-codec UDIF fixture and bounded decoder negative controls."""
import argparse, bz2, hashlib, json, plistlib, struct, tempfile, zlib
from pathlib import Path
import udif_raw_decode as U
ROOT = Path(__file__).resolve().parents[1]


def fixture(path, decoder, bad_kind=False, gap=False):
    values = [(0,bytes(512)),(1,b'R'*512),(0x80000005,b'Z'*512),(0x80000006,b'B'*512),(0x80000007,b'L'*512),(2,bytes(512))]
    data = bytearray(); entries = []; expected = bytearray()
    for i,(kind,raw) in enumerate(values):
        payload = b'' if kind in (0,2) else raw if kind == 1 else zlib.compress(raw) if kind == 0x80000005 else bz2.compress(raw) if kind == 0x80000006 else decoder.encode_fixture(raw)
        entries.append(struct.pack('>IIQQQQ',99 if bad_kind and i==0 else kind,0,i+(1 if gap else 0),1,len(data),len(payload)))
        data.extend(payload); expected.extend(raw)
    mish = bytearray(204); mish[:4] = b'mish'; struct.pack_into('>I',mish,200,len(entries))
    metadata = plistlib.dumps({'resource-fork':{'blkx':[{'Data':bytes(mish)+b''.join(entries)}]}})
    trailer = bytearray(512); trailer[:4] = b'koly'; struct.pack_into('>II',trailer,4,4,512); struct.pack_into('>QQ',trailer,24,0,len(data)); struct.pack_into('>QQ',trailer,216,len(data),len(metadata)); struct.pack_into('>Q',trailer,492,len(values)+(1 if gap else 0))
    path.write_bytes(data+metadata+trailer); return bytes(expected)


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--library',type=Path,required=True); p.add_argument('--output',type=Path,required=True); a = p.parse_args()
    U.D.need(not a.output.exists() and a.output.resolve().is_relative_to(ROOT/'reports'),'Fresh report required'); decoder = U.Lzfse(a.library.resolve()); checks = []
    def accept(name): checks.append(dict(name=name,passed=True))
    def reject(name,action):
        try: action()
        except ValueError: accept(name)
        else: raise AssertionError(name+' accepted')
    assert U.evidence_path('reports\\desktop-readiness\\audit.json') == 'reports/desktop-readiness/audit.json'; accept('Windows/POSIX relative evidence separators')
    reject('unsafe relative evidence path rejected',lambda:U.evidence_path('../audit.json'))
    payload = decoder.encode_fixture(b'ABCD'*16384)
    assert decoder.decode(payload,65536) == b'ABCD'*16384; accept('LZFSE roundtrip')
    reject('undersized declared output rejected',lambda:decoder.decode(payload,65535))
    reject('oversized declared output rejected',lambda:decoder.decode(payload,65537))
    reject('truncated LZFSE rejected',lambda:decoder.decode(payload[:-8],65536))
    reject('decoder resource bound enforced',lambda:decoder.decode(payload,U.MAX_CHUNK+1))
    for kind,encoded in ((0x80000005,zlib.compress(b'z'*512)),(0x80000006,bz2.compress(b'z'*512))):
        reject('stream suffix rejected '+hex(kind),lambda kind=kind,encoded=encoded:U.compressed(kind,encoded+b'suffix',512,decoder))
    with tempfile.TemporaryDirectory(prefix='nuwa-udif-') as folder:
        folder = Path(folder); image = folder/'fixture.dmg'; dest = folder/'raw.img'; expected = fixture(image,decoder)
        source = image.read_bytes(); result = U.decode_to_file(image,dest,decoder)
        assert dest.read_bytes() == expected and result['raw_sha256'] == hashlib.sha256(expected).hexdigest() and result['chunk_readback_passed']; accept('all six chunk kinds with actual per-chunk/file readback')
        assert image.read_bytes() == source; accept('original fixture bytes unchanged')
        reject('existing output rejected',lambda:U.decode_to_file(image,dest,decoder))
        fixture(image,decoder,bad_kind=True); reject('unsupported chunk rejected before output',lambda:U.decode_to_file(image,folder/'bad.img',decoder))
        fixture(image,decoder,gap=True); reject('logical gap rejected before output',lambda:U.decode_to_file(image,folder/'gap.img',decoder))
    report = dict(checks=checks,library_sha256=hashlib.sha256(a.library.read_bytes()).hexdigest(),sources=[dict(path='scripts/'+name,sha256=hashlib.sha256((ROOT/'scripts'/name).read_bytes()).hexdigest()) for name in ('udif_raw_decode.py','test-udif-raw-decode.py','desktop_root_contract.py')],device_accessed=False)
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_bytes(json.dumps(report,indent=2).encode()+b'\n'); print(json.dumps(dict(checks=len(checks),passed=True)))


if __name__ == '__main__': main()
