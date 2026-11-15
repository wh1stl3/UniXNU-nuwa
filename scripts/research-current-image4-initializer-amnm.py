"""Bounded host execution of the frozen Image4 initializer AMNM/CHMH decision.

Starts at the real initializer entry 0xfffffff0046e98cc (the provider table's
+0x10 slot), runs the actual Image4 code to the post-decision boundary
0xfffffff0046e9b2c or to the original panic entry 0xfffffff0046fa028, and
reports the exact stop. It also stops on invalid memory, a Unicorn exception or
the instruction budget. Per-dependency admission is not implemented, so an
unexpected stop is reported as such and is not called the first unmodelled
dependency.

The AMNM output slot 0xfffffff005cacef0 is not pre-filled and the run does not
begin at a digest helper. The initializer epilogue at 0xfffffff0046e9f00 is not
executed. SecureDTInit runs before the traced initializer; its writes are not
part of the write ledger.

Only the existing IOKit/OSData object boundary is modelled, populated from the
same ADT passed on the command line. Image4 dispatch, property conversion,
missing/oversized/wrong-type handling and the allow-missing branch execute real
instructions. The objects are fixtures, not a live IORegistry snapshot. No
kernel, ADT, candidate or device is modified.

This is host evidence, not a live-boot or authentication result. If the original
package input allows the missing digest, that only shows the in-package input
cannot reproduce the device state; it is not proof about the device.
"""
import argparse
import copy
import gc
import importlib.util
import json
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
PANIC_SITE = 0xfffffff0046e9f64
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
CHIP_DESCRIPTOR = 0xfffffff005cae660
BOOL_OUT = 0xfffffff005cacef0
BOOL_OUT_END = 0xfffffff005cacef8
CACHE_START = 0xfffffff005caced8
CACHE_PAYLOAD_START = BOOL_OUT_END
CACHE_WINDOW_END = 0xfffffff005cacffa
BNCH_BUFFER_START = CACHE_WINDOW_END
BNCH_BUFFER_END = 0xfffffff005cad02a
BNCH_PAD_START = BNCH_BUFFER_END
BNCH_PAD_END = 0xfffffff005cad02c
CHMH_LENGTH_START = 0xfffffff005cad02c
CHMH_LENGTH_END = 0xfffffff005cad030
DIGEST_OBJECT = 0xfffffff005cad030
DIGEST_OBJECT_END = 0xfffffff005cad070
LEDGER_END = DIGEST_OBJECT_END
POLICY_KEY = 'mix-n-match-prevention-status'
HASH_KEY = 'boot-manifest-hash'
PANIC_TEXT = 'failed to get previous stage manifest hash: %d'
STACK_SENTINEL = A.STOP
RUN_COUNT = 3000000

# Contiguous, disjoint byte regions for the raw write ledger. A write crossing a
# region boundary is split by byte into one segment per region; the sum of the
# segment sizes equals the original write size, so every byte is classified
# exactly once. BNCH and the adjacent CHMH length are intentionally not part of
# the Image4 cache window.
REGIONS = (
    ('cache_header_5caced8', CACHE_START, BOOL_OUT),
    ('amnm_out_5cacef0', BOOL_OUT, BOOL_OUT_END),
    ('cache_payload_5cacef8', CACHE_PAYLOAD_START, CACHE_WINDOW_END),
    ('bnch_buffer_5cacffa', BNCH_BUFFER_START, BNCH_BUFFER_END),
    ('bnch_pad_5cad02a', BNCH_PAD_START, BNCH_PAD_END),
    ('chmh_length_5cad02c', CHMH_LENGTH_START, CHMH_LENGTH_END),
    ('digest_object_5cad030', DIGEST_OBJECT, DIGEST_OBJECT_END),
)
CACHE_REGIONS = ('cache_header_5caced8', 'amnm_out_5cacef0', 'cache_payload_5cacef8')
CASE_ORDER = (
    'original-amnm-0-digest-missing',
    'fixture-amnm-nonzero-digest-missing',
    'fixture-digest-wrong-type',
    'fixture-digest-length-49',
)
CALL_ABI = {
    'id12_call': {'x0': hex(A.RUNTIME), 'x1': hex(CHIP_DESCRIPTOR), 'x2': 12,
                  'x3': hex(BOOL_OUT)},
    'id11_call': {'x0': hex(A.RUNTIME), 'x1': hex(CHIP_DESCRIPTOR), 'x2': 11,
                  'x3': hex(DIGEST_OBJECT)},
}
CASE_SEMANTICS = {
    'original-amnm-0-digest-missing': {
        'policy_u32': 0, 'wrong_type': None, 'id12': 0, 'id11': 2,
        'amnm_input': 0, 'store': 1, 'final_read': 1, 'branch': 1,
        'outcome': 'allow_missing_continues', 'stop_reason': 'boundary',
        'stop_pc': hex(DECISION_BOUNDARY), 'panic_errno': None, 'chmh_helper': 2,
    },
    'fixture-amnm-nonzero-digest-missing': {
        'policy_u32': 1, 'wrong_type': None, 'id12': 0, 'id11': 2,
        'amnm_input': 1, 'store': 0, 'final_read': 0, 'branch': 0,
        'outcome': 'panic', 'stop_reason': 'panic', 'stop_pc': hex(PANIC),
        'panic_errno': 2, 'chmh_helper': 2,
    },
    'fixture-digest-wrong-type': {
        'policy_u32': 0, 'wrong_type': HASH_KEY, 'id12': 0, 'id11': 96,
        'amnm_input': 0, 'store': 1, 'final_read': None, 'branch': None,
        'outcome': 'panic', 'stop_reason': 'panic', 'stop_pc': hex(PANIC),
        'panic_errno': 96, 'chmh_helper': 96,
    },
    'fixture-digest-length-49': {
        'policy_u32': 0, 'wrong_type': None, 'id12': 0, 'id11': 84,
        'amnm_input': 0, 'store': 1, 'final_read': None, 'branch': None,
        'outcome': 'panic', 'stop_reason': 'panic', 'stop_pc': hex(PANIC),
        'panic_errno': 84, 'chmh_helper': 84,
    },
}


def check_regions():
    if REGIONS[0][1] != CACHE_START or REGIONS[-1][2] != LEDGER_END:
        raise ValueError('Ledger region range changed')
    for left, right in zip(REGIONS, REGIONS[1:]):
        if left[2] != right[1]:
            raise ValueError('Ledger regions are not contiguous')
    if sum(end - start for _, start, end in REGIONS) != LEDGER_END - CACHE_START:
        raise ValueError('Ledger region byte count changed')


def raw_property(tree, path, key):
    node = C.find(tree, path)
    for name, flags, value in node['properties']:
        if name == key:
            return {'key': key, 'flags': hex(flags), 'length': len(value),
                    'value_hex': value.hex()}
    return None


def mutate(tree, path, key, value, flags=0):
    tree = copy.deepcopy(tree)
    node = C.find(tree, path)
    node['properties'] = [(k, f, v) for k, f, v in node['properties'] if k != key]
    if value is not None:
        node['properties'].append((key, flags, value))
    return C.encode(tree)


def case_adt(tree, policy=None, digest=None):
    data = C.encode(tree)
    if policy is not None:
        data = mutate(C.parse(data), '/chosen', POLICY_KEY, policy)
    if digest is not None:
        data = mutate(C.parse(data), '/chosen', HASH_KEY, digest)
    return data


def expected_case_data(tree, adt):
    return {
        CASE_ORDER[0]: adt,
        CASE_ORDER[1]: case_adt(tree, policy=b'\x01\0\0\0'),
        CASE_ORDER[2]: case_adt(tree, digest=bytes(48)),
        CASE_ORDER[3]: case_adt(tree, digest=bytes(49)),
    }


def snap(u):
    spans = {
        'bool_out': (BOOL_OUT, 8),
        'cache_header_5caced8': (CACHE_START, BOOL_OUT - CACHE_START),
        'cache_payload_5cacef8': (CACHE_PAYLOAD_START, CACHE_WINDOW_END - CACHE_PAYLOAD_START),
        'cache_window_5caced8_5cacffa': (CACHE_START, CACHE_WINDOW_END - CACHE_START),
        'bnch_buffer_5cacffa': (BNCH_BUFFER_START, BNCH_BUFFER_END - BNCH_BUFFER_START),
        'bnch_pad_5cad02a': (BNCH_PAD_START, BNCH_PAD_END - BNCH_PAD_START),
        'chmh_length_5cad02c': (CHMH_LENGTH_START, CHMH_LENGTH_END - CHMH_LENGTH_START),
        'digest_object': (DIGEST_OBJECT, DIGEST_OBJECT_END - DIGEST_OBJECT),
        'ledger_window': (CACHE_START, LEDGER_END - CACHE_START),
    }
    result = {name: bytes(u.mem_read(start, size)).hex()
              for name, (start, size) in spans.items()}
    result['bool_out_byte0'] = bytes(u.mem_read(BOOL_OUT, 1))[0]
    return result


def classify_write(lo, hi, value, size):
    segments = []
    for name, start, end in REGIONS:
        a, b = max(lo, start), min(hi, end)
        if a >= b:
            continue
        offset = a - lo
        width = b - a
        seg_value = (value >> (8 * offset)) & ((1 << (8 * width)) - 1)
        segments.append({'region': name, 'offset': offset, 'size': width,
                         'value': seg_value, 'start': hex(a), 'end': hex(b)})
    return segments, size - sum(s['size'] for s in segments)


def run_case(raw, macho, adt, wrong_type=False):
    model = A.Model(raw, macho, A.parse_adt(adt), wrong_type=wrong_type)
    u = model.u
    tree_va = 0xe00000
    u.mem_map(tree_va, B.align(len(adt)))
    u.mem_write(tree_va, adt)
    model.call(macho['symbols']['_SecureDTInit'], (tree_va, len(adt)))
    before = snap(u)
    trace, events = [], []
    ledger = []
    region_writes = {name: [] for name, _, _ in REGIONS}
    helper_calls, bool_reader_ids = [], []
    bool_context, helper_context = {'id': None}, {}
    stop = {'reason': None, 'pc': None, 'panic': None, 'variadic': None}

    def code(uc, pc, size, data):
        nonlocal helper_context
        trace.append(pc)
        if pc == PANIC:
            sp = uc.reg_read(A.UC_ARM64_REG_SP)
            stop.update(reason='panic', pc=pc,
                        panic=model.cstr(uc.reg_read(A.UC_ARM64_REG_X0)),
                        variadic=[model.get64(sp), model.get64(sp + 8)])
            uc.emu_stop()
            return
        if pc == DECISION_BOUNDARY:
            stop.update(reason='boundary', pc=pc)
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
            bool_context['id'] = uc.reg_read(A.UC_ARM64_REG_X2)
            bool_reader_ids.append(bool_context['id'])
        elif pc == BOOL_INPUT and bool_context['id'] == 12:
            events.append({'pc': hex(pc), 'event': 'amnm_property_value',
                           'w8': uc.reg_read(A.UC_ARM64_REG_W8) & 0xffffffff})
        elif pc == BOOL_STORE and bool_context['id'] == 12:
            events.append({'pc': hex(pc), 'event': 'amnm_store',
                           'byte': uc.reg_read(A.UC_ARM64_REG_W8) & 0xff})
        elif pc == DIGEST_CALL:
            events.append({'pc': hex(pc), 'event': 'id11_call',
                           'x0': hex(uc.reg_read(A.UC_ARM64_REG_X0)),
                           'x1': hex(uc.reg_read(A.UC_ARM64_REG_X1)),
                           'x2': uc.reg_read(A.UC_ARM64_REG_X2),
                           'x3': hex(uc.reg_read(A.UC_ARM64_REG_X3))})
        elif pc == DIGEST_RETURN:
            events.append({'pc': hex(pc), 'event': 'id11_return',
                           'w0': uc.reg_read(A.UC_ARM64_REG_W0) & 0xffffffff})
        elif pc == DIGEST_READER:
            events.append({'pc': hex(pc), 'event': 'digest_reader_entered',
                           'x2': uc.reg_read(A.UC_ARM64_REG_X2)})
        elif pc == HELPER:
            x3 = uc.reg_read(A.UC_ARM64_REG_X3)
            helper_context = {'key': model.cstr(uc.reg_read(A.UC_ARM64_REG_X1)),
                              'capacity': int.from_bytes(u.mem_read(x3, 4), 'little')}
        elif pc == 0xfffffff0046f08a0:
            rec = {**helper_context, 'w0': uc.reg_read(A.UC_ARM64_REG_W0) & 0xffffffff}
            helper_calls.append(rec)
            events.append({'pc': hex(pc), 'event': 'helper_return', **rec})
            helper_context = {}
        elif pc == FINAL_READ:
            events.append({'pc': hex(pc), 'event': 'final_read_5cacef0',
                           'byte': bytes(u.mem_read(BOOL_OUT, 1))[0]})
        elif pc == FINAL_BRANCH:
            events.append({'pc': hex(pc), 'event': 'final_branch_5cacef0',
                           'w8': uc.reg_read(A.UC_ARM64_REG_W8) & 0xff})
        elif pc == PANIC_SITE:
            events.append({'pc': hex(pc), 'event': 'panic_site',
                           'x0': uc.reg_read(A.UC_ARM64_REG_X0) & 0xffffffff})

    def write(uc, access, address, size, value, data):
        lo, hi = address, address + size
        segments, unclassified = classify_write(lo, hi, value, size)
        rec = {'index': len(ledger),
               'pc': hex(uc.reg_read(A.UC_ARM64_REG_PC)),
               'address': hex(lo), 'size': size, 'value': value,
               'segments': segments,
               'fully_classified': unclassified == 0,
               'unclassified_bytes': unclassified}
        ledger.append(rec)
        for seg in segments:
            region_writes[seg['region']].append({
                'ledger_index': rec['index'], 'pc': rec['pc'],
                'write_address': rec['address'], 'write_size': rec['size'], **seg})

    u.hook_add(U.UC_HOOK_CODE, code)
    u.hook_add(U.UC_HOOK_MEM_WRITE, write, begin=CACHE_START, end=LEDGER_END - 1)
    for i in range(19, 30):
        u.reg_write(getattr(A, 'UC_ARM64_REG_X%d' % i), 0x11220000 + i * 0x100)
    u.reg_write(A.UC_ARM64_REG_X0, A.PMAP_RUNTIME)
    u.reg_write(A.UC_ARM64_REG_LR, STACK_SENTINEL)
    u.reg_write(A.UC_ARM64_REG_SP, A.STACK + 0x8000)
    error = None
    try:
        u.emu_start(ENTRY, STACK_SENTINEL, count=RUN_COUNT)
    except U.UcError as exc:
        error = str(exc)
    pc = u.reg_read(A.UC_ARM64_REG_PC)
    if stop['reason'] is None:
        if model.bad:
            stop.update(reason='unmodelled_memory', pc=pc)
        elif pc == STACK_SENTINEL:
            stop.update(reason='returned_to_sentinel', pc=pc)
        else:
            stop.update(reason='unmodelled_stop', pc=pc)
    if error:
        stop['error'] = error
    after = snap(u)
    stub_pcs = set(model.hooks)
    donor = [p for p in trace if p >= 0xfffffff000000000 and p not in stub_pcs]
    cache_window = []
    for name in CACHE_REGIONS:
        cache_window.extend(region_writes[name])
    cache_window.sort(key=lambda s: (s['ledger_index'], s['offset']))
    return {
        'stop': {**stop, 'pc': hex(stop['pc']) if stop.get('pc') is not None else None},
        'model_bad': model.bad,
        'events': events,
        'helper_calls': helper_calls,
        'bool_reader_ids': bool_reader_ids,
        'fixture_events': list(model.events),
        'writes_ledger': ledger,
        'ledger_write_count': len(ledger),
        'ledger_fully_classified': all(r['fully_classified'] for r in ledger),
        'ledger_unclassified_bytes': sum(r['unclassified_bytes'] for r in ledger),
        'region_byte_counts': {name: sum(s['size'] for s in segs)
                               for name, segs in region_writes.items()},
        'writes_5cacef0': region_writes['amnm_out_5cacef0'],
        'writes_cache_header_5caced8': region_writes['cache_header_5caced8'],
        'writes_cache_payload_5cacef8': region_writes['cache_payload_5cacef8'],
        'writes_cache_window_5caced8_5cacffa': cache_window,
        'writes_bnch_buffer_5cacffa': region_writes['bnch_buffer_5cacffa'],
        'writes_bnch_pad_5cad02a': region_writes['bnch_pad_5cad02a'],
        'writes_chmh_length_5cad02c': region_writes['chmh_length_5cad02c'],
        'writes_digest_5cad030': region_writes['digest_object_5cad030'],
        'before': before,
        'after': after,
        'donor_pc_count': len(donor),
        'donor_pc_unique': len(set(donor)),
        'donor_pc_min': hex(min(donor)) if donor else None,
        'donor_pc_max': hex(max(donor)) if donor else None,
        'executed_donor_pcs': [hex(p) for p in donor],
        'stubbed_boundary_pcs': sorted(hex(p) for p in stub_pcs),
        'fixture_pc_count': len(trace) - len(donor),
    }


def validate_report(report, raw, adt):
    """Check exact report semantics; return logical semantic check groups."""
    check_regions()
    checks = []

    def require(condition, message):
        if not condition:
            raise ValueError(message)

    def group(name, fn):
        fn()
        checks.append({'name': name, 'passed': True})

    kernel_sha, adt_sha = B.sha(raw), B.sha(adt)
    require(report['entry'] == hex(ENTRY), 'entry changed')
    require(report['decision_boundary'] == hex(DECISION_BOUNDARY), 'boundary changed')
    require(report['panic_entry'] == hex(PANIC), 'panic entry changed')
    require(report['inputs']['kernel']['sha256'] == kernel_sha, 'kernel pin changed')
    require(report['inputs']['adt']['sha256'] == adt_sha, 'ADT pin changed')
    require(report['dependencies']['kernel_sha256'] == kernel_sha, 'dependency kernel changed')
    require(report['dependencies']['adt_sha256'] == adt_sha, 'dependency ADT changed')
    require(report['dependencies']['source_sha256'] ==
            B.sha(Path(__file__).read_bytes()), 'source hash changed')
    reused = report['dependencies']['reused_source_sha256']
    for rel in ('scripts/audit-image4-runtime-provider.py',
                'scripts/build-kernel-entry-probe.py',
                'scripts/nuwa_launch_context.py'):
        require(reused.get(rel) == B.sha((ROOT / rel).read_bytes()),
                'reused source hash changed: ' + rel)
    provenance = report['provenance']
    require(provenance['pmap_plus_0x10_initializer'] == hex(ENTRY), 'provenance initializer')
    require(provenance['pmap_plus_0x58_runtime'] == hex(A.RUNTIME), 'provenance runtime')
    require(provenance['runtime_plus_0x38_bool_reader'] == hex(BOOL_READER),
            'provenance bool reader')
    require(provenance['runtime_plus_0x50_digest_reader'] == hex(DIGEST_READER),
            'provenance digest reader')
    require(report['original_amnm_property'] ==
            {'key': POLICY_KEY, 'flags': '0x0', 'length': 4, 'value_hex': '00000000'},
            'original AMNM property changed')
    require(report['original_digest_property'] is None, 'original CHMH must be absent')
    require(report['classification']['bnch_buffer_is_not_cache'] is True,
            'classification BNCH statement changed')
    require(report['stop_semantics']['per_dependency_admission'] is False,
            'stop semantics must not claim per-dependency admission')
    require(report['trace_scope']['initializer_epilogue_46e9f00_executed'] is False,
            'epilogue claim changed')

    expected = expected_case_data(C.parse(adt), adt)
    require(list(report['cases']) == list(CASE_ORDER), 'case order/set changed')
    for name in CASE_ORDER:
        case = report['cases'][name]
        sem = CASE_SEMANTICS[name]
        data = expected[name]
        observed = case['observed']

        def case_identity():
            require(case['adt_sha256'] == B.sha(data), name + ': ADT hash changed')
            case_tree = C.parse(data)
            require(case['amnm_property'] == raw_property(case_tree, '/chosen', POLICY_KEY),
                    name + ': AMNM property shape/value changed')
            require(case['digest_property'] == raw_property(case_tree, '/chosen', HASH_KEY),
                    name + ': CHMH property shape/value changed')
            require(case['policy_u32'] == sem['policy_u32'], name + ': policy fixture changed')
            require(case['wrong_type'] == sem['wrong_type'], name + ': wrong-type fixture changed')
        group(name + ': identity/fixture', case_identity)

        def call_abi():
            for key in ('id12_call', 'id11_call'):
                call = observed[key]
                for field, value in CALL_ABI[key].items():
                    require(call.get(field) == value,
                            name + ': ' + key + ' ' + field + ' changed')
        group(name + ': id12/id11 call ABI', call_abi)

        def reader_semantics():
            require(observed['id12_return_w0'] == sem['id12'], name + ': id12 return changed')
            require(observed['id11_return_w0'] == sem['id11'], name + ': id11 return changed')
            require(observed['amnm_property_w8'] == sem['amnm_input'],
                    name + ': AMNM input value changed')
            require(observed['amnm_store_byte'] == sem['store'],
                    name + ': AMNM store value changed')
            require(observed['final_read_5cacef0'] == sem['final_read'],
                    name + ': final load changed')
            require(observed['final_branch_w8'] == sem['branch'],
                    name + ': final branch changed')
            require(observed['amnm_helper'] ==
                    [{'key': POLICY_KEY, 'capacity': 4, 'w0': 0}],
                    name + ': AMNM helper shape/errno changed')
            chmh = observed['chmh_helper']
            require(len(chmh) == 1 and chmh[0].get('key') == HASH_KEY
                    and chmh[0].get('capacity') == 48
                    and chmh[0].get('w0') == sem['chmh_helper'],
                    name + ': CHMH helper shape/errno changed')
            require(observed['bool_reader_identifiers'] == [5, 6, 7, 8, 9, 13, 10, 12],
                    name + ': bool reader identifier sequence changed')
        group(name + ': AMNM/CHMH reader semantics', reader_semantics)

        def write_semantics():
            def tie(segments, label):
                seen = set()
                for seg in segments:
                    index = seg.get('ledger_index')
                    require(isinstance(index, int) and 0 <= index < len(case['writes_ledger']),
                            name + ': ' + label + ' ledger index invalid')
                    core = {key: seg.get(key) for key in
                            ('region', 'offset', 'size', 'value', 'start', 'end')}
                    require(core in case['writes_ledger'][index]['segments'],
                            name + ': ' + label + ' not tied to the raw ledger')
                    key = (index, seg.get('offset'), seg.get('region'))
                    require(key not in seen, name + ': ' + label + ' duplicate segment')
                    seen.add(key)

            writes = case['writes_5cacef0']
            require(len(writes) == 1, name + ': AMNM output write count changed')
            write = writes[0]
            require(write.get('pc') == hex(BOOL_STORE)
                    and write.get('start') == hex(BOOL_OUT)
                    and write.get('size') == 1
                    and write.get('value') == sem['store'],
                    name + ': AMNM output write fields changed')
            require(case['writes_digest_5cad030'] == [],
                    name + ': digest object must have no writes')
            require(case['writes_cache_header_5caced8'] == [],
                    name + ': cache header must have no writes')
            require(len(case['writes_cache_payload_5cacef8']) > 0,
                    name + ': cache payload must be populated')
            require(len(case['writes_bnch_buffer_5cacffa']) > 0,
                    name + ': BNCH buffer writes must be present')
            require(all(s.get('region') in CACHE_REGIONS
                        for s in case['writes_cache_window_5caced8_5cacffa']),
                    name + ': cache window contains a non-cache region')
            require(all(s.get('region') == 'bnch_buffer_5cacffa'
                        for s in case['writes_bnch_buffer_5cacffa']),
                    name + ': BNCH region misclassified')
            tie(case['writes_cache_window_5caced8_5cacffa'], 'cache window')
            tie(case['writes_bnch_buffer_5cacffa'], 'BNCH buffer')
            tie(case['writes_chmh_length_5cad02c'], 'CHMH length')
            tie(case['writes_digest_5cad030'], 'digest object')
            length_writes = case['writes_chmh_length_5cad02c']
            require(len(length_writes) == 1
                    and length_writes[0].get('pc') == '0xfffffff0046e9ab4'
                    and length_writes[0].get('start') == hex(CHMH_LENGTH_START)
                    and length_writes[0].get('size') == 4
                    and length_writes[0].get('value') == 48,
                    name + ': CHMH length write changed')
            require(case['ledger_fully_classified'] is True
                    and case['ledger_unclassified_bytes'] == 0,
                    name + ': ledger has unclassified bytes')
            require(sum(case['region_byte_counts'].values()) ==
                    sum(rec['size'] for rec in case['writes_ledger']),
                    name + ': region byte counts do not close the ledger')
            require(case['ledger_write_count'] == len(case['writes_ledger']),
                    name + ': ledger count changed')
        group(name + ': write-ledger classification', write_semantics)

        def state_semantics():
            require(case['before']['bool_out_byte0'] == 0,
                    name + ': AMNM output was pre-filled')
            require(case['before']['digest_object'] == case['after']['digest_object'],
                    name + ': digest object changed')
            require(case['observed']['digest_object_unchanged'] is True,
                    name + ': digest object unchanged flag changed')
            require(case['before']['cache_header_5caced8'] ==
                    case['after']['cache_header_5caced8'],
                    name + ': cache header changed')
            require(case['observed']['cache_header_5caced8_unchanged'] is True,
                    name + ': cache header unchanged flag changed')
            require(case['after']['chmh_length_5cad02c'] == '30000000',
                    name + ': CHMH length state changed')
        group(name + ': independent state snapshots', state_semantics)

        def exit_semantics():
            require(case['outcome'] == sem['outcome'], name + ': outcome changed')
            require(case['stop']['reason'] == sem['stop_reason'],
                    name + ': stop reason changed')
            require(case['stop']['pc'] == sem['stop_pc'], name + ': stop PC changed')
            require(case['model_bad'] == [], name + ': invalid memory recorded')
            if sem['panic_errno'] is None:
                require(case['stop']['panic'] is None and case['stop']['variadic'] is None,
                        name + ': unexpected panic')
                require(observed['panic_site_x0'] is None, name + ': unexpected panic site')
            else:
                require(case['stop']['panic'] == PANIC_TEXT,
                        name + ': panic format changed')
                require(case['stop']['variadic']
                        and case['stop']['variadic'][0] == sem['panic_errno'],
                        name + ': panic errno changed')
                require(observed['panic_site_x0'] == sem['panic_errno'],
                        name + ': panic-site errno changed')
            require(case['real_exit_matches_expected'] is True,
                    name + ': expected-exit flag changed')
            invariants = case['invariants']
            passed = (all(invariants.values()) if isinstance(invariants, dict)
                      else all(c['passed'] for c in invariants))
            require(passed, name + ': mechanical invariant failed')
        group(name + ': real exit/panic', exit_semantics)

        def trace_semantics():
            pcs = set(case['executed_donor_pcs'])
            require(hex(ENTRY) in pcs, name + ': entry not in trace')
            require(hex(BOOL_READER) in pcs and hex(DIGEST_READER) in pcs,
                    name + ': real readers not in trace')
            require(hex(EPILOGUE_RET) not in pcs, name + ': initializer epilogue in trace')
            if sem['stop_reason'] == 'boundary':
                require(hex(DECISION_BOUNDARY) in pcs and hex(PANIC) not in pcs,
                        name + ': boundary trace changed')
                require(hex(PANIC_SITE) not in pcs, name + ': panic site in boundary case')
            else:
                require(hex(PANIC) in pcs and hex(PANIC_SITE) in pcs,
                        name + ': panic trace changed')
                require(hex(DECISION_BOUNDARY) not in pcs,
                        name + ': boundary in panic case')
            require(case['donor_pc_count'] > 0 and case['donor_pc_min']
                    and case['donor_pc_max'], name + ': empty trace')
        group(name + ': trace bounds', trace_semantics)

    require(all(c['passed'] for c in report['mechanical_checks'])
            if 'mechanical_checks' in report else True,
            'mechanical checks contain a failure')
    return checks


def negative_mutations(report, raw, adt):
    K = CASE_ORDER[0]
    N = CASE_ORDER[1]
    fake = {'ledger_index': 0, 'region': 'bnch_buffer_5cacffa',
            'pc': '0x0', 'address': hex(BNCH_BUFFER_START), 'size': 1,
            'value': 0, 'offset': 0, 'start': hex(BNCH_BUFFER_START),
            'end': hex(BNCH_BUFFER_START + 1)}
    mutations = (
        ('id12 x2', lambda r: r['cases'][K]['observed']['id12_call'].__setitem__('x2', 11)),
        ('id12 x3', lambda r: r['cases'][K]['observed']['id12_call'].__setitem__(
            'x3', hex(DIGEST_OBJECT))),
        ('id11 x2', lambda r: r['cases'][K]['observed']['id11_call'].__setitem__('x2', 12)),
        ('original AMNM length', lambda r: r['cases'][K]['amnm_property'].__setitem__(
            'length', 3)),
        ('original AMNM store', lambda r: r['cases'][K]['observed'].__setitem__(
            'amnm_store_byte', 0)),
        ('original final load', lambda r: r['cases'][K]['observed'].__setitem__(
            'final_read_5cacef0', 0)),
        ('original final branch', lambda r: r['cases'][K]['observed'].__setitem__(
            'final_branch_w8', 0)),
        ('original CHMH errno', lambda r: r['cases'][K]['observed']['chmh_helper'][0]
            .__setitem__('w0', 0)),
        ('negative id11 errno', lambda r: r['cases'][N]['observed'].__setitem__(
            'id11_return_w0', 0)),
        ('negative panic errno', lambda r: r['cases'][N]['stop']['variadic'].__setitem__(0, 0)),
        ('digest write nonempty', lambda r: r['cases'][K]['writes_digest_5cad030'].append(fake)),
        ('cache header write nonempty', lambda r: r['cases'][K]
            ['writes_cache_header_5caced8'].append(fake)),
        ('cache window BNCH write', lambda r: r['cases'][K]
            ['writes_cache_window_5caced8_5cacffa'].append(fake)),
        ('CHMH length write empty', lambda r: r['cases'][K].__setitem__(
            'writes_chmh_length_5cad02c', [])),
        ('CHMH length value', lambda r: r['cases'][K]['writes_chmh_length_5cad02c'][0]
            .__setitem__('value', 47)),
        ('BNCH writes empty', lambda r: r['cases'][K].__setitem__(
            'writes_bnch_buffer_5cacffa', [])),
        ('cache payload writes empty', lambda r: r['cases'][K].__setitem__(
            'writes_cache_payload_5cacef8', [])),
        ('epilogue in trace', lambda r: r['cases'][K]['executed_donor_pcs'].append(
            hex(EPILOGUE_RET))),
        ('stop pc', lambda r: r['cases'][K]['stop'].__setitem__('pc', hex(PANIC))),
        ('case ADT hash', lambda r: r['cases'][K].__setitem__('adt_sha256', '0' * 64)),
        ('input ADT hash', lambda r: r['inputs']['adt'].__setitem__('sha256', '0' * 64)),
        ('source hash', lambda r: r['dependencies'].__setitem__('source_sha256', '0' * 64)),
        ('region byte count', lambda r: r['cases'][K]['region_byte_counts'].__setitem__(
            'cache_header_5caced8', 1)),
        ('ledger classification flag', lambda r: r['cases'][K].__setitem__(
            'ledger_fully_classified', False)),
        ('digest unchanged flag', lambda r: r['cases'][K]['observed'].__setitem__(
            'digest_object_unchanged', False)),
    )
    results = []
    for label, mutate in mutations:
        candidate = copy.deepcopy(report)
        mutate(candidate)
        try:
            validate_report(candidate, raw, adt)
        except ValueError as exc:
            results.append({'mutation': label, 'rejected': True, 'reason': str(exc)})
        else:
            results.append({'mutation': label, 'rejected': False,
                            'reason': 'validator accepted a changed field'})
    return results


def write_exclusive(path, payload):
    path = path.resolve()
    if path.suffix != '.json' or not path.is_relative_to(ROOT / 'out'):
        raise ValueError('Output must be a JSON file under out/')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', newline='\n') as handle:
        handle.write(json.dumps(payload, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel', required=True, type=Path)
    parser.add_argument('--kernel-sha256', required=True)
    parser.add_argument('--adt', required=True, type=Path)
    parser.add_argument('--adt-sha256', required=True)
    parser.add_argument('--output', type=Path,
                        help='Fresh evidence JSON under out/')
    parser.add_argument('--negative-self-check', type=Path,
                        help='Existing report to validate and mutate')
    parser.add_argument('--negative-output', type=Path,
                        help='Fresh negative-check JSON under out/')
    args = parser.parse_args()
    raw, adt = args.kernel.read_bytes(), args.adt.read_bytes()
    if B.sha(raw) != args.kernel_sha256:
        raise ValueError('Kernel hash does not match the pinned input')
    if B.sha(adt) != args.adt_sha256:
        raise ValueError('ADT hash does not match the pinned input')
    check_regions()
    macho = B.macho(raw)
    tree = C.parse(adt)
    policy = raw_property(tree, '/chosen', POLICY_KEY)
    digest = raw_property(tree, '/chosen', HASH_KEY)
    if policy != {'key': POLICY_KEY, 'flags': '0x0', 'length': 4,
                  'value_hex': '00000000'}:
        raise ValueError('Pinned ADT AMNM property changed: %r' % (policy,))
    if digest is not None:
        raise ValueError('Pinned ADT unexpectedly contains ' + HASH_KEY)
    probe = A.Model(raw, macho, A.parse_adt(adt))
    pmap_init = probe.get64(A.PMAP_RUNTIME + 0x10)
    runtime = probe.get64(A.PMAP_RUNTIME + 0x58)
    readers = {0x38: probe.get64(runtime + 0x38), 0x50: probe.get64(runtime + 0x50)}
    del probe
    gc.collect()
    if (pmap_init, runtime, readers[0x38], readers[0x50]) != (
            ENTRY, A.RUNTIME, BOOL_READER, DIGEST_READER):
        raise ValueError('Unexpected initializer/runtime/reader binding')

    if args.negative_self_check:
        if not args.negative_output:
            raise ValueError('--negative-output is required with --negative-self-check')
        report_bytes = args.negative_self_check.read_bytes()
        report = json.loads(report_bytes)
        validate_report(report, raw, adt)
        results = negative_mutations(report, raw, adt)
        rejected = sum(1 for r in results if r['rejected'])
        payload = {
            'scope': 'Single-field report tamper negatives for the Image4 AMNM/CHMH host runner',
            'status': 'self-checked host evidence',
            'report': str(args.negative_self_check),
            'report_sha256': B.sha(report_bytes),
            'source_sha256': B.sha(Path(__file__).read_bytes()),
            'kernel_sha256': B.sha(raw), 'adt_sha256': B.sha(adt),
            'positive_validation': 'pass',
            'mutations': results,
            'all_rejected': rejected == len(results),
            'rejected': rejected, 'total': len(results),
            'note': ('A rejected mutation means the independent report validator caught the '
                     'single changed field; the generator is not simply compared with itself.'),
        }
        write_exclusive(args.negative_output, payload)
        print(json.dumps({'positive_validation': 'pass', 'rejected': rejected,
                          'total': len(results), 'all_rejected': rejected == len(results),
                          'output': str(args.negative_output.resolve())}))
        if rejected != len(results):
            sys.exit(1)
        return

    if not args.output:
        raise ValueError('--output is required for a normal run')
    mechanical = [
        {'name': 'provider table +0x10 selects 46e98cc', 'passed': True},
        {'name': 'PMAP +0x58 selects the Darwin runtime 5cb14d8', 'passed': True},
        {'name': 'runtime +0x38 selects the bool reader 46efe7c', 'passed': True},
        {'name': 'runtime +0x50 selects the digest reader 46f021c', 'passed': True},
    ]
    expected = expected_case_data(tree, adt)
    cases = (
        (CASE_ORDER[0], adt, 0, False),
        (CASE_ORDER[1], expected[CASE_ORDER[1]], 1, False),
        (CASE_ORDER[2], expected[CASE_ORDER[2]], 0, HASH_KEY),
        (CASE_ORDER[3], expected[CASE_ORDER[3]], 0, False),
    )
    report_cases = {}
    for name, data, policy_value, wrong_type in cases:
        result = run_case(raw, macho, data, wrong_type)
        case_tree = C.parse(data)
        result.update(case=name, adt_sha256=B.sha(data), policy_u32=policy_value,
                      wrong_type=HASH_KEY if wrong_type else None,
                      amnm_property=raw_property(case_tree, '/chosen', POLICY_KEY),
                      digest_property=raw_property(case_tree, '/chosen', HASH_KEY),
                      expected=CASE_SEMANTICS[name]['outcome'])
        entry_events = {e['event']: e for e in result['events']
                        if e['event'] != 'helper_return'}
        helpers = result['helper_calls']
        result['observed'] = {
            'id12_return_w0': entry_events.get('id12_return', {}).get('w0'),
            'id11_return_w0': entry_events.get('id11_return', {}).get('w0'),
            'amnm_property_w8': entry_events.get('amnm_property_value', {}).get('w8'),
            'amnm_store_byte': entry_events.get('amnm_store', {}).get('byte'),
            'final_read_5cacef0': entry_events.get('final_read_5cacef0', {}).get('byte'),
            'final_branch_w8': entry_events.get('final_branch_5cacef0', {}).get('w8'),
            'panic_site_x0': entry_events.get('panic_site', {}).get('x0'),
            'bool_output_pointer': entry_events.get('bool_output_pointer', {}).get('x3'),
            'id12_call': entry_events.get('id12_call'),
            'id11_call': entry_events.get('id11_call'),
            'helper_returns': [h['w0'] for h in helpers],
            'amnm_helper': [h for h in helpers if h.get('key') == POLICY_KEY],
            'chmh_helper': [h for h in helpers if h.get('key') == HASH_KEY],
            'bool_reader_identifiers': result['bool_reader_ids'],
            'digest_object_written': bool(result['writes_digest_5cad030']),
            'digest_object_unchanged': (
                result['before']['digest_object'] == result['after']['digest_object']),
            'cache_header_5caced8_written': bool(result['writes_cache_header_5caced8']),
            'cache_header_5caced8_unchanged': (
                result['before']['cache_header_5caced8'] ==
                result['after']['cache_header_5caced8']),
            'cache_payload_5cacef8_written': bool(result['writes_cache_payload_5cacef8']),
            'cache_window_non_cache_regions': sorted({
                s['region'] for s in result['writes_cache_window_5caced8_5cacffa']
                if s['region'] not in CACHE_REGIONS}),
            'bnch_buffer_5cacffa_written': bool(result['writes_bnch_buffer_5cacffa']),
            'chmh_length_5cad02c_written': bool(result['writes_chmh_length_5cad02c']),
            'bool_out_initial_zero': result['before']['bool_out_byte0'] == 0,
        }
        if result['stop']['reason'] == 'boundary':
            outcome = 'allow_missing_continues'
        elif result['stop']['reason'] == 'panic':
            outcome = 'panic'
        else:
            outcome = result['stop']['reason']
        result['outcome'] = outcome
        panic_ok = (result['stop']['reason'] == 'panic'
                    and result['stop']['panic'] == PANIC_TEXT
                    and result['stop']['variadic']
                    and result['stop']['variadic'][0] in (2, 84, 96))
        result['real_exit_matches_expected'] = (
            (name == CASE_ORDER[0] and outcome == 'allow_missing_continues')
            or (name == CASE_ORDER[1] and panic_ok
                and result['stop']['variadic'][0] == 2)
            or (name == CASE_ORDER[2] and panic_ok
                and result['stop']['variadic'][0] == 96)
            or (name == CASE_ORDER[3] and panic_ok
                and result['stop']['variadic'][0] == 84))
        if name == CASE_ORDER[0]:
            result['conclusion'] = (
                'The in-package ADT (AMNM u32=0, boot-manifest-hash absent) executes the '
                'real AMNM reader to 5cacef0 byte 1 and continues past 46e9b2c without '
                'panic under the ADT-backed IOKit fixture; this input cannot reproduce the '
                'device panic state. This is host evidence only, not a device or '
                'authentication result.')
        writes = result['writes_5cacef0']
        result['invariants'] = {
            'no_invalid_memory': not result['model_bad'],
            'bool_out_initial_zero': result['before']['bool_out_byte0'] == 0,
            'single_real_amnm_store': (
                len(writes) == 1 and writes[0]['pc'] == hex(BOOL_STORE)
                and writes[0]['start'] == hex(BOOL_OUT) and writes[0]['size'] == 1),
            'amnm_reader_capacity_4': (
                len(result['observed']['amnm_helper']) == 1
                and result['observed']['amnm_helper'][0]['capacity'] == 4
                and result['observed']['id12_return_w0'] == 0),
            'chmh_reader_capacity_48': (
                len(result['observed']['chmh_helper']) == 1
                and result['observed']['chmh_helper'][0]['capacity'] == 48),
            'digest_write_list_empty': result['writes_digest_5cad030'] == [],
            'cache_header_write_list_empty': result['writes_cache_header_5caced8'] == [],
            'bnch_write_list_present': bool(result['writes_bnch_buffer_5cacffa']),
            'chmh_length_write_present': bool(result['writes_chmh_length_5cad02c']),
            'ledger_fully_classified': result['ledger_fully_classified'],
            'bounded_stop_reason': (
                (name == CASE_ORDER[0] and result['stop']['reason'] == 'boundary')
                or (name != CASE_ORDER[0] and result['stop']['reason'] == 'panic')),
            'panic_from_46e9f64': (
                (name == CASE_ORDER[0] and result['observed']['panic_site_x0'] is None)
                or (name != CASE_ORDER[0]
                    and result['observed']['panic_site_x0']
                    == result['stop']['variadic'][0])),
        }
        for label, passed in result['invariants'].items():
            mechanical.append({'name': name + ': ' + label, 'passed': passed})
        report_cases[name] = result
        del result
        gc.collect()

    report = {
        'scope': __doc__,
        'status': 'self-checked host evidence',
        'entry': hex(ENTRY),
        'decision_boundary': hex(DECISION_BOUNDARY),
        'panic_entry': hex(PANIC),
        'inputs': {
            'kernel': {'path': str(args.kernel), 'bytes': len(raw), 'sha256': B.sha(raw)},
            'adt': {'path': str(args.adt), 'bytes': len(adt), 'sha256': B.sha(adt)},
        },
        'provenance': {
            'pmap_runtime_table': hex(A.PMAP_RUNTIME),
            'pmap_plus_0x10_initializer': hex(ENTRY),
            'pmap_plus_0x58_runtime': hex(A.RUNTIME),
            'runtime_plus_0x38_bool_reader': hex(BOOL_READER),
            'runtime_plus_0x50_digest_reader': hex(DIGEST_READER),
            'chip_descriptor': hex(CHIP_DESCRIPTOR),
            'amnm_output_5cacef0': hex(BOOL_OUT),
            'digest_object_5cad030': hex(DIGEST_OBJECT),
        },
        'execution_envelope': {
            'start': hex(ENTRY),
            'bounded_stop': hex(DECISION_BOUNDARY),
            'panic_entry': hex(PANIC),
            'instruction_budget': RUN_COUNT,
        },
        'classification': {
            'ledger_range': [hex(CACHE_START), hex(LEDGER_END)],
            'regions': [{'name': name, 'start': hex(start), 'end': hex(end)}
                        for name, start, end in REGIONS],
            'cache_window': [hex(CACHE_START), hex(CACHE_WINDOW_END)],
            'bnch_buffer': [hex(BNCH_BUFFER_START), hex(BNCH_BUFFER_END)],
            'chmh_length': [hex(CHMH_LENGTH_START), hex(CHMH_LENGTH_END)],
            'digest_object': [hex(DIGEST_OBJECT), hex(DIGEST_OBJECT_END)],
            'crossing_writes': 'split by byte into per-region segments; each byte counted once',
            'bnch_buffer_is_not_cache': True,
            'chmh_length_is_not_cache': True,
        },
        'stop_semantics': {
            'recognized_stops': [
                'post-decision boundary 46e9b2c', 'panic entry 46fa028',
                'invalid memory', 'Unicorn exception', 'instruction budget'],
            'per_dependency_admission': False,
            'unexpected_stop_is_reported_not_classified': True,
            'first_unmodelled_dependency_claimed': False,
        },
        'trace_scope': {
            'start': hex(ENTRY),
            'end': '46e9b2c or panic entry only',
            'initializer_epilogue_46e9f00_executed': False,
            'secure_dt_init_writes_in_ledger': False,
            'fixture_is_live_ioregistry': False,
        },
        'original_amnm_property': policy,
        'original_digest_property': digest,
        'modeled_boundaries': [
            'IORegistryEntry::fromPath (ADT path fixture)',
            'IORegistryEntry::getProperty/release (ADT node fixture)',
            'OSMetaClassBase::safeMetaCast (OSData type fixture)',
            'OSData::getLength/getBytesNoCopy (ADT property bytes fixture)',
            'Image4 runtime logging stub',
        ],
        'real_code': [
            'initializer 46e98cc entry through the bounded decision; epilogue not executed',
            'AMNM bool reader 46efe7c', 'CHMH digest reader 46f021c',
            'property helper 46f07e8',
            'all comparisons, conversions, copies, branches and panic calls',
            'SecureDTInit/SecureDTLookupEntry (before the traced run)',
        ],
        'dependencies': {
            'kernel_sha256': B.sha(raw), 'adt_sha256': B.sha(adt),
            'unicorn': getattr(U, '__version__', None),
            'python': sys.version.split()[0],
            'source_sha256': B.sha(Path(__file__).read_bytes()),
            'reused_source_sha256': {
                rel: B.sha((ROOT / rel).read_bytes()) for rel in (
                    'scripts/audit-image4-runtime-provider.py',
                    'scripts/build-kernel-entry-probe.py',
                    'scripts/nuwa_launch_context.py')
            },
        },
        'semantic_checks': [],
        'mechanical_checks': mechanical,
        'check_note': ('semantic_checks are logical groups from the independent report '
                       'validator; mechanical_checks are structural invariants. Neither '
                       'count is a count of independent semantic proofs.'),
        'cases': report_cases,
        'device_comparison': {
            'device_panic': 'failed to get previous stage manifest hash: 2 (parent/deep supplied)',
            'host_original': report_cases[CASE_ORDER[0]]['outcome'],
            'host_is_not_device_proof': True,
            'host_conclusion': ('the in-package input cannot reproduce the device panic state'
                                if report_cases[CASE_ORDER[0]]['outcome']
                                == 'allow_missing_continues' else
                                'the host reproduces a terminal panic from the same package '
                                'input; compare the observed errno with the device errno'),
            'next_investigation': ('only the existing loader->SecureDT->IORegistry conversion/'
                                   'execution binding, not a new fix or device run'),
        },
        'limitations': [
            'ADT-backed IOKit/OSData objects are fixtures, not a live IORegistry snapshot.',
            'No device, no real boot, no Apple trust chain, no authentication.',
            'X0 is the PMAP_CS table; the prologue selects the Darwin runtime via +0x58.',
            'Wrong-type/length cases mutate an independent ADT fixture in memory only; the pinned candidate and ADT are unchanged.',
            'The write ledger covers only the traced initializer interval; SecureDTInit writes before it are not included.',
            'Window writes are not a complete record of all initializer state writes.',
            'If the original input allows the missing digest, the next investigation is limited to the existing loader->SecureDT->IORegistry conversion/execution binding.',
            'The runner stops on invalid memory/exception/budget as well as boundary/panic; it does not implement per-dependency admission.',
        ],
        'device_accessed': False,
        'kernel_modified': False,
        'adt_modified': False,
    }
    semantic = validate_report(report, raw, adt)
    report['semantic_checks'] = semantic
    failed = [c['name'] for c in mechanical if not c['passed']]
    if failed:
        raise ValueError('Mechanical checks failed: ' + ', '.join(failed))
    write_exclusive(args.output, report)
    print(json.dumps({
        'semantic_checks': len(semantic),
        'mechanical_checks': len(mechanical),
        'failed_mechanical': failed,
        'original_outcome': report_cases[CASE_ORDER[0]]['outcome'],
        'output': str(args.output.resolve())}))


if __name__ == '__main__':
    main()
