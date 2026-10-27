"""Inspect fixed source and actual R-011 FD for the file-discovery chain.

Reads local artifacts and pinned upstream text in RAM; no device commands,
firmware generation, repository mutation, or upstream source copies.
"""
from concurrent.futures import ThreadPoolExecutor
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import struct
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports/system-volume-audit/discovery-chain.json'
GIT = 'C:/Program Files/Git/cmd/git.exe'
FW = Path('D:/Code/PortingiOS/nuwa/uefi-nuwa')
BASE = Path('D:/Code/PortingiOSLegacy/common/sources/UniXNU')
FW_PIN = '1ccf760d667b9eec6dd3491c90cc04ebb7c58340'
BASE_PIN = '75bc13dd34dc4e403826793739e316a264ce00dd'
MU_PIN = 'cfb93724a06ff86ff5ba971413368a7809ee42a5'
ARTIFACT = ROOT / 'out/firmware-ci/39835052901/nuwa-firmware-39835052901'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    if OUT.exists():
        raise ValueError('Fresh evidence destination required')
    records = []
    text = {}

    def local(root, pin, path, terms):
        raw = subprocess.check_output([GIT, '-c', f'safe.directory={root}', '-C', str(root),
                                       'show', pin + ':' + path])
        value = raw.decode()
        records.append(dict(repository='wh1stl3/uefi-nuwa' if root == FW else 'UniXNU/UniXNU',
                            commit=pin, path=path, sha256=sha(raw),
                            matching_lines={term: [i + 1 for i, line in enumerate(value.splitlines()) if term in line]
                                            for term in terms}))
        text[path] = value
        return value

    entry = local(BASE, BASE_PIN, 'package/UniXNUPkg/Application/UniXNU/UniXNU.c',
                  ['mFirmwareMarker', 'Host = UniXNUHostFirmware'])
    registrar = local(BASE, BASE_PIN, 'package/UniXNUPkg/Driver/UniXNUDxe/UniXNUDxe.c',
                      ['mFirmwareMarker', 'CopyMem (P, mFirmwareMarker'])
    main_source = local(BASE, BASE_PIN, 'package/UniXNUPkg/Library/UniXNULib/Main.c',
                        ['UniXNUHostFirmware', 'UniXNUConnectAll ();', 'UniXNUConfigLoad'])
    inject = local(BASE, BASE_PIN, 'package/UniXNUPkg/Library/UniXNULib/Inject.c',
                   ['UniXNUConnectAll', 'ConnectController', 'NeedConnect && Config->ConnectAll'])
    local(BASE, BASE_PIN, 'package/UniXNUPkg/Library/UniXNULib/Config.c',
          ['TryVolume', 'gEfiSimpleFileSystemProtocolGuid', 'TomlParse', 'config: loaded'])
    publisher = local(FW, FW_PIN, 'Platforms/Xiaomi/nuwaPkg/Drivers/NuwaBootMemoryDxe/NuwaBootMemoryDxe.c',
                      ['RAM_BLOCK_SIZE', 'InstallMultipleProtocolInterfaces', 'LogicalPartition', 'AllocatePages'])
    local(FW, FW_PIN, 'Platforms/Xiaomi/nuwaPkg/Drivers/NuwaBootMemoryDxe/NuwaBootMemoryDxe.inf', ['[Depex]', 'TRUE'])
    fdf = local(FW, FW_PIN, 'Platforms/Xiaomi/nuwaPkg/nuwa.fdf', ['APRIORI.inc', 'NuwaBootMemoryDxe.inf'])
    apriori = local(FW, FW_PIN, 'Platforms/Xiaomi/nuwaPkg/Include/APRIORI.inc',
                    ['DiskIoDxe.inf', 'PartitionDxe.inf', 'Fat.inf', 'EnglishDxe.inf'])
    map_source = local(FW, FW_PIN, 'Platforms/Xiaomi/nuwaPkg/Library/MemoryMapLib/MemoryMapLib.c', ['"Kernel"'])
    local(FW, FW_PIN, 'Silicon/Silicium/SiliciumPkg/Library/MemoryInitPeiLib/MemoryInitPei.c', ['BuildMemoryAllocationHob'])
    local(FW, FW_PIN, 'Silicon/Silicium/SiliciumPkg/Drivers/RamManagerDxe/RamManager.c',
          ['GetEfiMemoryMap', 'ParseMemoryRange', 'RegionEnd > CurrentRangeBase'])
    paths = ['FatPkg/EnhancedFatDxe/' + n for n in ('Fat.inf', 'Fat.c', 'Init.c')]
    paths += ['MdeModulePkg/Universal/Disk/' + n for n in (
        'DiskIoDxe/DiskIoDxe.inf', 'DiskIoDxe/DiskIo.c', 'PartitionDxe/PartitionDxe.inf',
        'UnicodeCollation/EnglishDxe/EnglishDxe.inf')]
    paths += ['MdePkg/Include/Pi/PiHob.h', 'MdePkg/Include/Uefi/UefiMultiPhase.h']

    def remote(path):
        url = f'https://raw.githubusercontent.com/microsoft/mu_basecore/{MU_PIN}/{path}'
        with urllib.request.urlopen(url, timeout=20) as response:
            raw = response.read()
        value = raw.decode()
        terms = ['FILE_GUID', 'gEfiBlockIoProtocolGuid', 'gEfiDiskIoProtocolGuid',
                 'gEfiSimpleFileSystemProtocolGuid', 'FatAllocateVolume', 'LogicalPartition']
        return path, value, dict(repository='microsoft/mu_basecore', commit=MU_PIN, path=path,
                                 sha256=sha(raw), url=url, license='BSD-2-Clause-Patent',
                                 matching_lines={term: [i + 1 for i, line in enumerate(value.splitlines()) if term in line]
                                                 for term in terms})

    with ThreadPoolExecutor(max_workers=4) as pool:
        for path, value, record in pool.map(remote, paths):
            text[path] = value
            records.append(record)
    if not re.search(r'typedef\s+UINT32\s+EFI_RESOURCE_ATTRIBUTE_TYPE\s*;', text['MdePkg/Include/Pi/PiHob.h']):
        raise ValueError('Unexpected resource attribute width')
    spec = importlib.util.spec_from_file_location('discovery_fd_reader', ROOT / 'scripts/ci/inspect-firmware-candidate.py')
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    captured_sec = []
    old_heap = reader.heap_descriptors

    def capture_sec(data):
        captured_sec.append(data)
        return old_heap(data)

    reader.heap_descriptors = capture_sec

    class Actual(reader.Firmware):
        def sections(self, data, owner, depth):
            at = 0
            while at + 4 <= len(data):
                size, kind = int.from_bytes(data[at:at + 3], 'little'), data[at + 3]
                header = 4
                if size == 0xffffff:
                    size, header = struct.unpack_from('<I', data, at + 4)[0], 8
                if not header <= size <= len(data) - at:
                    raise ValueError('Invalid section')
                body = data[at + header:at + size]
                if kind == 0x15:
                    owner['ui_name'] = body.decode('utf-16-le').rstrip('\0')
                if kind == 0x10:
                    owner['actual_pe'] = reader.pe(body)
                at = (at + size + 3) & ~3
            return super().sections(data, owner, depth)

    fd = (ARTIFACT / 'build/FV/SILICIUM_UEFI.fd').read_bytes()
    if sha(fd) != 'aca853390666e48dfd3901bdfca2a9deab0d7978a02152c4ad497564f0b8b4d6':
        raise ValueError('R-011 FD differs')
    actual = Actual()
    actual.volume(fd, 'R-011 actual FD')
    modules = []
    for path in paths:
        if not path.endswith('.inf'):
            continue
        guid = re.search(r'FILE_GUID\s*=\s*([0-9a-fA-F-]+)', text[path]).group(1).lower()
        matches = [f for f in actual.files if f['guid'] == guid]
        if len(matches) != 1 or 'actual_pe' not in matches[0]:
            raise ValueError('Actual filesystem-chain driver absent or duplicated: ' + path)
        item = matches[0]
        modules.append(dict(path=path, guid=guid, ui_name=item.get('ui_name'), image=item['actual_pe']))
    for guid in ('5c0e4b7a-31d2-4e8f-9a66-0b1f7d2c8e43', '9b665204-a133-47a2-9396-9e2b370a4e25'):
        item, = [f for f in actual.files if f['guid'] == guid]
        modules.append(dict(guid=guid, ui_name=item.get('ui_name'), image=item['actual_pe']))
    names = re.findall(r'^\s*\{"([^"]+)",\s*0x', map_source, re.M)
    if len(captured_sec) != 1:
        raise ValueError('Unique SEC required')
    sec = captured_sec[0]
    start = sec.index(names[0].encode().ljust(32, b'\0'))
    rows = []
    for index, name in enumerate(names):
        offset = start + index * 72
        if sec[offset:offset + 32] != name.encode().ljust(32, b'\0'):
            raise ValueError('Actual SEC table differs')
        address, size, hob, resource, attrs, memtype, arm = struct.unpack_from('<QQIIIII4x', sec, offset + 32)
        rows.append(dict(name=name, start=address, end_exclusive=address + size, memory_type=memtype))
    alias_definitions = local(FW, FW_PIN, 'Silicon/Silicium/SiliciumPkg/Include/Library/MemoryMapLib.h',
                              ['#define Reserv', 'EFI_RESOURCE_ATTRIBUTE_TYPE', 'EFI_MEMORY_TYPE'])
    aliases = dict(re.findall(r'^#define\s+(\w+)\s+(Efi\w+)\s*$', alias_definitions, re.M))
    enum_source = text['MdePkg/Include/Uefi/UefiMultiPhase.h']
    enum_source = enum_source[enum_source.index('  EfiReservedMemoryType,'):enum_source.index('  EfiMaxMemoryType')]
    enum_values = {name: i for i, name in enumerate(re.findall(r'^\s*(Efi\w+)\s*,', enum_source, re.M))}
    for row, line in zip(rows, re.findall(r'^\s*\{[^\n]+', map_source, re.M)):
        alias = line.split(',')[6].strip()
        if aliases[alias] not in enum_values or row['memory_type'] != enum_values[aliases[alias]]:
            raise ValueError('Actual SEC memory type differs from pinned source: ' + row['name'])
    dt = json.loads((ROOT / 'reports/system-volume-audit/inputs.json').read_text())['android_initrd']
    start, end = int(dt['start'], 16), int(dt['end_exclusive'], 16)
    covering = [row for row in rows if row['start'] <= start < end <= row['end_exclusive']]
    checks = dict(firmware_marker_registered_and_recognized='unixnu:firmware' in entry and 'CopyMem (P, mFirmwareMarker' in registrar,
                  connect_before_config=main_source.index('UniXNUConnectAll ();') < main_source.index('UniXNUConfigLoad'),
                  recursive_connect='ConnectController (Handles[Index], NULL, NULL, TRUE)' in inject,
                  disk_drivers_apriori=all(s in apriori for s in ('DiskIoDxe.inf', 'PartitionDxe.inf', 'Fat.inf', 'EnglishDxe.inf')),
                  publisher_in_fv='NuwaBootMemoryDxe.inf' in fdf,
                  fat_binding_no_logical_partition_gate='LogicalPartition' not in text['FatPkg/EnhancedFatDxe/Fat.c'],
                  fat_requires_diskio='gEfiDiskIoProtocolGuid' in text['FatPkg/EnhancedFatDxe/Fat.c'],
                  fat_installs_simplefs='&gEfiSimpleFileSystemProtocolGuid' in text['FatPkg/EnhancedFatDxe/Init.c'])
    if not all(checks.values()):
        raise ValueError('Source contract differs: ' + json.dumps(checks))
    report = dict(at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  scope='Pinned source and actual FD static inspection; no target execution',
                  sources=records, actual_fd_sha256=sha(fd), modules=modules, source_checks=checks,
                  descriptor_layout=dict(stride=72, resource_attribute_bytes=4, memory_type_offset=60,
                                         arm_attributes_offset=64, trailing_padding_bytes=4,
                                         all_source_memory_types_checked=len(rows)),
                  android_snapshot_only=dict(initrd=dt, covering_actual_sec_descriptors=covering),
                  conclusions=['No missing DiskIo/FAT/English module found in actual R-011 FD',
                               'Registered firmware-entry source connects controllers before config discovery',
                               'No partition table is demanded by the inspected FAT binding solely because LogicalPartition is false',
                               'Publisher does not independently validate or reserve candidate memory; actual mapping/lifetime still needs evidence'],
                  unverified=['Candidate host/load options and controller connect results',
                              'Candidate initrd mapping/cache attributes/ownership', 'Runtime FAT mount and target config parser'],
                  device_commands_executed=False, firmware_modified=False, board_feed_changed=False)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(source_checks=checks, actual_modules=[m.get('ui_name') for m in modules],
                         android_snapshot_covering_descriptors=covering), indent=2))


if __name__ == '__main__':
    main()
