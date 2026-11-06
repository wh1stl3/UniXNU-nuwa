"""Compare shipped PROBE29/30 header initialization; model only, no device access.

The snapshot-loss case is deliberately injected to test what the photographed
fields can prove. It is not evidence that snapshot loss occurred on hardware.
"""
import argparse
import importlib.util
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'out/python-tools'))
import unicorn as U
from unicorn import arm64_const as C
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM

spec = importlib.util.spec_from_file_location('builder', ROOT / 'scripts/build-kernel-entry-probe.py')
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)
FIRST = 0xfffffff00769bf90
FB, ROW, STACK = 0xb8000000, 5760, 0xf00000
MASK = (1 << 64) - 1
FONT = [0xf999f, 0x26227, 0xf1f8f, 0xf1f1f, 0x99f11, 0xf8f1f, 0xf8f9f, 0xf1244,
        0xf9f9f, 0xf9f1f, 0xf9f99, 0xe9e9e, 0xf888f, 0xe999e, 0xf8f8f, 0xf8f88]


def field(u, tag):
    y = 224 + (tag - 0xa022) * 28
    glyphs = []
    for n in range(20):
        bits = 0
        for row in range(5):
            for col in range(4):
                pixel = struct.unpack('<I', u.mem_read(FB + (y + row * 4) * ROW +
                                                      (256 + n * 24 + col * 4) * 4, 4))[0]
                assert pixel in (0, 0xffffffff)
                bits = (bits << 1) | bool(pixel)
        glyphs.append(bits)
    if not any(glyphs):
        return None
    digits = ''.join(f'{FONT.index(g):x}' for g in glyphs)
    assert int(digits[:4], 16) == tag
    return digits[4:].upper()


def inspect(build_path):
    b = json.loads(build_path.read_bytes())
    raw = (ROOT / b['candidate']['path']).read_bytes()
    assert B.sha(raw) == b['candidate']['sha256']
    m = B.macho(raw)
    ps = {k: int(v, 16) for k, v in b['probe']['symbols'].items()}
    start, end = ps['probe_dense_769bf90'], ps['probe_dense_769bf90_replay']
    cs = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
    cs.detail = True
    ins = list(cs.disasm(raw[B.backed(m, start, end-start):B.backed(m, start, end-start)+end-start], start))
    fields = {}
    for n, i in enumerate(ins):
        if i.mnemonic == 'mov' and i.op_str.startswith('x23, #0xa0'):
            tag = i.operands[1].imm
            prior = [x for x in ins[:n] if x.mnemonic == 'adr' and x.op_str.startswith('x15, ')
                     and x.operands[1].imm & MASK == ps['probe_scratch']]
            p = prior[-1].address
            fields[f'{tag:04X}'] = dict(load_snapshot=hex(p), tag_instruction=hex(i.address),
                                       code_page=hex(p & ~4095), y=224+(tag-0xa022)*28)
    assert fields['A036']['code_page'] == fields['A037']['code_page']
    result = dict(build=build_path.relative_to(ROOT).as_posix(), candidate_sha256=B.sha(raw),
                  revision=b['probe_revision'], hook_start=hex(start), replay=hex(end),
                  hook_bytes=end-start, probe_code_bytes=b['probe']['code_bytes'],
                  fields=fields, calls_inside_initialization=[hex(i.address) for i in ins if i.mnemonic in ('bl', 'blr')],
                  instructions=[dict(pc=hex(i.address), bytes=i.bytes.hex(), instruction=i.mnemonic+' '+i.op_str) for i in ins])
    return raw, m, ps, result


def execute(raw, m, ps, info, lose_snapshot=False):
    u = U.Uc(U.UC_ARCH_ARM64, U.UC_MODE_ARM)
    base = min(s['va'] for s in m['segments'] if s['size'])
    end = max(s['va']+s['size'] for s in m['segments'])
    u.mem_map(base, B.align(end-base))
    u.mem_map(STACK, 0x10000)
    u.mem_map(FB, 0x1200000)
    for s in m['segments']:
        if s['filesize']:
            u.mem_write(s['va'], raw[s['fileoff']:s['fileoff']+s['filesize']])
    for i in range(31):
        u.reg_write(getattr(C, f'UC_ARM64_REG_X{i}'), 0x100000+i*0x100)
    u.reg_write(C.UC_ARM64_REG_SP, STACK+0xe000)
    u.reg_write(C.UC_ARM64_REG_TPIDR_EL1, 0x1111)
    u.mem_write(ps['probe_scratch'], struct.pack('<QQ', FB, ROW))
    before = [u.reg_read(getattr(C, f'UC_ARM64_REG_X{i}')) for i in range(30)]
    count = writes = written_bytes = 0
    last_row = 0
    events = []
    watches = {int(v['load_snapshot'], 16): k for k, v in info['fields'].items()}
    scratch_writes = []

    def code(u, pc, size, data):
        nonlocal count
        count += 1
        if pc in watches:
            if lose_snapshot and watches[pc] == 'A037':
                u.mem_write(ps['probe_scratch'], bytes(8))
            events.append(dict(field=watches[pc], pc=hex(pc), instructions=count,
                               framebuffer_writes=writes, framebuffer_bytes=written_bytes))
        if pc == m['symbols']['_vn_rdwr']:
            u.emu_stop()

    def write(u, access, address, size, value, data):
        nonlocal writes, written_bytes, last_row
        if FB <= address < FB+0x1200000:
            writes += 1
            written_bytes += size
            last_row = max(last_row, (address+size-1-FB)//ROW)
        if ps['probe_scratch'] <= address < ps['probe_scratch']+16:
            scratch_writes.append(dict(pc=hex(u.reg_read(C.UC_ARM64_REG_PC)), address=hex(address)))

    u.hook_add(U.UC_HOOK_CODE, code)
    u.hook_add(U.UC_HOOK_MEM_WRITE, write)
    u.emu_start(FIRST, 0, count=2000000)
    assert u.reg_read(C.UC_ARM64_REG_PC) == m['symbols']['_vn_rdwr']
    assert before == [u.reg_read(getattr(C, f'UC_ARM64_REG_X{i}')) for i in range(30)]
    assert u.reg_read(C.UC_ARM64_REG_SP) == STACK+0xe000
    assert u.reg_read(C.UC_ARM64_REG_LR) == FIRST+4
    assert not scratch_writes
    actual = {f'{tag:04X}': field(u, tag) for tag in range(0xa034, 0xa03a)}
    assert actual['A034'] == '00000000000000FA' and actual['A035'] == 'FFFFFFFFFFFFFFFF'
    assert actual['A036'] == '0000000000000000'
    assert actual['A037'] == (None if lose_snapshot else '0000000000000000')
    if info['revision'] == 38:
        assert actual['A038'] == (None if lose_snapshot else '0000000000000000')
        assert actual['A039'] == (None if lose_snapshot else 'FFFFFFFFFFFFFFFF')
    return dict(injected_snapshot_loss=lose_snapshot, reached_native_vn_rdwr=True,
                native_arguments_and_sp_preserved=True, native_lr=hex(FIRST+4),
                instructions=count, framebuffer_writes=writes, framebuffer_bytes=written_bytes,
                max_written_row=last_row, snapshot_written_by_guest=scratch_writes, events=events, fields=actual)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    assert not a.output.exists() and a.output.resolve().is_relative_to(ROOT/'reports')
    reports = []
    for folder in ('2026-10-26-v37-context-qualified', '2026-10-26-v38'):
        raw, m, ps, info = inspect(ROOT/'reports/kernel-entry-probe'/folder/'build.json')
        info['normal_model'] = execute(raw, m, ps, info)
        if info['revision'] == 38:
            info['counterexample_model'] = execute(raw, m, ps, info, True)
        reports.append(info)
    prefixes = [[i for i in r['instructions'] if int(i['pc'], 16) <
                 int(r['fields']['A037']['load_snapshot'], 16)] for r in reports]
    assert len(prefixes[0]) == len(prefixes[1])
    differences = []
    for left, right in zip(*prefixes):
        if left['bytes'] != right['bytes']:
            lw = int.from_bytes(bytes.fromhex(left['bytes']), 'little')
            rw = int.from_bytes(bytes.fromhex(right['bytes']), 'little')
            # ADR: immlo and immhi relocate; opcode and destination must match.
            assert lw & 0x9f000000 == rw & 0x9f000000 == 0x10000000, (left, right)
            assert lw & 31 == rw & 31
            differences.append(dict(probe29=left, probe30=right))
    out = dict(scope=__doc__, sources=[dict(path=Path(__file__).relative_to(ROOT).as_posix(), sha256=B.sha(Path(__file__).read_bytes()))],
               candidates=reports, device_accessed=False, kernel_or_boot_package_modified=False,
               prefix_comparison=dict(end='Immediately before A037 snapshot load',
                                      static_instructions=len(prefixes[0]),
                                      only_adr_relocations_differ=True, differences=differences),
               limitations=['Flat mapped memory, no hardware interrupt delivery, cache, display scanout, scheduler or real timing',
                            'Snapshot loss is host-injected; not a hardware cause diagnosis',
                            'Execution ends at native vn_rdwr entry; no APFS body is executed'])
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(out, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps([dict(revision=r['revision'], normal=r['normal_model'],
                           counterexample=r.get('counterexample_model')) for r in reports]))


if __name__ == '__main__':
    main()
