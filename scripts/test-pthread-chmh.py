#!/usr/bin/env python3
"""Targeted negatives for the actual pthread CHMH FAT and outer candidate."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import sys

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('pthread_chmh', Path(__file__).with_name('build-pthread-chmh.py'))
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--candidate', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    out = M.P.reserve(a.output)
    selected = M.P.reject_links(a.candidate).resolve(strict=True)
    parent, inputs, material, ev = M.fixed(out)
    stock, _ = M.stock_inputs()
    image = (selected / 'vendor_boot.img').read_bytes()
    report = json.loads((selected / 'outer-record.json').read_text())
    actual = M.audit_image(image, selected, inputs, material, ev, stock, out / 'positive')
    M.audit_report(report, actual, selected)
    relative = dict(report, record_path=str((selected / 'record.json').relative_to(M.ROOT)))
    M.audit_report(relative, actual, selected)
    rejected = []

    def reject(name, fn):
        try:
            fn()
        except (ValueError, KeyError):
            rejected.append(name)
            return
        raise AssertionError('invalid input accepted: ' + name)

    for name, key, value in [('wrong-profile', 'profile', 'chmh-only-20261112-r1'),
                             ('record-hash', 'record_sha256', '0' * 64),
                             ('record-path-parent', 'record_path', str(M.C.RECORD)),
                             ('record-path-missing', 'record_path', 'out/missing-record.json'),
                             ('stock-as-backup', 'stock_sha256', M.BACKUP_SHA),
                             ('backup-as-stock', 'original_backup_sha256', M.V.STOCK_SHA),
                             ('backup-boolean', 'original_backup_is_template', 0),
                             ('loader', 'loader_sha256', '0' * 64)]:
        changed = dict(report, **{key: value})
        reject(name, lambda changed=changed: M.audit_report(changed, actual, selected))
    for name, key, value in [('old-kernel', 'kernel', parent['kernel']),
                             ('new-kernel-tamper', 'kernel', inputs['kernel'] + b'x'),
                             ('args', 'args', b'-v serial=4'),
                             ('config-args', 'config', inputs['config'].replace(b'-v serial=3', b'-v serial=4')),
                             ('parent-record', 'parent-record', inputs['parent-record'] + b'x'),
                             ('trust', 'trust', inputs['trust'] + b'x')]:
        changed = dict(inputs, **{key: value})
        reject(name, lambda changed=changed: M.check_inputs(changed))
    reject('material', lambda: M.inspect_payload(selected, parent, inputs, material + b'x', ev, out / 'material'))
    changed_ev = copy.deepcopy(ev)
    changed_ev['renderer_audit']['sha256'] = '0' * 64
    reject('evidence', lambda: M.inspect_payload(selected, parent, inputs, material, changed_ev, out / 'evidence'))
    good_adt = (selected / 'derived.adt').read_bytes()
    tree = M.C.C.parse(good_adt)
    chosen = M.C.C.find(tree, '/chosen')
    chosen['children'].append({'properties': [('name', 0, b'asmb\0')], 'children': []})
    asmb = M.C.C.encode(tree)
    reject('asmb', lambda: M.C.check_adt(inputs['parent-adt'], asmb, M.DIGEST))
    tree = M.C.C.parse(good_adt)
    chosen = M.C.C.find(tree, '/chosen')
    chosen['properties'] = [(k, f, bytes(48) if k == 'boot-manifest-hash' else v)
                            for k, f, v in chosen['properties']]
    reject('adt-digest', lambda: M.C.check_adt(inputs['parent-adt'], M.C.C.encode(tree), M.DIGEST))
    fixture = out / 'bad-record'
    fixture.mkdir()
    for name in ('payload.img', 'derived.adt', 'kernel.macho', 'layout.json'):
        shutil.copyfile(selected / name, fixture / name)
    bad_record = json.loads((selected / 'record.json').read_text())
    bad_record['profile'] = 'chmh-only-20261112-r1'
    (fixture / 'record.json').write_text(json.dumps(bad_record))
    reject('actual-record', lambda: M.inspect_payload(fixture, parent, inputs, material, ev, out / 'bad-record-audit'))
    (fixture / 'record.json').write_bytes((selected / 'record.json').read_bytes() + b' ')
    reject('record-synchronized-hash', lambda: M.inspect_payload(fixture, parent, inputs, material, ev, out / 'record-hash-audit'))
    changed = bytearray(image)
    changed[4096] ^= 1
    synced = dict(report, outer_sha256=M.O.sha(changed))
    reject('actual-outer-tamper-synchronized-report',
           lambda: M.audit_report(synced, M.audit_image(bytes(changed), selected, inputs, material, ev, stock, out / 'tampered-outer'), selected))
    (out / 'tests.json').write_text(json.dumps({'status': 'self-checked', 'positive_actual_outer': True,
                                                 'relative_record_path': True, 'rejected': rejected}, indent=2) + '\n')
    print(json.dumps({'status': 'self-checked', 'positive_actual_outer': True, 'negative_count': len(rejected), 'rejected': rejected}))


if __name__ == '__main__':
    main()
