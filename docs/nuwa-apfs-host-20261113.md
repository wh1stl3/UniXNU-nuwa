# Isolated VFS/APFS host closure — 2026-11-13

Work item scope: host only, UFS inactive. No hardware/SMMU/DMA, transport,
locking implementation, device, FAT/outer, CHMH, commit or push operation.
The concurrent c1 verifier's scripts, artifacts and original dependencies are
read-only. Board and porting record are not edited by this work item.

## Reuse and transformation

- Base: `out/nuwa-ufs-link-20261113-c1/run/kernel.macho`, 55517184 bytes,
  SHA256 `d67051dcc1c2a1767a7890e22e8d62cd2f0292e0da670661473ed74c283b933b`.
- Apply the already reviewed device patch
  `patches/xnu/8796-vfs-getvfs-with-vfsops.patch` to an exclusive 8796 source
  copy; replay the original compilation for `vfs_subr.o`. Existing mount lookup,
  lock and reference behavior is not modified beyond that reviewed patch.
- Reuse XNU's `generate_symbolset_plist.sh` and
  `generate_combined_symbolsets_plist.sh`. Check the combined metadata differs
  semantically by exactly the added BSD export, then embed it in the real link.
- Re-derive UFS eleven and PMGR eight N_ABS aliases from this exact donor's
  module segment offsets and fixed slide. Rebuild the two archives with the
  unchanged reviewed late objects; **no new late-transform input** is accepted.
- Add only `com.apple.filesystems.apfs` to the roots in memory. The official
  planner computes dependencies and binding writes; no fake symbol, arbitrary
  extra root, global undefined allowance or validation suppression is used.
- Reuse existing pthread/PMGR native inputs, actual donor prelink emitter and
  seven-span renderer. The inherited UFS and PMGR audits run from new private
  copies: UFS's descriptive `vfs_bridge_added` becomes true; PMGR's fixed old
  component-list equality becomes exact old-set union APFS. No other inherited
  assertion is removed or weakened. Private PMGR's ROOT is set to the device
  repository because its copied location is under out/.

Provenance: `UniXNU/UniXNU@693f5d9cae8a408dd18b39f3f9fdc4228c934241`
and `UniXNU/XnuPrelink@f1d80d37528a33e24643583787123c652b70a268`,
BSD-2-Clause-Patent; Apple xnu 8796.141.3, APSL-2.0/source-file notices;
local `wh1stl3/UniXNU-nuwa@029a79bb58a403c0f3441ed991ad312ae1102c39`
plus uncommitted c1/PMGR mechanisms (no repository LICENSE found, no external
redistribution asserted). ShengUfs/VerifiedRoot/provider provenance is retained
in the c1 document and input manifest; no second filesystem stack is introduced.
Upstream HEAD read-only at start: `7d85ede80092050f4d87f72ac7229bb605ce07fb`;
local base pin unchanged.

## Evidence and limitations

First implementation error: a1 `native-link.log:6`, missing original
`DARWIN_TRIPLE` environment selected macOS instead of iOS. Fixed by restoring
the c1 environment; a1 is retained. a2 produced a real isolated kernel and the
inherited UFS audit checked 269 imports, 11 aliases, 190 slots, two headers,
count/anchor, no startup and 52674 donor bindings. Its PMGR audit rejected the
intentional added component at the old fixed-list assertion, so a2 is not the
final deliverable. a3 also rebuilds the embedded KPI symbolset.

Audit-tool corrections on unchanged a3 bytes: APFS default entries target real
native `_vn_default_error`, not APFS text. A separate `_vnop_read_desc` GOT slot
is adjacent to an unrelated native executable import, so code adjacency alone
cannot establish an ops array. The final audit additionally requires actual
relocated `opv_desc_ops` and registration-pointer references; non-array imports
remain descriptor bindings but are not counted as operation entries.

## Final delivery — self-checked

All paths below are under `out/nuwa-apfs-host-20261113-a3/`.

| Artifact | SHA256 |
| --- | --- |
| `kernel.macho` (55545856 bytes) | `f173e820b6f4555e94445bcbb18155c7fc228d38f168c8cca82eb0436a0f6f66` |
| `native.macho` | `4f93c0ccc82523af6dce46ef2e469b4d15d8f4ae93514fcb5f2add697373b7a8` |
| `native-link.map` | `f60367a143ff214e5eab4660cc71bebb91893ffe966cb25102381f99be93c84c` |
| `prelink.macho` | `4d5b40f469bbb391f5a30a4d4277e1c4672dc16de814888bf500e6f038d6eef3` |
| `prelink.json` | `69d498a6252695b7ae4da750d97fa04c637ce712367c70a06e632ac12a56e153` |
| `provenance.json` | `8ead8952225857f13c3291e4aec6450f9aa647256749c51e0517bacee8e523fd` |
| `apfs-audit.json` | `363af68fb4cd192a5d8a84a25e03bf5fe48b95370cf2a84761e914a87acb89c8` |

- Builder, final audit and incremental tests exited 0. AST parsed three new
  Python scripts; a deliberately corrupted VFS import slot was rejected.
  Official porting-record check exited 0 (`14 structured areas checked`), and
  `git diff --check` exited 0. No record update/integration is made here.
- Planner added exactly APFS; all necessary declared transitive components
  were already in c1. No Libm/IOAVFamily/IOMobileGraphicsFamily restoration.
- Final APFS slot `0xfffffff005eac110` contains new native bridge address
  `0xfffffff00747547c`; actual final embedded BSD KPI metadata includes its
  export. All **4208 APFS** and **52674 total donor** pointer bindings match.
- **193 descriptor references** resolve to canonical native descriptors in the
  actual **63-entry** `vfs_op_descs` table (all active). **192 entry pairs** in
  **six arrays** (13/24/20/55/39/41) have real native/APFS executable targets,
  terminators, default implementations, relocated `opv_desc_ops`, writable
  vector pointers and relocated registration-pointer references. The remaining
  reference is a GOT import, not an operation entry. Registry indices are the
  expected indices assigned by unchanged `vfs_op_init`, not a claim that init
  or `vfs_fsadd` executed. This MH_KEXT_BUNDLE donor retains named descriptors;
  the official pointer planner resolves them directly. No fileset stripped-
  symbol descriptor alias/reindex adaptation is needed for these static inputs.
- All **1050376 APFS executable bytes** equal the donor modulo the explicit
  emitter binding writes; final Mach-O backed extents and nonoverlapping VM
  ranges pass. Seven renderer spans remain bounded.
- UFS audit retains zero undefineds, 269 imports, 11 aliases, 190 slots, two
  exact 544-byte policy headers, real pointers/count **2**, unique 395-byte
  anchor and dormant constructor/personality checks. PMGR audit retains eight
  bindings, 325 slots and ten bounded real-code checks. No late transform ran.
- Read-only upstream HEAD after the build remains `7d85ede8…`; no pin changed.
  `delivery.json` binds final scripts/doc, maps, manifests, audits and binaries.

Runtime VFS/APFS registration, mount lifetime, APFS ABI and persistent UFS boot
are not established by static binding success. No native-ufs-root argument,
personality, constructor auto-init or startup caller is added. No signature,
8 GB whole-block or APFS identity matrix is rerun. Inherited compile target and
LC_BUILD_VERSION remain iOS17; neither is iOS16 runtime ABI qualification.

## Independent verifier

WSL Ubuntu-22.04 root; cwd `/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa`;
Python `/home/wh1stl3/.local/bin/python3.11`, always `-B`:

```sh
/home/wh1stl3/.local/bin/python3.11 -B scripts/build-nuwa-apfs-host.py --out out/nuwa-apfs-host-verifier-20261113
/home/wh1stl3/.local/bin/python3.11 -B scripts/audit-nuwa-apfs-host.py --build out/nuwa-apfs-host-verifier-20261113 --report out/nuwa-apfs-host-verifier-20261113/apfs-audit.json
/home/wh1stl3/.local/bin/python3.11 -B scripts/test-nuwa-apfs-host.py --build out/nuwa-apfs-host-verifier-20261113
git diff --check
```

Use a fresh directory. The audit invokes the private UFS/PMGR audits itself.
Also audit delivered final bytes with a fresh report path. Re-run official
`scripts/porting-record.py check --device <device-repo> --base origin/main`
from the read-only base checkout using Python 3.11. Results remain self-checked
until independent verifier reruns the final build/tests; integration/acceptance
belongs to the parent.
