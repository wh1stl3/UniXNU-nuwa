"""R-009 A: inspect a diagnostic FD and create only the approved v4 container."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]
STOCK = Path('D:/Code/PortingiOS/nuwa/backups/recovery-20261020T121245314787Z/boot_a.img')
STOCK_SHA = 'ef558db2a4fb021259d7af47a2398d7e56476d759162e7819959cd701a11ff31'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('run_id', type=int)
    cli.add_argument('--profile', choices=('pil-no-auto', 'dxe-allocation', 'factory-heap', 'sec-handoff', 'constructor-trace', 'mmu-branches', 'hob-query'), default='pil-no-auto')
    args = cli.parse_args()
    approval = {'pil-no-auto': 'R-009 A', 'dxe-allocation': 'R-010 A', 'factory-heap': 'R-011 A',
                'sec-handoff': 'SEC-HANDOFF-OFFLINE', 'constructor-trace': 'CONSTRUCTOR-TRACE-OFFLINE', 'mmu-branches': 'MMU-BRANCHES-OFFLINE', 'hob-query': 'HOB-QUERY-OFFLINE'}[args.profile]
    artifact = ROOT / f'out/firmware-ci/{args.run_id}/nuwa-firmware-{args.run_id}'
    output = ROOT / f'out/trial-boot/{args.profile}-{args.run_id}'
    report = ROOT / f'reports/{args.profile}/{args.run_id}'
    if output.exists() or (report / 'package.json').exists():
        raise ValueError('Refusing to overwrite an existing trial package')
    profile = json.loads((ROOT / f'config/firmware-{args.profile}-profile.json').read_text())
    inputs = json.loads((artifact / 'inputs.json').read_text())
    if (inputs['recipe'] != profile['recipe'] or inputs['profile'] != args.profile
            or inputs['run_id'] != str(args.run_id)):
        raise ValueError('Runner inputs differ from the approved diagnostic profile')
    spec = importlib.util.spec_from_file_location('firmware_inspector', ROOT / 'scripts/ci/inspect-firmware-candidate.py')
    inspector = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(inspector)
    inspection = inspector.inspect(artifact, 'NuwaBootMemoryDxe', require_sec_trace=True, require_no_auto_abl=True,
                                   require_allocation_trace=args.profile in ('dxe-allocation', 'factory-heap', 'sec-handoff', 'constructor-trace', 'mmu-branches', 'hob-query'),
                                   allocation_profile=args.profile if args.profile != 'pil-no-auto' else 'dxe-allocation')
    original = STOCK.read_bytes()
    if sha(original) != STOCK_SHA:
        raise ValueError('Pinned original recovery boot changed')
    header = bytearray(original[:4096])
    if (header[:8] != b'ANDROID!' or struct.unpack_from('<I', header, 40)[0] != 4
            or struct.unpack_from('<I', header, 20)[0] != 1584
            or struct.unpack_from('<I', header, 12)[0] != 0
            or struct.unpack_from('<I', header, 1580)[0] != 0):
        raise ValueError('Unsupported original v4 header/ramdisk/signature')
    fd = (artifact / 'build/FV/SILICIUM_UEFI.fd').read_bytes()
    shim = (artifact / 'shim/shim.bin').read_bytes()
    if sha(shim) != '8a3b54765c895a0366539130fdf6e4e4a01e364fe7de067a38d0193606f9d462':
        raise ValueError('Expected unchanged R-008 corrected shim')
    payload = shim + fd
    if (sha(fd) != inspection['fd']['sha256'] or sha(shim) != inspection['shim']['sha256']
            or shim[56:60] != b'ARM\x64' or struct.unpack_from('<Q', shim, 16)[0] != len(payload)):
        raise ValueError('Inspected FD/shim differs from package input')
    struct.pack_into('<I', header, 8, len(payload))
    if header[:8] != original[:8] or header[12:] != original[12:4096]:
        raise ValueError('Only kernel_size may change in the original v4 header')
    image = bytes(header) + payload + b'\0' * (-len(payload) % 4096)
    if (struct.unpack_from('<I', image, 8)[0] != len(payload)
            or image[4096:4096 + len(shim)] != shim
            or image[4096 + len(shim):4096 + len(payload)] != fd
            or len(image) != 4096 + ((len(payload) + 4095) // 4096) * 4096):
        raise ValueError('Independent container bounds/content check failed')
    output.mkdir(parents=True)
    path = output / f'boot-{args.profile}-v4.img'
    path.write_bytes(image)
    if sha(path.read_bytes()) != sha(image):
        raise ValueError('Written package hash mismatch')
    metadata = {'approval': approval, 'scope': args.profile + ' firmware-only temporary v4 container',
                'allocation_trace': inspection['allocation_trace'], 'factory_heap': inspection['factory_heap'],
                'device_commit': inputs['device_commit'],
                'diagnostic_patch_sha256': next((p['sha256'] for p in profile['candidate']['patches']
                    if p['path'] == 'patches/firmware-candidates/0008-nuwa-dxe-allocation-trace.patch'), None),
                'run_id': args.run_id, 'firmware_commit': profile['recipe']['sources']['firmware']['commit'],
                'image_path': path.relative_to(ROOT).as_posix(), 'image_bytes': len(image), 'image_sha256': sha(image),
                'original_boot_sha256': STOCK_SHA, 'fd_sha256': sha(fd), 'shim_sha256': sha(shim),
                'shim_text_offset': inspection['shim']['text_offset'],
                'pil_config_sha256': inspection['pil_no_auto']['config']['sha256'],
                'pil_auto_entries': inspection['pil_no_auto']['config']['auto_entries'],
                'pil_driver_sha256': inspection['pil_no_auto']['retained_driver']['sha256'],
                'header_version': 4, 'page_bytes': 4096, 'kernel_bytes': len(payload),
                'changed_header_fields': ['kernel_size'], 'ramdisk_bytes': 0, 'signature_bytes': 0,
                'appended_dtb': False, 'fat_included': False, 'xnu_included': False,
                'dt_source': 'Installed nuwa vendor_boot via ABL; actual candidate handoff unverified',
                'candidate_device_executed': False, 'recovery_required': True}
    if args.profile in ('sec-handoff', 'constructor-trace', 'mmu-branches', 'hob-query'):
        metadata.update(handoff_markers=inspection['sec_entry_hob_producer']['handoff_markers'],
                        ready_to_execute=False,
                        authorization='User requested offline preparation and evening joint trial; no device action in this session',
                        execution_gate='Refresh identity/recovery/capture evidence and notify user in evening; strict candidate validation alone does not permit launch')
    if args.profile in ('constructor-trace', 'mmu-branches', 'hob-query'):
        metadata.update(constructor_markers=inspection['sec_entry_hob_producer']['constructor_markers'],
                        constructor_patch_sha256=next(p['sha256'] for p in profile['candidate']['patches'] if p['path'].endswith('0011-mu-constructor-trace.patch')),
                        execution_gate='Offline package only; integrate strict constructor profile gate and refresh capture/recovery evidence before a new trial')
    if args.profile in ('mmu-branches', 'hob-query'):
        metadata.update(mmu_markers=inspection['sec_entry_hob_producer']['mmu_markers'],
                        mmu_patch_sha256=next(p['sha256'] for p in profile['candidate']['patches'] if p['path'].endswith('0012-mmu-constructor-branches.patch')),
                        authorization='Offline build/package authorized; notify user before device testing',
                        execution_gate='Notify user and refresh identity, capture and recovery evidence before launch')
    if args.profile == 'hob-query':
        metadata.update(hob_markers=inspection['sec_entry_hob_producer']['hob_markers'],
                        hob_patch_sha256=profile['candidate']['patches'][-1]['sha256'])
    report.mkdir(parents=True, exist_ok=True)
    (report / 'artifact-inspection.json').write_text(json.dumps(inspection, indent=2) + '\n', encoding='utf-8')
    for destination in (report / 'package.json', output / 'package.json'):
        destination.write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
    (output / 'SHA256SUMS').write_text(sha(image) + '  ' + path.name + '\n', encoding='utf-8')
    print(json.dumps(metadata, indent=2))


if __name__ == '__main__':
    main()
