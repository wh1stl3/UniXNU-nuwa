"""Malformed load commands, signatures and root confinement regression checks."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import argparse

spec=importlib.util.spec_from_file_location('closure',Path(__file__).with_name('audit-userland-closure.py'))
A=importlib.util.module_from_spec(spec); spec.loader.exec_module(A)

def sample():
    raw=bytearray(512)
    struct.pack_into('<8I',raw,0,0xfeedfacf,0x100000c,0,2,2,96,0,0)
    struct.pack_into('<II16s4Q4I',raw,32,0x19,72,b'__TEXT',0x100000000,4096,0,512,5,5,0,0)
    struct.pack_into('<IIQQ',raw,104,0x80000028,24,128,0)
    return raw

checks=[]
def reject(name,fn):
    try: fn()
    except ValueError: checks.append(dict(name=name,passed=True))
    else: raise AssertionError(name)

good=sample(); assert A.macho(good)['entries'][0]['executable_segment'];checks.append(dict(name='valid-entry',passed=True))
bad=sample();struct.pack_into('<I',bad,36,0xfffffff8);reject('command-overrun',lambda:A.macho(bad))
bad=sample();struct.pack_into('<Q',bad,112,4096);reject('entry-outside-text',lambda:A.macho(bad))
bad=sample();struct.pack_into('<Q',bad,80,513);reject('segment-file-overrun',lambda:A.macho(bad))
bad=sample();struct.pack_into('<I',bad,16,1);reject('trailing-command-bytes',lambda:A.macho(bad))
cd=bytearray(80);struct.pack_into('>9I',cd,0,0xfade0c02,80,0x20001,0,48,44,0,1,512)
struct.pack_into('4B',cd,36,32,2,0,12);cd[44:48]=b'id\0\0';cd[48:]=hashlib.sha256(good).digest()
blob=struct.pack('>5I',0xfade0cc0,100,1,0,20)+cd
signed=good+blob
assert A.signatures(signed,512,100)[0]['page_integrity']=='matched';checks.append(dict(name='page-digest-match',passed=True))
broken=bytearray(signed);broken[128]^=1;reject('corrupt-code-page',lambda:A.signatures(broken,512,100))
broken=bytearray(signed);struct.pack_into('>I',broken,512+20+16,79);reject('hash-table-overrun',lambda:A.signatures(broken,512,100))
with tempfile.TemporaryDirectory(prefix='nuwa-closure-') as temp:
    root=Path(temp);(root/'bin').mkdir();(root/'bin/real').write_text('image')
    (root/'absolute').symlink_to('/bin/real');(root/'relative').symlink_to('bin/real')
    assert A.rooted(root,'/absolute')==root/'bin/real' and A.rooted(root,'/relative')==root/'bin/real'
    checks.append(dict(name='absolute-relative-image-symlink',passed=True))
    (root/'escape').symlink_to('../outside');reject('root-escape',lambda:A.rooted(root,'/escape'))
    (root/'loop').symlink_to('/loop');reject('symlink-loop',lambda:A.rooted(root,'/loop'))
result=dict(checks=checks,passed=True,script_sha256=A.sha(Path(__file__).read_bytes()),audit_script_sha256=A.sha(Path(A.__file__).read_bytes()))
cli=argparse.ArgumentParser();cli.add_argument('--output',type=Path);args=cli.parse_args()
if args.output:
    A.need(not args.output.exists() and args.output.resolve().is_relative_to(A.ROOT/'reports'),'Fresh reports path required')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_bytes(json.dumps(result,indent=2).encode()+b'\n')
print(json.dumps(result))
