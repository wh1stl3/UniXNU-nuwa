#!/usr/bin/env python3
"""Fail-closed, bounded final AMNM branch binder; no Mach-O expansion."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys

HERE = Path(__file__).resolve().parent

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def digest(raw): return hashlib.sha256(raw).hexdigest()

def all_symbols(image):
    raw = image.raw
    symbols = {}
    for cmd, at, size in image.image['commands']:
        if cmd != 2: continue
        symoff, count, stroff, strsize = struct.unpack_from('<4I', raw, at+8)
        for index in range(count):
            string, typ, sect, desc, val = struct.unpack_from('<IBBHQ', raw, symoff+index*16)
            if typ & 0xe0 or not string: continue
            if typ & 0xe not in (2, 0xe): continue
            name = raw[stroff+string:raw.index(b'\0', stroff+string)].decode()
            if name in symbols and symbols[name] != val:
                symbols[name] = None
            elif name not in symbols:
                symbols[name] = val
    return symbols

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build-result', type=Path, required=True)
    p.add_argument('--prelink-result', type=Path, required=True)
    p.add_argument('--first-discovery', type=Path, required=True)
    p.add_argument('--final-discovery', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    build = json.loads(args.build_result.read_text())
    prelink = json.loads(args.prelink_result.read_text())
    first = json.loads(args.first_discovery.read_text())
    final = json.loads(args.final_discovery.read_text())
    assert build['stages']['kernel']['exit'] == prelink['exit'] == 0
    assert first['sites'] == final['sites'] and first['original_words'] == final['original_words'], 'discovered bindings moved'
    assert prelink['prelink']['sha256'] == final['prelink']['sha256']
    source = Path(prelink['prelink']['path'])
    raw = source.read_bytes()
    assert digest(raw) == prelink['prelink']['sha256']
    reader = load(Path(build['work'])/'tree/kits/XnuPrelink/native_prelink.py', 'reader')
    diag = load(HERE/'build-nuwa-pmap-ret-diagnostic.py', 'diagnostic')
    image = diag.Image(reader, raw)
    symbols = all_symbols(image)
    sites = {k:int(v,16) for k,v in final['sites'].items()}
    bindings = {'_amnm_input_continue': sites['input']+4,
                '_amnm_store_continue': sites['store']+4,
                '_amnm_branch_zero': sites['branch_zero'],
                '_amnm_branch_nonzero': sites['branch_nonzero'],
                '_amnm_entry_continue': sites['entry']+4,
                '_amnm_precall_continue': sites['precall_blr'],
                '_amnm_precall_return': sites['return'],
                '_amnm_return_binding': sites['return'],
                '_amnm_reader_binding': sites['reader'],
                '_amnm_flag_binding': sites['flag']}
    for name, value in bindings.items(): assert symbols[name] == value, name
    assert image.word(sites['precall_blr']) == 0xd63f0100
    words = {'entry':0xd10643ff, 'precall_mov':0xaa1503e1,
             'input':0x7100011f, 'store':0x39000268, 'branch':int(final['original_words']['branch'],16)}
    targets = {'entry':'_amnm_entry_hook', 'precall_mov':'_amnm_precall_hook',
               'input':'_amnm_input_hook', 'store':'_amnm_store_hook', 'branch':'_amnm_branch_hook'}
    for name in targets.values(): image.span(symbols[name], 4, 5)
    # Verify each observer's final branch really resolves to its bound continuation.
    branch_checks = {'_amnm_input_hook':[(0xf4, bindings['_amnm_input_continue'])],
                     '_amnm_store_hook':[(0xf4, bindings['_amnm_store_continue'])],
                     '_amnm_branch_hook':[(0xe4, bindings['_amnm_branch_nonzero']), (0xe8, bindings['_amnm_branch_zero'])],
                     '_amnm_entry_hook':[(0xe0, bindings['_amnm_entry_continue'])],
                     '_amnm_precall_hook':[(0xf8, bindings['_amnm_precall_continue'])]}
    for name, checks in branch_checks.items():
        for offset, dest in checks:
            at = symbols[name]+offset
            assert image.word(at) == diag.branch(at,dest), (name, hex(at))
    assert image.word(symbols['_amnm_precall_hook']+0xf4) == 0xaa1503e1
    assert image.word(symbols['_amnm_input_hook']+0xf0) == 0x7100011f
    assert image.word(symbols['_amnm_store_hook']+0x5c) == 0x39000268
    assert image.word(symbols['_amnm_branch_hook']+0xe0) == 0x34000048
    log = symbols['_amnm_observer_log']
    log_segment, = [seg for seg in image.image['segments'] if seg['va'] <= log and log+1920 <= seg['va']+seg['size']]
    assert log_segment['name'] == '__DATA' and log_segment['initprot'] == 3 and log_segment['maxprot'] == 3
    assert log >= log_segment['va']+log_segment['filesize'], 'log needs independent zero-init proof'
    # Both panic paths preserve the existing ordinary/common entry shims.
    for name in ('_panic', '_panic_trap_to_debugger', '_panic_screen', '_panic_screen_common'):
        image.span(symbols[name],4,5)
    assert image.word(symbols['_panic_screen']) == 0x910003e1
    assert image.word(symbols['_panic_screen_common']) == 0xf9400021
    candidate = bytearray(raw)
    changes = []
    for name, symbol in targets.items():
        site = sites[name]
        assert image.word(site) == words[name], name
        encoded = diag.branch(site, symbols[symbol])
        off = image.offset(site,4)
        struct.pack_into('<I', candidate, off, encoded)
        changes.append({'name':name, 'site':hex(site), 'file_offset':hex(off),
                        'old':hex(words[name]), 'new':hex(encoded), 'target':hex(symbols[symbol])})
    for name, target in (('_panic','_panic_screen'),('_panic_trap_to_debugger','_panic_screen_common')):
        site = symbols[name]
        old = image.word(site)
        assert old not in (0, 0xffffffff)
        encoded = diag.branch(site, symbols[target])
        off = image.offset(site,4)
        assert all(c['file_offset'] != hex(off) for c in changes)
        struct.pack_into('<I', candidate, off, encoded)
        changes.append({'name':name, 'site':hex(site), 'file_offset':hex(off),
                        'old':hex(old), 'new':hex(encoded), 'target':hex(symbols[target])})
    assert len(candidate) == len(raw)
    allowed = {int(c['file_offset'],16)+i for c in changes for i in range(4)}
    assert all(i in allowed for i,(a,b) in enumerate(zip(raw,candidate)) if a != b)
    args.out.mkdir(exist_ok=False)
    path = args.out/'kernel-amnm.macho'
    path.write_bytes(candidate)
    manifest = {'status':'self-checked, not device approved', 'source':prelink['prelink'],
                'candidate':{'path':str(path), 'bytes':len(candidate), 'sha256':digest(candidate)},
                'binding':{k:hex(v) for k,v in bindings.items()}, 'changes':changes,
                'log':{'address':hex(log), 'bytes':1920, 'segment':log_segment['name'], 'initial':'zero-fill expected'},
                'notes':['No claim of runtime LSE or mapping behavior', 'No claim of final device acceptance']}
    (args.out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest,indent=2))

if __name__ == '__main__': main()
