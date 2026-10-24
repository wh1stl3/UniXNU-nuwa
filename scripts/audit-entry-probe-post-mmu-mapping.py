"""Walk the software-built bootstrap tables for post-MMU addresses of interest.

Extends pre-mmu-pagewalk.json's method to the framebuffer phys range, the probe
page VA and the arm_init KVA. Software model only; not hardware MMU behaviour.
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
from unicorn.arm64_const import *


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--build', type=Path, required=True)
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    spec = importlib.util.spec_from_file_location('test', ROOT / 'scripts/test-kernel-entry-probe.py')
    test = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = test
    spec.loader.exec_module(test)
    captured = []
    original = U.Uc.emu_stop

    def capture(uc):
        try:
            tcr = uc.cpr_read(3, 0, 2, 0, 2)
            ttbr0 = uc.reg_read(UC_ARM64_REG_TTBR0_EL1)
            ttbr1 = uc.reg_read(UC_ARM64_REG_TTBR1_EL1)
            snapshot = {'tcr': hex(tcr), 'ttbr0': hex(ttbr0), 'ttbr1': hex(ttbr1), 'walks': []}

            def walk(va, label):
                table = (ttbr1 if va >> 63 else ttbr0) & 0x0000fffffffff000
                rows = []
                for level, shift in ((1, 30), (2, 21), (3, 12)):
                    # T0SZ/T1SZ shorten the level-1 index exactly as the XNU walk did.
                    indexbits = (64 - ((tcr >> 16) & 63) - 30) if level == 1 and va >> 63 else 9
                    if level == 1 and not va >> 63:
                        indexbits = 64 - (tcr & 63) - 30
                    at = table + ((va >> shift) & ((1 << indexbits) - 1)) * 8
                    desc = struct.unpack('<Q', uc.mem_read(at, 8))[0]
                    rows.append({'level': level, 'table_offset': hex(at), 'descriptor': hex(desc)})
                    if not desc & 1:
                        return {'label': label, 'va': hex(va), 'mapped': False, 'rows': rows}
                    if level == 3 or not desc & 2:
                        pa = (desc & 0x0000fffffffff000 & ~((1 << shift) - 1)) | (va & ((1 << shift) - 1))
                        return {'label': label, 'va': hex(va), 'mapped': True, 'pa': hex(pa),
                                'block': (desc >> 1) & 3 == 1 or level == 2, 'rows': rows}
                    table = desc & 0x0000fffffffff000
                return {'label': label, 'va': hex(va), 'mapped': False, 'rows': rows}

            build = json.loads((ROOT / args.build).read_text())
            m = test.B.macho((ROOT / build['candidate']['path']).read_bytes())
            base = min(s['va'] for s in m['segments'] if s['size'])
            probe_va = int(build['probe']['va'], 16)
            arm_init = m['symbols']['_arm_init']
            for label, va in (('framebuffer PA 0xb8000000', 0xb8000000),
                              ('framebuffer PA +1 page', 0xb8001000),
                              ('probe page VA', probe_va),
                              ('arm_init KVA', arm_init),
                              ('sctlr site as PA-identity VA', test.PA + m['symbols']['_start_first_cpu'] + 0x318 - base),
                              ('boot_args synthetic VA', test.ARGS + base - test.PA)):
                snapshot['walks'].append(walk(va, label))
            snapshot['l1_sample'] = [hex(struct.unpack('<Q', uc.mem_read(ttbr0 + i * 8, 8))[0]) for i in range(4)]
            captured.append(snapshot)
        except Exception as error:  # noqa: BLE001 - report the failure, do not hide it
            captured.append({'error': f'{type(error).__name__}: {error}'})
        return original(uc)

    U.Uc.emu_stop = capture
    build = json.loads((ROOT / args.build).read_text())
    raw = (ROOT / build['candidate']['path']).read_bytes()
    test.run(raw, build)
    report = {'scope': 'Software-generated bootstrap table walk; not hardware MMU or device mapping',
              'build': str(args.build), 'candidate_sha256': build['candidate']['sha256'],
              'snapshots': captured}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    for walk in captured[0].get('walks', []):
        print(walk['label'], walk['va'], '->', walk.get('pa'), 'mapped=', walk['mapped'])


if __name__ == '__main__':
    main()
