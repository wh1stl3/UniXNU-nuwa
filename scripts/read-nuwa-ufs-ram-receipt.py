#!/usr/bin/env python3
"""One-shot host journal and fixed bulk-IN receiver; no shell or media commands."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import time

BYTES = 770 * 4096
PREP = "6bdcd73dcf47f64038afbce5c14c7fb2817da9e2074a2597acb8852898e6c3d2"
SB0 = "b227e878961df9b0d30ccdd73663206e396d3d2a0466141377439d11f74a86f5"


def receive(read, run_id, armed):
    def one(n):
        buffer = bytearray()
        while len(buffer) < n:
            data = read(min(16384, n - len(buffer)))
            if not data or len(data) > n - len(buffer):
                raise ValueError("short or oversized receipt")
            buffer.extend(data)
        return bytes(buffer)

    final = f"NUWARAM1 FINAL {run_id} CLAIM-CLOSED\n".encode()
    header = bytearray()
    while not header.endswith(b"\n") and len(header) < 55:
        header.extend(one(1))
    modes = ("WRITE",) if armed else ("CHECK-BLANK", "CHECK-SB0")
    if header not in [f"NUWARAM1 {mode} {run_id}\n".encode() for mode in modes]:
        raise ValueError("wrong receipt mode or run ID")
    output = {}
    if armed:
        prepare, commit = one(BYTES), one(BYTES)
        if hashlib.sha256(prepare).hexdigest() != PREP:
            raise ValueError("prepare readback hash")
        if hashlib.sha256(commit[:4096]).hexdigest() != SB0 or any(commit[4096:]):
            raise ValueError("commit readback mismatch")
        output.update({"prepare-readback.bin": prepare, "commit-readback.bin": commit})
    if one(len(final)) != final:
        raise ValueError("missing or wrong post-claim final receipt")
    output["final-receipt.txt"] = bytes(header) + final
    return output


def put(path, data):
    with path.open("xb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def reserve(journal, run_id, armed):
    # Stable local Linux/WSL directory per physical target, not per boot.
    # An existing path is never overwritten, even when a prior run has no result.
    put(journal, (json.dumps({"mode": "write" if armed else "check", "run_id": run_id})
                  + "\n").encode())


def capture(journal, read):
    bound = json.loads(journal.read_text(encoding="ascii"))
    run_id, armed = bound["run_id"], bound["mode"] == "write"
    marker = journal.with_name(journal.name + ".receive-started")
    put(marker, f"{run_id}\n".encode())
    for name, data in receive(read, run_id, armed).items():
        put(journal.with_name(journal.name + "." + name), data)


def usb_run(journal):
    import usb.core
    import usb.util

    bound = json.loads(journal.read_text(encoding="ascii"))
    run_id = bound["run_id"]
    devices = [d for d in usb.core.find(find_all=True, idVendor=0x1D6B, idProduct=0x0104)
               if usb.util.get_string(d, d.iSerialNumber) == run_id]
    if len(devices) != 1:
        raise ValueError("no unique device presenting reserved receipt run ID")
    device = devices[0]
    cfg = device[0]
    intf = cfg[(0, 0)]
    eps = list(intf)
    if (len(list(cfg)) != 1 or intf.bInterfaceClass != 0xFF or len(eps) != 1
            or eps[0].bEndpointAddress != 0x81 or eps[0].bmAttributes & 3 != 2):
        raise ValueError("unexpected USB descriptor layout")
    # USB bulk host receive buffers must accommodate a whole packet. Preserve
    # already received bytes for exact frame boundaries and short packets.
    pending = bytearray()
    deadline = time.monotonic() + 30

    def read(n):
        if not pending:
            ms = int((deadline - time.monotonic()) * 1000)
            if ms <= 0:
                raise TimeoutError("receipt transfer deadline")
            pending.extend(device.read(0x81, 16384, timeout=ms))
        data = bytes(pending[:n])
        del pending[:n]
        return data

    # Start marker is durable before any operation that could consume data.
    def start_read(n):
        nonlocal started
        if not started:
            device.set_configuration(cfg.bConfigurationValue)
            usb.util.claim_interface(device, 0)
            started = True
        return read(n)

    started = False
    capture(journal, start_read)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="action", required=True)
    allocate = sub.add_parser("reserve")
    allocate.add_argument("--mode", choices=("write", "check"), required=True)
    allocate.add_argument("--run-id", required=True)
    allocate.add_argument("journal", type=Path)
    fetch = sub.add_parser("receive")
    fetch.add_argument("journal", type=Path)
    args = p.parse_args()
    try:
        if args.action == "reserve":
            if not re.fullmatch("[0-9a-f]{32}", args.run_id):
                p.error("run ID must be 32 lowercase hex characters")
            reserve(args.journal, args.run_id, args.mode == "write")
        else:
            usb_run(args.journal)
    except (OSError, ImportError, ValueError) as e:
        p.exit(1, f"STOP: {e}; do not replay an attempted initialization\n")
