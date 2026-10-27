"""Universal slice selection and malformed-extent controls."""
import argparse, hashlib, json, struct
from pathlib import Path
import desktop_service_macho as M
ROOT = Path(__file__).resolve().parents[1]


def thin(sub=0):
    return struct.pack('<8I',0xfeedfacf,0x100000c,sub,2,0,0,0,0)


def fat(subs=(2,0)):
    raw = bytearray(0x1000*(len(subs)+1)); struct.pack_into('>II',raw,0,0xcafebabe,len(subs))
    for i,sub in enumerate(subs):
        off = (i+1)*0x1000; struct.pack_into('>5I',raw,8+i*20,0x100000c,sub,off,32,12); raw[off:off+32] = thin(sub)
    return raw


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output',type=Path,required=True); a = p.parse_args()
    M.need(not a.output.exists() and a.output.resolve().is_relative_to(ROOT/'reports'),'Fresh report required'); checks = []
    def accept(name):
        checks.append(dict(name=name,passed=True))
    def reject(name,raw):
        try:
            M.inspect(raw)
        except ValueError:
            accept(name)
        else:
            raise AssertionError(name+' accepted')
    assert M.inspect(thin())['selected']['subtype'] == 0; accept('thin ARM64-all')
    assert M.inspect(fat())['selected']['subtype'] == 0; accept('universal selects ARM64-all over earlier ARM64e')
    assert M.inspect(fat((2,)))['selected'] is None; accept('no ARM64e fallback')
    raw = fat(); struct.pack_into('>I',raw,16,len(raw)); reject('slice extent rejected',raw)
    raw = fat(); struct.pack_into('>I',raw,16,0x1001); reject('slice alignment rejected',raw)
    raw = fat(); struct.pack_into('>I',raw,28,0x1000007); struct.pack_into('>I',raw,36,0x1000); reject('overlapping slices rejected',raw)
    reject('duplicate architectures rejected',fat((0,0)))
    raw = bytearray(8192); struct.pack_into('>II',raw,0,0xcafebabf,1)
    struct.pack_into('>IIQQII',raw,8,0x100000c,0,4096,32,12,0); raw[4096:4128] = thin()
    assert M.inspect(raw)['selected']['offset'] == 4096; accept('64-bit universal table')
    assert M.inspect(b'#!/bin/sh\nexit 0\n')['selected'] is None; accept('unhandled format remains unqualified')
    report = dict(checks=checks,sources=[dict(path='scripts/'+name,sha256=hashlib.sha256((ROOT/'scripts'/name).read_bytes()).hexdigest()) for name in ('desktop_service_macho.py','test-desktop-service-macho.py','desktop_cache.py')],device_accessed=False)
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_bytes(json.dumps(report,indent=2).encode()+b'\n'); print(json.dumps(dict(checks=len(checks),passed=True)))


if __name__ == '__main__':
    main()
