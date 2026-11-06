"""Read an existing reference Android boot/FAT image; write metadata only.

Never extract, assemble, patch or execute firmware. Platform seeds are omitted.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import tomllib
import zlib

ROOT = Path(__file__).resolve().parents[2]


def sha(data):
    return hashlib.sha256(data).hexdigest()


class Fat32:
    def __init__(self, data):
        self.data = data
        self.bps, self.spc, self.reserved, self.fats, roots = struct.unpack_from('<HBHBH', data, 11)
        self.sectors = struct.unpack_from('<I', data, 32)[0]
        self.fat_sectors = struct.unpack_from('<I', data, 36)[0]
        self.root = struct.unpack_from('<I', data, 44)[0]
        if (data[510:512] != b'\x55\xaa' or roots or self.bps != 512
                or not self.spc or self.spc & (self.spc - 1)
                or self.sectors * self.bps != len(data)):
            raise ValueError('Unsupported or inconsistent FAT32 BPB')
        self.start = (self.reserved + self.fats * self.fat_sectors) * self.bps
        self.cluster_bytes = self.bps * self.spc
        self.limit = (len(data) - self.start) // self.cluster_bytes + 2

    def chain(self, cluster):
        chunks, seen = [], set()
        while cluster < 0x0ffffff8:
            if cluster < 2 or cluster >= self.limit or cluster in seen:
                raise ValueError('Invalid/cyclic FAT chain')
            seen.add(cluster)
            at = self.start + (cluster - 2) * self.cluster_bytes
            chunks.append(self.data[at:at + self.cluster_bytes])
            fat_at = self.reserved * self.bps + cluster * 4
            if fat_at + 4 > (self.reserved + self.fat_sectors) * self.bps:
                raise ValueError('FAT entry out of bounds')
            cluster = struct.unpack_from('<I', self.data, fat_at)[0] & 0x0fffffff
        return b''.join(chunks)

    def files(self, cluster=None, prefix='', visited=None):
        cluster = self.root if cluster is None else cluster
        visited = set() if visited is None else visited
        if cluster in visited:
            raise ValueError('Directory cycle')
        visited.add(cluster)
        data, lfn = self.chain(cluster), {}
        for at in range(0, len(data), 32):
            item = data[at:at + 32]
            if item[0] == 0:
                break
            if item[0] == 0xe5:
                lfn = {}
                continue
            attr = item[11]
            if attr == 15:
                if item[0] & 0x40:
                    lfn = {}
                lfn[item[0] & 31] = item[1:11] + item[14:26] + item[28:32]
                continue
            short = item[:8].decode('ascii').rstrip()
            ext = item[8:11].decode('ascii').rstrip()
            name = short + ('.' + ext if ext else '')
            if lfn:
                name = b''.join(lfn[k] for k in sorted(lfn)).decode('utf-16-le').split('\x00')[0].rstrip('\uffff')
            lfn = {}
            if name in ('.', '..') or attr & 8:
                continue
            first = (struct.unpack_from('<H', item, 20)[0] << 16) | struct.unpack_from('<H', item, 26)[0]
            size = struct.unpack_from('<I', item, 28)[0]
            path = prefix + '/' + name
            if attr & 16:
                yield from self.files(first, path, visited)
            else:
                content = self.chain(first) if size else b''
                if len(content) < size:
                    raise ValueError('Truncated file')
                yield path, content[:size]


def adt_properties(data):
    result = {}

    def node(at, parent, depth=0):
        if depth > 64 or at + 8 > len(data):
            raise ValueError('Invalid ADT node')
        count, children = struct.unpack_from('<II', data, at)
        at += 8
        props = {}
        for _ in range(count):
            if at + 36 > len(data):
                raise ValueError('Truncated ADT property')
            key = data[at:at + 32].split(b'\0')[0].decode('ascii')
            length = struct.unpack_from('<I', data, at + 32)[0] & 0x7fffffff
            at += 36
            if at + length > len(data):
                raise ValueError('Truncated ADT value')
            props[key] = data[at:at + length]
            at += (length + 3) & ~3
        name = props.get('name', b'').split(b'\0')[0].decode('ascii')
        path = (parent.rstrip('/') + '/' + name) if parent else '/'
        # Deliberately exclude unique-chip-id, serials and random-seed values.
        allowed = {'dram-base', 'dram-size', 'darwinboot-memory-size',
                   'certificate-production-status', 'certificate-security-mode',
                   'effective-production-status-ap', 'effective-security-mode-sep'}
        result[path] = {key: {'bytes': len(value), 'integer_le': int.from_bytes(value, 'little')}
                        for key, value in props.items() if key in allowed}
        result[path]['property_names'] = sorted(props)
        for _ in range(children):
            at = node(at, path, depth + 1)
        return at

    used = node(0, '')
    return {'nodes': result, 'parsed_bytes': used, 'trailing_bytes': len(data) - used}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--reference', type=Path, required=True, help='Existing nuwa-boot artifact directory')
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / 'reports'):
        raise ValueError('Metadata must stay under this repository reports/')
    ref = args.reference.resolve()
    boot = ref / 'out/nuwa/boot/boot.img'
    data = boot.read_bytes()
    if data[:8] != b'ANDROID!':
        raise ValueError('Expected Android boot container')
    ks, ka, rs, ra, ss, sa, tags, page, version, os_version = struct.unpack_from('<10I', data, 8)
    if page != 4096 or version != 1 or ss:
        raise ValueError('Inspector only supports this v1/4096/no-second reference')
    kernel = data[page:page + ks]
    inflate = zlib.decompressobj(16 + zlib.MAX_WBITS)
    combined = inflate.decompress(kernel)
    if not inflate.eof:
        raise ValueError('Truncated gzip')
    dtb = inflate.unused_data
    if dtb[:4] != bytes.fromhex('d00dfeed') or struct.unpack_from('>I', dtb, 4)[0] != len(dtb):
        raise ValueError('Invalid appended FDT')
    fd = (ref / 'uefi/Build/nuwaPkg/DEBUG_CLANGPDB/FV/SILICIUM_UEFI.fd').read_bytes()
    if not combined.endswith(fd):
        raise ValueError('Embedded firmware differs from artifact')
    shim = combined[:-len(fd)]
    text_offset, image_size = struct.unpack_from('<QQ', shim, 8)
    start = page * (1 + (ks + page - 1) // page)
    payload = data[start:start + rs]
    if len(payload) != rs:
        raise ValueError('Truncated ramdisk')
    files = dict(Fat32(payload).files())
    config = tomllib.loads(files['/EFI/UniXNU/unixnu.toml'].decode('utf-8'))
    km = files['/EFI/UniXNU/Payloads/kernel.macho']
    adt = files['/EFI/UniXNU/Payloads/kernel.macho.adt']
    boot_report = json.loads((ref / 'out/nuwa/boot/boot.json').read_text())
    payload_report = json.loads((ref / 'out/nuwa/payload/payload.json').read_text())
    log = (ref / 'uefi/build.log').read_text(errors='replace')
    report = {
        'scope': 'Read-only container/content checks; no ABL, UEFI, kernel or hardware execution',
        'boot_path': str(boot), 'boot_bytes': len(data), 'boot_sha256': sha(data),
        'header': {'version': version, 'page_bytes': page, 'kernel_bytes': ks,
                   'ramdisk_bytes': rs, 'kernel_address': hex(ka), 'ramdisk_address': hex(ra),
                   'tags_address': hex(tags), 'os_version_raw': os_version},
        'gzip': {'inflated_bytes': len(combined), 'shim_bytes': len(shim), 'fd_bytes': len(fd),
                 'fd_sha256': sha(fd), 'fd_matches_artifact': True},
        'shim': {'text_offset': hex(text_offset), 'image_size': image_size,
                 'covers_shim_and_fd': image_size == len(combined), 'arm64_magic': shim[56:60].hex()},
        'appended_dtb': {'bytes': len(dtb), 'sha256': sha(dtb)},
        'payload': {'bytes': len(payload), 'sha256': sha(payload),
                    'files': [{'path': p, 'bytes': len(b), 'sha256': sha(b)} for p, b in sorted(files.items())],
                    'config': config, 'adt': adt_properties(adt)},
        'report_hash_matches': {'boot': sha(data) == boot_report['image_sha256'],
                                'fd': sha(fd) == boot_report['fd_sha256'],
                                'payload': sha(payload) == payload_report['payload_sha256'],
                                'kernel': sha(km) == payload_report['payload_kernel_sha256'],
                                'adt': sha(adt) == payload_report['adt_sha256']},
        'named_build_log_mentions': {name: log.count(name) for name in ('DarwinBoot', 'UniXNUDxe', 'UniXNUPkg')},
        'efi_files_in_payload': [p for p in files if p.lower().endswith('.efi')],
        'device_verified': False,
    }
    if not all(report['report_hash_matches'].values()):
        raise ValueError('Reference reports and actual bytes disagree')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('boot_bytes', 'boot_sha256', 'report_hash_matches',
                                            'named_build_log_mentions', 'efi_files_in_payload')}))


if __name__ == '__main__':
    main()
