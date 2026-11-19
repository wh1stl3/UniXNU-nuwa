#!/usr/bin/env python3
"""Self-check for nuwa-boot-payload-flash.py: local gates and transport parsing.

No device command is executed. The fastboot calls are served by an in-memory
fake runner, and the wrong-hash/wrong-size cases use throwaway files under
out/nuwa-boot-payload-flash-selftest/.
"""
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TMP = ROOT / 'out/nuwa-boot-payload-flash-selftest'

spec = importlib.util.spec_from_file_location('nuwa_flash', HERE / 'nuwa-boot-payload-flash.py')
F = importlib.util.module_from_spec(spec)
spec.loader.exec_module(F)

passed, rejected = [], []


def refuses(name, fn):
    try:
        fn()
    except F.Refused:
        rejected.append(name)
    else:
        raise AssertionError('accepted invalid: ' + name)


class Device:
    """Fake fastboot. `products` maps serial -> product; others take a single reply."""

    def __init__(self, entries=('nuwa-serial',), products=None, slot='a',
                 size='0x6000000', flash_ok=True):
        self.entries = list(entries)
        self.products = products or {serial: 'nuwa' for serial in self.entries}
        self.slot = slot
        self.size = size
        self.flash_ok = flash_ok
        self.calls = []

    def __call__(self, argv, capture_output=True, text=True, timeout=None):
        self.calls.append(argv)
        if argv[1:] == ['devices']:
            body = 'List of devices attached\n' + ''.join(
                '%s\tfastboot\n' % serial for serial in self.entries)
            return subprocess.CompletedProcess(argv, 0, body, '')
        tail = ' '.join(argv[1:])
        if 'getvar product' in tail:
            product = self.products.get(argv[2], 'unknown')
            return subprocess.CompletedProcess(argv, 0, '', 'product: %s\n' % product)
        if 'getvar current-slot' in tail:
            if self.slot is None:
                return subprocess.CompletedProcess(argv, 1, '', "FAILED (remote: 'unknown command')\n")
            return subprocess.CompletedProcess(
                argv, 0, '', 'current-slot: %s\nFinished. Total time: 0.010s\n' % self.slot)
        if 'getvar partition-size:' in tail:
            return subprocess.CompletedProcess(argv, 0, '', 'partition-size:vendor_boot_a: %s\n' % self.size)
        if 'flash' in tail:
            if self.flash_ok:
                stderr = ("Sending 'vendor_boot_a' (98304 KB)                 OKAY [  2.266s]\n"
                          "Writing 'vendor_boot_a'                            OKAY [  0.036s]\n"
                          'Finished. Total time: 2.370s\n')
                return subprocess.CompletedProcess(argv, 0, '', stderr)
            return subprocess.CompletedProcess(
                argv, 1, '', "Sending 'vendor_boot_a' (98304 KB)  FAILED (remote: "
                             "'Requested download size is more than max allowed')\n")
        raise AssertionError('unexpected fastboot call: ' + tail)


# 1. local identity of the real r35 preset (present on this host)
if F.PRESETS['r35']['image'].is_file():
    candidate = F.check_preset(F.PRESETS['r35'])
    assert candidate['sha256_measured'] == F.PRESETS['r35']['image_sha256']
    assert candidate['kernel_sha256'] == F.PRESETS['r35']['kernel_sha256']
    assert candidate['authentication'] == 'NOT REACHED'
    assert candidate['chmh'] and candidate['derived_adt'] and candidate['payload']
    passed.append('r35-local-identity')

# 2. wrong size and wrong hash are refused
TMP.mkdir(parents=True, exist_ok=True)
tiny = TMP / 'tiny.img'
tiny.write_bytes(b'\0' * 4096)
refuses('wrong-size', lambda: F.check_plain({
    'image': tiny, 'image_bytes': F.VENDOR_BOOT_BYTES, 'image_sha256': '0' * 64}))
refuses('wrong-hash', lambda: F.check_plain({
    'image': tiny, 'image_bytes': 4096, 'image_sha256': '0' * 64}))
passed.append('wrong-size-hash-refused')

# 3. record.json cross-check: a tampered kernel digest is refused
if F.PRESETS['r35']['record'].is_file():
    data = json.loads(F.PRESETS['r35']['record'].read_text(encoding='utf-8'))
    data['inputs_sha256']['kernel'] = '0' * 64
    tampered = TMP / 'record-tampered.json'
    tampered.write_text(json.dumps(data), encoding='utf-8')
    preset = dict(F.PRESETS['r35'])
    preset['record'] = tampered
    refuses('record-kernel-mismatch', lambda: F.check_preset(preset))
    passed.append('record-cross-check')

# 4. vendor_boot.json mismatch is refused
if F.PRESETS['r35']['vendor_boot_json'].is_file():
    outer = json.loads(F.PRESETS['r35']['vendor_boot_json'].read_text(encoding='utf-8'))
    outer['image_sha256'] = '0' * 64
    tampered = TMP / 'vendor_boot-tampered.json'
    tampered.write_text(json.dumps(outer), encoding='utf-8')
    preset = dict(F.PRESETS['r35'])
    preset['vendor_boot_json'] = tampered
    refuses('outer-json-mismatch', lambda: F.check_preset(preset))
    passed.append('outer-cross-check')

# 5. identification: exactly one nuwa, and it must be the fixed serial
two_devices = Device(('emma', 'nuwa-serial'), {'emma': 'enuma', 'nuwa-serial': 'nuwa'})
identification = F.identify('fastboot', 'nuwa-serial', run=two_devices)
assert identification['nuwa_hits'] == 1 and identification['fastboot_devices_count'] == 2
passed.append('identify-one-nuwa')
refuses('identify-serial-mismatch', lambda: F.identify('fastboot', 'emma', run=two_devices))
refuses('identify-two-nuwa', lambda: F.identify(
    'fastboot', 'emma', run=Device(('e1', 'e2'), {'e1': 'nuwa', 'e2': 'nuwa'})))
refuses('identify-zero-nuwa', lambda: F.identify(
    'fastboot', 'e1', run=Device(('e1',), {'e1': 'enuma'})))

# 6. slot parser and gate
assert F.current_slot('fastboot', 's', run=Device()) == 'a'
assert F.current_slot('fastboot', 's', run=Device(slot='b')) == 'b'
unknown = Device(slot=None)
assert F.current_slot('fastboot', 's', run=unknown) is None
passed.append('slot-parser')
slot, ident = F.gate('fastboot', 'nuwa-serial', 'vendor_boot_a', run=Device())
assert ident['current_slot_before'] == 'a' and ident['partition_size_getvar'] == '0x6000000'
assert slot['nuwa_hits'] == 1
passed.append('gate-passes')
refuses('gate-slot-b', lambda: F.gate('fastboot', 'nuwa-serial', 'vendor_boot_a',
                                      run=Device(slot='b')))
refuses('gate-wrong-size', lambda: F.gate('fastboot', 'nuwa-serial', 'vendor_boot_a',
                                          run=Device(size='0x4000000')))

# 7. flash acknowledgement parsing
accepted = F.flash('fastboot', 's', 'vendor_boot_a', F.PRESETS['r35']['image'], run=Device())
assert accepted['accepted'] and accepted['writing_stage_reached']
rejected_flash = F.flash('fastboot', 's', 'vendor_boot_a', F.PRESETS['r35']['image'],
                         run=Device(flash_ok=False))
assert not rejected_flash['accepted'] and not rejected_flash['writing_stage_reached']
passed.append('flash-parsing')

# 8. the dry-run plan prints the commands without calling fastboot
plan_text = F.plan(type('Args', (), {'target': 'r35', 'include_stock_boot_a': False})())
assert 'no device command was executed' in plan_text
assert 'fastboot -s <serial> flash vendor_boot_a' in plan_text
passed.append('dry-run-plan')

shutil.rmtree(TMP, ignore_errors=True)
print(json.dumps({'passed': passed, 'rejected': rejected, 'status': 'self-checked'}, indent=2))
