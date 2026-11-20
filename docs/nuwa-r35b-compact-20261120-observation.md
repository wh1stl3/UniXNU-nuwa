# Compact r35b — host only

The old r35b package is below the unchanged 8 MiB FAT free-space floor
and must not be used. Its earlier review covered a different binary.

The compact build uses the same renderer source and exit guard as r35b.
It applies `-g0` only to `BootProgress.c` and `-Wl,-S` at the native link.
It retains every existing build assertion, including the source guard,
required diagnostic symbols and linked checks. The original build tag
remains `nuwa-r35`; it cannot identify the package on-screen.

The first compact link was rejected by the display audit at
`build-nuwa-display-native.py:106`: the two runtime `__FILE__` strings in
`machine.c` and `vm_unix.c` came from the new output directory, shortening
`__TEXT,__cstring` by 14 bytes and moving later sections. A macro-path map
restored the literal values but still changed their order. The recipe now
compiles those two units through the original path only after checking that
the old source is byte-identical to the newly generated source. No audit
check was waived.

The equivalence check reuses `audit_debug_strip` from this board's display
branch (`cfe6ab3`, BSD-2-Clause-Patent). It compares Mach-O header and
commands (allowing only audited symbol metadata, UUID and LINKEDIT extent
changes), mapped bytes outside LINKEDIT, the non-symbol LINKEDIT prefix,
and the multiset of non-STAB `(name, type, section, desc, value)` tuples.
The strict check repeats the tuple comparison on the final emitted kernels.
The prelink manifests' complete ordered binding arrays are compared as
JSON, along with donor executable hashes, component sets, entrypoints,
kernel interfaces, pointer counts, slide and early security initializers.
The FAT calculation is reused from the corrected packager (`ed9746a`);
the strict check compares its data-cluster scan with FSInfo and `fsck.fat -vn`.

The final native audit passed: 128,827 STABS removed, all 49,608
non-STAB tuples preserved; native file shrank by 3,713,312 B and final
kernel by 3,715,072 B. All 52,674 prelink binding records matched in order.
Host replay preserved the two signal records through 200 ordinary exits
and exercised a second 200-exit wave, reason records, capacity and row
width. No device or concurrency behavior was tested.

The base checkout remained at `693f5d9cae8a408dd18b39f3f9fdc4228c934241`.
The device repository upstream HEAD was `4548bbd2be0d7bccc0c789ca62934842026c6384`
before and after the kernel build. The base remote HEAD query failed with a
TLS termination error and was not retried.

## Final package — self-checked

Build, separate `--audit`, linked/object audit (`ALL PASS`) and strict
package checks all exited 0. The final kernel retained all 49,608 non-STAB
tuples. The outer readback FAT matched the packaged FAT; corrected FAT
scan, FSInfo and `fsck.fat -vn` agreed for both the old and new packages.
There are 129,022 data clusters of 512 B each. The old image uses 112,703;
the new one uses 105,447.

| Item | Old r35b | Compact r35b |
| --- | --- | --- |
| Kernel SHA-256 | `ad7e70f7e615494c6162cec1a72610e119e897414bb89e4e038075244442da2f` | `6262a25ab2211c8010a105d9456cdf46d38832c5edf3667f2b09a8262639deb8` |
| Kernel bytes | 55,721,984 | 52,006,912 |
| Vendor boot SHA-256 | `3c5c2df89ff67341af3fdc4a40eef82467a7360389685f4303f241315ecc9388` | `56e78d27d48e6368cd3f96fa2993bfcba44bea8684d9a6dbc87355dcfd198dbd` |
| FAT SHA-256 | `de26794988414ec4280fbe6937f86de5b6fd8868a0a69cc3d25c1f5fffb30afd` | `95fedd1001f9ee3a275f2decbb47cdc60d9c7301a335b5cc1ef99f6f0e1719c6` |
| ADT SHA-256 | `22a9e9f4bc13ccb4b3a020c1bc840e75b09c2e078bc15ce2e5323dd115e0cf3c` | `c8c769acdd0877616a697d582b72cb92aed5303c4c3f1e6096c7be53670c093d` |
| CHMH SHA-384 | `9ea4853ca37f2e59310720d6803a30d39c2a74da60d12c30896d168ed80fafbe246969138120f6b1b512a3d6fc3be0be` | `ca463c3f4ba9168203323e4350255d2b0c5f53e4033211dcf2f3124291c63ea7104b5d6fac7da9a3b859dafaefe58528` |
| FAT free vs 8 MiB floor | 8,355,328 B (−33,280 B, FAIL) | 12,070,400 B (+3,681,792 B, PASS) |

CHMH was derived from the new pinned kernel and unchanged boot arguments;
old CHMH was not reused. Authentication remains NOT REACHED. This is a
candidate for final diff review, not a device release. The prior review of
the unstripped r35b does not cover this image. Final boot-chain review
(`deep_reviewer`), an independent verifier rerun and current-round device
authorization remain outstanding.

## Reproduction

WSL Ubuntu-22.04 root, working directory the diagnostic worktree:

```sh
PY=/home/wh1stl3/.local/bin/python3.11
O=/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out
K=$O/nuwa-r35b-compact-r3-20261120
P=$O/nuwa-ufs-apfs-root-chmh-20261120-r35b-compact
A=$O/nuwa-r35b-compact-package-audit-20261120
"$PY" -B scripts/test-r35-exit-selection.py "$O/nuwa-r35-20261119/BootProgress.c"
"$PY" -B scripts/build-r35b-kernel.py "$O/nuwa-r35-20261119" "$K" --compact
"$PY" -B scripts/build-ufs-apfs-root-chmh-r35b.py --output "$P"
"$PY" -B scripts/build-ufs-apfs-root-chmh-r35b.py --output "$A" --audit "$P"
"$PY" -B scripts/test-r35b-compact-package.py "$P" "$A"
```

For an independent rerun use new package/audit paths. Build into a fresh
sibling rather than overwriting the pinned kernel directory; compare its
kernel hash to the selected build before independently auditing packaging.
