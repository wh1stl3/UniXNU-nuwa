# 20H392 MobileGestalt cache invalidation — host candidate

SpringBoard still asserts after the earlier `display-scale=3` experiment.
The seed contains none of these caches. An old device-generated cache with
scale 0 is the working hypothesis, based on the reported venus result,
not a confirmed nuwa diagnosis. This opt-in **invalidates caches so MG
rebuilds them**, rather than repairing the scale source. Rebuilding may
slow the first boot. Remove this bypass once MG is observed deriving the
correct scale from ADT. Turning the argument off does not undo a prior rename.

## Early write path

`load_init_program()` calls `nuwa_data_mount_prepare()` before initproc exec.
After the APFS Data device/type/read-only checks succeed, Data calls
`nuwa_boot_watchdog_policy()`. At that existing call site the optional
MG helper runs independently of the watchdog policy, only with
`nuwa-mg-reset=1` and a writable Data mount.

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

The normal DSP line ends in `MG r=<renamed>/<failed>` after an attempted run;
`j!` flags setup/journal errors independently of path errors. No suffix
means no completed sample, not proof the parameter was off. Like the rest
of row 9, the suffix can be missed on immediate panic or scanout handoff.
MG errors do not change the watchdog return or block initproc exec.

The path reuses the recorded nuwa watchdog compile recipe and the XNU
8796.141.3 syscall contracts in `bsd/vfs/vfs_syscalls.c` and
`bsd/kern/kern_descrip.c` (`xnu@1b191cb5`, pinned in `unixnu.lock`).
The source baseline stays `UniXNU@693f5d9cae8a408dd18b39f3f9fdc4228c934241`;
upstream HEAD read `8542980d02b4d2cc5c32ee3542de1760b2562aac` before and
after the build. No base edits or device commands.

## Host candidate — self-checked

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

**Reviewer + deep_reviewer required before any runtime use**: the hook writes
Data backed by `userdata` before userspace. Review the calling context,
APFS case/query and exclusive rename behavior, journal authorization and
persistence. Neither real APFS execution nor an independent verifier rerun
has occurred. Authentication **NOT REACHED**.

### Independent verifier rerun

Use the [pinned compact build](nuwa-r35l-display-dsp-20261122-observation.md)
with `--mg-reset` and a fresh output directory `$B`, then:

```sh
S=scripts/build-ufs-apfs-root-chmh-r35-display.py
H=ef9920d5e5f4db69c1368da2a73c788633d69029bc68e7b7e1a0139a056bba65
set -- --kernel "$B/kernel.macho" --kernel-sha256 "$H" \
  --enable-display --board-window --enable-mg-reset
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

Compare the extracted config and ADT to the 4.75 GiB baseline readback,
and recompute SHA-384 over `record.json`'s decoded `material_hex`.
