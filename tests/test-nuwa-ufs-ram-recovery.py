#!/usr/bin/env python3
"""Exercise the compiled receipt framer, host actual receiver and build bounds."""
import argparse
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("receiver", HERE / "scripts/read-nuwa-ufs-ram-receipt.py")
rx = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rx)


class Recovery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audit = json.loads((args.armed / "audit.json").read_text())
        cls.identifier = cls.audit["run_id"]
        cls.zero = bytes(rx.BYTES)
        cls.commit = args.sb0.read_bytes() + bytes(rx.BYTES - 4096)
        with tempfile.TemporaryDirectory() as temp:
            i = Path(temp) / "prepare"
            j = Path(temp) / "commit"
            i.write_bytes(cls.zero)
            j.write_bytes(cls.commit)
            cls.frame = subprocess.check_output([args.armed / "export-fixture", i, j])

    def test_compiled_export_and_actual_journal(self):
        with tempfile.TemporaryDirectory() as name:
            ledger = Path(name) / "target-first-init"
            rx.reserve(ledger, self.identifier, True)
            with self.assertRaises(FileExistsError):
                rx.reserve(ledger, "0" * 32, True)
            stream = io.BytesIO(self.frame)
            rx.capture(ledger, lambda count: stream.read(min(count, 503)))
            self.assertEqual(ledger.with_suffix(".prepare-readback.bin").read_bytes(), self.zero)
            self.assertEqual(ledger.with_suffix(".commit-readback.bin").read_bytes(), self.commit)
            self.assertIn(b"CLAIM-CLOSED\n", ledger.with_suffix(".final-receipt.txt").read_bytes())
            with self.assertRaises(FileExistsError):
                rx.capture(ledger, stream.read)

    def test_corrupt_wrong_id_or_truncated_never_succeeds(self):
        mid = len(self.frame) // 2
        for data, run in [(self.frame[:-1], self.identifier),
                          (self.frame[:mid] + b"\xff" + self.frame[mid+1:], self.identifier),
                          (self.frame, "0" * 32)]:
            with self.subTest(bytes=len(data), run=run), tempfile.TemporaryDirectory() as name:
                ledger = Path(name) / "target-first-init"
                rx.reserve(ledger, run, True)
                with self.assertRaises(ValueError):
                    rx.capture(ledger, io.BytesIO(data).read)
                self.assertTrue(ledger.with_suffix(".receive-started").exists())
                self.assertFalse(ledger.with_suffix(".final-receipt.txt").exists())

    def test_check_modes_never_admitted_as_write(self):
        for state in ("CHECK-BLANK", "CHECK-SB0"):
            data = (f"NUWARAM1 {state} {self.identifier}\n"
                    f"NUWARAM1 FINAL {self.identifier} CLAIM-CLOSED\n").encode()
            self.assertEqual(rx.receive(io.BytesIO(data).read, self.identifier, False), {"final-receipt.txt": data})
            with self.assertRaises(ValueError):
                rx.receive(io.BytesIO(data).read, self.identifier, True)

    def test_assets_unbound_and_read_only_has_no_pwrite(self):
        for path, armed in ((args.check, False), (args.armed, True)):
            audit = json.loads((path / "audit.json").read_text())
            self.assertFalse(audit["flashable"])
            self.assertEqual(audit["armed_for_review"], armed)
            self.assertEqual(audit["overlay_init"]["bc6b"]["symlink"], "/system/bin/init")
            self.assertIsNone(audit["overlay_init"]["vendor"])
            self.assertIsNone(audit["overlay_init"]["init_boot"]["symlink"])
            self.assertFalse(list(path.glob("*.img")))
            self.assertEqual((path / "UNBOUND-pid1-fragment.cpio.lz4").read_bytes()[:4], b"\x02!L\x18")
            elf = path / "nuwa-recovery-init"
            table = subprocess.check_output(["aarch64-linux-gnu-nm", elf], text=True)
            self.assertEqual(" pwrite64\n" in table, armed)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("armed", "check", "sb0"):
        p.add_argument("--" + name, type=Path, required=True)
    args, remaining = p.parse_known_args()
    unittest.main(argv=[__file__, *remaining], verbosity=2)
