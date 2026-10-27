"""Type4 block bounds, corruption and cross-block reconstruction tests."""
import argparse,importlib.util,json,struct,zlib
from pathlib import Path
spec=importlib.util.spec_from_file_location('payloads',Path(__file__).with_name('audit-compressed-payloads.py'))
A=importlib.util.module_from_spec(spec);spec.loader.exec_module(A)

def fixture(literal=False):
    raw=b'A'*65536+b'last-block';header=struct.pack('<IIQ',0x636d7066,4,len(raw))
    parts=[raw[:65536],raw[65536:]]
    blocks=[b'\xff'+p if literal else zlib.compress(p) for p in parts]
    data=bytearray(struct.pack('<I',2));offset=20
    for block in blocks:data+=struct.pack('<II',offset,len(block));offset+=len(block)
    data+=b''.join(blocks);rsrc=bytearray(struct.pack('>4I',16,20+len(data),4+len(data),0)+struct.pack('>I',len(data))+data)
    return header,rsrc,raw

def main():
    cli=argparse.ArgumentParser();cli.add_argument('--output',type=Path,required=True);args=cli.parse_args()
    A.need(args.output.resolve().is_relative_to(A.ROOT/'reports') and not args.output.exists(),'Fresh report required')
    checks=[]
    def reject(name,h,r):
        try:A.decode(h,r)
        except (ValueError,zlib.error):checks.append(dict(name=name,passed=True))
        else:raise AssertionError(name)
    for literal in (False,True):
        h,r,raw=fixture(literal);actual,detail=A.decode(h,r)
        assert actual==raw and len(detail['blocks'])==2
        checks.append(dict(name='literal-roundtrip' if literal else 'zlib-roundtrip',passed=True))
    h,r,raw=fixture()
    inline=struct.pack('<IIQ',0x636d7066,3,len(raw))+zlib.compress(raw)
    assert A.decode(inline,b'')[0]==raw;checks.append(dict(name='inline-type3',passed=True))
    decoded,codec=A.expand_block(zlib.compress(b'hello')+b'wrapper-tail',5)
    assert decoded==b'hello' and codec['unused_suffix_bytes']==12
    checks.append(dict(name='stream-end-with-wrapper-suffix',passed=True))
    reject('truncated-zlib-stream',inline[:-1],b'')
    reject('short-header',h[:15],r)
    bad=bytearray(r);struct.pack_into('>I',bad,0,0xfffffff0);reject('resource-data-overrun',h,bad)
    bad=bytearray(r);struct.pack_into('>I',bad,4,16);reject('management-overlap',h,bad)
    bad=bytearray(r);struct.pack_into('<I',bad,20,3);reject('wrong-block-count',h,bad)
    bad=bytearray(r);struct.pack_into('<I',bad,24,0);reject('block-overlaps-table',h,bad)
    bad=bytearray(r);struct.pack_into('<I',bad,28,65538);reject('oversized-block',h,bad)
    bad=bytearray(r);bad[-1]^=1;reject('checksum-corruption',h,bad)
    bad=bytearray(r);bad[40]=0x22;reject('unknown-block-marker',h,bad)
    bad=bytearray(h);struct.pack_into('<Q',bad,8,len(raw)-1);reject('wrong-expanded-size',bad,r)
    bad=bytearray(r);struct.pack_into('>I',bad,16,1);reject('length-prefix',h,bad)
    parts=[raw[:65536],raw[65536:]]
    for name,offset,n,blocks in (('first-header',0,4096,[0]),('cross-64k',65532,8,[0,1]),('partial-eof',len(raw)-4,16,[1]),('at-eof',len(raw),16,[])):
        data,used=A.read_window(parts,offset,n);assert data==raw[offset:offset+n] and used==blocks
        checks.append(dict(name=name,passed=True))
    result=dict(checks=checks,passed=True,audit_source_sha256=A.sha(Path(A.__file__).read_bytes()),test_source_sha256=A.sha(Path(__file__).read_bytes()),device_accessed=False)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_bytes(json.dumps(result,indent=2).encode()+b'\n');print(json.dumps(dict(checks=len(checks),passed=True)))
if __name__=='__main__':main()
