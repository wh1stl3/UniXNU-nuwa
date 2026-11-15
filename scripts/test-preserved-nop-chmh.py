#!/usr/bin/env python3
"""Actual-outer and four negative tests for the preserved-NOP profile."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('preserved_nop', Path(__file__).with_name('build-preserved-nop-chmh.py'))
profile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(profile)
M = profile.M
selected = M.ROOT / 'out/nuwa-ufs-preserved-nop-chmh-20261114-r1'
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
reject('old-kernel', lambda: M.check_inputs(dict(inputs, kernel=parent['kernel'])))
reject('material', lambda: M.inspect_payload(selected, parent, inputs, material + b'x', ev, out / 'bad-material'))
changed = bytearray(image)
changed[4096] ^= 1
synced = dict(report, outer_sha256=M.O.sha(changed))
reject('actual-outer', lambda: M.audit_report(synced, M.audit_image(bytes(changed), selected, inputs, material, ev, stock, out / 'bad-outer'), selected))
M.O.write_json(out / 'tests.json', {'status': 'self-checked', 'positive_actual_outer': True, 'rejected': rejected})
print(json.dumps({'status': 'self-checked', 'rejected': rejected}))
