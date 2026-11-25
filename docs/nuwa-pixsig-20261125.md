# nuwa PIX swap-source diagnostics — 2026-11-25

Host candidate only, **self-checked**; no device access or flash.
Authentication NOT REACHED; independent rerun pending.

## Hooks and interpretation

`scripts/verify-nuwa-display-host-abi.py:101–109` inserts three success hooks
into the staged GopFramebuffer `NativeLegacyDisplay.cpp` (upstream pin
`e47c1b8de169cd2bd0b885c7d85e433010e3cdf2`, BSD-2-Clause-Patent, unchanged):

| Staged `archive/NativeLegacyDisplay.cpp` | Counter |
|---|---|
| `kickOnce:307`, validated null surface, black fill and store barrier completed | `blank_ok` (`bk`) |
| `kickOnce:349`, half conversion and store barrier completed | `surface_ok` (`so`) |
| `kickOnce:391`, regular/differential CPU copy and store barrier completed | `surface_ok` (`so`) |

`co` stays a legacy aggregate. Failures do not count in `bk` or `so`.
GPU/direct and software-vsync are absent from this CPU-only candidate. Both
surface paths sample after the existing store barrier and outside copy
timing, but before `OSSafeReleaseNULL(source)` or request retirement: the
read-only, cache-prepared source mapping is still live. The sampler skips
source reads in interrupt context, with IRQs disabled, or with preemption
disabled. A skipped sample still counts the successful copy.

The window is the center of the **source rectangle actually copied** (the
copy starts at source origin and can crop a larger backing surface); `w/h`
are that rectangle’s dimensions, `st` is the underlying source row stride.
The sampler checks that rows fit the source allocation, reads only
`min(w,16) × min(h,16)` pixels and uses a 512-byte color table on the stack.
No heap allocation, full-screen pass or wait.

| Source FourCC | Handling |
|---|---|
| `BGRA` (`42475241`), zero planes | Bytes B,G,R,A → canonical 8-bit RGB; alpha ignored |
| `RGhA` (`52476841`), zero planes | Little-endian RGB binary16 components; alpha ignored, signed zero normalized, NaNs canonicalized and ignored for `nz` |
| `&BGA` (`26424741`), other IDs/plane layouts | `fmt_unsupported` (`unk`), no source reads; not treated as linear BGRA |

CRC-32/ISO-HDLC over canonical row-major RGB (RGB bytes or three LE
binary16 words per pixel). `nz` counts pixels with any nonzero, non-NaN RGB
channel; `uc` counts distinct RGB colors, including black, capped at 64.
The latest surface record retains its ordinal (`so`), `mach_absolute_time()`
ticks, dimensions, stride, format and statistics. `chg` compares only
adjacent valid surface records with matching width, height, stride and
format; blank fills do not supply a surface record, and missing or
unsupported samples break comparison. The panel takes one non-waiting
snapshot; ordinal and time are retained internally, not separate fields.

- Only `bk` advanced: this window recorded successful clears, not successful
  surface copies.
- `so>0` with valid black/constant samples: only the center region is known;
  this does not show that CoreAnimation rendered nothing.
- Comparable samples changed while the screen remained black: investigate
  downstream copy, conversion and scanout first.

`PIX bk=… so=… unk=… chg=…` and
`PIX+ w=… h=… st=… fmt=… crc=… nz=… uc=…` follow DSP at `PROC` priority.
`st`, `fmt` and `crc` are hex; the other values are decimal. The row budget
keeps `PIX` before `PIX+`; narrow lines drop `uc` first. `PIX+` is absent
before a surface outcome and uses dashes for unavailable statistics.
The existing crash-row and scanout-ownership behavior is unchanged.

## Host fixture

Actual production sampler, formatter and selector. CRCs cross-checked with
Python `zlib.crc32`. Numbers before PIX rows are measured columns (asserted
≤78, including the worst-case geometry/counters):

```text
blank only
25 PIX bk=1 so=0 unk=0 chg=0
black
25 PIX bk=1 so=1 unk=0 chg=0
56 PIX+ w=20 h=20 st=60 fmt=42475241 crc=f5a0f415 nz=0 uc=1
identical center signature
25 PIX bk=1 so=2 unk=0 chg=0
56 PIX+ w=20 h=20 st=60 fmt=42475241 crc=f5a0f415 nz=0 uc=1
solid, signature changed
25 PIX bk=1 so=3 unk=0 chg=1
58 PIX+ w=20 h=20 st=60 fmt=42475241 crc=a20c4b5d nz=256 uc=1
gradient, capped unique colors
25 PIX bk=1 so=4 unk=0 chg=2
59 PIX+ w=20 h=20 st=60 fmt=42475241 crc=bda2bb3d nz=255 uc=64
small/different geometry
25 PIX bk=1 so=5 unk=0 chg=2
54 PIX+ w=3 h=2 st=10 fmt=42475241 crc=00ba12f9 nz=1 uc=2
unsupported format
25 PIX bk=1 so=6 unk=1 chg=2
47 PIX+ w=3 h=2 st=10 fmt=26424741 crc=- nz=- uc=-
unsupported breaks comparison
25 PIX bk=1 so=7 unk=1 chg=2
54 PIX+ w=3 h=2 st=10 fmt=42475241 crc=45848421 nz=1 uc=2
half RGB
25 PIX bk=1 so=8 unk=1 chg=2
53 PIX+ w=1 h=1 st=8 fmt=52476841 crc=b4b105c9 nz=1 uc=1
no sample in elevated context
25 PIX bk=1 so=9 unk=1 chg=2
46 PIX+ w=1 h=1 st=8 fmt=52476841 crc=- nz=- uc=-
61 PIX bk=4294967295 so=4294967295 unk=4294967295 chg=4294967295
73 PIX+ w=16384 h=16384 st=ffffffffffffffff fmt=ffffffff crc=ffffffff nz=256
```

## Final package and verifier

`out/nuwa-pixsig-20261125-package/vendor_boot.img`, 100,663,296 bytes.
Single-core native replay. The pure-Python readback audit checked the
outer header/tail and entire FAT file set against crashframes: only the
kernel and its ADT CHMH field changed. The 561-byte args, including
`nuwa-sb-stack=900`, `disable-jobs=com.apple.iconservices.iconservicesagent`,
all `offline-legacy-*`, and no `sheng-smp`, are byte-identical. Seed is
unchanged. The 67,108,864-byte FAT has **11,021,824 bytes free** (≥8 MiB).
`fsck.fat -vn` agreed with the Python audit. DSP, PEER and linked crashcap
fixtures also passed the host self-check. UniXNU upstream HEAD before and
after the build was `8542980d02b4d2cc5c32ee3542de1760b2562aac`; the build
used the existing checkout `693f5d9cae8a408dd18b39f3f9fdc4228c934241`.

| Artifact | Digest |
|---|---|
| Kernel SHA-256 | `e00d6a3fba5bfa9f6601e11a1dd29115c902f62f1eb492e51bc3cd10a012f048` |
| Outer SHA-256 | `28d45ab6c3d7c5ec79cf14543af4836dadf04de7eddaa91fd876b36bc831dbcc` |
| CHMH SHA-384 | `4d752ffcbe7e174d0dac4bddec403a8bc0bf809eb161cb08d81a1770f357832b6bb1aa713d185a73dc96127c00f55599` |
| Readback FAT SHA-256 | `a1eeceec50fd185a59347fd9f8e5f8648b52155cbf71fef0ff7703686c89fe3a` |
| Seed SHA-256 | `3c81135b384d8e090521205f2d69b3c197521e6d03c63682419d021bf0f24e5e` |

Rollback outer SHA-256:
`b83021a7799cacb3bd4086162cae9474f267dc6dc6294eb11d5c4f0c6374e157`.

Rerun the single-core build in [the crashcap recipe](nuwa-crashcap-20261125.md#reproduction)
with `--pixsig` and a fresh `B` (this run used
`out/nuwa-pixsig-20261125-build-r2`); choose a fresh `P` for repacking.

```sh
"$PY" -B tests/test-nuwa-pixsig.py
"$PY" -B tests/test-nuwa-dspcount.py
"$PY" -B tests/test-nuwa-peer-probe.py
"$PY" -B tests/test-nuwa-crashcap.py "$B/kernel.macho"
MAKEFLAGS=-j1 taskset -c 0 "$PY" -B scripts/package-nuwa-crashcap.py \
  --pixsig --base "$BASE" --kernel "$B/kernel.macho" --out "$P"
"$PY" -B scripts/package-nuwa-crashcap.py --pixsig --audit-only \
  --base "$BASE" --kernel "$B/kernel.macho" --out "$P"
fsck.fat -vn "$P/readback-fat.img"
```
