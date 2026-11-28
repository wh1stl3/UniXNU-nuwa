#!/usr/bin/env python3
"""Real Linux direct file I/O and syscall fault tests for the recovery core."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

PAGE = 4096
SIZE = 770 * PAGE
OFFSET = 54282425 * PAGE
AUTH = "--authorize-nuwa-blank-data-init"


class Backend(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory(dir="/tmp")
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        self.target = self.root / "partition.img"
        self.disk = self.root / "lu0.img"
        self.output = self.root / "receipts"
        self.output.mkdir()
        with self.target.open("wb") as f:
            f.truncate(OFFSET + SIZE + PAGE)
            for offset, c in [(OFFSET - PAGE, b"L"), (OFFSET + SIZE, b"R")]:
                f.seek(offset)
                f.write(c * PAGE)
        with self.disk.open("wb") as f:
            for lba, label in [(1, "primary-header"), (2, "primary-entries"),
                               (61850623, "backup-header"), (61850619, "backup-entries")]:
                f.seek(lba * PAGE)
                f.write((args.gpt / f"sda-{label}.bin").read_bytes())

    def invoke(self, arg=None, fault=None):
        cfg = {
            "NUWA_TEST_TARGET": (self.target, os.O_RDWR | os.O_DIRECT),
            "NUWA_TEST_DISK": (self.disk, os.O_RDONLY | os.O_DIRECT),
            "NUWA_TEST_RECEIPTS": (self.output, os.O_RDONLY | os.O_DIRECTORY),
        }
        env = os.environ.copy()
        fds = []
        trace = self.root / "trace"
        try:
            for key, (path, flags) in cfg.items():
                fds.append(os.open(path, flags))
                env[key] = str(fds[-1])
            argv = ["strace", "-qq", "-s", "0", "-o", trace, "-e", "trace=pread64,pwrite64,fsync"]
            if fault:
                argv += ["-e", "inject=" + fault]
            argv += [args.built / "nuwa-data-init-host"]
            if arg:
                argv.append(arg)
            p = subprocess.run(argv, pass_fds=fds, env=env, capture_output=True, text=True, check=False)
        finally:
            for fd in fds:
                os.close(fd)
        self.assertTrue(trace.exists(), p.stderr)
        s = trace.read_text()
        ops = [m[1:] for m in re.findall(
            rf"^(pread64|pwrite64|fsync)\({fds[0]}(?:, .*?, (\d+), (\d+))?\) *= (.*)$", s, re.M)]
        return p, ops

    def media(self, expected, check_bounds=True):
        with self.target.open("rb") as f:
            if check_bounds:
                f.seek(OFFSET - PAGE)
                self.assertEqual(f.read(PAGE), b"L" * PAGE)
            f.seek(OFFSET)
            self.assertEqual(f.read(SIZE), expected)
            if check_bounds:
                self.assertEqual(f.read(PAGE), b"R" * PAGE)

    def test_write_direct_readbacks_and_reentry(self):
        p, ops = self.invoke(AUTH)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(ops, [
            (str(SIZE), str(OFFSET), str(SIZE)),
            (str(SIZE), str(OFFSET), str(SIZE)), ("", "", "0"),
            (str(SIZE), str(OFFSET), str(SIZE)),
            (str(PAGE), str(OFFSET), str(PAGE)), ("", "", "0"),
            (str(SIZE), str(OFFSET), str(SIZE)),
        ])
        prepared = bytes(SIZE)
        committed = args.sb0.read_bytes() + bytes(SIZE - PAGE)
        self.assertEqual((self.output / "prepare-readback.bin").read_bytes(), prepared)
        self.assertEqual((self.output / "commit-readback.bin").read_bytes(), committed)
        self.media(committed)
        p, ops = self.invoke(AUTH)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("preimage", p.stderr)
        self.assertEqual(len(ops), 1)

    def test_read_only(self):
        p, ops = self.invoke()
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(len(ops), 1)
        self.assertFalse(list(self.output.iterdir()))
        self.media(bytes(SIZE))

    def test_wrong_gpt_primary_and_backup(self):
        for lba in (1, 2, 61850619, 61850623):
            with self.subTest(lba=lba), self.disk.open("r+b", buffering=0) as f:
                offset = lba * PAGE
                original = os.pread(f.fileno(), 1, offset)
                os.pwrite(f.fileno(), bytes([original[0] ^ 1]), offset)
                p, ops = self.invoke(AUTH)
                self.assertNotEqual(p.returncode, 0)
                self.assertIn("GPT differs", p.stderr)
                self.assertFalse(ops)
                os.pwrite(f.fileno(), original, offset)
                self.media(bytes(SIZE))

    def test_short_real_preimage(self):
        os.truncate(self.target, OFFSET + PAGE)
        p, ops = self.invoke(AUTH)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("short I/O", p.stderr)
        self.assertEqual(ops, [(str(SIZE), str(OFFSET), str(PAGE))])

    def test_stop_at_syscall_fault(self):
        # Four GPT reads plus the dynamic loader's two pread64 calls precede
        # the metadata preimage in this native glibc build. Determine readback
        # ordinals from a real read-only trace, not from mock I/O.
        p, _ = self.invoke()
        self.assertEqual(p.returncode, 0, p.stderr)
        preimage = (self.root / "trace").read_text().count("pread64(")
        for fault, steps in [
            ("pwrite64:retval=4096:when=1", 2), ("fsync:error=EIO:when=1", 3),
            (f"pread64:retval=4096:when={preimage + 1}", 4),
            ("pwrite64:error=ENOSPC:when=2", 5), ("fsync:error=EIO:when=2", 6),
            (f"pread64:error=EIO:when={preimage + 2}", 7),
        ]:
            with self.subTest(fault=fault):
                p, ops = self.invoke(AUTH, fault)
                self.assertNotEqual(p.returncode, 0)
                self.assertEqual(len(ops), steps, p.stderr)
                self.assertIn("media completion uncertain", p.stderr)
                self.assertIn("INJECTED", ops[-1][-1])
                self.assertFalse((self.output / "commit-readback.bin").exists())
                (self.output / "prepare-readback.bin").unlink(missing_ok=True)
                with self.target.open("r+b", buffering=0) as f:
                    os.pwrite(f.fileno(), bytes(SIZE), OFFSET)
                self.media(bytes(SIZE))

    def test_production_cli_rejects_write_outside_pid1_and_free_lba(self):
        exe = args.built / "nuwa-data-init-cli-host"
        for arg, marker in [(AUTH, "PID 1" if os.geteuid() == 0 else "root recovery"),
                            ("57393401", "usage:")]:
            p = subprocess.run([exe, arg], capture_output=True, text=True, check=False)
            self.assertNotEqual(p.returncode, 0)
            self.assertIn(marker, p.stderr)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("built", "gpt", "sb0"):
        p.add_argument("--" + name, type=Path, required=True)
    args, remaining = p.parse_known_args()
    unittest.main(argv=[__file__, *remaining], verbosity=2)
