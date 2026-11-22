# FDR loader properties — static analysis

Donor `IOMFB_FDR_Loader` from iPhone10,3 iOS 16.7.16 20H392 OS image,
SHA-256 `a82f6ee8fad7fdfa83fcefcad0f6e443142419f41dab501b2371568902f99561`.
`llvm-objdump --macho --disassemble --symbolize-operands` and `__cfstring` /
`__cstring` dumps give the following addresses.

* `0x100001f24` obtains the main display and `0x100001f38` calls
  `IOMobileFramebufferGetServiceObject`; its result is stored at
  `0x10001c008`. `0x100001ff0` reads that service for `NormalModeEnable`;
  `0x1000021b8` reads the same global for `ADCLLoadAll`. These are properties
  on the display service, not its provider.
* `0x100001ff4` references `NormalModeEnable` CFString `0x100018c70`;
  `0x1000021bc` references `ADCLLoadAll` CFString `0x100018c50`. Both call
  `0x10000135c`: `IORegistryEntryCreateCFProperty` at `0x100001380`,
  `CFBooleanGetValue` at `0x10000138c`, normalized to true if nonzero.
  Missing property reaches `exit(1)` at `0x10000143c`. ADCL is read on the
  branch at `0x1000021ac`, not necessarily on every execution.
* `color-accuracy-index` CFString `0x100018cb0` is read at `0x1000020dc`
  via `0x1000012f8`, which uses `CFNumberGetValue` type 10 and defaults to
  zero if absent. It is conditional and not a missing-property fatal.

The experimental display publishes `NormalModeEnable=true` and
`ADCLLoadAll=false`, both OSBoolean. False is an experiment, not a claim of
panel calibration: we have no panel calibration data. The loader reads the
CFBoolean and ORs it with a separate mode predicate at `0x1000021d4`; skipping
all calibration loading on false is not established. Normal mode switching and the later
`NormalModeActive` read can still fail; no runtime outcome is inferred.
Failure to publish aborts with refused reason 15. Canvas and CLI remain intact.
Authentication NOT REACHED; device execution and independent verifier pending.

## Build blocker

The initial compact ON rebuild stopped at
`scripts/verify-nuwa-display-host-abi.py:617`, unresolved-symbol fingerprint
changed. Compared with `out/nuwa-r35l-fdr-on-compact/archive/archive.json`,
the new board object imports `_kOSBooleanTrue` and `_kOSBooleanFalse`. The
fingerprint gate remains enforced and its no-vsync expected value is updated
to `a2d0d02b50e7819b421d742e489a9761e6d8e808f4258bbd9a2c4be8460d8120`.
`git diff --check` was self-checked; independent verifier has not rerun a
final build.

The second compact ON build completed, producing kernel SHA-256
`e9f0b5e125be778b9c3fff8939659a6c9f67c61fb722c70a331c5ee8c8547b2d`.
Packaging then stopped at `scripts/build-ufs-apfs-root-chmh-r35-display.py:48`:
the ON profile accepts only hashes in `DISPLAY_KERNELS`, which does not
include this new kernel. The exact hash was subsequently added to the ON
allowlist without changing its enforcement.

## Final host package — self-checked

| Item | Digest |
| --- | --- |
| Kernel SHA-256 | `e9f0b5e125be778b9c3fff8939659a6c9f67c61fb722c70a331c5ee8c8547b2d` |
| Outer SHA-256 | `9aa47369b86ec9b7303efde1e1274877d979c6bb64c4b297456ed0621c2ecd84` |
| FAT SHA-256 | `cb544f11410bfc7f8c6c54f86c7072779152ede71d5c08e41de55c45b620251b` |
| Rebound CHMH SHA-384 | `14887a83f01b59d862b5de4d10589da7bd3d7fd63d4dc504ca2f471e6f710a77a61ad98f310a974acc06a6676eced1ec` |

Separate outer audit extracted the same kernel hash and the NUL-terminated
`NormalModeEnable` string at file offset `0x1370a0`. `fsck.fat -vn` and
`mdir` report 11,914,752 free bytes, above the 8,388,608-byte minimum.
Outer-readback `unixnu.toml` matches
`out/nuwa-r35l-cli-canvas-audit-20261122/outer-readback/EFI/UniXNU/unixnu.toml`
byte-for-byte. No device action; runtime and authentication remain unverified.

The exact final packaging and audit commands, run under WSL Ubuntu-22.04 as
root from this checkout with `/home/wh1stl3/.local/bin/python3.11 -B`, were:

```sh
S=scripts/build-ufs-apfs-root-chmh-r35-display.py
K=out/nuwa-fdr-properties-20261122-compact-r2/kernel.macho
H=e9f0b5e125be778b9c3fff8939659a6c9f67c61fb722c70a331c5ee8c8547b2d
P=out/nuwa-fdr-properties-20261122-package-r2
A=out/nuwa-fdr-properties-20261122-audit-r2
$PY -B "$S" --kernel "$K" --kernel-sha256 "$H" --enable-display --output "$P" </dev/null
$PY -B "$S" --kernel "$K" --kernel-sha256 "$H" --enable-display --output "$A" --audit "$P" </dev/null
fsck.fat -vn "$A/actual-vendor-ramdisk.img"
mdir -i "$A/actual-vendor-ramdisk.img" ::
```

Set `PY=/home/wh1stl3/.local/bin/python3.11`; use fresh output paths for a
verifier rerun. The original ON build invocation and input paths are recorded
in `nuwa-r35l-display-dsp-20261122-observation.md`. The packager pin change
and inherited low-level changes still require deep_reviewer review.
