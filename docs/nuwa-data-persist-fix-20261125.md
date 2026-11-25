# nuwa Data `st=4` — 2026-11-25

**Cause identified for the pinned PIX build: its retained-domain UFS
provider refuses mode-2 Data windows by design. Diagnostic package only;
Data persistence is not fixed.** Host self-checked; no device access or
flash. Authentication NOT REACHED; independent verifier pending.

## Evidence and open path

Reported: `PU1 DATA st=4 hdr=9 gpt=0/ff lba=0` and
`PU2 pres=0 ld=0 wr=0 sy=0 er=0`. In
`package/nuwa-ramblock/NativeRamBlock.cpp:94–164`, the three assignments
of `st=4` cover provider-open refusal, overlay-open/allocation failure and
restore failure. The latter two paths assign the first LBA and execute
the second GPT check; the stable `0/ff`, `lba=0`, `hdr=9` tuple instead
matches refusal. A GPT result of zero means the valid+ready precheck and
the GPT header/entry CRC checks passed before open.

Both `native-link.map` files (PIX and this candidate) link the same
`run-r5-visible-candidate/libObserveNativeUfs.a(NativeUfs.late.o)` from
`UniXNU-nuwa/out/nuwa-ufs-apfs-root-integration-20261114`. Its staged
sources are also available under the same relative path in this
worktree. `NativeUfs.cpp` SHA-256
`bb994c583382755ddfae954b23aff94d77a97428c7c933232b574ad3cd64b2bf`;
`RootCommands.h` SHA-256
`a16e55e1c1b3665231ec5d4c07fe9b1cdeb7edf834bd48f79e3aa80d6f8fa13a`.
Relevant code in **these** staged sources:

- `NativeUfs.cpp:873–879,1874–1875`: `StoreGeometry` stores `valid,
  first, last, imageBytes, entriesLba, headerCrc, entriesCrc, entryCount`.
  It is filled from the validated root layout, using the GPT userdata
  LBAs and root manifest image size. The two window globals start at zero.
- `NativeUfs.cpp:889–911`: `reserveBlocks()` caches
  `sheng-log-reserve` in MiB (default 1,024 for absent/invalid input or
  above 16,384) times 256. `storeMode()` caches the parsed
  `sheng-data-persist` in `0..2`, defaulting to zero for absent/invalid
  input. The pinned PIX FAT args contain mode 2 and reserve 1,024.
- `NativeUfs.cpp:916–944` checks these predicates in order:

  ```cpp
  if (!storeMode ()) reason = "off";
  else if (!gStoreGeometry.valid || !gHost.ready) reason = "no root layout";
  else if (gStoreRegionBlocks) reason = "already open";
  // partition = last - first + 1; imageBlocks = ceil(imageBytes / 4096)
  if (!blocks || reserve >= partition || blocks > partition - reserve) reason = "size";
  else if (partition - blocks - reserve < imageBlocks + 1024) reason = "overlaps the root image";
  // first = last + 1 - reserve - blocks
  if (storeMode () == 2 && !hostStoreOpen (first, blocks)) reason = "window refused";
  // On success only, publish region globals, set *firstLba and return 1.
  // For any return, supply reason through *why if non-null.
  ```

- `RootCommands.h:317–320`: actual `hostStoreOpen` body is `return false;`.
  Thus it does **not** check alignment, LBA contiguity or block size, and
  never registers a window. `hostLogOpen` is also stubbed (305–308);
  `hostWrite4k` and `hostSyncCache` return `kIOReturnNotWritable`
  (345–354). These are not the functions in the current ShengUfs feed
  checkout. For contrast, that checkout's `RootCommands.h:282–290`
  checks prior open, nonzero length, 32-bit LBA/end bounds and overlap
  with an open log range. It represents one contiguous 4 KiB LBA
  interval without a 2 MiB alignment rule.

In both linked native binaries `_native_ufs_store_open` is at
`0xfffffff0079aa8f0`. Its `cmp w8,#2` at `…aabc` selects the refusal
path: `mov w0,#0` at `…aac4`, pointer `0xfffffff00713bcf5` to `"window
refused"` at `…aac8–…aacc`, then the shared return path; there is no
host-window call or alignment check. Disassembly of open/write/sync/GPT
check matched between baseline and diagnostic native binaries.

## Geometry

Recorded userdata GPT, LUN 0: `board.toml:[userdata]` and
[`device-evidence-2026-11-07.md`](device-evidence-2026-11-07.md#1-storage).
Root size is from the [write/readback record](nuwa-launchd-reached-20261115.md);
seed logical size is verified against `out/seed-full-20261125/final-fat-roundtrip.raw`
and its encoded input SHA-256 matches the FAT seed. All LBAs are 4,096 B.

| Quantity | Value |
|---|---:|
| Seed logical bytes / 4,096 | 8,589,934,592 B / 4,096 = 2,097,152 pages |
| Bitmap blocks, ceil(pages / (8 × 4,096)) | 64 |
| Window blocks, 1 + bitmapBlocks + pages | 2,097,217 (8,590,200,832 B) |
| Root image, 8,446,279,680 B / 4,096 | 2,062,080 blocks |
| userdata first / last, inclusive | 3,110,976 / 61,850,618 |
| userdata length | 58,739,643 blocks (240,597,577,728 B) |
| Reserve, 1,024 MiB × 256 blocks/MiB | 262,144 blocks |
| Data range, half-open | `[59,491,258, 61,588,475)` |
| Root range, half-open | `[3,110,976, 5,173,056)` |
| Gap after root and before Data | 54,318,202 blocks (guard requires 1,024) |
| Log+export range if enabled in a provider that supports writes | `[61,776,891, 61,850,619)` |

The window is inside userdata, below the tail reserve, and clear of both
root and GPT. `59,491,258 % 512 = 442`; no 2 MiB alignment requirement is
implemented. These are recorded coordinates, not a new device read.

| Failure | Disposition for the reported tuple and pinned PIX inputs |
|---|---|
| `off` | Excluded: mode 2 in args; cached nonzero mode is required to reach the call. |
| `no root layout` | Excluded by pre-open `gpt=0`; the source tests the same valid/ready flags. |
| `already open` | Excluded for the linked mode-2 path: the only assignment is after success, and mode 2 cannot succeed. `storeAttached` also guards repeats on the consumer. |
| `size` | Excluded by the recorded size/seed/reserve. |
| `overlaps the root image` | Excluded by the recorded placement and guard. |
| `window refused` | Confirmed offline for the pinned build and recorded inputs; direct on-screen readout pending. |

Do not remove the stubs: the [2026-11-22 write-safety review relay](nuwa-session-20261122-findings.md)
records that a write timeout quarantines the single retained slot; root
reads cannot recover. Changing only open would still leave writes/sync
disabled and would no longer faithfully refuse mode 2. A durable-write
and root-read recovery design needs separate review. No geometry, GPT,
root, DMA, lock, provider or I/O policy was changed.

## Diagnostic and self-check

`attachStore()` publishes a short label from the existing `why`
out-parameter before setting the outcome state. `why=ok` means **window
open only**, not overlay success; `unknown` denotes an unrecognized reply,
and `-` denotes no result. Enabled only in the diagnostic replay banner;
it keeps PU1/PU2 slots and shortens PU1 `hdr/gpt/lba` to `h/g/l`:

```text
PU1 DATA st=4 h=9 g=0/ff why=window l=0
PU2 pres=0 ld=0 wr=0 sy=0 er=0
```

On an independently authorized future boot, record exact PU1 and PU2 and
the booted outer hash. If `why=size/overlap`, collect live userdata first/
last (4 KiB LBA), parsed reserve and seed/root byte lengths before changing
placement. If `why=ok` but state remains 4, investigate the overlay path
using `h`, `g`, `l` and PU2 rather than changing the provider. Seeing
`why=window` is expected and is not a persistence test.

The host fixture compiles the staged provider-open function and actual
stub with synthetic ready/mode inputs, production bitmap math, reason
mapping, and generated PU1 formatter. It passes all six refusals, the
exact 1,024-block guard and one block below it, bitmap rollover, mode-1
success and 16-digit LBA fit. PU1 is at most 51 columns including its
prefix and padding. Single-core link replay, linked crashcap and PIX
fixtures, independent-from-builder Python outer/FAT readback and
`fsck.fat -vn` all ran as local self-checks.

`out/nuwa-data-persist-diag-20261125-package/vendor_boot.img` is
100,663,296 B. Outer header/tail and all other FAT files match the
pinned PIX outer. The experimental CHMH is rebound; only the kernel and
ADT CHMH change. Args (561 bytes), seed and trust cache are byte-identical;
no `sheng-smp` or `sheng-data-reset`. Readback FAT free: 11,021,824 B.

| Artifact | Digest |
|---|---|
| Kernel SHA-256 | `fead9250859d518dc6ad16473b18def894571ba7910a8e48ae7519b64476e49d` |
| Outer SHA-256 | `fd4229d657e1986c521f932b9651c899a71ef5af1ca569f0742a438a1b2c3d09` |
| CHMH SHA-384 | `2e08e425c52195c772a6100b31d80faad8e6c8b23279aeca9a598d6c4fccbbd035673208c69aef3d1f8e58f3f2f75d75` |
| Readback FAT SHA-256 | `253e23c1d5a85e37e9f9493a18d66e7ddd64332733db722ff6cfb6bcde88f204` |
| Seed SHA-256 | `3c81135b384d8e090521205f2d69b3c197521e6d03c63682419d021bf0f24e5e` |

Verifier: use the [PIX recipe](nuwa-pixsig-20261125.md#final-package-and-verifier),
add `--data-persist-diag` to the build, then replace the package/audit
`--pixsig` flag with `--data-persist-diag`; use fresh `B`/`P`. Also run
`"$PY" -B tests/test-nuwa-data-persist.py "$BASE"`. Build pin
`693f5d9cae8a408dd18b39f3f9fdc4228c934241`, UniXNU upstream HEAD before and
after `8542980d02b4d2cc5c32ee3542de1760b2562aac`, not adopted. The replay
reuses the in-repository late object transform from
`scripts/build-nuwa-platform-power.py` and checks that it reproduces the
historical RamBlock late object before accepting the new one.
