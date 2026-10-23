"""Read-only validation of the exact offline-built SEC diagnostic package."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]
APPROVAL = 'SEC-HANDOFF-OFFLINE'


def validate(package_path):
    path = Path(package_path).resolve()
    package = json.loads(path.read_text())
    profiles = {'SEC-HANDOFF-OFFLINE': 'sec-handoff', 'CONSTRUCTOR-TRACE-OFFLINE': 'constructor-trace', 'MMU-BRANCHES-OFFLINE': 'mmu-branches'}
    profile_name = profiles.get(package.get('approval'))
    if profile_name is None or not path.is_relative_to(ROOT / 'reports' / profile_name) or path.name != 'package.json':
        raise ValueError('SEC diagnostic report outside its scope')
    run = package['run_id']
    if type(run) is not int or path.parent.name != str(run):
        raise ValueError('SEC diagnostic run/report mismatch')
    profile = json.loads((ROOT / f'config/firmware-{profile_name}-profile.json').read_text())
    artifact = ROOT / f'out/firmware-ci/{run}/nuwa-firmware-{run}'
    inputs = json.loads((artifact / 'inputs.json').read_text())
    if (inputs['recipe'] != profile['recipe'] or inputs['profile'] != profile_name
            or inputs['run_id'] != str(run) or package['device_commit'] != inputs['device_commit']):
        raise ValueError('SEC source/recipe evidence mismatch')
    spec = importlib.util.spec_from_file_location('sec_trial_inspector', ROOT / 'scripts/ci/inspect-firmware-candidate.py')
    inspector = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(inspector)
    actual = inspector.inspect(artifact, 'NuwaBootMemoryDxe', True, True, True, profile_name)
    expected = dict(approval=package['approval'], firmware_commit=profile['recipe']['sources']['firmware']['commit'],
                    original_boot_sha256='ef558db2a4fb021259d7af47a2398d7e56476d759162e7819959cd701a11ff31',
                    fd_sha256=actual['fd']['sha256'], shim_sha256=actual['shim']['sha256'],
                    shim_text_offset=0, pil_config_sha256=actual['pil_no_auto']['config']['sha256'],
                    pil_driver_sha256=actual['pil_no_auto']['retained_driver']['sha256'], pil_auto_entries=[],
                    allocation_trace=actual['allocation_trace'], factory_heap=actual['factory_heap'],
                    handoff_markers=actual['sec_entry_hob_producer']['handoff_markers'],
                    diagnostic_patch_sha256=next(p['sha256'] for p in profile['candidate']['patches']
                        if p['path'] == 'patches/firmware-candidates/0008-nuwa-dxe-allocation-trace.patch'),
                    header_version=4, page_bytes=4096, kernel_bytes=3145840, ramdisk_bytes=0, signature_bytes=0,
                    image_bytes=3153920, appended_dtb=False, fat_included=False, xnu_included=False)
    if profile_name in ('constructor-trace', 'mmu-branches'):
        expected.update(constructor_patch_sha256=next(p['sha256'] for p in profile['candidate']['patches'] if p['path'].endswith('0011-mu-constructor-trace.patch')),
                        constructor_markers=actual['sec_entry_hob_producer']['constructor_markers'])
    if profile_name == 'mmu-branches':
        expected.update(mmu_markers=actual['sec_entry_hob_producer']['mmu_markers'],
                        mmu_patch_sha256=profile['candidate']['patches'][-1]['sha256'])
    if any(package.get(key) != value for key, value in expected.items()):
        raise ValueError('SEC candidate exceeds inspected offline scope')
    image = (ROOT / package['image_path']).resolve()
    if not image.is_relative_to(ROOT / f'out/trial-boot/{profile_name}-{run}'):
        raise ValueError('SEC diagnostic image outside its scope')
    raw = image.read_bytes()
    if len(raw) != package['image_bytes'] or hashlib.sha256(raw).hexdigest() != package['image_sha256']:
        raise ValueError('SEC diagnostic container changed')
    shim = (artifact / 'shim/shim.bin').read_bytes()
    fd = (artifact / 'build/FV/SILICIUM_UEFI.fd').read_bytes()
    if raw[4096:4096 + len(shim) + len(fd)] != shim + fd:
        raise ValueError('SEC diagnostic container content changed')
    original = Path('D:/Code/PortingiOS/nuwa/backups/recovery-20261020T121245314787Z/boot_a.img').read_bytes()
    if hashlib.sha256(original).hexdigest() != expected['original_boot_sha256']:
        raise ValueError('Original recovery image changed')
    header = bytearray(original[:4096])
    struct.pack_into('<I', header, 8, len(shim) + len(fd))
    expected_image = bytes(header) + shim + fd + b'\0' * (-(len(shim) + len(fd)) % 4096)
    if raw != expected_image:
        raise ValueError('SEC diagnostic header/padding differs from original-based recipe')
    return package
