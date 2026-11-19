#!/usr/bin/env python3
"""One-command rollback of the nuwa boot payload after an r35 write.

Two targets, both from images already pinned on disk:
  r34    vendor_boot_a = out/nuwa-ufs-apfs-root-chmh-20261119-r34/vendor_boot.img
  stock  vendor_boot_a + boot_a = the 2026-11-15 device-dd backups

Dry-run by default. Execution reuses `nuwa-boot-payload-flash.py` (same gate,
same fastboot command shape) and needs a fixed serial plus this round's
authorization text. Fastboot cannot read a partition, so the script cannot prove
what is on the device now - only what it writes.
"""
import argparse
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / 'out/nuwa-boot-payload-write-20261115-01'

spec = importlib.util.spec_from_file_location('nuwa_flash', HERE / 'nuwa-boot-payload-flash.py')
F = importlib.util.module_from_spec(spec)
spec.loader.exec_module(F)

ROLLBACK_NOTE = ('fastboot cannot read a partition (no fetch), so the payload currently on '
                 'the device is not verified; this writes the rollback image and records the '
                 'bootloader acknowledgement only')


def plan(args):
    presets = [F.PRESETS[args.to]]
    if args.to == 'stock':
        presets.append(F.STOCK_BOOT_A)
    lines_out = ['dry-run: no device command was executed', '']
    for preset in presets:
        candidate = (F.check_preset(preset) if 'profile' in preset
                     else F.check_plain(preset))
        lines_out.append('local identity PASS %s %d B %s' % (
            candidate['file'], candidate['bytes'], candidate['sha256_measured']))
    lines_out += ['', 'device gate (read-only, --execute runs it first):',
                  '  fastboot devices',
                  '  fastboot -s <serial> getvar product            # must be the single nuwa',
                  '  fastboot -s <serial> getvar current-slot       # must answer a']
    for preset in presets:
        lines_out.append('rollback: fastboot -s <serial> flash %s %s'
                         % (preset['partition'], F.display_path(preset['image'])))
    if args.to == 'stock':
        lines_out += ['',
                      'warning: boot_a.stock.img is a 192 MiB full-partition dump; fastboot '
                      'acceptance of that size is unverified (ROLLBACK.md path B).',
                      'TWRP dd path (ROLLBACK.md path A) is the verified stock restore route.']
    lines_out += ['', F.READBACK_LIMIT, ROLLBACK_NOTE]
    return '\n'.join(lines_out)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Roll the nuwa boot payload back (dry-run by default).')
    parser.add_argument('--to', choices=('r34', 'stock'), default='r34',
                        help='rollback target (default r34)')
    parser.add_argument('--serial', help='fixed device serial for this round')
    parser.add_argument('--fastboot', default='fastboot')
    parser.add_argument('--authorization', default=os.environ.get('NUWA_WRITE_AUTHORIZATION'),
                        help="this round's authorization text (or NUWA_WRITE_AUTHORIZATION)")
    parser.add_argument('--execute', action='store_true', help='actually flash')
    parser.add_argument('--record', type=Path,
                        help='record path (default out/.../ROLLBACK-r35-execution.json)')
    parser.add_argument('--claim', type=Path,
                        help='claim path (default out/.../nuwa-boot-payload-rollback.claim)')
    args = parser.parse_args(argv)

    if not args.execute:
        try:
            print(plan(args))
        except F.Refused as error:
            print('REFUSED: ' + str(error))
            return 2
        return 0

    try:
        F.require(args.serial, '--execute requires the fixed --serial')
        F.require(args.authorization and args.authorization.strip(),
                  '--execute requires this round\'s authorization text '
                  '(--authorization or NUWA_WRITE_AUTHORIZATION)')
        presets = [F.PRESETS[args.to]]
        if args.to == 'stock':
            presets.append(F.STOCK_BOOT_A)
        candidates = [(F.check_preset(preset) if 'profile' in preset
                       else F.check_plain(preset)) for preset in presets]
        claim = args.claim or OUT / 'nuwa-boot-payload-rollback.claim'
        F.require(not Path(claim).exists(),
                  'rollback claim already exists (%s); do not replay' % claim)
        Path(claim).parent.mkdir(parents=True, exist_ok=True)
        Path(claim).write_text(json.dumps({
            'to': args.to,
            'images': [c['sha256_measured'] for c in candidates],
            'serial_recorded': False,
        }, indent=2) + '\n', encoding='utf-8')

        flashes = []
        identification = None
        slot = None
        for preset in presets:
            identification, slot = F.gate(args.fastboot, args.serial, preset['partition'])
            record = F.flash(args.fastboot, args.serial, preset['partition'], preset['image'])
            F.require(record['accepted'], 'flash was not acknowledged (%s); no retry'
                      % preset['partition'])
            flashes.append(record)

        record_path = args.record or OUT / 'ROLLBACK-r35-execution.json'
        F.write_record(record_path, {
            'status': 'executed',
            'date': time.strftime('%Y-%m-%d'),
            'operation': 'roll the nuwa boot payload back to %s over fastboot' % args.to,
            'transport': 'fastboot',
            'authorization': args.authorization.strip(),
            'identification': identification,
            'slot': slot,
            'candidate': candidates[0] if len(candidates) == 1 else candidates,
            'flash': flashes[0] if len(flashes) == 1 else flashes,
            'readback_verification': {
                'device_side_readback_possible': False,
                'reason': F.READBACK_REASON,
                'status': F.READBACK_LIMIT,
                'alternative_requires_twrp': F.TWRP_READBACK,
                'alternative_note': F.TWRP_READBACK_NOTE,
            },
            'notes': [ROLLBACK_NOTE],
            'scope': {
                'partitions_written': [p['partition'] for p in presets],
                'boot_a_written': any(p['partition'] == 'boot_a' for p in presets),
                'other_partitions_written': False,
                'slot_active_changed': False,
                'userdata_written_by_host': False,
                'format_performed': False,
            },
        })
        print('rollback acknowledged: %s' % args.to)
        print('record: ' + str(record_path))
        print(F.READBACK_LIMIT)
        return 0
    except F.Refused as error:
        print('REFUSED: ' + str(error))
        return 2


if __name__ == '__main__':
    sys.exit(main())
