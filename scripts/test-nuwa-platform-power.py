#!/usr/bin/env python3
"""Host verification of the guarded PMGR provider against the pinned carrier.

Three independent checks, all without any device or full IOKit emulation:

1. Real machine-code consumer (executed): the carrier's own nub read/write and
   readAon/writeAon instruction streams are run under unicorn with a modeled
   (mock) provider/nub object. The provider vtable slot data is the only mock;
   the executed instructions are the carrier's actual bytes.

2. Compiled provider object (symbol presence only): nuwa_pmgr_run and
   nuwa_pmgr_checkpoint are present, and readAon/writeAon are not redefined.
   This is a symbol-existence check, NOT the 325-slot vtable resolution (that
   is a static build-time check in build-nuwa-platform-power.py).

3. Build report bindings (JSON): the emitted nub read/write and readAon/writeAon
   bindings match the carrier addresses.

The publish/refusal lifecycle is not executed: the provider constructor,
attach/start/registerService and the unavailable() panic path are compiled but
never run here (no full IOKit emulation).
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, '/root/nuwa-pmap-ret-native-20261111/nuwa/ios-16.7.16-20H392/nuwa_pmap_ret/tree/kits/NativePrelink')
from native_prelink import macho, backed_offset  # noqa: E402

CARRIER = Path('/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/pthread-renderer-20261112-r1/renderer-baseline.macho')
CARRIER_SHA = 'e0c235f1de499c858d6eb672f989de7692f1d97140e1064da59391642fa11f5d'
NUB_READ = 0xfffffff004685734
NUB_WRITE = 0xfffffff004683dbc
READ_AON = 0xfffffff004681e04
WRITE_AON = 0xfffffff004681e0c


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--python-tools', type=Path, required=True)
    a = p.parse_args()
    assert not a.output.exists()
    sys.path.insert(0, str(a.python_tools))
    import unicorn as U
    from unicorn.arm64_const import UC_ARM64_REG_PC, UC_ARM64_REG_X0, UC_ARM64_REG_X8, UC_ARM64_REG_X30

    raw = CARRIER.read_bytes()
    assert sha(raw) == CARRIER_SHA
    meta = macho(raw)
    report = json.loads((a.build / 'build-report.json').read_text())
    assert report['carrier_sha256'] == CARRIER_SHA and report['virtual_entries'] == 325
    assert report['runtime_qualified'] is False and report['original_executable_modified'] is False

    def carrier_bytes(va, n):
        return raw[backed_offset(meta['segments'], va, n, len(raw)):backed_offset(meta['segments'], va, n, len(raw)) + n]

    # --- Part 1: real machine-code consumer, mock object data only ---
    # unicorn maps low addresses; rebase the four carrier code pages by the
    # kernel bias so the instruction stream bytes are the carrier's actual ones.
    BIAS = 0xfffffff000000000
    sites = {NUB_READ, NUB_WRITE, READ_AON, WRITE_AON}
    uc = U.Uc(U.UC_ARCH_ARM64, U.UC_MODE_ARM)
    for page in sorted({va & ~0xfff for va in sites}):
        uc.mem_map(page - BIAS, 0x1000)
        uc.mem_write(page - BIAS, carrier_bytes(page, 0x1000))
    uc.mem_map(0x30000000, 0x3000)  # mock provider object + vtable + nub
    halt = 0x30003000
    uc.mem_map(halt, 0x1000)  # mapped return slot for readAon/writeAon `ret`
    provider = 0x30000000
    vtable = 0x30001000
    nub = 0x30002000
    # Mock provider vtable: slot 312 readAon, slot 313 writeAon, all else zero.
    uc.mem_write(vtable + 312 * 8, struct.pack('<Q', READ_AON - BIAS))
    uc.mem_write(vtable + 313 * 8, struct.pack('<Q', WRITE_AON - BIAS))
    # Mock provider object: first word = vtable pointer (the readAon/writeAon
    # trampolines load x8 from [provider], then slot from [x8, #slot*8]).
    uc.mem_write(provider, struct.pack('<Q', vtable))
    # Mock nub object: +0x88 holds the provider pointer (the audit pins this
    # offset; the nub read/write load it and jump through the provider vtable).
    uc.mem_write(nub + 0x88, struct.pack('<Q', provider))
    # readAon returns 0xffffffff; writeAon is an empty return. Both are the
    # carrier's actual instruction words, verified by the audit, not rewritten.
    cases = []
    uc.reg_write(UC_ARM64_REG_X0, nub)
    uc.reg_write(UC_ARM64_REG_X30, halt)  # x30 = return address for the AON `ret`
    uc.emu_start(NUB_READ - BIAS, halt, count=50)
    cases.append(dict(what='nub_read_returns_ffffffff', x0=hex(uc.reg_read(UC_ARM64_REG_X0)),
                      expect='0xffffffff', passed=uc.reg_read(UC_ARM64_REG_X0) == 0xffffffff))
    uc.reg_write(UC_ARM64_REG_X0, nub)
    uc.reg_write(UC_ARM64_REG_X8, 0)
    uc.reg_write(UC_ARM64_REG_X30, halt)
    uc.emu_start(NUB_WRITE - BIAS, halt, count=50)
    # nub write loads the provider into x0, jumps through slot 313 writeAon and
    # returns with x0 = provider (writeAon is empty and does not restore x0).
    cases.append(dict(what='nub_write_routes_slot313', x0=hex(uc.reg_read(UC_ARM64_REG_X0)),
                      passed=uc.reg_read(UC_ARM64_REG_X0) == provider))
    # Direct readAon/writeAon: carrier bytes, no object data at all.
    uc.reg_write(UC_ARM64_REG_X0, 0)
    uc.reg_write(UC_ARM64_REG_X30, halt)
    uc.emu_start(READ_AON - BIAS, halt, count=10)
    cases.append(dict(what='read_aon_returns_ffffffff', x0=hex(uc.reg_read(UC_ARM64_REG_X0)),
                      passed=uc.reg_read(UC_ARM64_REG_X0) == 0xffffffff))
    # writeAon is a bare `ret`: record the pre-state, run it, then assert the
    # final PC is the return slot, x0 is untouched, and no mock memory changed.
    uc.reg_write(UC_ARM64_REG_X0, 0x1234)
    uc.reg_write(UC_ARM64_REG_X30, halt)
    pre_mem = bytes(uc.mem_read(0x30000000, 0x3000))
    uc.emu_start(WRITE_AON - BIAS, halt, count=10)
    cases.append(dict(what='write_aon_empty_return',
                      pc=hex(uc.reg_read(UC_ARM64_REG_PC)),
                      x0=hex(uc.reg_read(UC_ARM64_REG_X0)),
                      mem_unchanged=bytes(uc.mem_read(0x30000000, 0x3000)) == pre_mem,
                      passed=(uc.reg_read(UC_ARM64_REG_PC) == halt and
                              uc.reg_read(UC_ARM64_REG_X0) == 0x1234 and
                              bytes(uc.mem_read(0x30000000, 0x3000)) == pre_mem)))

    # --- Part 2: compiled provider object symbol presence (not vtable resolution) ---
    obj = macho((a.build / 'NuwaPlatformPower.o').read_bytes())
    sym_at = next(at for cmd, at, _ in obj['commands'] if cmd == 2)
    at, count, strings, _ = struct.unpack_from('<4I', (a.build / 'NuwaPlatformPower.o').read_bytes(), sym_at + 8)
    data = (a.build / 'NuwaPlatformPower.o').read_bytes()
    symbols = []
    for i in range(count):
        ix, kind, _, _, _ = struct.unpack_from('<IBBHQ', data, at + i * 16)
        symbols.append((data[strings + ix:data.index(b'\0', strings + ix)].decode(), kind))
    defined = {n for n, k in symbols if k in (0x0f, 0x0e)}
    # Check only the two lifecycle symbol definitions named below.
    require = ('_nuwa_pmgr_run' in defined, '_nuwa_pmgr_checkpoint' in defined)
    cases.append(dict(what='provider_lifecycle_symbols_present', passed=all(require)))
    # readAon/writeAon are inherited from ApplePMGR, not defined here.
    cases.append(dict(what='aon_methods_not_redefined',
                      passed=not any('readAon' in n or 'writeAon' in n for n in defined)))
    # --- Part 3: build report bindings (JSON) ---
    report_obj = json.loads((a.build / 'build-report.json').read_text())
    bindings = report_obj['bindings']
    cases.append(dict(what='bindings_match_carrier',
                      passed=bindings['_nuwa_original_pmgr_nub_read'] == hex(NUB_READ) and
                             bindings['_nuwa_original_pmgr_nub_write'] == hex(NUB_WRITE) and
                             bindings['__ZN9ApplePMGR7readAonEv'] == hex(READ_AON) and
                             bindings['__ZN9ApplePMGR8writeAonEy'] == hex(WRITE_AON)))

    result = dict(status='self-checked', carrier_sha256=CARRIER_SHA, cases=cases,
                  executed=dict(kind='4 carrier instruction-stream cases (unicorn, mock object data only)',
                                nub_read=NUB_READ, nub_write=NUB_WRITE, read_aon=READ_AON, write_aon=WRITE_AON),
                  static=dict(kind='2 symbol-presence checks + 1 JSON bindings check; the 325-slot vtable '
                                   'resolution is verified statically by build-nuwa-platform-power.py, not here',
                              vtable_resolution='build-time only', lifecycle_executed=False,
                              refusal_executed=False),
                  mock=dict(kind='provider/nub object data only; executed instructions are carrier bytes',
                            vtable=hex(vtable), provider=hex(provider), nub=hex(nub),
                            slot312=hex(READ_AON), slot313=hex(WRITE_AON)),
                  build_report=report_obj,
                  limits='Publish/refusal lifecycle is not executed; the provider constructor, attach/start/'
                         'registerService and unavailable() panic are compiled but not run. Only the carrier '
                         'instruction streams, compiled-object symbol presence and JSON bindings are verified. '
                         'No power hardware, publication or device run. Default off (nuwa-pmgr boot-arg).')
    assert all(c['passed'] for c in cases), cases
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'cases': len(cases), 'all_passed': True}, indent=2))


if __name__ == '__main__':
    main()
