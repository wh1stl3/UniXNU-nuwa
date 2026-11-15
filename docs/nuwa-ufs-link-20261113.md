# Dormant NativeUfs static link — 2026-11-13

**self-checked; inactive, not deployable.** Task C produced a real isolated
native/prelink/renderer kernel. No hardware, DMA/IOMMU, locking, transport,
personality, root argument, packaging, device, commit or push change was made.
No VFS bridge was added in this unit and no larger APFS closure was added.
Existing pthread/PMGR progress is retained, not upgraded to UFS runtime success.

All new work is confined to `out/nuwa-ufs-link-20261113-c1/` and this document.
Existing scripts/docs, r5, official checkout/pins, input providers and the concurrent
read-only verifier's dependencies are not edited. Source object and input hashes
are checked before linking; the unchanged r5 provenance inputs are rechecked.

## Inputs and reuse

Parent reports storage 11-alias/190-slot contract and VerifiedRoot provider
independent PASS; dual external-header input ordinary review PASS WITH CONDITIONS.
The separate full-block verifier remains outside this task. No 8 GB full-image
hash/signature or APFS identity test is rerun here.

| Reused input | SHA256 |
| --- | --- |
| original `NativeUfs.o` | `f673df6258caa1e41f84526ba054ddf7241961f2c42e899683ce54b2c88cac01` |
| `libVerifiedRootProviders.a` | `144ea75698720db92f523ab7bf72cba78f619951646aff0d28f6cf8a1dc908f4` |
| 2944-byte `libNuwaRootInputs.a` | `dc975e12945ef567763d530a5aac427f58ad321e5ff3b223db7998bf82388c57` |
| storage contract r3 | `2ff52dd7508bfd023eed8d884840edb3e49235591f1cd5fd3425504975937443` |

The corresponding external-table userdata remains the prior 8446279680-byte
candidate `da429da64b4d91a08b8adb1d3162f8348b37b358509ab1bd5d8bf09abdbf68d7`;
it is not read or modified by this link task. Its identity and full-window evidence
remain in `docs/root-external-policies-20261113.md`.

Reuse provenance (no newly fetched implementation):
- `UniXNU/ShengUfs@99d8bcd3e43dd24fc3c8437c67b5d4cc71ab94d0`, BSD-2-Clause:
  preserved object, not recompiled or replaced.
- `UniXNU/VerifiedRoot@974f043d0c71ba2e60331483a41c6c6d35274ee3`, BSD-2-Clause-Patent:
  existing real verifier/crypto provider archive.
- `UniXNU/UniXNU@693f5d9cae8a408dd18b39f3f9fdc4228c934241`, BSD-2-Clause-Patent:
  original native compilation/link inputs and official weak-default convention.
- `UniXNU/XnuPrelink@f1d80d37528a33e24643583787123c652b70a268`, BSD-2-Clause-Patent:
  existing parser, fixed-slide layout planning and actual donor-pointer emitter.
- `wh1stl3/UniXNU-nuwa@378a27b24318cc34e9b67b034ceccff8496fe774` plus existing
  uncommitted PMGR builders/auditor: late symbol-partition/relocation transform,
  static class audit and renderer. No repository LICENSE found; no external
  redistribution license asserted. Exact reused file/input hashes are retained.
- `apple-oss-distributions/IOStorageFamily@e45fbe30a7879e0b16e26dddb78538f1b00e0bff`,
  APSL-2.0: prior annotation contract only; no second storage implementation linked.

Read-only upstream HEAD before/after was
`7d85ede80092050f4d87f72ac7229bb605ce07fb`; local base pin remains unchanged.

## Actual link and final checks

The builder replays the r5 native-link command, retaining original
`vm_kern.o`, `param.o`, `ubsan_minimal.o`, PMGR late archive and root hook.
Only the output/map destinations and three force-loaded UFS/provider/input
archives are added. No global undefined allowance or duplicate globals/shims.

- Both final native and kernel have **zero undefined symbols**. All 269 original
  UFS imports have checked final addresses and concrete object ownership.
- Five hidden globals resolve to their original `vm_kern.o`, `param.o` and
  `ubsan_minimal.o` map owners. They are not copied/export substitutes.
- Eleven N_ABS aliases are newly derived from this donor's IOStorageFamily
  segment offsets and fixed slide `-0x1000000`. Absolute aliases reserve no
  layout storage, breaking the link/prelink cycle. Emitter collision checks and
  final module extents then independently confirm the addresses; no r5 addresses
  are copied. Numeric equality is a consequence of unchanged donor placement.
  ld64 omits N_ABS rows from its map; object symbol kind/value plus final symbol
  equality establish ownership, rather than misusing GOT map entries.
- The actual final storage metaclass/constructor/destructor audit and **190**
  donor slots pass; all **190** final NativeUfsBlock slots equal their object
  relocation symbols. Inherited targets resolve to the newly linked native.
- Final read-only `__DATA_CONST` contains two exact 544-byte headers, both real
  pointer targets and lengths, and count **2**. The original 395-byte anchor
  equals the archive member, occurs exactly once in both native and kernel and
  is in read-only storage. Runtime page protection is not established.
- Actual selected ld64 rejects undefined weak `_boot_progress_poll` (probe exit
  **1**, expected observed behavior). Only then the official weak-hidden
  `void boot_progress_poll(void) {}` convention is used. Object N_PEXT/WEAK_DEF
  and final **RET** are checked. This means **no observer**, not successful UFS.
- Original constructor exists. The reviewed partition-preserving transform
  swaps/remaps symbol indexes, empties `__mod_init_func`, and verifies partitions.
  UFS text bytes and all retained relocation semantics are unchanged. The final
  auto-init arrays exclude it, and executable segments contain no direct B/BL to
  it. There is **no real UFS startup entry**, so this kernel remains inactive.
  The actual kernel personality table is byte-identical to r5, with no NativeUfs.
- All **48,466** emitted donor pointer bindings are checked in final memory.
  Renderer differences are restricted to the recorded **seven** spans.
- Existing PMGR auditor reran against this new layout: **8 bindings, 325 slots,
  10 bounded real-code checks**, exit 0. This retains static startup ordering,
  pthread/PMGR/donor executable preservation and renderer checks, not complete
  IOKit lifecycle, pthread runtime or hardware evidence.

First audit-tool error was `audit.py:110`: it assumed ld64 listed absolute
aliases in its map. Corrected by checking original alias object N_ABS symbols
against final symbols and recording that owner. Read-only-anchor segment and
zero-sized executable-segment handling were also corrected; no linked artifact
was changed by audit fixes. Final audit exits 0.

## Artifacts

Paths below are relative to `out/nuwa-ufs-link-20261113-c1/run/`.

| Artifact | SHA256 |
| --- | --- |
| `kernel.macho` (55517184 bytes) | `d67051dcc1c2a1767a7890e22e8d62cd2f0292e0da670661473ed74c283b933b` |
| `native.macho` (17473024 bytes) | `37286c103786be68984ba39563a1f2bf77f4adb7f97edad2aa9c1a1120436a40` |
| `prelink.macho` | `cab52e54f788bd72df51da0db9b16dcd84f63796514510cf12fefbd537cf0d64` |
| `native-link.map` | `3d17aad7efb1c180a5170633a4d71d8ad3ab5773c3d0f484d0b77f9517ae60a5` |
| `NativeUfs.late.o` | `a9971b7a4e66a9c8868c88c508dc1fa0d733046ffa8f480f8766bb7fc0bac703` |
| `libDormantNativeUfs.a` | `aa1439211ea46d87f72ced7045f3076987232347b91f64b02b886176e60fc254` |
| `provenance.json` | `e2e79f8726f33e9afa7323683d7642119624cf833a39dbb5998f160beccb8775` |
| `ufs-link-audit.json` | `07f34a437991b91defad719e50a058a16d212ed4baec88ef14f2c979992a61e5` |
| PMGR `audit.json` | `a68c81e9a10b4c268121f9e14d024c86a1a24ef257be131b37a588eaebb2dac0` |
| `startup-audit.json` | `e8f6343a58d78bdd2f7ba494569a050d79ac2e0d41d20a930fedc11d2538ad77` |
| `commands.json` | `0fc1e3e0f825e2e3e79234fe48c8218ec9436beca952e7c5e514c67b567e5a85` |

`delivery.json` additionally binds scripts, renderer/prelink/bindings manifests,
audit outputs and this document. Subprocess argv/cwd/exits/logs are in
`commands.json`; build wrapper, final UFS audit and PMGR audit each exited 0.

## Independent verifier rerun

WSL Ubuntu-22.04 root, cwd `/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa`;
Python is `/home/wh1stl3/.local/bin/python3.11`, all commands use `-B`:

```sh
P=/home/wh1stl3/.local/bin/python3.11
W=out/nuwa-ufs-link-20261113-c1
$P -B $W/build.py --out out/nuwa-ufs-link-verifier-20261113
$P -B $W/audit.py --build out/nuwa-ufs-link-verifier-20261113 --report out/nuwa-ufs-link-verifier-20261113/ufs-link-audit.json
$P -B scripts/audit-nuwa-pmgr-kernel.py --build out/nuwa-ufs-link-verifier-20261113 --python-tools /home/wh1stl3/.local/lib/python3.10/site-packages
$P -B $W/self-check.py
git diff --check
```

Use a fresh directory; do not overwrite original outputs. Also audit the delivered
`run/` with `audit.py --report <fresh-report-path>` and rerun PMGR auditor there.
Path-dependent debug/layout hashes may differ; verify code/data, exact aliases,
provider ownership, all slots and relocation semantics, not whole-file equality.

Remaining: independent final build/test acceptance, directed actual ABI review
where required, UFS startup/lifecycle, nuwa power/clock/PHY/DMA ownership,
transport/concurrency, VFS/APFS integration and persistent real-device operation.
The inherited object LC_BUILD_VERSION is still iOS17.0, not iOS16 ABI proof.
Any future package needs new CHMH binding; this unit authorizes no package or
device execution. Final integration/acceptance remains with the parent.
