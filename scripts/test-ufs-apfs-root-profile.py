#!/usr/bin/env python3
"""Root profile host-input and no-authorization process-trap tests."""
import copy
import importlib.util
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('executor', ROOT / 'scripts/run-pmap-ret-once.py')
E = importlib.util.module_from_spec(spec)
spec.loader.exec_module(E)


def trap(*args, **kwargs):
    raise AssertionError('process invocation forbidden')


def rejected(fn):
    try:
        fn()
    except E.Stop:
        return
    raise AssertionError('negative input accepted')


subprocess.run = trap
run = E.Run(ROOT, 'root-profile-host-only', 'adb', 'fastboot', runner=trap, profile=E.ROOT_PROFILE)
assert not run.directory.exists()
run.host_inputs()
for phase in ('prepare', 'boot', 'restore'):
    result = run.execute(phase)
    assert result['dry_run'] and result['device_commands_executed'] == 0
    assert result['profile'] == E.ROOT_PROFILE
assert not run.directory.exists()
run.frozen = copy.deepcopy(run.frozen)
run.frozen['args'] += ' native-ufs-probe=2'
rejected(run.host_inputs)
run.frozen = copy.deepcopy(E.PROFILES[E.ROOT_PROFILE]['frozen'])
run.frozen['kernel_sha256'] = '0' * 64
rejected(run.host_inputs)
run.frozen = copy.deepcopy(E.PROFILES[E.ROOT_PROFILE]['frozen'])
run.frozen['chmh_hex'] = '0' * 96
rejected(run.host_inputs)
run.candidate_sha256 = '0' * 64
rejected(run.host_inputs)
assert E.PROFILES[E.NOP_PROFILE]['frozen']['args'] == '-v serial=3 nuwa-pmgr=2 native-ufs-probe=2 native-ufs-root=0'
E.Run(ROOT, 'old-nop-host-only', 'adb', 'fastboot', runner=trap, profile=E.NOP_PROFILE).host_inputs()
spec = importlib.util.spec_from_file_location('root_packer', ROOT / 'scripts/build-ufs-apfs-root-chmh.py')
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)
package = (ROOT / E.PROFILES[E.ROOT_PROFILE]['candidate']).parent
digest = bytes.fromhex(E.PROFILES[E.ROOT_PROFILE]['frozen']['chmh_hex'])
adt = (package / 'derived.adt').read_bytes()
parent = P.M.C.ADT.read_bytes()
P.check_adt(parent, adt, digest)
bad = bytearray(adt)
bad[bad.index(P.UUID.encode())] ^= 1
try:
    P.check_adt(parent, bytes(bad), digest)
except ValueError:
    pass
else:
    raise AssertionError('mutated root UUID accepted')
image = (package / 'vendor_boot.img').read_bytes()
fat = (package / 'payload.img').read_bytes()
stock = P.M.STOCK.read_bytes()
P.M.V.compare(stock, image, fat, len(stock))
bad = bytearray(image)
bad[len(bad) // 2] ^= 1
try:
    P.M.V.compare(stock, bytes(bad), fat, len(stock))
except (ValueError, AssertionError):
    pass
else:
    raise AssertionError('mutated outer accepted')
print('self-checked: host-inputs, 3 dry phases, no process, 4 binding negatives, old NOP args, root UUID and outer mutations')
