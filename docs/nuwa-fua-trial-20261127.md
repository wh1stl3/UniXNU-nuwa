# nuwa FUA-permissive disposable Data trial — 2026-11-27

Status: **host self-checked; flashed once to `vendor_boot_a` under explicit
2026-11-27 authorization, not booted**. The flash observation is
`docs/nuwa-fua-trial-20261127-observation.md`. This is an experiment package,
not a production candidate. The user explicitly accepted the risk that a sudden
power loss may lose data and that this package makes **no medium-durability
claim**.

Baseline: branch `research/nuwa-ufs-owner-api-20261126` at
`cb5973aee8db888ed41ca3594fe1ea5cb431ffde` plus the FUA change committed with
this document update.

## Scope

Only the RamBlock FUA/flush refusal policy changes. No mount logic, SB0 or
disposable write gate, authentication, partition table, DMA/IOMMU, locking
order, or boot argument changes.

Compile-time switch:

```c
#ifndef NUWA_DISPOSABLE_FUA_PERMISSIVE
#define NUWA_DISPOSABLE_FUA_PERMISSIVE 0
#endif
```

`NativeRamBlock.cpp` defines it only in a `NUWA_DISPOSABLE_DATA` build. The
build helper enables it only through `--disposable-fua-permissive`, which also
requires `--disposable-data --post-event`. A normal disposable build does not
define it and keeps the old refusal.

| Path | Default build | `NUWA_DISPOSABLE_FUA_PERMISSIVE=1` |
| --- | --- | --- |
| `doAsyncReadWrite()` with `kIOStorageOptionForceUnitAccess` | returns `kIOReturnUnsupported` before staging DMA | falls through to the ordinary read/write path and increments the FUA-request counter `nuwa_disposable_fua_requests` |
| `doSynchronizeCache()` | returns `kIOReturnUnsupported` when the disposable store is healthy | returns `kIOReturnSuccess` after `native_ufs_store_order()` and increments `nuwa_disposable_flushes`; `kIOReturnIOError` if `directFailed` or the store-order check fails |

The flush comment and implementation state the important limitation: the
disposable overlay commits each staged run inside `writeRun()` (data pages,
order, log page, order) before its write is acknowledged, so no log is left
pending at flush. `native_ufs_store_order()` rechecks the existing session after
all earlier commands; it is not a UFS cache flush. The accepted UFS write is
still the existing non-FUA `WriteVolatile` command, and the accepted FUA bit is
not forwarded to the medium. `flush=N` counts successful return values, not
durable completions.

The production `Provider<CandidatePort, false>` and `fuaProvenLocked() == false`
are unchanged.

## On-screen annotation

The existing panic-safe row 7 now ends with `fua=N flush=N`; the FUA trial build
also appends `FUA-EXP-nodur`:

```text
[data-trial] DATA0 st=... ... first-attempt fua=12 flush=3 FUA-EXP-nodur
```

The fields come from `nuwa_disposable_fua_requests` and
`nuwa_disposable_flushes`. The normal draw path and the already-reviewed
`boot_progress_critical_paint()` path both append the suffix. No new row and no
new draw mechanism is used. The trial kernel also contains the string
`NUWA-FUA-TRIAL-20261127`; an ordinary post-event build does not.

## Build and artifacts

WSL root, device worktree:

```sh
/home/wh1stl3/.local/bin/python3.11 -B scripts/build-nuwa-display-native.py \
  --base /mnt/d/Code/PortingiOS/UniXNU \
  --cpo /root/nuwa-pmap-ret-native-20261111/nuwa/ios-16.7.16-20H392/nuwa_pmap_ret/tree/build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/iokit/DEVELOPMENT/IOPMGR.cpo.json \
  --linker-dir /opt/unixnu-linux/CommandLineTools/usr/bin \
  --r35-dir out/nuwa-r35-20261119 \
  --r35l-dir out/nuwa-r35l-regs-full-20261121 \
  --cpu-only --no-software-vsync --candidate --mg-reset --hid-standin \
  --crashcap --pixsig --data-persist-diag \
  --data-candidate-gpt /mnt/d/Code/PortingiOS/nuwa/.cache/device-evidence/20261107-recovery/gpt-sda.bin \
  --disposable-data --post-event --disposable-fua-permissive \
  --out out/nuwa-fua-trial-20261127-build-r3

/home/wh1stl3/.local/bin/python3.11 -B scripts/package-nuwa-crashcap.py \
  --base /mnt/d/Code/PortingiOS/UniXNU \
  --kernel out/nuwa-fua-trial-20261127-build-r3/kernel.macho \
  --out out/nuwa-fua-trial-20261127-package \
  --disposable-data-template /mnt/d/Code/PortingiOS/nuwa/worktree-ufs-neon-20261126/out/nuwa-ufs-neon-20261126-package/vendor_boot.img \
  --post-event
```

| Artifact | Value |
| --- | --- |
| Kernel (52,207,616 B) | `b414fcf6648c61be85015712d48ca610ad0a96314d691066c423ef8d8ca01cad` |
| Outer (100,663,296 B) | `b5d1b9f1d75da5ac2c37f9ee52d570f3e7afb40b734189f52d05efa11c91c97e` |
| FAT readback (67,108,864 B) | `f9f96207d2c7ef2670e7977e9fd98cb236433705a329ab8a6a7d3f411daf2e2a` |
| CHMH SHA-384 | `5c730ebffe45b2ef1f47226bb4d48e7a9f9d5fb10fef33742c44c3cae3c42eabe2ec7a4d87d562633796f02b57317436` |
| ADT SHA-256 (13,680 B) | `05db501aa06408456d557ede61c467d68b2bd53dea75cbb5eecb4d1c4975a95b` |
| Args | 602 B, same tokens; no new boot arg |
| Seed / trust | `3c81135b…` / `eb1475f6…` unchanged |
| FAT free | 11,021,312 B |
| Template outer | `18fa4941…` exact read-root outer |

The FAT changes are only the kernel, its ADT CHMH and the
`nuwa-disposable-data=1` config the template already injects. The seed decoded
from the final FAT is still the pinned 8 GiB seed (`26957263…` raw,
`a106b0ce…` identity).

## Default-build and experimental disassembly

A control `NativeRamBlock.o` was built from the same current source and the
recorded r8 compile command without `NUWA_DISPOSABLE_FUA_PERMISSIVE`
(`out/nuwa-fua-trial-20261127-control/NativeRamBlock.default.o`,
SHA-256 `c0a297796bb93c946c6891281dc208bc96502581ad2b7710e642dd9cc0695ee4`).

Default `doAsyncReadWrite` at `0x1188-0x11dc`:

```text
ldrh w8, [x20]          ; attributes->options
tbnz w8, #0, 0x11d8     ; kIOStorageOptionForceUnitAccess
...
0x11d8: add w0, w0, #5  ; 0xe00002c2 + 5 = kIOReturnUnsupported
```

Default `doSynchronizeCache` selects `0xe00002d8 - 17 = 0xe00002c7`
(`kIOReturnUnsupported`) when the disposable store is healthy, and
`0xe00002d8 - 14 = 0xe00002ca` (`kIOReturnIOError`) after a failed commit.

Experimental object (`out/nuwa-fua-trial-20261127-build-r3/NativeRamBlock.o`,
SHA-256 `dbf1de8545ffca41d15e29cdf2b22ee95695af3ae2f2354aebdbe61e7fb8e665`):

```text
ldrh w8, [x20]
tbz  w8, #0, 0x1190      ; no FUA: skip the counter
adrp x8, _nuwa_disposable_fua_requests
ldxr/add/stxr loop       ; increment in place of the old refusal
0x1190: ...              ; ordinary gate and I/O path
```

No `kIOReturnUnsupported` return remains in the FUA branch. In the linked
kernel `_ZN14NativeRamBlock16doAsyncReadWrite...` the same `adrp/add` targets
`0xfffffff007ac5f10` (`_nuwa_disposable_fua_requests`). Its
`doSynchronizeCache` calls `_native_ufs_store_order`, and on success increments
`0xfffffff007ac5f18` (`_nuwa_disposable_flushes`) before returning zero.

The linked renderer `_boot_progress_critical_paint` loads both counters and
passes ` fua=%llu flush=%llu%s` to `_snprintf`; the third argument points at
`FUA-EXP-nodur`. It still calls `_px_text` twice and does not call `_refresh`
or `_boot_progress_prepare_scanout`.

## Tests run (all self-checked)

| Test | Result |
| --- | --- |
| `scripts/test-nuwa-postevent.py` on `build-r3/BootProgress.c` and `native-with-stabs.macho` | PASS; includes new `fua=7 flush=3` and `FUA-EXP-nodur` row assertions, critical top=120960 below=0, linked order and two `px_text` calls |
| `tests/test-nuwa-retained-entry.py out/nuwa-fua-trial-20261127-build-r3 … --disposable` | exit 0; `PASS staged disposable: … non-FUA WRITE(10) … no flush` |
| `tests/test-nuwa-crashcap.py build-r3/kernel.macho` | exit 0 |
| `tests/test-nuwa-data-persist.py /mnt/d/Code/PortingiOS/UniXNU` | exit 0 |
| `tests/test-nuwa-disposable-data.cpp` (ASan/UBSan) | exit 0 |
| `tests/test-nuwa-data-write.cpp` (ASan/UBSan) | exit 0 |
| `tests/test-nuwa-dualbank.cpp` (ASan/UBSan) | exit 0 |
| `package-nuwa-crashcap.py --audit-only`, `fsck.fat -vn`, `mdir` | exit 0; 9 files, 11,021,312 B free |
| `porting-record.py check --device .` | exit 0 (14 areas) |

The post-event test compiles and executes the generated `bp_fua_suffix` and
asserts the row contains `fua=7 flush=3`; it is not a screen photograph.

## Limits

- The outer was written to `vendor_boot_a` once (bootloader acknowledgement
  only); no boot, panic or panel visibility was observed. The two-row panic
  band remains verified only in the host framebuffer. Flash details:
  `docs/nuwa-fua-trial-20261127-observation.md`.
- `FUA-EXP-nodur` and `fua/flush` are diagnostics; they do not certify that
  the medium stored anything. A power loss can lose acknowledged data.
- The UFS write command is still the existing non-FUA `WriteVolatile`; the
  accepted RamBlock FUA bit is not a UFS FUA bit.
- The production path, default build and disposable write gate remain
  refusing FUA/flush as before; this package is not a route to enable them.
- The exact outer hash belongs to `out/nuwa-fua-trial-20261127-package`; a
  rebuild into another directory changes FAT timestamps. A verifier rebuild
  should compare the switch behavior, marker strings and tests rather than
  require the same outer hash.
