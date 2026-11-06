"""Decode an exact 64KiB private snapshot; no device IO or retention claim."""
import argparse
import hashlib
import json
import struct
import zlib
from pathlib import Path

WINDOW = 65536
HEADER = 64
COMMIT = 0x31444D435257554E


def decode(raw, nonce, sequence):
    if len(raw) != WINDOW:
        raise ValueError('Expected exactly 65536 bytes')
    if len(nonce) != 16 or not any(nonce) or not 0 < sequence < 2**64 or sequence == COMMIT:
        raise ValueError('Invalid expected trial identity')
    magic, version, header, window, length, flags, seq, actual_nonce, crc, hcrc, commit = struct.unpack_from('<8sHHIIIQ16sIIQ', raw)
    if (magic, version, header, window, flags) != (b'NUWARAM1', 1, HEADER, WINDOW, 0):
        raise ValueError('Unsupported header')
    if seq != sequence or actual_nonce != nonce:
        raise ValueError('Wrong trial identity')
    if commit != COMMIT ^ sequence:
        raise ValueError('Uncommitted or torn commit')
    if length > WINDOW - HEADER:
        raise ValueError('Payload outside window')
    if zlib.crc32(raw[:52]) != hcrc:
        raise ValueError('Header CRC mismatch')
    payload = raw[HEADER:HEADER + length]
    if zlib.crc32(payload) != crc or any(raw[HEADER + length:]):
        raise ValueError('Payload CRC or zero padding mismatch')
    return dict(format='NUWARAM1', sequence=seq, nonce=nonce.hex(), payload_bytes=length,
                payload_crc32=f'{crc:08x}', payload_sha256=hashlib.sha256(payload).hexdigest(),
                snapshot_sha256=hashlib.sha256(raw).hexdigest(),
                scope='Valid private snapshot; not proof of cache persistence or reset retention')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('snapshot', type=Path)
    p.add_argument('--nonce', required=True, help='Expected 16-byte trial nonce as 32 hex digits')
    p.add_argument('--sequence', required=True, type=lambda s: int(s, 0))
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args()
    if a.output.exists():
        p.error('Fresh output required')
    with a.snapshot.open('rb') as f:
        raw = f.read(WINDOW + 1)
    result = decode(raw, bytes.fromhex(a.nonce), a.sequence)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with a.output.open('x', encoding='utf-8') as f:
        json.dump(result, f, indent=2)
        f.write('\n')
    print('PASS snapshot format and expected trial identity')


if __name__ == '__main__':
    main()
