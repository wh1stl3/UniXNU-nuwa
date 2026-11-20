# r35 display integration — host only, self-checked

Full diagnostic kernel linked and emitted; **no vendor_boot candidate**. No
device I/O, base changes, runtime verification or merge. `6bfd722` had Plan B
PASS WITH CONDITIONS (parent report); that review did not cover this integration.

## Build and activation

- Device `board.toml` already selected `GopFramebuffer`. Its archive callback
  now produces `libNativeLegacyDisplay.late.a` and the pinned base's source-hash
  report; `nuwa_defconfig` enables `CONFIG_XNU_NATIVE_LEGACY_DISPLAY`.
- Two device-series patches port only the Legacy hooks from
  `UniXNU/UniXNU@693f5d9cae8a408dd18b39f3f9fdc4228c934241`,
  `offline-component-load-probes.patch` and `offline-legacy-start.patch`.
  Both apply with zero fuzz to the staged 8796 source and the r35 source copy
  (offsets only on r35). Early: after `vfsinit`, load IOMobileGraphicsFamily,
  then probe only if the load succeeds. Late: after successful `IOKitBSDInit`
  has published `IOBSD`, probe the prepared provider. Neither hook runs the
  display path without all three values below.
- Binding method reused via the existing nuwa 20H392 derivation and archive
  audit: `UniXNU/UniXNU-sheng@c8f92b208068eeaa4cd2b0f592671f04ee70076e`,
  `build-gop-legacy-display-27.py` / `check-legacy27-binds.py`,
  BSD-2-Clause-Patent. Uses nuwa's arm64 donor with fixed-collection veneers,
  manual constructor and linked metaclass GOT verification; no sheng board
  data, GPU path or software vsync sender. GopFramebuffer source pin:
  `e47c1b8de169cd2bd0b885c7d85e433010e3cdf2`.
- **Off (default):** exact r35 args; omit `offline-mobile-graphics-load`,
  `offline-legacy-register`, and `offline-legacy-gop` entirely.
  **On:** append `offline-mobile-graphics-load=1 offline-legacy-register=1 offline-legacy-gop=1`.
  A partial set does not activate the hooks. No `offline-mobile-graphics-client`
  flag is required. The common r35 args are:

  ```text
  -v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 aks=1 disable-watchdogd=1 build-tag=nuwa-r35 boot-progress-scale=3 sheng-data-persist=2 sheng-data-reset=1 sheng-log-reserve=1024
  ```

- Slot **329** remains unchanged. If the display is enabled and donor code
  reaches it, `NuwaLegacyDisplay: unqualified backend slot 329` is an expected
  diagnostic panic, not a regression or TimingEnable implementation.

## Host checks and limits

Run from this checkout in WSL as the owner of the `/root` r35 compile tree:

```bash
PY=/home/wh1stl3/.local/bin/python3.11
BASE=/mnt/d/Code/PortingiOS/UniXNU
CPO=/root/nuwa-pmap-ret-native-20261111/nuwa/ios-16.7.16-20H392/nuwa_pmap_ret/tree/build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/iokit/DEVELOPMENT/IOPMGR.cpo.json
A=out/nuwa-r35-display-20261120-r2
"$PY" -B scripts/build-nuwa-display-native.py --base "$BASE" --cpo "$CPO" \
  --linker-dir /opt/unixnu-linux/CommandLineTools/usr/bin \
  --r35-dir out/nuwa-r35-20261119 --cpu-only --no-software-vsync --candidate --out "$A"
"$PY" -B scripts/gate-libm-data-region.py --base "$BASE"
"$PY" -B scripts/test-scoped-libm-emitter.py --base "$BASE"
```

Use a new `--out` directory for reruns. The first build invocation, under the
default WSL user, stopped at `verify-nuwa-display-host-abi.py:518` (read access
to the pinned CPO); the command above used the normal r35 build user.
Archive callback exercised separately in an isolated assembled-layout fixture;
its emitted archive and source-hash report validated against the pinned base
linker's report checks. This was not a clean build from the stock stage-5
`unixnu prelink` command; that command does not use the scoped device emitter.

The r35 control relink matches native and map except output UUID/path. Candidate
rebuild replaces only the recorded `bsd_init.o` and force-loads the audited
display archive; it retains byte-identical r35 `libBootProgress.a`. Linked,
emitted and final ABI checks cover the metaclass/GOT and 160 inherited-slot
bindings. Strict emission preserves the 1224-byte Libm region; all seven
negative controls rejected. The final image has the same 95 automatic
constructor names in the same order as r35; the display constructor is
manual. Linked disassembly confirms `vfsinit` → arg gate → family load →
early probe, `IOKitBSDInit` → arg gate → late probe, and slot 329 → guard →
panic.
The r35 `verify_r35.sh` linked/object checks also returned `ALL PASS` with
the candidate kernel and staging config substituted and the packaged
seed/ADT section excluded; see `$A/r35-audit/check-linked.log`.

That establishes the default-off **nuwa display path** does not allocate,
register or take the r35 page's framebuffer. It is not global runtime
equivalence: the prelink adds IOMobileGraphicsFamily, IOAVFamily and Libm,
not just native code. IOMobileGraphicsFamily and Libm have no personalities;
IOAVFamily carries four donor personalities, including `IOAVSplitDisplay`
(matches `IOAVSliceVideoInterface`), and `OSBundleRequired=Root`. Independent
review must confirm the extra donor matching/startup paths do not publish a
display service with the args absent. Actual page behavior is unverified.

| Artifact in `$A` | SHA-256 |
| --- | --- |
| `archive/HOST-ONLY-incomplete-display.a` | `fccf1091f750987b10d5736c39072160ff87de0b301dcfcd62a73ca8374381de` |
| `native.macho` | `6bbc4f7aa818a4cc9361afc1ee8fcb975bc5a6e35c216e473e5d89b0aa4ec30e` |
| `prelink.macho` | `8b630300b03fda9115954b47790cc2606a095fb9a7024203e7b49e9d38c2c51c` |
| `kernel.macho` (55,865,344 B) | `476477dab77fe2342128ddd79881d6fd26b1d7b4d48d65e723860478aafdcb17` |

## Packaging blocker

```bash
H=476477dab77fe2342128ddd79881d6fd26b1d7b4d48d65e723860478aafdcb17
"$PY" -B scripts/build-ufs-apfs-root-chmh-r35-display.py --kernel "$A/kernel.macho" \
  --kernel-sha256 "$H" --output out/nuwa-r35-display-20261120-package-off
```

The entry reuses r35b's pinned r35 packaging pattern
(`UniXNU-nuwa@e0aae8197aafd4d742f2fee20301eef8bb4ea66e`) and retains the
existing root, ADT, FAT and outer checks. `--enable-display` selects the exact
on args above. The off build hit the first strict error at
`scripts/build-ufs-apfs-root-chmh-r14.py:320`, `verify_fat`:
`FAT free space below 8 MiB`. Its 64 MiB staging FAT had 8,277,504 B free,
111,104 B below the 8,388,608 B floor (r35: 8,420,864 B free). No gate or
layout changed; the on build and independent packaging audits did not run.

Off staging ADT's experimental CHMH (SHA-384, not a packaged image):
`d9f847b18af4cb17f799d611ad042be9021950a8dafa014a9a418afb5024c60d2636ec005297f118f6091d9aeca75b9c`.
No `vendor_boot` hash or on-path CHMH was produced. Authentication NOT REACHED.
The post-build upstream HEAD query failed on TLS receive; no retry or update.
Pending review: hook/ABI and default-off donor matching; then review a payload
budget change separately, retain strict gates, and independently rerun the
final build and packaging audits before considering device use.
