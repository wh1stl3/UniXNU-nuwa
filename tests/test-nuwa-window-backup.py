#!/usr/bin/env python3
"""Isolated synthetic host-file exercise; not a device backup or restore tool."""
import hashlib
import os
import tempfile
import unittest
from pathlib import Path

BLOCK = 4096
FIRST, END = 57393401, 61588475
ROOT, RESERVE = 8446279680, 262144
SEGMENT = 7 * BLOCK
SCALE_BLOCKS = 31
IDENTITY = (0, BLOCK, FIRST, END, ROOT, RESERVE,
            b"synthetic-gpt-primary-and-backup", b"synthetic-seed",
            b"synthetic-root", b"synthetic-guard")


def digest(data):
    return hashlib.sha256(data).hexdigest()


class Fixture:
    """All handles originate here; no paths supplied by callers."""
    def __init__(self, directory):
        self.media = Path(directory) / "new-media"
        self.parts = []
        self.binding = IDENTITY
        self.writes = 0
        with self.media.open("xb") as f:
            f.write(b"L" * BLOCK)
            for n in range(SCALE_BLOCKS):
                f.write(bytes([n + 1]) * BLOCK)
            f.write(b"R" * BLOCK)

    def backup(self):
        hashes = []
        total = hashlib.sha256()
        with self.media.open("rb") as f:
            f.seek(BLOCK)
            remaining = SCALE_BLOCKS * BLOCK
            while remaining:
                data = f.read(min(SEGMENT, remaining))
                assert data
                p = self.media.parent / ("new-part-%d" % len(self.parts))
                with p.open("xb") as out:
                    out.write(data)
                self.parts.append(p)
                hashes.append((len(data), digest(data)))
                total.update(data)
                remaining -= len(data)
        return (self.binding, hashes, total.hexdigest())

    def restore(self, manifest):
        binding, hashes, whole = manifest
        if binding != IDENTITY or len(hashes) != len(self.parts):
            raise ValueError("binding or segment count")
        total = hashlib.sha256()
        count = 0
        for path, (length, expected) in zip(self.parts, hashes):
            data = path.read_bytes()
            if len(data) != length or digest(data) != expected:
                raise ValueError("segment")
            total.update(data)
            count += len(data)
        if count != SCALE_BLOCKS * BLOCK or total.hexdigest() != whole:
            raise ValueError("window")
        with self.media.open("r+b") as out:
            out.seek(BLOCK)
            for path in self.parts:
                out.write(path.read_bytes())
                self.writes += 1
            out.flush()
            os.fsync(out.fileno())

    def readback(self):
        with self.media.open("rb") as f:
            before = f.read(BLOCK)
            data = f.read(SCALE_BLOCKS * BLOCK)
            after = f.read(BLOCK)
        return before, digest(data), after


class HostExercise(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="nuwa-host-window-")
        self.addCleanup(self.tmp.cleanup)
        self.fixture = Fixture(self.tmp.name)
        self.manifest = self.fixture.backup()

    def test_restore_after_torn_or_reported_error(self):
        for written in (BLOCK // 2, BLOCK):
            with self.fixture.media.open("r+b") as f:
                f.seek(BLOCK)
                f.write(b"X" * written)
                f.flush()
                os.fsync(f.fileno())
            # Both cases are treated as unknown, including an error after full write.
            self.fixture.restore(self.manifest)
            self.assertEqual(self.fixture.readback(),
                             (b"L" * BLOCK, self.manifest[2], b"R" * BLOCK))

    def test_reject_before_write(self):
        binding, hashes, whole = self.manifest
        for index in (2, 3, 6):
            altered = list(binding)
            altered[index] = b"wrong"
            with self.assertRaises(ValueError):
                self.fixture.restore((tuple(altered), hashes, whole))
        p = self.fixture.parts[1]
        original = p.read_bytes()
        for bad in (original[:-1], b"X" + original[1:]):
            p.write_bytes(bad)
            with self.assertRaises(ValueError):
                self.fixture.restore(self.manifest)
        self.assertEqual(self.fixture.writes, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
