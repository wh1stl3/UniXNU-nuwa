"""Targeted negatives against actual-byte CHMH vendor_boot gates."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location('chmh_outer', Path(__file__).with_name('build-chmh-only-vendor-boot.py'))
M = importlib.util.module_from_spec(spec); spec.loader.exec_module(M)
p = argparse.ArgumentParser()
p.add_argument('--built', required=True, type=Path)
p.add_argument('--output', required=True, type=Path)
a = p.parse_args()
out = M.P.reserve(a.output)
ctx = M.fixed(out)
image = (a.built / 'vendor_boot.img').read_bytes()
report = json.loads((a.built / 'outer-record.json').read_text())
actual = M.audit_image(image, ctx, out)
M.audit_report(report, actual)
relative = copy.deepcopy(report); relative['record_path'] = str((M.SELECTED / 'record.json').relative_to(M.ROOT))
M.audit_report(relative, actual)
rejected = []


def reject(name, fn):
    try:
        fn()
    except (ValueError, KeyError):
        rejected.append(name)
    else:
        raise AssertionError('Accepted invalid ' + name)


bad = copy.deepcopy(report); bad['profile'] = 'pmap-ret-continue-20261111-r1'
reject('profile', lambda: M.audit_report(bad, actual))
bad = copy.deepcopy(report); bad['record_sha256'] = '0' * 64
reject('record-hash', lambda: M.audit_report(bad, actual))
reject('record-bytes', lambda: M.check_record((M.SELECTED / 'record.json').read_bytes() + b' '))
for name, value in [('record-path-wrong', str(M.C.RECORD)),
                    ('record-path-missing', 'out/chmh-only-verifier-20261112/does-not-exist.json')]:
    altered = copy.deepcopy(report); altered['record_path'] = value
    reject(name, lambda altered=altered: M.audit_report(altered, actual))
for name, key, value in [('stock-mixed', 'stock_sha256', M.BACKUP_SHA),
                         ('backup-mixed', 'original_backup_sha256', M.V.STOCK_SHA),
                         ('backup-bool-integer', 'original_backup_is_template', 0),
                         ('backup-bool-true', 'original_backup_is_template', True)]:
    altered = copy.deepcopy(report); altered[key] = value
    reject(name, lambda altered=altered: M.audit_report(altered, actual))
reject('adt', lambda: M.C.check_adt(ctx['inputs']['parent-adt'], ctx['adt'][:-1] + bytes([ctx['adt'][-1] ^ 1]), M.C.EXPECTED_DIGEST))
reject('args', lambda: M.check_config(ctx['inputs']['config'].replace(b'-v serial=3', b'-v serial=4')))
parsed = M.V.parse(image)
offsets = {'header': 16, 'ramdisk': 4096, 'dtb': parsed['offsets']['dtb'],
           'table': parsed['offsets']['table'] + 8, 'bootconfig': parsed['offsets']['bootconfig'],
           'vbmeta': parsed['offsets']['vbmeta'], 'footer': len(image) - 1,
           'padding': parsed['offsets']['table'] + len(parsed['table'])}
for name, offset in offsets.items():
    changed = bytearray(image); changed[offset] ^= 1
    reject(name, lambda changed=changed: M.V.compare(ctx['stock'], bytes(changed), ctx['fat'], 100663296))
# Synchronizing the report hash does not bypass comparison against pinned stock/FAT.
changed = bytearray(image); changed[4096] ^= 1
sync = copy.deepcopy(report); sync['outer_sha256'] = M.O.sha(changed)
reject('synchronized-report-and-outer', lambda: M.audit_report(sync, M.audit_image(bytes(changed), ctx, out)))
reject('synchronized-report-against-original', lambda: M.audit_report(sync, actual))
M.O.write_json(out / 'tests.json', {'positive': True, 'rejected': rejected, 'status': 'self-checked'})
print('self-checked targeted negatives', len(rejected))
