"""Bounded, host-only execution of current nuwa Image4 BNCH instructions.

No Apple instructions are embedded here. Inputs are read-only; instruction
windows and coverage are written only below this repository's ignored out/.
This is not an authentication test or a device-release qualification.
"""
import argparse
import hashlib
import importlib.util
import json
import secrets
import struct
import sys
from pathlib import Path

import capstone
import unicorn
from unicorn.arm64_const import (
    UC_ARM64_REG_LR, UC_ARM64_REG_PC, UC_ARM64_REG_SP,
    UC_ARM64_REG_X0, UC_ARM64_REG_X2, UC_ARM64_REG_X3,
    UC_ARM64_REG_X19,
)

ROOT = Path(__file__).resolve().parents[1]
KERNEL_SHA = 'fb1e796d7357b3e7ff7027bb94377d1cd38eae7283a6c72a7460914a200a0fbd'
ADT_SHA = '9172e0ccd2efe250bcba05ce1e1884a5bb19a9c7d6a86527aaa35c36e5de453b'
INIT = 0xfffffff0046e98cc
READER = 0xfffffff0046eae28
PANIC = 0xfffffff0046fa028
LOCK = 0xfffffff0046f9fe0
BNCH_RETURN = 0xfffffff0046e9a28
DONOR_BEGIN, DONOR_END = 0xfffffff0046e4000, 0xfffffff0046fa100


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Import only definitions. Neither module's CLI/main is invoked; in particular
# the historical builder INPUT is never opened, nor is an adapter installed.
A = load('current_bnch_object_boundary', 'audit-image4-runtime-provider.py')
C = load('current_bnch_adt_codec', 'nuwa_launch_context.py')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def bound_input(path, expected, pin, size=None):
    require(expected == pin, 'Unsupported input pin (no address fallback)')
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == expected, 'Input SHA256 mismatch: ' + str(path))
    require(size is None or len(raw) == size, 'Input size mismatch')
    return raw


def variant(adt, value):
    tree = C.parse(adt)
    node = C.find(tree, '/chosen/manifest-properties')
    node['properties'] = [(k, f, v) for k, f, v in node['properties'] if k != 'BNCH']
    if value is not None:
        node['properties'].append(('BNCH', 0, value))
    return C.encode(tree)


def binding(raw, macho):
    def qword(pc):
        return struct.unpack('<Q', A.backed_bytes(raw, macho, pc, 8))[0]

    expected = {
        A.PMAP_RUNTIME: 5, A.PMAP_RUNTIME + 0x10: INIT,
        A.PMAP_RUNTIME + 0x58: A.RUNTIME, A.RUNTIME: 5,
        A.RUNTIME + 0x38: A.ENTRIES['bool'],
        A.RUNTIME + 0x50: A.ENTRIES['digest'],
    }
    for pc, value in expected.items():
        require(qword(pc) == value, 'Provider table mismatch: ' + hex(pc))
    symbols = macho['symbols']
    # The initializer's direct BL identifies the reader; no guessed entry.
    md = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)
    call = next(md.disasm(A.backed_bytes(raw, macho, BNCH_RETURN - 4, 4), BNCH_RETURN - 4))
    require(call.mnemonic == 'bl' and int(call.op_str[1:], 16) == READER,
            'Initializer BNCH call edge changed')
    got_symbols = {0xfffffff005cabae8: '_lck_spin_init'}
    for pc, name in got_symbols.items():
        require(qword(pc) == symbols[name], 'Kernel boundary binding changed: ' + name)
    tables = {}
    for label, base in [('pmap_cs', A.PMAP_RUNTIME), ('darwin', A.RUNTIME)]:
        tables[label] = {hex(off): hex(qword(base + off)) for off in range(0, 0x80, 8)}
    windows = {}
    for pc, length in [(INIT, 0x320), (READER, 0x90), (0xfffffff0046e9f50, 0x4c)]:
        windows[hex(pc)] = [dict(pc=hex(i.address), mnemonic=i.mnemonic, operands=i.op_str)
                            for i in md.disasm(A.backed_bytes(raw, macho, pc, length), pc)]
    return dict(tables=tables, windows=windows,
                symbols={k: hex(symbols[k]) for k in
                         ('_SecureDTInit', '_SecureDTLookupEntry', '_SecureDTGetProperty',
                          '_pmap_in_ppl', '_lck_spin_init', '_bzero', '_memcpy')},
                entry_provenance='pmap_cs+0x10 initializer -> BL at 0xfffffff0046e9a24 -> reader')


class Run:
    def __init__(self, raw, macho, adt):
        self.model = A.Model(raw, macho, A.parse_adt(adt))
        self.u = self.model.u
        self.coverage, self.stub_calls, self.writes = set(), [], []
        self.outcome = {}
        self.guard = None
        self.init_guard = None
        self.sync_boundaries = {v: k for k, v in macho['symbols'].items()
                                if k in ('_lck_spin_lock', '_lck_mtx_lock', '_lck_rw_lock_exclusive',
                                         '_lck_rw_lock_shared')}
        self.u.hook_add(unicorn.UC_HOOK_CODE, self.watch)
        self.u.hook_add(unicorn.UC_HOOK_MEM_WRITE, self.write)
        tree = 0xe00000
        self.u.mem_map(tree, A.B.align(len(adt)))
        self.u.mem_write(tree, adt)
        self.model.call(macho['symbols']['_SecureDTInit'], (tree, len(adt)))
        scratch = A.HEAP + 0x3000
        rc = self.model.call(macho['symbols']['_SecureDTLookupEntry'],
                             (0, self.string('/chosen/manifest-properties'), scratch))
        require(rc == 1, 'Actual ADT manifest-properties lookup failed')
        self.manifest_node = self.model.get64(scratch)
        self.coverage.clear()
        self.stub_calls.clear()

    def string(self, text):
        at = A.HEAP + 0x4000
        self.u.mem_write(at, text.encode() + b'\0')
        return at

    def write(self, u, access, address, size, value, data):
        if self.guard:
            lo, hi = self.guard
            if address < hi + 16 and address + size > lo - 16:
                self.writes.append(dict(pc=hex(u.reg_read(UC_ARM64_REG_PC)),
                                        address=hex(address), size=size))
                require(address >= lo and address + size <= hi, 'Donor output buffer overrun')

    def watch(self, u, pc, size, data):
        self.coverage.add(pc)
        if pc in self.model.hooks:
            self.stub_calls.append(dict(pc=hex(pc), boundary=self.model.hooks[pc]))
        if pc == 0xfffffff0046e9948:
            descriptor = u.reg_read(UC_ARM64_REG_X0)
            self.outcome['chip_descriptor'] = hex(descriptor)
            self.outcome['secure_boot_level'] = self.model.get64(descriptor + 8)
        if pc == 0xfffffff0046e994c:
            self.outcome['actual_pmap_in_ppl_result'] = u.reg_read(UC_ARM64_REG_X0)
        if pc == BNCH_RETURN - 4:
            out = u.reg_read(UC_ARM64_REG_X2)
            length = u.reg_read(UC_ARM64_REG_X3)
            capacity = struct.unpack('<I', u.mem_read(length, 4))[0]
            require(capacity == 48, 'Initializer capacity changed')
            self.guard = out, out + capacity
            self.init_guard = (out, length, bytes(u.mem_read(out - 16, 16)),
                               bytes(u.mem_read(out + capacity, 16)))
        if pc == BNCH_RETURN:
            self.outcome['bnch_errno'] = u.reg_read(UC_ARM64_REG_X0) & 0xffffffff
            out, length, before, after = self.init_guard
            require(bytes(u.mem_read(out - 16, 16)) == before and
                    bytes(u.mem_read(out + 48, 16)) == after, 'Initializer output overrun')
            self.outcome['bnch_output_length'] = struct.unpack('<I', u.mem_read(length, 4))[0]
            self.outcome['bnch_canaries_intact'] = True
            self.guard = None
        if pc == PANIC:
            sp = u.reg_read(UC_ARM64_REG_SP)
            self.outcome.update(stop='original panic edge',
                                panic=self.model.cstr(u.reg_read(UC_ARM64_REG_X0)),
                                panic_stack_values=[self.model.get64(sp), self.model.get64(sp + 8)])
            u.emu_stop()
        if pc in self.sync_boundaries:
            self.outcome.update(stop='unmodeled kernel synchronization boundary',
                                boundary_symbol=self.sync_boundaries[pc])
            u.emu_stop()

    def record(self):
        return dict(**self.outcome, terminal_pc=hex(self.u.reg_read(UC_ARM64_REG_PC)),
                    donor_pcs=[hex(p) for p in sorted(self.coverage)
                               if DONOR_BEGIN <= p < DONOR_END and
                               p not in self.model.hooks and p != PANIC],
                    all_pcs=[hex(p) for p in sorted(self.coverage)],
                    boundary_stubs=self.stub_calls, object_events=self.model.events,
                    invalid_memory=self.model.bad, output_writes=self.writes,
                    callback=None, nonce_comparison='NOT REACHED', authentication='NOT REACHED')

    def reader(self):
        out, length = A.HEAP + 0x3200, A.HEAP + 0x3300
        self.u.mem_write(out - 16, b'\xa5' * 80)
        self.u.mem_write(length, struct.pack('<I', 48))
        self.guard = out, out + 48
        errno = self.model.call(READER, (self.manifest_node, self.string('BNCH'), out, length))
        self.guard = None
        data = bytes(self.u.mem_read(out - 16, 80))
        require(data[:16] == b'\xa5' * 16 and data[64:] == b'\xa5' * 16, 'Output canary changed')
        self.outcome.update(stop='return', errno=errno,
                            output_length=struct.unpack('<I', self.u.mem_read(length, 4))[0],
                            canaries_intact=True, output_hex=data[16:64].hex())
        return self.record()

    def initialize(self):
        u = self.u
        u.reg_write(UC_ARM64_REG_X0, A.PMAP_RUNTIME)
        u.reg_write(UC_ARM64_REG_LR, A.STOP)
        u.reg_write(UC_ARM64_REG_SP, A.STACK + 0x8000)
        u.emu_start(INIT, A.STOP, count=300000)
        require(not self.model.bad, 'Invalid emulated memory')
        if u.reg_read(UC_ARM64_REG_PC) == A.STOP:
            self.outcome['stop'] = 'initializer return'
        require(bool(self.outcome.get('stop')), 'Initialization budget exhausted or unexpected return')
        self.outcome['runtime_x19'] = hex(u.reg_read(UC_ARM64_REG_X19))
        return self.record()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kernel', type=Path, required=True)
    p.add_argument('--kernel-sha256', required=True)
    p.add_argument('--adt', type=Path, required=True)
    p.add_argument('--adt-sha256', required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    out = a.output.resolve()
    require(out.is_relative_to(ROOT / 'out') and not out.exists(), 'Fresh output below device out/ required')
    raw = bound_input(a.kernel, a.kernel_sha256, KERNEL_SHA, 55357440)
    adt = bound_input(a.adt, a.adt_sha256, ADT_SHA)
    nodes = A.parse_adt(adt)
    require(nodes['/chosen'].get('mix-n-match-prevention-status') == bytes(4), 'Unexpected AMNM input')
    require('BNCH' not in nodes['/chosen/manifest-properties'], 'Baseline already has BNCH')
    macho = A.B.macho(raw)
    bindings = binding(raw, macho)
    token = secrets.token_bytes(48)
    epoch = secrets.token_hex(16)
    cases = {}
    for name, value, error in [('missing', None, 2), ('zero_length', b'', 0),
                               ('experimental_48', token, 0), ('oversized_49', token + b'x', 84)]:
        data = variant(adt, value)
        reader = Run(raw, macho, data).reader()
        require(reader['errno'] == error, 'Unexpected original reader errno: ' + name)
        expected_length = 48 if error else len(value)
        require(reader['output_length'] == expected_length, 'Unexpected reader output length: ' + name)
        if error:
            require(reader['output_hex'] == (b'\xa5' * 48).hex(), 'Error modified output')
        else:
            require(reader['output_length'] == len(value) and
                    reader['output_hex'] == (value + bytes(48 - len(value))).hex(), 'Copy result differs')
        init = Run(raw, macho, data).initialize()
        require(init.get('bnch_errno') == error, 'Reader/init errno disagreement')
        require(init.get('bnch_output_length') == expected_length, 'Unexpected initializer output length: ' + name)
        require(init['stop'] == ('original panic edge' if error else
                                 'initializer return'), 'Unexpected initialization edge')
        if error:
            require(init.get('panic') == 'failed to read boot nonce hash: secure boot level = %#llx: %d'
                    and init.get('panic_stack_values') == [0, error], 'Unexpected original panic: ' + name)
        cases[name] = dict(reader=reader, initialization=init)
    report = dict(status='self-checked', kernel_sha256=KERNEL_SHA, adt_sha256=ADT_SHA,
                  binding=bindings, cases=cases,
                  experiment=dict(domain='CSPRNG process-session epoch; emulated memory only',
                                  session_epoch=epoch, capacity=48,
                                  token_contract='48 is reader capacity, not a proven producer contract',
                                  hardware_antirollback=False, donor_identity=False,
                                  epoch_roll_rejection='NOT IMPLEMENTED; no donor rejection claim'),
                  next_blocker=dict(pc=None, symbol=None,
                                    reason='Initializer returned; no authenticated manifest or established bounded consumer invocation/state. Stop before authentication; no guessed function entry or undefined no-manifest execute call',
                                    consumer_equal='NOT REACHED', consumer_different='NOT REACHED',
                                    consumer_old_epoch='NOT REACHED', authentication='NOT REACHED',
                                    signed_positive='UNAVAILABLE; no firmware execute invoked'),
                  tools=dict(unicorn=unicorn.__version__, capstone=capstone.__version__),
                  harness_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  dependencies={name: hashlib.sha256((ROOT / 'scripts' / name).read_bytes()).hexdigest()
                                for name in ('audit-image4-runtime-provider.py',
                                             'build-kernel-entry-probe.py', 'nuwa_launch_context.py')},
                  invocation=dict(argv=sys.argv, cwd=str(Path.cwd()), success_exit_code=0),
                  coverage_semantics='donor_pcs excludes stubs and terminal boundary (visited, not executed); all_pcs includes them',
                  device_accessed=False, donor_modified=False)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(status='self-checked', cases=len(cases), output=str(out),
                         next_blocker=report['next_blocker'])))


if __name__ == '__main__':
    main()
