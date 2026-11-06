"""Drive the v20 probe read sites directly and decode what they render.

The v20 question is about values the kernel computes at run time, so the
model has to plant known values in the globals the probe reads and then check
the rendered hex rows against them. This is a rendering test: it proves the
probe reads the right address, offset and width, not that the kernel produces
those values on nuwa.

Sites exercised:
  probe_soc_base      - reads _DTInitialized, _DTRootNode, _gPESoCBasePhys and
                        PE_state_raw_90
  probe_wfe_timeout   - reads gPEClockFrequencyInfo.timebase_frequency_hz (+0x48)
                        and arm64_eventi
"""

import argparse
import hashlib
import importlib.util
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'out/python-tools'))
import unicorn as U
from unicorn.arm64_const import *

spec = importlib.util.spec_from_file_location('t', ROOT / 'scripts/test-kernel-entry-probe.py')
T = importlib.util.module_from_spec(spec)
spec.loader.exec_module(T)
B = T.B
PA, FB, ROW = T.PA, T.FB, T.ROW
STACK = 0x00000000_00F00000

FONT = ['11111001100110011111','00100110001000100111','11110001111110001111','11110001111100011111',
        '10011001111100010001','11111000111100011111','11111000111110011111','11110001001001000100',
        '11111001111110011111','11111001111100011111','11111001111110011001','11101001111010011110',
        '11111000100010001111','11101001100110011110','11111000111110001111','11111000111110001000']
LOOKUP = {bits: format(i, 'X') for i, bits in enumerate(FONT)}
# The glyph table above is a transcription of hex_font in the probe source.
# A wrong bit pattern silently costs a lookup entry and turns one digit into
# '?', so the table is checked against the source instead of trusted.
PROBE_FONT = [0xf999f, 0x26227, 0xf1f8f, 0xf1f1f, 0x99f11, 0xf8f1f, 0xf8f9f, 0xf1244,
              0xf9f9f, 0xf9f1f, 0xf9f99, 0xe9e9e, 0xf888f, 0xe999e, 0xf8f8f, 0xf8f88]


def tile_offset(y):
    return (256 + (y-256) % 512) * ROW + ((y-256)//512)*96*4


def data_y(y):
    return 224 + ((y-1088)//32)*28 if y >= 1088 else 756


def decode(uc, y, start_x=352, digits=16):
    """Read back the 16 hex digits rendered at row y."""
    text = ''
    for digit in range(digits):
        bits = ''.join('1' if struct.unpack('<I', uc.mem_read(FB + (data_y(y) + r * 4) * ROW + start_x * 4 + digit * 24 * 4 + c * 16, 4))[0] == 0xffffffff else '0'
                       for r in range(5) for c in range(4))
        text += LOOKUP.get(bits, '?')
    return text


def plant(uc, base, symbol, offset, raw):
    """Write raw bytes at the symbol's own KVA."""
    uc.mem_write(symbol + offset, raw)


def run_site(candidate, report, site, plants, rows):
    m = B.macho(candidate)
    base = min(s['va'] for s in m['segments'] if s['size'])
    end = max(s['va'] + s['size'] for s in m['segments'])
    uc = U.Uc(U.UC_ARCH_ARM64, U.UC_MODE_ARM)
    # The kernel image is mapped twice: at PA (V=P, where the cold path runs)
    # and at its own KVA (where the probe's absolute addresses live). The
    # hardware has both mappings live; the model needs both to make a probe
    # read of a kernel global meaningful. The KVA map has to sit at the real
    # addresses: the probe materialises absolute KVAs and loads through them,
    # so a window at any other base would not be the address it reads.
    uc.mem_map(PA, B.align(end - base) + 0x1000)
    uc.mem_map(base, (end - base) + 0x400000)
    uc.mem_map(FB, 0x1200000)
    # A C function entry always has a valid stack pointer; the probe saves and
    # restores the callee-saved registers on it. The model needs one too.
    uc.mem_map(STACK, 0x10000)
    for s in m['segments']:
        if s['filesize']:
            image = bytes(candidate[s['fileoff']:s['fileoff'] + s['filesize']])
            uc.mem_write(PA + s['va'] - base, image)
            uc.mem_write(s['va'], image)
    # The snapshot the renderers need: framebuffer base and line stride.
    scratch = int(report['probe']['symbols']['probe_scratch'], 16)
    uc.mem_write(scratch, struct.pack('<QQ', FB, ROW))
    for symbol, offset, raw in plants:
        plant(uc, base, symbol, offset, raw)
    symbols = report['probe']['symbols']
    entry = int(symbols[site], 16)
    stop = int(symbols[site + '_replay'], 16)
    bad = []

    def code(uc, addr, size, _):
        if addr == stop:
            uc.emu_stop()

    def invalid(uc, access, addr, size, value, _):
        bad.append(dict(access=access, address=hex(addr), pc=hex(uc.reg_read(UC_ARM64_REG_PC))))
        return False

    uc.hook_add(U.UC_HOOK_CODE, code)
    uc.hook_add(U.UC_HOOK_MEM_INVALID, invalid)
    uc.reg_write(UC_ARM64_REG_SP, STACK + 0x8000)
    error = None
    try:
        uc.emu_start(entry, 0, count=2000000)
    except U.UcError as e:
        error = str(e)
    return dict(error=error, bad_memory=bad,
                decoded={name: decode(uc, y) for name, y in rows.items()},
                tags={name: decode(uc,y,256,4) for name,y in rows.items()},
                rows={name: y for name, y in rows.items()})


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--build', type=Path, required=True)
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    report = json.loads(args.build.read_text())
    candidate = (ROOT / report['candidate']['path']).read_bytes()
    m = B.macho(candidate)
    symbols = m['symbols']
    checks = []

    def check(name, ok):
        checks.append(dict(name=name, passed=bool(ok)))
        if not ok:
            raise AssertionError(name)

    check('The glyph table matches the probe source font', FONT == [format(g, '020b') for g in PROBE_FONT])
    check('Every glyph is unique so a digit can be decoded',
          len(set(FONT)) == 16 and len(LOOKUP) == 16)

    # --- probe_soc_base ------------------------------------------------
    dt_init = 0x1
    dt_root = 0xfffffff0071ea000
    soc_base = 0x17000000
    dt_head = 0xfffffff0071ea000
    dt_size = 13120
    plants = [
        (symbols['_DTInitialized'], 0, struct.pack('<I', dt_init)),
        (symbols['_DTRootNode'], 0, struct.pack('<Q', dt_root)),
        (symbols['_gPESoCBasePhys'], 0, struct.pack('<Q', soc_base)),
        (symbols['_PE_state'], 0x90, struct.pack('<Q', dt_head)),
        (symbols['_PE_state'], 0xa0, struct.pack('<Q', dt_size)),
    ]
    rows = {'DTInitialized': 1344, 'DTRootNode': 1376, 'gPESoCBasePhys': 1408,
            'PE_state_raw_90': 1440, 'PE_state.bootArgs': 1472}
    result = run_site(candidate, report, 'probe_soc_base', plants, rows)
    check('The soc_base hook runs without a bad memory access', not result['bad_memory'] and not result['error'])
    check('DTInitialized renders its 32-bit value', result['decoded']['DTInitialized'] == '0000000000000001')
    check('DTRootNode renders the full 64-bit pointer',
          result['decoded']['DTRootNode'] == '%016X' % dt_root)
    check('gPESoCBasePhys renders the full 64-bit value',
          result['decoded']['gPESoCBasePhys'] == '%016X' % soc_base)
    check('PE_state_raw_90 renders the value at offset 0x90',
          result['decoded']['PE_state_raw_90'] == '%016X' % dt_head)
    check('PE_state.bootArgs renders the value at offset 0xa0',
          result['decoded']['PE_state.bootArgs'] == '%016X' % dt_size)

    # --- probe_wfe_timeout ---------------------------------------------
    timebase = 19200000
    eventi = 0xFFFFFFFF
    plants = [
        (symbols['_gPEClockFrequencyInfo'], 0x48, struct.pack('<Q', timebase)),
        (symbols['_arm64_eventi'], 0, struct.pack('<I', eventi)),
    ]
    rows = {'timebase_frequency_hz': 1504, 'arm64_eventi': 1536}
    result2 = run_site(candidate, report, 'probe_wfe_timeout', plants, rows)
    check('The wfe_timeout hook runs without a bad memory access',
          not result2['bad_memory'] and not result2['error'])
    check('timebase_frequency_hz renders the value at offset 0x48',
          result2['decoded']['timebase_frequency_hz'] == '%016X' % timebase)
    check('arm64_eventi renders its 32-bit value',
          result2['decoded']['arm64_eventi'] == '00000000FFFFFFFF')

    check('Every sampled data row has its own correct four-nibble field ID',
          all(result['tags'][k] == f'{0xa000+y//32:04X}' for k,y in result['rows'].items())
          and all(result2['tags'][k] == f'{0xa000+y//32:04X}' for k,y in result2['rows'].items()))

    # --- probe_panic_trap: the variadic argument ------------------------
    # panic("%s: invalid bit index (%u)", __FUNCTION__, bit_index): the first
    # variadic argument is the function name, a kernel text address that is
    # NOT page aligned. The probe must accept it and render the name.
    name = b'_enable_timebase_event_stream\0'
    name_addr = 0xfffffff007012343        # deliberately not page aligned
    uc = U.Uc(U.UC_ARCH_ARM64, U.UC_MODE_ARM)
    m2 = B.macho(candidate)
    base2 = min(s['va'] for s in m2['segments'] if s['size'])
    end2 = max(s['va'] + s['size'] for s in m2['segments'])
    uc.mem_map(PA, B.align(end2 - base2) + 0x1000)
    uc.mem_map(base2, (end2 - base2) + 0x400000)
    uc.mem_map(FB, 0x1200000)
    uc.mem_map(STACK, 0x10000)
    for s in m2['segments']:
        if s['filesize']:
            image = bytes(candidate[s['fileoff']:s['fileoff'] + s['filesize']])
            uc.mem_write(PA + s['va'] - base2, image)
            uc.mem_write(s['va'], image)
    scratch2 = int(report['probe']['symbols']['probe_scratch'], 16)
    uc.mem_write(scratch2, struct.pack('<QQ', FB, ROW))
    # The name lives in the kernel text so the probe can read it through the
    # same mapping the kernel uses.
    uc.mem_write(name_addr, name)
    # The va_list: x1 points at a __va_list_tag whose first word is the stack
    # slot of the first variadic argument; that slot holds the pointer.
    va_list_tag = STACK + 0x2000
    vararg_slot = STACK + 0x3000
    uc.mem_write(va_list_tag, struct.pack('<Q', vararg_slot))
    uc.mem_write(vararg_slot, struct.pack('<Q', name_addr))
    # x0 is the format string.
    fmt = STACK + 0x4000
    uc.mem_write(fmt, b'%s: invalid bit index (%u)\0')
    syms2 = report['probe']['symbols']
    entry2 = int(syms2['probe_panic_trap'], 16)
    stop2 = int(syms2['probe_panic_trap_replay'], 16)

    bad2 = []

    def code2(uc, addr, size, _):
        if addr == stop2:
            uc.emu_stop()

    def invalid2(uc, access, addr, size, value, _):
        bad2.append(dict(access=access, address=hex(addr), pc=hex(uc.reg_read(UC_ARM64_REG_PC))))
        return False

    uc.hook_add(U.UC_HOOK_CODE, code2)
    uc.hook_add(U.UC_HOOK_MEM_INVALID, invalid2)
    uc.reg_write(UC_ARM64_REG_SP, STACK + 0x8000)
    uc.reg_write(UC_ARM64_REG_X0, fmt)
    uc.reg_write(UC_ARM64_REG_X1, va_list_tag)
    error2 = None
    try:
        uc.emu_start(entry2, 0, count=2000000)
    except U.UcError as e:
        error2 = str(e)
    check('The panic hook runs without a bad memory access', not error2 and not bad2)
    arg_rows = {'function_name_1': 1088, 'function_name_2': 1248, 'argument_pointer': 1568,
                'format_1': 1280, 'format_2': 1312}
    decoded = {k: decode(uc, y) for k, y in arg_rows.items()}
    check('The variadic argument is accepted although it is not page aligned',
          decoded['function_name_1'] != '?' * 16)
    check('The function name is rendered as its first eight bytes',
          decoded['function_name_1'] == name[:8].hex().upper())
    check('The function name continues in the next eight bytes',
          decoded['function_name_2'] == name[8:16].hex().upper())
    check('The argument pointer is rendered as well',
          decoded['argument_pointer'] == '%016X' % name_addr)
    check('The format string is still rendered',
          decoded['format_1'] == b'%s: inva'.hex().upper())

    out = dict(scope=('Rendering test of the v20 probe read sites: known values are planted in '
                      'the kernel globals and the hex rows are decoded back from the '
                      'framebuffer. It proves the probe reads the intended address, offset '
                      'and width; it says nothing about nuwa runtime behaviour.'),
               build=str(args.build), candidate_sha256=report['candidate']['sha256'],
               source_sha256=hashlib.sha256((ROOT / 'package/entry-probe/entry-probe.S').read_bytes()).hexdigest(),
               checks=checks, soc_base=result, wfe_timeout=result2,
               panic_argument=dict(decoded=decoded, name=name.decode(), name_addr=hex(name_addr),
                                    error=error2, bad_memory=bad2))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(checks=len(checks), passed=True)))


if __name__ == '__main__':
    main()
