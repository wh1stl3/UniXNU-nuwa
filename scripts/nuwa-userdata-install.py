"""Nuwa-only, one-shot userdata installer. Default plan starts no processes.

Transport patterns: local run-pmap-ret-once.py (root su, synchronous writer,
independent exec-out readback) and .cache/super-window-v1/executor.py
(tmpfs staging, exact dd count, adjacent offline guard). Neither is imported.
"""
import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import struct
import subprocess
import sys
import uuid
import zlib
from pathlib import Path

SIZE = 8446279680
SHA256 = "da429da64b4d91a08b8adb1d3162f8348b37b358509ab1bd5d8bf09abdbf68d7"
CAPACITY = 240597577728
WINDOW = 64 * 1024 * 1024
STAGING_REQUIRED = WINDOW + 32 * 1024 * 1024
FIRST_LBA = 3110976
LAST_LBA = 61850618
LBA_BYTES = 4096
MANIFEST_KEY = "candidate/userdata/userdata-root.img"
CLAIM = Path(__file__).resolve().parents[1] / "out/nuwa-userdata-install.execution.claim"
DIAGNOSTICS = CLAIM.parent / "nuwa-userdata-diagnostics"
BACKUP_FILE = "userdata-prefix.bin"
BACKUP_RECORD = "complete.json"
# adb 1.0.41 (37.0.1-15733141) prints push completion on stderr, with no quiet
# option: "<local>: 1 file pushed, 0 skipped. 152.5 MB/s (67108864 bytes in 0.420s)".
# Only that single line is accepted, and its byte count must match the host file.
PUSH_SUMMARY = re.compile(
    rb"[^\r\n]+: 1 file pushed, 0 skipped\. [0-9.]+ [KMG]?B/s \((\d+) bytes in [0-9.]+s\)$")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def pushed_bytes(stderr):
    """Byte count from exactly one adb push summary line, else None (any extra text fails)."""
    if not isinstance(stderr, (bytes, bytearray)):
        return None
    match = PUSH_SUMMARY.match(bytes(stderr).replace(b"\r\n", b"\n"))
    return int(match.group(1)) if match else None


def failure_detail(exc, stage, private=(), result=None, command=None, argv=None, stdout=None):
    """Bounded facts only: redacted argv, no raw stdout or inferred guard cause."""
    def text(value, limit):
        if isinstance(value, bytes):
            value = value.decode("utf-8", "replace")
        value = str(value)
        for identifier in sorted(set(private), key=len, reverse=True):
            if identifier:
                value = value.replace(identifier, "<REDACTED>")
                value = value.replace(json.dumps(identifier)[1:-1], "<REDACTED>")
        value = re.sub(r"\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b",
                       "<REDACTED-UUID>", value, flags=re.I)
        return value[:limit]
    stderr = getattr(result, "stderr", None) if result is not None else getattr(exc, "stderr", None)
    inventory = command == "devices"
    if stdout is None:
        stdout = getattr(result, "stdout", None) if result is not None else getattr(exc, "output", None)
    captured = stdout is not None
    if isinstance(stdout, str):
        stdout = stdout.encode("utf-8", "replace")
    reason = ("subprocess timeout; completion unknown"
              if isinstance(exc, subprocess.TimeoutExpired) else text(exc, 512))
    return dict(stage=stage, exception=type(exc).__name__, reason=reason,
                command=command, returncode=getattr(result, "returncode", None),
                stderr=("[inventory withheld]" if inventory else text(stderr or b"", 2048)),
                stderr_bytes=len(stderr or b""), completion="unknown",
                client_completion="exited" if result is not None else "unknown",
                argv=[text(arg, 32768) for arg in (argv or [])],
                stdout_bytes=len(stdout) if captured else None,
                stdout_sha256=digest(stdout) if captured else None)


def persist_diagnostic(failure, directory):
    """Separate host journal; never replace the original failure with log I/O."""
    try:
        directory.mkdir(mode=0o700, exist_ok=True)
        path = directory / ("failure-" + uuid.uuid4().hex + ".json")
        with path.open("x", encoding="ascii") as stream:
            json.dump(failure, stream, ensure_ascii=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        sync_directory(directory)
        failure["diagnostic_file"] = str(path)
    except Exception as error:
        failure["diagnostic_write_exception"] = type(error).__name__


def window_geometry(size, window):
    require(size > 0 and window > 0, "invalid geometry")
    return [(offset, min(window, size - offset)) for offset in range(0, size, window)]


def prepare(path, size=SIZE, expected=SHA256, window=WINDOW):
    """Full execution-time source verification; never called by default."""
    require(window > 0 and size > 0, "invalid geometry")
    require(path.is_file() and path.stat().st_size == size, "source size")
    whole = hashlib.sha256()
    windows = []
    with path.open("rb") as source:
        for offset, length in window_geometry(size, window):
            data = source.read(length)
            require(len(data) == length, "short source")
            whole.update(data)
            windows.append((offset, length, digest(data)))
        require(not source.read(1), "long source")
    require(whole.hexdigest() == expected, "source hash")
    return windows


def claim(path):
    """Irrevocably consume the run before any device runner call."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="ascii") as file:
        file.write("consumed\n")
        file.flush()
        os.fsync(file.fileno())
    # Also persist the directory entry on POSIX execution hosts.
    if os.name == "posix":
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def frozen_image(manifest, pin):
    raw = manifest.read_bytes()
    require(re.fullmatch("[0-9a-f]{64}", pin or "") and digest(raw) == pin,
            "frozen manifest hash")
    entry = json.loads(raw)["inputs"][MANIFEST_KEY]
    require(entry["bytes"] == SIZE and entry["sha256"] == SHA256, "manifest image pin")
    # The frozen manifest contains WSL paths: execute from its original WSL host.
    image = Path(entry["path"])
    require(image.is_absolute(), "manifest image path")
    return image


def file_hash(path, size):
    require(not path.is_symlink() and path.is_file() and path.stat().st_size == size,
            "backup file size/type")
    whole = hashlib.sha256()
    count = 0
    with path.open("rb") as stream:
        while data := stream.read(WINDOW):
            count += len(data)
            whole.update(data)
    require(count == size, "backup file changed/short")
    return whole.hexdigest()


def sync_directory(path):
    if os.name == "posix":
        fd = os.open(path, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def backup_identity(adapter, nonce, size):
    """Salted identity binding; never persist raw serial, boot_id or snapshots."""
    require(adapter.binding is not None and hasattr(adapter, "gpt_pin"),
            "backup identity unbound")
    value = dict(nonce=nonce, serial=adapter.serial, product="nuwa", uid=0, slot="_a",
                 binding=adapter.binding, gpt=adapter.gpt_pin, offset=0, bytes=size)
    return digest(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii"))


def validate_backup(directory, record_pin, size, image):
    """Host-only, before claim/device processes. Never trusts a completion bool."""
    require(directory is not None and re.fullmatch("[0-9a-f]{64}", record_pin or ""),
            "verified backup required")
    directory = Path(directory)
    require(not directory.is_symlink() and directory.is_dir(), "backup directory")
    record_path = directory / BACKUP_RECORD
    require(not record_path.is_symlink() and record_path.is_file(), "backup record absent/type")
    raw = record_path.read_bytes()
    require(digest(raw) == record_pin, "backup record pin")
    record = json.loads(raw)
    require(record["schema"] == 1 and record["status"] == "complete"
            and record["scope"] == "userdata-prefix-only" and record["offset"] == 0
            and record["bytes"] == size and record["file"] == BACKUP_FILE
            and record["second_read_bytes"] == size
            and record["second_read_sha256"] == record["sha256"]
            and record["executor_sha256"] == digest(Path(__file__).read_bytes()),
            "backup record scope/completion/source")
    require(all(re.fullmatch("[0-9a-f]{64}", record[k])
                for k in ("sha256", "binding_sha256", "gpt_sha256"))
            and re.fullmatch("[0-9a-f]{32}", record["nonce"]), "backup record hashes")
    data_path = directory / BACKUP_FILE
    require(data_path.resolve() != image.resolve()
            and not (data_path.exists() and image.exists() and os.path.samefile(data_path, image)),
            "backup must not reuse installation image")
    require(file_hash(data_path, size) == record["sha256"], "backup local hash mismatch")
    return record


def create_backup(adapter, directory, *, size=SIZE, window=WINDOW):
    """Read-only DEVICE phase; exclusive host prefix file + second device pass.

    Failed outputs are retained, never marked complete, retried or overwritten.
    No staging dependency, remote mkdir, writer claim or recovery write exists.
    """
    adapter.stage = "backup-output-admission"
    require(adapter.read_only and adapter.backup_only, "backup needs read-only adapter")
    require(0 < size <= CAPACITY and size % 512 == 0 and window > 0 and window % 512 == 0,
            "backup range/alignment")
    directory = Path(directory)
    require(not directory.exists() and not directory.is_symlink()
            and directory.parent.is_dir(), "exclusive backup output required")
    adapter.stage = "backup-host-space"
    require(shutil.disk_usage(directory.parent).free >= size + WINDOW,
            "insufficient host backup space")
    adapter.stage = "backup-output-create"
    directory.mkdir(mode=0o700)  # Exclusive claim of output name, host only.
    sync_directory(directory.parent)
    try:
        adapter.stage = "backup-bind"
        adapter.bind_backup_source()
        nonce = uuid.uuid4().hex
        identity = backup_identity(adapter, nonce, size)
        first_hash = hashlib.sha256()
        count = 0
        with (directory / BACKUP_FILE).open("xb") as stream:
            for offset, length in window_geometry(size, window):
                data = adapter.raw(adapter.binding[0], offset, length, "backup")
                adapter.stage = "backup-host-write"
                require(len(data) == length and stream.write(data) == length, "short backup transfer")
                first_hash.update(data)
                count += len(data)
            adapter.stage = "backup-host-fsync"
            stream.flush()
            os.fsync(stream.fileno())
        require(count == size, "short backup file")
        pin = first_hash.hexdigest()
        adapter.stage = "backup-local-hash"
        require(file_hash(directory / BACKUP_FILE, size) == pin, "backup local hash mismatch")
        adapter.refresh_backup_source()
        second_hash = hashlib.sha256()
        second_count = 0
        for offset, length in window_geometry(size, window):
            data = adapter.raw(adapter.binding[0], offset, length, "backup-second")
            require(len(data) == length, "short second backup read")
            second_hash.update(data)
            second_count += len(data)
        adapter.refresh_backup_source()
        require(second_count == size and second_hash.hexdigest() == pin,
                "second backup read size/hash mismatch")
        require(backup_identity(adapter, nonce, size) == identity, "backup source changed")
        record = dict(schema=1, status="complete", scope="userdata-prefix-only",
                      offset=0, bytes=size, file=BACKUP_FILE, sha256=pin,
                      second_read_bytes=second_count, second_read_sha256=second_hash.hexdigest(),
                      nonce=nonce, binding_sha256=identity, gpt_sha256=adapter.gpt_pin,
                      executor_sha256=digest(Path(__file__).read_bytes()))
        raw = (json.dumps(record, sort_keys=True, indent=2) + "\n").encode("ascii")
        pending = directory / ".complete.pending.json"
        adapter.stage = "backup-record-write"
        with pending.open("xb") as stream:
            require(stream.write(raw) == len(raw), "short backup record")
            stream.flush()
            os.fsync(stream.fileno())
        sync_directory(directory)
        # Publish exclusively only after the complete file and both source
        # passes passed. A pending/partial file is never a completion record.
        completed = directory / BACKUP_RECORD
        adapter.stage = "backup-record-publish"
        os.link(pending, completed)
        try:
            sync_directory(directory)
        except Exception:
            completed.unlink()  # Our exact just-published host marker only.
            raise
        return dict(mode="backup", scope=record["scope"], bytes=size, sha256=pin,
                    record_sha256=digest(raw), device_writes=0)
    except Exception as exc:
        adapter.invalid = True
        adapter.failure = adapter.failure or adapter.diagnostic(exc)
        raise


def gpt_header(data, lba, last, block):
    require(len(data) == block and data[:8] == b"EFI PART", "physical GPT signature")
    revision, length, crc, reserved = struct.unpack_from("<4I", data, 8)
    require(revision == 0x10000 and 92 <= length <= block and reserved == 0,
            "physical GPT header")
    header = bytearray(data[:length])
    header[16:20] = b"\0" * 4
    require(zlib.crc32(header) == crc, "physical GPT header CRC")
    current, backup, first, end = struct.unpack_from("<4Q", data, 24)
    table, count, stride, table_crc = struct.unpack_from("<Q3I", data, 72)
    require(current == lba and backup == (last if lba == 1 else 1)
            and 2 <= first <= end < last and count > 0
            and stride >= 128 and stride % 8 == 0 and count * stride <= 16 * 1024 * 1024,
            "physical GPT geometry")
    sectors = (count * stride + block - 1) // block
    require((lba == 1 and 2 <= table and table + sectors <= first)
            or (lba == last and end < table and table + sectors <= last),
            "physical GPT table bounds")
    return dict(first=first, end=end, guid=data[56:72], table=table,
                count=count, stride=stride, crc=table_crc)


def userdata_exclusion_script(dev, proc="/proc"):
    """Same mount/FD/swap/writer checks in production and isolated host fixtures.

    Caller supplies canonical $target and $parent_target. Only tests replace the
    proc directory; no CLI override exists for the real /proc checks.
    """
    require(re.fullmatch(r"\d+:\d+", dev), "invalid device number")
    root = shlex.quote(str(proc))
    return f'''
for p in {root}/[0-9]*; do
 test -d "$p" || continue
 # Only an explicit zombie state skips this PID: it released every fd, mm and
 # namespace, so it cannot hold the device. A missing/unparsable stat or any
 # other state stays fail-closed; mountinfo is never skipped on read errors.
 state=$(cat "$p/stat") || exit 84
 case $state in *")"*) ;; *) exit 84;; esac
 state=${{state##*)}}
 state=${{state# }}
 state=${{state%% *}}
 case $state in Z) continue;; esac
 test -r "$p/mountinfo"
 if grep -q " {dev} " "$p/mountinfo"; then exit 81; else test "$?" = 1; fi
 for fd in "$p"/fd/*; do
  test -e "$fd" || continue
  link=$(readlink -f "$fd")
  test "$link" != "$target"
  test "$link" != "$parent_target"
 done
done
while read dev rest; do
 test "$dev" = Filename && continue
 swap_target=$(readlink -f "$dev")
 test "$swap_target" != "$target"
 test "$swap_target" != "$parent_target"
done < {root}/swaps
if pidof dd >/dev/null; then exit 82; else test "$?" = 1; fi
'''


class AndroidUserdata:
    """Only subprocess.run is injectable; tests exercise the real command builder.

    Any failed process permanently poisons this adapter. A timeout says nothing
    about remote writer closure. No automatic cleanup, retry or unlock exists.
    """
    def __init__(self, serial, host_dir, runner=None, adb="adb", fastboot="fastboot",
                 staging_root="/tmp", read_only=False, backup_only=False, diagnostics_dir=None):
        require(isinstance(serial, str) and serial and not serial.startswith("-")
                and not any(c.isspace() for c in serial), "explicit serial required")
        require(re.fullmatch(r"/[A-Za-z0-9_/-]+", staging_root)
                and "//" not in staging_root and not staging_root.endswith("/"),
                "canonical absolute staging root required")
        self.serial, self.host = serial, Path(host_dir)
        self.runner, self.adb, self.fastboot = runner or subprocess.run, adb, fastboot
        self.staging_root = staging_root
        self.read_only = read_only
        require(not backup_only or read_only, "backup adapter must be read-only")
        self.backup_only = backup_only
        self.remote = staging_root + "/nuwa-userdata-" + uuid.uuid4().hex
        self.invalid = False
        self.binding = None
        self.privileged_shell = None
        self.sequence = 0
        self.stage = "adapter-init"
        self.failure = None
        self.last_call = None
        self.diagnostics_dir = Path(diagnostics_dir) if diagnostics_dir is not None else DIAGNOSTICS

    def diagnostic(self, exc):
        private = [self.serial]
        if self.binding is not None:
            private.append(self.binding[10])
        if self.failure is None:
            context = self.last_call if self.last_call and self.last_call[0] == self.stage else None
            if context:
                _, argv, result, output = context
                binary = None
                try:
                    if output is not None and output.is_file():
                        binary = output.read_bytes()
                except OSError:
                    pass
                self.failure = failure_detail(exc, self.stage, private, result, argv[3], argv, binary)
            else:
                self.failure = failure_detail(exc, self.stage, private)
            self.persist_failure()
        return self.failure

    def persist_failure(self):
        """Separate HOST-only journal even for read-only device modes.

        Do not put diagnostics into a failed backup output or replace the first
        failure with an exception from diagnostic open/fsync.
        """
        persist_diagnostic(self.failure, self.diagnostics_dir)

    def event(self, name, **fields):
        # Failure argv is already redacted; never store raw outputs/identifiers.
        if self.read_only:
            return
        with (self.host / "events.jsonl").open("a", encoding="ascii") as stream:
            stream.write(json.dumps(dict(event=name, **fields)) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def call(self, tool, args, output=None, timeout=180, push_bytes=None):
        """push_bytes is the expected pushed size; every other call keeps empty-stderr only."""
        require(not self.invalid, "adapter poisoned; no retry")
        result = None
        argv = [tool, "-s", self.serial, *args]
        try:
            if output is None:
                result = self.runner(argv, stdin=subprocess.DEVNULL,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
            else:
                with output.open("xb") as stream:
                    result = self.runner(argv, stdin=subprocess.DEVNULL, stdout=stream,
                                         stderr=subprocess.PIPE, timeout=timeout)
                    stream.flush()
                    os.fsync(stream.fileno())
            if push_bytes is None:
                require(result.returncode == 0 and not result.stderr.strip(),
                        "device process failed/stderr; completion unknown")
            else:
                require(result.returncode == 0 and pushed_bytes(result.stderr) == push_bytes,
                        "push summary/byte count unconfirmed; completion unknown")
            self.last_call = (self.stage, argv, result, output)
            return result.stdout if output is None else b""
        except Exception as exc:
            self.invalid = True
            private = [self.serial] + ([self.binding[10]] if self.binding else [])
            binary = None
            try:
                if output is not None and output.is_file():
                    binary = output.read_bytes()  # Only this bounded window/GPT file.
            except OSError:
                pass
            self.failure = failure_detail(exc, self.stage, private, result, args[0], argv, binary)
            self.persist_failure()  # BEFORE exception conversion/from None.
            try:
                self.event("process-failed", **self.failure)
            except Exception as error:
                self.failure["event_write_exception"] = type(error).__name__
            raise ValueError("device process failed; no retry; writer state unknown") from None

    def select_privileged_shell(self):
        if self.privileged_shell is None:
            raw = self.call(self.adb, ["shell", "set -e; id -u; printf '\\nNUWA_UID_OK\\n'"])
            normalized = raw.replace(b"\r\n", b"\n")
            match = re.fullmatch(rb"([0-9]+)\n\nNUWA_UID_OK\n", normalized)
            require(match is not None, "invalid shell uid probe")
            self.privileged_shell = "sh" if int(match.group(1)) == 0 else "su"
        return self.privileged_shell

    def shell(self, script):
        # adb shell parses remote quoting; exec-out passes its argument directly.
        command = "set -eu\n" + script + '\nprintf "\\nNUWA_OK\\n"\n'
        raw = self.call(self.adb, ["shell", self.select_privileged_shell(), "-c", shlex.quote(command)])
        # Text shell protocol only. Retain call()/last_call raw bytes for
        # diagnostics; never apply newline conversion to exec-out block streams.
        text = raw.replace(b"\r\n", b"\n")
        require(text.endswith(b"\nNUWA_OK\n"), "missing remote completion")
        return text[:-len(b"\nNUWA_OK\n")].decode("ascii").strip()

    def unique(self):
        self.stage = "identity-inventory"
        rows = self.call(self.adb, ["devices", "-l"]).decode("ascii").splitlines()
        require(rows and rows[0] == "List of devices attached", "adb inventory")
        # Deliberately stricter than selecting one among several attached devices:
        # no peer receives a command, and ambiguous inventories stop immediately.
        peers = [line.split() for line in rows[1:] if line.strip()]
        require(len(peers) == 1 and len(peers[0]) >= 2
                and peers[0][0] == self.serial and peers[0][1] in ("device", "recovery"),
                "not a unique selected Android device")
        require(not self.call(self.fastboot, ["devices"]).strip(),
                "fastboot peer present; unique device unresolved")

    def snapshot_script(self):
        return r'''
test "$(getprop ro.product.device)" = nuwa
test "$(id -u)" = 0
test "$(getprop ro.boot.slot_suffix)" = _a
target=$(readlink -f /dev/block/by-name/userdata)
test -b "$target"
node=${target##*/}
sys=$(readlink -f "/sys/class/block/$node")
test -f "$sys/partition"
parent=${sys%/*}; parent=${parent##*/}
test -b "/dev/block/$parent"
printf '%s\n' "$target" "$node" "$parent"
cat "$sys/dev" "$sys/partition" "$sys/start" "$sys/size"
blockdev --getsize64 "$target"
blockdev --getsize64 "/dev/block/$parent"
blockdev --getss "/dev/block/$parent"
cat /proc/sys/kernel/random/boot_id
'''

    def snapshot(self):
        self.stage = "identity-snapshot"
        lines = self.shell(self.snapshot_script()).splitlines()
        require(len(lines) == 11 and re.fullmatch(r"/dev/block/[A-Za-z0-9_]+", lines[0])
                and lines[0] == "/dev/block/" + lines[1]
                and re.fullmatch("[A-Za-z0-9_]+", lines[2])
                and re.fullmatch(r"\d+:\d+", lines[3]), "userdata binding response")
        part, start, sectors, capacity, disk_bytes, block = map(int, lines[4:10])
        require(part > 0 and start * 512 == FIRST_LBA * LBA_BYTES
                and sectors * 512 == capacity == CAPACITY
                and block == LBA_BYTES and disk_bytes % block == 0
                and (start + sectors) * 512 <= disk_bytes and lines[10],
                "userdata sysfs/physical capacity or start mismatch")
        return tuple(lines)

    def staging_script(self, emit=False):
        """No mkdir, mount, test file or other device write, even on failure."""
        root = shlex.quote(self.staging_root)
        finish = ('printf "%s:%s:%s\\n" "$state" "$free" "$unit"'
                  if emit else 'test "$state" = ok')
        return f'''
check_staging() {{
 free=0; unit=0
 if ! test -d {root}; then state=missing
 elif test -L {root}; then state=symlink
 else
  resolved=$(readlink -f {root}) || return
  fs=$(stat -f -c %T {root}) || return
  if test "$resolved" != {root}; then state=noncanonical
  elif test "$fs" != tmpfs; then state=not-tmpfs
  else
   free=$(stat -f -c %a {root}) || return
   unit=$(stat -f -c %S {root}) || return
   test "$free" -ge 0 || return
   test "$unit" -gt 0 || return
   if test "$((free * unit))" -ge {STAGING_REQUIRED}; then state=ok
   else state=insufficient; fi
  fi
 fi
 {finish}
}}
check_staging
'''

    def tools_inspect(self):
        self.stage = "tools-inspect"
        self.shell(r'''
for tool in getprop id readlink cat blockdev ls grep pidof stat sha256sum dd; do
 command -v "$tool" >/dev/null
done
test "$(readlink -f /dev/null)" = /dev/null
test "$(stat -c %s /dev/null)" = 0
test "$(sha256sum /dev/null)" = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  /dev/null"
help=$(dd --help 2>&1)
case "$help" in *notrunc*) ;; *) exit 85;; esac
case "$help" in *fsync*) ;; *) exit 85;; esac
# Zero-count read only. No of=, test file, cache mutation or write syscall
# to a device is requested. This does not test writable dd/fsync behaviour.
dd if=/dev/null bs=512 count=0 2>&1
''')

    def inspect(self, serial):
        require(self.read_only and not self.backup_only and serial == self.serial,
                "read-only inspection required")
        self.inspection_stage = "identity"
        self.unique()
        self.binding = self.snapshot()
        self.inspection_stage = "tools"
        self.tools_inspect()
        self.inspection_stage = "staging"
        self.stage = "inspect-staging"
        fields = self.shell(self.staging_script(emit=True)).split(":")
        require(len(fields) == 3 and fields[0] in
                ("ok", "missing", "symlink", "noncanonical", "not-tmpfs", "insufficient"),
                "invalid staging response")
        self.staging_status = fields[0]
        require(self.staging_status == "ok", "staging unavailable")
        available = int(fields[1]) * int(fields[2])
        require(available >= STAGING_REQUIRED, "staging capacity insufficient")
        self.inspection_stage = "offline-guard"
        self.stage = "inspect-offline-guard"
        self.shell(self.guard())
        self.inspection_stage = "physical-GPT"
        self.physical_gpt()
        self.inspection_stage = "binding-refresh"
        require(self.snapshot() == self.binding, "target changed during inspection")
        self.stage = "inspect-offline-refresh"
        self.shell(self.guard())
        return dict(mode="inspect", status="read-only-checks-complete",
                    staging_root=self.staging_root, staging_available=available,
                    staging_required=STAGING_REQUIRED, capacity=CAPACITY,
                    physical_gpt_verified=True, write_compatibility="untested",
                    device_writes=0)

    def bind_backup_source(self):
        require(self.read_only and self.backup_only, "read-only backup required")
        self.unique()
        self.binding = self.snapshot()
        self.stage = "backup-offline-guard"
        self.shell(self.guard())
        self.physical_gpt()
        self.refresh_backup_source()

    def refresh_backup_source(self):
        self.unique()
        require(self.snapshot() == self.binding, "backup target/session changed")
        self.stage = "backup-offline-guard"
        self.shell(self.guard())
        self.physical_gpt()
        require(self.snapshot() == self.binding, "backup target/session changed")
        self.stage = "backup-offline-refresh"
        self.shell(self.guard())

    def guard(self):
        require(self.binding is not None, "unbound target")
        # Gate and dd run in the SAME privileged shell. No mounted alias, holder,
        # raw-parent opener, swap or competing dd is permitted.
        names = ("target", "node", "parent")
        script = self.snapshot_script().split("printf '%s\\n'")[0]
        for name, value in zip(names, self.binding[:3]):
            script += f'\ntest "${name}" = {shlex.quote(value)}\n'
        for suffix, value in zip(("dev", "partition", "start", "size"), self.binding[3:7]):
            script += f'test "$(cat "$sys/{suffix}")" = {shlex.quote(value)}\n'
        script += f'''
test "$(blockdev --getsize64 "$target")" = {CAPACITY}
test "$(blockdev --getsize64 "/dev/block/$parent")" = {self.binding[8]}
test "$(blockdev --getss "/dev/block/$parent")" = {LBA_BYTES}
test "$(cat /proc/sys/kernel/random/boot_id)" = {shlex.quote(self.binding[10])}
holders=$(ls -A "$sys/holders"); test -z "$holders"
parent_holders=$(ls -A "/sys/class/block/$parent/holders"); test -z "$parent_holders"
parent_target="/dev/block/$parent"
'''
        script += userdata_exclusion_script(self.binding[3])
        if not self.backup_only:
            script += self.staging_script()
        return script

    def raw(self, target, offset, length, label):
        require(offset >= 0 and length > 0 and offset % 512 == 0 and length % 512 == 0,
                "read alignment")
        self.sequence += 1
        self.stage = "read-" + label
        command = ["exec-out", self.select_privileged_shell(), "-c", "set -eu\n" + self.guard() +
                   f"\nexec dd if={target} bs=512 skip={offset // 512} count={length // 512} 2>/dev/null"]
        if self.read_only:
            # Inspect keeps the bounded GPT read in memory: no host work dir,
            # claim, event file or remote staging directory is created.
            data = self.call(self.adb, command, timeout=600)
            require(len(data) == length, "short read-only device read")
            return data
        path = self.host / f"{self.sequence:05d}-{label}.raw"
        # Binary stdout never traverses shell-v2, a PTY or a text decoder.
        self.call(self.adb, command, output=path, timeout=600)
        require(path.stat().st_size == length, "short independent readback")
        data = path.read_bytes()
        path.unlink()  # Only our exact host temporary read file.
        return data

    def physical_gpt(self):
        disk = "/dev/block/" + self.binding[2]
        block = int(self.binding[9])
        last = int(self.binding[8]) // block - 1
        tables, headers, header_bytes = [], [], []
        for lba in (1, last):
            raw_header = self.raw(disk, lba * block, block, "gpt-header")
            header_bytes.append(raw_header)
            header = gpt_header(raw_header, lba, last, block)
            n = header["count"] * header["stride"]
            table = self.raw(disk, header["table"] * block,
                             (n + block - 1) // block * block, "gpt-table")[:n]
            require(zlib.crc32(table) == header["crc"], "physical GPT table CRC")
            tables.append(table)
            headers.append(header)
        require(tables[0] == tables[1] and all(headers[0][k] == headers[1][k]
                for k in ("first", "end", "guid", "count", "stride", "crc")),
                "physical GPT primary/backup disagree")
        header, table = headers[0], tables[0]
        matches, ranges = [], []
        for i in range(header["count"]):
            entry = table[i * header["stride"]:(i + 1) * header["stride"]]
            if entry[:16] == b"\0" * 16:
                continue
            first, end = struct.unpack_from("<QQ", entry, 32)
            require(header["first"] <= first <= end <= header["end"], "GPT entry bounds")
            ranges.append((first, end))
            if entry[56:128].decode("utf-16-le").rstrip("\0") == "userdata":
                matches.append((i + 1, first, end))
        ranges.sort()
        require(all(a[1] < b[0] for a, b in zip(ranges, ranges[1:])),
                "physical GPT overlapping partitions")
        require(matches == [(int(self.binding[4]), FIRST_LBA, LAST_LBA)],
                "GPT userdata does not match by-name/sysfs")
        proof = digest(b"".join(header_bytes) + tables[0])
        if hasattr(self, "gpt_pin"):
            require(proof == self.gpt_pin, "physical GPT changed")
        self.gpt_pin = proof

    def preflight(self, serial, backup=None, without_backup=False):
        require(not self.read_only, "inspect cannot create staging")
        require(serial == self.serial, "serial changed")
        require(without_backup is True or backup is not None, "verified backup required")
        require(not (without_backup and backup is not None), "backup and waiver are mutually exclusive")
        self.write_admitted = False
        self.unique()
        self.binding = self.snapshot()
        self.tools_inspect()  # Mandatory in write itself, before first mkdir/push.
        self.stage = "preflight-offline-guard"
        self.shell(self.guard())
        self.physical_gpt()
        require(self.snapshot() == self.binding, "target changed during GPT read")
        self.stage = "preflight-offline-refresh"
        self.shell(self.guard())
        if not without_backup:
            require(backup["gpt_sha256"] == self.gpt_pin
                    and backup["binding_sha256"] == backup_identity(self, backup["nonce"], backup["bytes"]),
                    "current target does not match backup binding")
        self.write_admitted = True
        self.write_limit = SIZE if without_backup else backup["bytes"]
        # shell-owned staging works for adb push; root reads it only after
        # size/hash validation. It must not reside on userdata.
        self.stage = "staging-create"
        self.call(self.adb, ["shell", "mkdir", "-m", "700", self.remote])
        self.stage = "staging-type-check"
        self.shell(f'test "$(stat -f -c %T {self.remote})" = tmpfs\n'
                   f'test ! -L {self.remote}\ntest -d {self.remote}')
        return "nuwa", "userdata", CAPACITY

    def push_host_path(self, path):
        """WSL -> Windows conversion ONLY for the local operand of adb.exe push."""
        if os.name != "posix" or not self.adb.lower().endswith(".exe"):
            return str(path)
        self.stage = "push-host-path"
        result = None
        try:
            result = self.runner(["wslpath", "-w", str(path.resolve())],
                                 stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, timeout=30)
            require(result.returncode == 0 and not result.stderr.strip(), "wslpath failed")
            converted = result.stdout.decode("utf-8").strip()
            require(re.fullmatch(r"(?:[A-Za-z]:\\|\\\\)[^\r\n]+", converted),
                    "wslpath did not return one Windows host path")
            return converted
        except Exception as exc:
            self.invalid = True
            self.failure = failure_detail(exc, self.stage, [self.serial], result, "wslpath",
                                          ["wslpath", "-w", str(path.resolve())])
            self.persist_failure()
            raise ValueError("Windows push host path conversion failed; no fallback") from None

    def write(self, serial, offset, data):
        require(not self.read_only, "inspect cannot write")
        require(getattr(self, "write_admitted", False), "verified backup required")
        require(serial == self.serial and not self.invalid, "invalid session")
        require(offset % 512 == 0 and len(data) % 512 == 0 and data
                and offset + len(data) <= min(SIZE, self.write_limit), "write bounds")
        local = self.host / "input.raw"
        self.stage = "window-host-input"
        local.write_bytes(data)
        host_path = self.push_host_path(local)
        self.stage = "window-push"
        self.call(self.adb, ["push", host_path, self.remote + "/input.raw"], push_bytes=len(data))
        self.stage = "window-upload-validation"
        self.shell(f'test ! -L {self.remote}/input.raw\n'
                   f'test "$(stat -c %s {self.remote}/input.raw)" = {len(data)}\n'
                   f'test "$(sha256sum {self.remote}/input.raw)" = "{digest(data)}  {self.remote}/input.raw"')
        # Refresh CRC-checked physical GPT before each destructive window.
        self.physical_gpt()
        self.event("writer-starting", offset=offset, length=len(data))
        self.stage = "window-writer"
        text = self.shell(self.guard() + f'''
set +e
dd if={self.remote}/input.raw of={self.binding[0]} bs=512 count={len(data) // 512} seek={offset // 512} conv=notrunc,fsync 2>{self.remote}/dd.stderr
rc=$?
set -e
printf 'DD_RC=%s\\n' "$rc"
cat {self.remote}/dd.stderr
test "$rc" = 0
# Foreground dd has exited and closed its fd. Check no other dd survives.
if pidof dd >/dev/null; then exit 83; else test "$?" = 1; fi
printf 'WRITER_CLOSED\\n'
''')
        counts = re.findall(r"(?m)^(\d+) bytes(?:\s|$)", text)
        require(text.startswith("DD_RC=0\n") and text.endswith("WRITER_CLOSED")
                and counts == [str(len(data))]
                and not re.search(r"error|failed|denied|invalid", text, re.I),
                "writer completion/count unproven")
        self.event("writer-closed", offset=offset, length=len(data), dd_returncode=0,
                   dd_bytes=len(data), closure="foreground-exit-and-pidof-absent")
        self.stage = "window-sync-cache"
        self.shell("sync\necho 3 > /proc/sys/vm/drop_caches")
        return len(data), True

    def read(self, serial, offset, length):
        require(serial == self.serial, "serial changed")
        self.stage = "readback-offline-guard"
        self.shell(self.guard())
        return self.raw(self.binding[0], offset, length, "readback")

    def final_begin(self):
        require(not self.read_only, "inspect cannot mutate cache")
        self.unique()
        require(self.snapshot() == self.binding, "final target changed")
        self.physical_gpt()
        self.stage = "final-readback-sync"
        self.shell(self.guard() + "\nsync\necho 3 > /proc/sys/vm/drop_caches")


def execute(path, serial, authorized, claim_path, runner, *, size=SIZE,
            expected=SHA256, capacity=CAPACITY, window=WINDOW,
            backup_dir=None, backup_record_sha256=None, without_backup=False):
    try:
        return _execute(path, serial, authorized, claim_path, runner, size=size,
                        expected=expected, capacity=capacity, window=window,
                        backup_dir=backup_dir, backup_record_sha256=backup_record_sha256,
                        without_backup=without_backup)
    except Exception as exc:
        if isinstance(runner, AndroidUserdata):
            runner.invalid = True
            runner.failure = runner.failure or runner.diagnostic(exc)
        raise


def _execute(path, serial, authorized, claim_path, runner, *, size,
             expected, capacity, window, backup_dir, backup_record_sha256, without_backup):
    """One irreversible host claim; independent second complete readback pass."""
    runner.stage = "authorization"
    require(authorized is True and isinstance(serial, str) and serial
            and not serial.startswith("-") and not any(c.isspace() for c in serial),
            "authorization and serial required")
    require(os.name == "posix", "write requires WSL/POSIX Python with directory fsync")
    require(isinstance(without_backup, bool), "explicit backup policy required")
    runner.stage = "backup-policy"
    if without_backup:
        require(backup_dir is None and backup_record_sha256 is None,
                "backup and waiver are mutually exclusive")
        backup = None
    else:
        backup = validate_backup(backup_dir, backup_record_sha256, size, path)
    runner.stage = "run-claim"
    claim(claim_path)
    if without_backup and isinstance(runner, AndroidUserdata):
        runner.stage = "backup-policy-audit"
        runner.event("backup-policy", policy="without-backup", explicit_user_choice=True,
                     userdata_rollback=False, backed_up=False)
    runner.stage = "source-full-hash"
    windows = prepare(path, size, expected, window)
    geometry = runner.preflight(serial, backup=backup, without_backup=without_backup)
    require(geometry == ("nuwa", "userdata", capacity), "target or capacity")
    require(size <= capacity, "capacity insufficient")
    runner.stage = "source-open"
    with path.open("rb") as source:
        for offset, length, expected_window in windows:
            runner.stage = "source-window-validation"
            require(offset >= 0 and length > 0 and offset + length <= size
                    and offset + length <= capacity, "window bounds")
            source.seek(offset)
            data = source.read(length)
            require(len(data) == length and digest(data) == expected_window, "source changed")
            result = runner.write(serial, offset, data)
            require(result == (length, True), "short write or writer not closed")
            result = runner.read(serial, offset, length)
            require(len(result) == length and digest(result) == expected_window,
                    "short or mismatched readback")
    runner.final_begin()
    read_hash = hashlib.sha256()
    read_size = 0
    for offset, length, _ in windows:
        result = runner.read(serial, offset, length)
        require(len(result) == length, "short final readback")
        read_hash.update(result)
        read_size += len(result)
    require(read_size == size and read_hash.hexdigest() == expected, "final readback size/hash")
    return {"bytes": size, "sha256": expected, "windows": len(windows),
            "backup_policy": "without-backup" if without_backup else "verified-backup",
            "userdata_rollback": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", nargs="?", choices=("plan", "dryrun", "inspect", "backup", "write"), default="plan")
    parser.add_argument("--authorize-userdata-write-this-round", action="store_true")
    parser.add_argument("--exclusive-offline-userdata", action="store_true")
    parser.add_argument("--reviewed-and-independently-verified", action="store_true")
    parser.add_argument("--serial")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--manifest-sha256")
    parser.add_argument("--executor-sha256")
    parser.add_argument("--adb", default="adb")
    parser.add_argument("--fastboot", default="fastboot")
    parser.add_argument("--staging-root", default="/tmp")
    parser.add_argument("--backup-dir", type=Path)
    parser.add_argument("--backup-record-sha256")
    parser.add_argument("--without-backup", action="store_true")
    args = parser.parse_args()
    require(not args.without_backup or args.mode == "write",
            "--without-backup is only valid for authorized write")
    if args.mode in ("plan", "dryrun"):
        print(json.dumps(dict(mode=args.mode, image_bytes=SIZE, sha256=SHA256,
                              window_bytes=WINDOW, real_device_adapter=True,
                              device_calls=0, userdata_rollback=False)))
        return
    if args.mode == "backup":
        require(os.name == "posix", "backup requires WSL/POSIX Python with directory fsync")
        require(args.serial and args.backup_dir and args.exclusive_offline_userdata
                and args.reviewed_and_independently_verified, "backup requires serial/output/review/exclusion")
        require(args.executor_sha256 == digest(Path(__file__).read_bytes()),
                "reviewed executor source hash required")
        require(args.backup_dir.resolve().is_relative_to(CLAIM.parent.resolve()),
                "backup must remain under local out")
        adapter = AndroidUserdata(args.serial, Path("."), adb=args.adb, fastboot=args.fastboot,
                                  read_only=True, backup_only=True)
        try:
            print(json.dumps(create_backup(adapter, args.backup_dir)))
        except Exception as exc:
            print(json.dumps(dict(mode="backup", status="refused", error=adapter.diagnostic(exc))))
            raise SystemExit(1)
        return
    if args.mode == "inspect":
        require(args.serial, "inspect requires explicit serial")
        adapter = AndroidUserdata(args.serial, Path("."), adb=args.adb, fastboot=args.fastboot,
                                  staging_root=args.staging_root, read_only=True)
        try:
            print(json.dumps(adapter.inspect(args.serial)))
        except Exception as exc:
            print(json.dumps(dict(mode="inspect", status="refused",
                                  check=adapter.inspection_stage,
                                  staging_status=getattr(adapter, "staging_status", "not-confirmed"),
                                  device_writes=0, error=adapter.diagnostic(exc))))
            raise SystemExit(1)
        return
    require(args.authorize_userdata_write_this_round and args.exclusive_offline_userdata
            and args.reviewed_and_independently_verified and args.manifest
            and args.serial, "write requires this-round authorization, review, offline exclusion and frozen inputs")
    require(args.executor_sha256 == digest(Path(__file__).read_bytes()),
            "reviewed executor source hash required")
    if args.without_backup:
        require(args.backup_dir is None and args.backup_record_sha256 is None,
                "backup and waiver are mutually exclusive")
    else:
        require(args.backup_dir and args.backup_record_sha256, "verified backup required")
    image = frozen_image(args.manifest, args.manifest_sha256)
    host = CLAIM.parent / "nuwa-userdata-install-execution"
    # Fixed claim path, not a user-chosen run ID. Never automatically release it,
    # even on source, device, transport or verification failure.
    host.mkdir(exist_ok=True)
    adapter = AndroidUserdata(args.serial, host, adb=args.adb, fastboot=args.fastboot,
                              staging_root=args.staging_root)
    try:
        result = execute(image, args.serial, True, CLAIM, adapter,
                         backup_dir=args.backup_dir, backup_record_sha256=args.backup_record_sha256,
                         without_backup=args.without_backup)
        adapter.event("complete", **result)
        print(json.dumps(result))
    except Exception as exc:
        adapter.invalid = True
        print(json.dumps(dict(mode="write", status="refused", error=adapter.diagnostic(exc),
                              userdata_rollback=False, retry=False)))
        raise SystemExit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        identifiers = []
        for i, arg in enumerate(sys.argv[1:], 1):
            if arg == "--serial" and i + 1 < len(sys.argv):
                identifiers.append(sys.argv[i + 1])
            elif arg.startswith("--serial="):
                identifiers.append(arg.split("=", 1)[1])
        diagnostic = failure_detail(exc, "cli-or-host", identifiers)
        persist_diagnostic(diagnostic, DIAGNOSTICS)
        print(json.dumps(dict(status="STOP", error=diagnostic,
                              retry=False, userdata_rollback=False)))
        raise SystemExit(1)
