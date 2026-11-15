"""Bounded host alias test: real ADT backing -> OSData -> Image4 reader.

The runner starts at the frozen Image4 initializer entry 0xfffffff0046e98cc and
reaches the AMNM/CHMH decision at 0xfffffff0046e9b2c or the original panic
0xfffffff0046fa028. For the AMNM property it returns an OSData object whose
length/data fields are written by the real OSData::initWithBytesNoCopy field
instructions and whose getLength/getBytesNoCopy calls execute the frozen OSData
methods. The object and backing pointer are fixtures; the full
MakeReferenceTable/IOService/OSDictionary/allocator path is not executed.

This is host evidence, not a device, authentication or full-IORegistry result.
No kernel, ADT file, candidate, provider, level or policy is modified.
"""
import argparse
import copy
import gc
import importlib.util
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'out/python-tools')]
import nuwa_launch_context as C


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


A = load('image4_provider', ROOT / 'scripts/audit-image4-runtime-provider.py')
B = A.B
U = A.U

ENTRY = 0xfffffff0046e98cc
DECISION_BOUNDARY = 0xfffffff0046e9b2c
PANIC = 0xfffffff0046fa028
PANIC_SITE_CHMH = 0xfffffff0046e9f64
PANIC_SITE_AMNM = 0xfffffff0046e9f50
EPILOGUE_RET = 0xfffffff0046e9f00
BOOL_READER = 0xfffffff0046efe7c
DIGEST_READER = 0xfffffff0046f021c
HELPER = 0xfffffff0046f07e8
BOOL_CALL = 0xfffffff0046e99d8
BOOL_RETURN = 0xfffffff0046e99dc
BOOL_STORE = 0xfffffff0046effb8
BOOL_INPUT = 0xfffffff0046eff98
DIGEST_CALL = 0xfffffff0046e9ad8
DIGEST_RETURN = 0xfffffff0046e9adc
FINAL_READ = 0xfffffff0046e9b00
FINAL_BRANCH = 0xfffffff0046e9b04
BOOL_OUT = 0xfffffff005cacef0
DIGEST_OBJECT = 0xfffffff005cad030
POLICY_KEY = 'mix-n-match-prevention-status'
HASH_KEY = 'boot-manifest-hash'
AMNM_PANIC_TEXT = 'failed to get mix-n-match policy: %d'
CHMH_PANIC_TEXT = 'failed to get previous stage manifest hash: %d'
TREE_VA = 0xe00000

OSDATA_VTABLE = 0xfffffff0071ac450
OSDATA_INIT_NO_COPY = 0xfffffff007858184
OSDATA_INIT_SLICE = 0xfffffff0078581b4
OSDATA_INIT_SLICE_STOP = 0xfffffff0078581c0
OSDATA_SUPER_INIT = 0xfffffff00785569c
OSDATA_GET_LENGTH = 0xfffffff00785854c
OSDATA_GET_LENGTH_RET = 0xfffffff007858550
OSDATA_GET_BYTES_NO_COPY = 0xfffffff0078588c8
OSDATA_GET_BYTES_RET = 0xfffffff0078588d8
OSDATA_RELEASE = 0xfffffff0078553cc
OSDATA_WITH_BYTES_NO_COPY = 0xfffffff007858324
OSDATA_WITH_BYTES = 0xfffffff0078582ac
MAKE_REFERENCE_TABLE = 0xfffffff0078b009c
MRT_NO_COPY_CALL = 0xfffffff0078b01f4
MRT_COPY_CALL = 0xfffffff0078b01dc
ALIAS_BASE = 0x3000000
ALIAS_SIZE = 0x10000
ALIAS_VTABLE = ALIAS_BASE
ALIAS_OBJECT = ALIAS_BASE + 0x1000
ALIAS_RELEASE_THUNK = ALIAS_BASE + 0x2000
ALIAS_STACK = ALIAS_BASE + 0x8000
CASE_ORDER = (
    'snapshot-original',
    'alias-original',
    'snapshot-backing-mutated',
    'alias-backing-mutated',
    'alias-length-5',
    'alias-length-3',
    'alias-wrong-type',
)
CASE_EXPECT = {
    'snapshot-original': dict(model='snapshot', mutate=False, alias_length=None,
                              wrong_type=False, id12=0, id11=2, amnm_input=0,
                              store=1, final=1, branch=1, outcome='boundary',
                              panic=None, errno=None, amnm_helper=0, chmh_helper=2),
    'alias-original': dict(model='alias', mutate=False, alias_length=None,
                           wrong_type=False, id12=0, id11=2, amnm_input=0,
                           store=1, final=1, branch=1, outcome='boundary',
                           panic=None, errno=None, amnm_helper=0, chmh_helper=2),
    'snapshot-backing-mutated': dict(model='snapshot', mutate=True, alias_length=None,
                                     wrong_type=False, id12=0, id11=2, amnm_input=0,
                                     store=1, final=1, branch=1, outcome='boundary',
                                     panic=None, errno=None, amnm_helper=0, chmh_helper=2),
    'alias-backing-mutated': dict(model='alias', mutate=True, alias_length=None,
                                  wrong_type=False, id12=0, id11=2, amnm_input=1,
                                  store=0, final=0, branch=0, outcome='panic',
                                  panic=CHMH_PANIC_TEXT, errno=2, amnm_helper=0,
                                  chmh_helper=2),
    'alias-length-5': dict(model='alias', mutate=False, alias_length=5,
                           wrong_type=False, id12=84, id11=None, amnm_input=None,
                           store=None, final=None, branch=None, outcome='panic',
                           panic=AMNM_PANIC_TEXT, errno=84, amnm_helper=84,
                           chmh_helper=None),
    'alias-length-3': dict(model='alias', mutate=False, alias_length=3,
                           wrong_type=False, id12=0, id11=2, amnm_input=0,
                           store=1, final=1, branch=1, outcome='boundary',
                           panic=None, errno=None, amnm_helper=0, chmh_helper=2),
    'alias-wrong-type': dict(model='alias', mutate=False, alias_length=None,
                             wrong_type=True, id12=96, id11=None, amnm_input=None,
                             store=None, final=None, branch=None, outcome='panic',
                             panic=AMNM_PANIC_TEXT, errno=96, amnm_helper=96,
                             chmh_helper=None),
}


def adt_offsets(raw):
    out = {}

    def read(at, parent, depth):
        if depth > 64 or at + 8 > len(raw):
            raise ValueError('Invalid ADT node')
        count, children = struct.unpack_from('<II', raw, at)
        at += 8
        props = {}
        for _ in range(count):
            if at + 36 > len(raw):
                raise ValueError('Truncated ADT property')
            key = raw[at:at + 32].split(b'\0')[0].decode('ascii')
            flags_size = struct.unpack_from('<I', raw, at + 32)[0]
            size = flags_size & 0x7fffffff
            value_at = at + 36
            if value_at + size > len(raw):
                raise ValueError('ADT property out of range')
            props[key] = {'offset': value_at, 'length': size,
                          'flags': flags_size & 0x80000000}
            at = value_at + ((size + 3) & ~3)
        name = props.get('name')
        if name is None:
            raise ValueError('ADT node lacks name')
        name = raw[name['offset']:name['offset'] + name['length']].split(b'\0')[0].decode('ascii')
        path = parent.rstrip('/') + '/' + name if parent else '/'
        if path in out:
            raise ValueError('Duplicate ADT path')
        out[path] = props
        for _ in range(children):
            at = read(at, path, depth + 1)
        return at

    end = read(0, '', 0)
    if end != len(raw):
        raise ValueError('ADT trailing bytes')
    return out


def get_prop(offsets, path, key):
    props = offsets.get(path)
    if props is None or key not in props:
        raise ValueError('Missing ADT property ' + path + '/' + key)
    return props[key]


def adt_value_map(offsets, raw):
    result = {}
    for path, props in offsets.items():
        for key, meta in props.items():
            value = raw[meta['offset']:meta['offset'] + meta['length']]
            result[path + '/' + key] = {
                'offset': meta['offset'], 'length': meta['length'],
                'sha256': B.sha(value)}
    return result


def read_u32(u, address):
    return int.from_bytes(u.mem_read(address, 4), 'little')


def read_u64(u, address):
    return int.from_bytes(u.mem_read(address, 8), 'little')


def real_vtable(raw, macho):
    at = B.backed(macho, OSDATA_VTABLE, 0x140)
    data = bytearray(raw[at:at + 0x140])
    entries = {offset: struct.unpack_from('<Q', data, offset)[0]
               for offset in (0x28, 0x88, 0xa0, 0xd8)}
    expected = {0x28: OSDATA_RELEASE, 0x88: OSDATA_INIT_NO_COPY,
                0xa0: OSDATA_GET_LENGTH, 0xd8: OSDATA_GET_BYTES_NO_COPY}
    if entries != expected:
        raise ValueError('Real OSData vtable changed: %r' % (entries,))
    return data, entries


def build_alias_object(model, raw, macho, backing, length):
    u = model.u
    u.mem_map(ALIAS_BASE, ALIAS_SIZE)
    vtable, entries = real_vtable(raw, macho)
    struct.pack_into('<Q', vtable, 0x28, ALIAS_RELEASE_THUNK)
    u.mem_write(ALIAS_VTABLE, bytes(vtable))
    u.mem_write(ALIAS_RELEASE_THUNK, struct.pack('<I', 0xd65f03c0))  # ret
    u.mem_write(ALIAS_OBJECT, bytes(0x40))
    u.mem_write(ALIAS_OBJECT, struct.pack('<Q', ALIAS_VTABLE))
    slice_pcs = []
    hook = u.hook_add(U.UC_HOOK_CODE, lambda uc, pc, size, data: slice_pcs.append(pc))
    u.reg_write(A.UC_ARM64_REG_X19, backing)
    u.reg_write(A.UC_ARM64_REG_X20, ALIAS_OBJECT)
    u.reg_write(A.UC_ARM64_REG_X21, length)
    u.reg_write(A.UC_ARM64_REG_SP, ALIAS_STACK + 0x8000)
    u.reg_write(A.UC_ARM64_REG_LR, A.STOP)
    u.emu_start(OSDATA_INIT_SLICE, OSDATA_INIT_SLICE_STOP, count=100)
    u.hook_del(hook)
    if u.reg_read(A.UC_ARM64_REG_PC) != OSDATA_INIT_SLICE_STOP:
        raise ValueError('OSData field slice did not reach its stop')
    object_length = read_u32(u, ALIAS_OBJECT + 0xc)
    object_capacity = read_u32(u, ALIAS_OBJECT + 0x10)
    object_data = read_u64(u, ALIAS_OBJECT + 0x18)
    real_length = model.call(OSDATA_GET_LENGTH, (ALIAS_OBJECT,)) & 0xffffffff
    real_data = model.call(OSDATA_GET_BYTES_NO_COPY, (ALIAS_OBJECT,))
    return {
        'object': hex(ALIAS_OBJECT),
        'vtable': hex(ALIAS_VTABLE),
        'real_vtable': hex(OSDATA_VTABLE),
        'vtable_entries': {hex(k): hex(v) for k, v in entries.items()},
        'release_stub': hex(ALIAS_RELEASE_THUNK),
        'field_slice': [hex(p) for p in slice_pcs],
        'field_slice_stop': hex(OSDATA_INIT_SLICE_STOP),
        'skipped_dependency': ('OSData::initWithBytesNoCopy calls OSObject::init at '
                               + hex(OSDATA_SUPER_INIT)
                               + '; the metaclass/refcount/allocator path is outside this fixture'),
        'length': object_length,
        'capacity': hex(object_capacity),
        'data_pointer': hex(object_data),
        'real_getLength': real_length,
        'real_getBytesNoCopy': hex(real_data),
        'data_equals_backing': object_data == backing,
        'length_equals_requested': object_length == length,
    }


class AliasModel(A.Model):
    def __init__(self, raw, macho, nodes):
        super().__init__(raw, macho, nodes)
        self.alias_object = None
        self.alias_length = 0
        self.alias_wrong = False
        self.alias_events = []
        self.hooks[ALIAS_RELEASE_THUNK] = 'alias_release'

    def watch(self, u, pc, size, data):
        name = self.hooks.get(pc)
        if name == 'alias_release':
            self.alias_events.append({'pc': hex(pc), 'event': 'alias_release'})
            u.reg_write(A.UC_ARM64_REG_X0, 0)
            u.reg_write(A.UC_ARM64_REG_PC, u.reg_read(A.UC_ARM64_REG_LR))
            return
        if name == 'property':
            key = self.cstr(u.reg_read(A.UC_ARM64_REG_X1))
            path = self.objects.get(u.reg_read(A.UC_ARM64_REG_X0))
            if key == POLICY_KEY and path == '/chosen' and self.alias_object is not None:
                self.alias_events.append({'pc': hex(pc), 'event': 'alias_property',
                                          'object': hex(self.alias_object),
                                          'length': self.alias_length})
                if self.alias_wrong:
                    self.wrong_objects.add(self.alias_object)
                u.reg_write(A.UC_ARM64_REG_X0, self.alias_object)
                u.reg_write(A.UC_ARM64_REG_PC, u.reg_read(A.UC_ARM64_REG_LR))
                return
        super().watch(u, pc, size, data)


def run_initializer(model, macho):
    u = model.u
    events, trace = [], []
    bool_id = {'value': None}
    bool_ids = []
    helper_context = {}
    stop = {'reason': None, 'pc': None, 'panic': None, 'variadic': None}
    getter = {'getLength': [], 'getBytesNoCopy': [], 'release': []}

    def code(uc, pc, size, data):
        nonlocal helper_context
        trace.append(pc)
        if pc == DECISION_BOUNDARY:
            stop.update(reason='boundary', pc=pc)
            uc.emu_stop()
            return
        if pc == PANIC:
            sp = uc.reg_read(A.UC_ARM64_REG_SP)
            stop.update(reason='panic', pc=pc,
                        panic=model.cstr(uc.reg_read(A.UC_ARM64_REG_X0)),
                        variadic=[model.get64(sp), model.get64(sp + 8)])
            uc.emu_stop()
            return
        if pc == 0xfffffff0046e99c4:
            events.append({'pc': hex(pc), 'event': 'bool_output_pointer',
                           'x3': hex(uc.reg_read(A.UC_ARM64_REG_X3))})
        elif pc == BOOL_CALL:
            events.append({'pc': hex(pc), 'event': 'id12_call',
                           'x0': hex(uc.reg_read(A.UC_ARM64_REG_X0)),
                           'x1': hex(uc.reg_read(A.UC_ARM64_REG_X1)),
                           'x2': uc.reg_read(A.UC_ARM64_REG_X2),
                           'x3': hex(uc.reg_read(A.UC_ARM64_REG_X3))})
        elif pc == BOOL_RETURN:
            events.append({'pc': hex(pc), 'event': 'id12_return',
                           'w0': uc.reg_read(A.UC_ARM64_REG_W0) & 0xffffffff})
        elif pc == BOOL_READER:
            bool_id['value'] = uc.reg_read(A.UC_ARM64_REG_X2)
            bool_ids.append(bool_id['value'])
        elif pc == BOOL_INPUT and bool_id['value'] == 12:
            events.append({'pc': hex(pc), 'event': 'amnm_input',
                           'w8': uc.reg_read(A.UC_ARM64_REG_W8) & 0xffffffff})
        elif pc == BOOL_STORE and bool_id['value'] == 12:
            events.append({'pc': hex(pc), 'event': 'amnm_store',
                           'byte': uc.reg_read(A.UC_ARM64_REG_W8) & 0xff})
        elif pc == DIGEST_CALL:
            events.append({'pc': hex(pc), 'event': 'id11_call',
                           'x2': uc.reg_read(A.UC_ARM64_REG_X2),
                           'x3': hex(uc.reg_read(A.UC_ARM64_REG_X3))})
        elif pc == DIGEST_RETURN:
            events.append({'pc': hex(pc), 'event': 'id11_return',
                           'w0': uc.reg_read(A.UC_ARM64_REG_W0) & 0xffffffff})
        elif pc == HELPER:
            x3 = uc.reg_read(A.UC_ARM64_REG_X3)
            helper_context = {'key': model.cstr(uc.reg_read(A.UC_ARM64_REG_X1)),
                              'capacity': read_u32(u, x3)}
            events.append({'pc': hex(pc), 'event': 'helper_enter', **helper_context})
        elif pc == 0xfffffff0046f08a0:
            rec = {**helper_context, 'w0': uc.reg_read(A.UC_ARM64_REG_W0) & 0xffffffff}
            events.append({'pc': hex(pc), 'event': 'helper_return', **rec})
            helper_context = {}
        elif pc == FINAL_READ:
            events.append({'pc': hex(pc), 'event': 'final_read',
                           'byte': bytes(u.mem_read(BOOL_OUT, 1))[0]})
        elif pc == FINAL_BRANCH:
            events.append({'pc': hex(pc), 'event': 'final_branch',
                           'w8': uc.reg_read(A.UC_ARM64_REG_W8) & 0xff})
        elif pc == PANIC_SITE_AMNM:
            events.append({'pc': hex(pc), 'event': 'panic_site_amnm',
                           'x0': uc.reg_read(A.UC_ARM64_REG_X0) & 0xffffffff})
        elif pc == PANIC_SITE_CHMH:
            events.append({'pc': hex(pc), 'event': 'panic_site_chmh',
                           'x0': uc.reg_read(A.UC_ARM64_REG_X0) & 0xffffffff})
        elif pc == OSDATA_GET_LENGTH:
            getter['getLength'].append({'pc': hex(pc), 'event': 'alias_getLength'})
        elif pc == OSDATA_GET_LENGTH_RET:
            getter['getLength'].append({'pc': hex(pc), 'event': 'alias_getLength_return',
                                        'w0': uc.reg_read(A.UC_ARM64_REG_W0) & 0xffffffff})
        elif pc == OSDATA_GET_BYTES_NO_COPY:
            getter['getBytesNoCopy'].append({'pc': hex(pc),
                                             'event': 'alias_getBytesNoCopy'})
        elif pc == OSDATA_GET_BYTES_RET:
            getter['getBytesNoCopy'].append({'pc': hex(pc),
                                             'event': 'alias_getBytesNoCopy_return',
                                             'x0': hex(uc.reg_read(A.UC_ARM64_REG_X0))})
        elif pc == ALIAS_RELEASE_THUNK:
            getter['release'].append({'pc': hex(pc), 'event': 'alias_release'})

    u.hook_add(U.UC_HOOK_CODE, code)
    for i in range(19, 30):
        u.reg_write(getattr(A, 'UC_ARM64_REG_X%d' % i), 0x11220000 + i * 0x100)
    u.reg_write(A.UC_ARM64_REG_X0, A.PMAP_RUNTIME)
    u.reg_write(A.UC_ARM64_REG_LR, A.STOP)
    u.reg_write(A.UC_ARM64_REG_SP, A.STACK + 0x8000)
    error = None
    try:
        u.emu_start(ENTRY, A.STOP, count=3000000)
    except U.UcError as exc:
        error = str(exc)
    pc = u.reg_read(A.UC_ARM64_REG_PC)
    if stop['reason'] is None:
        if model.bad:
            stop.update(reason='unmodelled_memory', pc=pc)
        elif pc == A.STOP:
            stop.update(reason='returned_to_sentinel', pc=pc)
        else:
            stop.update(reason='unmodelled_stop', pc=pc)
    if error:
        stop['error'] = error
    stub = set(model.hooks)
    donor = [p for p in trace if p >= 0xfffffff000000000 and p not in stub]
    return {
        'stop': {**stop, 'pc': hex(stop['pc']) if stop.get('pc') is not None else None},
        'events': events,
        'bool_reader_ids': bool_ids,
        'getter_calls': getter,
        'model_bad': model.bad,
        'donor_pc_count': len(donor),
        'donor_pc_min': hex(min(donor)) if donor else None,
        'donor_pc_max': hex(max(donor)) if donor else None,
        'executed_donor_pcs': [hex(p) for p in donor],
        'fixture_pc_count': len(trace) - len(donor),
    }


def run_case(raw, macho, adt, name):
    cfg = CASE_EXPECT[name]
    nodes = A.parse_adt(adt)
    model = AliasModel(raw, macho, nodes) if cfg['model'] == 'alias' else A.Model(raw, macho, nodes)
    u = model.u
    u.mem_map(TREE_VA, B.align(len(adt)))
    u.mem_write(TREE_VA, adt)
    model.call(macho['symbols']['_SecureDTInit'], (TREE_VA, len(adt)))
    offsets = adt_offsets(adt)
    amnm = get_prop(offsets, '/chosen', POLICY_KEY)
    backing = TREE_VA + amnm['offset']
    backing_before = bytes(u.mem_read(backing, amnm['length']))
    alias = None
    if cfg['model'] == 'alias':
        length = amnm['length'] if cfg['alias_length'] is None else cfg['alias_length']
        alias = build_alias_object(model, raw, macho, backing, length)
        model.alias_object = ALIAS_OBJECT
        model.alias_length = length
        model.alias_wrong = cfg['wrong_type']
    if cfg['mutate']:
        u.mem_write(backing, b'\x01' + bytes(max(0, amnm['length'] - 1)))
    backing_after = bytes(u.mem_read(backing, amnm['length']))
    old_pointer = None
    old_value = None
    if cfg['model'] == 'snapshot':
        old_pointer = A.HEAP + 0x1f000
    result = run_initializer(model, macho)
    if cfg['model'] == 'snapshot':
        old_value = bytes(u.mem_read(old_pointer, amnm['length'])).hex()
    entry = {e['event']: e for e in result['events'] if e['event'] != 'helper_return'}
    helpers = [e for e in result['events'] if e['event'] == 'helper_return']
    amnm_helpers = [h for h in helpers if h.get('key') == POLICY_KEY]
    chmh_helpers = [h for h in helpers if h.get('key') == HASH_KEY]
    reader = {
        'id12_call': entry.get('id12_call'),
        'id12_return': entry.get('id12_return', {}).get('w0'),
        'id11_call': entry.get('id11_call'),
        'id11_return': entry.get('id11_return', {}).get('w0'),
        'amnm_input': entry.get('amnm_input', {}).get('w8'),
        'amnm_store': entry.get('amnm_store', {}).get('byte'),
        'final_read': entry.get('final_read', {}).get('byte'),
        'final_branch': entry.get('final_branch', {}).get('w8'),
        'panic_site_amnm': entry.get('panic_site_amnm', {}).get('x0'),
        'panic_site_chmh': entry.get('panic_site_chmh', {}).get('x0'),
        'helpers': helpers,
        'amnm_helper': amnm_helpers,
        'chmh_helper': chmh_helpers,
        'bool_reader_ids': result['bool_reader_ids'],
    }
    if result['stop']['reason'] == 'boundary':
        outcome = 'boundary'
    elif result['stop']['reason'] == 'panic':
        outcome = 'panic'
    else:
        outcome = result['stop']['reason']
    return {
        'case': name,
        'model': cfg['model'],
        'adt_sha256': B.sha(adt),
        'backing': {
            'offset': hex(amnm['offset']), 'address': hex(backing),
            'length': amnm['length'], 'before_hex': backing_before.hex(),
            'after_hex': backing_after.hex(), 'mutated': cfg['mutate'],
        },
        'alias_object': alias,
        'old_fixture_bytes_pointer': hex(old_pointer) if old_pointer is not None else None,
        'old_fixture_bytes_value_hex': old_value,
        'alias_events': list(getattr(model, 'alias_events', [])),
        'reader': reader,
        'outcome': outcome,
        'stop': result['stop'],
        'model_bad': result['model_bad'],
        'getter_calls': result['getter_calls'],
        'donor_pc_count': result['donor_pc_count'],
        'donor_pc_min': result['donor_pc_min'],
        'donor_pc_max': result['donor_pc_max'],
        'executed_donor_pcs': result['executed_donor_pcs'],
        'fixture_pc_count': result['fixture_pc_count'],
    }


def validate_report(report, raw, adt):
    checks = []

    def require(condition, message):
        if not condition:
            raise ValueError(message)

    def group(name, fn):
        fn()
        checks.append({'name': name, 'passed': True})

    kernel_sha, adt_sha = B.sha(raw), B.sha(adt)
    require(report['inputs']['kernel']['sha256'] == kernel_sha, 'kernel pin changed')
    require(report['inputs']['adt']['sha256'] == adt_sha, 'ADT pin changed')
    require(report['dependencies']['source_sha256'] == B.sha(Path(__file__).read_bytes()),
            'source hash changed')
    reused = report['dependencies']['reused_source_sha256']
    for rel in ('scripts/audit-image4-runtime-provider.py',
                'scripts/build-kernel-entry-probe.py',
                'scripts/nuwa_launch_context.py'):
        require(reused.get(rel) == B.sha((ROOT / rel).read_bytes()),
                'reused hash changed: ' + rel)
    offsets = adt_offsets(adt)
    amnm = get_prop(offsets, '/chosen', POLICY_KEY)
    trust = get_prop(offsets, '/chosen/memory-map', 'TrustCache')
    bnch = get_prop(offsets, '/chosen/manifest-properties', 'BNCH')
    require(amnm['offset'] == 0x2538 and amnm['length'] == 4, 'AMNM offset/length changed')
    require(report['adt_backing']['device_tree_property_present'] is False,
            'DeviceTree presence changed')
    require(report['adt_backing']['memory_map_properties'] == ['TrustCache', 'name'],
            'memory-map properties changed')
    require(trust['offset'] == 0x2598 and trust['length'] == 16, 'TrustCache offset changed')
    require(bnch['offset'] == 0x260c and bnch['length'] == 48, 'BNCH offset changed')
    require(amnm['offset'] + amnm['length'] <= trust['offset']
            or trust['offset'] + trust['length'] <= amnm['offset'],
            'AMNM overlaps TrustCache')
    require(amnm['offset'] + amnm['length'] <= bnch['offset']
            or bnch['offset'] + bnch['length'] <= amnm['offset'],
            'AMNM overlaps BNCH')
    require(report['stop_adt']['sha256'] ==
            'ff7d25234c1c6d3ed14e63e3e5489f26fdf65d1f7f649f20b8f6704f8b4ab736',
            'stop ADT hash changed')
    stop_compare = report['stop_adt_comparison']
    require(stop_compare['structure_same'] is True, 'stop ADT structure changed')
    require(stop_compare['amnm_same'] is True, 'stop ADT AMNM changed')
    require(stop_compare['trustcache_same'] is True, 'stop TrustCache changed')
    require(stop_compare['random_seed_differs'] is True, 'random-seed difference lost')
    require(stop_compare['bnch_differs'] is True, 'BNCH difference lost')
    require(stop_compare['differing_properties'] ==
            ['/chosen/manifest-properties/BNCH', '/chosen/random-seed'],
            'stop ADT differing-property set changed')
    require(report['osdata_binding']['vtable_entries']['0xa0'] == hex(OSDATA_GET_LENGTH),
            'getLength vtable changed')
    require(report['osdata_binding']['vtable_entries']['0xd8'] == hex(OSDATA_GET_BYTES_NO_COPY),
            'getBytesNoCopy vtable changed')
    require(report['osdata_binding']['vtable_entries']['0x28'] == hex(OSDATA_RELEASE),
            'release vtable changed')
    require(report['osdata_binding']['make_reference_table'] == hex(MAKE_REFERENCE_TABLE),
            'MakeReferenceTable address changed')
    require(report['osdata_binding']['mrt_no_copy_call'] == hex(MRT_NO_COPY_CALL),
            'MakeReferenceTable no-copy call changed')
    require(report['osdata_binding']['mrt_copy_call'] == hex(MRT_COPY_CALL),
            'MakeReferenceTable copy call changed')
    checks.append({'name': 'inputs/backing/osdata binding', 'passed': True})
    require(list(report['cases']) == list(CASE_ORDER), 'case order changed')
    for name in CASE_ORDER:
        c = report['cases'][name]
        sem = CASE_EXPECT[name]
        require(c['model'] == sem['model'], name + ': model changed')
        require(c['backing']['offset'] == hex(amnm['offset']), name + ': backing offset changed')
        require(c['backing']['length'] == amnm['length'], name + ': backing length changed')
        require(c['backing']['mutated'] == sem['mutate'], name + ': mutation flag changed')
        expected_before = bytes.fromhex('00000000')
        expected_after = bytes.fromhex('01000000') if sem['mutate'] else expected_before
        require(bytes.fromhex(c['backing']['before_hex']) == expected_before,
                name + ': backing before changed')
        require(bytes.fromhex(c['backing']['after_hex']) == expected_after,
                name + ': backing after changed')
        if sem['model'] == 'alias':
            alias = c['alias_object']
            require(alias is not None, name + ': missing alias object')
            req_len = amnm['length'] if sem['alias_length'] is None else sem['alias_length']
            require(alias['length'] == req_len, name + ': alias length changed')
            require(alias['real_getLength'] == req_len, name + ': real getLength changed')
            require(alias['data_pointer'] == hex(TREE_VA + amnm['offset']),
                    name + ': alias data pointer changed')
            require(alias['real_getBytesNoCopy'] == alias['data_pointer'],
                    name + ': real getBytesNoCopy changed')
            require(alias['data_equals_backing'] is True, name + ': data not backed by ADT')
            require(alias['length_equals_requested'] is True, name + ': field slice length changed')
            require(alias['capacity'] == '0xffffffff', name + ': capacity not EXTERNAL')
            require(alias['field_slice'] == [
                hex(OSDATA_INIT_SLICE), hex(OSDATA_INIT_SLICE + 4),
                hex(OSDATA_INIT_SLICE + 8)] and alias['field_slice_stop'] ==
                hex(OSDATA_INIT_SLICE_STOP), name + ': field slice changed')
        else:
            require(c['old_fixture_bytes_pointer'] == hex(A.HEAP + 0x1f000),
                    name + ': old fixture pointer changed')
            require(c['old_fixture_bytes_value_hex'] == '00000000',
                    name + ': old snapshot value changed')
        r = c['reader']
        require(r['id12_return'] == sem['id12'], name + ': id12 return changed')
        require(r['id11_return'] == sem['id11'], name + ': id11 return changed')
        require(r['amnm_input'] == sem['amnm_input'], name + ': AMNM input changed')
        require(r['amnm_store'] == sem['store'], name + ': AMNM store changed')
        require(r['final_read'] == sem['final'], name + ': final read changed')
        require(r['final_branch'] == sem['branch'], name + ': final branch changed')
        amnm_helpers = r['amnm_helper']
        require(len(amnm_helpers) == 1
                and amnm_helpers[0].get('key') == POLICY_KEY
                and amnm_helpers[0].get('capacity') == 4
                and amnm_helpers[0].get('w0') == sem['amnm_helper'],
                name + ': AMNM helper shape/errno changed')
        if sem['chmh_helper'] is None:
            require(r['chmh_helper'] == [], name + ': unexpected CHMH helper')
        else:
            chmh_helpers = r['chmh_helper']
            require(len(chmh_helpers) == 1
                    and chmh_helpers[0].get('key') == HASH_KEY
                    and chmh_helpers[0].get('capacity') == 48
                    and chmh_helpers[0].get('w0') == sem['chmh_helper'],
                    name + ': CHMH helper shape/errno changed')
        require(r['bool_reader_ids'] == [5, 6, 7, 8, 9, 13, 10, 12],
                name + ': bool reader sequence changed')
        if sem['model'] == 'alias':
            get_length = c['getter_calls']['getLength']
            get_bytes = c['getter_calls']['getBytesNoCopy']
            if sem['wrong_type']:
                require(get_length == [] and get_bytes == [],
                        name + ': wrong-type reader getters changed')
            else:
                require(any(e.get('event') == 'alias_getLength_return'
                            and e.get('w0') == req_len for e in get_length),
                        name + ': reader getLength value changed')
                if req_len <= amnm['length']:
                    require(any(e.get('event') == 'alias_getBytesNoCopy_return'
                                and e.get('x0') == hex(TREE_VA + amnm['offset'])
                                for e in get_bytes),
                            name + ': reader getBytesNoCopy value changed')
                else:
                    require(get_bytes == [], name + ': unexpected getBytesNoCopy')
        require(c['outcome'] == sem['outcome'], name + ': outcome changed')
        require(c['stop']['reason'] ==
                ('boundary' if sem['outcome'] == 'boundary' else 'panic'),
                name + ': stop reason changed')
        if sem['panic'] is None:
            require(c['stop']['panic'] is None and c['stop']['variadic'] is None,
                    name + ': unexpected panic')
        else:
            require(c['stop']['panic'] == sem['panic'], name + ': panic format changed')
            require(c['stop']['variadic'] and c['stop']['variadic'][0] == sem['errno'],
                    name + ': panic errno changed')
        require(c['model_bad'] == [], name + ': invalid memory')
        if sem['alias_length'] == 5:
            require(r['panic_site_amnm'] == 84, name + ': AMNM panic site changed')
        if sem['wrong_type']:
            require(r['panic_site_amnm'] == 96, name + ': AMNM wrong-type site changed')
        if sem['mutate'] and sem['model'] == 'alias':
            require(r['panic_site_chmh'] == 2, name + ': CHMH panic site changed')
        pcs = set(c['executed_donor_pcs'])
        require(hex(ENTRY) in pcs and hex(BOOL_READER) in pcs and hex(DIGEST_READER) in pcs,
                name + ': real code not in trace')
        require(hex(EPILOGUE_RET) not in pcs, name + ': epilogue in trace')
        checks.append({'name': name + ': alias/reader/exit/trace', 'passed': True})
    comparisons = report['comparisons']
    require(comparisons['positive_alias_matches_snapshot'] is True,
            'positive alias/snapshot mismatch')
    require(comparisons['negative_alias_sees_mutation'] is True,
            'alias did not see backing mutation')
    require(comparisons['negative_snapshot_keeps_original'] is True,
            'snapshot saw backing mutation')
    require(comparisons['length_5_rejected'] is True, 'length-5 rejection changed')
    require(comparisons['length_3_accepted'] is True, 'length-3 acceptance changed')
    require(comparisons['wrong_type_rejected'] is True, 'wrong-type rejection changed')
    require(report['input_unchanged']['adt_bytes'] == len(adt), 'input ADT length changed')
    require(report['input_unchanged']['kernel_bytes'] == len(raw), 'input kernel length changed')
    checks.append({'name': 'comparisons/input unchanged', 'passed': True})
    return checks


def negative_mutations(report):
    K = 'alias-original'
    M = 'alias-backing-mutated'
    S = 'snapshot-backing-mutated'
    L = 'alias-length-5'
    T = 'alias-wrong-type'
    fake = {'event': 'fake'}
    mutations = (
        ('alias getBytesNoCopy pointer', lambda r: r['cases'][K]['alias_object'].__setitem__(
            'real_getBytesNoCopy', '0x1')),
        ('alias real getLength', lambda r: r['cases'][K]['alias_object'].__setitem__(
            'real_getLength', 3)),
        ('alias capacity', lambda r: r['cases'][K]['alias_object'].__setitem__(
            'capacity', '0x4')),
        ('alias-mutated store', lambda r: r['cases'][M]['reader'].__setitem__(
            'amnm_store', 1)),
        ('snapshot-mutated store', lambda r: r['cases'][S]['reader'].__setitem__(
            'amnm_store', 0)),
        ('length-5 errno', lambda r: r['cases'][L]['reader'].__setitem__('id12_return', 0)),
        ('wrong-type errno', lambda r: r['cases'][T]['reader'].__setitem__('id12_return', 0)),
        ('AMNM offset', lambda r: r['cases'][K]['backing'].__setitem__('offset', '0x2539')),
        ('input ADT hash', lambda r: r['inputs']['adt'].__setitem__('sha256', '0' * 64)),
        ('source hash', lambda r: r['dependencies'].__setitem__('source_sha256', '0' * 64)),
        ('comparison flag', lambda r: r['comparisons'].__setitem__(
            'negative_alias_sees_mutation', False)),
        ('stop ADT hash', lambda r: r['stop_adt'].__setitem__('sha256', '0' * 64)),
    )
    results = []
    for label, mutate in mutations:
        candidate = copy.deepcopy(report)
        mutate(candidate)
        try:
            validate_report(candidate, RAW, ADT)
        except ValueError as exc:
            results.append({'mutation': label, 'rejected': True, 'reason': str(exc)})
        else:
            results.append({'mutation': label, 'rejected': False})
    return results


RAW = None
ADT = None


def write_exclusive(path, payload):
    path = path.resolve()
    if path.suffix != '.json' or not path.is_relative_to(ROOT / 'out'):
        raise ValueError('Output must be a JSON file under out/')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', newline='\n') as handle:
        handle.write(json.dumps(payload, indent=2) + '\n')


def main():
    global RAW, ADT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel', required=True, type=Path)
    parser.add_argument('--kernel-sha256', required=True)
    parser.add_argument('--adt', required=True, type=Path)
    parser.add_argument('--adt-sha256', required=True)
    parser.add_argument('--stop-adt', required=True, type=Path)
    parser.add_argument('--stop-adt-sha256', required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--negative-self-check', type=Path)
    parser.add_argument('--negative-output', type=Path)
    args = parser.parse_args()
    RAW, ADT = args.kernel.read_bytes(), args.adt.read_bytes()
    stop_adt = args.stop_adt.read_bytes()
    if B.sha(RAW) != args.kernel_sha256:
        raise ValueError('Kernel hash mismatch')
    if B.sha(ADT) != args.adt_sha256:
        raise ValueError('ADT hash mismatch')
    if B.sha(stop_adt) != args.stop_adt_sha256:
        raise ValueError('Stop ADT hash mismatch')
    if args.negative_self_check:
        if not args.negative_output:
            raise ValueError('--negative-output required')
        report_bytes = args.negative_self_check.read_bytes()
        report = json.loads(report_bytes)
        validate_report(report, RAW, ADT)
        results = negative_mutations(report)
        rejected = sum(1 for r in results if r['rejected'])
        payload = {
            'scope': 'Single-field tamper negatives for the OSData alias runner',
            'status': 'self-checked host evidence',
            'report_sha256': B.sha(report_bytes),
            'source_sha256': B.sha(Path(__file__).read_bytes()),
            'kernel_sha256': B.sha(RAW), 'adt_sha256': B.sha(ADT),
            'positive_validation': 'pass',
            'mutations': results, 'rejected': rejected, 'total': len(results),
            'all_rejected': rejected == len(results),
        }
        write_exclusive(args.negative_output, payload)
        print(json.dumps({'positive_validation': 'pass', 'rejected': rejected,
                          'total': len(results), 'all_rejected': rejected == len(results),
                          'output': str(args.negative_output.resolve())}))
        if rejected != len(results):
            sys.exit(1)
        return
    if not args.output:
        raise ValueError('--output required')
    macho = B.macho(RAW)
    offsets = adt_offsets(ADT)
    amnm = get_prop(offsets, '/chosen', POLICY_KEY)
    trust = get_prop(offsets, '/chosen/memory-map', 'TrustCache')
    bnch = get_prop(offsets, '/chosen/manifest-properties', 'BNCH')
    stop_offsets = adt_offsets(stop_adt)
    stop_amnm = get_prop(stop_offsets, '/chosen', POLICY_KEY)
    stop_bnch = get_prop(stop_offsets, '/chosen/manifest-properties', 'BNCH')
    stop_random = get_prop(stop_offsets, '/chosen', 'random-seed')
    random = get_prop(offsets, '/chosen', 'random-seed')
    actual_values = adt_value_map(offsets, ADT)
    stop_values = adt_value_map(stop_offsets, stop_adt)
    structure_same = (set(actual_values) == set(stop_values)
                      and all(actual_values[key]['offset'] == stop_values[key]['offset']
                              and actual_values[key]['length'] == stop_values[key]['length']
                              for key in actual_values))
    differing = sorted(key for key in actual_values
                       if actual_values[key]['sha256'] != stop_values[key]['sha256'])
    vtable, entries = real_vtable(RAW, macho)
    cases = {}
    for name in CASE_ORDER:
        cases[name] = run_case(RAW, macho, ADT, name)
        gc.collect()
    positive = (cases['alias-original']['reader']['amnm_store'] ==
                cases['snapshot-original']['reader']['amnm_store'] == 1
                and cases['alias-original']['reader']['final_read'] ==
                cases['snapshot-original']['reader']['final_read'] == 1
                and cases['alias-original']['outcome'] ==
                cases['snapshot-original']['outcome'] == 'boundary')
    negative_alias = (cases['alias-backing-mutated']['reader']['amnm_input'] == 1
                      and cases['alias-backing-mutated']['reader']['amnm_store'] == 0
                      and cases['alias-backing-mutated']['reader']['final_read'] == 0
                      and cases['alias-backing-mutated']['outcome'] == 'panic'
                      and cases['alias-backing-mutated']['stop']['variadic'][0] == 2)
    negative_snapshot = (cases['snapshot-backing-mutated']['reader']['amnm_input'] == 0
                         and cases['snapshot-backing-mutated']['reader']['amnm_store'] == 1
                         and cases['snapshot-backing-mutated']['reader']['final_read'] == 1
                         and cases['snapshot-backing-mutated']['outcome'] == 'boundary')
    report = {
        'scope': __doc__,
        'status': 'self-checked host evidence',
        'inputs': {
            'kernel': {'path': str(args.kernel), 'bytes': len(RAW), 'sha256': B.sha(RAW)},
            'adt': {'path': str(args.adt), 'bytes': len(ADT), 'sha256': B.sha(ADT)},
            'stop_adt': {'path': str(args.stop_adt), 'bytes': len(stop_adt),
                         'sha256': B.sha(stop_adt)},
        },
        'stop_adt': {
            'sha256': B.sha(stop_adt),
            'amnm_offset': hex(stop_amnm['offset']), 'amnm_length': stop_amnm['length'],
            'amnm_value_hex': stop_adt[stop_amnm['offset']:
                                      stop_amnm['offset'] + stop_amnm['length']].hex(),
            'bnch_offset': hex(stop_bnch['offset']), 'bnch_length': stop_bnch['length'],
            'bnch_value_hex': stop_adt[stop_bnch['offset']:
                                      stop_bnch['offset'] + stop_bnch['length']].hex(),
            'random_seed_offset': hex(stop_random['offset']),
            'random_seed_length': stop_random['length'],
            'random_seed_value_hex': stop_adt[stop_random['offset']:
                                             stop_random['offset'] + stop_random['length']].hex(),
            'note': ('read-only control only; not used as runner input. Structure and AMNM '
                     'match; random-seed and BNCH contents differ; args stage5 removal is '
                     'not a causal chain and does not blame the restore RET.'),
        },
        'stop_adt_comparison': {
            'structure_same': structure_same,
            'differing_properties': differing,
            'amnm_same': (actual_values['/chosen/' + POLICY_KEY] ==
                          stop_values['/chosen/' + POLICY_KEY]),
            'trustcache_same': (actual_values['/chosen/memory-map/TrustCache'] ==
                                stop_values['/chosen/memory-map/TrustCache']),
            'random_seed_differs': (
                actual_values['/chosen/random-seed']['sha256'] !=
                stop_values['/chosen/random-seed']['sha256']),
            'bnch_differs': (
                actual_values['/chosen/manifest-properties/BNCH']['sha256'] !=
                stop_values['/chosen/manifest-properties/BNCH']['sha256']),
            'args_note': ('stage5 removal is a known input difference; no causal chain to '
                          'the restore RET is established'),
        },
        'adt_backing': {
            'tree_va': hex(TREE_VA),
            'amnm_offset': hex(amnm['offset']), 'amnm_length': amnm['length'],
            'amnm_address': hex(TREE_VA + amnm['offset']),
            'amnm_value_hex': ADT[amnm['offset']:amnm['offset'] + amnm['length']].hex(),
            'trustcache_offset': hex(trust['offset']), 'trustcache_length': trust['length'],
            'device_tree_property_present': ('DeviceTree' in offsets['/chosen/memory-map']),
            'memory_map_properties': sorted(offsets['/chosen/memory-map']),
            'free_dt_inference': ('DeviceTree absent -> IODeviceTreeAlloc freeDT=false, '
                                  'MakeReferenceTable(copy=false) source lines 179-186,394-443'),
            'bnch_offset': hex(bnch['offset']), 'bnch_length': bnch['length'],
            'overlap_free': ((amnm['offset'] + amnm['length'] <= trust['offset']
                              or trust['offset'] + trust['length'] <= amnm['offset'])
                             and (amnm['offset'] + amnm['length'] <= bnch['offset']
                                  or bnch['offset'] + bnch['length'] <= amnm['offset'])),
            'random_seed_offset': hex(random['offset']),
            'random_seed_length': random['length'],
        },
        'osdata_binding': {
            'vtable': hex(OSDATA_VTABLE),
            'vtable_entries': {hex(k): hex(v) for k, v in entries.items()},
            'init_no_copy': hex(OSDATA_INIT_NO_COPY),
            'init_slice': [hex(OSDATA_INIT_SLICE), hex(OSDATA_INIT_SLICE_STOP)],
            'super_init': hex(OSDATA_SUPER_INIT),
            'get_length': hex(OSDATA_GET_LENGTH),
            'get_bytes_no_copy': hex(OSDATA_GET_BYTES_NO_COPY),
            'with_bytes_no_copy': hex(OSDATA_WITH_BYTES_NO_COPY),
            'with_bytes': hex(OSDATA_WITH_BYTES),
            'make_reference_table': hex(MAKE_REFERENCE_TABLE),
            'mrt_no_copy_call': hex(MRT_NO_COPY_CALL),
            'mrt_copy_call': hex(MRT_COPY_CALL),
            'constructor_boundary': ('MakeReferenceTable/IOService/OSDictionary/OSSymbol and '
                                     'OSObject::init/metaclass/allocator are not executed; the '
                                     'copy=false field slice and real getters are'),
        },
        'cases': cases,
        'comparisons': {
            'positive_alias_matches_snapshot': positive,
            'negative_alias_sees_mutation': negative_alias,
            'negative_snapshot_keeps_original': negative_snapshot,
            'length_5_rejected': (cases['alias-length-5']['reader']['id12_return'] == 84
                                  and cases['alias-length-5']['outcome'] == 'panic'
                                  and cases['alias-length-5']['stop']['variadic'][0] == 84),
            'length_3_accepted': (cases['alias-length-3']['alias_object']['real_getLength'] == 3
                                  and cases['alias-length-3']['reader']['amnm_store'] == 1
                                  and cases['alias-length-3']['outcome'] == 'boundary'),
            'wrong_type_rejected': (cases['alias-wrong-type']['reader']['id12_return'] == 96
                                    and cases['alias-wrong-type']['outcome'] == 'panic'
                                    and cases['alias-wrong-type']['stop']['variadic'][0] == 96),
        },
        'semantic_checks': [],
        'mechanical_checks': [],
        'check_note': ('semantic checks are logical groups from the validator; they are not '
                       'a count of independent proofs.'),
        'dependencies': {
            'kernel_sha256': B.sha(RAW), 'adt_sha256': B.sha(ADT),
            'source_sha256': B.sha(Path(__file__).read_bytes()),
            'unicorn': getattr(U, '__version__', None),
            'python': sys.version.split()[0],
            'reused_source_sha256': {
                rel: B.sha((ROOT / rel).read_bytes()) for rel in (
                    'scripts/audit-image4-runtime-provider.py',
                    'scripts/build-kernel-entry-probe.py',
                    'scripts/nuwa_launch_context.py')
            },
        },
        'input_unchanged': {
            'adt_bytes': len(ADT), 'kernel_bytes': len(RAW),
            'note': 'backing mutations were emulator-memory writes only; input files unchanged',
        },
        'limitations': [
            'The OSData object/vtable/backing are explicit fixtures; the full IOService/'
            'OSDictionary/MakeReferenceTable and OSObject::init/metaclass/allocator path is '
            'not executed.',
            'The object release is a no-op fixture; the observed reader path did not release '
            'the alias object.',
            'This is host evidence, not a live IORegistry, device, authentication or '
            'device-overwrite proof.',
            'The backing mutation is an emulator-memory perturbation, not a hardware or '
            'loader action.',
            'The r2 runner/evidence are unchanged; this is a separate narrow runner.',
            'The stop ADT is read-only comparison only; random-seed/BNCH differences have no '
            'established causal chain.',
        ],
    }
    report['semantic_checks'] = validate_report(report, RAW, ADT)
    report['mechanical_checks'] = [
        {'name': 'alias data pointer equals ADT backing', 'passed': True},
        {'name': 'snapshot old fixture pointer is HEAP+1f000', 'passed': True},
        {'name': 'inputs unchanged', 'passed': True},
    ]
    write_exclusive(args.output, report)
    print(json.dumps({
        'semantic_checks': len(report['semantic_checks']),
        'positive_alias_matches_snapshot': positive,
        'negative_alias_sees_mutation': negative_alias,
        'negative_snapshot_keeps_original': negative_snapshot,
        'output': str(args.output.resolve())}))


if __name__ == '__main__':
    main()
