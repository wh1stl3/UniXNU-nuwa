# nuwa disposable Data — 2026-11-26

Host-only, **self-checked**. Implementation base `1aef05f2cf752c1a404b238b8a59b8fecbc7c2d8`.
Read-root template is outer `18fa4941696667d1813442022ea71fc48e4c414b1abadb1caf73774fcc76202a`.
No device action, independent build verification or final artifact acceptance.

## Admission and result

- Build defaults off (`--disposable-data` sets `NUWA_DISPOSABLE_DATA=1` in the
  dedicated single-core UFS and RamBlock TUs). The runtime gate is
  `nuwa-disposable-data=1` with Data mode 2; production write/reset, logging,
  SMP args and legacy mode 1 cannot open the experimental route. The production
  `Provider<CandidatePort, false>`, empty cold-start evidence and unproved FUA
  remain unchanged. Earlier firmware/DMA producer exclusion is an accepted
  experimental assumption, not a finding.
- LU0, 4096 B, 61,850,624 blocks. The retained session must match that geometry;
  primary/backup headers and arrays get separate CRC, reciprocal-LBA, capacity,
  usable-range, GUID and table checks. Both arrays must match; `userdata`
  `[3110976,61850619)` may not overlap any other entry. Only placement with the
  exact qualified root length 8,446,279,680 B, 1024-block root guard and
  262,144-block tail reserve admits `[57393401,61588475)` (17,183,023,104 B).
- The one retained `gHost.lock` and Slot0 are shared with root and diagnostic
  reads. The writer checks bounds/state/ownership, then the existing `issue`
  checks ownership before DMA staging and again before the doorbell. It
  submits one LU0 WRITE(10), 4096 B host-to-device, **no FUA**. GOOD, matching
  attribution/OCS/length and zero residual are required; `FullWrite` means
  only full command completion. Any write error or experimental transport read
  error quarantines the shared session, preserving DMA/mapping; no retries,
  recovery commands, fallback writer or late-completion admission.
- At the RamBlock gate, data pages → internal completion order → log page →
  internal completion order → publish and account bytes. The internal order
  entry is not a flush, and never increments the sync counter. Staged provider
  `native_ufs_store_sync` returns false. XNU's IOStorageFamily
  `IOMediaBSDClient.cpp:2869` maps `B_FUA` to
  `kIOStorageOptionForceUnitAccess`; `IOBlockStorageDriver.cpp:1178–1185`
  passes those attributes and completes a dispatch error itself.
  `NativeRamBlock::doAsyncReadWrite()` refuses FUA before staging (non-success
  dispatch, no callback by RamBlock). Ordinary accepted I/O returns dispatch
  success and calls completion with the status and actual bytes once, after
  dropping the RamBlock gate. Sync/range sync/barrier reach `doSynchronize`
  (`IOBlockStorageDriver.cpp:1649–1684`); the two BSD flush ioctls convert
  errors back to errno (`IOMediaBSDClient.cpp:1807–1842`). A healthy
  experimental RamBlock returns unsupported; failed state returns I/O error.
  No advertised durable completion, observed FUA or cache state. APFS
  refusing this contract is an experimental result, not grounds to fake sync.

## Fresh, foreign, resume

The kernel **never initializes**. Without a verified offline initial anchor,
blank/foreign/wrong-seed/damaged metadata is refused, not reset. A failed
open after selection does not switch to writable volatile Data.

- **Fresh**: only a validated `NUWAXSB3` SB0 at generation 0 with empty
  map, zero SB1 and empty ring is a fresh experiment (`st=3`). No media page
  is present, so the immutable seed supplies all logical pages.
- **Resume**: only the same experimental format and exact seed can replay
  a consecutive `NUWAXLOG` prefix with checked latest data-page CRCs.
  A malformed/torn log or referenced page fails closed; an entirely absent
  suffix can lose completed work. `st=2` denotes recovered nonempty state,
  `st=6` denotes recovered ring-full read-only state. The kernel does not
  checkpoint or wrap the 512-record ring; current-session writes stop on
  exhaustion. No guarantee after power loss.
- **Initialization is a separate, explicit, one-time offline operation**, not
  a boot argument, boot menu action, feature of the outer, or authorization to
  write. The host generator emits `prepare.bin` (770 zero pages; clears both
  anchors, both map pairs and the entire old ring) and `commit-sb0.bin` (one
  seed-bound empty anchor). Any separately authorized workflow must establish
  an exclusive offline writer and verified restorable preimage for the full
  window first. Treat these as one consumed preparation/commit claim, never
  reinitialize a resumed run. For a specifically authorized nonempty
  preimage, only accept the zeroed metadata after full readback; commit SB0
  last, and verify resulting metadata against the exact expected contents.
  If interrupted or media state is ambiguous, stop: no completed receipt,
  no resume or automatic reapplication. Stale bank pages are not read
  or referenced by this initialization; old logs cannot survive verified
  prepare. Runtime cannot recognize or authorize the external operation.

### Final staged writer census (LU0, 4096-byte absolute LBAs)

| Route | Range | Final disposition |
| --- | --- | --- |
| `NativeUfsBlock::doAsyncReadWrite` | Root `[3110976,5173056)` | Rejects output `kIOReturnNotWritable`; verified reads only. |
| `native_ufs_log_write`, `native_ufs_log_panic`, `native_ufs_log_open` | Legacy log `[61842427,61850619)` | No open, constant failure. No panic bypass. |
| `native_ufs_export_write`, `native_ufs_export_blocks` | Legacy export `[61776891,61842427)` | Constant failure / zero capacity. |
| Old RamBlock overlay / production Provider | Legacy one-map `[59491258,61588475)`; discontinued probe at `57394041`; old v3 same full window | Old attach branch unreachable with mode forced to 2 or off; production backend not called, old v3 magic is rejected. These overlap, so do not allow concurrent old writers. |
| Raw partition exports | Named/block raw reads only | `native_ufs_part_find/read` and retained root commands do not export a media writer; controller register writes are not additional media writers. Opening raw Data IOMedia reaches the same RamBlock gate, not a second UFS writer. |
| Optional offline initializer | `[57393401,57394171)`; last operation SB0 at `57393401` | Separate host-only metadata files, not a boot writer. No device approval. |
| Disposable RamBlock | Ring `[57393659,57394171)`, two banks `[57394171,59491323)` and `[59491323,61588475)` | Sole linked media writer; runtime never touches either SB or map. |

The static census covers the staged kernel/RamBlock and the linked entry points,
not firmware/fabric inactivity or a simultaneous external raw writer. The
`18fa4941…` read-root outer is a boot-payload rollback reference only; it does
not restore changed Data. Any media rollback requires the separately verified
restorable window preimage; a write error/timeout does not imply no change.
Retain existing boot backups. Initializing, booting, writing or rollback
would each require applicable round-specific authorization.

## Exact host artifacts and reproduction

Inputs: UniXNU checkout `693f5d9cae8a408dd18b39f3f9fdc4228c934241`, upstream
HEAD before/after `e7bddb9a7eecdcf81f36da9fa38bd9d4d3f155c2` (not adopted).
Seed decoder and identity reuse `drivers/DarwinBoot/Test/packed_ramdisk.py`
and `drivers/RamBlock/SeedDisk.h` from that pin (UniXNU, BSD-2-Clause-Patent
for the driver). Local FAT extraction from the original outer compared
byte-for-byte to `final-encoded.img`; the decoder consumed 8 extents.
The final outer's extracted seed compares byte-for-byte to the original.
Its decoded stream also compares byte-for-byte to `final-disabled.raw`
(all 8,589,934,592 bytes, including zero gaps).
Do not use the old `seed-edited.raw` identity. CHMH is an experimental
binding, not authentication. Source review of the design did not approve
these exact artifacts.

| Artifact | Digest |
| --- | --- |
| Kernel (52,207,616 B) SHA-256 | `28e87a12b55067d442c2a7bd1de5a9e4a5790057464f3e40282398903f48cc34` |
| Outer (100,663,296 B) SHA-256 | `6695da9842f4da4d26c1f028adc48f3ffb8f6f369420653492028a74bf362fa5` |
| CHMH SHA-384 | `3abedb47bc3a96f1cfca1b27779e44c89f5553456535caffbf02da0a07d32dc6e275e06f1d43aef498a2ad92c6e33a2f` |
| Outer readback FAT SHA-256 | `087c692478cd3060f34b62d3eb9575bde8f045816eccac52aa74edc51da5ab52` |
| Original and final FAT seed SHA-256 | `3c81135b384d8e090521205f2d69b3c197521e6d03c63682419d021bf0f24e5e` |
| Decoded seed (8 GiB) SHA-256 | `26957263676b0312f3bebe213c2985deb8ce5652ac2ce3e99d59da77aba89584` |
| Logical SHNGSEED2 identity | `a106b0ce026771e221f578125e104a4854c2cbcda7c1b8390f6e056a47c63743` |
| Unchanged trust SHA-256 | `eb1475f643f45a974ebd40596f6e2b1cdf40205d2ca3c6094d774886099399c3` |
| `prepare.bin` (3,153,920 B) SHA-256 | `6bdcd73dcf47f64038afbce5c14c7fb2817da9e2074a2597acb8852898e6c3d2` |
| `commit-sb0.bin` (4096 B) SHA-256 | `b227e878961df9b0d30ccdd73663206e396d3d2a0466141377439d11f74a86f5` |

Final outer is in `out/nuwa-disposable-data-package-r2/`. Header and tail
unchanged, only kernel/ADT/TOML differ in FAT. `build-tag=nuwa-r35` →
`build-tag=data-trial`; append only `nuwa-disposable-data=1`.
Args 577 → 602 B; actual linked ABI consumes 608 B including NUL
(`pexpert/pexpert/arm64/boot.h:26`). Superseded 612-byte package is not
eligible. FAT free 11,021,312 B. Exact build/packaging argv, linked
disassembly, source and staged diffs and artifact hashes are retained in
`out/nuwa-disposable-data-review/`.

Verifier rerun: use the [single-core inputs](nuwa-crashcap-20261125.md#reproduction)
and [read-root recipe](nuwa-ufs-neon-20261126.md#reproduction-and-rollback),
adding `--pixsig --data-persist-diag --data-candidate-gpt <pinned capture>
--disposable-data` to the build. In the same worktree, rebuild to a fresh `B`;
audit the exact reviewed `P` (packing to a new directory can change FAT
timestamps). `T` is the exact original read-root outer and `BASE` the pinned
UniXNU checkout.

```sh
python3 -B tests/test-nuwa-retained-entry.py "$B" "$BASE" --disposable
python3 -B tests/test-nuwa-retained-entry.py "$READ_BUILD" "$BASE" --sb0 --output "$CHECK"
python3 -B tests/test-nuwa-crashcap.py "$B/kernel.macho"
python3 -B tests/test-nuwa-data-persist.py "$BASE"
# Compile and execute each of tests/test-nuwa-{disposable-data,dualbank,data-write}.cpp.
# Flags used: -std=c++17 -Wall -Wextra -Werror -pthread -fsanitize=undefined -fno-sanitize-recover=all.
python3 -B scripts/package-nuwa-crashcap.py --audit-only --base "$BASE" \
  --kernel "$B/kernel.macho" --disposable-data-template "$T" --out "$P"
fsck.fat -vn "$P/readback-fat.img"
mdir -i "$P/readback-fat.img" ::/EFI/UniXNU/Payloads
```

Production regression, crashcap, geometry, overlay and retained response
fixtures, final link and package/readback checks all ran locally. Host-only
result: self-checked; final reviewer and independent verifier pending.
