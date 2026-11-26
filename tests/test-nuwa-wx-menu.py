#!/usr/bin/env python3
"""Run the exact r4 UniXNU menu against the final WX config with a no-write EFI substitute."""
import argparse
import hashlib
import json
from pathlib import Path
import selectors
import socket
import subprocess
import tempfile
import time
import tomllib

LOADER = "8dc2d4d755d3dd603d7232b01a410eb83095346cf3f8fd3e9f41757e8ec11c2f"
TITLE = b"SB0 W - MANUAL ONE-WRITE EXPERIMENT"
QUESTION = b"Run ONE experimental SB0 write? After any attempt use R, not W."
DEFAULT = b"Booting Power off"
PROXY = r"""
#include <Uefi.h>
EFI_STATUS EFIAPI EfiMain(EFI_HANDLE self, EFI_SYSTEM_TABLE *st) {
  (VOID)self;
  st->ConOut->OutputString(st->ConOut, L"WX-NOWRITE START\r\n");
#if PROXY_WATCHDOG
  if (st->BootServices->SetWatchdogTimer(2, 0x10000, 0, NULL) != EFI_SUCCESS) {
    st->ConOut->OutputString(st->ConOut, L"WX-NOWRITE WATCHDOG-FAILED\r\n");
    return EFI_UNSUPPORTED;
  }
  st->ConOut->OutputString(st->ConOut, L"WX-NOWRITE WATCHDOG-ARMED\r\n");
  for (;;) st->BootServices->Stall(10000);
#else
  st->RuntimeServices->ResetSystem(EfiResetCold, EFI_SUCCESS, 0, NULL);
  st->ConOut->OutputString(st->ConOut, L"WX-NOWRITE RESET-RETURNED\r\n");
  return EFI_UNSUPPORTED;
#endif
}
"""


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(*args):
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL)


def make_fat(out, loader, basecore, config, watchdog):
    source, obj, efi = (out / name for name in ("proxy.c", "probe.obj", "NoWrite.efi"))
    source.write_text(PROXY)
    headers = basecore / "MdePkg/Include"
    run("clang", "--target=aarch64-pc-windows-msvc", "-fshort-wchar", "-ffreestanding",
        "-fno-stack-protector", "-O2", "-Wall", "-Werror", f"-DPROXY_WATCHDOG={int(watchdog)}",
        "-I", headers, "-I", headers / "AArch64", "-c", source, "-o", obj)
    run("lld-link", "/machine:arm64", "/entry:EfiMain", "/subsystem:efi_application",
        "/nodefaultlib", "/timestamp:0", f"/out:{efi}", obj)
    # Change only dispatch: retain the exact entries, order, default, timeout,
    # confirmation and args. The fixture disk never contains the WX kernel.
    assert config.count(b'type = "xnu"\npath = "Payloads/kernel.macho"\n'
                        b'initrd = "Payloads/scratch-data.img"\n') == 1
    config = config.replace(b'type = "xnu"\npath = "Payloads/kernel.macho"\n'
                            b'initrd = "Payloads/scratch-data.img"\n',
                            b'type = "efi"\npath = "Payloads/NoWrite.efi"\n')
    fixture_config = out / "unixnu.toml"
    fixture_config.write_bytes(config)
    fat = out / "read-only-fixture.img"
    with fat.open("wb") as f:
        f.truncate(64 * 1024 * 1024)
    run("mkfs.fat", "-F", "32", fat)
    for name in ("EFI", "EFI/BOOT", "EFI/UniXNU", "EFI/UniXNU/Payloads"):
        run("mmd", "-i", fat, "::/" + name)
    run("mcopy", "-i", fat, loader, "::/EFI/BOOT/BOOTAA64.EFI")
    run("mcopy", "-i", fat, fixture_config, "::/EFI/UniXNU/unixnu.toml")
    run("mcopy", "-i", fat, efi, "::/EFI/UniXNU/Payloads/NoWrite.efi")
    return fat


def exercise(out, bios, fat, case):
    before = sha(fat)
    transcript, events = bytearray(), []
    with (tempfile.TemporaryDirectory(prefix="nuwa-wx-", dir=Path.home()) as temp,
          selectors.DefaultSelector() as sel, socket.socket(socket.AF_UNIX) as qmp):
        endpoint = Path(temp) / "qmp"
        args = ["qemu-system-aarch64", "-M", "virt", "-cpu", "cortex-a57", "-m", "256",
                "-nographic", "-monitor", "none", "-serial", "stdio", "-nic", "none",
                "-bios", str(bios), "-qmp", f"unix:{endpoint},server=on,wait=off",
                "-drive", f"if=none,id=boot,format=raw,readonly=on,file={fat}",
                "-device", "virtio-blk-pci,drive=boot"]
        p = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             bufsize=0)
        qmp_lines = bytearray()
        try:
            for _ in range(100):
                if endpoint.exists():
                    break
                assert p.poll() is None
                time.sleep(.05)
            qmp.connect(str(endpoint))
            qmp.sendall(b'{"execute":"qmp_capabilities"}\r\n')
            sel.register(p.stdout, selectors.EVENT_READ, "console")
            sel.register(qmp, selectors.EVENT_READ, "qmp")

            def pump(seconds):
                for key, _ in sel.select(seconds):
                    if key.data == "console":
                        got = p.stdout.read(65536)
                        if got:
                            transcript.extend(got)
                        else:
                            sel.unregister(key.fileobj)
                    else:
                        got = qmp.recv(65536)
                        if not got:
                            sel.unregister(qmp)
                        qmp_lines.extend(got)
                        while b"\n" in qmp_lines:
                            line, tail = qmp_lines.split(b"\n", 1)
                            qmp_lines[:] = tail
                            events.append(json.loads(line))

            def until(done, seconds, detail):
                until_time = time.monotonic() + seconds
                while not done():
                    assert time.monotonic() < until_time, detail
                    pump(.1)

            def send(data):
                p.stdin.write(data)
                p.stdin.flush()

            until(lambda: DEFAULT in transcript, 30, "r4 menu did not parse safe default")
            assert TITLE in transcript
            first = len(transcript)
            if case != "idle":
                send(b"2")
                until(lambda: QUESTION in transcript[first:], 12, "explicit W selection did not open confirmation")
                if case == "cancel":
                    # Clear the r4 prompt's original selection/drain interval.
                    time.sleep(.9)
                    send(b"n")
                    until(lambda: b"cancelled" in transcript[first:] or b"Select an entry" in transcript[first:],
                          12, "confirmation did not cancel")
                    send(b"1")
                else:
                    time.sleep(.9)
                    send(b"\r")
                    until(lambda: b"WX-NOWRITE START" in transcript[first:], 12, "confirmed no-write EFI did not start")
                    reset_at = len(transcript)
                    if case == "watchdog":
                        until(lambda: b"WX-NOWRITE WATCHDOG-ARMED" in transcript[first:],
                              8, "EFI watchdog not armed")
                    until(lambda: any(e.get("event") == "RESET" for e in events), 20, "QEMU did not reset")
                    # No keys after reset: the exact r4 menu must choose shutdown.
                    until(lambda: DEFAULT in transcript[reset_at:], 30, "reset did not restore safe default")
            until(lambda: p.poll() is not None, 30, "VM did not shut down")
            pump(0)
            assert p.returncode == 0
            resets = [e for e in events if e.get("event") == "RESET"]
            starts = transcript.count(b"WX-NOWRITE START")
            assert starts == len(resets) == int(case in ("cold", "watchdog")), (starts, resets)
            assert b"FAILED" not in transcript[first:] or b"WX-NOWRITE WATCHDOG-FAILED" not in transcript
            assert any(e.get("event") == "SHUTDOWN" for e in events)
        finally:
            if p.poll() is None:
                p.kill()
            p.wait()
            (out / "console.log").write_bytes(transcript)
            (out / "qmp.json").write_text(json.dumps(events, indent=2) + "\n")
            (out / "argv.json").write_text(json.dumps(args, indent=2) + "\n")
    assert sha(fat) == before
    return dict(fixture_sha256=before, proxy_starts=starts, qmp_resets=resets, qemu_exit=0)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for arg in ("outer", "loader", "basecore", "bios", "output"):
        p.add_argument(f"--{arg}", type=Path, required=True)
    p.add_argument("--case", choices=("idle", "cancel", "cold", "watchdog"), action="append")
    a = p.parse_args()
    output = a.output.resolve()
    output.mkdir()
    assert sha(a.loader) == LOADER, "not the exact r4 UniXNU EFI application"
    with a.outer.open("rb") as src:
        header = src.read(4096)
        assert header[:8] == b"VNDRBOOT" and int.from_bytes(header[24:28], "little") == 67108864
        fat = src.read(67108864)
    extracted = output / "outer-fat.img"
    extracted.write_bytes(fat)
    config_file = output / "wx-final-unixnu.toml"
    run("mcopy", "-i", extracted, "::/EFI/UniXNU/unixnu.toml", config_file)
    config = config_file.read_bytes()
    decoded = tomllib.loads(config.decode())
    assert decoded["boot"] == dict(default="shutdown", timeout=10, fallback_timeout=10, rotate=60)
    assert [entry["id"] for entry in decoded["entry"]] == ["shutdown", "xnu", "reset", "tools"]
    assert decoded["entry"][0]["type"] == "action" and decoded["entry"][0]["action"] == "shutdown"
    assert decoded["entry"][1]["confirm"].encode() == QUESTION
    report = {"outer_sha256": sha(a.outer), "loader_sha256": LOADER, "bios_sha256": sha(a.bios)}
    for case in a.case or ("idle", "cancel", "cold", "watchdog"):
        out = output / case
        out.mkdir()
        case_fat = make_fat(out, a.loader.resolve(), a.basecore.resolve(), config, case == "watchdog")
        report[case] = exercise(out, a.bios.resolve(), case_fat, case)
        print("PASS", case, report[case], flush=True)
    (output / "audit.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
