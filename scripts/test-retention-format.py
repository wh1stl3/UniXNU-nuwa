"""Serial host sanitizer and AArch64 QEMU codec checks; never accesses a device."""
import argparse
import hashlib
import importlib.util
import json
import struct
import subprocess
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args()
    out = a.output.resolve()
    if not out.is_relative_to(ROOT / 'out') or out.exists():
        p.error('Fresh directory below out/ required')
    out.mkdir(parents=True)
    commands = []
    def run(argv):
        r = subprocess.run(argv, capture_output=True, timeout=120)
        commands.append(dict(argv=argv, exit_code=r.returncode, stdout=r.stdout.decode(errors='replace'), stderr=r.stderr.decode(errors='replace')))
        (out / 'commands.json').write_text(json.dumps(commands, indent=2) + '\n', encoding='utf-8')
        if r.returncode:
            raise RuntimeError(commands[-1])
    def linux(path):
        return '/mnt/d/' + path.resolve().as_posix()[3:]
    wsl = ['wsl', '-d', 'Ubuntu-22.04', '--']
    source = ROOT / 'tests/retention_format_host.c'
    run(wsl + ['/usr/bin/clang', '--version'])
    run(wsl + ['/usr/bin/clang', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', '-fsanitize=address,undefined', '-fno-omit-frame-pointer', linux(source), '-o', linux(out / 'host-test')])
    run(wsl + [linux(out / 'host-test'), linux(out / 'host.bin')])
    run(wsl + ['aarch64-linux-gnu-gcc', '--version'])
    run(wsl + ['aarch64-linux-gnu-gcc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', '-static', linux(source), '-o', linux(out / 'arm-test')])
    qemu = ROOT / 'out/upstream-host-tests/qemu-runtime/usr/bin/qemu-aarch64'
    run(wsl + [linux(qemu), '--version'])
    run(wsl + [linux(qemu), linux(out / 'arm-test'), linux(out / 'arm.bin')])
    spec = importlib.util.spec_from_file_location('decoder', ROOT / 'scripts/decode-retention-record.py')
    d = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(d)
    raw = (out / 'host.bin').read_bytes()
    assert raw == (out / 'arm.bin').read_bytes()
    nonce = bytes(range(1, 17))
    decoded = d.decode(raw, nonce, 17)
    # Independent Python reference encoding, not a second invocation of the C writer.
    payload = bytes((i * 37 + 11) & 255 for i in range(257))
    head = struct.pack('<8sHHIIIQ16sI', b'NUWARAM1', 1, 64, 65536, len(payload), 0, 17, nonce, zlib.crc32(payload))
    reference = head + struct.pack('<IQ', zlib.crc32(head), d.COMMIT ^ 17) + payload + bytes(65536 - 64 - len(payload))
    assert raw == reference
    rejected = []
    def reject(name, value, expected_nonce=nonce, sequence=17):
        try:
            d.decode(value, expected_nonce, sequence)
        except ValueError:
            rejected.append(name)
        else:
            raise AssertionError('Accepted ' + name)
    for i in range(512):
        bad = bytearray(raw); bad[i // 8] ^= 1 << (i % 8)
        reject(f'header-bit-{i}', bad)
    reject('stale-nonce', raw, bytes(range(16)))
    reject('stale-sequence', raw, sequence=18)
    reject('truncated', raw[:-1]); reject('trailing-data', raw + b'0')
    for offset in (64, 320, 321, 65535):
        bad = bytearray(raw); bad[offset] ^= 1; reject(f'payload-or-padding-{offset}', bad)
    bad = bytearray(raw); struct.pack_into('<I', bad, 16, 0xffffffff); struct.pack_into('<I', bad, 52, zlib.crc32(bad[:52])); reject('oversize-valid-header-crc', bad)
    files = [source, ROOT / 'tests/nuwa_retention_format.h', Path(__file__).resolve(), ROOT / 'scripts/decode-retention-record.py', qemu, out / 'host.bin', out / 'arm.bin']
    report = dict(scope='Host ASan/UBSan and AArch64 QEMU user-mode codec only; no firmware boot, cache or reset qualification', decoded=decoded, identical_host_arm_reference=True, python_negative_controls=len(rejected), rejected=rejected,
                  files=[dict(path=str(f), sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for f in files])
    (out / 'result.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print('PASS host sanitizer, AArch64 QEMU, independent reference and', len(rejected), 'decoder negative controls')


if __name__ == '__main__':
    main()
