#!/usr/bin/env python3
"""nuwa boot payload flash into the active _a slot (r35 pack).

Route is the one the device actually ran in r11-r34
(`out/nuwa-boot-payload-write-20261115-01/WRITE-r34.json`):
`fastboot -s <serial> flash vendor_boot_a <whole image>`, target identified by
one `getvar product` per enumerated device, no device-side readback (the
bootloader answers `Device does not support fetch command`), no slot change,
one normal reboot at most.

`kernel.macho` is not a flash target: it is packaged inside `vendor_boot.img`
(WRITE-r34.json records it as candidate metadata, not as a written partition),
so this script only hash-checks it and carries its digest into the record.

Host-only by default. `--execute` additionally needs a fixed serial and this
round's authorization text (`--authorization` or NUWA_WRITE_AUTHORIZATION).
Identification policy and the current-slot parser are copied from
`scripts/run-pmap-ret-once.py` (same repository, same constants).
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'out/nuwa-boot-payload-write-20261115-01'
R34 = ROOT / 'out/nuwa-ufs-apfs-root-chmh-20261119-r34'
R35 = ROOT / 'out/nuwa-ufs-apfs-root-chmh-20261119-r35'

VENDOR_BOOT_BYTES = 100663296
BOOT_A_BYTES = 201326592
PRODUCT_RE = re.compile(r'^(?:\(bootloader\)\s*)?product:\s*(\S+)\s*$', re.M)
PARTITION_SIZE_RE = re.compile(r'partition-size(?::\S+)?:\s*(0x[0-9a-fA-F]+)')
TIMING_RE = re.compile(r'Finished\.(?: Total time: [0-9]+(?:\.[0-9]+)?s)?', re.I)

PRESETS = {
    'r35': {
        'profile': 'nuwa-ufs-apfs-root-chmh-20261119-r35',
        'partition': 'vendor_boot_a',
        'image': R35 / 'vendor_boot.img',
        'image_bytes': VENDOR_BOOT_BYTES,
        'image_sha256': 'c6e64820cc46c1a54e65d3640994ad7acf0e7aa807dfd3765eac82f483a4a7ed',
        'kernel': R35 / 'kernel.macho',
        'kernel_bytes': 55721984,
        'kernel_sha256': '787610183dc7f772e2d01aa183f72f2fcc52245fc44407e6c815ced614412464',
        'record': R35 / 'record.json',
        'vendor_boot_json': R35 / 'vendor_boot.json',
    },
    'r34': {
        'profile': 'nuwa-ufs-apfs-root-chmh-20261119-r34',
        'partition': 'vendor_boot_a',
        'image': R34 / 'vendor_boot.img',
        'image_bytes': VENDOR_BOOT_BYTES,
        'image_sha256': '46aa4fd9f575a30824543fed7c128c5013d35af8d62a98715d0312d1752c891e',
        'kernel': R34 / 'kernel.macho',
        'kernel_bytes': 55717888,
        'kernel_sha256': 'ce24818ea19e1301dc0f4173a448ff3088aabf9bcc413f645f93c1c569a7f6dd',
        'record': R34 / 'record.json',
        'vendor_boot_json': R34 / 'vendor_boot.json',
    },
    'stock': {
        'profile': 'stock vendor_boot_a (2026-11-15 device dd + adb pull backup)',
        'partition': 'vendor_boot_a',
        'image': OUT / 'vendor_boot_a.stock.img',
        'image_bytes': VENDOR_BOOT_BYTES,
        'image_sha256': '493ca426964adabb195a00ded4ff49793bc7efd5d7bea2a567bcfd0c970a8dad',
        'kernel': None,
        'kernel_bytes': None,
        'kernel_sha256': None,
        'record': None,
        'vendor_boot_json': None,
    },
}

STOCK_BOOT_A = {
    'partition': 'boot_a',
    'image': OUT / 'boot_a.stock.img',
    'image_bytes': BOOT_A_BYTES,
    'image_sha256': 'd530872b80f9cc44a260411a1a7d1c6357a9d3e562577e803e7a82945226c0d9',
}

READBACK_LIMIT = ('无回读验证 — only bootloader write acknowledgement '
                  '(Sending OKAY + Writing OKAY)')
READBACK_REASON = ("bootloader has no 'fastboot fetch'; no adb in fastboot mode; "
                   "post-flash getvar deliberately skipped")
TWRP_READBACK = [
    "adb -s <SERIAL> shell 'sha256sum /dev/block/by-name/vendor_boot_a'",
    "adb -s <SERIAL> shell 'sha256sum /dev/block/by-name/boot_a'",
]
TWRP_READBACK_NOTE = ('alternative only (TWRP recovery path verified 2026-11-15): '
                      'boot recovery_a, no fastboot; not part of the fastboot flow')


class Refused(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise Refused(message)


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def redact(text, serial):
    if serial:
        text = text.replace(serial, '<nuwa serial>')
    return text


def display_path(path):
    path = Path(path).resolve()
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def check_preset(preset):
    """Local identity gate. Runs no device command; also used by --dry-run."""
    image = Path(preset['image'])
    require(image.is_file(), 'missing image ' + str(image))
    size = image.stat().st_size
    require(size == preset['image_bytes'],
            'image size %d != pinned %d for %s' % (size, preset['image_bytes'], image.name))
    digest = sha256_file(image)
    require(digest == preset['image_sha256'],
            'image sha256 %s != pinned %s for %s' % (digest, preset['image_sha256'], image.name))
    candidate = {
        'file': display_path(image),
        'bytes': size,
        'sha256_measured': digest,
        'sha256_expected': preset['image_sha256'],
        'local_checks_passed': True,
        'profile': preset['profile'],
        'authentication': None,
    }
    kernel = preset['kernel']
    if kernel is not None:
        require(kernel.is_file(), 'missing kernel ' + str(kernel))
        kernel_bytes = kernel.stat().st_size
        require(kernel_bytes == preset['kernel_bytes'],
                'kernel size %d != pinned %d' % (kernel_bytes, preset['kernel_bytes']))
        kernel_sha = sha256_file(kernel)
        require(kernel_sha == preset['kernel_sha256'],
                'kernel sha256 %s != pinned %s' % (kernel_sha, preset['kernel_sha256']))
        candidate['kernel'] = display_path(kernel)
        candidate['kernel_bytes'] = kernel_bytes
        candidate['kernel_sha256'] = kernel_sha
        candidate['kernel_note'] = ('packaging input only; the kernel travels inside '
                                    'vendor_boot.img and is not a separate flash target')
    vendor_boot_json = preset['vendor_boot_json']
    if vendor_boot_json is not None:
        require(vendor_boot_json.is_file(), 'missing ' + str(vendor_boot_json))
        outer = json.loads(vendor_boot_json.read_text(encoding='utf-8'))
        candidate['vendor_boot_json_image_sha256'] = outer.get('image_sha256')
        candidate['vendor_boot_json_image_bytes'] = outer.get('image_bytes')
        require(outer.get('image_sha256') == preset['image_sha256'],
                'vendor_boot.json image_sha256 does not match the pinned image')
        require(outer.get('image_bytes') == preset['image_bytes'],
                'vendor_boot.json image_bytes does not match the pinned image')
    record = preset['record']
    if record is not None:
        require(record.is_file(), 'missing ' + str(record))
        data = json.loads(record.read_text(encoding='utf-8'))
        inputs = data.get('inputs_sha256') or {}
        candidate['profile_record'] = data.get('profile')
        require(data.get('profile') == preset['profile'],
                'record.json profile does not match the preset')
        if kernel is not None:
            require(inputs.get('kernel') == preset['kernel_sha256'],
                    'record.json kernel input does not match kernel.macho')
        candidate['chmh'] = data.get('chmh_hex')
        candidate['derived_adt'] = data.get('derived_adt_sha256')
        candidate['payload'] = data.get('payload_sha256')
        candidate['authentication'] = data.get('authentication')
        candidate['args'] = data.get('kernel_args')
        candidate['trust_material'] = inputs.get('trust')
        require(candidate['chmh'] and candidate['derived_adt'] and candidate['payload'],
                'record.json identity fields incomplete')
    return candidate


def call(fastboot, args, run=subprocess.run, timeout=20):
    argv = [fastboot, *args]
    redacted = list(args)
    if redacted[:1] == ['-s']:
        redacted[1] = '<REDACTED>'
    shown = [argv[0], *redacted]
    try:
        result = run(argv, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise Refused('timeout after %ss: %s (remote completion UNKNOWN)'
                      % (timeout, ' '.join(shown))) from None
    except OSError as error:
        raise Refused('%s: %s' % (type(error).__name__, ' '.join(shown))) from None
    return {'argv': shown, 'returncode': result.returncode,
            'stdout': result.stdout or '', 'stderr': result.stderr or ''}


def devices(fastboot, run=subprocess.run):
    result = call(fastboot, ['devices'], run=run, timeout=60)
    entries = []
    for line in result['stdout'].splitlines():
        if not line.strip() or line.startswith('List of devices attached'):
            continue
        parts = line.split()
        require(len(parts) >= 2 and parts[1] == 'fastboot',
                'unrecognized fastboot enumeration line')
        entries.append(parts[0])
    return result, entries


def identify(fastboot, serial, run=subprocess.run):
    """One getvar product per device; exactly one nuwa hit, and it must be serial."""
    enumeration, entries = devices(fastboot, run=run)
    ser = serial or ''
    identification = {
        'fastboot_devices_count': len(entries),
        'devices_queried': len(entries),
        'nuwa_hits': 0,
        'query_policy': ('one getvar product per device, no retry; '
                         'stop only on 0 or >=2 nuwa hits'),
        'stop_condition_triggered': False,
        'serial_recorded_in_files': False,
        'events': [enumeration['argv']],
    }
    targets = []
    for candidate_serial in entries:
        result = call(fastboot, ['-s', candidate_serial, 'getvar', 'product'], run=run)
        values = PRODUCT_RE.findall(result['stdout'] + '\n' + result['stderr'])
        require(len(values) == 1, 'product missing/ambiguous; stopped')
        if values == ['nuwa']:
            targets.append(candidate_serial)
        identification['events'].append(result['argv'] + [values[0]])
    identification['nuwa_hits'] = len(targets)
    if len(targets) != 1:
        identification['stop_condition_triggered'] = True
        raise Refused('zero or multiple nuwa targets; stopped')
    require(ser and targets[0] == ser,
            'fixed --serial is not the single nuwa target; stopped')
    return identification


def current_slot(fastboot, serial, run=subprocess.run):
    """Same parser as run-pmap-ret-once.py; an unsupported reply is not a slot."""
    result = call(fastboot, ['-s', serial, 'getvar', 'current-slot'], run=run)
    response = result['stdout'] + '\n' + result['stderr']
    body = [line.strip() for line in response.splitlines()
            if line.strip() and not TIMING_RE.fullmatch(line.strip())]
    if body == ["FAILED (remote: 'unknown command')"] and result['returncode'] == 1:
        return None
    require(result['returncode'] == 0 and len(body) == 1,
            'current-slot failed/mixed; no write')
    match = re.fullmatch(r'(?:\(bootloader\)\s*)?current-slot:\s*([ab])', body[0])
    require(match is not None, 'current-slot malformed/ambiguous; no write')
    return match.group(1)


def partition_size(fastboot, serial, partition, run=subprocess.run):
    result = call(fastboot, ['-s', serial, 'getvar', 'partition-size:' + partition], run=run)
    values = PARTITION_SIZE_RE.findall(result['stdout'] + result['stderr'])
    if not values:
        return None
    return int(values[0], 16)


def flash(fastboot, serial, partition, image, run=subprocess.run, timeout=180):
    result = call(fastboot, ['-s', serial, 'flash', partition, str(image)],
                  run=run, timeout=timeout)
    text = result['stdout'] + '\n' + result['stderr']
    sent = re.search(r"Sending '%s' \(\d+ KB\)\s+OKAY" % re.escape(partition), text)
    wrote = re.search(r"Writing '%s'\s+OKAY" % re.escape(partition), text)
    ok = result['returncode'] == 0 and sent is not None and wrote is not None
    record = {
        'partition': partition,
        'command': ' '.join(['fastboot', '-s', '<nuwa serial>', 'flash', partition,
                             display_path(image)]),
        'output_lines': [redact(line, serial) for line in text.splitlines() if line.strip()],
        'exit_code': result['returncode'],
        'writing_stage_reached': sent is not None and wrote is not None,
        'accepted': ok,
    }
    return record


def gate(fastboot, serial, partition, run=subprocess.run):
    identification = identify(fastboot, serial, run=run)
    slot = current_slot(fastboot, serial, run=run)
    require(slot == 'a', 'current slot is %s, not a; no write' % (slot or 'unreadable'))
    size = partition_size(fastboot, serial, partition, run=run)
    if size is not None:
        expected = VENDOR_BOOT_BYTES if partition == 'vendor_boot_a' else BOOT_A_BYTES
        require(size == expected,
                'partition-size:%s answered %#x, not the pinned capacity; no write'
                % (partition, size))
    return identification, {
        'current_slot_before': slot,
        'slot_active_changed': False,
        'partition_size_getvar': None if size is None else hex(size),
        'partition_size_note': ('None means the intermittent getvar failure seen in r28-r33; '
                                'it is recorded, not treated as a real zero size'),
    }


def plan(args):
    presets = [PRESETS[args.target]]
    if args.include_stock_boot_a:
        presets.append(STOCK_BOOT_A)
    if getattr(args, 'image', None):
        presets[0] = dict(presets[0], image=Path(args.image).resolve())
    lines_out = ['dry-run: no device command was executed', '']
    for preset in presets:
        candidate = check_preset(preset) if 'profile' in preset else check_plain(preset)
        lines_out.append('local identity PASS %s %d B %s' % (
            candidate['file'], candidate['bytes'], candidate['sha256_measured']))
        if candidate.get('kernel_sha256'):
            lines_out.append('  kernel PASS %s %d B %s' % (
                candidate['kernel'], candidate['kernel_bytes'], candidate['kernel_sha256']))
        lines_out.append('  flash  fastboot -s <serial> flash %s %s'
                         % (preset['partition'], candidate['file']))
    lines_out += [
        '',
        'device gate (read-only, --execute runs it first):',
        '  fastboot devices',
        '  fastboot -s <serial> getvar product            # every device, once',
        '  fastboot -s <serial> getvar current-slot       # must answer a',
        '  fastboot -s <serial> getvar partition-size:vendor_boot_a',
        '',
        'write: fastboot -s <serial> flash vendor_boot_a <image>',
        'after: ' + READBACK_LIMIT,
        'no slot change; no fastboot boot; reboot only with --reboot',
        'kernel.macho is inside vendor_boot.img and is not flashed separately',
    ]
    return '\n'.join(lines_out)


def check_plain(preset):
    image = Path(preset['image'])
    require(image.is_file(), 'missing image ' + str(image))
    size = image.stat().st_size
    require(size == preset['image_bytes'],
            'image size %d != pinned %d for %s' % (size, preset['image_bytes'], image.name))
    digest = sha256_file(image)
    require(digest == preset['image_sha256'],
            'image sha256 %s != pinned %s for %s' % (digest, preset['image_sha256'], image.name))
    return {'file': display_path(image), 'bytes': size,
            'sha256_measured': digest, 'sha256_expected': preset['image_sha256'],
            'local_checks_passed': True, 'profile': None,
            'authentication': None}


def write_record(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Flash the nuwa boot payload into the active _a slot over fastboot '
                    '(dry-run by default; no device command without --execute).')
    parser.add_argument('--target', choices=sorted(PRESETS), default='r35',
                        help='payload preset (default r35)')
    parser.add_argument('--include-stock-boot-a', action='store_true',
                        help='also flash the stock boot_a image (rollback to factory)')
    parser.add_argument('--serial', help='fixed device serial for this round')
    parser.add_argument('--fastboot', default='fastboot')
    parser.add_argument('--authorization', default=os.environ.get('NUWA_WRITE_AUTHORIZATION'),
                        help="this round's authorization text (or NUWA_WRITE_AUTHORIZATION)")
    parser.add_argument('--check-only', action='store_true',
                        help='run the read-only identification/slot gate and stop')
    parser.add_argument('--execute', action='store_true',
                        help='actually flash (needs --serial and authorization text)')
    parser.add_argument('--reboot', action='store_true',
                        help='one normal reboot after a successful write')
    parser.add_argument('--allow-reboot-bootloader-fallback', action='store_true',
                        help='r33-measured remedy: one `reboot bootloader` on remote '
                             'download-size rejection, then a single retry')
    parser.add_argument('--record', type=Path,
                        help='write record path (default out/.../WRITE-<target>.json)')
    parser.add_argument('--image', type=Path,
                        help='dry-run only: check this file against the pinned size/hash '
                             'instead of the preset path (refused with --execute)')
    parser.add_argument('--claim', type=Path,
                        help='write claim path (default out/.../nuwa-boot-payload-<target>.claim)')
    args = parser.parse_args(argv)

    if not args.execute:
        if args.check_only:
            print('REFUSED: --check-only also runs read-only device commands; '
                  'add --execute (no write happens)')
            return 2
        try:
            output = plan(args)
        except Refused as error:
            print('REFUSED: ' + str(error))
            return 2
        print(output)
        return 0

    try:
        require(not (args.execute and args.image),
                '--image is a dry-run check only; --execute always uses the pinned preset path')
        require(args.serial, '--execute requires the fixed --serial')
        if args.check_only:
            gate(args.fastboot, args.serial, PRESETS[args.target]['partition'])
            print('gate PASS: unique nuwa, slot a; no write performed')
            return 0
        require(args.authorization and args.authorization.strip(),
                '--execute requires this round\'s authorization text '
                '(--authorization or NUWA_WRITE_AUTHORIZATION)')
        presets = [PRESETS[args.target]]
        if args.include_stock_boot_a:
            require(args.target == 'stock', '--include-stock-boot-a only applies to --target stock')
            presets.append(STOCK_BOOT_A)
        candidates = []
        for preset in presets:
            candidates.append(check_preset(preset) if 'profile' in preset else check_plain(preset))
        claim = args.claim or OUT / ('nuwa-boot-payload-%s.claim' % args.target)
        require(not Path(claim).exists(),
                'write claim already exists (%s); do not replay a consumed write' % claim)

        Path(claim).parent.mkdir(parents=True, exist_ok=True)
        Path(claim).write_text(json.dumps({
            'target': args.target,
            'images': [c['sha256_measured'] for c in candidates],
            'serial_recorded': False,
        }, indent=2) + '\n', encoding='utf-8')

        flashes = []
        identification = None
        slot = None
        for preset in presets:
            identification, slot = gate(args.fastboot, args.serial, preset['partition'])
            record = flash(args.fastboot, args.serial, preset['partition'], preset['image'])
            if not record['accepted'] and args.allow_reboot_bootloader_fallback:
                text = '\n'.join(record['output_lines'])
                if 'Requested download size is more than max allowed' in text:
                    call(args.fastboot, ['-s', args.serial, 'reboot', 'bootloader'],
                         timeout=60)
                    identification = None
                    for _ in range(3):
                        time.sleep(5)
                        try:
                            identification = identify(args.fastboot, args.serial)
                        except Refused:
                            continue
                        break
                    require(identification is not None,
                            'target did not re-enumerate after reboot bootloader; no retry')
                    record = flash(args.fastboot, args.serial, preset['partition'],
                                   preset['image'])
                    record['fallback'] = 'one reboot bootloader, then a single retry (r33 route)'
            require(record['accepted'], 'flash was not acknowledged (%s); no retry'
                    % preset['partition'])
            flashes.append(record)

        reboot = None
        if args.reboot:
            result = call(args.fastboot, ['-s', args.serial, 'reboot'], timeout=60)
            reboot = {'command': 'fastboot -s <nuwa serial> reboot',
                      'output_lines': [redact(line, args.serial)
                                       for line in (result['stdout'] + result['stderr']).splitlines()
                                       if line.strip()],
                      'variant': 'normal reboot (no recovery/bootloader target, no fastboot boot)'}

        record_path = args.record or OUT / ('WRITE-%s.json' % args.target)
        payload = {
            'status': 'executed',
            'date': time.strftime('%Y-%m-%d'),
            'operation': ('flash %s with the %s payload over fastboot (identify by product)'
                          % ('/'.join(p['partition'] for p in presets), args.target)),
            'transport': 'fastboot',
            'authorization': args.authorization.strip(),
            'identification': identification,
            'slot': slot,
            'candidate': candidates[0] if len(candidates) == 1 else candidates,
            'flash': flashes[0] if len(flashes) == 1 else flashes,
            'readback_verification': {
                'device_side_readback_possible': False,
                'reason': READBACK_REASON,
                'status': READBACK_LIMIT,
                'alternative_requires_twrp': TWRP_READBACK,
                'alternative_note': TWRP_READBACK_NOTE,
            },
            'reboot': reboot,
            'scope': {
                'partitions_written': [p['partition'] for p in presets],
                'boot_a_written': any(p['partition'] == 'boot_a' for p in presets),
                'other_partitions_written': False,
                'slot_active_changed': False,
                'userdata_written_by_host': False,
                'format_performed': False,
            },
        }
        write_record(record_path, payload)
        print('flash acknowledged: ' + ', '.join(p['partition'] for p in presets))
        print('record: ' + str(record_path))
        print(READBACK_LIMIT)
        return 0
    except Refused as error:
        print('REFUSED: ' + str(error))
        return 2


if __name__ == '__main__':
    sys.exit(main())
