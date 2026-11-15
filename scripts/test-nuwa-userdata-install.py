import hashlib
import importlib.util
import json
import re
import tempfile
import unittest
import shlex
import struct
import subprocess
import zlib
import io
from contextlib import redirect_stdout
from unittest.mock import patch
from pathlib import Path
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location("userdata", Path(__file__).with_name("nuwa-userdata-install.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Runner:
    def __init__(self, target=("nuwa", "userdata", 1024), fault=None):
        self.calls = []
        self.target = target
        self.fault = fault
        self.disk = bytearray(1024)

    def preflight(self, serial, backup=None, without_backup=False):
        self.calls.append("preflight")
        return self.target

    def write(self, serial, offset, data):
        self.calls.append("write")
        if self.fault == "short-write":
            return len(data) - 1, True
        if self.fault == "writer-open":
            return len(data), False
        self.disk[offset:offset + len(data)] = data
        return len(data), True

    def read(self, serial, offset, length):
        self.calls.append("read")
        data = bytes(self.disk[offset:offset + length])
        if self.fault == "short-read":
            return data[:-1]
        if self.fault == "bad-read":
            return bytes([data[0] ^ 1]) + data[1:]
        return data

    def final_begin(self):
        self.calls.append("final-begin")


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.image = self.root / "image"
        self.data = b"0123456789abcdef" * 32
        self.image.write_bytes(self.data)
        self.pin = hashlib.sha256(self.data).hexdigest()
        self.runclaim = self.root / "claim"
        diagnostic_patch = patch.object(module, "DIAGNOSTICS", self.root / "diagnostics")
        diagnostic_patch.start()
        self.addCleanup(diagnostic_patch.stop)
        self.runner = Runner()
        self.backup_dir, self.backup_pin = test_backup(self.root, 512)

    def run_it(self, authorized=True, serial="test"):
        return module.execute(self.image, serial, authorized, self.runclaim,
                              self.runner, size=512, expected=self.pin,
                              capacity=1024, window=128, backup_dir=self.backup_dir,
                              backup_record_sha256=self.backup_pin)

    def test_success_and_consumed(self):
        self.assertEqual(self.run_it()["windows"], 4)
        calls = self.runner.calls[:]
        with self.assertRaises(FileExistsError):
            self.run_it()
        self.assertEqual(self.runner.calls, calls)

    def test_unauthorized_zero_calls(self):
        with self.assertRaises(ValueError):
            self.run_it(False)
        self.assertEqual(self.runner.calls, [])
        self.assertFalse(self.runclaim.exists())

    def test_wrong_target_and_capacity(self):
        for target in (("nuwa", "super", 32), ("other", "userdata", 32),
                       ("nuwa", "userdata", 8)):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as temp:
                self.runner = Runner(target)
                self.runclaim = Path(temp) / "claim"
                with self.assertRaises(ValueError):
                    self.run_it()
                self.assertEqual(self.runner.calls, ["preflight"])

    def test_failures_stop(self):
        for fault in ("short-write", "writer-open", "short-read", "bad-read"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as temp:
                self.runner = Runner(fault=fault)
                self.runclaim = Path(temp) / "claim"
                with self.assertRaises(ValueError):
                    self.run_it()
                self.assertEqual(self.runner.calls.count("write"), 1)
                self.assertEqual(self.runner.calls.count("read"),
                                 int(fault in ("short-read", "bad-read")))
                self.assertTrue(self.runclaim.exists())


class Processes:
    """A process-boundary fixture, not a Device replacement. Never spawns."""
    def __init__(self, fault=None):
        self.fault = fault
        self.calls = []
        self.writes = 0
        self.reads = 0
        self.final = False
        self.extents = {}
        self.last = module.LAST_LBA + 100
        self.block = module.LBA_BYTES
        self.table = bytearray(self.block * 4)
        entry = 31 * 128
        self.table[entry:entry + 16] = b"T" * 16
        self.table[entry + 16:entry + 32] = b"U" * 16
        struct.pack_into("<QQ", self.table, entry + 32, module.FIRST_LBA, module.LAST_LBA)
        name = "userdata".encode("utf-16-le")
        self.table[entry + 56:entry + 56 + len(name)] = name
        if fault == "gpt-name":
            self.table[entry + 56:entry + 56 + len(name)] = "not-data".encode("utf-16-le")
        if fault == "gpt-start":
            struct.pack_into("<Q", self.table, entry + 32, module.FIRST_LBA + 1)
        if fault == "gpt-end":
            struct.pack_into("<Q", self.table, entry + 40, module.LAST_LBA - 1)
        self.snapshot = [
            "/dev/block/sdz32", "sdz32", "sdz", "65:32", "32",
            str(module.FIRST_LBA * 8), str(module.CAPACITY // 512),
            str(module.CAPACITY), str((self.last + 1) * self.block),
            str(self.block), "synthetic-boot",
        ]

    def header(self, lba):
        data = bytearray(self.block)
        data[:8] = b"EFI PART"
        struct.pack_into("<4I", data, 8, 0x10000, 92, 0, 0)
        struct.pack_into("<4Q", data, 24, lba, self.last if lba == 1 else 1,
                         6, self.last - 5)
        data[56:72] = b"G" * 16
        if self.fault == "gpt-backup" and lba == self.last:
            data[56:72] = b"H" * 16
        if self.fault == "between-gpt" and self.writes == 1 and self.reads >= 1:
            data[56:72] = b"J" * 16
        if self.fault == "other-gpt":
            data[56:72] = b"K" * 16
        struct.pack_into("<Q3I", data, 72, 2 if lba == 1 else self.last - 4,
                         128, 128, zlib.crc32(self.table))
        struct.pack_into("<I", data, 16, zlib.crc32(data[:92]))
        if self.fault == "gpt-crc":
            data[56] ^= 1  # Valid GUID field, not reserved/header geometry.
        return bytes(data)

    def __call__(self, argv, **kwargs):
        between = self.writes == 1 and self.reads >= 1
        self.calls.append(argv)
        assert argv[1:3] == ["-s", "SYNTHETIC"]
        assert kwargs["stdin"] == subprocess.DEVNULL
        args = argv[3:]
        out, err, rc = b"", b"", 0
        if args == ["devices", "-l"]:
            state = getattr(self, "inventory_state",
                            {"recovery": "recovery", "offline": "offline",
                             "unauthorized": "unauthorized"}.get(self.fault, "device"))
            out = f"List of devices attached\nSYNTHETIC {state} product:nuwa\n".encode()
            if self.fault == "inventory":
                out += b"SECOND device\n"
        elif args == ["devices"]:
            out = b"SECOND fastboot\n" if self.fault == "fastboot-peer" else b""
        elif args == ["shell", "set -e; id -u; printf '\\nNUWA_UID_OK\\n'"]:
            out = b"0\r\n\r\nNUWA_UID_OK\r\n" if getattr(self, "shell_uid", 2000) == 0 else b"2000\n\nNUWA_UID_OK\n"
            if self.fault == "uid-fail":
                rc, err, out = 1, b"uid probe failed", b""
            elif self.fault == "uid-malformed":
                out = b"0\n"
        elif args[:2] == ["shell", "mkdir"]:
            assert args[2:4] == ["-m", "700"] and "/nuwa-userdata-" in args[4]
        elif args[0] == "push":
            sent = Path(args[1]).read_bytes()
            self.staged = sent
            if self.fault == "push-short":
                self.staged = sent[:-1]
            if self.fault == "push-hash":
                self.staged = bytes([sent[0] ^ 1]) + sent[1:]
            # Same line shape as adb 1.0.41; the count is what the host file held.
            err = (f"{args[1]}: 1 file pushed, 0 skipped. "
                   f"152.5 MB/s ({len(sent)} bytes in 0.420s)\r\n").encode()
        elif args[:3] in (["shell", "su", "-c"], ["shell", "sh", "-c"]):
            script = shlex.split(args[3])[0]
            assert script.startswith("set -eu\n") and script.endswith('printf "\\nNUWA_OK\\n"\n')
            if "help=$(dd --help" in script:
                out = b"0+0 records in\n0+0 records out\n0 bytes copied"
                if self.fault == "tools-fail":
                    rc, err = 85, b"tool probe rejected for SYNTHETIC"
                if self.fault == "tools-boot-change":
                    self.snapshot[10] = "different-boot"
            elif 'printf "%s:%s:%s\\n"' in script:
                status = {"staging-missing": "missing", "staging-full": "insufficient",
                          "staging-disk": "not-tmpfs"}.get(self.fault, "ok")
                out = f"{status}:262144:4096".encode()
            elif "printf '%s\\n'" in script:
                snapshot = self.snapshot[:]
                if self.fault == "byname":
                    snapshot[0] = "/dev/block/sdz31"
                if self.fault == "capacity":
                    snapshot[7] = "512"
                if self.fault == "start":
                    snapshot[5] = "0"
                if self.fault == "backup-boot-change" and self.reads >= 2:
                    snapshot[10] = "different-boot"
                out = "\n".join(snapshot).encode()
                if self.fault == "product":
                    rc = 1  # test "$(getprop ro.product.device)" = nuwa failed.
                if self.fault == "su-denied":
                    rc = 1
            elif "/input.raw\n" in script and "stat -c %s" in script:
                expected = int(re.search(r'stat -c %s [^"]+\)" = (\d+)', script)[1])
                pin = re.search(r'sha256sum [^"]+\)" = "([0-9a-f]{64})  ', script)[1]
                if len(self.staged) != expected or module.digest(self.staged) != pin:
                    rc = 1
            elif "dd if=" in script:
                # Check actual guard is adjacent, before the destructive command.
                for token in ("by-name/userdata", '"$sys/holders"', "/proc/swaps",
                              '"$p/stat"', '"$p/mountinfo"', '"$p"/fd/*', "pidof dd", "boot_id"):
                    assert token in script
                assert script.index('"$sys/holders"') < script.index("dd if=")
                self.writes += 1
                if self.fault == "timeout":
                    raise subprocess.TimeoutExpired(argv, 180)
                offset = int(re.search(r" seek=(\d+)", script)[1]) * 512
                length = int(re.search(r" count=(\d+)", script)[1]) * 512
                self.extents[offset, length] = self.staged
                count = length - 1 if self.fault == "short-write" else length
                out = f"DD_RC=0\n1+0 records in\n1+0 records out\n{count} bytes copied\nWRITER_CLOSED".encode()
                if self.fault == "writer-open":
                    rc = 83
                if self.fault == "writer-fail":
                    rc = 1
                if self.fault == "no-writerclosed":
                    out = out.removesuffix(b"WRITER_CLOSED")
            elif '"$sys/holders"' in script and self.fault == "holders":
                rc = 1
            elif '"$sys/holders"' in script and self.fault == "backup-writer":
                rc = 82
            elif "echo 3 >" in script and "/proc/swaps" in script:
                self.final = True
            if rc == 0:
                if not (self.fault == "no-nuwa-ok" and "conv=notrunc,fsync" in script):
                    out += b"\nNUWA_OK\n"
        elif args[:3] in (["exec-out", "su", "-c"], ["exec-out", "sh", "-c"]):
            command = args[3]
            assert not command.startswith("'")
            assert command.startswith("set -eu\n") and '"$sys/holders"' in command
            match = re.search(r"\nexec dd if=(/dev/block/[a-z0-9]+) bs=512 skip=(\d+) count=(\d+) 2>/dev/null$", command)
            assert match, command
            target, offset, length = match[1], int(match[2]) * 512, int(match[3]) * 512
            if target == "/dev/block/sdz":
                lba = offset // self.block
                if lba in (1, self.last):
                    out = self.header(lba)
                else:
                    assert lba in (2, self.last - 4)
                    out = bytes(self.table)
                    if self.fault == "gpt-table":
                        out = out[:-1] + bytes([out[-1] ^ 1])
            else:
                assert target == "/dev/block/sdz32"
                self.reads += 1
                out = self.extents[offset, length]
                if self.fault == "read-short" or (self.final and self.fault == "final-short"):
                    out = out[:-1]
                if self.fault == "backup-short" or (self.fault == "backup-second-short" and self.reads > 2):
                    out = out[:-1]
                if self.fault == "backup-different" and self.reads > 2:
                    out = bytes([out[0] ^ 1]) + out[1:]
                if self.fault == "read-hash" or (self.final and self.fault == "final-hash"):
                    out = bytes([out[0] ^ 1]) + out[1:]
            if hasattr(kwargs["stdout"], "write"):
                kwargs["stdout"].write(out)
                out = None
        else:
            raise AssertionError(argv)
        # Simulate a changed remote binding/session AFTER the first window was
        # independently read, and BEFORE the next guarded raw command. This
        # remains a subprocess-response simulation, not real Android execution.
        command = (shlex.split(args[3])[0] if args[:3] in (["shell", "su", "-c"], ["shell", "sh", "-c"])
                   else args[3] if args[:3] in (["exec-out", "su", "-c"], ["exec-out", "sh", "-c"]) else "")
        if (between and '"$sys/holders"' in command
                and self.fault in ("between-boot", "between-binding")):
            if self.fault == "between-boot":
                assert 'test "$(cat /proc/sys/kernel/random/boot_id)" = synthetic-boot' in command
            else:
                assert 'test "$target" = /dev/block/sdz32' in command
            rc = 1
            # Nothing gets written to the device: any GPT output above is just
            # fabricated return bytes; a failed process stops before next writer.
            out = b""
        return subprocess.CompletedProcess(argv, rc, out, err)


def test_backup(root, size, name="backup"):
    """Real backup orchestration/adapter, synthetic media and process layer."""
    proc = Processes()
    for offset, length in module.window_geometry(size, 512):
        proc.extents[offset, length] = b"B" * length
    adapter = module.AndroidUserdata("SYNTHETIC", root, proc,
                                    read_only=True, backup_only=True)
    directory = root / name
    result = module.create_backup(adapter, directory, size=size, window=512)
    return directory, result["record_sha256"]


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        diagnostic_patch = patch.object(module, "DIAGNOSTICS", self.root / "diagnostics")
        diagnostic_patch.start()
        self.addCleanup(diagnostic_patch.stop)
        self.image = self.root / "image"
        self.data = bytes(range(256)) * 4
        self.image.write_bytes(self.data)
        self.pin = hashlib.sha256(self.data).hexdigest()
        self.backup_dir, self.backup_pin = test_backup(self.root, 1024)

    def install(self, fault=None, authorized=True):
        self.proc = Processes(fault)
        self.adapter = module.AndroidUserdata("SYNTHETIC", self.root, self.proc)
        return module.execute(self.image, "SYNTHETIC", authorized, self.root / "claim",
                              self.adapter, size=1024, expected=self.pin,
                              window=512, backup_dir=self.backup_dir,
                              backup_record_sha256=self.backup_pin)

    def test_unauthorized_zero_processes(self):
        with self.assertRaises(ValueError):
            self.install(authorized=False)
        self.assertEqual(self.proc.calls, [])

    def test_cli_default_dryrun_and_unauthorized_no_process(self):
        for argv in ([], ["dryrun"], ["write", "--serial", "SYNTHETIC"],
                     ["write", "--serial", "SYNTHETIC",
                      "--authorize-userdata-write-this-round", "--exclusive-offline-userdata",
                      "--reviewed-and-independently-verified", "--manifest", "unused",
                      "--executor-sha256", "wrong"]):
            with self.subTest(argv=argv), patch("sys.argv", ["installer", *argv]), \
                    patch.object(module.subprocess, "run", side_effect=AssertionError("must not spawn")) as spawn:
                if argv and argv[0] == "write":
                    with self.assertRaises(ValueError):
                        module.main()
                else:
                    module.main()
                spawn.assert_not_called()

    def test_frozen_manifest(self):
        manifest = self.root / "manifest.json"
        raw = json.dumps({"inputs": {module.MANIFEST_KEY: {
            "path": str(self.image.resolve()), "bytes": module.SIZE,
            "sha256": module.SHA256}}}).encode()
        manifest.write_bytes(raw)
        self.assertEqual(module.frozen_image(manifest, module.digest(raw)), self.image.resolve())
        with self.assertRaises(ValueError):
            module.frozen_image(manifest, "0" * 64)

    def test_complete_and_reuse(self):
        self.assertEqual(self.install()["bytes"], 1024)
        self.assertEqual((self.proc.writes, self.proc.reads), (2, 4))
        self.assertTrue(self.proc.final)
        events = [json.loads(line) for line in (self.root / "events.jsonl").read_text().splitlines()]
        self.assertEqual([e["event"] for e in events],
                         ["writer-starting", "writer-closed"] * 2)
        count = len(self.proc.calls)
        with self.assertRaises(FileExistsError):
            module.execute(self.image, "SYNTHETIC", True, self.root / "claim",
                           self.adapter, size=1024, expected=self.pin, window=512,
                           backup_dir=self.backup_dir, backup_record_sha256=self.backup_pin)
        self.assertEqual(len(self.proc.calls), count)

    def test_generated_shell_syntax_host_parser_only(self):
        self.install()
        scripts = []
        for argv in self.proc.calls:
            if argv[3:6] == ["shell", "su", "-c"]:
                scripts.append(shlex.split(argv[6])[0])
            elif argv[3:6] == ["exec-out", "su", "-c"]:
                scripts.append(argv[6])
        for script in scripts:
            # Syntax parsing only: sh -n never executes generated device code.
            result = subprocess.run(["sh", "-n"], input=script.encode(),
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_rejected_identity_geometry_and_holders(self):
        for fault in ("inventory", "offline", "unauthorized", "fastboot-peer", "product", "byname", "capacity", "start",
                      "holders", "gpt-crc", "gpt-table", "gpt-backup",
                      "gpt-start", "gpt-end", "gpt-name"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as tmp:
                self.root = Path(tmp)
                with self.assertRaises(ValueError):
                    self.install(fault)
                self.assertEqual(self.proc.writes, 0)
                self.assertTrue((self.root / "claim").exists())

    def test_recovery_inspect_keeps_identity_and_binding_guards(self):
        proc = Processes("recovery")
        adapter = module.AndroidUserdata("SYNTHETIC", self.root, proc, read_only=True)
        result = adapter.inspect("SYNTHETIC")
        self.assertEqual(result["status"], "read-only-checks-complete")
        self.assertEqual(proc.writes, 0)
        self.assertTrue(any("getprop ro.product.device" in str(call) for call in proc.calls))
        self.assertTrue(any('"$sys/holders"' in str(call) for call in proc.calls))

        for fault in ("inventory", "product", "tools-boot-change"):
            with self.subTest(fault=fault):
                proc = Processes(fault)
                proc.inventory_state = "recovery"
                adapter = module.AndroidUserdata("SYNTHETIC", self.root, proc, read_only=True)
                with self.assertRaises(ValueError):
                    adapter.inspect("SYNTHETIC")
                self.assertEqual(proc.writes, 0)

    def test_root_shell_selection_and_probe_failures(self):
        proc = Processes("recovery")
        proc.shell_uid = 0
        adapter = module.AndroidUserdata("SYNTHETIC", self.root, proc, read_only=True)
        self.assertEqual(adapter.inspect("SYNTHETIC")["status"], "read-only-checks-complete")
        self.assertTrue(any(a[3:6] == ["shell", "sh", "-c"] for a in proc.calls))
        self.assertTrue(any(a[3:6] == ["exec-out", "sh", "-c"] for a in proc.calls))
        self.assertFalse(any(a[4:5] == ["su"] for a in proc.calls))
        self.assertEqual(sum(a[3:5] == ["shell", "set -e; id -u; printf '\\nNUWA_UID_OK\\n'"]
                             for a in proc.calls), 1)
        proc = Processes("recovery")
        adapter = module.AndroidUserdata("SYNTHETIC", self.root, proc, read_only=True)
        self.assertEqual(adapter.inspect("SYNTHETIC")["status"], "read-only-checks-complete")
        self.assertTrue(any(a[3:6] == ["shell", "su", "-c"] for a in proc.calls))
        self.assertTrue(any(a[3:6] == ["exec-out", "su", "-c"] for a in proc.calls))
        for fault in ("uid-fail", "uid-malformed", "su-denied"):
            with self.subTest(fault=fault):
                proc = Processes(fault)
                proc.inventory_state = "recovery"
                adapter = module.AndroidUserdata("SYNTHETIC", self.root, proc, read_only=True)
                with self.assertRaises(ValueError):
                    adapter.inspect("SYNTHETIC")
                self.assertEqual(proc.writes, 0)
                self.assertFalse(any(a[3:4] == ["exec-out"] for a in proc.calls))

    def test_transfer_and_writer_failures(self):
        for fault in ("push-short", "push-hash", "short-write", "writer-open", "writer-fail", "timeout",
                      "read-short", "read-hash", "final-hash", "final-short"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as tmp:
                self.root = Path(tmp)
                with self.assertRaises(ValueError):
                    self.install(fault)
                self.assertLessEqual(self.proc.writes, 2 if fault.startswith("final-") else 1)
                if fault in ("writer-open", "writer-fail", "timeout", "short-write"):
                    self.assertEqual(self.proc.reads, 0)
                    events = (self.root / "events.jsonl").read_text()
                    self.assertNotIn('"event": "writer-closed"', events)
                if fault == "timeout":
                    self.assertTrue(self.adapter.invalid)
                    before = len(self.proc.calls)
                    with self.assertRaises(ValueError):
                        self.adapter.call("adb", ["devices"])
                    self.assertEqual(len(self.proc.calls), before)
                self.assertTrue(self.adapter.invalid)


class IncrementalTests(unittest.TestCase):
    """Directed review/verifier gaps only; select this class for the delta run."""
    setUp = AdapterTests.setUp
    install = AdapterTests.install

    def test_crc_reason_is_header_crc(self):
        proc = Processes("gpt-crc")
        raw = proc.header(1)
        self.assertEqual(struct.unpack_from("<I", raw, 20)[0], 0)
        with self.assertRaisesRegex(ValueError, "^physical GPT header CRC$"):
            module.gpt_header(raw, 1, proc.last, proc.block)

    def test_between_windows_and_missing_completion(self):
        expected = {
            "between-boot": "device process failed; no retry; writer state unknown",
            "between-binding": "device process failed; no retry; writer state unknown",
            "between-gpt": "physical GPT changed",
            "no-writerclosed": "writer completion/count unproven",
            "no-nuwa-ok": "missing remote completion",
        }
        for fault, reason in expected.items():
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as tmp:
                self.root = Path(tmp)
                with self.assertRaises(ValueError) as raised:
                    self.install(fault)
                self.assertEqual(str(raised.exception), reason)
                self.assertEqual(self.proc.writes, 1)
                self.assertEqual(self.proc.reads, 1 if fault.startswith("between-") else 0)
                events = [json.loads(line) for line in
                          (self.root / "events.jsonl").read_text().splitlines()]
                self.assertEqual(sum(e["event"] == "writer-closed" for e in events),
                                 1 if fault.startswith("between-") else 0)
                self.assertTrue(self.adapter.invalid)
                self.assertTrue((self.root / "claim").exists())

    def test_aligned_partial_window_end_to_end(self):
        data = bytes(range(256)) * 10  # 1024 + 1024 + 512, not a full last window.
        self.image.write_bytes(data)
        proc = Processes()
        adapter = module.AndroidUserdata("SYNTHETIC", self.root, proc)
        directory, record_pin = test_backup(self.root, len(data), "partial-backup")
        result = module.execute(self.image, "SYNTHETIC", True, self.root / "claim",
                                adapter, size=len(data), expected=module.digest(data), window=1024,
                                backup_dir=directory, backup_record_sha256=record_pin)
        self.assertEqual(result["windows"], 3)
        self.assertEqual((proc.writes, proc.reads), (3, 6))
        writes = [shlex.split(a[6])[0] for a in proc.calls if a[3:6] == ["shell", "su", "-c"]
                  and "conv=notrunc,fsync" in a[6]]
        self.assertIn("count=1 seek=4 conv=notrunc,fsync", writes[-1])

    def test_actual_tail_geometry_and_adapter_bounds(self):
        windows = module.window_geometry(module.SIZE, module.WINDOW)
        self.assertEqual(len(windows), 126)
        offset, length = windows[-1]
        self.assertEqual((offset, length), (125 * module.WINDOW, 55 * 1024 * 1024))
        proc = Processes()
        adapter = module.AndroidUserdata("SYNTHETIC", self.root, proc)
        # This direct adapter bounds test uses a synthetic full-range identity
        # record, not a claimed 8GB host backup. execute()/CLI validate the actual
        # host file independently; BackupTests exercise that admission gate.
        identity = module.AndroidUserdata("SYNTHETIC", self.root, Processes(),
                                         read_only=True, backup_only=True)
        identity.bind_backup_source()
        record = json.loads((self.backup_dir / module.BACKUP_RECORD).read_text())
        record["bytes"] = module.SIZE
        record["binding_sha256"] = module.backup_identity(identity, record["nonce"], module.SIZE)
        adapter.preflight("SYNTHETIC", backup=record)
        data = b"\xa5" * length  # Only the actual 55MiB tail; no 8GB source hash.
        before = len(proc.calls)
        for bad_offset, bad_data in ((offset + 1, data), (offset, data[:-1]),
                                     (offset + 512, data), (offset, b"")):
            with self.assertRaisesRegex(ValueError, "^write bounds$"):
                adapter.write("SYNTHETIC", bad_offset, bad_data)
            self.assertEqual(len(proc.calls), before)
        self.assertEqual(adapter.write("SYNTHETIC", offset, data), (length, True))
        self.assertEqual(adapter.read("SYNTHETIC", offset, length), data)
        self.assertEqual((proc.writes, proc.reads), (1, 1))

    def test_inspect_cli_zero_write_contract(self):
        for fault in (None, "staging-missing", "staging-full", "staging-disk"):
            with self.subTest(fault=fault):
                proc = Processes(fault)
                with patch("sys.argv", ["installer", "inspect", "--serial", "SYNTHETIC",
                                        "--staging-root", "/dev"]), \
                        patch.object(module.subprocess, "run", side_effect=proc), \
                        patch.object(module.Path, "mkdir", side_effect=AssertionError("no mkdir")), \
                        patch.object(module.Path, "open", side_effect=AssertionError("no host output")), \
                        patch.object(module, "claim", side_effect=AssertionError("no claim")):
                    if fault:
                        with self.assertRaises(SystemExit) as stopped:
                            module.main()
                        self.assertEqual(stopped.exception.code, 1)
                    else:
                        module.main()
                self.assertEqual(proc.writes, 0)
                self.assertFalse(proc.final)
                for argv in proc.calls:
                    args = argv[3:]
                    self.assertNotIn(args[0], ("push", "pull"))
                    self.assertNotEqual(args[:2], ["shell", "mkdir"])
                    if args[:3] in (["shell", "su", "-c"], ["exec-out", "su", "-c"]):
                        script = shlex.split(args[3])[0] if args[0] == "shell" else args[3]
                        code = "\n".join(line for line in script.splitlines()
                                         if not line.lstrip().startswith("#"))
                        for forbidden in (" of=", "conv=", "drop_caches", " > "):
                            self.assertNotIn(forbidden, code)
                        self.assertNotRegex(code, r"(?m)^\s*(?:mkdir|sync|mount|tee)(?:\s|$)")
                        result = subprocess.run(["sh", "-n"], input=script.encode(),
                                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        self.assertEqual(result.returncode, 0, result.stderr)
        with patch("sys.argv", ["installer", "inspect"]), \
                patch.object(module.subprocess, "run", side_effect=AssertionError("no process")) as runner:
            with self.assertRaisesRegex(ValueError, "inspect requires explicit serial"):
                module.main()
            runner.assert_not_called()
        AdapterTests.test_cli_default_dryrun_and_unauthorized_no_process(self)

    def test_actual_exclusion_shell_on_host_fixtures(self):
        live = "123 (sh) S 1 1 1 0 -1 4194560\n"
        zombie = "689 (pigz) Z 1 1 1 0 -1 4194560\n"
        # (stat text, mountinfo, expected rc). stat: None = absent, "dir" =
        # unreadable. mountinfo: "clean", "hit", None = absent, "dir" = read
        # error like the device EINVAL. 0 = clean or zombie skip, 81 = mount
        # hit, 82 = live dd, 84 = stat read/parse failure, 1 = other failures.
        cases = {
            None: (live, "clean", 0),
            "mount": (live, "hit", 81),
            "target-fd": (live, "clean", 1),
            "parent-fd": (live, "clean", 1),
            "swap": (live, "clean", 1),
            "parent-swap": (live, "clean", 1),
            "missing-mountinfo": (live, None, 1),
            "mountinfo-error": (live, "dir", 1),
            "writer": (live, "clean", 82),
            "zombie": (zombie, "dir", 0),
            "zombie-comm-parens": ("689 (pigz worker (789)) Z 1 1 1 0 -1\n", "dir", 0),
            "live-comm-parens-mount": ("689 (pigz worker (789)) R 1 1 1 0 -1\n", "hit", 81),
            "absent-stat": (None, "clean", 84),
            "unreadable-stat": ("dir", "clean", 84),
        }
        for fault, (stat_text, mountinfo, expected) in cases.items():
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                proc = root / "proc"
                process = proc / "123"
                (process / "fd").mkdir(parents=True)
                target, parent = root / "userdata", root / "disk"
                target.touch()
                parent.touch()
                if stat_text == "dir":
                    (process / "stat").mkdir()
                elif stat_text is not None:
                    (process / "stat").write_text(stat_text)
                if mountinfo == "dir":
                    (process / "mountinfo").mkdir()
                elif mountinfo is not None:
                    line = "1 0 65:32 / /alias rw - ext4 /alias rw\n" if mountinfo == "hit" \
                        else "1 0 0:1 / /fixture rw - tmpfs tmpfs rw\n"
                    (process / "mountinfo").write_text(line)
                (proc / "swaps").write_text("Filename Type Size Used Priority\n")
                if fault in ("target-fd", "parent-fd"):
                    (process / "fd/7").symlink_to(target if fault == "target-fd" else parent)
                if fault in ("swap", "parent-swap"):
                    alias = root / "swap-alias"
                    alias.symlink_to(target if fault == "swap" else parent)
                    (proc / "swaps").write_text(f"Filename Type Size Used Priority\n{alias} partition 1 0 -1\n")
                prefix = (f"target={shlex.quote(str(target))}\n"
                          f"parent_target={shlex.quote(str(parent))}\n"
                          f"pidof() {{ return {0 if fault == 'writer' else 1}; }}\n")
                result = subprocess.run(["sh", "-eu", "-c", prefix +
                                         module.userdata_exclusion_script("65:32", proc)],
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                self.assertEqual(result.returncode, expected, result.stderr)

    def test_actual_staging_shell_on_host_fixtures(self):
        for state in ("ok", "missing", "not-tmpfs", "insufficient", "symlink"):
            with self.subTest(state=state), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / "staging"
                if state != "missing":
                    root.mkdir()
                if state == "symlink":
                    root = Path(tmp) / "alias"
                    root.symlink_to(Path(tmp) / "staging")
                adapter = module.AndroidUserdata("SYNTHETIC", self.root,
                                                staging_root=str(root), read_only=True)
                # Real shell/readlink/branching; stat's filesystem/capacity
                # responses are mocked. This is NOT an Android tmpfs test.
                prefix = f'''
stat() {{
 case "$3" in
  %T) echo {'ext4' if state == 'not-tmpfs' else 'tmpfs'};;
  %a) echo {1 if state == 'insufficient' else 262144};;
  %S) echo 4096;;
  *) return 2;;
 esac
}}
'''
                probe = subprocess.run(["sh", "-eu", "-c", prefix + adapter.staging_script(emit=True)],
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                self.assertEqual(probe.returncode, 0, probe.stderr)
                self.assertEqual(probe.stdout.decode().split(":")[0], state)
                gate = subprocess.run(["sh", "-eu", "-c", prefix + adapter.staging_script()],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                self.assertEqual(gate.returncode == 0, state == "ok")


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        diagnostic_patch = patch.object(module, "DIAGNOSTICS", self.root / "diagnostics")
        diagnostic_patch.start()
        self.addCleanup(diagnostic_patch.stop)
        self.directory = self.root / "backup"
        self.image = self.root / "installation-image"
        self.data = bytes(range(256)) * 4
        self.image.write_bytes(self.data)
        self.pin = module.digest(self.data)

    def source(self, fault=None, read_only=True):
        proc = Processes(fault)
        proc.extents[0, 512] = proc.extents[512, 512] = b"B" * 512
        adapter = module.AndroidUserdata("SYNTHETIC", self.root, proc,
                                        read_only=read_only, backup_only=read_only)
        return adapter, proc

    def backup(self, fault=None):
        self.adapter, self.proc = self.source(fault)
        return module.create_backup(self.adapter, self.directory, size=1024, window=512)

    def install(self, proc, record_pin=None, directory=None, image=None):
        adapter = module.AndroidUserdata("SYNTHETIC", self.root, proc)
        result = module.execute(image or self.image, "SYNTHETIC", True, self.root / "claim",
                                adapter, size=1024, expected=self.pin, window=512,
                                backup_dir=directory, backup_record_sha256=record_pin)
        return result

    def test_success_two_pass_backup_and_bound_write(self):
        result = self.backup()
        self.assertEqual(result["scope"], "userdata-prefix-only")
        self.assertEqual(result["sha256"], module.digest(b"B" * 1024))
        self.assertNotEqual(result["sha256"], self.pin)
        self.assertEqual((self.proc.reads, self.proc.writes), (4, 0))
        record = json.loads((self.directory / module.BACKUP_RECORD).read_text())
        self.assertEqual(record["second_read_sha256"], result["sha256"])
        self.assertEqual(record["gpt_sha256"], self.adapter.gpt_pin)
        self.assertEqual((record["offset"], record["bytes"]), (0, 1024))
        raw = (self.directory / module.BACKUP_RECORD).read_text()
        self.assertNotIn("SYNTHETIC", raw)
        self.assertNotIn("synthetic-boot", raw)
        self.assertEqual((self.directory / module.BACKUP_FILE).read_bytes(), b"B" * 1024)
        for argv in self.proc.calls:
            self.assertNotEqual(argv[3:5], ["shell", "mkdir"])
            self.assertNotIn(argv[3], ("push", "pull"))
            if argv[3:6] in (["shell", "su", "-c"], ["exec-out", "su", "-c"]):
                command = shlex.split(argv[6])[0] if argv[3] == "shell" else argv[6]
                self.assertNotIn("check_staging", command)
                self.assertNotIn("drop_caches", command)
                self.assertNotIn(" of=", command)
                self.assertNotIn("conv=", command)
                parsed = subprocess.run(["sh", "-n"], input=command.encode(),
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                self.assertEqual(parsed.returncode, 0, parsed.stderr)
        _, proc = self.source(read_only=False)
        installed = self.install(proc, result["record_sha256"], self.directory)
        self.assertEqual(installed["windows"], 2)
        self.assertEqual((proc.writes, proc.reads), (2, 4))

    def test_short_or_different_reads_never_complete(self):
        for fault, reason in (("backup-short", "short read-only device read"),
                              ("backup-second-short", "short read-only device read"),
                              ("backup-different", "second backup read size/hash mismatch"),
                              ("backup-boot-change", "backup target/session changed")):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as tmp:
                self.directory = Path(tmp) / "backup"
                with self.assertRaises(ValueError) as raised:
                    self.backup(fault)
                self.assertEqual(str(raised.exception), reason)
                self.assertFalse((self.directory / module.BACKUP_RECORD).exists())
                self.assertEqual(self.proc.writes, 0)
                self.assertTrue(self.adapter.invalid)

    def test_host_space_and_exclusive_output_before_process(self):
        self.adapter, self.proc = self.source()
        with patch.object(module.shutil, "disk_usage", return_value=SimpleNamespace(free=1)):
            with self.assertRaisesRegex(ValueError, "^insufficient host backup space$"):
                module.create_backup(self.adapter, self.directory, size=1024, window=512)
        self.assertEqual(self.proc.calls, [])
        self.assertFalse(self.directory.exists())
        self.directory.mkdir()
        with self.assertRaisesRegex(ValueError, "^exclusive backup output required$"):
            module.create_backup(self.adapter, self.directory, size=1024, window=512)
        self.assertEqual(self.proc.calls, [])

    def test_backup_wrong_target_or_writer_refused(self):
        for fault in ("product", "byname", "capacity", "holders", "backup-writer"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as tmp:
                self.directory = Path(tmp) / "backup"
                with self.assertRaises(ValueError):
                    self.backup(fault)
                self.assertFalse((self.directory / module.BACKUP_RECORD).exists())
                self.assertEqual((self.proc.reads, self.proc.writes), (0, 0))

    def test_missing_backup_or_bad_local_file_zero_calls(self):
        _, proc = self.source(read_only=False)
        with self.assertRaisesRegex(ValueError, "^verified backup required$"):
            self.install(proc)
        self.assertEqual(proc.calls, [])
        self.assertFalse((self.root / "claim").exists())
        with self.assertRaisesRegex(ValueError, "^verified backup required$"):
            module.AndroidUserdata("SYNTHETIC", self.root, proc).write("SYNTHETIC", 0, b"A" * 512)
        self.assertEqual(proc.calls, [])
        result = self.backup()
        (self.directory / module.BACKUP_FILE).write_bytes(b"C" * 1024)
        with self.assertRaisesRegex(ValueError, "^backup local hash mismatch$"):
            self.install(proc, result["record_sha256"], self.directory)
        self.assertEqual(proc.calls, [])
        self.assertFalse((self.root / "claim").exists())

    def test_current_boot_or_gpt_mismatch_no_staging_or_write(self):
        result = self.backup()
        for kind in ("boot", "gpt"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                self.root = Path(tmp)
                _, proc = self.source("other-gpt" if kind == "gpt" else None, read_only=False)
                if kind == "boot":
                    proc.snapshot[10] = "different-boot"
                with self.assertRaisesRegex(ValueError, "^current target does not match backup binding$"):
                    self.install(proc, result["record_sha256"], self.directory)
                self.assertEqual(proc.writes, 0)
                self.assertFalse(any(a[3:5] == ["shell", "mkdir"] or a[3] == "push" for a in proc.calls))
                self.assertTrue((self.root / "claim").exists())

    def test_no_installation_image_reuse(self):
        result = self.backup()
        _, proc = self.source(read_only=False)
        with self.assertRaisesRegex(ValueError, "^backup must not reuse installation image$"):
            self.install(proc, result["record_sha256"], self.directory,
                         image=self.directory / module.BACKUP_FILE)
        self.assertEqual(proc.calls, [])

    def test_cli_default_and_missing_gates_zero_process(self):
        AdapterTests.test_cli_default_dryrun_and_unauthorized_no_process(self)
        for argv in (["backup"], ["backup", "--serial", "SYNTHETIC"],
                     ["write", "--serial", "SYNTHETIC", "--authorize-userdata-write-this-round",
                      "--exclusive-offline-userdata", "--reviewed-and-independently-verified",
                      "--manifest", "unused", "--executor-sha256",
                      module.digest(Path(module.__file__).read_bytes())]):
            with self.subTest(argv=argv), patch("sys.argv", ["installer", *argv]), \
                    patch.object(module.subprocess, "run", side_effect=AssertionError("no process")) as runner:
                with self.assertRaises(ValueError):
                    module.main()
                runner.assert_not_called()


class NoBackupTests(unittest.TestCase):
    def setUp(self):
        out = Path(__file__).resolve().parents[1] / "out"
        self.tmp = tempfile.TemporaryDirectory(prefix="userdata-no-backup-test-", dir=out)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.image = self.root / "image"
        self.data = bytes(range(256)) * 4
        self.image.write_bytes(self.data)
        self.pin = module.digest(self.data)
        diagnostic_patch = patch.object(module, "DIAGNOSTICS", self.root / "diagnostics")
        diagnostic_patch.start()
        self.addCleanup(diagnostic_patch.stop)

    def run_write(self, authorized=True, without_backup=True, fault=None):
        self.proc = Processes(fault)
        self.adapter = module.AndroidUserdata("SYNTHETIC", self.root, self.proc)
        return module.execute(self.image, "SYNTHETIC", authorized, self.root / "claim",
                              self.adapter, size=1024, expected=self.pin, window=512,
                              without_backup=without_backup)

    def test_default_backup_and_explicit_authorization(self):
        with self.assertRaisesRegex(ValueError, "^verified backup required$"):
            self.run_write(without_backup=False)
        self.assertEqual(self.proc.calls, [])
        with self.assertRaisesRegex(ValueError, "authorization and serial required"):
            self.run_write(authorized=False)
        self.assertEqual(self.proc.calls, [])
        self.assertFalse((self.root / "claim").exists())
        with self.assertRaisesRegex(ValueError, "backup and waiver are mutually exclusive"):
            module.execute(self.image, "SYNTHETIC", True, self.root / "claim", self.adapter,
                           size=1024, expected=self.pin, window=512, without_backup=True,
                           backup_dir=self.root / "must-not-read", backup_record_sha256="0" * 64)
        self.assertEqual(self.proc.calls, [])
        with patch.object(module, "validate_backup", side_effect=AssertionError("no backup reads")):
            self.assertEqual(self.run_write()["windows"], 2)
        events = [json.loads(line) for line in (self.root / "events.jsonl").read_text().splitlines()]
        self.assertEqual(events[0], dict(event="backup-policy", policy="without-backup",
                                        explicit_user_choice=True, userdata_rollback=False,
                                        backed_up=False))
        self.assertEqual((self.proc.writes, self.proc.reads), (2, 4))
        self.assertTrue(self.proc.final)
        count = len(self.proc.calls)
        with self.assertRaises(FileExistsError):
            module.execute(self.image, "SYNTHETIC", True, self.root / "claim", self.adapter,
                           size=1024, expected=self.pin, window=512, without_backup=True)
        self.assertEqual(len(self.proc.calls), count)

    def test_tools_failure_or_boot_change_before_mkdir(self):
        for fault in ("tools-fail", "tools-boot-change"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory(dir=self.root) as tmp:
                root = self.root
                self.root = Path(tmp)
                with self.assertRaises(ValueError):
                    self.run_write(fault=fault)
                self.assertEqual(self.proc.writes, 0)
                self.assertFalse(any(a[3:5] == ["shell", "mkdir"] or a[3] == "push"
                                     for a in self.proc.calls))
                if fault == "tools-fail":
                    self.assertEqual(self.adapter.failure["stage"], "tools-inspect")
                    self.assertEqual(self.adapter.failure["returncode"], 85)
                self.root = root

    def test_windows_exe_push_uses_real_wslpath_only_for_host(self):
        proc = Processes()
        observed, mapping = [], {}
        def runner(argv, **kwargs):
            observed.append(argv[:])
            if argv[0] == "wslpath":
                # Actual LOCAL wslpath; all adb.exe/fastboot commands stay fake.
                result = subprocess.run(argv, **kwargs)
                mapping[result.stdout.decode().strip()] = argv[-1]
                return result
            synthetic = argv[:]
            if argv[3] == "push":
                self.assertIn(argv[4], mapping)
                self.assertTrue(argv[5].startswith("/tmp/nuwa-userdata-"))
                self.assertTrue(argv[5].endswith("/input.raw"))
                synthetic[4] = mapping[argv[4]]  # Fixture filesystem only.
            return proc(synthetic, **kwargs)
        host = self.root / "host space"
        host.mkdir()
        adapter = module.AndroidUserdata("SYNTHETIC", host, runner, adb="/mnt/c/tools/adb.exe")
        module.execute(self.image, "SYNTHETIC", True, self.root / "claim", adapter,
                       size=1024, expected=self.pin, window=512, without_backup=True)
        pushes = [a for a in observed if len(a) > 3 and a[3] == "push"]
        self.assertEqual(len(pushes), 2)
        for argv in pushes:
            self.assertRegex(argv[4], r"^[Dd]:\\")
            self.assertIn("host space\\input.raw", argv[4])
            self.assertEqual(argv[1:3], ["-s", "SYNTHETIC"])
        self.assertEqual(sum(a[0] == "wslpath" for a in observed), 2)

    def test_redacted_persistent_process_diagnostics(self):
        secret, boot = "SYNTHETIC", "12345678-1234-1234-1234-123456789abc"
        binary = b"\x00SYNTHETIC\xffbinary-output"
        for kind in ("nonzero", "stderr", "timeout", "exception"):
            with self.subTest(kind=kind):
                def runner(argv, **kwargs):
                    if kind == "timeout":
                        raise subprocess.TimeoutExpired(argv, 9, output=binary,
                                                        stderr=f"{secret} {boot}".encode())
                    if kind == "exception":
                        raise OSError(f"failed to open {secret} {boot}")
                    return subprocess.CompletedProcess(argv, 7 if kind == "nonzero" else 0,
                                                       binary, (f"{secret} {boot} " * 200).encode())
                adapter = module.AndroidUserdata(secret, self.root, runner, read_only=True)
                adapter.stage = "probe-read"
                with self.assertRaises(ValueError):
                    adapter.call("adb", ["exec-out", "su", "-c", f"read {boot}"])
                fact = adapter.failure
                saved = Path(fact["diagnostic_file"]).read_text()
                for value in (secret, boot, "binary-output"):
                    self.assertNotIn(value, saved)
                    self.assertNotIn(value, json.dumps(fact))
                self.assertLessEqual(len(fact["stderr"]), 2048)
                self.assertEqual(fact["argv"][2], "<REDACTED>")
                if kind != "exception":
                    self.assertEqual(fact["stdout_bytes"], len(binary))
                    self.assertEqual(fact["stdout_sha256"], module.digest(binary))
                if kind in ("nonzero", "stderr"):
                    self.assertEqual(fact["returncode"], 7 if kind == "nonzero" else 0)
                if kind == "timeout":
                    self.assertEqual(fact["exception"], "TimeoutExpired")
                    self.assertEqual(fact["reason"], "subprocess timeout; completion unknown")
                self.assertTrue(adapter.invalid)

    def test_host_fsync_failure_has_stage_and_durable_diagnostic(self):
        original = module.os.fsync
        first = True
        def fsync(fd):
            nonlocal first
            if first:
                first = False
                raise OSError("fsync failed for SYNTHETIC")
            return original(fd)
        with patch.object(module.os, "fsync", side_effect=fsync):
            with self.assertRaises(OSError):
                self.run_write()
        self.assertEqual(self.proc.calls, [])
        self.assertEqual(self.adapter.failure["stage"], "run-claim")
        self.assertEqual(self.adapter.failure["exception"], "OSError")
        saved = Path(self.adapter.failure["diagnostic_file"]).read_text()
        self.assertNotIn("SYNTHETIC", saved)

    def test_cli_waiver_requires_all_existing_write_gates(self):
        for extra in ([], ["--authorize-userdata-write-this-round"]):
            with patch("sys.argv", ["installer", "write", "--without-backup",
                                    "--serial", "SYNTHETIC", *extra]), \
                    patch.object(module.subprocess, "run", side_effect=AssertionError("no process")) as run:
                with self.assertRaises(ValueError):
                    module.main()
                run.assert_not_called()
        proc = Processes()
        original = module.execute
        def tiny_execute(*args, **kwargs):
            return original(*args, **kwargs, size=1024, expected=self.pin, window=512)
        argv = ["installer", "write", "--without-backup", "--serial", "SYNTHETIC",
                "--authorize-userdata-write-this-round", "--exclusive-offline-userdata",
                "--reviewed-and-independently-verified", "--manifest", "synthetic-manifest",
                "--executor-sha256", module.digest(Path(module.__file__).read_bytes())]
        with patch("sys.argv", argv), patch.object(module, "CLAIM", self.root / "claim"), \
                patch.object(module, "frozen_image", return_value=self.image), \
                patch.object(module, "execute", side_effect=tiny_execute), \
                patch.object(module.subprocess, "run", side_effect=proc), \
                patch.object(module, "validate_backup", side_effect=AssertionError("no backup read")), \
                redirect_stdout(io.StringIO()):
            module.main()
        self.assertEqual((proc.writes, proc.reads), (2, 4))

    def test_waiver_preserves_fail_closed_write_and_readback(self):
        for fault in ("holders", "gpt-crc", "short-write", "writer-open", "read-hash", "final-hash"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory(dir=self.root) as tmp:
                root = self.root
                self.root = Path(tmp)
                with self.assertRaises(ValueError):
                    self.run_write(fault=fault)
                self.assertTrue(self.adapter.invalid)
                self.assertTrue((self.root / "claim").exists())
                self.assertLessEqual(self.proc.writes, 2 if fault == "final-hash" else 1)
                if fault in ("short-write", "writer-open"):
                    self.assertEqual(self.proc.reads, 0)
                    self.assertNotIn('"event": "writer-closed"',
                                     (self.root / "events.jsonl").read_text())
                self.root = root

    def test_host_input_open_failure_does_not_disappear(self):
        with patch.object(module.Path, "write_bytes", side_effect=OSError("open failed SYNTHETIC")):
            with self.assertRaises(OSError):
                self.run_write()
        self.assertEqual(self.proc.writes, 0)
        self.assertEqual(self.adapter.failure["stage"], "window-host-input")
        self.assertEqual(self.adapter.failure["exception"], "OSError")
        self.assertNotIn("SYNTHETIC", Path(self.adapter.failure["diagnostic_file"]).read_text())


class TextProtocolTests(unittest.TestCase):
    setUp = NoBackupTests.setUp
    # Shape of confirmed 146-byte device response, with a synthetic same-length
    # UUID. Its SHA is intentionally NOT the real private-UUID capture SHA.
    SNAPSHOT = (
        b"/dev/block/sda32\r\nsda32\r\nsda\r\n259:16\r\n32\r\n24887808\r\n"
        b"469917144\r\n240597577728\r\n253340155904\r\n4096\r\n"
        b"00000000-0000-0000-0000-000000000000\r\n\r\nNUWA_OK\r\n"
    )

    def response(self, payload, rc=0, stderr=b"", read_only=True):
        def runner(argv, **kwargs):
            if hasattr(kwargs["stdout"], "write"):
                kwargs["stdout"].write(payload)
                stdout = None
            else:
                stdout = payload
            return subprocess.CompletedProcess(argv, rc, stdout, stderr)
        adapter = module.AndroidUserdata("SYNTHETIC", self.root, runner, read_only=read_only)
        adapter.privileged_shell = "su"  # Isolate protocol parsing from UID selection.
        return adapter

    def test_confirmed_shape_lf_crlf_and_original_diagnostic_hash(self):
        self.assertEqual(len(self.SNAPSHOT), 146)
        self.assertEqual(self.SNAPSHOT.count(b"\r\n"), 13)
        self.assertEqual(self.SNAPSHOT.count(b"\n") - self.SNAPSHOT.count(b"\r\n"), 0)
        normalized = self.SNAPSHOT.replace(b"\r\n", b"\n")
        for payload in (self.SNAPSHOT, normalized):
            with self.subTest(crlf=payload == self.SNAPSHOT):
                adapter = self.response(payload)
                fields = adapter.snapshot()
                self.assertEqual(len(fields), 11)
                self.assertEqual(fields[:5], ("/dev/block/sda32", "sda32", "sda", "259:16", "32"))
                self.assertEqual(adapter.last_call[2].stdout, payload)
                diagnostic = adapter.diagnostic(ValueError("host diagnostic probe"))
                self.assertEqual(diagnostic["stdout_bytes"], len(payload))
                self.assertEqual(diagnostic["stdout_sha256"], module.digest(payload))
        self.assertNotEqual(module.digest(normalized), module.digest(self.SNAPSHOT))

    def test_missing_fake_or_trailing_footer_rejected(self):
        for payload in (b"payload\r\n", b"NUWA_OK\r\n", b"payload\r\nNUWA_OKAY\r\n",
                        b"payload\r\nNUWA_OK\r\ntrailer", b"payload\rNUWA_OK\r",
                        b"payload\r\nNUWA_OK", b"payload\r\nnot-NUWA_OK\r\n"):
            with self.subTest(payload=payload):
                with self.assertRaisesRegex(ValueError, "^missing remote completion$"):
                    self.response(payload).shell("identity probe")

    def test_ascii_fields_rc_and_stderr_gates_retained(self):
        with self.assertRaises(UnicodeDecodeError):
            self.response(b"\xff\r\n\r\nNUWA_OK\r\n").shell("identity probe")
        bad = self.SNAPSHOT.replace(b"240597577728\r\n", b"512\r\n")
        with self.assertRaisesRegex(ValueError, "^userdata sysfs/physical capacity or start mismatch$"):
            self.response(bad).snapshot()
        with self.assertRaisesRegex(ValueError, "^userdata binding response$"):
            self.response(b"one-field\r\n\r\nNUWA_OK\r\n").snapshot()
        for rc, stderr in ((1, b""), (0, b"warning")):
            with self.subTest(rc=rc):
                adapter = self.response(self.SNAPSHOT, rc, stderr)
                with self.assertRaisesRegex(ValueError, "device process failed; no retry"):
                    adapter.snapshot()
                self.assertEqual(adapter.failure["returncode"], rc)
                self.assertEqual(adapter.failure["stdout_bytes"], 146)
                self.assertEqual(adapter.failure["stdout_sha256"], module.digest(self.SNAPSHOT))

    def test_exec_out_binary_memory_and_file_paths_unchanged(self):
        payload = ((b"\x00\r\nNUWA_OK\r\n" + bytes(range(256))) * 2)[:512]
        self.assertEqual(len(payload), 512)
        self.assertIn(b"\r\n", payload)
        fields = tuple(self.SNAPSHOT.replace(b"\r\n", b"\n")[:-len(b"\nNUWA_OK\n")]
                       .decode().strip().splitlines())
        for read_only in (True, False):
            with self.subTest(read_only=read_only):
                adapter = self.response(payload, read_only=read_only)
                adapter.binding = fields
                result = adapter.raw(fields[0], 0, 512, "binary-data")
                self.assertEqual(result, payload)
                self.assertEqual(module.digest(result), module.digest(payload))

    def test_physical_gpt_with_crlf_in_binary_guid_unchanged(self):
        proc = Processes()
        offset = 31 * 128 + 16  # Actual synthetic userdata entry's unique GUID.
        proc.table[offset:offset + 16] = b"\r\n" + b"U" * 14
        adapter = module.AndroidUserdata("SYNTHETIC", self.root, proc, read_only=True)
        adapter.binding = tuple(proc.snapshot)
        adapter.physical_gpt()
        expected = module.digest(proc.header(1) + proc.header(proc.last) + bytes(proc.table))
        self.assertEqual(adapter.gpt_pin, expected)
        self.assertIn(b"\r\n", proc.table)

    def test_all_shell_consumers_with_lf_and_crlf_binary_image(self):
        # Snapshot, tools, guards, staging, upload check, writer status/closure,
        # sync and final gate all pass through shell(); exec-out is not rewritten.
        self.data = ((b"\x00\r\n\nNUWA_OK\r\n" + bytes(range(32))) * 32)[:1024]
        self.image.write_bytes(self.data)
        for crlf in (False, True):
            with self.subTest(crlf=crlf), tempfile.TemporaryDirectory(dir=self.root) as tmp:
                root = Path(tmp)
                proc = Processes()
                def runner(argv, **kwargs):
                    result = proc(argv, **kwargs)
                    if crlf and argv[3:6] == ["shell", "su", "-c"]:
                        result.stdout = result.stdout.replace(b"\n", b"\r\n")
                    return result
                adapter = module.AndroidUserdata("SYNTHETIC", root, runner)
                result = module.execute(self.image, "SYNTHETIC", True, root / "claim", adapter,
                                        size=1024, expected=module.digest(self.data),
                                        window=512, without_backup=True)
                self.assertEqual(result["sha256"], module.digest(self.data))
                self.assertEqual((proc.writes, proc.reads), (2, 4))
                self.assertTrue(proc.final)
                events = [json.loads(line) for line in (root / "events.jsonl").read_text().splitlines()]
                self.assertEqual(sum(e["event"] == "writer-closed" for e in events), 2)


class PushSummaryTests(unittest.TestCase):
    """adb push reports completion on stderr; only one exact, sized line is accepted."""
    LINE = "C:\\host\\input.raw: 1 file pushed, 0 skipped. 152.5 MB/s ({} bytes in 0.420s)"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        diagnostic_patch = patch.object(module, "DIAGNOSTICS", self.root / "diagnostics")
        diagnostic_patch.start()
        self.addCleanup(diagnostic_patch.stop)

    def push(self, stderr, push_bytes=1024, rc=0):
        def runner(argv, **kwargs):
            return subprocess.CompletedProcess(argv, rc, b"", stderr)
        adapter = module.AndroidUserdata("SYNTHETIC", self.root, runner)
        return adapter, lambda: adapter.call(
            "adb", ["push", "C:\\host\\input.raw", "/remote/input.raw"], push_bytes=push_bytes)

    def rejected(self, adapter, call):
        with self.assertRaisesRegex(ValueError, "^device process failed; no retry"):
            call()
        self.assertTrue(adapter.invalid)
        self.assertEqual(adapter.failure["stage"], "adapter-init")
        self.assertEqual(adapter.failure["reason"],
                         "push summary/byte count unconfirmed; completion unknown")

    def test_single_summary_line_with_exact_bytes_accepted(self):
        for eol in (b"\r\n", b"\n"):  # CRLF is the observed Windows adb.exe shape.
            with self.subTest(eol=eol):
                adapter, call = self.push(self.LINE.format(1024).encode() + eol)
                self.assertEqual(call(), b"")
                self.assertFalse(adapter.invalid)
                self.assertIsNone(adapter.failure)
                self.assertEqual(adapter.last_call[2].stderr,
                                 self.LINE.format(1024).encode() + eol)

    def test_byte_count_mismatch_rejected(self):
        for reported in (0, 1023, 1025, 67108864):
            with self.subTest(reported=reported):
                adapter, call = self.push(self.LINE.format(reported).encode() + b"\r\n")
                self.rejected(adapter, call)

    def test_extra_or_foreign_stderr_rejected(self):
        line = self.LINE.format(1024).encode()
        for stderr in (b"\r\n" + line + b"\r\n",  # leading blank line
                       b"wsl: proxy warning\r\n" + line + b"\r\n",  # WSL text mixed in
                       line + b"\r\nadb: warning\r\n",
                       line + b"\r\n" + line + b"\r\n",
                       line + b" trailing",
                       line + b"\r",
                       b"",  # No positive completion at all.
                       b"C:\\host\\input.raw: 2 files pushed, 0 skipped. 152.5 MB/s (1024 bytes in 0.420s)\r\n",
                       b"C:\\host\\input.raw: 1 file pushed, 1 skipped. 152.5 MB/s (1024 bytes in 0.420s)\r\n",
                       b"C:\\host\\input.raw: 1 file pushed, 0 skipped. 152.5 MB/s\r\n"):
            with self.subTest(stderr=stderr):
                adapter, call = self.push(stderr)
                self.rejected(adapter, call)

    def test_nonzero_returncode_with_summary_rejected(self):
        adapter, call = self.push(self.LINE.format(1024).encode() + b"\r\n", rc=1)
        self.rejected(adapter, call)
        self.assertEqual(adapter.failure["returncode"], 1)

    def test_other_calls_keep_strict_stderr_contract(self):
        def runner(stderr):
            return lambda argv, **kwargs: subprocess.CompletedProcess(
                argv, 0, b"List of devices attached\r\n", stderr)
        adapter = module.AndroidUserdata("SYNTHETIC", self.root, runner(b"warning\r\n"))
        with self.assertRaisesRegex(ValueError, "^device process failed; no retry"):
            adapter.call("adb", ["devices", "-l"])
        self.assertEqual(adapter.failure["reason"],
                         "device process failed/stderr; completion unknown")
        quiet = module.AndroidUserdata("SYNTHETIC", self.root, runner(b""))
        self.assertEqual(quiet.call("adb", ["devices", "-l"]), b"List of devices attached\r\n")
        self.assertFalse(quiet.invalid)
        # A push summary is not evidence for any non-push call.
        summary = module.AndroidUserdata("SYNTHETIC", self.root,
                                         runner(self.LINE.format(1024).encode() + b"\r\n"))
        with self.assertRaisesRegex(ValueError, "^device process failed; no retry"):
            summary.call("adb", ["shell", "id -u"])


if __name__ == "__main__":
    unittest.main()
