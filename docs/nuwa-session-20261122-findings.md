# nuwa 2026-11-22 session findings

Scope: consolidation only; no build or device commands in this documentation
pass. Runtime observations and the deep-review decision below are relayed by
the parent session; their original captures, disassembly output and review
transcript were not supplied to this subagent. Host claims are self-checked
or relayed, not independently verified.

- **Memory:** the reported page reads `MEM tot=4864MiB`, so the 4.75 GiB
  window took effect. The parent reports that the bootstrap page table's 16
  pages suffice. Sources: parent session report; configuration and candidate
  provenance in [window record](nuwa-window-475g-20261122.md).
- **Data overlay:** the reported `DS=4` denotes persistent overlay open
  failure; `package/nuwa-ramblock/NativeRamBlock.cpp:98-105` assigns state 4
  when store open fails. The parent reports linked-kernel disassembly showing
  mode 2 reaches unconditional `mov w0,#0` refusal. Thus the reported boots
  did not persist `/private/var`; a writable RAM overlay is not persistent.
  This corrects the premise of a resumed old cache in
  [MG reset](nuwa-mg-reset-20261122.md), not the underlying seed.
- **Stub audit:** parent reports `hostStoreOpen` and `hostLogOpen` both
  unconditionally return false; BootProgress diagnostic `boot_diag_scan`,
  `boot_diag_stream`, `log_tick`, exit fault-reason and trace rows are empty
  or return 0. AKS matches the upstream tree and is a software substitute;
  PMGR explicitly refuses operations; the UFS root block device's read-only
  behavior is intentional. Sources: parent session audit; AKS scope and
  read-only root design in `porting.toml` storage findings. These are not
  claims of hardware-backed security or a complete diagnostic stream.
- **Write safety:** the parent reports deep_reviewer ruled out enabling
  persistent writes with the single retained slot: timeout quarantines the
  slot and root reads cannot recover. Keep read-only stubs. RAM overlay
  changes disappear on reboot. Source: parent relay of deep review; retained
  slot/quarantine design in `porting.toml` storage findings. Exit condition:
  a separately reviewed storage design that safely recovers root reads and
  provides durable writes; no such implementation is claimed here.
- **Display:** parent reports `DSP s=4 r=0` and
  `CLI in=4 out=4 ret=0 bb=1`: registration returned, an instrumented
  `newUserClient` returned success and the exact backboardd name was seen.
  No swap submission was observed. Counters and identity are independently
  sampled; `bb=1` is not executable authentication or by itself proof of
  a successful userspace open. Sources: parent session observations;
  [DSP decode](nuwa-r35l-display-dsp-20261122-observation.md) and
  [identity probe](nuwa-r35m-client-identity-20261122.md).
- **FDR:** parent reports `IOMFB_FDR_Loader` still exits 1 after adding
  `NormalModeEnable`, `ADCLLoadAll`, and canvas properties; these additions
  did not change the observed exit. Sources: parent session observations;
  [property record](nuwa-fdr-properties-20261122.md) and
  [FDR probe](nuwa-r35l-fdr-20261122.md). This does not identify the cause.
- **HID:** parent reports the HID stand-in was tried and SpringBoard still
  asserted. This excludes that experiment as a sufficient fix, not all HID
  causes. Sources: parent session observation and
  [stand-in design](nuwa-hid-standin-20261122.md).
- **SpringBoard assertion and exclusions:** the assertion persists after the
  `display-scale=3` experiment and the HID stand-in; FDR property/canvas
  additions did not change the loader exit. A stale persistent MG cache is
  not supported by the observed failed overlay open. Sources: parent session
  observations; [MG reset record](nuwa-mg-reset-20261122.md). The precise
  assertion site and any additional exclusion list were not supplied and
  remain to be recorded; none is inferred from these negative experiments.

Interaction and persistent reboot acceptance remain unmet; authentication
remains **NOT REACHED**. No independent verifier rerun in this documentation pass.

## SpringBoard display-mode assertion: updated localization

The following findings are relayed by the parent session; the disassembly and
runtime captures were not independently examined in this documentation pass.
They update the earlier statement that the precise assertion site was unknown.

- The latest SpringBoard crash PC ending in `0xbd4` is in
  FrontBoardServices, not SpringBoard.framework: unslid `0x19b91abd4` is
  `brk #0` at
  `-[FBSDisplayMode _initWithWidth:height:preferredScale:scaleOverride:refreshRate:gamut:hdr:rotation:virtual:validityCheck:] +0x244`.
  The parent reports the same origin as the crash recorded for venus.
- When `validityCheck == 1`, failure of any check reaches `brk`: height and
  width must each be neither zero nor all ones; refreshRate must be greater
  than zero on both the zero and nonzero preferredScale branches;
  scaleOverride must be at least 2^-52 when preferredScale is zero; gamut
  must be in `{0,1}`, hdr in `{0,1,2}`, and rotation in `{0,1,2,3}`.
- At construction point `0x19b92dda4`, the source object is sent `width`,
  `height`, `preferredScale`, `refreshRate`, `colorGamut`, and `hdrMode`,
  in that order. The receiver comes from the constructor's `x2` via
  `_objc_retain_x2`; its runtime class and the data sources of the three
  IMPs remain unresolved.
- We publish `canvas-width/height` on the provider nub and the six
  `IOMFBDisplayRefresh` keys, with a software 60 Hz fallback; rotation is
  not published. Whether this construction path actually reads any of these
  properties is unproven.
- The leading candidates are refreshRate or width/height being read as zero,
  not a confirmed runtime diagnosis. Do not change external interfaces on
  this basis without runtime readings.
- Next candidates, without selecting a conclusion: (a) trace the caller's
  `x2` source and class; (b) enumerate the actual property tables of our
  display service and provider read-only on the kernel side to confirm
  publication; (c) if missing refresh is confirmed, publish a value backed
  by evidence.
