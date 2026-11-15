#!/usr/bin/env python3
"""Re-read final AMNM image and fail closed on binding or byte mismatches."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

HERE = Path(__file__).resolve().parent
def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
def sha(raw): return hashlib.sha256(raw).hexdigest()

def check_zero_objects(image, symbols):
    """Validate complete object extents, not just their starting addresses."""
    objects = [('_amnm_observer_log', 1920), ('_amnm_local_panic_text', 2048),
               ('_amnm_panic_winner', 4)]
    boot_segments = [s for s in image.image['segments'] if s['name'] == '__BOOTDATA']
    assert len(boot_segments) == 1, 'missing or ambiguous __BOOTDATA'
    boot = boot_segments[0]
    spans = []
    for name, length in objects:
        start = symbols[name]
        assert isinstance(start, int) and 0 <= start < start + length <= 1 << 64, name
        end = start + length
        segments = [s for s in image.image['segments'] if s['va'] <= start and end <= s['va'] + s['size']]
        assert len(segments) == 1, name + ': segment extent'
        seg = segments[0]
        assert seg['name'] == '__DATA' and seg['initprot'] == seg['maxprot'] == 3, name + ': RW/NX'
        assert start >= seg['va'] + seg['filesize'], name + ': file-backed'
        assert end <= boot['va'] or start >= boot['va'] + boot['size'], name + ': BOOTDATA'
        sections = [s for s in seg['sections'] if s['va'] <= start and end <= s['va'] + s['size']]
        assert len(sections) == 1, name + ': section extent'
        section = sections[0]
        flags = struct.unpack_from('<I', image.raw, section['command_offset'] + 64)[0]
        assert flags & 0xff == 1, name + ': not S_ZEROFILL'
        spans.append({'symbol': name, 'va': hex(start), 'end': hex(end), 'bytes': length,
                      'segment': seg['name'], 'section': section['name'],
                      'initprot': seg['initprot'], 'maxprot': seg['maxprot'],
                      'initial': 'zero-fill', 'section_type': hex(flags & 0xff)})
    ordered = sorted(spans, key=lambda item: int(item['va'], 16))
    for left, right in zip(ordered, ordered[1:]):
        assert int(left['end'], 16) <= int(right['va'], 16), 'AMNM zero-fill objects overlap'
    return spans

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build-result', type=Path, required=True)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    build = json.loads(a.build_result.read_text()); manifest = json.loads(a.manifest.read_text())
    raw = Path(manifest['candidate']['path']).read_bytes()
    before = Path(manifest['source']['path']).read_bytes()
    assert sha(raw) == manifest['candidate']['sha256'] and sha(before) == manifest['source']['sha256']
    assert len(raw) == len(before)
    reader = load(Path(build['work'])/'tree/kits/XnuPrelink/native_prelink.py', 'reader')
    diag = load(HERE/'build-nuwa-pmap-ret-diagnostic.py', 'diag')
    binder = load(HERE/'bind-amnm-final.py', 'binder')
    image = diag.Image(reader, raw); original = diag.Image(reader, before); symbols = binder.all_symbols(image)
    allowed = set()
    for event in manifest['changes']:
        at, dest, off = int(event['site'],16), int(event['target'],16), int(event['file_offset'],16)
        assert image.offset(at,4) == off
        assert struct.unpack_from('<I',before,off)[0] == int(event['old'],16)
        assert image.word(at) == int(event['new'],16) == diag.branch(at,dest)
        image.span(at,4,5); image.span(dest,4,5)
        assert not (allowed & set(range(off,off+4)))
        allowed.update(range(off,off+4))
    changed = [i for i,(x,y) in enumerate(zip(before,raw)) if x != y]
    assert set(changed) <= allowed
    for name,val in manifest['binding'].items(): assert symbols[name] == int(val,16), name
    assert image.word(int(manifest['binding']['_amnm_precall_continue'],16)) == 0xd63f0100
    checks = {'_amnm_input_hook': [(0xf0,0x7100011f)],
              '_amnm_store_hook': [(0x5c,0x39000268)],
              '_amnm_branch_hook': [(0xe0,0x34000048)],
              '_amnm_entry_hook': [(0xdc,0xd10643ff)],
              '_amnm_precall_hook': [(0xf4,0xaa1503e1)]}
    for name, expected in checks.items():
        for off,word in expected: assert image.word(symbols[name]+off) == word, name
        # Each hook's first global operation is the actual LDADDAL opcode.
        assert image.word(symbols[name]+0x58) == 0xf8ea012b
    assert image.word(symbols['_panic_screen']) == 0x910003e1
    assert image.word(symbols['_panic_screen_common']) == 0xf9400021
    binding = {k:int(v,16) for k,v in manifest['binding'].items()}
    # Decode the linked ADRP+ADD, rather than trusting absolute symbol records.
    def adrp_add(at, register):
        adrp, add = image.word(at), image.word(at+4)
        assert adrp & 0x9f00001f == 0x90000000 | register
        assert add & 0xffc003ff == 0x91000000 | (register<<5) | register
        displacement = diag.A.signed((((adrp>>5)&0x7ffff)<<2)|((adrp>>29)&3), 21)<<12
        return (at & ~4095) + displacement + ((add>>10)&0xfff)
    for symbol in checks:
        assert adrp_add(symbols[symbol]+0x4c,9) == symbols['_amnm_observer_log']
    assert adrp_add(symbols['_amnm_precall_hook']+0x94,13) == binding['_amnm_precall_return']
    for symbol, offset in [('_amnm_input_hook',0xa0),('_amnm_store_hook',0xa4),
                           ('_amnm_branch_hook',0x90),('_amnm_entry_hook',0x8c),
                           ('_amnm_precall_hook',0xa4)]:
        assert image.word(symbols[symbol]+offset) == 0xc89ffd8b
    entry = next(int(c['site'],16) for c in manifest['changes'] if c['name'] == 'entry')
    assert original.word(entry) == 0xd10643ff
    assert original.word(entry+0x18) == 0xa9187bfd
    assert original.word(entry+0x1c) == 0x910603fd
    reader_entry = binding['_amnm_reader_binding']
    assert [original.word(reader_entry+x) for x in (0,12,16,20,24)] == [
        0xd10103ff,0xa9037bfd,0x9100c3fd,0xaa0303f3,0xaa0203f5]
    for symbol, off, target in [('_amnm_input_hook',0xf4,'_amnm_input_continue'),
        ('_amnm_store_hook',0xf4,'_amnm_store_continue'),
        ('_amnm_branch_hook',0xe4,'_amnm_branch_nonzero'),
        ('_amnm_branch_hook',0xe8,'_amnm_branch_zero'),
        ('_amnm_entry_hook',0xe0,'_amnm_entry_continue'),
        ('_amnm_precall_hook',0xf8,'_amnm_precall_continue')]:
        site = symbols[symbol]+off
        assert image.word(site) == diag.branch(site,binding[target])
    log, panic_log, winner = check_zero_objects(image, symbols)
    map_path = Path(build['link_map']['path'])
    map_raw = map_path.read_bytes()
    assert sha(map_raw) == build['link_map']['sha256']
    assert b'amnm-stage1-bindings.o' not in map_raw
    assert b'amnm-stage2-bindings.o' in map_raw
    report = {'status':'self-checked, not independently verified or device approved',
              'candidate':manifest['candidate'], 'changed_bytes':len(changed),
              'patched_instructions':len(manifest['changes']),
              'log':log, 'panic_text':panic_log, 'winner':winner,
              'limitations':['Runtime mapping/lifetime and LSE execution are not established',
                             'Renderer uses a local 2048-byte panic buffer; boot-progress banner integration not established',
                             'Stage-two prelink source record conservatively says trap placeholders; archive map was checked instead']}
    a.out.mkdir(exist_ok=False)
    (a.out/'audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__ == '__main__': main()
