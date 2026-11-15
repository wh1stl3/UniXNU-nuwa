# Image4 initializer AMNM/CHMH host boundary (2026-11-11, r2 evidence fix)

**Status: self-checked host evidence only; r2 evidence-layer fix.** No device,
adb/fastboot, build, commit or push was performed. This is not independently
verified and not a live-boot, authentication or device-release result. The
parallel verifier was reading the pre-fix `evidence.json`; that result cannot be
used as a pass for this r2 version. Final acceptance and any independent
verifier run remain with the parent orchestrator.

The deep-review core conclusion is unchanged: the in-package input allows the
missing digest under the ADT-backed fixture, so it cannot reproduce the device
panic state. This r2 change corrects the evidence layer and adds semantic and
tamper negatives; it does not change the frozen inputs or the host conclusion.

## Correction to the pre-fix evidence

The pre-fix write classification used `DIGEST_OBJECT` as the end of the cache
window while the snapshot ended at `CACHE_WINDOW_END=5cacffa`. As a result,
writes to the 48-byte BNCH buffer (`5cacffa..5cad02a`, including
`5cad00a/012/01a/022`) and the adjacent CHMH length field at `5cad02c` were
counted as cache-window writes. The pre-fix `cache_window` count (43) was
therefore not a cache-only count.

r2 replaces that with a contiguous, disjoint region ledger over
`[5caced8, 5cad070)`:

| Region | Range | Meaning |
| --- | --- | --- |
| `cache_header_5caced8` | `5caced8..5cacef0` | cache header, no writes |
| `amnm_out_5cacef0` | `5cacef0..5cacef8` | AMNM byte output |
| `cache_payload_5cacef8` | `5cacef8..5cacffa` | Image4 cache object payload |
| `bnch_buffer_5cacffa` | `5cacffa..5cad02a` | 48-byte BNCH buffer, independent |
| `bnch_pad_5cad02a` | `5cad02a..5cad02c` | 2-byte pad |
| `chmh_length_5cad02c` | `5cad02c..5cad030` | CHMH length field, independent |
| `digest_object_5cad030` | `5cad030..5cad070` | CHMH digest object |

Every write hook record keeps the raw address/size/value and is split by byte
into one segment per region. The sum of segment sizes closes the raw write size;
each byte is classified once. A write that would extend outside the ledger
range is retained with `unclassified_bytes` instead of being silently dropped
or double-counted. `bnch_pad` is included so the region map is contiguous.

Corrected original-case ledger: **43 writes**, all fully classified, 0
unclassified bytes. Cache window `[5caced8,5cacffa)` has **30** writes: **1**
AMNM byte at `5cacef0` plus **29** cache-payload writes. BNCH buffer has **12**
writes / **96** bytes; CHMH length has **1** write of **48** at `46e9ab4`;
digest object and cache header have **0** writes. Region byte totals:
header 0, AMNM 1, cache payload 189, BNCH 96, pad 0, CHMH length 4, digest 0
(total 290 bytes of write payload).

## Frozen inputs

| Input | Bytes | SHA256 |
| --- | ---: | --- |
| `/root/nuwa-pmap-ret-native-20261111/diagnostic-20261111-r1/renderer-baseline.macho` | 55386112 | `7fd3d933aae66d8e34a0d3ebfa142137978976d7521e04cef20321109750b6f4` |
| `out/owner-pmap-ret-continuation-verifier-final-20261111/adt-generation/final.adt` | 13256 | `885094de4597fb2d1734ba4092c805968097d021c8f482653b238436586d27a4` |

The ADT is byte-identical to
`out/owner-continuation-vendor-boot-verifier-20261111/extracted/EFI/UniXNU/Payloads/kernel.macho.adt`
(same SHA256). No a296 artifact, implementer package or real candidate was
modified. Case-specific ADTs are independent in-memory fixtures.

Original ADT shape: `/chosen/mix-n-match-prevention-status` flags `0x0`,
length **4**, value `00000000`; `/chosen/boot-manifest-hash` **absent**;
`/chosen/manifest-properties/BNCH` present, 48 bytes.

## Runner and stop semantics

`scripts/research-current-image4-initializer-amnm.py` reuses
`audit-image4-runtime-provider.py` (`Model`, `parse_adt`),
`build-kernel-entry-probe.py` (Mach-O helpers) and
`nuwa_launch_context.py` (ADT codec). Those files and the old harness pins are
unchanged.

- Start at the real entry `46e98cc`; `[5cad070+0x10]` selects it, `+0x58`
  selects Darwin runtime `5cb14d8`, `[runtime+0x38]=46efe7c`,
  `[runtime+0x50]=46f021c`. `X0` is the PMAP_CS table; no pointer/level change.
- `5cacef0` is not pre-filled; the run starts at the entry, not at a digest
  helper. The initializer epilogue `46e9f00` is **not executed**; the trace ends
  at `46e9b2c` or at the panic entry `46fa028`.
- The runner stops on the post-decision boundary, the panic entry, invalid
  memory, a Unicorn exception or the instruction budget. It does **not**
  implement per-dependency admission, so it does not claim "first unmodelled
  dependency" as an enforced stop; an unexpected stop is reported as such.
- The write ledger covers only this traced interval. `SecureDTInit` runs before
  it, and its writes are not in the ledger. The IOKit/OSData objects are
  fixtures from the same ADT, not a live IORegistry snapshot.

Real code: initializer entry/prologue through the decision, AMNM bool reader
`46efe7c`, CHMH digest reader `46f021c`, helper `46f07e8`, conversions,
comparisons, copies, branches, panic calls, and the pre-run SecureDT calls.
Modelled boundaries only: `IORegistryEntry::fromPath`, `getProperty`/`release`,
`safeMetaCast`, `OSData::getLength`/`getBytesNoCopy`, Image4 runtime logging.

## Results (4 cases, fresh state each)

Evidence SHA256 `b14a0a15b6fd6b54bda10d9aed79ac34b39a9062f5a873e668ff91df3f887c77`.
28 logical semantic check groups, 52 mechanical invariants; counts are not
independent semantic proofs.

| Case | AMNM fixture | CHMH fixture | id12 call / return | id11 call / return | store / final | Exit |
| --- | --- | --- | --- | --- | --- | --- |
| original | u32=0 len4 `00000000` | absent | `(runtime, chip, 12, 5cacef0)` / 0 | `(runtime, chip, 11, 5cad030)` / 2 | 1 / 1 | boundary `46e9b2c` |
| nonzero AMNM + missing | u32=1 len4 `01000000` | absent | same / 0 | same / 2 | 0 / 0 | panic `46e9f64`/`46fa028`, errno 2 |
| wrong type | u32=0 | 48 bytes, forced wrong OSData type | same / 0 | same / 96 | 1 / not read | panic, errno 96 |
| length 49 | u32=0 | 49 bytes | same / 0 | same / 84 | 1 / not read | panic, errno 84 |

`chip` is `5cae660`. The AMNM helper is exactly one call keyed
`mix-n-match-prevention-status` with capacity 4 and return 0; the CHMH helper is
exactly one call keyed `boot-manifest-hash` with capacity 48 and return 2/96/84.
The AMNM output store is exactly one write at `46effb8`; the digest object
`5cad030` has an empty write list and is unchanged; the cache header
`[5caced8,5cacef0)` has an empty write list and is unchanged; the cache payload
is populated. Original final load/branch at `46e9b00`/`46e9b04` are both 1.

## Semantic negatives (single-field tamper rejection)

`negative-checks-r2.json` SHA256
`98cf03fbd702f766f4f685d21af54dee2c8b8bb5599814924743fb799a627cd3` records
**25/25 rejected** single-field mutations of the r2 report, including:

- id12/id11 call argument changes; AMNM property length; AMNM store value;
  final load/branch value; CHMH helper/reader errno.
- nonempty digest write list; nonempty cache-header write list; a BNCH write
  inserted into the cache window; CHMH length write removed or changed.
- BNCH write list emptied; cache payload write list emptied; region byte count
  changed; ledger classification flag changed.
- epilogue `46e9f00` appended to the trace; stop PC changed; case ADT hash,
  input ADT hash or source hash changed; digest-unchanged flag changed.

The validator (`validate_report`) is an independent report check: it recomputes
input/case hashes and applies the exact call ABI, reader/helper, write-ledger,
stop/panic and trace assertions. The generator does not merely compare its own
expected object with itself; the tamper suite demonstrates rejection of key
single-field inconsistencies.

## Before/after artifacts

| Artifact | Before (pre-fix) | After (r2) |
| --- | --- | --- |
| runner | `f8c1ba3e980f6a37c2e92dcf5b0c175c259cfb0ee38a528e9c071a1691a2bad1` | `96265f953dd6194cf8dad5700308e7d5da038c8ff4af0db2c42b79bee240fe7e` |
| evidence | `out/.../evidence.json` `6dcc809b3bd5723780ac5aa7e3a5d21ab432ed0efb20993c565d5bb8c67dd8be` | `out/.../evidence-r2.json` `b14a0a15b6fd6b54bda10d9aed79ac34b39a9062f5a873e668ff91df3f887c77` |
| negatives | not present | `out/.../negative-checks-r2.json` `98cf03fbd702f766f4f685d21af54dee2c8b8bb5599814924743fb799a627cd3` |

The pre-fix `evidence.json` was **not overwritten**; it is retained for the
parallel verifier. `repro-check.json` and `superseded-r*.json` are older
retained iterations; `evidence-r2.json` is the r2 fixed evidence.

## Self-check commands

Windows cwd `D:/Code/PortingiOS/nuwa/UniXNU-nuwa`; WSL Ubuntu-22.04 cwd
`/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa`, `/usr/bin/python3` 3.10.12 with
Unicorn 2.1.4 (`PYTHONPATH=/home/wh1stl3/.local/lib/python3.10/site-packages`).
No network access.

```powershell
wsl -d Ubuntu-22.04 -u root -- env PYTHONPATH=/home/wh1stl3/.local/lib/python3.10/site-packages /usr/bin/python3 -B -m py_compile /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/scripts/research-current-image4-initializer-amnm.py

wsl -d Ubuntu-22.04 -u root -- env PYTHONPATH=/home/wh1stl3/.local/lib/python3.10/site-packages /usr/bin/python3 -B /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/scripts/research-current-image4-initializer-amnm.py --kernel /root/nuwa-pmap-ret-native-20261111/diagnostic-20261111-r1/renderer-baseline.macho --kernel-sha256 7fd3d933aae66d8e34a0d3ebfa142137978976d7521e04cef20321109750b6f4 --adt /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/owner-pmap-ret-continuation-verifier-final-20261111/adt-generation/final.adt --adt-sha256 885094de4597fb2d1734ba4092c805968097d021c8f482653b238436586d27a4 --output /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/image4-initializer-amnm-20261111/evidence-r2.json

wsl -d Ubuntu-22.04 -u root -- env PYTHONPATH=/home/wh1stl3/.local/lib/python3.10/site-packages /usr/bin/python3 -B /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/scripts/research-current-image4-initializer-amnm.py --kernel /root/nuwa-pmap-ret-native-20261111/diagnostic-20261111-r1/renderer-baseline.macho --kernel-sha256 7fd3d933aae66d8e34a0d3ebfa142137978976d7521e04cef20321109750b6f4 --adt /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/owner-pmap-ret-continuation-verifier-final-20261111/adt-generation/final.adt --adt-sha256 885094de4597fb2d1734ba4092c805968097d021c8f482653b238436586d27a4 --negative-self-check /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/image4-initializer-amnm-20261111/evidence-r2.json --negative-output /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/image4-initializer-amnm-20261111/negative-checks-r2.json
```

Actual exits: `py_compile` 0; normal run 0 (28 semantic groups, 52 mechanical
checks, no failures); negative run 0 (25/25 rejected). The runner refuses to
overwrite evidence (`open('x')`); a rerun needs a fresh output path.

Reused-source hashes recorded in the evidence:
`audit-image4-runtime-provider.py` `39e5d879...ebecbd`,
`build-kernel-entry-probe.py` `e34c0de7...9bb77a`,
`nuwa_launch_context.py` `40e1b776...64de8f`.

## Limitations

- The IOKit/OSData objects are fixtures from the same ADT, not a live
  IORegistry; the loader/conversion is the next thing to investigate.
- Host-only: no device, no real boot, no Apple trust chain, no nonce or
  signature validation, no authentication.
- The wrong-type case uses the existing `safeMetaCast` fixture to represent a
  non-OSData property; it is an explicit fixture, not a device observation.
- The write ledger is only the traced initializer interval; `SecureDTInit`
  writes before it are excluded, and window writes are not all initializer
  state writes.
- The runner stops on invalid memory/exception/budget as well as
  boundary/panic; per-dependency admission is not implemented.
- The pre-fix `evidence.json` and the parallel verifier's pre-fix result do not
  constitute a pass for this r2 version.
- Integration, independent review and any device decision remain with the
  parent orchestrator.
