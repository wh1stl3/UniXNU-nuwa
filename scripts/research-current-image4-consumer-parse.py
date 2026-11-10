"""Current-image registration/dispatch/manifest-parse negative, not authentication.

Read-only pinned Apple inputs; constructed offline state, not a kernel snapshot.
Only logging is stubbed. No Image4 security result or provider slot is replaced.
"""
import argparse
import hashlib
import importlib.util
import json
import struct
import sys
from pathlib import Path

import capstone
import unicorn
from unicorn.arm64_const import (UC_ARM64_REG_LR, UC_ARM64_REG_PC,
                                 UC_ARM64_REG_SP, UC_ARM64_REG_X0,
                                 UC_ARM64_REG_X1, UC_ARM64_REG_X2,
                                 UC_ARM64_REG_X3, UC_ARM64_REG_X19)

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('bnch_definitions', ROOT / 'scripts/research-current-image4-bnch.py')
H = importlib.util.module_from_spec(spec)
spec.loader.exec_module(H)
A = H.A
TABLE, SLOT = 0xfffffff005cb1578, 0xfffffff0071aa1d8
REGISTER, REG_SITE, THUNK = 0xfffffff0078950d0, 0xfffffff0046f1834, 0xfffffff0046f9ea8
WRAPPER, EXECUTE = 0xfffffff00771c1a8, 0xfffffff0046e4d88
SPEC, PARSE_CALL, ERROR_MAP = 0xfffffff005cadca0, 0xfffffff0046e4fc0, 0xfffffff0046f3160
PRINTF = 0xfffffff007292e10
UNREACHED = {'firmware_construct': 0xfffffff0046e5224, 'firmware_execute': 0xfffffff0046e5268,
             'authentication_callback': 0xfffffff0046e5288, 'pmap_install': 0xfffffff0046ea69c}
PAYLOAD_SHA = '63e01c03b31e1532a5581a24865490673f0b5c297b0199fe0095637c6100ef4b'
# Self-authored malformed input, not an Apple manifest or extracted bytes.
MALFORMED = b'nuwa-offline-malformed-im4m\n'
DATA, MANIFEST, BUFFERS = 0x2000000, 0x2020000, 0x2021000


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def bind(raw, macho):
    md = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)
    def qword(at):
        return struct.unpack('<Q', A.backed_bytes(raw, macho, at, 8))[0]
    for name, address in {'_img4if': SLOT, '_img4_interface_register': REGISTER,
                          '_xnu_image4_execute_object': WRAPPER, '_printf': PRINTF}.items():
        H.require(macho['symbols'][name] == address, 'Symbol binding changed: ' + name)
    for at, expected in {TABLE: 18, TABLE + 0x218: EXECUTE, TABLE + 0x198: A.PMAP_RUNTIME,
                         TABLE + 0x208: SPEC, 0xfffffff005caba18: REGISTER}.items():
        H.require(qword(at) == expected, 'Interface binding changed: ' + hex(at))
    tag = struct.unpack('<I', A.backed_bytes(raw, macho, SPEC + 0x28, 4))[0]
    H.require(tag == int.from_bytes(b'apin', 'big'), 'Supplemental specification tag changed')
    instructions = list(md.disasm(A.backed_bytes(raw, macho, REG_SITE, 12), REG_SITE))
    H.require([(i.mnemonic, i.op_str) for i in instructions] ==
              [('adrp', 'x0, #0xfffffff005cb1000'), ('add', 'x0, x0, #0x578'),
               ('bl', '#0xfffffff0046f9ea8')], 'Donor registration call site changed')
    for pc, target in {PARSE_CALL: 0xfffffff0046ec81c,
                       0xfffffff0046e4fcc: ERROR_MAP, 0xfffffff00771c214: PRINTF}.items():
        i = next(md.disasm(A.backed_bytes(raw, macho, pc, 4), pc))
        H.require(i.mnemonic == 'bl' and int(i.op_str[1:], 16) == target, 'Call edge changed: ' + hex(pc))
    windows = {}
    for pc, length in [(REG_SITE, 12), (THUNK, 12), (REGISTER, 0x14), (WRAPPER, 0x94),
                        (EXECUTE, 0x2b0), (ERROR_MAP, 0x38)]:
        windows[hex(pc)] = [dict(pc=hex(i.address), mnemonic=i.mnemonic, operands=i.op_str)
                           for i in md.disasm(A.backed_bytes(raw, macho, pc, length), pc)]
    return dict(version=18, table=hex(TABLE), supplemental_spec=hex(SPEC), tag='apin',
                runtime=hex(A.PMAP_RUNTIME), execute=hex(EXECUTE), windows=windows)


class Consumer:
    def __init__(self, raw, macho, payload, manifest):
        # Same file-backed/otherwise-zero mapping as BNCH fixture. No ADT or
        # runtime initializer is invoked/claimed for this early parser path.
        self.model = A.Model(raw, macho, {})
        self.model.hooks.clear()
        self.u = self.model.u
        self.u.mem_map(DATA, 0x23000)
        self.u.mem_write(DATA, payload)
        self.u.mem_write(MANIFEST, manifest)
        self.payload, self.manifest = payload, manifest
        self.u.mem_write(BUFFERS, struct.pack('<4Q', 0, DATA, len(payload), 0))
        self.u.mem_write(BUFFERS + 32, struct.pack('<4Q', 0, MANIFEST, len(manifest), 0))
        self.pcs, self.logs, self.events, self.slot_writes = set(), [], [], []
        self.phase = 'registration'
        self.stop = None
        self.log = self.model.get64(A.PMAP_RUNTIME + 0x28)
        self.sync = {v: k for k, v in macho['symbols'].items()
                     if k in ('_lck_spin_lock', '_lck_mtx_lock', '_lck_rw_lock_exclusive', '_lck_rw_lock_shared')}
        self.u.hook_add(unicorn.UC_HOOK_CODE, self.watch)
        self.u.hook_add(unicorn.UC_HOOK_MEM_WRITE, self.write)

    def write(self, u, access, address, size, value, data):
        if address < SLOT + 8 and address + size > SLOT:
            pc = u.reg_read(UC_ARM64_REG_PC)
            value &= (1 << 64) - 1  # Unicorn memory-hook values may be signed.
            H.require(self.phase == 'registration' and pc == REGISTER + 12 and
                      address == SLOT and size == 8 and value == TABLE, 'Unexpected interface slot write')
            self.slot_writes.append(dict(pc=hex(pc), value=hex(value), size=size))

    def watch(self, u, pc, size, data):
        self.pcs.add(pc)
        if pc in UNREACHED.values() or pc in self.sync:
            self.stop = dict(pc=hex(pc), reason='unmodeled security/state boundary; instruction not executed')
            u.emu_stop()
            return
        if pc == EXECUTE:
            values = [u.reg_read(r) for r in (UC_ARM64_REG_X0, UC_ARM64_REG_X1,
                                            UC_ARM64_REG_X2, UC_ARM64_REG_X3)]
            H.require(values == [A.PMAP_RUNTIME, SPEC, BUFFERS, BUFFERS + 32], 'Wrong real dispatch ABI')
            self.events.append(dict(pc=hex(pc), dispatch_arguments=[hex(v) for v in values]))
        if pc == PARSE_CALL:
            pointer, length = u.reg_read(UC_ARM64_REG_X0), u.reg_read(UC_ARM64_REG_X1)
            H.require(pointer == MANIFEST and length == len(self.manifest), 'Wrong manifest pointer/length')
            H.require(bytes(u.mem_read(pointer, length)) == self.manifest, 'Manifest bytes changed')
            self.events.append(dict(pc=hex(pc), manifest_pointer=hex(pointer), manifest_length=length))
        if pc in (0xfffffff0046e4fc4, ERROR_MAP, 0xfffffff0046e4fd0, 0xfffffff00771c1fc):
            self.events.append(dict(pc=hex(pc), raw_x0=u.reg_read(UC_ARM64_REG_X0)))
        if pc in (self.log, PRINTF):
            saved = u.reg_read(UC_ARM64_REG_X19)
            self.logs.append(dict(pc=hex(pc), boundary='pure runtime log' if pc == self.log else 'XNU printf',
                                  saved_x19=saved, lr=hex(u.reg_read(UC_ARM64_REG_LR))))
            # Only the logging return is synthetic. Error in callee-saved X19
            # remains untouched; the original wrapper reloads X0 from X19.
            u.reg_write(UC_ARM64_REG_X0, 0)
            u.reg_write(UC_ARM64_REG_PC, u.reg_read(UC_ARM64_REG_LR))
            H.require(u.reg_read(UC_ARM64_REG_X19) == saved, 'Log stub changed saved error')

    def run(self):
        H.require(self.model.get64(SLOT) == 0, 'Interface slot must start NULL')
        self.u.reg_write(UC_ARM64_REG_SP, A.STACK + 0x8000)
        self.u.emu_start(REG_SITE, REG_SITE + 12, count=1000)
        H.require(self.u.reg_read(UC_ARM64_REG_PC) == REG_SITE + 12 and
                  self.model.get64(SLOT) == TABLE and len(self.slot_writes) == 1 and
                  REGISTER in self.pcs and THUNK in self.pcs, 'Real interface registration did not complete once')
        registration_pcs = sorted(self.pcs)
        self.pcs.clear()
        self.phase = 'consumer'
        self.u.reg_write(UC_ARM64_REG_SP, A.STACK + 0x8000)
        self.u.reg_write(UC_ARM64_REG_LR, A.STOP)
        for reg, value in [(UC_ARM64_REG_X0, 1), (UC_ARM64_REG_X1, BUFFERS), (UC_ARM64_REG_X2, BUFFERS + 32)]:
            self.u.reg_write(reg, value)
        self.u.emu_start(WRAPPER, A.STOP, count=100000)
        pc = self.u.reg_read(UC_ARM64_REG_PC)
        H.require(not self.model.bad, 'Invalid emulated memory: ' + str(self.model.bad))
        if self.stop:
            return dict(status='BLOCKED', boundary=self.stop, terminal_pc=hex(pc), returned=False,
                        all_pcs=[hex(p) for p in sorted(self.pcs)], events=self.events, stubs=self.logs)
        H.require(pc == A.STOP, 'Instruction budget exhausted before return')
        errno = self.u.reg_read(UC_ARM64_REG_X0) & 0xffffffff
        H.require(errno != 0 and all(p in self.pcs for p in (WRAPPER, EXECUTE, PARSE_CALL, ERROR_MAP)),
                  'No real manifest parsing negative observed')
        H.require(not any(p in self.pcs for p in UNREACHED.values()), 'Unexpected authentication reach')
        wrapper = next(e['raw_x0'] for e in self.events if e['pc'] == hex(0xfffffff00771c1fc))
        observed = {e['pc']: e['raw_x0'] for e in self.events if 'raw_x0' in e}
        H.require(observed[hex(0xfffffff0046e4fc4)] != 0 and
                  observed[hex(0xfffffff0046e4fc4)] == observed[hex(ERROR_MAP)] and
                  observed[hex(0xfffffff0046e4fd0)] == wrapper == errno,
                  'Parser/mapper/wrapper did not preserve original error chain')
        printf = [s for s in self.logs if s['pc'] == hex(PRINTF)]
        H.require(len(printf) == 1 and printf[0]['saved_x19'] == errno, 'Printf saved errno mismatch')
        H.require(bytes(self.u.mem_read(DATA, len(self.payload))) == self.payload and
                  bytes(self.u.mem_read(MANIFEST, len(self.manifest))) == self.manifest and
                  bytes(self.u.mem_read(BUFFERS, 64)) ==
                  struct.pack('<8Q', 0, DATA, len(self.payload), 0, 0, MANIFEST, len(self.manifest), 0),
                  'Input bytes/descriptors changed in emulator')
        return dict(status='self-checked', returned=True, errno=errno, terminal_pc=hex(pc),
                    registration_pcs=[hex(p) for p in registration_pcs], registration_slot_writes=self.slot_writes,
                    donor_pcs=[hex(p) for p in sorted(self.pcs)
                               if H.DONOR_BEGIN <= p < H.DONOR_END and p != self.log],
                    all_pcs=[hex(p) for p in sorted(self.pcs)], stubs=self.logs, events=self.events,
                    invalid_memory=self.model.bad, inputs_unchanged=True,
                    not_reached={n: dict(pc=hex(p), result='NOT REACHED') for n,p in UNREACHED.items()},
                    nonce_comparison='NOT REACHED', authentication='NOT REACHED', callback=None)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kernel', type=Path, required=True)
    p.add_argument('--kernel-sha256', required=True)
    p.add_argument('--payload', type=Path, required=True)
    p.add_argument('--payload-sha256', required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    out = a.output.resolve()
    H.require(out.is_relative_to(ROOT / 'out') and not out.exists(), 'Fresh device out/ evidence required')
    raw = H.bound_input(a.kernel, a.kernel_sha256, H.KERNEL_SHA, 55357440)
    payload = H.bound_input(a.payload, a.payload_sha256, PAYLOAD_SHA, 66289)
    macho = A.B.macho(raw)
    bindings = bind(raw, macho)
    result = Consumer(raw, macho, payload, MALFORMED).run()
    report = dict(scope=__doc__, bindings=bindings, result=result,
                  kernel_sha256=H.KERNEL_SHA, payload_sha256=PAYLOAD_SHA,
                  manifest=dict(origin='self-authored malformed fixture, non-NULL', hex=MALFORMED.hex(),
                                sha256=sha(MALFORMED), pointer=hex(MANIFEST), length=len(MALFORMED)),
                  buffers=dict(payload=dict(pointer=hex(DATA), length=len(payload), descriptor=hex(BUFFERS)),
                               manifest=dict(pointer=hex(MANIFEST), length=len(MALFORMED), descriptor=hex(BUFFERS+32)),
                               version=0, deallocator=None),
                  initial_state='file-backed segment bytes; other mapped memory zero; synthetic stack/heap/buffers; no live runtime snapshot or runtime initialization',
                  limitation='trst payload with supplemental apin spec and malformed manifest: early parsing negative only; no signed apin positive, nonce/authentication or device release proof',
                  dependencies={name: sha((ROOT / 'scripts' / name).read_bytes()) for name in
                                ('research-current-image4-bnch.py', 'audit-image4-runtime-provider.py',
                                 'build-kernel-entry-probe.py', 'nuwa_launch_context.py')},
                  harness_sha256=sha(Path(__file__).read_bytes()), invocation=dict(argv=sys.argv, cwd=str(Path.cwd())),
                  tools=dict(unicorn=unicorn.__version__, capstone=capstone.__version__), device_accessed=False)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(status=result['status'], errno=result.get('errno'), terminal_pc=result['terminal_pc'], output=str(out))))
    if result['status'] == 'BLOCKED':
        sys.exit(2)


if __name__ == '__main__':
    main()
