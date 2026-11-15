"""Negative checks against the actual CHMH generator and FAT audit."""
import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location('publisher', Path(__file__).with_name('build-chmh-only-payload.py'))
P = importlib.util.module_from_spec(spec); spec.loader.exec_module(P)
C = P.C
parser = argparse.ArgumentParser()
parser.add_argument('--candidate', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
out = args.output.resolve()
P.require(out.is_relative_to((P.ROOT / 'out').resolve()), 'Output outside out/')
out.mkdir(parents=True, exist_ok=False)
parent = P.extract(P.FAT, out / 'parent')
inputs = P.fixed_inputs(parent)
_, digest = P.check_inputs(inputs)
good = P.derived(inputs['parent-adt'], digest)
P.check_adt(inputs['parent-adt'], good, digest)
count = 0


def reject(fn):
    global count
    try:
        fn()
    except (ValueError, KeyError):
        count += 1
        return
    raise AssertionError('Invalid input accepted')


def altered(mode):
    tree = C.parse(good)
    chosen = C.find(tree, '/chosen')
    if mode == 'missing':
        chosen['properties'] = [x for x in chosen['properties'] if x[0] != 'boot-manifest-hash']
    elif mode == 'duplicate':
        chosen['properties'].append(('boot-manifest-hash', 0, digest))
    elif mode in ('hextext', 'hextext48', 'short', 'wrong'):
        value = {'hextext': digest.hex().encode(), 'hextext48': digest.hex().encode()[:48],
                 'short': digest[:-1], 'wrong': bytes(48)}[mode]
        chosen['properties'] = [(k, f, value if k == 'boot-manifest-hash' else v) for k, f, v in chosen['properties']]
    elif mode == 'asmb':
        chosen['children'].append({'properties': [('name', 0, b'asmb\0')], 'children': []})
    elif mode == 'smb':
        chosen['properties'].append(('lp-smb0', 0, bytes(4)))
    return C.encode(tree)


for name in ('missing', 'duplicate', 'hextext', 'hextext48', 'short', 'wrong', 'asmb', 'smb'):
    reject(lambda name=name: P.check_adt(inputs['parent-adt'], altered(name), digest))
for key in ('parent-adt', 'loader', 'trust', 'kernel', 'args', 'config', 'parent-record', 'fat'):
    changed = dict(inputs); changed[key] += b'x'
    reject(lambda changed=changed: P.check_inputs(changed))

# The real FAT and report are copied into fresh test output. Modify actual ADT,
# then synchronize the report and derived sidecar; fixed input semantics still reject.
candidate = args.candidate.resolve(strict=True)
P.audit(candidate, parent, inputs, out / 'positive-readback')
tamper = out / 'tamper'; tamper.mkdir()
shutil.copyfile(candidate / 'payload.img', tamper / 'payload.img')
bad = altered('wrong'); (tamper / 'derived.adt').write_bytes(bad)
p = subprocess.run(['mcopy', '-o', '-i', str(tamper / 'payload.img'), str(tamper / 'derived.adt'), '::/EFI/UniXNU/Payloads/kernel.macho.adt'], capture_output=True)
assert p.returncode == 0
record = json.loads((candidate / 'record.json').read_text())
record['derived_adt_sha256'] = P.sha(bad)
record['derived_adt_bytes'] = len(bad)
record['payload_sha256'] = P.sha((tamper / 'payload.img').read_bytes())
record['chmh_hex'] = bytes(48).hex()
(tamper / 'record.json').write_text(json.dumps(record))
reject(lambda: P.audit(tamper, parent, inputs, out / 'tamper-readback'))
rawdir = out / 'raw-tamper'; rawdir.mkdir()
raw = bytearray((candidate / 'payload.img').read_bytes()); raw[-1] ^= 1
(rawdir / 'payload.img').write_bytes(raw)
shutil.copyfile(candidate / 'derived.adt', rawdir / 'derived.adt')
record = json.loads((candidate / 'record.json').read_text())
record['payload_sha256'] = P.sha(raw)
(rawdir / 'record.json').write_text(json.dumps(record))
reject(lambda: P.audit(rawdir, parent, inputs, out / 'raw-tamper-readback'))
print('self-checked negative cases:', count, 'positive FAT audit: 1')
