# Signed-text fixup (official mechanism) — 20H392 dyld cache entry

Status: host build and packaging **self-checked**; no device action. Reviewer and
`deep_reviewer` re-review are required (VM/pmap, signature semantics, concurrency).
Authentication remains **NOT REACHED**.

## Deep review summary

`deep_reviewer` returned **CHANGES REQUIRED**, and the finding is
**mechanism-level**: the two validation sources contradict each other — pages
validated one by one (`vm_page_validate_cs_mapped_slow`) versus the pager's
interval validation (`cs_validate_range` in `vm_fourk_pager.c`) leave the page
state inconsistent after a post-validation rewrite. The port itself was judged
**faithful** to upstream.

That verdict is **not changed by this revision**. This round only fixes one
parser boundary case (an unterminated trailing `/chosen/text-fixups` entry is now
rejected instead of parsed) and the documentation wording of the `TF=` counters
and the empty-table statement. The mechanism-level inconsistency, its risk
entries and the `deep_reviewer` requirement stand.

## What this is

`UniXNU/patches/xnu/native-text-fixup.patch` is an official UniXNU patch. After a
code-signed page passes signature validation, it matches the page by
`vnode name + file offset + original bytes` and rewrites the bytes through a
kernel write alias, then makes the instruction cache coherent. The table is the
`/chosen/text-fixups` property (NUL-separated entries), written by
`scripts/make-nuwa-adt.py --text-fixup`. This round ports it into the nuwa 8796
device series so the 20H392 dyld shared cache can be patched by one entry:

```
dyld_shared_cache_arm64.13,1cd5a9c,684a19d0004d47f9,c0035fd6004d47f9
```

`0x1cd5a9c` holds `68 4a 19 d0` (`adrp`) + `00 4d 47 f9` (`ldr`); the replacement
turns the first instruction into `c0 03 5f d6` (`ret`). Target is
`+[AWAttentionAwarenessConfiguration initialize]`, whose tail call goes to
`+[AWClientPreferences initializePreferences]`. A `ret` at entry returns without
running the tail call.

The offset field is **bare hex**, not `0x…`: `make-nuwa-adt.py`'s validator
(`[0-9a-fA-F]{1,16}`) and `cs_text_fixup_parse()` (hex digit per character) both
reject an `x`. The `0x` form in the task brief is notation, not the stored bytes.

## Port into xnu-8796.141.3

`patches/xnu/8796-native-text-fixup.patch` carries the upstream mechanism plus a
preamble and one parser-hardening deviation (see below). GNU `patch -p1 --fuzz=0`
and `git apply --check` both succeed. Context differences, all line offsets only:

| File | Upstream hunk | 8796 landing |
| --- | --- | --- |
| `bsd/kern/ubc_subr.c` | `@@ -6043,6 +6043,177 @@ cs_validate_hash` | 5830 (`-213`), before `cs_validate_range` at 5834; on the r35 4K-hash-cache TU (`out/nuwa-r35-20261119/tree/...`) 6010 (`-33`) |
| `osfmk/vm/vm_fault.c` | `@@ -100,6 +100,9 @@` include block | unchanged at 102 |
| `osfmk/vm/vm_fault.c` | `@@ -7797,6 +7800,14 @@ vm_page_validate_cs_mapped_slow` | 7562 (`-238`), after `page->vmp_cs_nx` (body 7515..7570) |
| `osfmk/vm/vm_protos.h` | `@@ -539,6 +539,7 @@` | 529 (`-10`), after `cs_validate_range` |

Deviation from upstream (parser only, review-requested): `cs_text_fixup_init()`
now tests `s + length == end` before copying an entry and ignores an
unterminated tail entry (`printf "text-fixups[%d]: unterminated, ignored"`).
Before, a property ending without a NUL was parsed as if the strnlen length were
a terminator. No entry that parsed before is dropped. The property bytes are
unchanged, so this is not a mechanism change. Host test:
`scripts/test-nuwa-text-fixup-parser.py` extracts this exact hunk, compiles it
against stubs, and places the table against a `PROT_NONE` page so any read past
the property end faults; it asserts the tail is rejected, earlier entries keep
their counts, the pre-table canary is untouched, and a valid entry still rewrites
its two bytes.

8796 specifics confirmed by compiling both TUs with the recorded 8796 flags:

- `validated` / `tainted` are `int` bit masks written by `cs_validate_page`; the
  `VMP_CS_ALL_TRUE` / `VMP_CS_ALL_FALSE` comparison keeps upstream meaning.
- `TUNABLE_STR`, `STARTUP` and `os_atomic_inc` resolve through `ubc_subr.c`'s
  existing includes; no extra include was added.
- `phystokv` and the `cache_sync_page` from the added `<arm/caches_internal.h>`
  are reachable in `vm_fault.c`.
- Empty table: this hook changes no page bytes and does not call
  `cache_sync_page()`. It does **not** make the image bit-identical to an
  unpatched build: the patched TU/objects, early-boot parsing, exported
  `cs_text_fixup_*` symbols and the banner's `TF=0/0` all differ.

The patch is in `patches/xnu/series` before the two display hooks. It is not one
of the three opt-in launchd bypasses; it is compiled unconditionally and its
effect is controlled entirely by the ADT table.

## Banner readout

The diag renderer appends the fixup counters to the `SVC` row when the symbols are
linked in (weak-import gate, so a kernel without the patch keeps the old row):

```
SVC <svc> K=<lo>x<hi> H=<hid> TF=<parsed>/<applied>
```

`parsed` = `cs_text_fixup_parsed`, `applied` = `cs_text_fixup_applied` (both
`uint32_t` exported by the patched `ubc_subr.c`).

- `TF=<parsed>/<applied>`; `1/0` means one entry parsed but no validated page
  matched its name/offset/bytes; `0/0` means no valid entry was parsed.
- `applied` counts page writes, so it can exceed 1 if a page is re-instantiated
  and matched again; it is not a distinct-page count.
- A field that is absent (not `0/0`) means the kernel was built without the
  fixup symbols, i.e. the old banner row.

Measured widths on the host from the exact format (`test-banner-short-values.py`):
worst case `SVC ffffffff K=255x16777215 H=7 TF=4294967295/4294967295` is
**56 columns**; the ordinary case `SVC 00 K=0x0 H=0 TF=0/0` is 23; the row array
is 120 wide. Both are ≤ 80.

## Build

Two TUs are rebuilt from the same source bases the r35l kernel used and swapped
into the recorded native link; everything else is the unchanged r35l replay:

- `bsd/kern/ubc_subr.c` from `out/nuwa-r35-20261119/tree` (contains the 4K
  hash-cache change), SHA-256 `6d9dbdcd…9be0`.
- `osfmk/vm/vm_fault.c` and `osfmk/vm/vm_protos.h` from the xnu tree recorded in
  the compile database, SHA-256 `99081417…b934` / `3ef4c0ca…79ee`.
- Patch SHA-256 `492355cf…344a`; rebuilt objects `ubc_subr.o`
  `d8dea798…ab19`, `vm_fault.o` `35dc0c27…ff34` (`text-fixup.json` beside the
  kernel).

The final kernel also carries the HID stand-in (`_nuwa_hid_stage`) and the MG
reset diagnostic (`_nuwa_mg_reset_diag`), and defines `_cs_text_fixup_page` at
`fffffff007753e4c`, `_cs_text_fixup_parsed` at `fffffff007ab9e88` and
`_cs_text_fixup_applied` at `fffffff007ab9e8c`; `libBootProgress.a` keeps them as
undefined imports resolved by the link, and the `TF=%u/%u` and
`unterminated, ignored` strings are present once in the image.

Recipe (WSL root, worktree `out/`; the resume-only chain, not the old
`--enable-display` shortcut):

```sh
PY=/home/wh1stl3/.local/bin/python3.11
BASE=/mnt/d/Code/PortingiOS/UniXNU
CPO=/root/nuwa-pmap-ret-native-20261111/nuwa/ios-16.7.16-20H392/nuwa_pmap_ret/tree/build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/iokit/DEVELOPMENT/IOPMGR.cpo.json
"$PY" -B scripts/build-nuwa-display-native.py --base "$BASE" --cpo "$CPO" \
  --linker-dir /opt/unixnu-linux/CommandLineTools/usr/bin \
  --r35-dir out/nuwa-r35-20261119 --r35l-dir out/nuwa-r35l-regs-full-20261121 \
  --cpu-only --no-software-vsync --candidate --hid-standin --mg-reset --text-fixup \
  --out out/nuwa-textfixup-20261123-r3
"$PY" -B scripts/build-ufs-apfs-root-chmh-r35-display.py \
  --kernel out/nuwa-textfixup-20261123-r3/kernel.macho \
  --kernel-sha256 e161a629690a503d63a1f4a346b3e1f488df6f09ecfb375e51d7e5a62e7e0c5e \
  --systemgroup-seed out/nuwa-textfixup-20261123-r3-seed/data-8g-sg.dbr \
  --enable-display --board-window --enable-mg-reset-resume-only --enable-hid-standin \
  --text-fixup --output out/nuwa-textfixup-20261123-final3-package
```

The packager (`scripts/build-ufs-apfs-root-chmh-r35-display.py`) is the
resume-only entry: it pins the exact HID-stage argument string, the SystemGroup
seed (SHA-256, identity, 2,121,888 encoded bytes, APFS UUID), the 4.75 GiB window
and the reference TOML byte-for-byte, adds `/chosen/display-scale` u32 3 and, in
`--text-fixup` mode, `/chosen/text-fixups`. The parallel guard rewrite is kept;
the only change made here is to update `PINS['seed']` only when the key already
exists (the unconditional insert failed the parent-input check with
`KeyError: 'seed'`).

## Artifacts (final candidate, host self-checked)

| Artifact | Bytes | SHA-256 |
| --- | --- | --- |
| Kernel | 52,191,232 | `e161a629690a503d63a1f4a346b3e1f488df6f09ecfb375e51d7e5a62e7e0c5e` |
| Outer `vendor_boot.img` | 100,663,296 | `008292803585920f7753ef8f895987a41fa031b37d14093666d192d90cd547d3` |
| FAT `payload.img` (outer-readback identical) | 67,108,864 | `bf145419a849c28aec6568fc2bae5f216136001c98352c29e722fcd86e7ee0f5` |
| Derived ADT | 13,788 | `c5a0a229ff1aef266449aadd3e31dd93e4a61ec69a7a0dbba5b061f7a74795c8` |
| CHMH (SHA-384) | — | `acac3c657720e8a392ecd247029cda83a2a0e9298333dd84797a37fd60ec2546a356357540a7dc5b2bace8bea7807a5c` |
| `record.json` | — | `78c3ddc810ea2b4c0ac0790c43f2e8e41d6a7f1aaca346cfd22ba9d39cfd90c4` |

`fsck.fat -vn` reports 106,247 / 129,022 clusters used and **11,660,800 bytes
free** (≥ 8 MiB). The packaged `unixnu.toml` SHA-256 is
`91bb0d9e1256f3dd3fd5a6dd4b1c0c276342ef92bf4b684c6609fadfa5f87e62`, i.e. the
same bytes as `vendor-boot-hid-stage/unixnu.toml`; the args string is therefore
identical character for character.

Self-check extracted directly from the shipped `vendor_boot.img` (FAT sliced at
4096, asserted byte-identical to `payload.img`, files read with `mcopy`):

- args (535 bytes): `-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2
  rd=uuid boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 aks=1
  disable-watchdogd=1 build-tag=nuwa-r35 boot-progress-scale=3
  sheng-data-persist=2 sheng-log-reserve=1024 offline-mobile-graphics-load=1
  offline-legacy-register=1 offline-legacy-gop=1 offline-legacy-pm=1
  offline-legacy-phase=4 offline-legacy-validate=1 offline-legacy-transfer=1
  offline-legacy-cpu-present=1 nuwa-lite=1 nuwa-mg-reset=1 nuwa-sb-restart=400
  nuwa-sb-restart-every=180 nuwa-hid-standin=1` — no `sheng-data-reset`.
- `/chosen/text-fixups` = `b"dyld_shared_cache_arm64.13,1cd5a9c,684a19d0004d47f9,c0035fd6004d47f9\0"`.
- `/chosen/display-scale` = `03 00 00 00`.
- embedded seed SHA-256 = `692355638b31d347ced5983a5910491f0556156f79675c2e371ebe9987683247`.

Compared with `vendor-boot-hid-stage`, the args are exactly equal and the ADT
differs only by the new `boot-manifest-hash` and the added `text-fixups` property;
every other `/chosen` value is unchanged.

The earlier r2 package (kernel `8ca2e912…dafb`, no HID/MG) and r1 package
(kernel `f0a52c9a…b1798`) are superseded and must not be used.

## Risks (not softened)

- **Range validation can bypass the page state.** `vm_fourk_pager.c` calls the
  range validator (`cs_validate_range()`) on the changed interval. A range hit
  can validate the modified bytes without restoring a whole-page "validated"
  state, and no bookkeeping can undo that. This port only hooks the paged slow
  path; the range path is unchanged.
- **Recycled pages.** After a page is reclaimed and re-faulted, the fixup may be
  written again (slow path) or the original bytes may survive (bitmap hit). The
  counters can therefore exceed 1, and behaviour is not idempotent-by-design.
- **Shared pages.** The write happens on the first validator's path through a
  physical alias. Visibility to other mappings of the same page is not proven.
- **Instruction cache.** On a single core `cache_sync_page()` is expected to be
  sufficient; cross-core behaviour is unverified (`SMP` is still off here).
- **Match strength.** Identity is `vnode name component + file offset + original
  bytes`, not a full path or a cdhash. A different file with the same name
  component and identical bytes at that offset would also match.

## Bypass ledger

| Field | Value |
| --- | --- |
| Symptom | The donor dyld shared cache calls `+[AWAttentionAwarenessConfiguration initialize]`, whose tail call reaches a signed subcache path that stalls before display; no signed artifact exists for 20H392. |
| Bypass | Official signed-text fixup: one ADT entry rewrites the first `adrp` to `ret` after signature validation. |
| Cost | Code inside a signed file is disabled after validation; the kernel reports it only through `TF=` and the `text-fixup:` console line. Authentication semantics are not preserved for that instruction. |
| Exit condition | A real signed artifact or a source-level fix that removes the need for the fixup. |
| Stop-loss | On any observed taint rejection, a process killed by the system, or a new random crash, remove the ADT entry (rebuild the ADT without `--text-fixup`) and revert this series patch. |

## Review required

`deep_reviewer`: VM/pmap write-alias and cache coherence, signature-validation
semantics (post-validation mutation, range path), and concurrency/counters. The
existing CHANGES REQUIRED verdict is mechanism-level and is **not** closed by the
parser fix.
Ordinary reviewer: banner gate, off behaviour, ADT equality, series order, and
the new unterminated-entry rejection with `test-nuwa-text-fixup-parser.py`.
Independent verifier has not rerun the build or packaging; runtime behaviour,
the actual `TF=` reading, and whether the fixup changes the display outcome are
unverified.
