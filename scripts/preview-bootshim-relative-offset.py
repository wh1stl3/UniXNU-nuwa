"""Prepare source-only text_offset correction and a conditional ABL model.

Does not assemble, change the firmware checkout or emit any image.
"""
import difflib
import hashlib
import json
from pathlib import Path
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]
FIRMWARE = Path('D:/Code/PortingiOS/nuwa/uefi-nuwa')
BASE = '5e4a8c814b89f62a4ba2bc145249314fed5db787'


def main():
    source = subprocess.check_output(['git', '-C', str(FIRMWARE), 'show',
                                      f'{BASE}:BootShim/BootShim.S']).decode().replace('\r\n', '\n')
    current = (FIRMWARE / 'BootShim/BootShim.S').read_text().replace('\r\n', '\n')
    if source != current:
        raise ValueError('Preserve changed firmware source; baseline differs')
    old = '  .quad FD_BASE         /* Text Offset */'
    new = '  .quad 0               /* Image load offset relative to the bootloader kernel base */'
    if source.count(old) != 1:
        raise ValueError('Unexpected BootShim header')
    patched = source.replace(old, new)
    if patched.count('ldr   x5, =FD_BASE') != source.count('ldr   x5, =FD_BASE'):
        raise ValueError('FD copy/entry destination changed')
    patch = ''.join(difflib.unified_diff(source.splitlines(True), patched.splitlines(True),
                                       fromfile='a/BootShim/BootShim.S', tofile='b/BootShim/BootShim.S'))
    destination = ROOT / 'patches/firmware-candidates/0006-bootshim-relative-text-offset.patch'
    destination.write_text(patch, encoding='utf-8', newline='\n')
    subprocess.run(['git', '-C', str(FIRMWARE), 'apply', '--check', str(destination)], check=True)
    factory = json.loads((ROOT / 'reports/loader-integration/audit.json').read_text())['factory']
    region, = [r for r in factory['rows'] if r['name'] == 'Kernel']
    base, end = region['base'], region['base'] + region['size']
    shim = ROOT / 'out/firmware-ci/39809636575/nuwa-firmware-39809636575'
    candidates = [p for p in shim.rglob('*') if p.is_file() and p.stat().st_size == 112
                  and hashlib.sha256(p.read_bytes()).hexdigest() ==
                  '9346a527441b242c69414fd7e3d6fa17813f281d562fef13d9ba8373d39007a9']
    if not candidates:
        raise ValueError('Pinned R-007 BootShim unavailable')
    raw = candidates[0].read_bytes()
    offset, size = struct.unpack_from('<QQ', raw, 8)
    if raw[56:60] != b'ARM\x64' or size != 0x300070 or offset != 0xa7100000:
        raise ValueError('Unexpected actual header')
    report = dict(result='Source patch applies; conditional arithmetic only, no compilation/execution',
        base_commit=BASE, source_sha256=hashlib.sha256(source.encode()).hexdigest(),
        patched_source_sha256=hashlib.sha256(patched.encode()).hexdigest(),
        patch=str(destination.relative_to(ROOT)).replace('\\', '/'),
        patch_sha256=hashlib.sha256(patch.encode()).hexdigest(),
        original_shim_sha256=hashlib.sha256(raw).hexdigest(),
        existing_image_size=hex(size), original_text_offset=hex(offset), proposed_text_offset='0x0',
        unchanged_fd_destination='0xa7100000',
        factory_source_sha256=factory['source_sha256'], factory_region=region,
        assumptions=['Both KernelBaseAddr/KernelSize GetVariable calls succeed',
                     'Normal platform branch (fde0 returns zero), raw ARM64, image_size nonzero',
                     'Variable values equal the Kernel descriptor in matching installed xbl_config',
                     'Ramdisk/page/DT deductions do not wrap the unsigned address arithmetic'],
        model=dict(kernel_base=hex(base), kernel_end=hex(end),
                   original_load=hex(base+offset), proposed_load=hex(base),
                   original_load_above_end=base+offset > end,
                   original_result='DTAddr below KernelEnd cannot exceed KernelLoadAddr; EFI_BUFFER_TOO_SMALL',
                   proposed_result='Removes this out-of-window load; does not prove copy/entry/SEC success'),
        fallback='Without both variables ABL uses its own base/offset path, ignoring this header field',
        runtime_values_observed=False, trial_error_observed=False, firmware_source_changed=False,
        image_generated=False, approval_required_for_build='R-008',
        protocol_source='https://docs.kernel.org/arch/arm64/booting.html')
    (ROOT / 'reports/abl-handoff/relative-offset-preview.json').write_text(
        json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
