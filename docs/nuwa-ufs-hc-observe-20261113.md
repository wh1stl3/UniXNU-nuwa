# nuwa UFS: returning markers and four HC reads

**self-checked; host-only candidate, not device/package approval.** This extends
the r4 software checkpoint. Parent reports the r4 NULL preModLoad cleanup High
finding deep-closed. The r4 kernel/source/scripts are unchanged. No FAT, executor,
device command, new CHMH, payload native-root gate, UUID, VMM or product default
is changed. PMGR restore and dual external-table independent PASS remain
completed, per `out/pending-evidence-close-20261113/summary/verifier-summary.md`;
their full-block/signature work is reused, not rerun.

## Artifact and scope

Current kernel:
`out/nuwa-ufs-hc-observe-20261113/run-r7/kernel.macho`, **55,545,856 B**,
SHA256 `134d1a24ca32b91d3f41cfdf2d95831abdd4ec4c5be827e291970723d14ba0f5`.
Old HC r5 is **withdrawn**, retained unchanged. HC r6 contains only the gate fix,
not the PAR fix, and is not a final candidate. Earlier run directories are work
history, not this delivery.
The separate handoff `out/nuwa-ufs-handoff-observe-20261113/run-r4/` is preserved.

Implementation files:
- `patches/sheng-ufs/nuwa-ufs-hc-observe.patch`: an explicit overlay on the r4
  ShengUfs patch; not in product/default series.
- `package/diagnostics/NuwaUfsMarker.h`: returning font/pixel marker, using the
  existing console mapping; not a new display driver.
- Exclusive `out/nuwa-ufs-hc-observe-20261113/{build,test,audit,self-check}.py`:
  adapt the immutable r4/a3 builders and c1/APFS audits; original files untouched.
- This document and storage evidence in `porting.toml`.

The gate remains exact probe=2, root=0/absent, init5, root provider. Class
initialization is one-shot. preModLoad NULL still pairs postModLoad(NULL), state3,
ctor0; normal post failure is state4 and can partially register resident classes,
not rollback/uninitialization. No unload/retry. Marker calls occur before
preModLoad and after postModLoad, never inside that registration-lock interval.

### Two incremental findings

1. Ordinary review identified an ignored INIT_RETURN marker failure. After
   registration succeeds, marker false now sets terminal **init7**, not init5.
   Classes remain resident/possibly registered: no unload, rollback or retry.
   The final-byte chained test runs init with its second marker false, then
   start, then init again on the same instance/state. All three snapshots retain
   state7, mapper0/read0, and ctor/pre/post counts1/1/1; later calls only parse
   boot arguments. The original NULL cleanup remains exercised separately.
2. Directed deep identified the unprotected AT/PAR interval. The helper now
   follows this target kernel's `machine_routines_asm.s:mmu_kvtop` pattern:
   save DAIF, `DAIFSet #3` (IRQ/FIQ only), save PAR, AT, ISB, capture PAR into a
   GPR, restore caller PAR, restore exact DAIF. Only this short interval is
   masked, not drawing or mapping. One volatile asm block uses three distinct
   early-clobber `=&r` outputs and a `memory` clobber; the input VA cannot alias
   those outputs. Final code checks the exact eight-instruction system-register
   sequence and register separation. No private lock is introduced.

`run-r7/two-findings.json` binds the real execution traces, gate machine code,
all eleven refusal postconditions, and four translation-mask cases to this
exact kernel. Closure/reacceptance remains with incremental deep and verifier.

## Access contract

Only these four accesses, in order, each once as an aligned 32-bit load:

| i | Register | Physical address |
|---|---|---|
| 1 | VER | 0x1d84008 |
| 2 | CAP | 0x1d84000 |
| 3 | HCS | 0x1d84030 |
| 4 | HCE | 0x1d84034 |

Address/offset sources: nuwa firmware DTB's ufshc node, shared
`dts/sm8550.dtsi:41-45`, and the original
ShengUfs `NativeUfs.cpp:204-211`. Source snapshots/hashes and the decomposed nuwa
DTB are retained locally. The address source is **not** evidence that HC survives
ExitBootServices; unknown inherited state is the experimental measurement target.
Values are raw, with no unknown register/bit decoding.

No GCC, IS, SMMU, UTRLBA or PHY/power/control read/write; no returned-address
dereference, DMA, queue, hostBringUp/adoptAndRead/startRoot/hostSubmit, retry or
polling path from the selected entry. Mapping and framebuffer publication are
explicit software effects, not UFS control writes.

`mapPhys` is the original IODeviceMemory withRange/map mechanism, kept noinline
for an actual boundary audit. It requests `[0x1d84000,0x1d84038)` using
`kIOMapAnywhere|kIOMapInhibitCache`. IOMemoryDescriptor translates inhibit to
VM_WIMG_IO/MAP_MEM_IO and requests RW, not execute. Final `wimg_to_pte` code is
executed in bounded tests: with explicit nuwa DRAM geometry, non-DRAM HC receives
AttrIndx3 plus NX/PNX; pinned `proc_reg.h` defines MAIR_DISABLE=0 (Device-nGnRnE).
The real DRAM branch is also tested as a discriminator, not used for HC.

Software mapping page expansion uses runtime `PAGE_SIZE` (`1<<PAGE_SHIFT_CONST`), printed in
MAP_ATTEMPT's raw/state field. Host tests exercise both boundaries:
- 4 KiB: `[0x1d84000,0x1d85000)`.
- 16 KiB: `[0x1d84000,0x1d88000)`; the final 4 KiB extends beyond the DT's
  0x3000 HC resource, but **no load/store** targets that padding.

Those are runtime-boundary calculations, not a measured device page size.
Before the first HC load, AT S1E1W must resolve the returned virtual address to
exact HC PA with effective PAR Attr byte0; otherwise MAP_FAILED is published
and the candidate stops without a register read. AT is translation-only.
This proves an implementable effective-attribute check, not a captured live
MAIR/PTE. The host mapper-policy test and runtime translation check must not be
described as an observed hardware page table.

`fMap` retains the IOMemoryMap throughout all loads. Complete/error panic stops
before object release. If display refuses and the entry returns, there are no
subsequent HC loads. The object's ordinary cleanup is not a new mapping owner.

## Returning display and publication contract

The r4 loader's bound DarwinBoot commit
`3c75734014cdab0acd9541e88057b7606ee7ae08:DarwinBootPkg/Driver/BootVideo.h`
checks BGRX32 GOP format, stride/height and FrameBufferSize before populating
Boot_Video. XNU PE_init copies that into PE_state.video; initialize_screen creates
the vinfo mapping. The marker uses **that existing virtual mapping**, never a
guessed framebuffer PA or a new framebuffer alias.

Each call matches current PE console geometry to vinfo, refuses nonphysical
boot source/offset/rotation/depth/stride/geometry mismatch, then validates every
4 KiB subpage intersecting its target band with AT S1E1W. Translation must be
writable, physically match the loader-derived backing, and have uniform actual
memory attributes. No framebuffer store occurs before all checks succeed.
If these conditions cannot be established, the marker returns false and no
following HC load occurs.

Rows append in 16-pixel bands from y=64, maximum16, with fixed ASCII formatting.
The entire reserved area must end at or above height/8; the existing panic
renderer clears only from height/8 down, preserving these stage rows. The marker
does not invoke panic_screen_main, touch the first-panic sentinel, park, remap or
start a worker. Return preserves DAIF; the translation helper temporarily masks
IRQ/FIQ only within the protected interval above. It restores caller PAR before
unmasking; a subsequently delivered interrupt can use PAR again without
contaminating the already captured result. Marker ABI tests check x19-x29, SP,
DAIF and PAR under their stated masked initial state, nonoverlapping bands and
write bounds.

Normal-memory bands are cleaned to PoC using the real
CTR_EL0.DminLine-derived line size (`4 << field`), followed by DSB SY.
Device-memory bands use DSB SY without cache maintenance. Tests execute final
marker code with modeled 64/128-byte line sizes and effective normal/device
attributes, checking every clean address and publication order. There is no
fixed delay. Store/PoC publication is implemented; actual panel scan visibility
remains an observation required in the authorized device run.

**Frozen lifecycle scope:** initialize_screen retains lastVideoVirt until
another console reinitialization, which can remove the old mapping. The marker
does not claim to pin that mapping across concurrent console base/mode changes.
It executes in the root-bootstrap checkpoint window; selected closure lacks
IOGraphicsFamily/framebuffer drivers, and the marker itself neither reinitializes
nor releases the console. Parent reports directed deep accepted this frozen
closure/root window: no concurrent console-remap producer was found. That is
not an established UAF finding and this repair does not reopen the analysis or
add a speculative lock. Point-in-time AT validation is still not a lifetime pin;
preserve the reviewed frozen scope.

Stages are INIT_ENTER, INIT_RETURN (state), START_ENTER, MAP_ATTEMPT (page size),
MAP_FAILED, then ATTEMPT i/completed=i-1/address before each single load, saved
raw/completed update, and COMPLETED i/raw. After four samples HC_SNAPSHOT_DONE
is published, then the existing renderer/panic stops with all four raw values.
ATTEMPT raw=0 is a placeholder, not a sampled value.

RAM status is not reset-persistent evidence. A final visible marker is not a
unique fault cause. The existing exception/panic path may retain ESR/FAR/PC
best-effort; this unit adds no exception framework and promises no exception
display. Missing output is NOT REACHED, with no causal attribution.

## Validation and verifier commands

WSL Ubuntu-22.04 root; cwd device repository:

```sh
P=/home/wh1stl3/.local/bin/python3.11
W=out/nuwa-ufs-hc-observe-20261113
$P -B $W/build.py --out out/nuwa-ufs-hc-observe-fix-verifier-20261113
$P -B $W/self-check.py --build out/nuwa-ufs-hc-observe-fix-verifier-20261113 --incremental-fix
```

Local build and self-check exit0, **self-checked only**. `commands.json` and
`selfcheck-commands.json` retain actual argv/cwd/exit/log hashes. `tests.json`
contains **19** incremental final ARM64 cases: 13 existing driver cases (normal
four reads, all11 marker-refusal positions, NULL pre/post cleanup), one new
init→start→init chain, one existing returning/cache-publication marker case,
and four local translation IRQ/FIQ cases. The old full matrix is not rerun.

The historical51 were **41 driver + 8 marker + 2 wimg**, not51 hardware or
lifecycle tests. Driver external calls/mapper/marker are mocks; marker and wimg
code run separately. Driver/marker initial DAIF is 0x3c0 (all masked); they did
not establish open-IRQ preservation. The old reject=n cases lacked refusal
postconditions, so the old51 cannot establish refusal-stop correctness.

Those eleven existing cases now assert return, exact allowed completed-read
count `0,0,0,1,1,2,2,3,3,4,4`, attempted/completed/hc_read counters, mapper count,
no extra marker/panic, and fail immediately on **any** HC access after refusal.
The chain adds INIT_RETURN failure propagation and constructor non-retry.
The four local translator cases start DAIF=0x300/0x340/0x380/0x3c0, covering all
IRQ/FIQ mask combinations while preserving D/A. An interrupt request is injected
between AT and MRS PAR; delivery is decided using the actual emulated PSTATE
mask. It is blocked there, and if unmasked on restoration is delivered afterward
and deliberately overwrites PAR. The captured return remains correct. These
are executed final sysreg instructions with modeled interrupt/PAR hardware
effects, not actual CPU preemption, IOKit, panel scan or full lifecycle evidence.

Necessary final-layout audit rederives UFS11/190 slots, PMGR8/325 slots, all
52,674 donor bindings, APFS 4,208 bindings/192 operation pairs, policies/anchor
and seven renderer spans. Zero undefineds; exact personality and one explicit
constructor remain checked. No full signature-block or old complete ABI matrix
replay. iOS17 deployment metadata still does not qualify private iOS16 ABI.

The full hash binds **this exact file**, not byte-for-byte reproducibility.
Parent reports the independent build differed only in `_PrelinkKCID` and
related LINKEDIT metadata, with code/relocations equal. Across output paths or
builds compare code, relocation and layout/metadata semantics; do not demand
the same full hash or change the existing build system to manufacture it.

The first patch-application failure was insufficient unified-diff context;
corrected before successful build. During added mapper-policy testing the test
initialized gPhysBase rather than the actual gDramBase inputs; the final-code
failure identified this and the fixture now uses gDramBase/gDramSize. No kernel
behavior was changed to make a test pass.

Final integration remains with the parent: ordinary review + independent
verifier and incremental directed deep closure of these two findings.
Other accepted deep conditions remain frozen, not re-proven by this unit. Any later package
requires a new CHMH binding and a separate device authorization request.

## Sources and licenses

- ShengUfs `99d8bcd3e43dd24fc3c8437c67b5d4cc71ab94d0`: BSD-2-Clause repository,
  source SPDX BSD-2-Clause-Patent retained; existing driver/inspect/mapPhys.
- UniXNU `693f5d9cae8a408dd18b39f3f9fdc4228c934241`,
  BSD-2-Clause-Patent: actual kernel/renderer primitives.
- XnuPrelink `f1d80d37528a33e24643583787123c652b70a268`,
  BSD-2-Clause-Patent: original planner/emitter/parser.
- DarwinBoot `3c75734014cdab0acd9541e88057b7606ee7ae08`,
  BSD-2-Clause-Patent: loader GOP validation.
- wh1stl3/uefi-nuwa `121df32d292df1499fb75638bfc19e1a041bd2a9`,
  AOSP Font.h BSD-2-Clause notice retained in the compiled include; input bytes
  and hash recorded, no firmware edit.
- VerifiedRoot `974f043d0c71ba2e60331483a41c6c6d35274ee3`,
  BSD-2-Clause-Patent: unchanged providers and accepted external policies.
- Existing nuwa r4/a3/c1 builders/auditors on device
  `029a79bb58a403c0f3441ed991ad312ae1102c39` plus recorded local inputs:
  reused mechanism, no repository redistribution license asserted.
