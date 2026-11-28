# nuwa UFS ownership: targeted host research

Status: **static research / self-checked**, no device access. Baseline
`f84744c8dd47197dd3cabdc2c249d5b239f07d67`; no handoff or write admission
is established. This extends, rather than replaces, the cold matrix.

## Actual firmware and source boundary

Local `uefi-nuwa` HEAD `121df32d292df1499fb75638bfc19e1a041bd2a9`:
`Binaries/nuwa/README.md:3–5,56–60` identifies Xiaomi 13 Pro firmware
`OS2.0.110.0.VMBEUXM`, `BOOT.MXF.2.1.1-00218-KAILUA-1.36233.1`, and
documents a UFSDxe sleep-to-wakeup patch. `UFSDxe.inf:4,9–11` names FFS GUID
`0D35CD8E-97EA-4F9A-96AF-0F0D89F76567` and selects a patched PE binary,
not source. `nuwaPkg/Include/{DXE,APRIORI}.inc:45,44` include it; both
also include DiskIo and FAT. This is repository configuration, not proof
of the device's currently running loader or its binary's event behavior.
In particular the README does not identify the patched call site or caller.
Searches for this exact Qualcomm version and exit callback did not locate
corresponding supported source or a public nuwa producer-stop interface.
No closed binary was analyzed.

## A concrete upstream alternative, not a drop-in

Qualcomm's public [edk2-platforms `eedc0612ddb2bcecef5053ab31672fe058c2f21d`](https://github.com/tianocore/edk2-platforms/commit/eedc0612ddb2bcecef5053ab31672fe058c2f21d)
introduces `QcomUfsHcDriverEntry`: platform protocol and non-discoverable
MMIO registration with noncoherent DMA. It **assumes XBL already initialized
UFS**; no initial XBL-to-new-driver producer or DMA drain is proven. The
[RB3Gen2 integration `90e8f6f455138469f9337c416bb43515c733e7e9`](https://github.com/tianocore/edk2-platforms/commit/90e8f6f455138469f9337c416bb43515c733e7e9)
adds `NonDiscoverablePciDeviceDxe`, `QcomUfsHcDxe`, `UfsPciHcDxe`,
`UfsPassThruDxe`, `ScsiBusDxe`, `ScsiDiskDxe` to both DSC/FDF and
`NonCoherentDmaLib` to DSC. Its platform values are not nuwa inputs.
Both are BSD-2-Clause-Patent. This is a real supported public stack on
RB3Gen2, **not evidence of support for nuwa or binary equivalence**.

[EDK II `edk2-stable202508` UfsPassThru.c](https://github.com/tianocore/edk2/blob/edk2-stable202508/MdeModulePkg/Bus/Ufs/UfsPassThruDxe/UfsPassThru.c)
`UfsPassThruDriverBindingStart` opens the host protocol, initializes the
controller, starts an async timer and installs ExtScsiPassThru and UFS
device config. `UfsPassThruDriverBindingStop` signals queued requests,
uninstalls protocols, calls `UfsControllerStop`, then unmaps/frees lists.
Inspect its controller-stop and timeout/error paths and platform DMA
implementation before relying on it: the mere call/return and freeing
resources are not proof of a Qualcomm interconnect-wide fence. The same
file's `UfsPassThruResetChannel` and `ResetTargetLun` return success without
doing a reset, an explicit counterexample to treating interface success as
hardware evidence. `UfsPassThru.c` does not establish the behavior of the
proprietary nuwa UFSDxe.

The [upstream UFS host protocol header](https://github.com/tianocore/edk2/blob/edk2-stable202508/MdeModulePkg/Include/Protocol/UfsHostController.h)
defines `gEdkiiUfsHostControllerProtocolGuid` and Map/Unmap/Flush, not a
global producer-seal API. The older
[initial UFS stack commit `0591696eff9962b52b3b0137e865198096353573`](https://github.com/tianocore/edk2/commit/0591696eff9962b52b3b0137e865198096353573)
provides provenance, not nuwa ABI compatibility. The UFS HC protocol is
EDK II-specific, not evidence that the proprietary driver publishes it.

## Contract boundaries

* [UEFI 2.11 §7.4.6 and §7.3.13](https://uefi.org/specs/UEFI/2.11/07_Services_Boot_Services.html):
  EBS ends boot services and signals registered exit callbacks; it does not
  itself identify every producer or guarantee its DMA is drained.
  DisconnectController invokes applicable Driver Binding Stop; it can fail
  and requires the actual controller/driver graph and actual Stop contract.
  [§11.1.4](https://uefi.org/specs/UEFI/2.11/11_Protocols_UEFI_Driver_Model.html)
  requires Stop to undo Start and free its resources, but that generic
  contract alone does not identify an interconnect completion primitive.
* [§13.9.5](https://uefi.org/specs/UEFI/2.11/13_Protocols_Media_Access.html)
  BlockIo FlushBlocks concerns modified data for that block device; it
  neither seals all producers nor is a global DMA drain. Close file handles
  before direct access to their underlying filesystem blocks (§13.5.1).
* [§15.7.1–2](https://uefi.org/specs/UEFI/2.11/15_Protocols_SCSI_Driver_Models_and_Bus_Support.html)
  ExtScsiPassThru GUID `143b7632-b81b-4cb7-abd3-b625a5b9bffe`: NULL event
  requests blocking completion; async requires event completion and status
  inspection. A completed command says nothing about unrelated producers
  or earlier timeout paths. Neither BlockIo nor ExtScsiPassThru is a
  supported post-EBS runtime storage interface.

## An actual Arm lead and its boundary

Public SM8550 [upstream DTS submission](https://lore-kernel.gnuweeb.org/lkml/20221130101744.2849294-7-abel.vesa@linaro.org/t/)
identifies apps SMMU as `qcom,smmu-500`, `arm,mmu-500`; this is a
compatible, not proof of nuwa implementation revision, routing or privilege.
Arm [MMU-500 TRM DDI0517 r2p4 §2.3.5 / TBU barrier support](https://documentation-service.arm.com/static/5e908ca6c8052b1608761ab4?token=)
describes a barrier after initiating invalidation-related transactions.
Arm [MMU-500 errata SDEN-1698882, 357313 and 469112](https://documentation-service.arm.com/static/69bc44bb5536af3b0e7a052d?token=)
specifies completion for transactions **affected by invalidations** and
describes SYSBARDISABLE and stalled-transaction qualifications. This is
stronger than saying all sync is merely a register barrier, but is not yet
an all-old-UFS-DMA fence: unknown bypass/translation coverage, stream/TBU
routing, invalidation scope, earlier-stage transactions, secure ownership,
implementation revision and producer exclusion. No SM8550-specific public
contract covering those has been found. Do not program or infer values.

## Most promising next route

Investigate replacing the DXE storage stack with the public Qualcomm/EDK II
stack **only after** establishing an authoritative XBL-to-DXE initial
handoff; then design a single source-available owner through loader work,
with explicit request ledger, producer seal, completion/error handling,
DMA mappings and a reviewed transition to XNU. This removes a later
proprietary DXE boundary, but **does not remove the first XBL boundary**.
If XBL cannot provide an initial fence, the route remains blocked.
Alternatively preserve every old DMA-reachable allocation and mapping
unchanged until proven safe, including descriptors, payloads and page
tables; this requires authoritative complete inventory and memory-map
reservation before reuse, and still does not exclude a continuing producer
or overlapping writes. Unknown reachability makes this alternative fail
closed. Neither keeping EFI Boot Services callable after EBS nor silently
skipping callbacks is a valid supported ownership model.

Immediate host work: (1) inspect exact pinned r4 loader FD/manifest and
Mu nuwa DSC/FDF build graph without binary disassembly, confirm which
sources and firmware package version actually built it; (2) compare pinned
public `UfsControllerInit`, `UfsControllerStop`, async timeout, DMA Map
and Unmap paths against the RB3 provider and EBS/Disconnect callers;
(3) obtain XBL source or vendor-published contract for initial ownership,
and the MMU-500 implementation/routing and affected-transaction scope;
(4) model negative cases: late callback, command timeout, failed disconnect,
stalled transaction, bypass and unknown old mapping. A negative case must
keep the existing production write gate closed. No proposed implementation
is authorized here; boot chain, DMA and concurrency changes require deep
review.

Search entrances used: local `uefi-nuwa` recursive `UFSDxe|UfsHostController`;
web searches for `Qualcomm Uefi UFSDxe ExitBootServices UFS source protocol`,
`SM8550 UFS Qualcomm EDK2 UfsDxe source exit boot services protocol`
(search tool returned an error), Qualcomm UFS host protocol GUID, EDK2
Qualcomm UFS sources, UEFI Disconnect/BlockIo/ExtScsi, and SM8550 SMMU
fence/MMU-500. Qualcomm's public
[boot log guide 80-70015-4 rev AA](https://docs.qualcomm.com/doc/80-70015-4/topic/uefi-log.html)
shows an example UFSDxe and EBS, not this nuwa version or a fence.
No network retry or device command was performed.

## Follow-up: source and platform compatibility, 2026-11-26

Upstream UniXNU HEAD was checked before this follow-up:
`e7bddb9a7eecdcf81f36da9fa38bd9d4d3f155c2`; no pin was changed. The
following comparisons use the above fixed edk2-platforms commits and EDK II
`edk2-stable202508` as an explicit source comparison, not an assertion
that RB3Gen2 was built with that particular edk2 tag.

**First ownership boundary is earlier than the new driver.** `QcomUfsHcDriverEntry`
only installs its platform protocol and registers a non-discoverable MMIO
device. Its platform struct uses NULL override and callback, obsolete
reference-clock selection, `SkipHceReenable=TRUE` and
`SkipLinkStartup=TRUE`, as identified by the
[v3 protocol definition](https://github.com/tianocore/edk2/blob/edk2-stable202508/MdeModulePkg/Include/Protocol/UfsHostControllerPlatform.h).
It consumes no handoff HOB in that entry point. In the comparison version
`UfsPassThruDriverBindingStart` calls `GetUfsHcInfo`, then
`UfsControllerInit`; `UfsEnableHostController` skips HCE re-enable and
`UfsDeviceDetection` skips link startup when the platform flags apply.
Nevertheless `UfsInitTaskManagementRequestList` and
`UfsInitTransferRequestList` allocate/map **new** lists, write new base
registers and start them; NOP and descriptor queries follow. There is no
prior-owner ledger, seal or all-transaction drain in these inspected
functions. A source-available DXE replacement therefore cannot bootstrap
exclusive ownership merely by skipping reset. In the actual r4 chain the
Mu image is loaded after the earlier Android/ABL firmware: the relevant
boundary is **all prior firmware/ABL → Mu**, not simply XBL → DXE.

**Stop and timeout are concrete counterexamples, not a nuwa verdict.**
In [UfsPassThruHci.c](https://github.com/tianocore/edk2/blob/edk2-stable202508/MdeModulePkg/Bus/Ufs/UfsPassThruDxe/UfsPassThruHci.c),
`UfsControllerStop` writes both run/stop registers zero, writes HCE zero,
then waits for HCE zero; it does not invoke a platform SMMU/interconnect
drain. `UfsPassThruDriverBindingStop` signals queued requests before
`UfsControllerStop`, and only asserts its status before unmapping/freeing.
`ProcessAsyncTaskList` on timeout calls `SignalCallerEvent`, which calls
Flush, `UfsStopExecCmd`, unmaps/frees, then signals; the caller does not
check those cleanup return values. The synchronous `UfsExecScsiCmds`
timeout also goes to Flush/stop/unmap/free. These are observable source
sequences, not a claim that hardware necessarily misbehaves. They do not
document an interconnect-wide drain for this board or validate timeout
reuse. `DmaMap` in [NonCoherentDmaLib](https://github.com/tianocore/edk2/blob/edk2-stable202508/EmbeddedPkg/Library/NonCoherentDmaLib/NonCoherentDmaLib.c)
uses device offset and cache/bounce handling; `DmaUnmap` may invalidate,
copy and free. It is not an SMMU domain ownership protocol.

**Actual integration mismatch established.** This batch ran a seven-check
Python text fixture in WSL against local `uefi-nuwa` HEAD
`121df32d292df1499fb75638bfc19e1a041bd2a9`: nuwa DSC → Kailua DSC include
→ Qcom DSC include → Silicium DSC include; the last maps
`DmaLib` to `CoherentDmaLib`, unlike RB3Gen2's explicit
`NonCoherentDmaLib`. Nuwa FDF includes DXE and APRIORI, both include the
OEM UFSDxe. None of the four upstream non-discoverable/host/pass-through
module names appeared in those seven inspected fragments. All seven
assertions passed. This is an include-path/text check, **not** EDK II
preprocessing, effective per-module library resolution or a build.
The full set of required module packages, platform PCDs, DMA library
overrides, security policy and mutual exclusion from the OEM provider is
not wired. The Android FDT declares `dma-coherent`, while RB3 selects
noncoherent DMA: neither decides the actual Mu/stream coherency.
`Mu_Basecore` submodule is not populated; a stock RB3 build or a mock of
invented handoff inputs would not discriminate these ownership questions,
so no firmware build or synthetic interface fixture was performed.

**SMMU identity is now narrowed, not a fence.** Previously captured nuwa
Android live DTS, SHA256
`1a329e36397fbc64b98b745e6a1f6794d18d3ff2a0c3f25202a68d2459c66101`,
is audited in [nuwa-ufs-input-audit](nuwa-ufs-input-audit-20261110.md):
UFS phandle points to `qcom,qsmmu-v500`, SID `0x60`, first provider
window `0x15000000 + 0x100000`. Independently, fixed upstream Linux
[SM8550 DTS `45e34c8af58f23db4474e2bfe79183efec09a18b`](https://kernel.googlesource.com/pub/scm/linux/kernel/git/torvalds/linux/+/45e34c8af58f23db4474e2bfe79183efec09a18b/arch/arm64/boot/dts/qcom/sm8550.dtsi)
uses the same apps-SMMU window and UFS SID with
`qcom,sm8550-smmu-500`, `qcom,smmu-500`, `arm,mmu-500`.
This supports a same-SoC **software-description correlation** to MMU-500,
not an identification-register read, exact silicon revision, secure
configuration, firmware stream route, or proof every old transaction
traverses this TBU. Thus the generic Arm invalidation/sync guarantees and
errata above remain candidates only; no board-level fence is inferred.

**Other public consumer and HOB search.** Linaro's
[2024 U-Boot boot-flow account](https://www.linaro.org/blog/initial-u-boot-release-for-qualcomm-platforms/)
says SBL prepares a HOB list, but does not specify a UFS ownership HOB.
The fixed upstream [U-Boot Qualcomm UFS commit
`0c9c501a87e0070b944ffcd8f0d9942353048f41`](https://patches.linaro.org/project/u-boot/patch/20240910-topic-ufs-qcom-controller-v1-4-54c0d2231b10@linaro.org/)
reports testing on SM8550 and provides reset/PHY/clock initialization,
not an XBL transaction-drain or handoff contract. Qualcomm's
[Lemans SPL UFS v4 cover letter, 2026-10-19](https://lists.u-boot-project.org/pipermail/u-boot/2026-October/635934.html)
describes XBL → SPL and UFS loading, explicitly reports build tests on
Rockchip boards, not a nuwa handoff result. No explicit nuwa UFS HOB or
resource descriptor encoding an outstanding-DMA fence was found in these
inspected sources. The generic HOB list and reserved-memory descriptions
do not establish which old DMA mappings or producers exist.

**Host checks executed.** The fixture above used Python `Path.read_text`
and exact substring assertions against the seven named files. It can be
reproduced by checking the named include chain and matching `DmaLib|`,
`UFSDxe.inf`, and the four RB3 module names; the first Windows `python`
invocation failed because Python was not installed there, then the same
fixture ran using `wsl -d Ubuntu-22.04 -- python3 -`. Also ran:

```sh
c++ -std=c++17 -Wall -Wextra -Werror -fsanitize=undefined \
  tests/test-nuwa-ufs-reinit.cpp -o /tmp/nuwa-ufs-reinit-research
/tmp/nuwa-ufs-reinit-research
```

WSL produced 13 PASS lines, including missing fence/invalid identity and
no-retry timeout cases. These are mock permit invariants, not hardware
completion evidence. Independent verifier has not rerun them.

The required `porting-record.py check --base origin/main` was run in WSL
with `GIT_DIR` and `GIT_WORK_TREE` set to the actual worktree paths because
the Windows-created `.git` link is not directly resolvable by WSL git. It
failed at the first pre-existing branch-versus-main code finding:
`tests/NuwaDataFixtureGpt.h: add its owner area and paths to porting.toml`.
This document-only batch did not modify that file or the record. The first
attempt without those environment variables failed earlier on the worktree
gitdir path; an intermediate attempt lost the quoted device argument.

**Information to request from Qualcomm/OEM:** exact nuwa
`BOOT.MXF.2.1.1-00218-KAILUA-1.36233.1` XBL/ABL and patched UFSDxe
interface/source or approved handoff specification; identification of
all producers and exit callback ordering; old request/descriptor/data
and SMMU table allocations and lifetime; explicit success and timeout
drain semantics across UFS, SMMU and downstream fabric; SM8550 apps-SMMU
revision/configuration, UFS stream/TBU route, bypass and secure ownership,
and applicable MMU-500 errata; clock/PHY/ICE ownership and DMA coherency.
If unavailable, independently advance the existing host-only display
acceptance/IOSurface lifecycle evidence work and Data recovery/negative
tests with the production UFS write gate closed. Neither needs another
device snapshot, nor entails modifying the protected boot chain.
