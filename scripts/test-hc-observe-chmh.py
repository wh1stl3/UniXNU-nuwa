#!/usr/bin/env python3
"""Targeted HC profile negative checks against the actual packaged outer."""
import importlib.util
import argparse
import json
from pathlib import Path
import shutil
import sys

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('hc', Path(__file__).with_name('build-hc-observe-chmh.py'))
hc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hc)
M = hc.M
selected = M.ROOT / 'out/nuwa-ufs-hc-chmh-20261113-r1'
parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, default=selected / 'negative-tests')
out = M.P.reserve(parser.parse_args().output)
parent, inputs, material, ev = M.fixed(out)
stock, _ = M.stock_inputs()
image = (selected / 'vendor_boot.img').read_bytes()
report = json.loads((selected / 'outer-record.json').read_text())
actual = M.audit_image(image, selected, inputs, material, ev, stock, out / 'positive')
M.audit_report(report, actual, selected)
rejected = []


def reject(name, call):
    try:
        call()
    except (ValueError, KeyError):
        rejected.append(name)
        return
    raise AssertionError('invalid input accepted: ' + name)


reject('profile', lambda: M.audit_report(dict(report, profile='other'), actual, selected))
for name, key, value in [
    ('kernel', 'kernel', parent['kernel']),
    ('args', 'args', inputs['args'] + b' '),
    ('probe0', 'args', inputs['args'].replace(b'probe=2', b'probe=0')),
    ('probe3', 'args', inputs['args'].replace(b'probe=2', b'probe=3')),
    ('root1', 'args', inputs['args'].replace(b'root=0', b'root=1')),
    ('config-root1', 'config', inputs['config'].replace(b'root=0', b'root=1')),
    ('parent-adt', 'parent-adt', inputs['parent-adt'] + b'x'),
]:
    changed = dict(inputs, **{key: value})
    reject(name, lambda changed=changed: M.check_inputs(changed))
reject('material', lambda: M.inspect_payload(selected, parent, inputs, material + b'x', ev, out / 'bad-material'))
adt = bytearray((selected / 'derived.adt').read_bytes())
adt[-1] ^= 1
reject('derived-adt', lambda: M.C.check_adt(inputs['parent-adt'], bytes(adt), M.DIGEST))
fixture = out / 'bad-record'
fixture.mkdir()
for name in ('payload.img', 'derived.adt', 'kernel.macho', 'layout.json', 'provenance.json'):
    shutil.copyfile(selected / name, fixture / name)
(fixture / 'record.json').write_bytes((selected / 'record.json').read_bytes() + b' ')
reject('record', lambda: M.inspect_payload(fixture, parent, inputs, material, ev, out / 'bad-record-audit'))
changed = bytearray(image)
changed[4096] ^= 1
synced = dict(report, outer_sha256=M.O.sha(changed))
reject('actual-outer', lambda: M.audit_report(synced, M.audit_image(bytes(changed), selected, inputs, material, ev, stock, out / 'bad-outer'), selected))
M.O.write_json(out / 'tests.json', {'status': 'self-checked', 'positive_actual_outer': True, 'rejected': rejected})
print(json.dumps({'status': 'self-checked', 'rejected': rejected}))
