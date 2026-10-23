"""Inspect pinned actual MMU helper/cache/HOB paths; never access hardware."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'out/python-tools'))
import capstone


def main():
    output = ROOT / 'reports/hob-query/audit.json'
    if output.exists():
        raise ValueError('Fresh evidence required')
    artifact = ROOT / 'out/firmware-ci/39958974666/nuwa-firmware-39958974666'
    spec = importlib.util.spec_from_file_location('mmu_reader', ROOT / 'scripts/ci/inspect-firmware-candidate.py')
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    captured = []
    original = reader.heap_descriptors
    reader.heap_descriptors = lambda data: (captured.append(data), original(data))[1]
    fd = (artifact / 'build/FV/SILICIUM_UEFI.fd').read_bytes()
    if hashlib.sha256(fd).hexdigest() != 'ea0277e8087b036c062866388a67fd75a9cf24f61cb0de0bc2132bc7f2243227':
        raise ValueError('Wrong actual artifact')
    reader.Firmware().volume(fd, 'Actual FD')
    if len(captured) != 1:
        raise ValueError('Unique SEC required')
    data = captured[0]
    stripped = struct.unpack_from('<H', data, 6)[0]
    base = struct.unpack_from('<Q', data, 16)[0]
    sections = []
    for i in range(data[4]):
        at = 40 + 40 * i
        vs, va, size, offset = struct.unpack_from('<4I', data, at + 8)
        sections.append((base + va, offset - stripped + 40, size))
    def read(address, size):
        for va, at, length in sections:
            if va <= address and address + size <= va + length:
                return data[at + address - va:at + address - va + size]
        raise ValueError('Address not backed by actual TE')
    mapping = artifact / 'build/FV/Ffs/9AFFB503-E643-4141-8B90-17E8588B1D35Sec/9AFFB503-E643-4141-8B90-17E8588B1D35.map'
    symbols = {}
    for match in re.finditer(r'^([0-9a-fA-F]{8,16})\s+0+\s+0\s+(\S+)\s*$', mapping.read_text(), re.M):
        symbols[match[2]] = base + int(match[1], 16)
    engine = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_LITTLE_ENDIAN)
    names = ['SerialPortWrite', 'GetNextHob', 'CompareGuid', 'GetFirstGuidHob', 'GetNextGuidHob', 'ArmDataCacheLineLength', 'CacheRangeOperation',
             'ArmCleanDataCacheEntryByMVA', 'ArmReplaceLiveTranslationEntry']
    dumps = []
    for name in names:
        if name not in symbols:
            continue
        address = symbols[name]
        end = min(a for a in symbols.values() if a > address)
        size = min(end - address, 512)
        dumps.append(dict(symbol=name, preferred_address=hex(address), bytes=size,
                          instructions=[dict(address=hex(i.address), bytes=i.bytes.hex(), mnemonic=i.mnemonic, operands=i.op_str)
                                        for i in engine.disasm(read(address, size), address)]))
    size_address = symbols['ArmReplaceLiveTranslationEntrySize']
    helper_size = struct.unpack('<I', read(size_address, 4))[0]
    helper = read(symbols['ArmReplaceLiveTranslationEntry'], helper_size)
    mu = Path('D:/Code/PortingiOS/common/sources/mu-nuwa-firmware/Mu_Basecore')
    pin = 'cfb93724a06ff86ff5ba971413368a7809ee42a5'
    paths = ['UefiCpuPkg/Library/ArmMmuLib/AArch64/ArmMmuLibReplaceEntry.S',
             'ArmPkg/Library/ArmCacheMaintenanceLib/ArmCacheMaintenanceLib.c',
             'EmbeddedPkg/Library/PrePiHobLib/Hob.c',
             'UefiCpuPkg/Library/ArmMmuLib/AArch64/ArmMmuLibCore.c']
    sources = []
    for path in paths:
        raw = subprocess.check_output(['git', '--no-optional-locks', '-c', f'safe.directory={mu}', '-C', str(mu), 'show', pin + ':' + path])
        patterns = ['Constructor', 'GetFirstGuidHob', 'GetNextGuidHob', 'GET_NEXT_HOB', 'END_OF_HOB',
                    'ArmReplaceLiveTranslationEntrySize', '.long', '.word', 'WriteBackDataCacheRange',
                    'CacheRangeOperation', 'LineLength', 'LineOperation', 'ArmDataSynchronizationBarrier']
        sources.append(dict(repository='microsoft/mu_basecore', commit=pin, path=path,
                            sha256=hashlib.sha256(raw).hexdigest(), license='BSD-2-Clause-Patent',
                            anchors=[dict(line=n, text=line.strip()) for n, line in enumerate(raw.decode().splitlines(), 1)
                                     if any(p in line for p in patterns)]))
    result = dict(scope='Actual TE and pinned source static audit; not runtime PCs or register measurements',
                  fd_sha256=hashlib.sha256(fd).hexdigest(), sec_sha256=hashlib.sha256(data).hexdigest(),
                  map_sha256=hashlib.sha256(mapping.read_bytes()).hexdigest(), functions=dumps, sources=sources,
                  helper=dict(preferred_address=hex(symbols['ArmReplaceLiveTranslationEntry']),
                              size_field_preferred_address=hex(size_address), bytes=helper_size,
                              sha256=hashlib.sha256(helper).hexdigest()),
                  unverified=['Whether GUID HOB lookup returns', 'Selected MMU constructor branch',
                              'Runtime CTR_EL0/current EL and cache-operation permission', 'Exception PC and fault registers'],
                  device_accessed=False, images_modified=False)
    output.parent.mkdir(parents=True)
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(helper=result['helper'], functions=dumps), indent=2))


if __name__ == '__main__':
    main()
