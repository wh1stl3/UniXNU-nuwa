# PMAP observer: first normal native/pristine-prelink layout

Follow-up: parent reports independent layout verifier PASS and reviewer PASS WITH CONDITIONS;
new renderer/two-B candidate is separately [self-checked here](pmap-ret-diagnostic-20261111.md), not independently accepted yet.

2026-11-11 task checkpoint, **self-checked only**. This supersedes the earlier
component-only “no native map yet” state in `pmap-ret-observer-link-20261111.md`.
Parent reports that component review/verifier accepted the unbound component;
this new native/prelink and its layout have not yet been independently verified.
No renderer generation, two-B binding, payload/bootimg, device, commit/push,
source-pin change, base/component/firmware edit or owner-wrapper edit.

## Actual build and inputs

Windows launch cwd: `D:/Code/PortingiOS/nuwa/UniXNU-nuwa`.
Linux build cwd: `/mnt/d/Code/PortingiOS/UniXNU`.
Dedicated ext4 root **R**: `/root/nuwa-pmap-ret-native-20261111`, initially absent.
Work **W**: `R/nuwa/ios-16.7.16-20H392/nuwa_pmap_ret`; tree **T**: `W/tree`.
No spaces/commas, no release/--os/per-OS defconfig reset.

Fixed base `693f5d9cae8a408dd18b39f3f9fdc4228c934241`; device HEAD
`63769f208783769f7fa4ec5cffc14d3eba37b21a` plus authorized local changes.
SoC `a9f45dc60c035084b95463781538380f4c3606c9`.
ArmCpu `93a5030c5d983d0ef90f0fca93879d6e36ad1ba8`;
ArmDTPlatform `417ff95d6a6e8607ddea9309ec45c3bfd4a67c60`;
XnuPrelink `f1d80d37528a33e24643583787123c652b70a268`.
XNU `1b191cb58250d0705d8a51287127505aa4bc0789` / 8796.141.3, iOS16.7.16/20H392.
Other reference pins are recorded completely in `R/build-result.json`'s nested
`previous_attempt.references`; unchanged caches were copied, not fetched.
27 selected device-series patches were normally applied in the private work
source; their exact paths/hashes are `W/xnu-inputs.json`.

`scripts/build-nuwa-pmap-ret-native.py` invokes the actual fixed-base parser,
Context, cmd_defconfig, feeds.resolve, tree.assemble, kernel.build and
kernel.prelink. It does **not** call CLI prepare's shared submodule updater or
feeds.fetch, avoiding base checkout writes. Entire build runs under `unshare
-n`, with Git file transport only and Python bytecode writes disabled. Source
reference copies live in R/feeds, not the old tree. A private `[build]` empty
config avoids reading base unixnu.local.toml.

Actual command family (all options below were explicit):

```sh
# Linux cwd /mnt/d/Code/PortingiOS/UniXNU; launched via wsl -d Ubuntu-22.04 -u root --cd <cwd> --
unshare -n /home/wh1stl3/.local/bin/python3.11 -B /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/scripts/build-nuwa-pmap-ret-native.py \
  --base /mnt/d/Code/PortingiOS/UniXNU \
  --cache-feeds /mnt/d/Code/PortingiOS/UniXNU/out/feeds \
  --soc /mnt/d/Code/PortingiOS/nuwa/UniXNU-sm8550-common \
  --kernelcache /mnt/d/Code/PortingiOS/UniXNU/out/ipsw/20H392/kernelcache.decompressed \
  --out /root/nuwa-pmap-ret-native-20261111 --jobs 8
```

Three actual invocations, no polling or duplicate successful build:

1. Above command, exit1: defconfig/cache-copy/assemble exit0; source preparation
   failed at `prepare-xnu-source.py:52`, absent DriverKit metadata cache.
   urllib attempted remote lookup, rejected by the network namespace (no
   external traffic). Native compilation/link and prelink had not occurred.
2. Same command plus `--resume-offline-headers
   /mnt/d/Code/PortingiOS/UniXNU/out/nuwa/ios-16.7.16-20H392/nuwa/tree`, exit1.
   Copied existing default/8796 DriverKit and TrustCache JSON metadata. The
   source already contained the needed headers: actual normal preparer printed
   **Restored 0**, `offline_restored_headers=[]`. Missing-header copies would
   require exact cached Git blob hashes. After successful source preparation,
   the exact normal xnu-inputs signature was written to complete its previously
   failed final step; no patch or compiler option was bypassed. Bootstrap then
   stopped at `scripts/linux/prepare-xnu.py:115`: private compiler-rt source
   absent, Git HTTPS transport denied. No native object record/kernel yet.
3. Same command plus `--resume-offline-libs <same old nuwa tree>`, exit **0**.
   Copied only pinned llvm-project `58c46bae21181fb4240cf964461bea738d96d50e`
   and Libc `899a3b2d52d95d75e05fb286a5e64975ec3de757` source caches, verified
   HEAD/clean tracked state; preserved failed-fetch directory. No old library,
   fakeroot, object, archive or kernel was reused. Normal bootstrap → all five
   archive recipes → final native link → pristine prelink then completed.

The two denied network attempts are recorded failures, not downloads or
network retries. Only existing approved nuwa/base caches were used to fix
missing offline input paths. Failure records remain in
`R/build-result-first-header-failure.json` and
`R/build-result-bootstrap-libs-failure.json`; final JSON nests both histories.
Background shell completion IDs: `sh_1c69f5c9b001BPu10OAKXWUl64` (1),
`sh_1c6a2f644001u1W304iWpS4Yli` (1), `sh_1c6a69bea0019Iqp3gSpnxzO1S` (0).
Detailed original failure output remains in those shell results; the normal
bootstrap log is the latest attempt, not falsely claimed to preserve all runs.

Final JSON UTC timestamps (actual host clock, not inferred from task date):
kernel `2026-11-10T18:09:34.925363Z`–`18:10:49.187027Z` (74.262s), exit0;
prelink `18:10:49.205527Z`–`18:10:51.435783Z` (2.230s), exit0. Bootstrap is an
internal normal preparatory pass; no separate successful bootstrap exit is
invented. The kernel stage's final normal link and prelink are separate facts.

Effective `.config`: `XNU_BUILD_ARCHIVES=true`, observer=true; all baseline
options retained, default board defconfig unchanged. Ordered fifth recipe
actually built the observer archive; archive log is
`W/logs/archive-05-build-nuwa-pmap-ret-observer.log`. Extra archive/map flags
were consumed by the normal link. Fresh output checks plus the new link map's
live observer member prove this was not a stale incremental native. Extra
archive dependency caveat remains: future archive changes require explicit
relink, not an assumed make dependency.

## Artifacts and linked observer layout

| Artifact | Actual path relative to W | Bytes | SHA256 |
| --- | --- | ---: | --- |
| native | `tree/build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/mach.development.bcm2837.unstripped` | 17344304 | `4a5bf5cc4f6920409b09fdf11eea21389b52b490e247515ab07ffdd38a7f8aa2` |
| pristine prelink | `kernel/kernel.macho` | 55386112 | `3a38b6781c17f30efe2d49c946cf06c47cea5a52cfc58b69ab491c421917b6ef` |
| native map | `tree/build/nuwa-pmap-ret-observer/native-link.map` | 5994203 | `25c892e8a167c448bb1d24853c0420b09b716361f110b17960c90ffcf2ccb460` |

Donor decompressed input: 50937856B,
`2ec297bac95bcba01046fd0148e97e7e5885c05a6c18827f39f534ba375c1221`.
No historical fb1e prepared kernel was reused or declared the new candidate.

Native and pristine-prelink have identical observer VAs/file offsets/words:

| Symbol suffix | VA | File offset | Segment / section | init/maxprot |
| --- | --- | --- | --- | --- |
| entry | `0xfffffff007991338` | `0x98d338` | `__TEXT_EXEC,__text` | 5 / 5 (RX) |
| renderer_branch | `0xfffffff007991340` | `0x98d340` | same | 5 / 5 |
| message | `0xfffffff0071331bd` | `0x12f1bd` | `__TEXT,__cstring` | 1 / 1 (R) |

Words: `d0ffbd00 9106f400 14000000`; decoded ADRP+ADD equals the actual
53-byte constant message address. Slot is still **B .**, unbound. These are
Mach-O load-command permissions, not a claim that runtime pmap mappings were
executed/verified. Complete sections/segments are in layout.json/headers dumps.

Map member `[971]` is the new `libNuwaPmapRetObserver.a(pmap-ret-observer.o)`.
Exactly its three live atoms are attributed: entry8B, slot4B, literal53B.
cctools displays the cstring as a literal string rather than its symbol name;
the actual defined message symbol VA is independently matched. No observer
init atom/registration or unexpected undefined symbol exists. The component
object is checked by the enhanced relocation-field test; source/builder/object/
archive paths/sizes/hashes are saved in `component_provenance`.

## Fresh AppleImage4 and RET evidence (not execution)

Audit identifies `com.apple.security.AppleImage4`, CFBundleVersion5.0.0,
AppleSecurityExtension=true from **this** pristine prelink's __PRELINK_INFO,
then reads its embedded Mach-O and actual runtime tables. Unique named
`pmap cs`, version5, at `0xfffffff005cad070` selects init
`0xfffffff0046e98cc` via +0x10; +0x58 is actual `darwin kernel` runtime
`0xfffffff005cb14d8` (init `0xfffffff0046efda4`). The module's __img4_rt set
contains the PMAP pointer. These module VAs happen to match older donor-based
experiments, but were rediscovered, not copied as input addresses.

The module has **no LC_FUNCTION_STARTS**. Audit therefore explicitly bounds a
scan from its runtime initializer to the next executable runtime method
`0xfffffff0046e9f9c` (allocator), not an invented compiler function extent.
Module identity and matching segment deltas establish correspondence to the
donor; every code byte in that bounded range equals its donor counterpart.
Exactly one normal RET (`0xd65f03c0`) is at `0xfffffff0046e9f00`, file offset
`0x19acf00`. `pmap-initializer.disasm.txt:395–410`: original canary CMP/B.NE
at `...9edc/9ee0` → failure path `...9f18`; original x29/x30 and x19–x28
restores, `ADD SP,SP,#400` at `...9efc`, then RET at line404. SP adjustment
400 is divisible by16; no body/canary/error/restore byte was edited. Other
tail-log/error paths remain original, not hooked.

Static sequence/arguments rechecked from new code and native/GOT bindings:

- `monitor-to-public-order.disasm.txt:23–27`: when the original mode branch
  chooses the kernel monitor provider, call `...46f140c` → stub `...46f9ef0`
  → GOT `...5caba48` → new `_kernel_image4_get_monitor_exports`
  `0xfffffff00771ff88`. Returned x0 is stored at `...5cb14d0` by `...46f1414`;
  that store precedes runtime-dispatch call `...46f141c` → `...46e4a28`.
  Native monitor implementation `_xnu_image4_get_monitor_exports`
  `0xfffffff0077202ec` logs and returns NULL (`native-monitor.disasm.txt`).
  This is a static conditional dataflow, not proof of which mode executes.
- `runtime-initializer-dispatch.disasm.txt:7–20,67–72`: default Darwin runtime
  init occurs first; linker-set loop loads each runtime's +0x10 and dispatches
  `x0=x25` (`...46e4b28`) / BLR (`...46e4b2c`). For PMAP the callback x0 is
  its actual table. No separate x1 success/status contract is invented; the
  PMAP body reads x19 from `[x0,#0x58]` (Darwin `i4rt_context`, unrelated to ArmCpu secondary opt-in).
- Later secondary runtime/config **description helper**, not an assumed
  initializer: `...46f1830` calls `...46ef83c`, actual x0=`...5cb14d8`,
  x1=`...5cb1310`; decoded from the immediately preceding ADRP/ADD pairs.
- Only after that does `...46f183c` call stub `...46f9ea8` / GOT
  `...5caba18` → new `_img4_interface_register` `0xfffffff0078990d0`, passing
  table `...5cb1578`, version18; its +0x198 is the discovered PMAP runtime.
  Thus stopping at the normal PMAP RET does **not** establish public interface
  registration, later initialization, authentication or stage5 success.

The exports-NULL path above is not the source of software monitor=0. The new
follow-up proves `_code_signing_configuration`'s zero store → AppleImage4
output slot → PMAP bit1 test explicitly. Also, fixed source HEADs/cache stamps
do not imply raw-clean key inputs: ArmCpu/native_prelink consumed bytes match
HEAD only after line-ending normalization, with both hashes recorded there.

## Layout audit command and remaining gate

Actual audit cwd `/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa`; command exit **0**:

```sh
/home/wh1stl3/.local/bin/python3.11 -B scripts/audit-nuwa-pmap-ret-layout.py --build-result /root/nuwa-pmap-ret-native-20261111/build-result.json --out /root/nuwa-pmap-ret-native-20261111/layout-audit-final-r2
```

The audit reads existing images only; uses the ordinary XnuPrelink Mach-O/XML
reader and system llvm-objdump. It corrected two evidence-format assumptions
(non-UTF8 unrelated map symbols; cstring literal atom label), and stopped an
initial function-start query because LC_FUNCTION_STARTS is absent; the explicit
bounded scan above replaces that assumption. Intermediate audit directories
are preserved. No such audit correction rebuilt or modified the images.

Evidence mirror: `out/pmap-ret-native-layout-20261111/` (build histories,
final-r2 layout JSON, headers/disassembly/map/config/logs); binaries stay in R.
Independent verifier should rerun the final audit command with fresh
`--out R/layout-verifier-final`, independently cross-check the two full hashes,
normal final-link/archive logs, permissions/map ownership and RET/canary flow,
then `git diff --check`. If parent requires a full rebuild, use a separately
authorized fresh out and the recorded offline prerequisites; do not rerun into
R or silently reuse its compiled output. No independent rerun is claimed here.

Checkpoint achieved: **new native + pristine prelink + reviewable unbound
layout**. Next minimal action is independent layout/flow review, then establish
legal renderer placement/ordinary entry in this new layout. Renderer cave
ownership/reach has **not** been qualified; no old cave/remaining33B/segment
expansion is assumed. Do not bind either B or change the fixed owner-wrapper
kernel gate until the parent accepts the new layout and final patch brief.
