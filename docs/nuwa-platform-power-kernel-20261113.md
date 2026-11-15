# PMGR root-publication kernel — self-checked

## Executor checkpoint

Parent reports kernel directed deep review PASS WITH CONDITIONS and independent
verifier PASS, and mode-2 packaging ordinary review and independent verifier
PASS. Explicit executor profile is self-checked only, awaiting independent
review and verifier: see `docs/pmgr-executor-host-20261113.md`. Earlier pending
packaging/review statements below are historical. PMGR publication and AMFI
consumption remain runtime targets; old panic disappearance does not prove
pthread passed. No device phase is authorized.

## 2026-11-13 mode-2 isolated host package

Parent reports directed deep review **PASS WITH CONDITIONS** permitting isolated
packaging and independent no-reuse rebuild **PASS** (debug/length/KCID differ,
code and data agree). This does not establish runtime behavior or merge the opt-in
patch into normal configuration. The previous pending-review statements below
are historical.

`scripts/build-pmgr-mode2-chmh.py` fixes the r5 kernel above and exact arguments
`-v serial=3 nuwa-pmgr=2`. The versioned CHMH material binds kernel, loader,
trust, args and parent ADT. The derived ADT adds only CHMH, forbids ASMB, and
the actual outer ramdisk is read back as four FAT members. Frozen parent ADT,
trust, loader, stock template and distinct original backup retain their pins.
`out/pmgr-mode2-chmh-20261113-r4/` contains the FAT, outer, layout, record,
provenance references, official command and audit. SHA256: FAT
`a9697c46d775e722d902cceea32070518ea2e8e5cfce8af8abc4eccd25afe701`, outer
`ad74c1cb7beee59b60bc0fbb446a7439e8a21a39a3f956ea574b6a62410efd45`, ADT
`59e78384804830a981e894451c66301c873afbb1da5d768220e538db2a4c8fff`, record
`be10c1a9c113e84ad3ac9d29f26e453c3ea01a02c0b7bbc75987f4208b1dd3c4`.

The build and targeted 23-negative test are **self-checked**, not independently
verified. Targeted negatives include kernel, args, modes 1/3, config, material,
record and actual outer tampering. The first build attempt failed at the config
short-name assertion: the actual pinned FAT name is `UNIXNU~1TOM`; corrected.
No executor or device action. Real nub publication and AMFI consumption remain
the runtime target; disappearance of the old panic alone is not acceptance.
CHMH is an unauthenticated experimental identity, authentication NOT REACHED;
software PMGR is not a hardware implementation. Review and independent verifier
must rerun the final build and targeted tests before executor binding.

## Current delivery (supersedes the initial blocker below)

An actual isolated native/prelink/renderer kernel exists at
`out/nuwa-pmgr-kernel-20261113-r5/kernel.macho`: **55451648 B**, SHA256
`81b85228316574782f9d5390956c3ce3d8c97e4b345a9ea1631feacf3280b5d1`.
Parent supplied ordinary reviewer `ses_e2cfcc7e4ffe9FwH4JIapXJBed`
**PASS WITH CONDITIONS** for the root-parent route. The initial hard-blocker
judgment was withdrawn; the actual changed startup/ABI link still needs directed
`deep_reviewer` and independent `verifier`, not device approval.

`nuwa_pmgr_run(IOService *publicationParent)` borrows the existing root device.
Every provider attach/start/stop/detach and provider-parent relationship check
uses that argument, not `getPlatform()`. The original nub's `+0x88` remains the
software provider, never the root. Successful provider/nub initial references
remain for boot lifetime; the existing reverse cleanup and detach/stop unwind
are preserved. No worker, wait for platform, AMFI edit, global synchronous root
matching, new MMIO, hardware success claim, or locking change was introduced.

The device-owned opt-in patch
`patches/xnu/8796-nuwa-pmgr-root-publication.patch` is applied only in the isolated
builder, **not** the normal patch series or board pins. It inserts exactly one
`nuwa_pmgr_run(this)` in `IOPlatformExpertDevice::startIOServiceMatching`, after
successful workloop creation and before the original `registerService()`.
Final callsite: `0xfffffff0079023a0`, target `0xfffffff007991510`. Default missing
or zero `nuwa-pmgr` returns without loading a kext or running the initializer.

## Startup ordering and final ABI checks

Permanent script: `scripts/audit-nuwa-pmgr-kernel.py`; machine/source evidence:
`out/nuwa-pmgr-kernel-20261113-r5/startup-audit.json`.

- Recorded bootstrap source orders `PE_init_iokit` → MAC policy registration →
  bootstrap removal/lockdown → root workloop/PMGR hook → original root matching
  → `bsd_init` → `mac_cred_label_associate_kernel` → registered policy callback.
- The final Sandbox kmod entry `0xfffffff0054ba258` loads its actual start pointer
  `0xfffffff006ae8dc8` → `0xfffffff0054bcd80`, which calls stub
  `0xfffffff0054e3ca4` / GOT `0xfffffff005ef85b0` → AMFI
  `0xfffffff004704320` → `0xfffffff004703c54`.
- Actual AMFI `ADRP/ADD/STP` at `...4703ed4–edc` stores callback
  `0xfffffff004706f34` at policyops `+0x50`; the call at `...4703fa4`
  resolves to the newly linked native `mac_policy_register`.
- Only the later BSD callback constructs worker argument
  `0xfffffff0046fe6cc` and calls actual native `kernel_thread_start` at
  `...4706f6c`. Publication is placed before **worker creation**, not based on
  a guessed 30-second runtime budget. Static ordering, not device execution.
- All donor anchors are translated through the actual final module segments.
  Their VAs stayed equal because the donor slide remained `-0x1000000`;
  native targets changed and are re-resolved. Sandbox GOT, registration import,
  worker argument/import, and wait import are asserted, not merely printed.
- Eight PMGR bindings are derived as exact donor component/segment offsets plus
  the selected slide, then checked against final N_ABS symbols and final mapped
  PMGR extents. The old reviewed archive binding member is hash-checked. Values
  remain numerically equal because donor placement is unchanged, not because old
  prelink addresses were blindly reused. The emitter rechecks all collisions
  against the new native layout and rebinds donor kernel pointers to that native.
- All 325 **final** provider vslots are checked against object relocation names;
  inherited native slots also equal the new native IOPMGR table. Storage remains
  `0x36968`, genuine nub `0x740`, binding at `+0x88`. Real parent metaclass identity
  and runtime size/equality checks remain; they were not executed end-to-end.
- The late object has empty `__mod_init_func`; final auto-init table excludes
  its initializer. Exactly one manual BL reaches it, inside gated `nuwa_pmgr_run`.
  Exactly one final BL reaches `nuwa_pmgr_run`, from the root hook.
- PMGR, pthread, AMFI and Sandbox executable bytes equal the exact donor modulo
  declared pointer relocations. All manifest pointer bindings are checked in
  final memory. Renderer changes are restricted to its recorded seven spans;
  source, font, observer padding ownership, normal PMAP RET and idle observer
  branch are reused/checked. No old stop probe or new CHMH is installed.

## Actual execution boundary

Incremental audit exit **0**, 10/10 bounded real-code checks:

1. Missing/zero boot arg returns; invalid mode returns; modes 1/2/3 reach the
   real OSKext-load entry and stop there; repeated invocation is rejected.
   Only boot-arg parsing is mocked. No fake OSKext/IOKit success is supplied.
2. The actual final slot-170 guard runs through its observation/checkpoint to
   the real panic entry. This is not the complete mode-3 lifecycle.
3. Actual final donor nub read/write run through the newly linked 325-slot
   provider vtable with mock object storage: read `0xffffffff`, write routes to
   original empty writeAon, mock storage unchanged.

Mode 1 allocation/cleanup, mode 2 attach/start/publication/matching, mode 3 full
allocation-to-refusal path, metaclass registration, OSKext startup, pthread
runtime and hardware remain **unexecuted**. Full donor/native ABI qualification
is not claimed by these static and bounded checks. No full IOKit simulator added.

## Artifacts (same r5 directory)

| File | SHA256 |
| --- | --- |
| `native.macho` | `98c4f8bd18bbf0829846e191039811d5feba12ad7ad4a1082e0a9402bc3f4185` |
| `prelink.macho` | `62d3efb13d8fcf59fd38c5095cb0a33ca1ba6d109ea2e6aab285ffaaeb6f581a` |
| `libNuwaPlatformPower.a` | `d7141f5f6139bef7756caf49b5f3838fa8458167e1881bb8d1ae32c2ac55983a` |
| `native-link.map` | `90d1d88f1d1d694f0a219fd3e1c8c3c51180948b5bb4dea58de9d1bc60789e49` |
| `original-bindings.json` | `55429a7dd2b8a2ccf26da59f148074b585c888469ff0320da5e9db2cbc1e0cb1` |
| `prelink.json` | `39a8207171b0774443876db89d6a18dad36049b21f8a8c404b4a30c156042a25` |
| `provenance.json` | `82f6bb10d8adead8c3da824d564b51ad66b6298b5c0da23df8a19470d448207d` |
| `startup-audit.json` | `216de401faacbb77e9dba181a8d4d861e544f70ac79e6c54f7ad69d3eb5e4253` |
| `audit.json` | `54f24ddbf85e34eee9c1cdbc4adeddef7c6e73f4dfeaa3d4413556df556b9853` |
| `kernel.json` | `d3c435d48dcd138d77d3d5fca03bbfae8b525f653c8ea4caf68cb69419190e1a` |

`kernel.json` binds the exact kernel, native map, prelink, startup audit, full
audit, renderer manifest, provenance and eight-binding file. Commands/exits are
in `commands.json`. Original r2 archive `568885fd…93d29e`, recorded native and
pthread/renderer inputs were retained. Only the provider's changed parent
contract and the root callsite object were recompiled; existing native object
inputs/archives and exact renderer sources/font were reused with hashes.

## Reproduction and independent verification

WSL Ubuntu-22.04 root, cwd `/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa`:

```sh
/home/wh1stl3/.local/bin/python3.11 -B scripts/build-nuwa-pmgr-kernel.py --out out/nuwa-pmgr-kernel-20261113-r5 --reuse-provider out/nuwa-pmgr-kernel-20261113-r2/provider
/home/wh1stl3/.local/bin/python3.11 -B scripts/audit-nuwa-pmgr-kernel.py --build out/nuwa-pmgr-kernel-20261113-r5 --python-tools /home/wh1stl3/.local/lib/python3.10/site-packages
```

Both final commands exit 0. The builder requires a fresh output directory; do
not rerun into r5. Independent verifier should build into a new directory
**without** `--reuse-provider` to recompile the changed source, then run the audit
on that build and separately on r5. Also rerun the record-check command below
and `git diff --check`. Source paths can affect diagnostic strings/debug/layout;
do not assume whole-kernel hash identity across different build paths. Every
build must rederive/check bindings and preserve its own manifest.

Final incremental `out/nuwa-pmgr-kernel-20261113-r5/self-check.py` with the same
interpreter exits 0: AST/in-memory compile, 11 changed/new-file whitespace checks,
TOML 14 areas, manifest/document/source SHA checks and `git diff --check`.
Unified-diff blank context lines are syntax, not trailing-whitespace defects.
The record-check command shown in the historical section below was rerun on the
final records and exited 0 (`nuwa: 14 structured areas checked`). These are
self-checks only; independent verifier has not rerun the final build/test.

Earlier attempt r2 exited 1 at isolated `IOPlatformExpert.cpp:46`, missing local
`IOKitKernelInternal.h`; fixed with explicit original-directory `-iquote`. r3
exited 1 because system ELF ld was selected; restored the recorded CLT PATH.
r4 linked/prelinked successfully but exited 1 reading link map as UTF-8; fixed
to Latin-1, matching the existing map audit. Those directories are retained.
Audit parser corrections concerned localized weak symbols and actual `STP`,
not kernel changes; a 120-second attempt timed out without a result. Final
audit maps each segment once and reuses one Unicorn instance, then exited 0.
The old archive matrix was not rerun.

Read-only upstream HEAD before and after the build was
`dff276535db3ac394f628cec58a718cd46c20ac2` (both commands exit 0).
Local base `693f5d9c…`, original source/pins, board/normal series unchanged by
this work. No FAT/outer/executor/device work, commit or push. Any future package
must recompute CHMH for this exact kernel. Existing restoration PASS and its
serial/process-exit/live-state limitations remain as recorded below.

<details>
<summary>Historical initial checkpoint — superseded, not a current blocker</summary>

No new kernel was emitted. The first source-level blocker is
`package/NuwaPlatformPower.cpp:116–117`: mode 2 requires a non-null
`IOService::getPlatform()` before attaching the provider. Reusing r2 unchanged at
the end of `InitIOKit` cannot publish the nub: that platform does not exist yet.
Moving the call to asynchronous platform matching would not establish the
requested single-threaded early-publication ordering or the AMFI deadline.
No such late call was installed merely on an assumed timing budget.

## Actual source chain

Read from the recorded native build's patched xnu-8796 tree, not current upstream:

1. `osfmk/kern/startup.c:688–698`: bootstrap thread calls `PE_init_iokit()`;
   interrupts are still disabled on return.
2. `pexpert/arm/pe_init.c:393–394`: `InitIOKit()` then `ConfigureIOKit()`.
3. `iokit/Kernel/IOStartIOKit.cpp:135–171`: initializes IOKit/libkern, creates
   and attaches `IOPlatformExpertDevice`, then records startup extensions.
   `libsa/bootstrap.cpp:183–218,608–658` reads prelinked metadata, loads KECs
   (including the selected donor pthread), and submits personalities. This is
   not the start of the actual `IOPlatformExpert` service.
4. `IOStartIOKit.cpp:174–178` calls root `configureDefaults()`;
   `IOPlatformExpert.cpp:2131–2145` creates NVRAM/identity data, not the platform
   expert service. `IOService.cpp:1535–1538` simply returns `gIOPlatform`.
5. `startup.c:716–720` → `security/mac_base.c:365–377` →
   `libsa/bootstrap.cpp:505–560`: normal security-extension loading through
   `OSKext::loadKextWithIdentifier`. AMFI is marked `AppleSecurityExtension=true`
   in the actual carrier. `libkern/OSKextLib.cpp:46–49` is the same OSKext API
   used by the r2 provider; `OSKext.cpp:5910–6010,8197–8320` covers lookup/load
   and the C++/kmod start path. This does not prove when AMFI schedules its worker.
6. `startup.c:756–773`: removes bootstrap segments, locks down, and calls
   `PE_lockdown_iokit()`; `pe_init.c:413` then starts general matching.
   `IOPlatformExpertDevice::startIOServiceMatching` at
   `IOPlatformExpert.cpp:2057–2066` registers the root service. Only the later
   `IOPlatformExpert::start`, at `IOPlatformExpert.cpp:175–176`, installs the
   platform pointer. Its `configure(provider)` follows at line 195.

This distinguishes the root **device** from the platform **expert**; treating
them as interchangeable is the integration error to avoid.

## Actual AMFI consumer evidence

Carrier: `out/pthread-renderer-20261112-r1/renderer-baseline.macho`, SHA256
`e0c235f1de499c858d6eb672f989de7692f1d97140e1064da59391642fa11f5d`.

- Body at `0xfffffff0046fe730`, string address `0xfffffff003e2628a`:
  `serviceMatching("ApplePMGRNub")` then the wait at `0xfffffff0046fe770`.
- `mov/movk` at `...e764/...e768/...e76c` constructs `0x6fc23ac00`
  (30,000,000,000 ns). No timeout modification.
- Stub `0xfffffff004717f9c` loads pointer `0xfffffff005cb5800`, whose actual
  target is native `0xfffffff0078c635c`, exported as
  `IOService::waitForMatchingService(OSDictionary *, unsigned long long)`.
- The audit records direct callers of this body, **not** a proven complete
  kmod-start-to-worker scheduling graph. That graph and the deadline remain
  unqualified; no claim that security-extension loading itself begins the wait.

## Preserved inputs and deliverables

- Formal r2 archive unchanged: SHA256
  `568885fd698489843701907e5d8216f3c9b377c678a2d6710bd8652bad93d29e`.
  Parent reports ordinary review PASS; independent verifier evidence is
  `out/nuwa-platform-power-verifier-r2-20261113/verifier-summary.md`.
- Local evidence: `out/nuwa-platform-power-kernel-20261113-r1/startup-audit.py`
  and `startup-audit.json`. JSON SHA256
  `98cdad82d0f6a38869e09ee0fd23afa1cb5cc6dc1f8577b0b23e927c6fb1a5d0`.
  It records source hashes/excerpts, the actual carrier hash, AMFI instructions,
  and resolved wait imports. It is not a kernel manifest/link map.
- Reproducibility wording fixed in the host document and power record:
  debug paths affect debug contents/layout, not only `__debug_line` or a fixed
  size; compare non-debug contents plus relocation semantics/bindings.
  The test's obsolete panic-reference comment was removed; behavior unchanged.
- Upstream read-only `git ls-remote origin HEAD` returned
  `dff276535db3ac394f628cec58a718cd46c20ac2`, exit 0. Local base pin unchanged.

## Commands and status

WSL Ubuntu-22.04 root, from the device repository:

```sh
/home/wh1stl3/.local/bin/python3.11 -B out/nuwa-platform-power-kernel-20261113-r1/startup-audit.py
```

Final audit exit 0. The first two audit attempts exited 1 at the missing-window
assertion: the inspection script initially stopped on executable padding and
then searched only the first occurrence of a duplicated string. Padding handling,
all string occurrences and 64-bit Capstone immediate normalization were corrected;
the final artifact above uses the actual AMFI reference. No archive matrix rerun.

Incremental `self-check.py` (same directory/interpreter) checks the test edit is
comment-only by reconstructing the independent r2 source SHA and comparing ASTs;
also checks TOML parsing, changed-file whitespace, unchanged provider source,
actual wait import and `git diff --check`. Exit 0. Independent verifier should
rerun that command and the startup audit, not the old archive matrix.

Record check, cwd `/mnt/d/Code/PortingiOS/UniXNU`:
`/home/wh1stl3/.local/bin/python3.11 -B scripts/porting-record.py check --device
../nuwa/UniXNU-nuwa --base origin/feat/step7-kernel-patches-8796`.
First attempt exited 1 (`power: verification evidence needs a commit`); the new
evidence was corrected to identify HEAD `029a79bb58a403c0f3441ed991ad312ae1102c39`
plus uncommitted changes. No commit was made.

## Required disposition

The minimal design change to review is an explicit root-device publication
parent passed from `InitIOKit` after extension recording, rather than requiring
the not-yet-created platform expert. That changes the reviewed provider contract;
it was **not** silently substituted for the formally pinned r2 archive. A late
platform-start hook is not equivalent evidence and needs its own scheduling proof.

No final link, eight-binding rederivation, native object/vslot/metaclass ABI
requalification, or one-shot hook test was reached. Modes 1/2/3 lifecycle and
refusal remain unexecuted. No new MMIO path, AMFI edit, FAT/outer/executor,
CHMH, official-tree edit, pin edit, device command, commit or push. Pthread
runtime remains unproven. A future kernel must derive all original bindings
from its donor/slide/layout and recompute CHMH; startup/ABI changes require
directed `deep_reviewer` review and independent `verifier` before integration.

Recovery is no longer described as in progress: independent PASS is recorded in
`out/verify-pmap-ret-run-pthread-chmh-20261112-01-20261113/verification-summary.md`.
Backup and restore-readback were 100663296 B, both SHA256
`493ca426964adabb195a00ded4ff49793bc7efd5d7bea2a567bcfd0c970a8dad`;
the existing report covers B restore and A/Android/root/_a evidence. Overall
process exit and raw serial association remain limited; this is not live-state
or persistent-interaction evidence.

</details>
