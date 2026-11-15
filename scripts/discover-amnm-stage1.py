#!/usr/bin/env python3
"""Discover AMNM patch points from this run's stage-one prelink, without editing it."""
import hashlib
import argparse
import importlib.util
import json
from pathlib import Path
import struct
import sys

HERE = Path(__file__).resolve().parent
ROOT = Path('/root/nuwa-amnm-binding-stage1-prelink-20261111')
BUILD = Path('/root/nuwa-amnm-stage1-20261111/native/build-result.json')
OUT = Path('/root/nuwa-amnm-binding-discovery-20261111')

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def unique(seq):
    assert len(seq) == 1, seq
    return seq[0]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prelink-result', type=Path, default=ROOT/'result.json')
    parser.add_argument('--build-result', type=Path, default=BUILD)
    parser.add_argument('--out', type=Path, default=OUT)
    options = parser.parse_args()
    stage = json.loads(options.prelink_result.read_text())
    record = json.loads(options.build_result.read_text())
    path = Path(stage['prelink']['path'])
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == stage['prelink']['sha256']
    reader = load(Path(record['work'])/'tree/kits/XnuPrelink/native_prelink.py', 'native_reader')
    diag = load(HERE/'build-nuwa-pmap-ret-diagnostic.py', 'diagnostic')
    image = diag.Image(reader, raw)
    pmap = diag.discover_pmap(image)
    runtime = pmap['runtime']
    darwin = struct.unpack('<Q', image.read(runtime+0x58, 8))[0]
    callee = struct.unpack('<Q', image.read(darwin+0x38, 8))[0]
    start, end = pmap['initializer'], pmap['end']
    assert image.word(start) == 0xd10643ff
    # Full instruction neighborhood, not merely an address pin.
    prefix = (0xf9401e68, ) # LDR x8,[x19,#56]
    call = unique([a for a in range(start+16, end-4, 4)
                   if image.word(a) == 0xaa1503e1 and image.word(a+4) == 0xd63f0100
                   and image.word(a-4) == 0xaa1303e0 and image.word(a-16) == prefix[0]])
    # Recover the ADRP+ADD and post-indexed STR of the actual x3 output.
    adrp_at = call-32
    adrp, add = image.word(adrp_at), image.word(adrp_at+4)
    assert (adrp & 0x9f00001f) == 0x90000003
    assert (add & 0xffc003ff) == 0x91000063
    page = (adrp_at & ~4095) + (diag.A.signed((((adrp>>5)&0x7ffff)<<2)|((adrp>>29)&3), 21)<<12)
    before_postindex = page + ((add>>10)&0xfff)
    assert image.word(call-20) == 0xf8038468 # STR x8,[x3],#56
    flag = before_postindex + 56
    # Reader observations must be uniquely bounded by this known runtime target.
    input_site = unique([a for a in range(callee, callee+0x500, 4)
                         if image.word(a) == 0x7100011f and image.word(a-4) == 0xb9400fe8
                         and image.word(a+4) == 0x1a9f17e8])
    store = unique([a for a in range(input_site, input_site+0x50, 4)
                    if image.word(a) == 0x39000268 and image.word(a-4) == 0x1a9f07e8])
    branch_site = unique([a for a in range(start, end-4, 4)
                          if image.word(a) & 0xff00001f == 0x34000008
                          and image.word(a-4) & 0xffc003ff == 0x39400108])
    ldr_at = branch_site-4
    adrp_at2 = branch_site-8
    word = image.word(adrp_at2)
    assert word & 0x9f00001f == 0x90000008
    branch_page = (adrp_at2 & ~4095) + (diag.A.signed((((word>>5)&0x7ffff)<<2)|((word>>29)&3), 21)<<12)
    assert branch_page + ((image.word(ldr_at)>>10)&0xfff) == flag
    cbz = image.word(branch_site)
    zero = branch_site + (diag.A.signed((cbz>>5)&0x7ffff, 19)<<2)
    sites = {'entry': start, 'precall_mov': call, 'precall_blr': call+4,
             'input': input_site, 'store': store, 'branch': branch_site,
             'branch_zero': zero, 'branch_nonzero': branch_site+4,
             'reader': callee, 'flag': flag, 'return': call+8}
    options.out.mkdir(exist_ok=False)
    result = {'status':'self-checked, unbound and non-runnable', 'prelink':stage['prelink'],
              'runtime':hex(runtime), 'darwin':hex(darwin),
              'sites':{k:hex(v) for k,v in sites.items()},
              'original_words':{k:hex(image.word(sites[k])) for k in ('entry','precall_mov','precall_blr','input','store','branch')}}
    (options.out/'discovery.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))

if __name__ == '__main__': main()
