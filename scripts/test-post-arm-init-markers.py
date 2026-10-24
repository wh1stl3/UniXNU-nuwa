"""Run the v6 candidate past _arm_init with the real ADT and check the new markers.

The ADT is loaded into a scratch physical page and boot_args.deviceTreeP/Length are
set, because without it SecureDTLookupEntry fails and the clock path never runs
(D-036). Execution then continues past the C-entry markers until the model stops.
"""
import argparse, hashlib, importlib.util, json, struct, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'out/python-tools'))
import unicorn as U
from unicorn.arm64_const import *
spec = importlib.util.spec_from_file_location('t', ROOT/'scripts/test-kernel-entry-probe.py')
T = importlib.util.module_from_spec(spec); spec.loader.exec_module(T)
B = T.B
ADT_PATH = ROOT/'out/trial-boot/xnu-entry-probe-02/kernel.macho.adt'
PA, FB, ROW, ARGS = T.PA, T.FB, T.ROW, T.ARGS
ADT_PA = ARGS + 0x200000
NULL_DEREF = '_current_percpu_base+0xc'


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--build', type=Path, required=True)
    cli.add_argument('--output', type=Path, required=True)
    cli.add_argument('--no-adt', action='store_true', help='keep the model-fidelity gap as a control')
    args = cli.parse_args()
    report = json.loads(args.build.read_text())
    candidate = (ROOT/report['candidate']['path']).read_bytes()
    checks = []
    def check(name, ok):
        checks.append(dict(name=name, passed=bool(ok)))
        if not ok: raise AssertionError(name)

    m = B.macho(candidate)
    base = min(s['va'] for s in m['segments'] if s['size'])
    end = max(s['va'] + s['size'] for s in m['segments'])
    uc = U.Uc(U.UC_ARCH_ARM64, U.UC_MODE_ARM)
    uc.mem_map(PA, B.align(end-base)+0x8000000); uc.mem_map(ARGS, 0x1000)
    uc.mem_map(FB, 0x1200000); uc.mem_map(ADT_PA, 0x10000)
    for s in m['segments']:
        if s['filesize']: uc.mem_write(PA+s['va']-base, bytes(candidate[s['fileoff']:s['fileoff']+s['filesize']]))
    args_buf = bytearray(4096); struct.pack_into('<HH', args_buf, 0, 2, 2)
    struct.pack_into('<4Q', args_buf, 8, base, PA, 0x40000000, ARGS+0x10000)
    struct.pack_into('<6Q', args_buf, 0x28, FB, 1, ROW, 1440, 3200, 32)
    if not args.no_adt:
        uc.mem_write(ADT_PA, ADT_PATH.read_bytes())
        struct.pack_into('<Q', args_buf, 0x58, ADT_PA)
        struct.pack_into('<I', args_buf, 0x60, ADT_PATH.stat().st_size)
    uc.mem_write(ARGS, bytes(args_buf))
    uc.reg_write(UC_ARM64_REG_X0, ARGS); uc.reg_write(UC_ARM64_REG_X20, ARGS); uc.reg_write(UC_ARM64_REG_PSTATE, 0x3c5)
    uc.cpr_write(3, 6, 1, 1, 0, T.SCR_EL3_AARCH64); uc.cpr_write(3, 4, 1, 1, 0, T.HCR_EL2_RW)

    symbols = report['probe']['symbols']
    watch = {int(symbols[name], 16): label for name, label in (
        ('probe_mmu_on_replay', 'cyan'), ('probe_arm_init_replay', 'white'),
        ('probe_cpu_base_replay', 'cpu_base'), ('probe_arm_vm_replay', 'arm_vm_init'),
        ('probe_pmap_replay', 'pmap_bootstrap'), ('probe_kernel_bootstrap_replay', 'kernel_bootstrap'))}
    hits = {}; count = [0]; bad = []
    def code(uc, addr, size, _):
        count[0] += 1
        if addr in watch and addr not in hits: hits[addr] = count[0]
    def invalid(uc, access, addr, size, value, _):
        bad.append(dict(access=access, address=hex(addr), pc=hex(uc.reg_read(UC_ARM64_REG_PC)))); return False
    uc.hook_add(U.UC_HOOK_CODE, code); uc.hook_add(U.UC_HOOK_MEM_INVALID, invalid)
    error = None
    try: uc.emu_start(PA+m['entry']-base, 0, count=3000000)
    except U.UcError as e: error = str(e)
    pc = uc.reg_read(UC_ARM64_REG_PC)
    best = max((v, k) for k, v in m['symbols'].items() if v <= pc)
    pixels = {str(y): hex(struct.unpack('<I', uc.mem_read(FB+y*ROW, 4))[0]) for y in (256, 352, 448, 736, 832, 896, 960, 1024, 1088)}
    reached = {watch[k]: hits[k] for k in hits}

    if args.no_adt:
        check('Without the ADT the run still reaches the arm_init hook', 'white' in reached)
    else:
        check('Cyan and white still correct', (pixels['736'], pixels['832']) == ('0xff00ffff', '0xffffffff'))
        check('_current_percpu_base marker paints its band', pixels['896'] == '0xff8000ff')
        check('_current_percpu_base marker is the first new marker reached',
              reached.get('cpu_base') == min(v for k, v in reached.items() if k not in ('cyan', 'white')))
        check('Execution still stops at the same per-CPU null dereference',
              f'{best[1]}+{pc-best[0]:#x}' == NULL_DEREF)
        check('No invalid memory access other than the reported stop', all(b['pc'] == hex(pc) for b in bad))
    result = {'scope': ('v6 C-entry markers executed in the model with the real ADT; '
                        'not hardware behaviour'),
              'build': str(args.build), 'candidate_sha256': report['candidate']['sha256'],
              'adt_used': not args.no_adt, 'adt_sha256': (hashlib.sha256(ADT_PATH.read_bytes()).hexdigest()
                                                          if not args.no_adt else None),
              'instructions': count[0], 'error': error, 'stopped_at': hex(pc),
              'stopped_symbol': f'{best[1]}+{pc-best[0]:#x}', 'reached': reached, 'pixels': pixels,
              'bad_memory': bad, 'checks': checks}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'checks': len(checks), 'passed': True, 'reached': reached, 'pixels': pixels,
                      'stopped_symbol': result['stopped_symbol']}))


if __name__ == '__main__':
    main()
