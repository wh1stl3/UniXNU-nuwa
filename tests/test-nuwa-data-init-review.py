#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("review", ROOT / "scripts/nuwa-data-init-review.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
PREPARE = (ROOT / "out/nuwa-disposable-data-init/prepare.bin").read_bytes()
COMMIT = (ROOT / "out/nuwa-disposable-data-init/commit-sb0.bin").read_bytes()
OFFSET = (m.META_FIRST - m.PART_FIRST) * m.BLOCK


class Mock:
    def __init__(self, fail=None):
        self.data = bytearray(PREPARE)
        self.calls = []
        self.fail = fail

    def action(self, name, offset=None):
        self.calls.append(name)
        if offset is not None and offset != OFFSET:
            raise AssertionError("wrong offset")
        if len(self.calls) == self.fail:
            raise OSError("injected")

    def read(self, offset, size):
        self.action("read", offset)
        return bytes(self.data[:size])

    def write(self, offset, data):
        self.action("write", offset)
        self.data[:len(data)] = data
        return len(data)

    def sync(self):
        self.action("sync")
        return True


class Tests(unittest.TestCase):
    def test_geometry(self):
        self.assertEqual(m.geometry("partition", (259, 16), 4096, m.PART_BLOCKS,
                                    m.PART_FIRST * 8), OFFSET)
        self.assertEqual(m.geometry("whole", (8, 0), 4096, m.DISK_BLOCKS, 0),
                         m.META_FIRST * 4096)
        for args in [("partition", (8, 0), 4096, m.PART_BLOCKS, m.PART_FIRST * 8),
                     ("partition", (259, 16), 512, m.PART_BLOCKS, m.PART_FIRST * 8),
                     ("partition", (259, 16), 4096, m.PART_BLOCKS - 1, m.PART_FIRST * 8),
                     ("partition", (259, 16), 4096, m.PART_BLOCKS, m.PART_FIRST * 8 + 1),
                     ("whole", (8, 0), 4096, m.DISK_BLOCKS - 1, 0),
                     ("other", (8, 0), 4096, m.DISK_BLOCKS, 0)]:
            with self.assertRaises(m.Refused):
                m.geometry(*args)

    def test_success_order(self):
        io = Mock()
        m.transaction(io, OFFSET, PREPARE, COMMIT)
        self.assertEqual(io.calls, ["read", "write", "sync", "read", "write", "sync", "read"])
        self.assertEqual(io.data, COMMIT + PREPARE[m.BLOCK:])

    def test_injected_failure_stops_at_first_error(self):
        for n in range(1, 8):
            io = Mock(n)
            with self.assertRaises(OSError):
                m.transaction(io, OFFSET, PREPARE, COMMIT)
            self.assertEqual(len(io.calls), n)

    def test_bad_input_and_preimage(self):
        for prepare, commit, offset in [(PREPARE[:-1], COMMIT, OFFSET),
                                        (PREPARE, COMMIT[:-1], OFFSET),
                                        (PREPARE, COMMIT, OFFSET + 4096)]:
            io = Mock()
            with self.assertRaises(m.Refused):
                m.transaction(io, offset, prepare, commit)
            self.assertEqual(io.calls, [])
        io = Mock()
        io.data[0] = 1
        with self.assertRaises(m.Refused):
            m.transaction(io, OFFSET, PREPARE, COMMIT)
        self.assertEqual(io.calls, ["read"])

    def test_short_read_write_and_bad_sync(self):
        for step in range(1, 8):
            class Bad(Mock):
                def read(self, offset, size):
                    result = super().read(offset, size)
                    return result[:-1] if len(self.calls) == step else result

                def write(self, offset, data):
                    result = super().write(offset, data)
                    return result - 1 if len(self.calls) == step else result

                def sync(self):
                    result = super().sync()
                    return False if len(self.calls) == step else result

            io = Bad()
            with self.assertRaises(m.Refused):
                m.transaction(io, OFFSET, PREPARE, COMMIT)
            self.assertEqual(len(io.calls), step)


if __name__ == "__main__":
    unittest.main()
