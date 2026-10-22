"""Audit r6 repacking in memory. Never execute reference scripts or write images."""
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tomllib
import zlib

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = Path('D:/Code/PortingiOSWithUniXNU')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def legacy_id(kernel, ramdisk, second):
    digest = hashlib.sha1()
    for part in (kernel, ramdisk, second, b''):
        digest.update(part)
        digest.update(struct.pack('<I', len(part)))
    return digest.digest().ljust(32, b'\0')


def main():
    template = REFERENCE / '.work/artifacts/nuwa-boot-r6/out/nuwa/boot/boot.img'
    data = template.read_bytes()
    if sha(data) != 'ed8c401576fcf5ed3cd5ca871457d7a38038d9f02bbf22875b24d5d301295acd':
        raise ValueError('Unexpected reference r6 image')
    ks, ka, rs, ra, ss, sa, tags, page, version = struct.unpack_from('<9I', data, 8)
    recovery_size, recovery_at, header_size = struct.unpack_from('<IQI', data, 1632)
    if (data[:8] != b'ANDROID!' or page != 4096 or version != 1 or ss
            or recovery_size or recovery_at or header_size != 1648):
        raise ValueError('Unsupported reference layout')
    ram_at = page + ((ks + page - 1) // page) * page
    end = ram_at + ((rs + page - 1) // page) * page
    if end != len(data):
        raise ValueError('Truncated or trailing reference data')
    kernel, ramdisk = data[page:page + ks], data[ram_at:ram_at + rs]
    dec = zlib.decompressobj(31)
    payload = dec.decompress(kernel)
    if not dec.eof or dec.unused_data[:4] != bytes.fromhex('d00dfeed'):
        raise ValueError('Invalid gzip/FDT boundary')
    dtb, shim, fd = dec.unused_data, payload[:112], payload[112:]
    if (shim[56:60] != b'ARM\x64' or fd[40:44] != b'_FVH'
            or struct.unpack_from('>I', dtb, 4)[0] != len(dtb)):
        raise ValueError('Invalid shim/FD/FDT input')
    rebuilt_kernel = gzip.compress(payload, compresslevel=9, mtime=0) + dtb
    if len(rebuilt_kernel) != ks:
        raise ValueError('This runtime changed compressed size; bounded diff unavailable')
    differences = [page + i for i, (a, b) in enumerate(zip(kernel, rebuilt_kernel)) if a != b]
    old_id, new_id = data[576:608], legacy_id(rebuilt_kernel, ramdisk, b'')
    id_diff = [576 + i for i, (a, b) in enumerate(zip(old_id, new_id)) if a != b]
    own_fd = (ROOT / 'out/firmware-ci/39764322744/nuwa-firmware-39764322744/build/FV/SILICIUM_UEFI.fd').read_bytes()
    if sha(own_fd) != 'a0bbb9645f4af2de66e4e29e1b5deaf508e95c41f33de4fd9f811ab03bde1c83':
        raise ValueError('Own FD differs from inspected input')
    replacement_kernel = gzip.compress(shim + own_fd, compresslevel=9, mtime=0) + dtb
    replacement_bytes = page + ((len(replacement_kernel) + page - 1) // page) * page + rs
    own = ROOT / 'scripts/ci/inspect-reference-boot.py'
    spec = importlib.util.spec_from_file_location('own_inspector', own)
    inspector = importlib.util.module_from_spec(spec); spec.loader.exec_module(inspector)
    files = dict(inspector.Fat32(ramdisk).files())
    config = tomllib.loads(files['/EFI/UniXNU/unixnu.toml'].decode())
    adt = inspector.adt_properties(files['/EFI/UniXNU/Payloads/kernel.macho.adt'])
    sources = [REFERENCE / 'scripts/build/repack-nuwa-boot.py', REFERENCE / 'docs/build-findings.md']
    result = dict(scope='Read-only template/source audit; rebuilt kernel bytes exist only in RAM',
                  source_inputs=[dict(path=str(p), sha256=sha(p.read_bytes())) for p in sources],
                  template=dict(path=str(template), bytes=len(data), sha256=sha(data),
                  version=version, page_bytes=page, kernel_bytes=ks, ramdisk_bytes=rs,
                  original_id_matches_aosp=old_id == legacy_id(kernel, ramdisk, b''),
                  recovery_dtbo_bytes=recovery_size, shim_sha256=sha(shim), fd_sha256=sha(fd), dtb_sha256=sha(dtb)),
                  same_fd_roundtrip=dict(bytes_preserved=len(data),
                  kernel_differing_absolute_offsets=differences, id_differing_absolute_offsets=id_diff,
                  original_gzip_os=kernel[9], rebuilt_gzip_os=rebuilt_kernel[9],
                  only_os_byte_changed_in_kernel=differences == [page + 9],
                  id_field_bytes=len(new_id), ramdisk_unchanged=True),
                  own_fd_memory_only_trial=dict(fd_sha256=sha(own_fd), kernel_bytes=len(replacement_kernel),
                  projected_image_bytes=replacement_bytes, old_template_bytes=len(data),
                  old_payload_would_be_retained=True, safe_to_execute=False),
                  payload_files=[dict(path=k, bytes=len(v), sha256=sha(v)) for k,v in files.items()],
                  boot_settings=config.get('boot', {}), adt=adt,
                  new_image_written=False, reference_script_executed=False)
    output = ROOT / 'reports/repack-reference-review.json'
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(template=result['template'], same_fd_roundtrip=result['same_fd_roundtrip'],
                         file_paths=list(files), boot_settings=result['boot_settings'], adt=adt), indent=2))


if __name__ == '__main__':
    main()
