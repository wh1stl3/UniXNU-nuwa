"""Make and verify an explicit-init RamBlock object; offline analysis only.

Run with WSL Python. LLVM 14 Mach-O cannot globalize symbols with objcopy,
so reassemble compiler output with one .globl directive, then remove automatic
init/term lists. No runtime caller or production build is enabled here.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]
INIT = '__GLOBAL__sub_I_NativeRamBlock.cpp'
REMOVED = {'__DATA,__mod_init_func', '__DATA,__mod_term_func'}

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def inspect(raw):
    if struct.unpack_from('<III', raw) != (0xfeedfacf, 0x100000c, 0):
        raise ValueError('Expected arm64 Mach-O')
    sections = []; symbols = []; at = 32
    for _ in range(struct.unpack_from('<I', raw, 16)[0]):
        cmd, size = struct.unpack_from('<II', raw, at)
        if cmd == 0x19:
            for i in range(struct.unpack_from('<I', raw, at + 64)[0]):
                p = at + 72 + i * 80
                name, seg = (raw[p+x:p+x+16].split(b'\0')[0].decode() for x in (0,16))
                va, length, offset, align, ro, nr, flags = struct.unpack_from('<QQIIIII', raw, p+32)
                sections.append(dict(name=seg+','+name, va=va, size=length, align=align,
                                     flags=flags, offset=offset, ro=ro, nr=nr))
        elif cmd == 2:
            sy, count, st, _ = struct.unpack_from('<4I', raw, at+8)
            for i in range(count):
                ix, kind, sec, desc, value = struct.unpack_from('<IBBHQ', raw, sy+i*16)
                name=raw[st+ix:raw.index(b'\0', st+ix)].decode()
                symbols.append(dict(name=name, kind=kind, sec=sec, desc=desc, value=value))
        at += size
    result = {}
    for s in sections:
        rel=[]
        for i in range(s['nr']):
            address, word=struct.unpack_from('<II', raw, s['ro']+i*8)
            target=word & 0xffffff
            # ARM64_RELOC_ADDEND carries a signed 24-bit addend, not a section.
            if word >> 28 == 10:
                target=('addend', target)
            elif word >> 27 & 1:
                target=('symbol', symbols[target]['name'])
            else:
                target=('section', sections[target-1]['name'] if target else 'absolute')
            rel.append((address, word >> 24, target))
        zero=(s['flags'] & 0xff) in (1,12,18)
        data=b'' if zero else raw[s['offset']:s['offset']+s['size']]
        result[s['name']]=dict(size=s['size'], align=s['align'], flags=s['flags'],
                              sha256=hashlib.sha256(data).hexdigest(), relocations=rel)
    normalized={}
    for s in symbols:
        section=sections[s['sec']-1] if s['sec'] else None
        normalized[s['name']]=(s['kind'], section['name'] if section else None,
                              s['desc'], s['value']-section['va'] if section else s['value'])
    return result, normalized

def verify(before, after, removed=REMOVED):
    a, sa=inspect(before); b, sb=inspect(after)
    if set(a)-set(b) != removed or set(b)-set(a):
        raise ValueError('Unexpected section removal')
    for name in b:
        if a[name] != b[name]:
            raise ValueError('Section bytes/relocations changed: '+name)
    # Symbols are allowed to move in the table; references must still resolve
    # to the same names. Only the explicit initializer changes visibility.
    expected={n:v for n,v in sa.items() if v[1] not in removed}
    kind, section, desc, value=expected[INIT]
    expected[INIT]=(kind | 1, section, desc, value)
    if expected != sb:
        changed=[n for n in set(expected)|set(sb) if expected.get(n)!=sb.get(n)]
        raise ValueError('Unexpected symbol change: '+str(changed))
    return len(b), sum(len(s['relocations']) for s in b.values())

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    out=parser.parse_args().output.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'out'):
        raise ValueError('Fresh out directory required')
    src=ROOT/'reports/desktop-readiness/2026-10-29-ramblock-compile-r2'
    probe=json.loads((src/'probe.json').read_bytes())
    if sha(src/'reference.o')!=probe['object_sha256']:
        raise ValueError('Input object drift')
    for item in probe['headers_and_source']:
        if sha(Path(item['path']))!=item['sha256']:
            raise ValueError('Source/header drift: '+item['path'])
    out.mkdir(parents=True)
    (out/'build-script.py').write_bytes(Path(__file__).read_bytes())
    commands=[]
    def run(cmd):
        i=len(commands); commands.append(cmd)
        r=subprocess.run(cmd,capture_output=True)
        (out/('command-'+str(i)+'.stdout')).write_bytes(r.stdout)
        (out/('command-'+str(i)+'.stderr')).write_bytes(r.stderr)
        (out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
        if r.returncode: raise RuntimeError('Command failed: '+str(i))
    cmd=probe['command'][:]
    pos=cmd.index('-MMD'); cmd=cmd[:pos]+['-S',cmd[cmd.index('-c')+1],'-o',str(out/'original.s')]
    run(cmd)
    (out/'explicit.s').write_bytes((out/'original.s').read_bytes()+('\n.globl '+INIT+'\n').encode())
    run(['/usr/bin/clang','-target','arm64-apple-ios16.0','-c',str(out/'explicit.s'),'-o',str(out/'explicit.o')])
    late=out/'NativeRamBlock.late.o'
    run(['/usr/bin/llvm-objcopy-14','--strip-debug',str(src/'reference.o'),str(out/'baseline.o')])
    run(['/usr/bin/llvm-objcopy-14','--strip-debug']+['--remove-section='+n for n in sorted(REMOVED)]+[str(out/'explicit.o'),str(late)])
    baseline=(out/'baseline.o').read_bytes()
    sections, relocs=verify(baseline,late.read_bytes())
    negatives=[]
    try: verify(baseline,baseline)
    except ValueError as e: negatives.append(dict(case='automatic-init-retained',reason=str(e)))
    else: raise ValueError('Negative accepted')
    altered=bytearray(late.read_bytes()); altered[inspect_offset(late.read_bytes())]^=1
    try: verify(baseline,altered)
    except ValueError as e: negatives.append(dict(case='text-byte-modified',reason=str(e)))
    else: raise ValueError('Negative accepted')
    archive=out/'libNativeRamBlock.late-analysis.a'
    wrapper=ROOT/'package/NativeRamBlockLateInit.cpp'
    wrappercmd=probe['command'][:probe['command'].index('-MMD')]+['-c',str(wrapper),'-o',str(out/'NativeRamBlockLateInit.o')]
    run(wrappercmd)
    wrappersections,_=inspect((out/'NativeRamBlockLateInit.o').read_bytes())
    if any(n in wrappersections for n in REMOVED):
        raise ValueError('Wrapper has automatic initialization')
    (out/'NativeRamBlockLateInit.cpp').write_bytes(wrapper.read_bytes())
    run(['/usr/bin/llvm-objdump-14','--disassemble','--reloc',str(out/'NativeRamBlockLateInit.o')])
    run(['/usr/bin/clang','--version'])
    run(['/usr/bin/llvm-objcopy-14','--version'])
    # Keep address aliases separate: next kernel's link layout must be rebound.
    run(['/usr/bin/llvm-ar-14','rcs',str(archive),str(late),str(out/'NativeRamBlockLateInit.o')])
    run(['/usr/bin/llvm-nm-14','-g',str(archive)])
    report=dict(deployable=False,kernel_linked=False,hardware_executed=False,
        initializer=INIT,source_object_sha256=sha(src/'reference.o'),
        object_sha256=sha(late),archive_sha256=sha(archive),
        wrapper_source_sha256=sha(wrapper),wrapper_object_sha256=sha(out/'NativeRamBlockLateInit.o'),
        retained_sections=sections,retained_relocations=relocs,negative_tests=negatives,
        removed_sections=sorted(REMOVED),unload_supported=False,debug_stripped=True,
        scope='Explicit initializer and registration wrapper. No boot caller, publication, or fixed-address aliases included.',
        blockers=['Production headers/compiler','Serialized caller after original storage registration',
                  'Existing OSKext identity and pre/postModLoad pair','Final link/loader/root/Data qualification'])
    (out/'qualification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

def inspect_offset(raw):
    at=32
    for _ in range(struct.unpack_from('<I',raw,16)[0]):
        cmd,size=struct.unpack_from('<II',raw,at)
        if cmd==0x19:
            for i in range(struct.unpack_from('<I',raw,at+64)[0]):
                p=at+72+i*80
                if raw[p:p+16].split(b'\0')[0]==b'__text':
                    return struct.unpack_from('<I',raw,p+48)[0]
        at+=size
    raise ValueError('No text')

if __name__=='__main__': main()
