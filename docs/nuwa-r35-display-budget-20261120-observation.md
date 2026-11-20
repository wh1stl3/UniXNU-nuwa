# r35 OFF / display ON products — host only, self-checked

Both images passed the unchanged 64 MiB FAT / 8 MiB free-space checks,
and separate host outer/FAT readback. OFF and ON are **different artifacts**,
not supported as two runtime modes of the display kernel. Use only
`out/nuwa-r35-display-split-{off,on}` for this round. Earlier same-kernel
experiments in `out/nuwa-r35-display-compact-package-*` are superseded.

## Budget: where the original 111,104 B shortfall came from

Bytes below are for r35 versus the first display candidate. Object sizes
include headers, relocations and DWARF. Map bytes are totals of linker
symbol extents (may include zero-fill); these are not additive with the
final aligned-segment budget. Display rows have no r35 counterpart.

| Input | r35 object/archive | First display | Delta | r35 → display map |
| --- | ---: | ---: | ---: | ---: |
| `bsd_init.o` | 174,472 | 176,328 | +1,856 | 14,405 → 14,736 |
| `libBootProgress.a` | 322,312 | 322,312 | 0 | 2,204,248 → 2,204,248 |
| display late archive total | 0 | 749,360 | +749,360 | subtotal, see below |
| ↳ `NativeLegacyDisplay.manual.o` | 0 | 326,745 | +326,745 | 0 → 17,737 |
| ↳ `NuwaLegacyDisplay.o` | 0 | 219,144 | +219,144 | 0 → 3,081 |
| ↳ `original-bindings.o` (original-class executable veneers) | 0 | 23,784 | +23,784 | 0 → 704 |
| ↳ `original-addresses.o` (absolute targets and metaclass) | 0 | 11,736 | +11,736 | 0 → 0 |
| ↳ `NuwaDisplayRefresh.o` | 0 | 146,656 | +146,656 | 0 → 658 |
| ↳ archive index/headers/padding | 0 | 21,295 | +21,295 | not mapped |
| raw `NativeLegacyDisplay.o` (before removing automatic ctor pointer) | 0 | 326,872 | +326,872 host only | not linked |

The candidate uses `HOST-ONLY-incomplete-display.a` from the strict archive
builder; the device callback publishes the same recipe under
`libNativeLegacyDisplay.late.a`. They are not two link inputs. The renderer
archive and all other r35 inputs are reused except `bsd_init.o`.

| Final persisted region | r35 | First display | Delta |
| --- | ---: | ---: | ---: |
| `__DATA_CONST` | 884,736 | 901,120 | +16,384 |
| `__TEXT_EXEC` | 7,962,624 | 7,979,008 | +16,384 |
| `__LINKEDIT` | 6,488,736 | 6,528,136 | +39,400 |
| `__PRELINK_INFO` | 389,120 | 462,848 | +73,728 |
| Gaps between file-backed segments | 3,424 | 888 | −2,536 |
| **Kernel total** | **55,721,984** | **55,865,344** | **+143,360** |

All other segment file lengths are unchanged. The metadata XML delta is
76,281 B before alignment: IOAVFamily +3,494, IOMobileGraphicsFamily +2,634,
Libm +2,053 (shared bundle entries total delta 0), and `_PrelinkLinkKASLROffsets`
+68,100 Base64 bytes for 12,769 more 32-bit fixup sites: IOAVFamily 10,421
(41,684 raw bytes), IOMobileGraphicsFamily 2,344 (9,376), and Libm 4 (16).
Those are required fixups, not redundant data. r35 had 32,256 B above the FAT floor;
143,360 − 32,256 = 111,104 B short, as measured on its failed successor FAT.

## ON reductions, in order

1. Compile the three new C++ members with `-g0` (`llvm-objdump -h` shows
   no remaining debug sections). The manual class object drops to 50,508 B,
   board provider to 7,824 B, refresh to 2,016 B; both generated assembly
   members keep their sizes. Archive: 749,360 → 117,160 B. The fully linked,
   emitted and rendered kernel measures 55,857,152 B (−8,192); at 512 B per
   FAT cluster that would still be 102,912 B below the floor on the same
   budget. No constructor or functional section was dropped.
   The assembled-layout device archive callback also emitted 117,160 B
   and passed the base linker's archive/report hash checks.
2. The actual archive/link map contains each of the five members once.
   The raw class object is not a member and has no final cost. Do not
   drop `original-addresses.o` based on its zero map bytes: removing it
   in an isolated negative relink failed with undefined
   `IOMobileFramebufferLegacy::gMetaClass` from the manual class object.
   No duplicate or unused linked member was removed; reclaimed 0 B.
3. The native link's `-S` removes only linked STABS and their strings from
   the ON output. The same inputs also produce `native-with-stabs.macho`
   for host symbolication. The builder compares Mach-O command layout,
   non-debug LINKEDIT prefix, all mapped bytes outside LINKEDIT and
   50,037 non-STAB symbol tuples (including local/global names, types,
   section ordinals and values). It removes 128,827 STABS, saving
   3,713,008 B native and 3,710,976 B in the final rounded image.
   No constant or executable coalescing was necessary.

Compared to the first display candidate, both slim stages preserve native
mapped bytes, all non-STAB symbols, the entire 160-slot linked audit,
65,443 prelink binding records, donor entrypoints, donor executable hashes
and scoped Libm bytes. Sparse index VA/length/ABI and 31 ordered headers
are identical; its file offset moves with LINKEDIT. The automatic ctor
table bytes and both BSD hook call sites are in unchanged mapped regions.
Emitted and final linked metaclass/slot audits still run. Slot 329
remains an expected `unqualified backend slot 329` diagnostic panic
when reached by the donor. TimingEnable is not implemented.
The full r35 linked/object and seed/ADT checks also returned `ALL PASS`
using the final ON kernel and actual packaged input
(`out/nuwa-r35-display-budget-compact/r35-audit/check-linked.log`).

## Product evidence

OFF equals r35 because it has **identical boot inputs**: `cmp` passed on
kernel, ADT, config, FAT and entire `vendor_boot.img`. Its CHMH matches r35.
The -off profile independently requires the fixed r35 kernel digest; a
display kernel paired with its own correct digest exits 2 before output
creation. ON accepts explicitly pinned display builds and rebinds CHMH.
ON appends only `offline-mobile-graphics-load=1 offline-legacy-register=1 offline-legacy-gop=1`
to the exact [r35 boot args](nuwa-r35-display-20261120-observation.md#build-and-activation).
Seed, loader, trust and outer layout are unchanged.

| | OFF | ON |
| --- | --- | --- |
| Kernel SHA-256 | `787610183dc7f772e2d01aa183f72f2fcc52245fc44407e6c815ced614412464` | `89355aa4e0dc0f3d2e9ef1971e94d45f6584f66d4ae318e6ac2bdc832fce4b39` |
| CHMH SHA-384 | `e767b49dd510f8effb79a269620a18ef509a4ffd7bcbbb0c8fb566308fbd8458552b15378927cdafcabe2659874f4b94` | `82ea00c07f5b5a0232473b0f634da254397ad73c0ea92a4fc597efdd4dead97ccd8cf33f25c7d617d9ece5cfc6bcb9cd` |
| `vendor_boot.img` SHA-256 (100,663,296 B) | `c6e64820cc46c1a54e65d3640994ad7acf0e7aa807dfd3765eac82f483a4a7ed` | `09d11016b7710a29f8aba936fe397aae79bf7ec01cef5ef27b760ec37b967efa` |
| FAT / `actual-vendor-ramdisk.img` readback SHA-256 | `90a5447c8c67a18c9f14fdb6a67c1620252f5ab472555b018478c9149518121e` | `3d8ed2bd8009d704c570adda524aa3b378165c243feb61d044fda66a4a620664` |
| `outer-record.json` SHA-256 | `0c2b0d4a52b3cc9200d03161b0a5f5bca48207489c8f766084f58f697c76b3e3` | `c5c9241d9a1a2e10a00906732c7f974f94433aafd402c081015100756d9ae594` |
| Outer readback `audit.json` SHA-256 | `ef1ffc5ef46f97b9086294af9fa6566a2feeac17d84d0678f95551724349e6a5` | `40549bc2b80e752079124960f7e64e55e0d62a331942c68c2d43a02edf86ce5a` |
| FAT free (above floor) | 8,420,864 B (+32,256) | 11,996,672 B (+3,608,064) |

## Reproduce independently

WSL root, device checkout. Choose fresh output directories when rerunning.
Base remains pinned at `693f5d9cae8a408dd18b39f3f9fdc4228c934241`;
read-only upstream HEAD check returned `8542980d02b4d2cc5c32ee3542de1760b2562aac`.
Use the base, CPO and linker from the
[first integration command](nuwa-r35-display-20261120-observation.md#host-checks-and-limits);
use `--out out/nuwa-r35-display-budget-archive --keep-link-debug` for
stage 1 and `--out out/nuwa-r35-display-budget-compact` for the final build.
Then:

```bash
PY=/home/wh1stl3/.local/bin/python3.11
S=scripts/build-ufs-apfs-root-chmh-r35-display.py
K0=out/nuwa-r35-20261119/kernel.macho
H0=787610183dc7f772e2d01aa183f72f2fcc52245fc44407e6c815ced614412464
K1=out/nuwa-r35-display-budget-compact/kernel.macho
H1=89355aa4e0dc0f3d2e9ef1971e94d45f6584f66d4ae318e6ac2bdc832fce4b39
"$PY" -B scripts/test-nuwa-display-packaging.py --kernel "$K1" --kernel-sha256 "$H1"
for mode in off on; do
  P=out/nuwa-r35-display-split-$mode
  if [ "$mode" = off ]; then
    args=(--kernel "$K0" --kernel-sha256 "$H0")
  else
    args=(--kernel "$K1" --kernel-sha256 "$H1" --enable-display)
  fi
  "$PY" -B "$S" "${args[@]}" --output "$P"
  "$PY" -B "$S" "${args[@]}" --output "$P-audit" --audit "$P"
done
```

No device I/O, no change to the FAT check, and no merge. Authentication
NOT REACHED; review the ON debug-free link and its layout before any
device use. Independent verifier and runtime validation pending.
