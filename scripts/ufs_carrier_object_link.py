"""Resolve CI-built arm64 Mach-O objects against the tested nuwa boot carrier.

Link at two translated origins; accept only identical section bytes or aligned
absolute pointers whose value tracks the origin exactly. PC-relative code must
match byte for byte. Restrict every rebased pointer to the donor/carrier maps
or the new sections. No dynamic loader or runtime symbol lookup is assumed.
"""
import argparse
import hashlib
import json
import struct
import subprocess
from pathlib import Path
import flush_trace_inputs as trace

ROOT = trace.R
BIAS = 0xfffffff000000000
BASE = 0x084ec000
DELTA = 0x400000

def linux(path):
    return '/mnt/d/'+path.resolve().as_posix()[3:]

def run(*args):
    result=subprocess.run(['wsl','-d','Ubuntu-22.04','--',*map(str,args)],capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr.replace(b'\0',b'').decode(errors='replace'))
    return result.stdout

def sections(blob):
    count,=struct.unpack_from('<I',blob,16)
    at=32
    found={}
    for _ in range(count):
        cmd,length=struct.unpack_from('<II',blob,at)
        if cmd==0x19:
            n=struct.unpack_from('<I',blob,at+64)[0]
            for i in range(n):
                off=at+72+i*80
                sect,seg,addr,size,fileoff=struct.unpack_from('<16s16sQQI',blob,off)
                key=(seg.rstrip(b'\0').decode(),sect.rstrip(b'\0').decode())
                assert key not in found
                found[key]=(addr,blob[fileoff:fileoff+size] if fileoff else bytes(size))
        at+=length
    return found

def link(carrier, objects, work, linker, entry):
    work.mkdir(parents=True,exist_ok=False)
    macho=trace.builder().macho(carrier)
    symbols=dict(macho['symbols'])
    contract=json.loads((ROOT/'config/ramblock-ios16-link-contract.json').read_bytes())
    symbols.update({k:int(v,16) for k,v in contract['bindings'].items()})
    undefined=set()
    defined=set()
    for obj in objects:
        undefined.update(run('llvm-nm','-u','-j',linux(obj)).decode().splitlines())
        defined.update(run('llvm-nm','--defined-only','-j',linux(obj)).decode().splitlines())
    imports=undefined-defined
    missing=imports-symbols.keys()
    if missing:raise ValueError('Unbound carrier imports: '+str(sorted(missing)))
    products=[]
    for n,delta in enumerate((0,DELTA)):
        source=work/f'imports-{n}.S'
        source.write_text('\n'.join(f'.globl {k}\n{k} = {symbols[k]-BIAS+delta:#x}' for k in sorted(imports))+'\n')
        run('clang','-target','arm64-apple-ios16.0','-c',linux(source),'-o',linux(source.with_suffix('.o')))
        target=work/f'linked-{n}.macho'
        run(linux(linker),'-arch','arm64','-platform_version','ios','16.0','16.0','-no_fixup_chains','-no_uuid',
            '-no_adhoc_codesign','-pagezero_size',hex(BASE+delta),'-e',entry,'-o',linux(target),
            *[linux(p) for p in objects+[source.with_suffix('.o')]])
        products.append(sections(target.read_bytes()))
    first,second=products
    assert first.keys()==second.keys()
    ranges=[(s['va']-BIAS,s['va']-BIAS+s['size']) for s in macho['segments'] if s['size']]
    ranges.extend((a,a+len(data)) for a,data in first.values())
    chunks={}; pointers=0
    for key,(addr,original) in first.items():
        other_addr,other=second[key]
        assert other_addr-addr==DELTA and len(original)==len(other)
        buf=bytearray(original)
        for i in range(0,len(buf),8):
            left,right=original[i:i+8],other[i:i+8]
            if left==right:continue
            old=int.from_bytes(left,'little')
            if (key[1]=='__text' or len(left)!=8 or (addr+i)%8 or int.from_bytes(right,'little')!=old+DELTA
                    or not any(lo<=old<hi for lo,hi in ranges)):
                raise ValueError(f'Unexpected origin-dependent field {key} +{i:#x}: {left.hex()} vs {right.hex()}')
            struct.pack_into('<Q',buf,i,BIAS+old)
            pointers+=1
        chunks[key]=(addr+BIAS,bytes(buf))
    (work/'imports.json').write_text(json.dumps({k:hex(symbols[k]) for k in sorted(imports)},indent=2))
    print('Resolved',len(imports),'imports and',pointers,'absolute pointers')
    return chunks

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--carrier',type=Path,required=True)
    p.add_argument('--object',type=Path,action='append',required=True)
    p.add_argument('--linker',type=Path,required=True)
    p.add_argument('--work',type=Path,required=True)
    p.add_argument('--entry',default='_native_ufs_register_late')
    a=p.parse_args()
    for key,(addr,data) in link(a.carrier.read_bytes(),a.object,a.work,a.linker,a.entry).items():
        print(key,hex(addr),len(data))
