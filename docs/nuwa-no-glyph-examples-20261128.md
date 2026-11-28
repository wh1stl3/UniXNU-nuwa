# nuwa FUA diagnostic renderer without glyph examples — 2026-11-28

Status: **host self-checked; ordinary reviewer PASS WITH CONDITIONS; independent
verifier pending**. Subsequent flash and reboot:
[device observation](nuwa-no-glyph-flash-20261128-observation.md). Baseline worktree HEAD
`ba02fc006e47432a8186396fb25cbedecfaec959` plus this change; baseline UniXNU
`693f5d9cae8a408dd18b39f3f9fdc4228c934241`. Upstream HEAD checked before and
after the build: UniXNU `e7bddb9a7eecdcf81f36da9fa38bd9d4d3f155c2`,
UniXNU-nuwa `fe6b859367cc7b0641e9ae7dda46d8b5c6fc4fb0`.

The candidate removes the diagnostic page's glyph-example strings and their
exclusive `st_char` / `st_text` drawing helpers. The separately useful pixel
comb and rules remain at their original coordinates. Other diagnostic rows
and all storage, write-gate and authentication code are outside the change.
The page's PIX, SB, DATA, PROC, UFS TIME and other rows remain unchanged:
the generated `BootProgress.c` matches the pinned banner-r2 source byte for
byte except for the example-only regions. The non-text bars are retained, not
claimed to be invisible.

## UI trace investigation

The pinned r35l renderer has weak references to `boot_ui_trace_*`, but the
selected `package/boot-progress-r13/nuwa_boot_progress_stubs.c` makes the trace
state variables absolute zero and defines `boot_ui_trace_snapshot()` as a no-op
and `boot_ui_trace_role_rows()` to return zero. The banner-r2 linked kernel
confirms those definitions. No `boot-ui-trace`, `boot-ui-focus*`, or
`boot-ui-chrono` parsing implementation was found in the device patches or
actual 8796 build tree. The official guide describes another implementation,
not this one. Arguments alone cannot enable UI trace here.

The baseline args are 602 bytes of text. Appending the five merlinx comparison
tokens (`boot-ui-focus=lsd`, `boot-ui-focus2=SpringBoard`,
`boot-ui-focus3=backboardd`, `boot-ui-focus4=lsd`, `boot-ui-chrono=1`), including
their separating spaces, would make 709 bytes of text / 710 bytes including the
terminating NUL. The five tokens printed verbatim in the official debugging
guide (`launchd`, `SpringBoard`, `backboardd`, `Setup` and `boot-ui-chrono=1`)
would make 715 bytes of text / 716 bytes including NUL. The selected XNU arm64
`boot_args.CommandLine` buffer is 608 bytes including NUL, so both exceed the
607-byte text limit. No trace args are added; args are unchanged. This 710-byte
counting correction follows the final ordinary reviewer
`ses_de229b371ffeLyDZjum1Eg4tZw` (**PASS WITH CONDITIONS**); it does not change
the package. The experimental CHMH still must bind the new kernel.

The linked candidate confirms this directly: `llvm-nm -P kernel.macho` shows
`_boot_ui_trace_{index,label,phase,ready,rows}` at absolute zero; `llvm-objdump`
shows `_boot_ui_trace_role_rows` as `mov w0,#0; ret` and
`_boot_ui_trace_snapshot` as `ret`. The existing `nuwa-sb-stack=900` is a
separate lsd stackshot, not this UI trace. The generic guide
`UniXNU/docs/zh/guide/debugging.md:283-303` describes encoded rows and
8-second page rotation for an implemented trace; those display claims do not
apply to this kernel.

## Build and package

WSL root, working directory
`/mnt/d/Code/PortingiOS/nuwa/worktree-ufs-owner-api-20261126`:

```sh
p=/home/wh1stl3/.local/bin/python3.11
base=/mnt/d/Code/PortingiOS/UniXNU
b=out/nuwa-no-glyph-20261128-build
pkg=out/nuwa-no-glyph-20261128-package
template=/mnt/d/Code/PortingiOS/nuwa/worktree-ufs-neon-20261126/out/nuwa-ufs-neon-20261126-package/vendor_boot.img

$p -B scripts/build-nuwa-display-native.py \
  --base "$base" \
  --cpo /root/nuwa-pmap-ret-native-20261111/nuwa/ios-16.7.16-20H392/nuwa_pmap_ret/tree/build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/iokit/DEVELOPMENT/IOPMGR.cpo.json \
  --linker-dir /opt/unixnu-linux/CommandLineTools/usr/bin \
  --r35-dir out/nuwa-r35-20261119 \
  --r35l-dir out/nuwa-r35l-regs-full-20261121 \
  --cpu-only --no-software-vsync --candidate --mg-reset --hid-standin \
  --crashcap --pixsig --data-persist-diag \
  --data-candidate-gpt /mnt/d/Code/PortingiOS/nuwa/.cache/device-evidence/20261107-recovery/gpt-sda.bin \
  --disposable-data --post-event --disposable-fua-permissive --out "$b"

$p -B scripts/package-nuwa-crashcap.py --base "$base" \
  --kernel "$b/kernel.macho" --out "$pkg" \
  --disposable-data-template "$template" --post-event
```

Both commands exited 0. Logs: `out/nuwa-no-glyph-20261128-build.log` and
`out/nuwa-no-glyph-20261128-package.log`.

| Artifact | Bytes | Hash |
| --- | ---: | --- |
| `out/nuwa-no-glyph-20261128-package/vendor_boot.img` | 100,663,296 | SHA-256 `8d77f769bbc23ce7eb4c93957fe6bd2bb47ee22509dd5cc59c3d8beecb1fcca7` |
| `out/nuwa-no-glyph-20261128-build/kernel.macho` | 52,191,232 | SHA-256 `1faf93575a20568066f8f9c7f5f99c3022b20645591eb2e51a54536b5e6d685d` |
| `out/nuwa-no-glyph-20261128-package/readback-fat.img` | 67,108,864 | SHA-256 `7707385991a9f6f2d74fdd8b77627922826e0d7161b5b48b926134c221b9c12b` |
| CHMH (experimental) | 48 | SHA-384 `be2ebbfb29235aacaa9fdd46eada8cdd0ae8959a2179b4f79dc63cd4082afb8e4ad24b4b6162def390f7d967496a7c96` |
| `out/nuwa-no-glyph-20261128-package/kernel.macho.adt` | 13,680 | SHA-256 `7ac5a94d9936e2cde59918a575e16826b653f24e5ee9ba580c1da983fcf86936` |

The FAT has 11,037,696 bytes free. Compared to banner-r2 outer
`7211a98853226d4b1ca3345d1b5300bcfcf08b667a3b342b2cacc779082e4495`,
the header and tail match; the only changed FAT file contents are the kernel
and ADT. The `unixnu.toml` contents, all 602 args bytes, seed and trust cache
are byte-identical. The packaging audit's three-file difference is against the
separate `18fa4941…` read-root template, not banner-r2.

## Self-checks

The following commands exited 0, with output in
`out/nuwa-no-glyph-20261128-tests.log`:

```sh
$p -B scripts/test-nuwa-glyph-removal.py --renderer "$b/BootProgress.c" --kernel "$b/kernel.macho"
$p -B scripts/test-nuwa-postevent.py --renderer "$b/BootProgress.c" --kernel "$b/native-with-stabs.macho"
$p -B tests/test-nuwa-pixsig.py
$p -B tests/test-nuwa-crashcap.py "$b/kernel.macho"
$p -B scripts/test-banner-budget.py
$p -B scripts/test-sb-stack-row.py
$p -B scripts/test-sb-stack-paint.py
$p -B tests/test-nuwa-retained-entry.py "$b" "$base" --disposable --output "$b/selfcheck-retained"
$p -B scripts/package-nuwa-crashcap.py --base "$base" --kernel "$b/kernel.macho" \
  --out "$pkg" --disposable-data-template "$template" --post-event --audit-only
fsck.fat -vn "$pkg/readback-fat.img"
mdir -i "$pkg/readback-fat.img" ::/EFI/UniXNU/Payloads/
```

The glyph test pins the earlier generated source and checks every remaining
byte, the pixel probe coordinates, and absence of the example strings in the
new kernel. The post-event host fixture checks the named rows and executes the
critical-paint fixture; it is not a panel observation. A separate FAT parser
comparison against banner-r2 and
`$p -B "$base/scripts/porting-record.py" check --device "$PWD"` each exited 0.

No panel, runtime, durability or authentication result is claimed. This is
still the FUA-permissive disposable experiment: acceptance of FUA does not
establish media durability. CHMH is experimental, not authentication.
`device_release=false`; this host package record itself grants no device authorization.
