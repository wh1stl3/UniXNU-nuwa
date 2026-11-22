# 20H392 MobileGestalt cache invalidation — resume-only host candidate

SpringBoard still asserts after the earlier `display-scale=3` experiment.
The seed contains none of these caches. An old device-generated cache with
scale 0 is the working hypothesis, based on the reported venus result,
not a confirmed nuwa diagnosis. This opt-in **invalidates caches so MG
rebuilds them**, rather than repairing the scale source. Rebuilding may
slow the first boot. Remove this bypass once MG is observed deriving the
correct scale from ADT. This experiment preserves the existing Data overlay
and invalidates MG caches only by renaming the named files; it does not
reseed Data or delete caches. The diagnostic journal and normal boot writes
are separate from the cache treatment.

## Data prerequisite and recovery

Use a matching, already-initialized overlay for the same Data seed.
`NativeRamBlock::attachStore()` (`package/nuwa-ramblock/NativeRamBlock.cpp:85–136`)
uses `sheng-data-persist=2` for read-write persistence. Only
`sheng-data-reset=1` or `=2` makes `discardRequested()` true. With the key
absent, blank, mismatched or damaged stores are not reinitialized. The prior
candidate included `sheng-data-reset=1` and is invalid for testing an old
cache: it dropped the very pages needed for the experiment.

To revert, remove `nuwa-mg-reset=1` from the next boot profile while retaining
`sheng-data-persist=2` and keeping `sheng-data-reset` absent. With the affected
Data volume offline from iOS (and the device write separately authorized),
copy out any newly generated counterpart before moving each verified
`.nuwa-bak` file back to its original name on the same volume. Never overwrite
an existing cache in place, and use the journal plus directory inspection to
distinguish actual backups from skips and interrupted runs. On a
case-insensitive volume restore the Preferences alias only once. Turning the
argument off alone does not undo a rename.

## Early write path

`load_init_program()` calls `nuwa_data_mount_prepare()` before initproc exec.
After the APFS Data device/type/read-only checks succeed, Data calls
`nuwa_boot_watchdog_policy()`. At that existing call site the optional
MG helper runs independently of the watchdog policy, only with
`nuwa-mg-reset=1`, a writable Data mount, and `native_data_persist_state == 2`
(RW Resumed). The helper checks that state before any file operation, including
opening its journal. Other states publish `MG skip` and a console
`MG not attempted: DS=…` message with no MG filesystem I/O.

It checks the three fixed cache names in `nuwa_mg_reset.c`, opens their
parent directories without symlink traversal, verifies the same Data
device, and only renames regular source files. It checks the destination
without following its final symlink; any existing destination is kept.
The actual same-directory rename also uses `RENAME_EXCL` and does not use
an overwrite fallback. `_PC_CASE_SENSITIVE` on Preferences controls
whether the two spellings are visited separately or the second is logged
as an alias; if that query fails, neither preference path is renamed.
Missing directories, missing files, aliases and existing `.nuwa-bak`
entries are skips, not failures. A regenerated cache is left intact on
the next boot if its backup already exists.

The append-only `/private/var/db/nuwa-mg-reset.journal` records each full path,
presence (`yes`, `no`, or `unknown`), action, and numeric errno. The private
journal is opened and the run header written before any rename; a journal
write failure stops subsequent renames. The journal is synced before closing
after the path loop. The log and renames are not one atomic transaction;
`j!` or interrupted boot can leave a rename without a persisted record.
The console also receives the path results and a summary errno.

The MG build's DSP line reports live `DS=<state>` before CLI fields, followed
by `MG skip` or `MG r=<renamed>/<failed>` once the helper records a result.
`j!` flags setup/journal errors independently of path errors. The live state
can differ from the gate-time console sample if persistence later fails.
No MG marker means no completed sample, not proof the parameter was off.
Row 9 can be missed on immediate panic or scanout handoff. MG errors do not
change the watchdog return or block initproc exec.

The path reuses the recorded nuwa watchdog compile recipe and the XNU
8796.141.3 syscall contracts in `bsd/vfs/vfs_syscalls.c` and
`bsd/kern/kern_descrip.c` (`xnu@1b191cb5`, pinned in `unixnu.lock`).
The source baseline stays `UniXNU@693f5d9cae8a408dd18b39f3f9fdc4228c934241`;
upstream HEAD read `8542980d02b4d2cc5c32ee3542de1760b2562aac` before and
after the build. No base edits or device commands.

## Historical reset candidate — invalid for this experiment

| Artifact | Digest |
| --- | --- |
| Kernel SHA-256 | `ef9920d5e5f4db69c1368da2a73c788633d69029bc68e7b7e1a0139a056bba65` |
| Outer SHA-256 | `52d261a0f7cf19241102e4921b24b6c00d8769f0c310a958299adee901f27473` |
| Outer-extracted FAT SHA-256 | `cc4decc1574c3e543adae7de485cc6d26783bd79125c3145b672553242aa681e` |
| Outer-extracted ADT SHA-256 | `b593018e0c9b9ae494c8a5402c8fd925e9cbe3619e0bd3c93e3471c2ef1b3b7a` |
| Recomputed experimental CHMH SHA-384 | `685e2861a272895dc6f26f06eb51f1be26664158844149bbbcb60f319c13060a992afb81fa439890e40bf759cce19c6e` |

Local build `out/nuwa-mg-reset-build-r2-20261122/`, package
`out/nuwa-mg-reset-package-20261122/vendor_boot.img`, and separate audit
`out/nuwa-mg-reset-audit-20261122/`. Outer readback config differs from the
[4.75 GiB baseline](nuwa-window-475g-20261122.md) only by appending
`nuwa-mg-reset=1` after `nuwa-lite=1` (489-byte args). The outer ADT differs
from that baseline only by the recomputed CHMH bytes; the baseline has no
`display-scale` property, and this build does not introduce one.
`fsck.fat -vn` and `mdir` agree on **11,898,368 free bytes** (minimum
8,388,608). The packager also rejected the MG kernel under the unmodified ON
profile. Linked disassembly shows Data→watchdog→MG and MG→`renameatx_np`.
Syscall-model and prior watchdog/FDR/exception/IRQ tests ran successfully.

## Resume-only display ON candidate — self-checked

`--enable-display --board-window --enable-mg-reset-resume-only` retains the
4.75 GiB window (`0x130000000`) and `nuwa-lite=1`. Compared with the old MG
candidate, the outer-extracted args differ only by removal of
`sheng-data-reset=1`. The packager asserts the key is absent on outer
readback in both build and audit modes. Compared with the 4.75 GiB non-MG
baseline, the full config also adds `nuwa-mg-reset=1`, and the ADT differs
only in CHMH. Full readback (470 bytes):

```text
-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 aks=1 disable-watchdogd=1 build-tag=nuwa-r35 boot-progress-scale=3 sheng-data-persist=2 sheng-log-reserve=1024 offline-mobile-graphics-load=1 offline-legacy-register=1 offline-legacy-gop=1 offline-legacy-pm=1 offline-legacy-phase=4 offline-legacy-validate=1 offline-legacy-transfer=1 offline-legacy-cpu-present=1 nuwa-lite=1 nuwa-mg-reset=1
```

| Artifact | Digest |
| --- | --- |
| ON kernel SHA-256 (52,178,944 B) | `0637d5f37a78370085c03da762888dadb6ba6269dbbb0b2a517d3b47972a5d9b` |
| Outer SHA-256 (100,663,296 B) | `867996b932c8616a971eae7718bdd809e26fd5e23efdc13171966b1add225c95` |
| FAT SHA-256 (outer-extracted, 67,108,864 B) | `ea295d15dcb89fba73630f3cd8b0cb0fb7bc71b5d8a2d2a388cd34bad258c1cd` |
| ADT SHA-256 (outer-extracted) | `a06f8ee8838ec8e0be8d78ac093dce7f0e6c64d928239b62882ddea6d8f556bc` |
| Experimental CHMH SHA-384 (rebound and recomputed) | `bdc29edc388fc2703fb72c932d01f7d59188dcbb492da6778ea3b3db0885ceef0fdd19d8b68b72412b73fda22a064a0f` |

`fsck.fat -vn` (105,783 of 129,022 clusters used, 512 bytes per cluster)
and `mdir` agree on **11,898,368 bytes free**, above 8,388,608 bytes.
The MG syscall model confirms states 0, 1 and 3–8 do not open or write
files, and state 2 reaches the prior rename tests. Watchdog models, FDR
renderer checks, and the linked exception/register/IRQ checks passed.
Local artifacts are in `out/nuwa-mg-resume-only-{build,package,audit}-20261122/`.
The same pinned base and upstream HEAD noted above were checked before
and after this build. No device commands ran.

**deep_reviewer re-review required before any runtime use**: review the
resume-only premise and overlay state gate, plus the early APFS rename and
journal path on `userdata`-backed Data. Real APFS execution and independent
verification have not occurred. Authentication **NOT REACHED**.

### Independent verifier rerun

Use the [pinned compact build](nuwa-r35l-display-dsp-20261122-observation.md)
with `--mg-reset` and a fresh output directory `$B`, then:

```sh
S=scripts/build-ufs-apfs-root-chmh-r35-display.py
H=$(sha256sum "$B/kernel.macho" | cut -d' ' -f1)
set -- --kernel "$B/kernel.macho" --kernel-sha256 "$H" \
  --enable-display --board-window --enable-mg-reset-resume-only
"$PY" -B scripts/test-nuwa-mg-reset.py
"$PY" -B scripts/test-nuwa-watchdog-atomic.py
"$PY" -B scripts/test-nuwa-watchdog-policy.py
"$PY" -B scripts/test-r35-display-fdr.py out/nuwa-r35l-regs-full-20261121/BootProgress.c
for x in r35g-ux r35k-regs r35e-irqguard; do
  "$PY" -B "scripts/test-$x-linked.py" "$B/kernel.macho"
done
"$PY" -B "$S" "$@" --output "$P" </dev/null
"$PY" -B "$S" "$@" --audit "$P" --output "$A" </dev/null
fsck.fat -vn "$A/actual-vendor-ramdisk.img"
mdir -i "$A/actual-vendor-ramdisk.img" ::
sha256sum "$B/kernel.macho" "$P/vendor_boot.img" "$A/actual-vendor-ramdisk.img"
```

Compare the extracted config and ADT to the 4.75 GiB baseline readback:
the only args changes are removal of `sheng-data-reset=1` and addition of
`nuwa-mg-reset=1`. Confirm `sheng-data-reset` has no value or bare token in
the outer readback. Recompute SHA-384 over `record.json`'s decoded
`material_hex`.

## 复审记录

- 结论：PASS WITH CONDITIONS（deep_reviewer，方案 A）。
- 要点：outer `867996b9…5c95` 回读确认无 `sheng-data-reset`；`discardRequested()` 仅在 reset 为 1 或 2 时成立；`PersistOverlay.h:87–108` 匹配 overlay 原位续用，不匹配且未请求 reset 返回 `Kept`；`==2` 门禁足够（RW Resumed=2，Kept=7，Fresh=3）；MG 在打开目录/journal 前检查状态，非 2 直接返回。
- 放行表述：保持 userdata 原样、不选 Install/reset，可做一次缓存失效实验；须记录 DS、MG 标记、journal 逐项结果与 SpringBoard 是否仍断言。

该复审由主控转述，未经文档内自证。
