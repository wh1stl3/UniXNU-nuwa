"""Official host vendor_boot packing + independent outer/FAT readback; never a device entry."""
import argparse
import struct
import subprocess
import sys
import tomllib
import zlib
from pathlib import Path
from types import SimpleNamespace

import owner_bnch as O
import owner_payload as P

FAT_SHA = '500a639be732722ad55f135d30b60803c23eb6cb17e16ccdb5e4b41203789797'
ADT_SHA = 'ff7d25234c1c6d3ed14e63e3e5489f26fdf65d1f7f649f20b8f6704f8b4ab736'
RECORD_SHA = 'b0dcd72a8115bb29ae44c2458bb22a587c50a8bad7705b06d2d2f952df996c0b'
STOCK_SHA = '5ad2a9dc751870fa3c367fa2833582147541f5b62b880dcbdf525003ad68cc23'
R4_SHA = '692cfcca51af81230fecbba15425cf598182fbe53abb362b6046dec0f24dc2e5'
CLI_PINS = {
    'unixnu': 'e15d5bc4745d80634d4c252848deead96ce426182cd825beb70ba1afffa2a1f5',
    'scripts/unixnu/cli.py': '1adafc2943a969f53216c4fbbc053992640d8053901264c7c77e3d48c49c8206',
    'scripts/unixnu/vendor_boot.py': '11e9cac117d46b7ad7b826395357a6d82713c2b65f3c1a23acf11f23f721500f',
}


def align(n):
    return (n + 4095) & -4096


def gpt_capacity(raw):
    h = raw[4096:8192]
    O.require(h[:8] == b'EFI PART', 'nuwa GPT signature/block size mismatch')
    size, crc = struct.unpack_from('<II', h, 12)
    O.require(92 <= size <= 4096, 'GPT header bounds')
    check = bytearray(h[:size])
    check[16:20] = bytes(4)
    O.require(zlib.crc32(check) == crc, 'GPT header CRC mismatch')
    lba = struct.unpack_from('<Q', h, 72)[0]
    count, stride, crc = struct.unpack_from('<III', h, 80)
    O.require(stride >= 128 and stride % 8 == 0 and 0 < count <= 4096, 'GPT entry geometry')
    entries = raw[lba * 4096:lba * 4096 + count * stride]
    O.require(len(entries) == count * stride and zlib.crc32(entries) == crc, 'GPT entries CRC/bounds')
    found = {}
    for at in range(0, len(entries), stride):
        name = entries[at + 56:at + 128].decode('utf-16-le').split('\0')[0]
        if name in ('vendor_boot_a', 'vendor_boot_b'):
            O.require(name not in found, 'Duplicate vendor_boot GPT name')
            first, last = struct.unpack_from('<QQ', entries, at + 32)
            O.require(first <= last, 'GPT reversed range')
            found[name] = {'first_lba': first, 'last_lba': last, 'lba_bytes': 4096,
                           'bytes': (last - first + 1) * 4096}
    O.require(set(found) == {'vendor_boot_a', 'vendor_boot_b'} and
              found['vendor_boot_b']['bytes'] == 100663296, 'Unexpected nuwa vendor_boot capacity')
    return found


def parse(raw):
    O.require(len(raw) >= 8192 and raw[:8] == b'VNDRBOOT', 'vendor_boot magic/size')
    version, page = struct.unpack_from('<II', raw, 8)
    O.require((version, page) == (4, 4096), 'Only fixed v4/page4096 layout supported')
    address, ramdisk_size = struct.unpack_from('<II', raw, 20)
    header_size, dtb_size = struct.unpack_from('<II', raw, 2096)
    table_size, count, entry, bootconfig_size = struct.unpack_from('<IIII', raw, 2112)
    O.require(header_size == 2128 and entry == 108 and count == 1 and table_size == count * entry,
              'Unexpected fixed stock header/table geometry')
    dtb_start = align(page + ramdisk_size)
    table_start = align(dtb_start + dtb_size)
    config_start = align(table_start + table_size)
    vbmeta_start = align(config_start + bootconfig_size)
    footer = raw[-64:]
    O.require(footer[:4] == b'AVBf', 'Expected stock AVB footer missing')
    original_size, actual_vbmeta, vbmeta_size = struct.unpack_from('>QQQ', footer, 12)
    O.require(actual_vbmeta == vbmeta_start and vbmeta_start + vbmeta_size <= len(raw) - 64,
              'vendor_boot vbmeta/footer bounds')
    return {'header': raw[:page], 'ramdisk': raw[page:page + ramdisk_size], 'address': address,
            'dtb': raw[dtb_start:dtb_start + dtb_size], 'table': raw[table_start:table_start + table_size],
            'bootconfig': raw[config_start:config_start + bootconfig_size],
            'vbmeta': raw[vbmeta_start:vbmeta_start + vbmeta_size], 'footer': footer,
            'offsets': {'dtb': dtb_start, 'table': table_start, 'bootconfig': config_start, 'vbmeta': vbmeta_start},
            'footer_original_size': original_size, 'partition_bytes': len(raw), 'table_count': count}


def compare(stock, image, fat, capacity):
    before, after = parse(stock), parse(image)
    O.require(len(image) == capacity == len(stock), 'Outer file does not match captured partition capacity')
    O.require(after['ramdisk'] == fat, 'Actual vendor ramdisk is not the frozen verifier FAT')
    O.require(after['address'] == before['address'] == 0x01000000, 'Stock ramdisk address changed')
    header = bytearray(after['header'])
    header[20:28] = before['header'][20:28]
    O.require(bytes(header) == before['header'], 'Header field outside ramdisk size/address changed')
    O.require(struct.unpack_from('<I', after['header'], 24)[0] == len(fat), 'Wrong ramdisk size field')
    for key in ('dtb', 'bootconfig', 'vbmeta'):
        O.require(after[key] == before[key], 'Stock part changed: ' + key)
    table = bytearray(after['table'])
    O.require(struct.unpack_from('<II', table) == (len(fat), 0), 'v4 table size/offset mismatch')
    table[:8] = before['table'][:8]
    O.require(bytes(table) == before['table'], 'v4 table type/name/board_id changed')
    footer = bytearray(after['footer'])
    O.require(struct.unpack_from('>QQQ', footer, 12) ==
              (after['offsets']['vbmeta'], after['offsets']['vbmeta'], len(before['vbmeta'])),
              'Footer retarget fields mismatch')
    footer[12:36] = before['footer'][12:36]
    O.require(bytes(footer) == before['footer'], 'AVB footer outside retarget fields changed')
    regions = [(0, 4096), (4096, 4096 + len(fat)),
               *[(after['offsets'][k], after['offsets'][k] + len(after[k]))
                 for k in ('dtb', 'table', 'bootconfig', 'vbmeta')], (len(image) - 64, len(image))]
    O.require(all(a[1] <= b[0] and not any(image[a[1]:b[0]]) for a, b in zip(regions, regions[1:])),
              'Unexpected overlap/nonzero outer alignment or partition padding')
    return {'preserved_sha256': {k: O.sha(after[k]) for k in ('dtb', 'bootconfig', 'vbmeta')},
            'stock_offsets': before['offsets'], 'outer_offsets': after['offsets'],
            'ramdisk_address': after['address'], 'table_count': after['table_count'],
            'header_outside_ramdisk_fields_equal': True, 'table_outside_size_offset_equal': True,
            'footer_outside_retarget_equal': True, 'zero_padding_checked': True,
            'avb_authentication_claimed': False}


def check_base(base):
    base, _ = P.sources(base)
    for name, pin in CLI_PINS.items():
        raw = (base / name).read_bytes()
        O.require(O.sha(raw) == pin and raw.replace(b'\r\n', b'\n') ==
                  O.git(base, 'show', O.REVISION + ':' + name).replace(b'\r\n', b'\n'),
                  'Official vendor_boot entry/source drift: ' + name)
    return base


def build(base, candidate, stock_path, loader, layout_path, output):
    base = check_base(base)
    candidate = Path(candidate).resolve(strict=True)
    O.require(candidate == (O.ROOT / 'out/owner-pmap-ret-package-verifier-final-20261111').resolve(),
              'Only parent-selected independent verifier candidate may be packed')
    source = O.read_json(candidate / 'payload-record.json')
    fat_path = Path(source['payload_path']).resolve(strict=True)
    O.require(fat_path.is_relative_to(candidate), 'FAT outside selected candidate')
    fat = fat_path.read_bytes()
    O.require(len(fat) == 67108864 and O.sha(fat) == source['payload_sha256'] == FAT_SHA,
              'Selected verifier FAT pin mismatch')
    kernel = (candidate / 'inputs/kernel.macho').read_bytes()
    artifact = P.qualify_prepared(kernel, source['prepared_kernel_sha256'], P.DIAGNOSTIC_PROFILE)
    O.require(source['profile'] == P.DIAGNOSTIC_PROFILE and source['diagnostic_only'], 'Wrong selected profile')
    adt = (candidate / 'adt-generation/final.adt').read_bytes()
    record_path = candidate / 'adt-generation/record.json'
    O.require(O.sha(adt) == source['adt_sha256'] == ADT_SHA and
              O.sha(record_path.read_bytes()) == source['owner_record_sha256'] == RECORD_SHA, 'Selected ADT/record pin mismatch')
    board = O.read_json(candidate / 'runtime-board.json')
    kwargs = O.read_json(candidate / 'adt-generation/keywords.json')
    O.load_record(record_path, O.binding((candidate / 'adt-generation/input.dtb').read_bytes(), board, kwargs, artifact))
    layout = O.read_json(layout_path)
    O.require(Path(layout['candidate']).resolve() == candidate and layout['kernel_sha256'] == artifact['kernel_sha256']
              and layout['adt_sha256'] == ADT_SHA and layout['r4_image_sha256'] == R4_SHA
              and layout['relative_ranges_disjoint'], 'Selected independent layout binding mismatch')
    loader_raw = Path(loader).read_bytes()
    O.require(len(loader_raw) == 1495040 and O.sha(loader_raw) == R4_SHA, 'Fixed independent r4 boot pin mismatch')
    stock_path = Path(stock_path).resolve(strict=True)
    O.require(stock_path == (O.ROOT / '.cache/stock/vendor_boot_b.img').resolve(), 'Wrong nuwa stock path')
    stock = stock_path.read_bytes()
    O.require(O.sha(stock) == STOCK_SHA == O.read_json(O.ROOT / '.cache/stock/vendor_boot.json')['stock_sha256']
              and O.sha((O.ROOT / '.cache/stock/vendor_boot_a.img').read_bytes()) == STOCK_SHA,
              'Nuwa historical stock A/B source hash mismatch')
    partitions = gpt_capacity((O.ROOT.parent / '.cache/device-evidence/20261107-recovery/gpt-sde.bin').read_bytes())
    O.require(len(stock) == partitions['vendor_boot_b']['bytes'], 'Stock/GPT capacity mismatch')
    parse(stock)
    out = P.reserve(output)
    try:
        (out / 'build-input.toml').write_text('[build]\n')
        destination = out / 'vendor_boot.img'
        O.require(not destination.exists() and not (out / 'vendor_boot.json').exists(), 'Outer output already exists')
        soc = P.verify_soc(O.ROOT.parent / 'UniXNU-sm8550-common')
        command = [sys.executable, '-B', str(base / 'unixnu'), 'vendor_boot', '--stock', str(stock_path),
                   '--ramdisk', str(fat_path), '-o', str(destination), '-D', str(O.ROOT),
                   '--out', str(out / 'context'), '--config', str(out / 'build-input.toml'),
                   '--local-module', 'soc:sm8550=' + str(soc), '-j', '1']
        result = subprocess.run(command, cwd=base, capture_output=True, text=True)
        O.write_json(out / 'official-command.json', {'command': command, 'cwd': str(base), 'exit': result.returncode,
                                                    'stdout': result.stdout, 'stderr': result.stderr})
        O.require(result.returncode == 0, 'Official vendor_boot failed (see official-command.json)')
        image = destination.read_bytes()
        differences = compare(stock, image, fat, partitions['vendor_boot_b']['bytes'])
        extracted_fat = out / 'actual-vendor-ramdisk.img'
        extracted_fat.write_bytes(parse(image)['ramdisk'])
        extraction = out / 'extracted'
        extraction.mkdir()
        P.capture(['mcopy', '-s', '-i', extracted_fat, '::/EFI', extraction], out / 'extract-command.json')
        expected = {'Payloads/kernel.macho': kernel, 'Payloads/kernel.macho.adt': adt,
                    'Payloads/kernel.macho.trustcache': (candidate / 'inputs/kernel.macho.trustcache').read_bytes(),
                    'unixnu.toml': (candidate / 'extracted/EFI/UniXNU/unixnu.toml').read_bytes()}
        O.require(board['payload']['kernel_args'] == P.DIAGNOSTIC_ARGS, 'Selected boot args changed')
        hashes = P.verify_extracted(extraction, expected, adt, record_path, SimpleNamespace(board=board),
                                    ' '.join(P.DIAGNOSTIC_ARGS), artifact)
        O.require(hashes == source['fat_hashes'] and set(hashes) == set(expected), 'Outer FAT content binding mismatch')
        config = tomllib.loads(expected['unixnu.toml'].decode())
        O.require(len(config['entry']) == 4 and sum(e['type'] == 'xnu' for e in config['entry']) == 1
                  and sum(e['type'] == 'action' for e in config['entry']) == 3
                  and config['boot']['default'] == 'xnu', 'Expected one XNU + three actions/default=xnu')
        # Self-check refusal paths against actual output without rebuilding/mutating any image file.
        negatives = []
        for name, offset in [('header', 16), ('ramdisk', 4096)]:
            changed = bytearray(image)
            changed[offset] ^= 1
            try:
                compare(stock, bytes(changed), fat, len(stock))
            except ValueError:
                negatives.append(name)
            else:
                raise ValueError('Outer tamper accepted: ' + name)
        check_base(base)
        O.require(stock_path.read_bytes() == stock and fat_path.read_bytes() == fat and
                  Path(loader).read_bytes() == loader_raw, 'Frozen source input changed during packing')
        manifest = {'status': 'self-checked', 'official_exit': result.returncode, 'readback_complete': True,
            'base_revision': O.REVISION, 'selected_candidate': str(candidate), 'profile': P.DIAGNOSTIC_PROFILE,
            'stock_sha256': STOCK_SHA, 'partition_evidence': partitions, 'vendor_boot_sha256': O.sha(image),
            'vendor_boot_bytes': len(image), 'vendor_ramdisk_sha256': O.sha(extracted_fat.read_bytes()),
            'r4_boot_sha256': R4_SHA, 'kernel_sha256': artifact['kernel_sha256'], 'adt_sha256': ADT_SHA,
            'owner_record_sha256': RECORD_SHA, 'selected_layout_sha256': O.sha(Path(layout_path).read_bytes()),
            'outer_comparison': differences, 'fat_hashes': hashes, 'tamper_negatives_rejected': negatives,
            'entry_counts': {'xnu': 1, 'action': 3}, 'default_entry': 'xnu',
            'runtime_volume_selection_proven': False, 'scope': 'Config prefers startup volume else first valid volume; FAT internals do not establish runtime selection',
            'range_static_review': 'Not verified by this packer; see independent range evidence and parent acceptance records',
            'remaining_resource_conditions': ['GOP', 'EFI memory map'], 'device_release': False,
            'authentication': 'NOT REACHED', 'payload_generated': False, 'new_bnch_drawn': False}
        O.write_json(out / 'outer-record.json', manifest)
        return manifest
    except Exception as error:
        O.write_json(out / 'failure.json', {'status': 'failed', 'failure_type': type(error).__name__, 'device_release': False})
        raise


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('base', 'candidate', 'stock', 'loader', 'layout', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    result = build(a.base, a.candidate, a.stock, a.loader, a.layout, a.output)
    print('self-checked outer vendor_boot:', result['vendor_boot_sha256'], '; no device authorization/release')


if __name__ == '__main__':
    main()
