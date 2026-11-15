#!/usr/bin/env python3
"""Host-only incremental tests against the historical r4 root package."""
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('root_package', ROOT / 'scripts/build-ufs-apfs-root-chmh.py')
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)
M = P.M
output = ROOT / 'out/nuwa-ufs-apfs-root-chmh-20261114-r1'
M.KERNEL_BYTES = 55545856
M.KERNEL_SHA = '3ac37037104c98f11fc009abc42cf3495802f874ab3aa9fff1a929079454ad45'


def rejected(fn):
    try:
        fn()
    except (ValueError, AssertionError):
        return
    raise AssertionError('negative control accepted')


kernel = (output / 'kernel.macho').read_bytes()
P.check_root(kernel)
bad = bytearray(kernel)
bad[-1] ^= 1
rejected(lambda: P.check_root(bytes(bad)))
parent = M.C.ADT.read_bytes()
record = json.loads((output / 'record.json').read_bytes())
digest = bytes.fromhex(record['chmh_hex'])
adt = (output / 'derived.adt').read_bytes()
P.check_adt(parent, adt, digest)
bad = bytearray(adt)
at = bad.index(P.UUID.encode())
bad[at] ^= 1
rejected(lambda: P.check_adt(parent, bytes(bad), digest))
bad = bytearray(adt)
at = bad.index(digest)
bad[at] ^= 1
rejected(lambda: P.check_adt(parent, bytes(bad), digest))
image = (output / 'vendor_boot.img').read_bytes()
fat = (output / 'payload.img').read_bytes()
stock = M.STOCK.read_bytes()
M.V.compare(stock, image, fat, len(stock))
bad = bytearray(image)
bad[len(bad) // 2] ^= 1
rejected(lambda: M.V.compare(stock, bytes(bad), fat, len(stock)))
inputs = json.loads((ROOT / 'out/nuwa-ufs-apfs-root-integration-20261114/run-r4/root-inputs.json').read_text())
userdata = ROOT / 'out/root-external-policies-20261113/candidate/userdata/userdata-root.img'
with userdata.open('rb') as stream:
    header = stream.read(4096)
    assert hashlib.sha256(header).hexdigest() == inputs['userdata_header_sha256']
    for entry in inputs['entries']:
        if entry['name'].endswith('.vroot'):
            stream.seek(entry['offset'])
            left = entry['size']
            digest = hashlib.sha256()
            while left:
                data = stream.read(min(left, 1024 * 1024))
                assert data
                digest.update(data)
                left -= len(data)
            assert digest.hexdigest() == entry['sha256']
print('self-checked: r4 kernel/policies, ADT root+CHMH mutations, outer mutation, userdata policy tables')
