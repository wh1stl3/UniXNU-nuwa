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
# r17: the fixed-dyld-path candidate must validate and stay process-free in the dry phases.
current = E.Run(ROOT, 'r17-host-only', 'adb', 'fastboot', runner=trap, profile=E.R17_PROFILE)
assert not current.directory.exists()
current.host_inputs()
assert E.PROFILES[E.R17_PROFILE]['candidate_sha256'] == \
    '579d19b4714364a842d90f48343d21e23dcfece7f783bd147a5d7206fdd8a12a'
assert 'build-tag=nuwa-r17' in E.PROFILES[E.R17_PROFILE]['frozen']['args']
for phase in ('prepare', 'boot', 'restore'):
    result = current.execute(phase)
    assert result['dry_run'] and result['device_commands_executed'] == 0
    assert result['profile'] == E.R17_PROFILE
assert not current.directory.exists()
current.frozen = copy.deepcopy(current.frozen)
current.frozen['kernel_sha256'] = '0' * 64
rejected(current.host_inputs)
# r17c: same mounts plus the synchronous repaint; validates the same way.
repaint = E.Run(ROOT, 'r17c-host-only', 'adb', 'fastboot', runner=trap, profile=E.R17C_PROFILE)
repaint.host_inputs()
assert E.PROFILES[E.R17C_PROFILE]['candidate_sha256'] == \
    'dfbbc3038c455fa188fae2080ebb2502a18facefc71d178514490a20789ec7a1'
assert 'build-tag=nuwa-r17c' in E.PROFILES[E.R17C_PROFILE]['frozen']['args']
for phase in ('prepare', 'boot', 'restore'):
    result = repaint.execute(phase)
    assert result['dry_run'] and result['device_commands_executed'] == 0
    assert result['profile'] == E.R17C_PROFILE
assert not repaint.directory.exists()
# r18: the union-on-/ candidate; validates and stays process-free like the others.
union = E.Run(ROOT, 'r18-host-only', 'adb', 'fastboot', runner=trap, profile=E.R18_PROFILE)
union.host_inputs()
assert E.PROFILES[E.R18_PROFILE]['candidate_sha256'] == \
    'a1996558ce34d27e33068012b22d05ddf9f8c56b995a73be49089d8ae1824bdd'
assert 'build-tag=nuwa-r18' in E.PROFILES[E.R18_PROFILE]['frozen']['args']
for phase in ('prepare', 'boot', 'restore'):
    result = union.execute(phase)
    assert result['dry_run'] and result['device_commands_executed'] == 0
    assert result['profile'] == E.R18_PROFILE
assert not union.directory.exists()
union.frozen = copy.deepcopy(union.frozen)
union.frozen['args'] += ' native-ufs-probe=2'
rejected(union.host_inputs)
# r19: the cache-probe candidate; same host-input and dry-phase contract.
probe = E.Run(ROOT, 'r19-host-only', 'adb', 'fastboot', runner=trap, profile=E.R19_PROFILE)
probe.host_inputs()
assert E.PROFILES[E.R19_PROFILE]['candidate_sha256'] == \
    'd5f2855ffbc9b79ba2aad3d987dbe97d4dcf82a63f47ac812ae3053edc9aabbb'
assert 'build-tag=nuwa-r19' in E.PROFILES[E.R19_PROFILE]['frozen']['args']
for phase in ('prepare', 'boot', 'restore'):
    result = probe.execute(phase)
    assert result['dry_run'] and result['device_commands_executed'] == 0
    assert result['profile'] == E.R19_PROFILE
assert not probe.directory.exists()
probe.frozen = copy.deepcopy(probe.frozen)
probe.frozen['chmh_hex'] = '0' * 96
rejected(probe.host_inputs)
# r20: trace-on candidate with the AMFI / code-signing view.
trace = E.Run(ROOT, 'r20-host-only', 'adb', 'fastboot', runner=trap, profile=E.R20_PROFILE)
trace.host_inputs()
assert E.PROFILES[E.R20_PROFILE]['candidate_sha256'] == \
    '6d6282388232b2d64d31f10902eb5a338f7463c2444ba36f7b83c2f53aa12d5f'
assert 'build-tag=nuwa-r20' in E.PROFILES[E.R20_PROFILE]['frozen']['args']
for phase in ('prepare', 'boot', 'restore'):
    result = trace.execute(phase)
    assert result['dry_run'] and result['device_commands_executed'] == 0
    assert result['profile'] == E.R20_PROFILE
assert not trace.directory.exists()
trace.frozen = copy.deepcopy(trace.frozen)
trace.frozen['kernel_sha256'] = '0' * 64
rejected(trace.host_inputs)
# r22: no dyld override, six probes, 4K hash cache, flags readback.
fixed22 = E.Run(ROOT, 'r22-host-only', 'adb', 'fastboot', runner=trap, profile=E.R22_PROFILE)
fixed22.host_inputs()
assert E.PROFILES[E.R22_PROFILE]['candidate_sha256'] == \
    '8660cf6baf53a92939abe3638d45521db0cd9c67a4656cb8fa00e3c52353e7d0'
assert 'build-tag=nuwa-r22' in E.PROFILES[E.R22_PROFILE]['frozen']['args']
for phase in ('prepare', 'boot', 'restore'):
    result = fixed22.execute(phase)
    assert result['dry_run'] and result['device_commands_executed'] == 0
    assert result['profile'] == E.R22_PROFILE
assert not fixed22.directory.exists()
fixed22.frozen = copy.deepcopy(fixed22.frozen)
fixed22.frozen['args'] += ' native-ufs-probe=2'
rejected(fixed22.host_inputs)
# r23: the probe holds no usecount (one lookup, one put) and the magic is 16 bytes.
fixed23 = E.Run(ROOT, 'r23-host-only', 'adb', 'fastboot', runner=trap, profile=E.R23_PROFILE)
fixed23.host_inputs()
assert E.PROFILES[E.R23_PROFILE]['candidate_sha256'] == \
    '1a9f6299f90e5f9cfdd3e728e2679c59d6e381a112f5d3915454696286321e18'
assert 'build-tag=nuwa-r23' in E.PROFILES[E.R23_PROFILE]['frozen']['args']
assert E.PROFILES[E.R23_PROFILE]['frozen']['kernel_sha256'] == \
    '89db8ee910a23d8732f18393e2065ab9ae2a1bb69b9f7d0fcd2fa96de966fdf2'
for phase in ('prepare', 'boot', 'restore'):
    result = fixed23.execute(phase)
    assert result['dry_run'] and result['device_commands_executed'] == 0
    assert result['profile'] == E.R23_PROFILE
assert not fixed23.directory.exists()
fixed23.frozen = copy.deepcopy(fixed23.frozen)
fixed23.frozen['kernel_sha256'] = '0' * 64
rejected(fixed23.host_inputs)
# r24: root reference across the union mount, reboot log, Data seed observations.
fixed24 = E.Run(ROOT, 'r24-host-only', 'adb', 'fastboot', runner=trap, profile=E.R24_PROFILE)
fixed24.host_inputs()
assert E.PROFILES[E.R24_PROFILE]['candidate_sha256'] == \
    '469524541c818af9527864644b9f5a7d19e9be822072ca6e1d60ae9136ee5e8a'
assert 'build-tag=nuwa-r24' in E.PROFILES[E.R24_PROFILE]['frozen']['args']
assert E.PROFILES[E.R24_PROFILE]['frozen']['kernel_sha256'] == \
    'd8fc613a2e0a5749ab3708b40292a00ac9bd5c070579cc75857f04a113f738a7'
for phase in ('prepare', 'boot', 'restore'):
    result = fixed24.execute(phase)
    assert result['dry_run'] and result['device_commands_executed'] == 0
    assert result['profile'] == E.R24_PROFILE
assert not fixed24.directory.exists()
fixed24.frozen = copy.deepcopy(fixed24.frozen)
fixed24.frozen['kernel_sha256'] = '0' * 64
rejected(fixed24.host_inputs)
# r25: the console-only observations moved onto the diagnostic page.
fixed25 = E.Run(ROOT, 'r25-host-only', 'adb', 'fastboot', runner=trap, profile=E.R25_PROFILE)
fixed25.host_inputs()
assert E.PROFILES[E.R25_PROFILE]['candidate_sha256'] == \
    'fcfd25489425a6abe7bc262a9169d81df6b4f68b06a9017ec427f4360afafc6f'
assert 'build-tag=nuwa-r25' in E.PROFILES[E.R25_PROFILE]['frozen']['args']
assert E.PROFILES[E.R25_PROFILE]['frozen']['kernel_sha256'] == \
    'c4a2bdecde81ad511a153ab262ded1bd44a6078bea796a8b0e5bcab6982e362a'
for phase in ('prepare', 'boot', 'restore'):
    result = fixed25.execute(phase)
    assert result['dry_run'] and result['device_commands_executed'] == 0
    assert result['profile'] == E.R25_PROFILE
assert not fixed25.directory.exists()
fixed25.frozen = copy.deepcopy(fixed25.frozen)
fixed25.frozen['kernel_sha256'] = '0' * 64
rejected(fixed25.host_inputs)
# r26: the Data ram disk is created explicitly instead of via the IOResources persona.
fixed26 = E.Run(ROOT, 'r26-host-only', 'adb', 'fastboot', runner=trap, profile=E.R26_PROFILE)
fixed26.host_inputs()
assert E.PROFILES[E.R26_PROFILE]['candidate_sha256'] == \
    'fc2fba6ab650d4ad2a742e4a20ad5146b86feb87535e84d90de5edd18d42d186'
assert 'build-tag=nuwa-r26' in E.PROFILES[E.R26_PROFILE]['frozen']['args']
assert E.PROFILES[E.R26_PROFILE]['frozen']['kernel_sha256'] == \
    '0ff3494854ee02dbb33e2d07ceb074da2d68fcfc18089c328791f35f4ac1f08a'
for phase in ('prepare', 'boot', 'restore'):
    result = fixed26.execute(phase)
    assert result['dry_run'] and result['device_commands_executed'] == 0
    assert result['profile'] == E.R26_PROFILE
assert not fixed26.directory.exists()
fixed26.frozen = copy.deepcopy(fixed26.frozen)
fixed26.frozen['kernel_sha256'] = '0' * 64
rejected(fixed26.host_inputs)
# r27: the Data disk is created at the data mount, after bsd_autoconf.
fixed27 = E.Run(ROOT, 'r27-host-only', 'adb', 'fastboot', runner=trap, profile=E.R27_PROFILE)
fixed27.host_inputs()
assert E.PROFILES[E.R27_PROFILE]['candidate_sha256'] == \
    'aa51fa0f0d0578308df939b94af1eb071f12b44a6d6015b3b9c3244c2c462401'
assert 'build-tag=nuwa-r27' in E.PROFILES[E.R27_PROFILE]['frozen']['args']
assert E.PROFILES[E.R27_PROFILE]['frozen']['kernel_sha256'] == \
    'a8921ab06add3bf514adfca4eafe74dd879176d76dceb887c74d211cfef6dd85'
for phase in ('prepare', 'boot', 'restore'):
    result = fixed27.execute(phase)
    assert result['dry_run'] and result['device_commands_executed'] == 0
    assert result['profile'] == E.R27_PROFILE
assert not fixed27.directory.exists()
fixed27.frozen = copy.deepcopy(fixed27.frozen)
fixed27.frozen['kernel_sha256'] = '0' * 64
rejected(fixed27.host_inputs)
# r28: class registration bracketed by preModLoad/postModLoad; r24 root guard removed.
fixed28 = E.Run(ROOT, 'r28-host-only', 'adb', 'fastboot', runner=trap, profile=E.R28_PROFILE)
fixed28.host_inputs()
assert E.PROFILES[E.R28_PROFILE]['candidate_sha256'] == \
    '2652369b1c2eb00f5396e8c1f19719709fc224b2c396199ba97a61cc247bacf7'
assert 'build-tag=nuwa-r28' in E.PROFILES[E.R28_PROFILE]['frozen']['args']
assert E.PROFILES[E.R28_PROFILE]['frozen']['kernel_sha256'] == \
    'e000e7a6ac99b5f72e0ea1b0d73521c07986a0a126ff62b4b2250f46abb43391'
for phase in ('prepare', 'boot', 'restore'):
    result = fixed28.execute(phase)
    assert result['dry_run'] and result['device_commands_executed'] == 0
    assert result['profile'] == E.R28_PROFILE
assert not fixed28.directory.exists()
fixed28.frozen = copy.deepcopy(fixed28.frozen)
fixed28.frozen['kernel_sha256'] = '0' * 64
rejected(fixed28.host_inputs)
# r29: root cdir reference in set_rootvnode + reboot requester at the three entry points.
fixed29 = E.Run(ROOT, 'r29-host-only', 'adb', 'fastboot', runner=trap, profile=E.R29_PROFILE)
fixed29.host_inputs()
assert E.PROFILES[E.R29_PROFILE]['candidate_sha256'] == \
    'e1f247f334e270730078e23368933d24c0c027f60c15c94d261f0624f214ffb6'
assert 'build-tag=nuwa-r29' in E.PROFILES[E.R29_PROFILE]['frozen']['args']
assert E.PROFILES[E.R29_PROFILE]['frozen']['kernel_sha256'] == \
    'ca33a66413e987a0dc97148f033d94c0d18f9db87df880e0b5c18a2997254de7'
for phase in ('prepare', 'boot', 'restore'):
    result = fixed29.execute(phase)
    assert result['dry_run'] and result['device_commands_executed'] == 0
    assert result['profile'] == E.R29_PROFILE
assert not fixed29.directory.exists()
fixed29.frozen = copy.deepcopy(fixed29.frozen)
fixed29.frozen['kernel_sha256'] = '0' * 64
rejected(fixed29.host_inputs)
# r30: reboot howto, keybag directories and the bsd_init -> keybagd time (observation only).
fixed30 = E.Run(ROOT, 'r30-host-only', 'adb', 'fastboot', runner=trap, profile=E.R30_PROFILE)
fixed30.host_inputs()
assert E.PROFILES[E.R30_PROFILE]['candidate_sha256'] == \
    'd5d99a03597c3d571784beb4b8893d6f00c27aa7160ab749146a725f7ff5b97e'
assert 'build-tag=nuwa-r30' in E.PROFILES[E.R30_PROFILE]['frozen']['args']
assert E.PROFILES[E.R30_PROFILE]['frozen']['kernel_sha256'] == \
    '334e43567a4084ab864aa3a363c71f9e87dd339f2b6596c107a54758107a3def'
for phase in ('prepare', 'boot', 'restore'):
    result = fixed30.execute(phase)
    assert result['dry_run'] and result['device_commands_executed'] == 0
    assert result['profile'] == E.R30_PROFILE
assert not fixed30.directory.exists()
fixed30.frozen = copy.deepcopy(fixed30.frozen)
fixed30.frozen['kernel_sha256'] = '0' * 64
rejected(fixed30.host_inputs)
# r31: AppleKeyStoreState linked in, gated by aks=1 (args change -> new CHMH).
fixed31 = E.Run(ROOT, 'r31-host-only', 'adb', 'fastboot', runner=trap, profile=E.R31_PROFILE)
fixed31.host_inputs()
assert E.PROFILES[E.R31_PROFILE]['candidate_sha256'] == \
    'c9ed423d3f6b3ac8ebf1d9fe79ac60d31b684cd56fe4abb8e3559b1e1286ffd9'
assert 'aks=1' in E.PROFILES[E.R31_PROFILE]['frozen']['args']
assert 'build-tag=nuwa-r31' in E.PROFILES[E.R31_PROFILE]['frozen']['args']
assert E.PROFILES[E.R31_PROFILE]['frozen']['kernel_sha256'] == \
    '626543a02f1a9d79e404ad588416e4f810ed1d7bb106ed9759c3b460a4227afd'
for phase in ('prepare', 'boot', 'restore'):
    result = fixed31.execute(phase)
    assert result['dry_run'] and result['device_commands_executed'] == 0
    assert result['profile'] == E.R31_PROFILE
assert not fixed31.directory.exists()
fixed31.frozen = copy.deepcopy(fixed31.frozen)
fixed31.frozen['kernel_sha256'] = '0' * 64
rejected(fixed31.host_inputs)
# r32: AppleKeyStore dispatch ring drawn on row 10 (same args, new build tag -> new CHMH).
fixed32 = E.Run(ROOT, 'r32-host-only', 'adb', 'fastboot', runner=trap, profile=E.R32_PROFILE)
fixed32.host_inputs()
assert E.PROFILES[E.R32_PROFILE]['candidate_sha256'] == \
    'dfecf0f3d9a5497e7a67875e225ae1dae56dbfb92da43653e205c0acb366e9c7'
assert 'build-tag=nuwa-r32' in E.PROFILES[E.R32_PROFILE]['frozen']['args']
assert E.PROFILES[E.R32_PROFILE]['frozen']['kernel_sha256'] == \
    '8a343b2784ea63862a971645c22fda3916b5dc9802cc0f01ce7c25dc5dd07966'
for phase in ('prepare', 'boot', 'restore'):
    result = fixed32.execute(phase)
    assert result['dry_run'] and result['device_commands_executed'] == 0
    assert result['profile'] == E.R32_PROFILE
assert not fixed32.directory.exists()
fixed32.frozen = copy.deepcopy(fixed32.frozen)
fixed32.frozen['kernel_sha256'] = '0' * 64
rejected(fixed32.host_inputs)
# r33: the AKS ring moved into the panic-safe band (row 6); new build tag -> new CHMH.
fixed33 = E.Run(ROOT, 'r33-host-only', 'adb', 'fastboot', runner=trap, profile=E.R33_PROFILE)
fixed33.host_inputs()
assert E.PROFILES[E.R33_PROFILE]['candidate_sha256'] == \
    '2d97df5ffe06b81ed9ac16e4be8abaed9897b4bba1ebd8e3388cea5fa9e33f29'
assert 'build-tag=nuwa-r33' in E.PROFILES[E.R33_PROFILE]['frozen']['args']
assert E.PROFILES[E.R33_PROFILE]['frozen']['kernel_sha256'] == \
    '6234a90ca614f26c13779b1f17adf76b3c503f5d2f485188adae3baa54701535'
for phase in ('prepare', 'boot', 'restore'):
    result = fixed33.execute(phase)
    assert result['dry_run'] and result['device_commands_executed'] == 0
    assert result['profile'] == E.R33_PROFILE
assert not fixed33.directory.exists()
fixed33.frozen = copy.deepcopy(fixed33.frozen)
fixed33.frozen['kernel_sha256'] = '0' * 64
rejected(fixed33.host_inputs)
# r34: keybag seed + ADT /defaults no-effaceable-storage + kernel launchd disabled list.
fixed34 = E.Run(ROOT, 'r34-host-only', 'adb', 'fastboot', runner=trap, profile=E.R34_PROFILE)
fixed34.host_inputs()
assert E.PROFILES[E.R34_PROFILE]['candidate_sha256'] == \
    '46aa4fd9f575a30824543fed7c128c5013d35af8d62a98715d0312d1752c891e'
assert 'disable-watchdogd=1' in E.PROFILES[E.R34_PROFILE]['frozen']['args']
assert 'build-tag=nuwa-r34' in E.PROFILES[E.R34_PROFILE]['frozen']['args']
assert E.PROFILES[E.R34_PROFILE]['frozen']['kernel_sha256'] == \
    'ce24818ea19e1301dc0f4173a448ff3088aabf9bcc413f645f93c1c569a7f6dd'
assert E.PROFILES[E.R34_PROFILE]['frozen']['seed_sha256'] == \
    '2c95d15be323eeb336c58aa1d9cc35bc72c0923942e76a702ab24c0a858c8110'
for phase in ('prepare', 'boot', 'restore'):
    result = fixed34.execute(phase)
    assert result['dry_run'] and result['device_commands_executed'] == 0
    assert result['profile'] == E.R34_PROFILE
assert not fixed34.directory.exists()
fixed34.frozen = copy.deepcopy(fixed34.frozen)
fixed34.frozen['kernel_sha256'] = '0' * 64
rejected(fixed34.host_inputs)
# r35: abnormal-exit ring drawn on row 0 (safe band); new tag -> new CHMH.
fixed35 = E.Run(ROOT, 'r35-host-only', 'adb', 'fastboot', runner=trap, profile=E.R35_PROFILE)
fixed35.host_inputs()
assert E.PROFILES[E.R35_PROFILE]['candidate_sha256'] == \
    'c6e64820cc46c1a54e65d3640994ad7acf0e7aa807dfd3765eac82f483a4a7ed'
assert 'build-tag=nuwa-r35' in E.PROFILES[E.R35_PROFILE]['frozen']['args']
assert E.PROFILES[E.R35_PROFILE]['frozen']['kernel_sha256'] == \
    '787610183dc7f772e2d01aa183f72f2fcc52245fc44407e6c815ced614412464'
for phase in ('prepare', 'boot', 'restore'):
    result = fixed35.execute(phase)
    assert result['dry_run'] and result['device_commands_executed'] == 0
    assert result['profile'] == E.R35_PROFILE
assert not fixed35.directory.exists()
fixed35.frozen = copy.deepcopy(fixed35.frozen)
fixed35.frozen['kernel_sha256'] = '0' * 64
rejected(fixed35.host_inputs)
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
