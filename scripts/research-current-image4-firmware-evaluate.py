"""Bounded native PMAP_CS firmware evaluation of a self-authored untrusted DER.

Not an XNU object installation, accepted manifest, nonce closure or device test.
Apple inputs are read-only; all generated artifacts stay in fresh device out/.
"""
import argparse
import hashlib
import importlib.util
import json
import secrets
import struct
import subprocess
import sys
from pathlib import Path

import capstone
import unicorn
from unicorn.arm64_const import *

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('consumer_definitions', ROOT / 'scripts/research-current-image4-consumer-parse.py')
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)
H, A = P.H, P.A
ENTRIES = {0x130: 0xfffffff0046e6ad4, 0x138: 0xfffffff0046e62f0,
           0x140: 0xfffffff0046e6d90, 0x1c0: 0xfffffff0046e7214,
           0x198: A.PMAP_RUNTIME, 0x100: 0xfffffff0046f0f30}
OBSERVE = {0xfffffff0046e76a8: 'payload_parse_return', 0xfffffff0046e7740: 'manifest_parse_return',
           0xfffffff0046f7a30: 'issuer_name_length_compare', 0xfffffff0046f7a34: 'issuer_name_length_branch',
           0xfffffff0046f7a48: 'issuer_name_memcmp_return',
           0xfffffff0046f7a6c: 'certificate_link_validation_call',
           0xfffffff0046f7778: 'certificate_link_validation_entry',
           0xfffffff0046f7a70: 'certificate_link_validation_return',
           0xfffffff0046e77b8: 'context_return', 0xfffffff0046e6a38: 'verifier_call',
           0xfffffff0046e6a3c: 'verifier_return', 0xfffffff0046f6908: 'native_digest_call',
           0xfffffff0046f690c: 'native_digest_return',
           0xfffffff0046f6824: 'verifier_entry', 0xfffffff0046f6968: 'certificate_call',
           0xfffffff0046f7cf8: 'certificate_entry', 0xfffffff0046f696c: 'certificate_return',
           0xfffffff0046f69bc: 'signature_call', 0xfffffff0046f6f10: 'signature_entry',
           0xfffffff0046f69c0: 'signature_return'}
MEM, FW, EXEC, PB, MB, PAY, MAN = 0x3000000, 0x3000000, 0x3001000, 0x3001100, 0x3001120, 0x3010000, 0x3030000
IM4P_SHA384 = '6aa93bf357fd7a96470428b72cd736062688cff7dbc5683ce7ef542426bd1348a43fbbdf55c8907af17dac02e74b8b89'
HELPER = 0xfffffff0046ef814
DIGEST_CALLBACK = 0xfffffff0046f85e0
DIGEST_CACHES = {0xfffffff005cb06d0: (0xfffffff0046ef824, 0xfffffff005ca82b0),
                 0xfffffff005cb06d8: (0xfffffff0046ef830, 0xfffffff005ca6f00)}
BASELINE_CERT_SHA = '5b6dbcbe8868cc61f504fbdddb5684dfca7323d86682b4fd1c36cf4a09681015'
BASELINE_KEY_SHA = '39c75ab3d5c60185cdc3e929a2fa5731019b7bbd4300732773af586d3ae23b27'
ALLOC_ENTRY = 0xfffffff0078a9e98
WORKSPACE_CALL = 0xfffffff0046d45a0
ALLOC_SOURCE = (0xfffffff00469f868, 0xfffffff0046d89a4, 0xfffffff0046d89a8, 0xfffffff0046d89ac)
FREE_ENTRY = 0xfffffff0078a9ec0


class LedgerViolation(Exception):
    pass


class DataLedger:
    """One observed request only. Host alignment/poison are fixture policy."""
    PAGE, BASE, SIZE, POISON = 4096, 0x4000000, 2584, 0xa5

    def __init__(self, u, oom=False):
        self.u, self.oom = u, oom
        self.ptr = self.BASE + 0x100  # Host fixture alignment, not donor guarantee.
        self.attempts, self.live, self.freed = 0, False, False
        self.events, self.writers = [], {}
        self.stage, self.coverage = 'operation', {}
        self.accesses = {'read': 0, 'write': 0}
        u.hook_add(unicorn.UC_HOOK_MEM_READ | unicorn.UC_HOOK_MEM_WRITE | unicorn.UC_HOOK_MEM_FETCH, self.memory)
        u.hook_add(unicorn.UC_HOOK_MEM_INVALID, self.invalid)

    def need(self, condition, reason):
        if not condition:
            raise LedgerViolation(reason)

    def allocate(self, size):
        self.need(not self.live, 'overlapping/live allocation')
        self.need(self.attempts == 0, 'allocation count/total budget exceeded')
        self.need(size == self.SIZE, 'unsupported allocation size')
        self.attempts += 1
        if self.oom:
            self.events.append(dict(kind='OOM', request=size, successful_allocations=0))
            return 0
        self.u.mem_map(self.BASE, self.PAGE)
        self.u.mem_write(self.BASE, bytes([self.POISON]) * self.PAGE)
        self.live = True
        self.events.append(dict(kind='allocate', pointer=hex(self.ptr), request=size,
                                alignment=16, poison=self.POISON, count_limit=1,
                                single_limit=self.SIZE, total_limit=self.SIZE))
        return self.ptr

    def access(self, kind, address, size, pc):
        if address + size <= self.BASE or address >= self.BASE + self.PAGE:
            return
        self.need(self.live, 'use after free/no live allocation')
        self.need(kind != 'fetch', 'execution from Data region')
        self.need(self.ptr <= address and address + size <= self.ptr + self.SIZE,
                  'request bounds/guard/page-padding access')
        self.accesses[kind] += 1
        if kind == 'write':
            lo, hi = address - self.ptr, address + size - self.ptr
            self.coverage.setdefault(self.stage, set()).update(range(lo, hi))
            writer = self.writers.setdefault(hex(pc), dict(count=0, min_offset=lo, max_end=hi))
            writer['count'] += 1
            writer['min_offset'], writer['max_end'] = min(writer['min_offset'], lo), max(writer['max_end'], hi)

    def memory(self, u, access, address, size, value, data):
        kind = 'write' if access == unicorn.UC_MEM_WRITE else ('fetch' if access == unicorn.UC_MEM_FETCH else 'read')
        self.access(kind, address, size, u.reg_read(UC_ARM64_REG_PC))

    def invalid(self, u, access, address, size, value, data):
        if self.BASE - self.PAGE <= address < self.BASE + 2*self.PAGE:
            raise LedgerViolation('unmapped guard/UAF/protection access at ' + hex(address))
        return False

    def guards(self):
        raw = bytes(self.u.mem_read(self.BASE, self.PAGE))
        off = self.ptr - self.BASE
        self.need(raw[:off] == bytes([self.POISON])*off and
                  raw[off+self.SIZE:] == bytes([self.POISON])*(self.PAGE-off-self.SIZE),
                  'guard/canary/page-padding corruption')

    def finish_zero(self, stage):
        self.guards()
        self.need(bytes(self.u.mem_read(self.ptr, self.SIZE)) == bytes(self.SIZE), 'native zeroization incomplete')
        self.need(len(self.coverage.get(stage, set())) == self.SIZE,
                  'native zero-write coverage incomplete (including possible DCZVA limitation)')
        self.events.append(dict(kind=stage, native_zero=True, native_written_bytes=self.SIZE))
        self.stage = 'operation'

    def free(self, pointer, size):
        self.need(not self.freed, 'double free')
        self.need(self.live, 'free without allocation')
        self.need(pointer == self.ptr, 'interior/foreign free')
        self.need(size == self.SIZE, 'wrong free request size')
        self.need(len(self.coverage.get('workspace_clear', set())) == self.SIZE,
                  'free without complete native clear write coverage')
        self.guards()
        raw = bytes(self.u.mem_read(pointer, size))
        self.need(raw == bytes(size), 'free before native zeroization')
        self.events.append(dict(kind='free', pointer=hex(pointer), original_request=size,
                                native_all_zero=True, native_content_hex=raw.hex(),
                                content_sha256=digest(raw), guards_intact=True))
        self.u.mem_protect(self.BASE, self.PAGE, unicorn.UC_PROT_NONE)
        self.live, self.freed = False, True
        # Explicit host-after-free hygiene, not evidence of native clearing.
        self.u.mem_write(pointer, bytes(size))
        self.events.append(dict(kind='host_after_free_cleanup', native=False, permissions='NONE'))

    def record(self):
        return dict(attempts=self.attempts, live=self.live, freed=self.freed, oom=self.oom,
                    events=self.events, accesses=self.accesses, writers=self.writers,
                    native_write_coverage={k: len(v) for k,v in self.coverage.items()})


def ledger_selftest():
    """Isolated model negatives, NOT donor authentication negatives."""
    checks = []
    def model():
        return DataLedger(unicorn.Uc(unicorn.UC_ARCH_ARM64, unicorn.UC_MODE_ARM))
    def rejects(label, action):
        try:
            action()
        except LedgerViolation:
            checks.append(label)
        else:
            raise AssertionError('Ledger false positive: ' + label)
    m = model(); p = m.allocate(m.SIZE)
    assert p % 16 == 0 and bytes(m.u.mem_read(p, m.SIZE)) == bytes([m.POISON])*m.SIZE
    m.access('read', p, m.SIZE, 0)
    rejects('overrun', lambda: m.access('write', p+m.SIZE-1, 2, 0))
    rejects('underrun', lambda: m.access('read', p-1, 1, 0))
    rejects('page padding', lambda: m.access('read', p+m.SIZE+32, 1, 0))
    rejects('overlap', lambda: m.allocate(m.SIZE))
    rejects('wrong size', lambda: m.free(p, m.SIZE-1))
    rejects('interior free', lambda: m.free(p+16, m.SIZE))
    m.stage = 'workspace_clear'; m.access('write', p, m.SIZE, 0)  # Isolated coverage precondition.
    rejects('nonzero free', lambda: m.free(p, m.SIZE))
    m.u.mem_write(p, bytes(m.SIZE))  # Isolated test preparation, never donor evidence.
    m.free(p, m.SIZE)
    rejects('double free', lambda: m.free(p, m.SIZE))
    rejects('UAF', lambda: m.access('read', p, 1, 0))
    rejects('allocation count budget', lambda: m.allocate(m.SIZE))
    x = model(); rejects('single request limit', lambda: x.allocate(x.SIZE+1))
    x.allocate(x.SIZE); x.u.mem_write(x.ptr-1, b'x')
    rejects('canary damage', x.guards)
    x = model(); x.allocate(x.SIZE); x.u.mem_write(x.ptr, bytes(x.SIZE))
    rejects('missing native write coverage', lambda: x.finish_zero('initial_bzero'))
    print(json.dumps(dict(status='self-checked', scope=ledger_selftest.__doc__, checks=checks)))


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def tlv(tag, value):
    n = len(value)
    length = bytes([n]) if n < 128 else bytes([0x80 | ((n.bit_length()+7)//8)]) + n.to_bytes((n.bit_length()+7)//8, 'big')
    return tag + length + value


def sequence(*values):
    return tlv(b'\x30', b''.join(values))


def setof(*values):
    return tlv(b'\x31', b''.join(sorted(values)))


def ia5(value):
    return tlv(b'\x16', value.encode('ascii'))


def property4(name, value):
    number = int.from_bytes(name.encode('ascii'), 'big')
    groups = [number & 127]
    number >>= 7
    while number:
        groups.append((number & 127) | 128)
        number >>= 7
    return tlv(b'\xff' + bytes(reversed(groups)), sequence(ia5(name), value))


def manifest_der(payload, certificate):
    # Self-authored MANP is an empty property SET, not guessed board identity.
    manp = property4('MANP', setof())
    trst = property4('trst', setof(property4('DGST', tlv(b'\x04', hashlib.sha384(payload).digest()))))
    manb = property4('MANB', setof(manp, trst))
    return sequence(ia5('IM4M'), tlv(b'\x02', b'\0'), setof(manb),
                    tlv(b'\x04', bytes(256)), sequence(certificate))


def der_item(raw, at=0):
    """Bounded DER reader for certificate fields; not an Image4 validator."""
    H.require(at + 2 <= len(raw), 'Truncated DER header')
    tag, size = raw[at], raw[at + 1]
    H.require(tag & 31 != 31, 'Unexpected high tag in certificate field')
    start = at + 2
    if size & 128:
        count = size & 127
        H.require(0 < count <= 4 and start + count <= len(raw) and raw[start] != 0, 'Invalid DER length')
        size = int.from_bytes(raw[start:start + count], 'big')
        H.require(size >= 128, 'Non-minimal DER length')
        start += count
    H.require(start + size <= len(raw), 'DER content exceeds input')
    return tag, start, start + size


def der_fields(raw):
    tag, start, end = der_item(raw)
    H.require(tag == 0x30 and end == len(raw), 'Expected complete certificate SEQUENCE')
    fields = []
    while start < end:
        _, _, stop = der_item(raw, start)
        fields.append(raw[start:stop])
        start = stop
    return fields


def issuer_negative(raw, macho, baseline, key, work):
    """Change only Issuer in the original own-key certificate, then re-sign it.

    Native root data are read from pinned input; no Apple certificate is embedded
    in source or added to a trust store. The result is deliberately NOT trusted.
    """
    root_address, root_length_slot = 0xfffffff003e1aa30, 0xfffffff003e1af90
    root_length = struct.unpack('<Q', A.backed_bytes(raw, macho, root_length_slot, 8))[0]
    H.require(root_length == 1374, 'Pinned native root length changed')
    root = A.backed_bytes(raw, macho, root_address, root_length)
    root_tbs = der_fields(der_fields(root)[0])
    H.require(root_tbs[0][0] == 0xa0, 'Expected explicit root certificate version')
    subject = root_tbs[5]
    _, name_start, name_end = der_item(subject)
    H.require(name_end - name_start == 75, 'Native root Subject content length changed')
    cert = der_fields(baseline)
    tbs = der_fields(cert[0])
    H.require(len(cert) == 3 and tbs[0][0] == 0xa0, 'Unexpected baseline certificate layout')
    _, old_start, old_end = der_item(tbs[3])
    H.require(old_end - old_start == 42 and tbs[3] == tbs[5], 'Unexpected baseline Issuer/Subject')
    old_issuer = tbs[3]
    tbs[3] = subject
    new_tbs = sequence(*tbs)
    (work / 'own-tbs.der').write_bytes(new_tbs)
    (work / 'native-root-subject-name.der').write_bytes(subject)
    commands = []
    for command in [
        ['/usr/bin/openssl', 'pkey', '-in', str(key), '-pubout', '-outform', 'DER', '-out', str(work / 'own-public.der')],
        ['/usr/bin/openssl', 'dgst', '-sha384', '-sign', str(key), '-out', str(work / 'own-cert-signature.bin'), str(work / 'own-tbs.der')]]:
        completed = subprocess.run(command, capture_output=True, text=True)
        commands.append(dict(argv=command, exit_code=completed.returncode))
        H.require(completed.returncode == 0, 'Own-key certificate command failed: ' + completed.stderr)
    H.require((work / 'own-public.der').read_bytes() == tbs[6], 'Key is not the baseline certificate key')
    result = sequence(new_tbs, cert[1], tlv(b'\x03', b'\0' + (work / 'own-cert-signature.bin').read_bytes()))
    after = der_fields(der_fields(result)[0])
    before = der_fields(cert[0])
    H.require(len(after) == len(before) and all(after[i] == before[i] for i in range(len(before)) if i != 3)
              and after[3] == subject and cert[1] == der_fields(result)[1], 'Non-Issuer certificate field changed')
    return result, commands, dict(root_address=hex(root_address), root_length=root_length,
                                  tbs_schema=hex(0xfffffff003e1d6c8),
                                  original_issuer_content_length=42, new_issuer_content_length=75,
                                  old_issuer_sha256=digest(old_issuer), new_issuer_sha256=digest(subject),
                                  unchanged_tbs_fields_except_issuer=True, baseline_public_key_retained=True,
                                  trust='Own key signed; matching Issuer Name does NOT confer Apple trust')


def bindings(raw, macho):
    proof = P.bind(raw, macho)
    for offset, target in ENTRIES.items():
        value = struct.unpack('<Q', A.backed_bytes(raw, macho, P.TABLE + offset, 8))[0]
        H.require(value == target, 'Firmware interface changed: ' + hex(offset))
    for address, target in {0xfffffff005cb48f8: 0xfffffff0046f7cf8,
                            0xfffffff005cb4900: 0xfffffff0046f6f10,
                            0xfffffff005cab9d8: 0xfffffff0046cf6ec,
                            0xfffffff005cab9e0: 0xfffffff0046d76e8}.items():
        H.require(struct.unpack('<Q', A.backed_bytes(raw, macho, address, 8))[0] == target,
                  'Native chip security callback binding changed')
    md = capstone.Cs(capstone.CS_ARCH_ARM64, 0)
    H.require(macho['symbols']['_IOMallocData_external'] == ALLOC_ENTRY and
              struct.unpack('<Q', A.backed_bytes(raw, macho, 0xfffffff005ca6888, 8))[0] == ALLOC_ENTRY,
              'IOMallocData_external symbol/GOT binding changed')
    H.require(macho['symbols']['_IOFreeData'] == FREE_ENTRY and
              struct.unpack('<Q', A.backed_bytes(raw, macho, 0xfffffff005ca6880, 8))[0] == FREE_ENTRY and
              macho['symbols']['_bzero'] == 0xfffffff00799f8c0 and
              macho['symbols']['_memset_s'] == 0xfffffff00799ee60,
              'Data free/native zeroizer binding changed')
    i = next(md.disasm(A.backed_bytes(raw, macho, ALLOC_SOURCE[0], 4), ALLOC_SOURCE[0]))
    H.require(i.mnemonic == 'bl' and int(i.op_str[1:], 16) == ALLOC_SOURCE[1], 'Allocator source BL changed')
    thunk = list(md.disasm(A.backed_bytes(raw, macho, ALLOC_SOURCE[1], 12), ALLOC_SOURCE[1]))
    H.require([(i.mnemonic, i.op_str) for i in thunk] ==
              [('adrp', 'x16, #0xfffffff005ca6000'), ('ldr', 'x16, [x16, #0x888]'), ('br', 'x16')],
              'Allocator thunk/GOT provenance changed')
    public_key = der_fields(A.backed_bytes(raw, macho, 0xfffffff003e1ab28, 526))
    tag, start, end = der_item(public_key[0])
    modulus = public_key[0][start:end]
    H.require(tag == 2 and len(modulus) == 513 and modulus[0] == 0, 'Pinned root modulus encoding changed')
    nbytes = len(modulus.lstrip(b'\0'))
    static_n = (nbytes + 7) >> 3
    proof['allocator_provenance'] = dict(source_chain=[hex(p) for p in ALLOC_SOURCE],
                                        got=hex(0xfffffff005ca6888), target=hex(ALLOC_ENTRY),
                                        static_expectation=dict(origin='pinned DER only; not runtime sampling',
                                                                modulus_integer_length=len(modulus), stripped_nbytes=nbytes,
                                                                n=static_n, capacity=5*static_n+3, request=40*static_n+24))
    for pc, target in {0xfffffff0046f1418: HELPER, 0xfffffff0046f141c: 0xfffffff0046e4a28,
                       0xfffffff0046ef81c: 0xfffffff0046f9e54,
                       0xfffffff0046ef828: 0xfffffff0046f9e60}.items():
        i = next(md.disasm(A.backed_bytes(raw, macho, pc, 4), pc))
        H.require(i.mnemonic == 'bl' and int(i.op_str[1:], 16) == target, 'Digest helper call edge changed')
    desc = struct.unpack('<8Q', A.backed_bytes(raw, macho, 0xfffffff005ca6f00, 64))
    H.require(desc[:4] == (48, 64, 128, 11) and desc[6:] == (0xfffffff0046a8c90, 0xfffffff0046d3d44)
              and A.backed_bytes(raw, macho, desc[4], 11).hex() == '0609608648016503040202',
              'SHA384 descriptor binding changed')
    proof['digest_helper'] = dict(entry=hex(HELPER), caches={hex(k): hex(v[1]) for k,v in DIGEST_CACHES.items()},
                                 sha384_descriptor=hex(0xfffffff005ca6f00), output_size=48, state_size=64,
                                 block_size=128, oid='0609608648016503040202',
                                 compress=hex(desc[6]), final=hex(desc[7]))
    proof['firmware_entries'] = {hex(k): hex(v) for k, v in ENTRIES.items()}
    proof['native_schema'] = hex(0xfffffff003e195a0)
    proof['schema_parser'] = hex(0xfffffff0046f3abc)
    for pc, size in [(0xfffffff0046e7688, 0x134), (0xfffffff0046e6a24, 0x18),
                     (0xfffffff0046f6948, 0x7c), (0xfffffff0046f85e0, 0x70),
                     (HELPER, 0x28), (0xfffffff0046f9e54, 0x18),
                     (0xfffffff0046cf6ec, 12), (0xfffffff0046d76e8, 12),
                     (WORKSPACE_CALL - 0x10, 0x18), (ALLOC_SOURCE[0], 4), (ALLOC_SOURCE[1], 12),
                     (0xfffffff00469f874, 16), (0xfffffff00469f95c, 0x1c),
                     (0xfffffff0046d8998, 12), (0xfffffff0046b6a98, 16)]:
        proof['windows'][hex(pc)] = [dict(pc=hex(i.address), mnemonic=i.mnemonic, operands=i.op_str)
                                     for i in md.disasm(A.backed_bytes(raw, macho, pc, size), pc)]
    return proof


class Evaluation:
    def __init__(self, raw, macho, adt, payload, manifest, allocator_mode='observe'):
        # Continuous original initialization, not an injected runtime snapshot.
        # BNCH is explicitly an experimental CSPRNG session input in memory.
        token = secrets.token_bytes(48)
        self.nodes = A.parse_adt(H.variant(adt, token))
        self.model = A.Model(raw, macho, self.nodes)
        self.u = self.model.u
        self.phase, self.coverage, self.stubs, self.events, self.calls = 'setup', {}, [], [], []
        self.slot_writes, self.blocked = [], None
        self.helper_writes, self.digest_calls, self.digest_pending = [], [], []
        self.workspace_breadcrumb, self.allocation_observation = None, None
        self.allocation_observations = []
        self.allocator_mode = allocator_mode
        self.ledger = DataLedger(self.u, oom=allocator_mode == 'oom') if allocator_mode != 'observe' else None
        self.resource_failure, self.zero_pending, self.workspace_closed = None, None, False
        self.signature_pending, self.signature_results = [], []
        self.sync = {v: k for k, v in macho['symbols'].items()
                     if k in ('_lck_spin_lock', '_lck_mtx_lock', '_lck_rw_lock_exclusive', '_lck_rw_lock_shared')}
        self.log = self.model.get64(A.PMAP_RUNTIME + 0x28)
        self.u.hook_add(unicorn.UC_HOOK_CODE, self.watch)
        self.u.hook_add(unicorn.UC_HOOK_MEM_WRITE, self.write)
        tree = 0xe00000
        # Map the same BNCH-only variant used to construct modeled objects.
        treebytes = H.variant(adt, token)
        self.u.mem_map(tree, A.B.align(len(treebytes)))
        self.u.mem_write(tree, treebytes)
        self.u.mem_map(MEM, 0x50000)
        self.u.mem_write(PAY, payload)
        self.u.mem_write(MAN, manifest)
        self.u.mem_write(EXEC, struct.pack('<3Q', 1, 0, 0))
        self.u.mem_write(PB, struct.pack('<4Q', 0, PAY, len(payload), 0))
        self.u.mem_write(MB, struct.pack('<4Q', 0, MAN, len(manifest), 0))
        self.setup = (macho['symbols']['_SecureDTInit'], tree, len(treebytes))

    def write(self, u, access, address, size, value, data):
        for slot, (expected_pc, expected_value) in DIGEST_CACHES.items():
            if address < slot + 8 and address + size > slot:
                value &= (1 << 64) - 1
                H.require(self.phase == 'digest descriptor helper' and address == slot and size == 8
                          and u.reg_read(UC_ARM64_REG_PC) == expected_pc and value == expected_value,
                          'Unexpected digest descriptor cache write')
                self.helper_writes.append(dict(pc=hex(expected_pc), slot=hex(slot), descriptor=hex(value)))
        if address < P.SLOT + 8 and address + size > P.SLOT:
            value &= (1 << 64) - 1
            H.require(self.phase == 'registration' and u.reg_read(UC_ARM64_REG_PC) == P.REGISTER + 12
                      and address == P.SLOT and size == 8 and value == P.TABLE, 'Unexpected interface slot write')
            self.slot_writes.append(dict(pc=hex(P.REGISTER + 12), value=hex(value)))

    def watch(self, u, pc, size, data):
        self.coverage.setdefault(self.phase, set()).add(pc)
        if pc == WORKSPACE_CALL:
            ctx = u.reg_read(UC_ARM64_REG_X19)
            self.workspace_breadcrumb = dict(pc=hex(pc), x0=u.reg_read(UC_ARM64_REG_X0),
                                             x19=hex(ctx), ctx_first_qword=self.model.get64(ctx))
        if pc == ALLOC_ENTRY:
            sp = u.reg_read(UC_ARM64_REG_SP)
            request, saved = u.reg_read(UC_ARM64_REG_X0), u.reg_read(UC_ARM64_REG_X19)
            lr, workspace_lr = u.reg_read(UC_ARM64_REG_LR), self.model.get64(sp + 0x18)
            ctx = self.model.get64(sp + 8)
            approved_ctx = (workspace_lr == WORKSPACE_CALL + 4 and lr == ALLOC_SOURCE[0] + 4
                            and request == DataLedger.SIZE and self.workspace_breadcrumb is not None
                            and self.workspace_breadcrumb['x19'] == hex(ctx))
            # A different caller's saved X19 is NOT a pubkey-context contract.
            n = self.model.get64(ctx) if approved_ctx else None
            limit = (1 << 64) - 1
            capacity, formula = (5*n + 3, 40*n + 24) if n is not None else (None, None)
            safe = None if n is None else (n <= (limit - 3)//5 and n <= (limit - 24)//40 and capacity <= limit//8)
            checks = dict(overflow_safe=safe, request_matches_formula=safe and request == formula,
                          saved_request_matches=saved == request, lr_matches=lr == ALLOC_SOURCE[0] + 4,
                          workspace_lr_matches=workspace_lr == WORKSPACE_CALL + 4,
                          source_chain_visited=all(p in self.coverage[self.phase] for p in ALLOC_SOURCE))
            self.allocation_observation = dict(pc=hex(pc), before_first_instruction=True,
                                               request_x0=request, saved_request_x19=saved, lr=hex(lr), sp=hex(sp),
                                               workspace_lr_sp18=hex(workspace_lr), caller_ctx_sp08=hex(ctx),
                                               ctx_n=n, capacity_from_runtime_n=capacity,
                                               request_from_runtime_n=formula, checks=checks,
                                               breadcrumb=self.workspace_breadcrumb)
            self.allocation_observations.append(self.allocation_observation)
            if self.allocator_mode != 'observe':
                supported = (all(checks.values()) and n == 64 and request == DataLedger.SIZE and
                             self.workspace_breadcrumb is not None and
                             self.workspace_breadcrumb['x19'] == hex(ctx) and
                             self.workspace_breadcrumb['ctx_first_qword'] == n)
                if not supported or self.ledger.attempts != 0:
                    self.blocked = dict(phase=self.phase, pc=hex(pc), boundary='new allocation source/size/count/purpose; not admitted')
                    u.emu_stop(); return
                pointer = self.ledger.allocate(request)
                self.stubs.append(dict(phase=self.phase, pc=hex(pc), boundary='bounded Data allocation ABI',
                                       request=request, result=hex(pointer), mode=self.allocator_mode))
                u.reg_write(UC_ARM64_REG_X0, pointer)
                u.reg_write(UC_ARM64_REG_PC, lr)
                return
            self.blocked = dict(phase=self.phase, pc=hex(pc),
                                boundary='IOMallocData_external entry; observation complete, allocator NOT executed',
                                observation_complete=all(checks.values()))
            u.emu_stop()
            return
        if self.ledger:
            if pc == FREE_ENTRY:
                ptr, size = u.reg_read(UC_ARM64_REG_X0), u.reg_read(UC_ARM64_REG_X1)
                lr = u.reg_read(UC_ARM64_REG_LR)
                self.ledger.need(lr == 0xfffffff00469f968 and
                                 all(p in self.coverage[self.phase] for p in
                                     (0xfffffff00469f964, 0xfffffff00469f768, 0xfffffff00469f7d0,
                                      0xfffffff00469f7e0, 0xfffffff0046d8998)), 'unapproved free provenance')
                self.ledger.free(ptr, size)
                self.stubs.append(dict(phase=self.phase, pc=hex(pc), boundary='bounded Data free ABI',
                                       pointer=hex(ptr), original_request=size, lr=hex(lr), result_kind='void'))
                u.reg_write(UC_ARM64_REG_PC, lr)  # Void free: no fabricated security return.
                return
            if self.zero_pending and pc == self.zero_pending[1]:
                self.events.append(dict(phase=self.phase, pc=hex(pc), boundary='native zeroizer return',
                                        stage=self.zero_pending[0], raw_x0=u.reg_read(UC_ARM64_REG_X0),
                                        result_kind='void' if self.zero_pending[0] == 'initial_bzero' else 'memset_s native status'))
                self.ledger.finish_zero(self.zero_pending[0])
                self.zero_pending = None
            if pc == 0xfffffff00799f8c0 and u.reg_read(UC_ARM64_REG_X0) == self.ledger.ptr and self.ledger.live:
                if u.reg_read(UC_ARM64_REG_LR) == 0xfffffff00469f880:
                    self.ledger.need(u.reg_read(UC_ARM64_REG_X1) == self.ledger.SIZE, 'initial bzero length mismatch')
                    self.ledger.need(bytes(u.mem_read(self.ledger.ptr, self.ledger.SIZE)) ==
                                     bytes([self.ledger.POISON])*self.ledger.SIZE, 'allocation was pre-cleared')
                    self.ledger.stage = 'initial_bzero'
                    self.zero_pending = ('initial_bzero', u.reg_read(UC_ARM64_REG_LR))
                    self.events.append(dict(phase=self.phase, pc=hex(pc), boundary='original bzero entry',
                                            pointer=hex(self.ledger.ptr), size=self.ledger.SIZE, initial_poison=True))
            if pc == 0xfffffff00799ee60 and u.reg_read(UC_ARM64_REG_X0) == self.ledger.ptr and self.ledger.live:
                args = [u.reg_read(r) for r in (UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X2, UC_ARM64_REG_X3)]
                self.ledger.need(args == [self.ledger.ptr, self.ledger.SIZE, 0, self.ledger.SIZE], 'native memset_s ABI mismatch')
                self.ledger.stage = 'workspace_clear'
                self.zero_pending = ('workspace_clear', u.reg_read(UC_ARM64_REG_LR))
                self.events.append(dict(phase=self.phase, pc=hex(pc), boundary='original memset_s entry', args=args))
            if pc == 0xfffffff0046d45d4:
                ws = u.reg_read(UC_ARM64_REG_SP) + 8
                fields = [self.model.get64(ws + 8*i) for i in range(6)]
                self.ledger.need(fields == [0 if self.ledger.oom else self.ledger.ptr, 323, 0,
                                           0xfffffff00469f8b4, 0xfffffff00469f8f8, 0xfffffff00469f934],
                                 'unexpected original workspace initialization')
                self.events.append(dict(phase=self.phase, pc=hex(pc), boundary='native workspace initialized',
                                        pointer=hex(ws), fields=fields))
            if pc in (0xfffffff00469f968, 0xfffffff00469f96c, 0xfffffff00469f970):
                ws = u.reg_read(UC_ARM64_REG_X19)
                fields = [self.model.get64(ws + 8*i) for i in range(3)]
                self.events.append(dict(phase=self.phase, pc=hex(pc), boundary='native workspace field cleanup', fields=fields))
                if pc == 0xfffffff00469f970:
                    self.ledger.need(fields == [0, 0, 0], 'native workspace fields not cleared')
                    self.workspace_closed = True
            if pc in (0xfffffff00469f870, 0xfffffff00469f880, 0xfffffff0046d4604,
                      0xfffffff0046d4608, 0xfffffff0046d4630):
                w19 = u.reg_read(UC_ARM64_REG_X19) & 0xffffffff
                self.events.append(dict(phase=self.phase, pc=hex(pc), boundary='native allocation/OOM propagation',
                                        x0=u.reg_read(UC_ARM64_REG_X0), raw_w19=w19,
                                        internal_signed_w19=w19-(1<<32) if w19 & (1<<31) else w19))
        if self.signature_pending and pc == self.signature_pending[-1]['return_pc']:
            sig = self.signature_pending.pop()
            sig.update(returned=True, native_return=u.reg_read(UC_ARM64_REG_X0))
        if pc == 0xfffffff0046f6f10:
            sig = dict(entry=hex(pc), return_pc=u.reg_read(UC_ARM64_REG_LR), returned=False,
                       args=[hex(u.reg_read(UC_ARM64_REG_X0+i)) for i in range(8)])
            self.signature_results.append(sig); self.signature_pending.append(sig)
        if self.digest_pending and pc == self.digest_pending[-1]['return_pc']:
            call = self.digest_pending.pop()
            call['native_return'] = u.reg_read(UC_ARM64_REG_X0)
            call['returned'] = True
            if call['native_return'] == 0:
                actual = bytes(u.mem_read(call['output_pointer'], call['output_length'])).hex()
                call['native_output_hex'] = actual
                call['host_sha384_equal'] = actual == call['host_sha384_hex']
                H.require(call['host_sha384_equal'], 'Native/host SHA384 mismatch; no output was replaced')
        if pc == DIGEST_CALLBACK:
            pointer, length = u.reg_read(UC_ARM64_REG_X0), u.reg_read(UC_ARM64_REG_X1)
            output, output_len = u.reg_read(UC_ARM64_REG_X2), u.reg_read(UC_ARM64_REG_X3)
            H.require(0 < length <= 0x20000 and output_len == 48, 'Unexpected native SHA384 callback bounds')
            call = dict(entry_pc=hex(pc), input_pointer=hex(pointer), input_length=length,
                        output_pointer=output, output_length=output_len,
                        return_pc=u.reg_read(UC_ARM64_REG_LR), returned=False,
                        host_sha384_hex=hashlib.sha384(bytes(u.mem_read(pointer, length))).hexdigest())
            self.digest_calls.append(call)
            self.digest_pending.append(call)
        if pc in self.model.hooks:
            self.stubs.append(dict(phase=self.phase, pc=hex(pc), boundary=self.model.hooks[pc]))
        if pc == self.log:
            self.stubs.append(dict(phase=self.phase, pc=hex(pc), boundary='pure PMAP runtime log'))
            u.reg_write(UC_ARM64_REG_X0, 0)
            u.reg_write(UC_ARM64_REG_PC, u.reg_read(UC_ARM64_REG_LR))
        if pc in OBSERVE:
            event = dict(phase=self.phase, pc=hex(pc), boundary=OBSERVE[pc], x0=u.reg_read(UC_ARM64_REG_X0))
            if OBSERVE[pc] in ('certificate_call', 'signature_call'):
                event['actual_target_x8'] = hex(u.reg_read(UC_ARM64_REG_X8))
            if pc in (0xfffffff0046f7a30, 0xfffffff0046f7a34):
                sp = u.reg_read(UC_ARM64_REG_SP)
                index = u.reg_read(UC_ARM64_REG_X21)
                entry = u.reg_read(UC_ARM64_REG_X19) + index * 0xa0
                event.update(root_subject_pointer=hex(self.model.get64(sp + 0x138)),
                             root_subject_length=u.reg_read(UC_ARM64_REG_X2),
                             issuer_pointer=hex(self.model.get64(entry + 0x100)),
                             issuer_length=u.reg_read(UC_ARM64_REG_X8), index=index,
                             nzcv=u.reg_read(UC_ARM64_REG_NZCV))
            if pc == 0xfffffff0046f7a6c:
                args = [u.reg_read(reg) for reg in (UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X2)]
                event['actual_arguments'] = [hex(v) for v in args]
                event['argument_structures_hex'] = [bytes(u.mem_read(v, 0xa0)).hex() for v in args]
            self.events.append(event)
        if pc == 0xfffffff0046f8620:
            slot = u.reg_read(UC_ARM64_REG_X9)
            self.events.append(dict(phase=self.phase, pc=hex(pc), boundary='native_digest_descriptor_cache',
                                    slot=hex(slot), value=hex(self.model.get64(slot))))
        if pc == 0xfffffff0046f8624 and u.reg_read(UC_ARM64_REG_X0) == 0:
            self.blocked = dict(phase=self.phase, pc=hex(pc),
                                boundary='native digest descriptor cache NULL in constructed state; no certificate/signature rejection',
                                descriptor_cache_slot=hex(u.reg_read(UC_ARM64_REG_X9)), descriptor=0)
            u.emu_stop()
        if pc in self.sync or pc in (H.PANIC, 0xfffffff0046ea69c, 0xfffffff0046e5268):
            self.blocked = dict(phase=self.phase, pc=hex(pc), boundary=self.sync.get(pc, 'panic/install/execute forbidden in evaluation'))
            u.emu_stop()

    def call(self, name, entry, args, void=False, budget=1000000):
        if self.blocked:
            return None
        self.phase = name
        for i, value in enumerate(args):
            self.u.reg_write(UC_ARM64_REG_X0 + i, value)
        self.u.reg_write(UC_ARM64_REG_SP, A.STACK + 0x8000)
        self.u.reg_write(UC_ARM64_REG_LR, A.STOP)
        try:
            self.u.emu_start(entry, A.STOP, count=budget)
        except LedgerViolation as exc:
            self.resource_failure = str(exc)
            self.blocked = dict(phase=name, pc=hex(self.u.reg_read(UC_ARM64_REG_PC)), boundary='Data resource/model violation', error=str(exc))
        except unicorn.UcError as exc:
            self.blocked = dict(phase=name, pc=hex(self.u.reg_read(UC_ARM64_REG_PC)),
                                boundary='unmet memory/emulator state', error=str(exc), invalid_memory=self.model.bad)
        pc = self.u.reg_read(UC_ARM64_REG_PC)
        if self.blocked:
            self.calls.append(dict(name=name, entry=hex(entry), args=[hex(v) for v in args],
                                   returned=False, terminal_pc=hex(pc), result_kind='BLOCKED; no return errno'))
            return None
        if pc != A.STOP:
            self.blocked = dict(phase=name, pc=hex(pc), boundary='instruction budget exhausted')
            return None
        value = self.u.reg_read(UC_ARM64_REG_X0)
        self.calls.append(dict(name=name, entry=hex(entry), args=[hex(v) for v in args],
                               returned=True, terminal_pc=hex(pc), raw_x0=value,
                               result_kind='void; X0 is not errno' if void else 'native return'))
        return value

    def run(self):
        entry, tree, size = self.setup
        self.call('SecureDT setup', entry, (tree, size))
        if not self.blocked:
            H.require(all(self.model.get64(slot) == 0 for slot in DIGEST_CACHES),
                      'Digest descriptor caches must begin NULL')
            self.call('digest descriptor helper', HELPER, (), void=True, budget=1000)
            if not self.blocked:
                H.require(len(self.helper_writes) == 2 and
                          all(self.model.get64(slot) == expected[1] for slot, expected in DIGEST_CACHES.items())
                          and self.u.reg_read(UC_ARM64_REG_SP) == A.STACK + 0x8000,
                          'Original helper did not initialize both descriptor caches exactly once')
        if not self.blocked:
            self.call('continuous initializer', H.INIT, (A.PMAP_RUNTIME,), void=True)
        if not self.blocked:
            H.require(self.model.get64(P.SLOT) == 0, 'Interface slot must begin NULL')
            self.phase = 'registration'
            self.u.emu_start(P.REG_SITE, P.REG_SITE + 12, count=1000)
            H.require(self.u.reg_read(UC_ARM64_REG_PC) == P.REG_SITE + 12 and
                      self.model.get64(P.SLOT) == P.TABLE and len(self.slot_writes) == 1, 'Native registration failed')
        chip = None
        if not self.blocked:
            chip = self.call('native personalized chip', ENTRIES[0x100], ())
        if not self.blocked:
            fw = self.call('init_from_buff', ENTRIES[0x130], (FW, 0x500))
            if not self.blocked:
                H.require(fw == FW, 'Unexpected firmware storage result')
            self.call('firmware init', ENTRIES[0x138],
                      (fw, A.PMAP_RUNTIME, EXEC, int.from_bytes(b'trst', 'big'), PB, 0), void=True)
            self.call('attach manifest', ENTRIES[0x140], (fw, MB), void=True)
        errno = None
        if not self.blocked:
            errno = self.call('evaluate', ENTRIES[0x1c0], (FW, chip, 0))
        if self.ledger and not self.blocked:
            closed = (self.ledger.attempts == 1 and not self.ledger.live and
                      ((self.ledger.oom and not self.ledger.freed) or
                       (self.ledger.freed and self.workspace_closed and self.zero_pending is None and
                        all(len(self.ledger.coverage.get(stage, set())) == self.ledger.SIZE
                            for stage in ('initial_bzero', 'workspace_clear')))))
            if not closed:
                self.resource_failure = 'normal return with unclosed Data/workspace lifetime'
        reached = {event['boundary']: event['x0'] for event in self.events if 'x0' in event}
        status = 'RESOURCE_FAILURE' if self.resource_failure else ('BLOCKED' if self.blocked else ('UNEXPECTED_ZERO' if errno == 0 else 'self-checked'))
        return dict(status=status, blocked=self.blocked, errno=errno,
                    terminal_pc=hex(self.u.reg_read(UC_ARM64_REG_PC)), chip=hex(chip) if chip else None,
                    nonce=None, flags=0, callback=None, calls=self.calls, events=self.events,
                    slot_writes=self.slot_writes, stubs=self.stubs,
                    helper_writes=self.helper_writes, native_digest_calls=self.digest_calls,
                    allocation_observation=self.allocation_observation,
                    allocation_observations=self.allocation_observations,
                    observed_allocation_requests=len(self.allocation_observations),
                    allocator_mode=self.allocator_mode, data_ledger=self.ledger.record() if self.ledger else None,
                    resource_failure=self.resource_failure, workspace_closed=self.workspace_closed,
                    native_signature_calls=self.signature_results,
                    coverage={name: dict(all_pcs=[hex(p) for p in sorted(pcs)],
                                        donor_pcs=[hex(p) for p in sorted(pcs) if H.DONOR_BEGIN <= p < H.DONOR_END
                                                   and p not in self.model.hooks and p != self.log
                                                   and (not self.blocked or hex(p) != self.blocked['pc'])])
                              for name, pcs in self.coverage.items()},
                    checks={name: reached.get(name, 'NOT REACHED') for name in OBSERVE.values()},
                    invalid_memory=self.model.bad,
                    interpretation='Only observed native boundaries classify rejection; parser/context errors are not signature rejection. Zero is unexpected, never a positive.')


def main():
    if sys.argv[1:] == ['--ledger-self-test']:
        ledger_selftest()
        return
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kernel', type=Path, required=True)
    p.add_argument('--kernel-sha256', required=True)
    p.add_argument('--payload', type=Path, required=True)
    p.add_argument('--payload-sha256', required=True)
    p.add_argument('--adt', type=Path, required=True)
    p.add_argument('--adt-sha256', required=True)
    p.add_argument('--certificate', type=Path, required=True)
    p.add_argument('--certificate-sha256', required=True)
    p.add_argument('--key', type=Path, required=True)
    p.add_argument('--key-sha256', required=True)
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--allocator-mode', choices=('observe', 'ledger', 'oom'), default='observe')
    a = p.parse_args()
    work = a.work.resolve()
    H.require(work.is_relative_to(ROOT / 'out') and not work.exists(), 'Fresh device out/ directory required')
    raw = H.bound_input(a.kernel, a.kernel_sha256, H.KERNEL_SHA, 55357440)
    payload = H.bound_input(a.payload, a.payload_sha256, P.PAYLOAD_SHA, 66289)
    adt = H.bound_input(a.adt, a.adt_sha256, H.ADT_SHA)
    baseline = H.bound_input(a.certificate, a.certificate_sha256, BASELINE_CERT_SHA)
    H.bound_input(a.key, a.key_sha256, BASELINE_KEY_SHA)
    H.require(hashlib.sha384(payload).hexdigest() == IM4P_SHA384, 'Whole IM4P SHA384 mismatch')
    macho = A.B.macho(raw)
    proof = bindings(raw, macho)
    work.mkdir(parents=True)
    certificate, commands, issuer_change = issuer_negative(raw, macho, baseline, a.key, work)
    (work / 'self-authored-cert.der').write_bytes(certificate)
    manifest = manifest_der(payload, certificate)
    (work / 'self-authored.im4m').write_bytes(manifest)
    result = Evaluation(raw, macho, adt, payload, manifest, a.allocator_mode).run()
    report = dict(scope=__doc__, status=result['status'], result=result, binding=proof,
                  inputs=dict(kernel_sha256=H.KERNEL_SHA, adt_sha256=H.ADT_SHA,
                              payload_sha256=P.PAYLOAD_SHA, payload_sha384=IM4P_SHA384,
                              manifest_sha256=digest(manifest), manifest_length=len(manifest),
                              certificate_sha256=digest(certificate), baseline_certificate_sha256=BASELINE_CERT_SHA,
                              retained_own_key_sha256=BASELINE_KEY_SHA),
                  construction='DER sorted SETs, MANP empty, trst DGST over whole IM4P, zero invalid manifest signature, retained own-key certificate with ONLY Issuer changed to pinned native root Subject; NOT Apple signed or trusted',
                  issuer_change=issuer_change,
                  initial_state='file segments plus zero memory, synthetic objects/stack; actual SecureDT, original digest descriptor helper once, and original initializer run continuously using experimental CSPRNG 48-byte BNCH only in memory, not hardware/donor nonce',
                  certificate_commands=commands, harness_sha256=digest(Path(__file__).read_bytes()),
                  dependencies={name: digest((ROOT / 'scripts' / name).read_bytes()) for name in
                                ('research-current-image4-consumer-parse.py', 'research-current-image4-bnch.py',
                                 'audit-image4-runtime-provider.py', 'build-kernel-entry-probe.py', 'nuwa_launch_context.py')},
                  invocation=dict(argv=sys.argv, cwd=str(Path.cwd())),
                  tools=dict(unicorn=unicorn.__version__, capstone=capstone.__version__),
                  signed_trusted_positive=False, device_accessed=False)
    (work / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(status=result['status'], errno=result['errno'], blocked=result['blocked'], checks=result['checks'], report=str(work / 'report.json'))))
    if result['status'] != 'self-checked':
        sys.exit(1 if result['status'] == 'RESOURCE_FAILURE' else 2)


if __name__ == '__main__':
    main()
