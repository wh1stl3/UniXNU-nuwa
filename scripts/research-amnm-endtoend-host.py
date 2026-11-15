"""Single-thread host execution of the final instrumented initializer.

Only the exact LDADDAL x10,x11,[x9] encoding is modelled. This says nothing
about hardware atomicity. IOKit objects are the existing ADT-backed fixtures.
"""
import ctypes
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('initializer', ROOT / 'scripts/research-current-image4-initializer-amnm.py')
I = importlib.util.module_from_spec(spec)
spec.loader.exec_module(I)
A, B, U = I.A, I.B, I.U
KERNEL = Path('/root/nuwa-amnm-final-candidate-stage3-20261111/kernel-amnm.macho')
ADT = ROOT / 'out/owner-pmap-ret-continuation-verifier-final-20261111/adt-generation/final.adt'
OUT = ROOT / 'out/amnm-endtoend-host-20261112'
PIN_K = '1754a89e8e92e20baafeaf0e1f98361b0d41ddaea8f420dd44d34d1357f2d162'
PIN_A = '885094de4597fb2d1734ba4092c805968097d021c8f482653b238436586d27a4'
sha = lambda b: hashlib.sha256(b).hexdigest()


class Slot(ctypes.Structure):
    _fields_ = [('commit', ctypes.c_uint64), ('kind', ctypes.c_uint64), ('payload', ctypes.c_uint64 * 10)]


class Log(ctypes.Structure):
    _fields_ = [('next', ctypes.c_uint64), ('reserved', ctypes.c_uint8 * 120), ('slots', Slot * 16), ('summary', ctypes.c_char * 256)]


class Snapshot(ctypes.Structure):
    _fields_ = [('count', ctypes.c_uint64), ('n1', ctypes.c_uint64), ('n2', ctypes.c_uint64), ('loss', ctypes.c_uint), ('slots', Slot * 16)]


class Binding(ctypes.Structure):
    _fields_ = [('reader', ctypes.c_uint64), ('flag', ctypes.c_uint64), ('ret', ctypes.c_uint64)]


class Association(ctypes.Structure):
    _fields_ = [('loss', ctypes.c_uint), ('input', ctypes.c_uint32), ('store', ctypes.c_uint32), ('branch', ctypes.c_uint32)]


def associate(raw, libpath):
    lib = ctypes.CDLL(str(libpath))
    lib.amnm_snapshot_read.argtypes = [ctypes.POINTER(Log), ctypes.POINTER(Snapshot)]
    lib.amnm_snapshot_read.restype = ctypes.c_int
    lib.amnm_associate.argtypes = [ctypes.POINTER(Snapshot), ctypes.POINTER(Binding)]
    lib.amnm_associate.restype = Association
    lib.amnm_summary.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.POINTER(Snapshot), ctypes.POINTER(Association)]
    lib.amnm_summary.restype = ctypes.c_size_t
    log = Log.from_buffer_copy(raw)
    snap = Snapshot()
    status = lib.amnm_snapshot_read(ctypes.byref(log), ctypes.byref(snap))
    binding = Binding(I.BOOL_READER, I.BOOL_OUT, I.BOOL_RETURN)
    result = lib.amnm_associate(ctypes.byref(snap), ctypes.byref(binding))
    buf = ctypes.create_string_buffer(256)
    n = lib.amnm_summary(buf, len(buf), ctypes.byref(snap), ctypes.byref(result))
    return {'snapshot_status': status, 'count': snap.count, 'n1': snap.n1, 'n2': snap.n2,
            'snapshot_loss': snap.loss, 'association_loss': result.loss,
            'input': result.input, 'store': result.store, 'branch': result.branch,
            'summary': buf.value.decode(), 'summary_length': n,
            'boundary': 'unmodified C host implementation on frozen emulator log; not ARM panic execution'}


def run(raw, macho, adt, libpath):
    model = A.Model(raw, macho, A.parse_adt(adt))
    u = model.u
    u.mem_map(0xe00000, B.align(len(adt)))
    u.mem_write(0xe00000, adt)
    model.call(macho['symbols']['_SecureDTInit'], (0xe00000, len(adt)))
    logva = macho['symbols']['_amnm_observer_log']
    hooks = {macho['symbols']['_amnm_' + name + '_hook']: name for name in ('entry', 'precall', 'input', 'store', 'branch')}
    trace, events, atomics, readers, helpers, writes = [], [], [], [], [], []
    pending_readers, pending_helpers = [], []
    stop = {}
    def reg(name): return u.reg_read(getattr(A, 'UC_ARM64_REG_' + name))
    def code(uc, pc, size, data):
        trace.append(hex(pc))
        if pc in (I.DECISION_BOUNDARY, I.PANIC):
            stop.update(reason='boundary' if pc == I.DECISION_BOUNDARY else 'panic', pc=hex(pc))
            if pc == I.PANIC:
                stop.update(panic=model.cstr(reg('X0')), variadic=[model.get64(reg('SP')), model.get64(reg('SP') + 8)])
            uc.emu_stop(); return
        if pc in hooks:
            events.append({'hook': hooks[pc], 'pc': hex(pc)})
        opcode = bytes(uc.mem_read(pc, 4))
        if opcode == bytes.fromhex('2b01eaf8'):
            addr, source = reg('X9'), reg('X10')
            old = int.from_bytes(uc.mem_read(addr, 8), 'little')
            uc.mem_write(addr, ((old + source) & 0xffffffffffffffff).to_bytes(8, 'little'))
            uc.reg_write(A.UC_ARM64_REG_X11, old)
            uc.reg_write(A.UC_ARM64_REG_PC, pc + 4)
            atomics.append({'pc': hex(pc), 'opcode': opcode.hex(), 'address': hex(addr), 'source': source, 'old': old})
        if pc == I.BOOL_READER:
            rec = {'caller': hex(reg('LR')), 'id': reg('X2'), 'output': hex(reg('X3'))}
            readers.append(rec); pending_readers.append((reg('LR'), rec))
        if pending_readers and pc == pending_readers[-1][0]:
            pending_readers.pop()[1]['return'] = reg('W0') & 0xffffffff
        if pc == I.HELPER:
            rec = {'caller': hex(reg('LR')), 'key': model.cstr(reg('X1'))}
            helpers.append(rec); pending_helpers.append((reg('LR'), rec))
        if pending_helpers and pc == pending_helpers[-1][0]:
            pending_helpers.pop()[1]['errno'] = reg('W0') & 0xffffffff
        if pc == I.FINAL_READ:
            events.append({'event': 'flag_read', 'pc': hex(pc), 'byte': bytes(uc.mem_read(I.BOOL_OUT, 1))[0]})
        if pc == I.FINAL_BRANCH:
            events.append({'event': 'branch_operand', 'pc': hex(pc), 'w8': reg('W8') & 0xffffffff})
    def write(uc, access, address, size, value, data):
        if address <= I.BOOL_OUT < address + size:
            writes.append({'pc': hex(reg('PC')), 'address': hex(address), 'size': size, 'value': value})
    u.hook_add(U.UC_HOOK_CODE, code)
    u.hook_add(U.UC_HOOK_MEM_WRITE, write, begin=I.BOOL_OUT, end=I.BOOL_OUT)
    for i in range(19, 30): u.reg_write(getattr(A, 'UC_ARM64_REG_X%d' % i), 0x11220000 + i * 0x100)
    u.reg_write(A.UC_ARM64_REG_X0, A.PMAP_RUNTIME)
    u.reg_write(A.UC_ARM64_REG_LR, A.STOP)
    u.reg_write(A.UC_ARM64_REG_SP, A.STACK + 0x8000)
    try:
        u.emu_start(I.ENTRY, A.STOP, count=I.RUN_COUNT)
    except U.UcError as exc:
        stop.update(reason='unmodelled_exception', pc=hex(reg('PC')), error=str(exc))
    if not stop: stop.update(reason='unexpected_stop', pc=hex(reg('PC')))
    log = bytes(u.mem_read(logva, 1920))
    slots = []
    fields = {1: ('entry_sp','entry_fp','entry_lr'), 2: ('callee','runtime','id','output','caller_sp','caller_fp','return_pc'),
              3: ('input_u32','id','output','reader_sp','reader_fp','caller_fp','caller_lr'),
              4: ('byte_value','target','id','reader_sp','reader_fp','caller_fp','caller_lr'),
              5: ('input_u32','initializer_sp','initializer_fp')}
    for i in range(16):
        b = log[128+i*96:128+(i+1)*96]
        words = struct.unpack('<12Q', b)
        slots.append({'index': i, 'raw_hex': b.hex(), 'commit': words[0], 'kind': words[1],
                      'payload_words': list(words[2:]), 'decoded': dict(zip(fields.get(words[1], ()), words[2:]))})
    return {'stop': stop, 'model_bad': model.bad, 'log_address': hex(logva),
            'next_sequence': int.from_bytes(log[:8], 'little'), 'log_raw_hex': log.hex(), 'slots': slots,
            'events': events, 'reader_calls': readers, 'helper_calls': helpers, 'flag_writes': writes,
            'atomics_single_thread': atomics, 'executed_pcs': trace, 'fixture_events': model.events,
            'association': associate(log, libpath)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', type=Path, default=OUT,
                        help='fresh ignored output directory')
    out = parser.parse_args().output_dir.resolve()
    if not out.is_relative_to((ROOT / 'out').resolve()):
        raise ValueError('output directory must be under ignored out/')
    raw, adt = KERNEL.read_bytes(), ADT.read_bytes()
    if sha(raw) != PIN_K or sha(adt) != PIN_A: raise ValueError('input hash mismatch')
    out.mkdir(exist_ok=False)
    libpath = out / 'amnm-record-host.so'
    cmd = ['/usr/bin/cc', '-shared', '-fPIC', '-O2', str(ROOT / 'package/diagnostics/amnm-record.c'), '-o', str(libpath)]
    subprocess.run(cmd, check=True)
    report = {'cwd': os.getcwd(), 'argv': sys.argv, 'kernel': str(KERNEL), 'kernel_sha256': sha(raw),
              'adt': str(ADT), 'adt_sha256': sha(adt), 'compile_command': cmd,
              'source_sha256': {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in
                [Path(__file__).resolve(), ROOT / 'scripts/research-current-image4-initializer-amnm.py',
                 ROOT / 'scripts/audit-image4-runtime-provider.py', ROOT / 'scripts/build-kernel-entry-probe.py',
                 ROOT / 'scripts/nuwa_launch_context.py', ROOT / 'package/diagnostics/amnm-record.c', ROOT / 'package/diagnostics/amnm-record.h']},
              'case': run(raw, B.macho(raw), adt, libpath)}
    with (out / 'evidence.json').open('x') as f: json.dump(report, f, indent=2); f.write('\n')
    print(json.dumps({'stop': report['case']['stop'], 'sequence': report['case']['next_sequence'],
                      'association': report['case']['association'], 'readers': report['case']['reader_calls']}))
    return 0 if report['case']['stop']['reason'] in ('boundary', 'panic') else 1


if __name__ == '__main__': sys.exit(main())
