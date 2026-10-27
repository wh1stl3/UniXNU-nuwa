"""Compare actual diagnostic SEC memory tables with the R-011 baseline."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / 'out/firmware-ci/39835052901/nuwa-firmware-39835052901'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('artifact', type=Path)
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / 'reports') or output.exists():
        raise ValueError('Fresh repo report required')
    spec = importlib.util.spec_from_file_location('sec_memory_reader', ROOT / 'scripts/ci/inspect-firmware-candidate.py')
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    profile = json.loads((ROOT / 'config/firmware-sec-handoff-profile.json').read_text())
    commit = profile['recipe']['sources']['firmware']['commit']
    path = 'Platforms/Xiaomi/nuwaPkg/Library/MemoryMapLib/MemoryMapLib.c'
    source = subprocess.check_output(['git', '--no-optional-locks', '-c', 'safe.directory=D:/Code/PortingiOS/nuwa/uefi-nuwa',
                                      '-C', 'D:/Code/PortingiOS/nuwa/uefi-nuwa', 'show', commit + ':' + path]).decode()
    names = re.findall(r'^\s*\{"([^"]+)",\s*0x', source, re.M)
    if len(names) != 41 or names.count('DXE Heap') != 1:
        raise ValueError('Unexpected actual-source memory descriptor layout')
    captured = []
    original = reader.heap_descriptors

    def capture(data):
        captured.append(data)
        return original(data)

    reader.heap_descriptors = capture
    tables, records = [], []
    for artifact in (BASELINE, args.artifact.resolve()):
        captured.clear()
        fd = (artifact / 'build/FV/SILICIUM_UEFI.fd').read_bytes()
        firmware = reader.Firmware()
        firmware.volume(fd, 'FD/FVMAIN_COMPACT')
        if len(captured) != 1:
            raise ValueError('Unique actual SEC required')
        body = captured[0]
        prefix = names[0].encode().ljust(32, b'\0')
        if body.count(prefix) != 1:
            raise ValueError('Memory table location ambiguous')
        at = body.index(prefix)
        table = body[at:at + 72 * len(names)]
        for index, name in enumerate(names):
            if table[72 * index:72 * index + 32] != name.encode().ljust(32, b'\0'):
                raise ValueError('Memory descriptor order/stride differs')
        tables.append(table)
        records.append(dict(fd_sha256=sha(fd), sec_sha256=sha(body), table_sha256=sha(table),
                            table_offset=at, handoff_markers={m: m.encode() in body for m in reader.HANDOFF_MARKERS}))
    if tables[0] != tables[1]:
        raise ValueError('Diagnostic actual SEC changes memory descriptor bytes')
    if any(records[0]['handoff_markers'].values()) or not all(records[1]['handoff_markers'].values()):
        raise ValueError('Unexpected baseline/new SEC diagnostic markers')
    result = dict(result='actual SEC tables identical; all four new log markers present', descriptor_count=len(names),
                  stride=72, compared_bytes=len(tables[0]), baseline=records[0], candidate=records[1],
                  firmware_commit=commit, device_executed=False,
                  limitation='Static binary consistency only; not HOB correctness, runtime logger availability or XNU execution')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
