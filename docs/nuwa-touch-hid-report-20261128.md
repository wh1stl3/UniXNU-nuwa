# nuwa report 3 descriptor and encoder (2026-11-28)

**Host self-checked only.** This is not connected to a kernel, a probe, an
IOHID device or a hardware producer. No device image was built and there is
no runtime validation of ten fingers, lifts, orientation or backboardd.

## Sources

- Descriptor and report 3 approach adapted from
  [UniXNU/ShengHidInput `NativeHidInput.cpp` at
  `71a40e76daeae1bb4127546f96ffa7339c7a06ff`](https://github.com/UniXNU/ShengHidInput/blob/71a40e76daeae1bb4127546f96ffa7339c7a06ff/NativeHidInput.cpp),
  BSD-2-Clause-Patent, copyright 2026 NativeHidInput contributors. The full
  upstream notice, terms and disclaimer are retained in `NuwaHidReport.c`;
  binary redistribution must reproduce them in accompanying materials.
  Upstream uses ten six-byte fingers and no pressure. This version adds a
  pressure byte per finger, uses nuwa coordinate maxima, sets the Contact
  Count logical maximum to ten and uses a standalone C encoder.
- `NuwaTouchBoard.h` and `docs/nuwa-recovery-final-fields-20261126.md`
  record recovery's declared input capabilities: ten slots, X 0–14399, Y
  0–31999. These are capability ranges, not observed physical touch events or
  proof of the display orientation. The `ShengHidInput` 30480/20320 board
  denominators and edge thresholds are not reused.
- Read-only stage checks: device origin HEAD
  `fe6b859367cc7b0641e9ae7dda46d8b5c6fc4fb0`, UniXNU origin HEAD
  `fdf81eaa832ce5c850d3c53c698407aa722a4653`, ShengHidInput origin HEAD
  `114061452959a547aaa08f9ca5aa54033394ca2f`. The implementation remains
  based on the explicitly requested pinned revision above.

## Report 3 layout

The descriptor advertises one Digitizers/Touch Screen application collection
with ten Digitizers/Finger physical collections. The returned array includes
the report ID: 1 + 10 × 7 + 1 = **72 bytes**. Multibyte coordinates are
little-endian. For finger `i` in 0..9, its first byte is `1 + 7*i`.

| Offset from finger start | Usage | Bits | Logical range / encoding |
| --- | --- | ---: | --- |
| 0 bit 0 | Digitizers Tip Switch `0x42` | 1 | 1 down, 0 lift |
| 0 bit 1 | Digitizers Touch Valid `0x47` | 1 | 1 for a present down or lift entry; 0 for an unused slot |
| 0 bits 2–7 | Constant padding | 6 | 0 |
| 1 | Digitizers Contact Identifier `0x51` | 8 | 0–255, supplied ID |
| 2–3 | Generic Desktop X `0x30` | 16 | 0–32767 |
| 4–5 | Generic Desktop Y `0x31` | 16 | 0–32767 |
| 6 | Digitizers Tip Pressure `0x30` | 8 | 0–255 supplied logical pressure on down; 0 on lift |
| byte 71 of report | Digitizers Contact Count `0x54` | 8 | 0–10 emitted entries, **including** explicit/automatic lifts |

The caller supplies pressure already in the descriptor's logical range; no
raw-controller pressure range or physical calibration is asserted. Unused
slots are completely zero. Contact Identifier is a report field, **not**
assumed to equal `IOHIDEvent` identity or index.

## Encoder contract

`nuwa_hid_encode_report` takes a zero-initialized copyable state, a complete
current set of down contacts plus optional explicit `tip=0` contacts, and an
output buffer. IDs must be unique in one call, even between downs and lifts.
It first emits the caller's entries in supplied order; an earlier down ID
missing from the set is then emitted once as `valid=1, tip=0`, at its last
encoded position. Subsequent empty calls do not repeat that lift. ID reuse in
a later call is a new contact; a lift and a new down with the same ID cannot
be represented in the same call. Explicit lifts carry the supplied position,
but pressure is always zero. The state tracks only successfully **encoded**
downs; it does not prove that a consumer received anything.

If current entries plus missing-ID lifts exceed ten, the encoder returns
`NUWA_HID_REPORT_NEEDS_SPLIT` without changing state or output. The caller
must first send an intermediate complete set containing the surviving downs
and the necessary lifts, then encode the new full set. It must not silently
discard a lift. Duplicate IDs, `tip` other than 0/1, more than ten entries or
a short output buffer return `NUWA_HID_REPORT_INVALID`, also without changing
state or output.

The transform clamps each unsigned input to the declared native maximum and
uses integer truncation towards zero:

```
x_report = min(x, 14399) * 32767 / 14399
y_report = min(y, 31999) * 32767 / 31999
```

Thus both endpoints map exactly, 7200 maps to X 16384, and 16000 maps to Y
16384. This version fixes `x -> X`, `y -> Y`; there is **no configurable
orientation**, axis swap, flip or rotation. Whether this orientation aligns
with the actual displayed image is unverified.

## Future `handleReport` integration — not implemented

The intended path is to publish this descriptor through an appropriately
qualified `IOHIDDevice::newReportDescriptor`, put each complete 72-byte report
in an `IOMemoryDescriptor` and submit an input report through the normal
`IOHIDDevice::handleReport` path. Upstream uses an
`IOBufferMemoryDescriptor` for this purpose. The 20H392 extraction records
the device `handleReport` slot as 181, but its complete prototype, target TU,
matching, imports, ownership and final rebinding are not qualified. No code
here calls it. See `docs/nuwa-touch-hid-abi-20261128.md`; the donor
`IOHIDDevice` table has **207 slots**, not 219 or 256.

Before such integration, `deep_reviewer` must review the actual 20H392
linkage/ABI and lifecycle, producer ownership and serialization, descriptor
publication/matching, buffer lifetime and input report completion/failure.
An eventual sender must encode into a candidate state and settle how to
commit or recover it after successful, failed or ambiguous delivery; advancing
this encoder's state alone is not a delivery acknowledgment. Release splitting
and ID lifetime require the same review. No edge wrapper, vtable copying,
private event-field writes, hardware producer or kernel submission is enabled.
The donor's object offsets are not used by the descriptor or encoder.

## Host self-check

From the worktree in WSL:

```sh
python3 -B scripts/build-nuwa-touch-probe.py --hid-self-test --self-test
```

The test's descriptor parser checks all ten fingers' field widths, usage pages,
logical limits, bit offsets, report ID, count and 72-byte length. Encoder tests
cover down/move/explicit and omitted-ID lifts, two-finger reorder and
alternation, ten entries, split-and-retry, endpoints, truncation, clamping,
ID reuse, invalid inputs and unchanged state/output on refusal. These tests
model encoded bytes only, not actual IOHID parsing or hardware.

The record check's `--base` compares commits rather than untracked files. For
this Windows-created worktree, run both the CLI and the additional explicit
path/owner check from WSL:

```sh
W=/mnt/d/Code/PortingiOS/nuwa/worktree-touch-probe-20261128
B=/mnt/d/Code/PortingiOS/UniXNU
G=/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/.git/worktrees/worktree-touch-probe-20261128
env GIT_DIR="$G" GIT_WORK_TREE="$W" /home/wh1stl3/.local/bin/python3.11 -B \
  "$B/scripts/porting-record.py" check --device "$W" --base origin/main
env GIT_DIR="$G" GIT_WORK_TREE="$W" BASE="$B" /home/wh1stl3/.local/bin/python3.11 -B - <<'PY'
import os, runpy, subprocess, tomllib
from pathlib import Path
worktree = Path(os.environ["GIT_WORK_TREE"])
tool = runpy.run_path(os.environ["BASE"] + "/scripts/porting-record.py")
previous = tomllib.loads(subprocess.check_output(
    ["git", "show", "origin/main:porting.toml"], text=True))
current = tomllib.loads((worktree / "porting.toml").read_text())
paths = [
    "package/nuwa-touch/NuwaHidReport.h",
    "package/nuwa-touch/NuwaHidReport.c",
    "tests/test-nuwa-hid-report.c",
    "scripts/build-nuwa-touch-probe.py",
    "docs/nuwa-touch-hid-report-20261128.md",
]
tool["check_changes"]({a["id"]: a for a in previous["area"]},
                      {a["id"]: a for a in current["area"]}, paths)
print("report paths: owner/findings check self-checked")
PY
```
