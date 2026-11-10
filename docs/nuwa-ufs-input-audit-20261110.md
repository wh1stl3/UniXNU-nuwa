# nuwa UFS driver-input audit — 2026-11-10

**self-checked; driver readiness BLOCKED.** This is an offline resource inventory,
not driver selection, a hardware probe, installation, or storage qualification.
Only this document and `scripts/audit-nuwa-ufs-inputs.py` are task-owned. No
board/DTS/SoC/base/feeds/submodule, Image4 research, or existing status file changed.
No device client was invoked. No commit/push.

## Inputs and reproducibility

- Local nuwa capture: `../.cache/device-evidence/20261107-recovery/live.dts`,
  SHA256 `1a329e36397fbc64b98b745e6a1f6794d18d3ff2a0c3f25202a68d2459c66101`.
  Raw input stays ignored; only resource properties are exported.
- Catalog: `../../UniXNU/components.toml:123–140`; repository
  `https://github.com/UniXNU/ShengUfs.git`, fixed revision
  `99d8bcd3e43dd24fc3c8437c67b5d4cc71ab94d0`.
- Base checkout and existing Windows `out/feeds` had no `NativeUfs.cpp`.
  One HTTPS download (no retry) used
  `https://codeload.github.com/UniXNU/ShengUfs/tar.gz/99d8bcd3e43dd24fc3c8437c67b5d4cc71ab94d0`.
  Ignored archive `out/ufs-input-audit-20261110/input/ShengUfs-99d8bcd.tar.gz`,
  SHA256 `56579a870f62974c47458cab36f8ffb441915f7d391542944ff3b2839146f366`.
  Extracted sibling `ShengUfs-<full revision>/` is the explicit driver-source input.
  The script checks catalog pin, archive root and **every archived file's bytes**
  against that directory; JSON records file hashes. This is HTTPS commit-archive
  provenance, not Git object/signature authentication. No alternate HEAD used.
- Existing WSL `/usr/bin/dtc` and `/usr/bin/fdtget`, both DTC 1.6.1. The system
  `python3` lacks `tomllib` (`script:16`, initial exit 1); the existing
  `/home/wh1stl3/.local/bin/python3.11` works. No package installation.

Run in WSL Ubuntu-22.04, cwd `/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa`:

```sh
/home/wh1stl3/.local/bin/python3.11 scripts/audit-nuwa-ufs-inputs.py --self-test
/home/wh1stl3/.local/bin/python3.11 scripts/audit-nuwa-ufs-inputs.py \
  --dts ../.cache/device-evidence/20261107-recovery/live.dts \
  --driver-source out/ufs-input-audit-20261110/input/ShengUfs-99d8bcd3e43dd24fc3c8437c67b5d4cc71ab94d0 \
  --driver-archive out/ufs-input-audit-20261110/input/ShengUfs-99d8bcd.tar.gz \
  --catalog ../../UniXNU/components.toml \
  --out out/ufs-input-audit-20261110/final
git diff --check
git check-ignore out/ufs-input-audit-20261110/final/resources.json
```

From PowerShell, prefix Python commands with
`wsl -d Ubuntu-22.04 --cd /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa --`.
`--out` must be within this device repo's ignored `out/`; it must not overwrite
inputs. Use a separate output subdirectory for independent verification.
Outputs are `resources.json`, `resources.md`, compiled `input.dtb` and local-only
`dtc-local.log`. Do not publish raw DTB or tool logs. On failure consult
`error.json`, not resources from an earlier invocation in the same directory.

The parser is **dtc → DTB → fdtget**, not regex DTS parsing. It indexes phandles
across the tree, then follows allowlisted typed resource references from the host,
including provider dependencies and cycles. Each reference has originating
node/property/cell offset, raw cells, target and resolved/unresolved status;
inherited interrupt-parent records its defining ancestor. Unresolved handles,
missing argument widths, truncated tuples and invalid reg widths are input issues.
Exit 0 means supported inventory completed; exit 2 means incomplete; exit 1 means
tool/syntax/source failure. **All results retain `driver_readiness=BLOCKED`.**

The export is deliberately not a complete Android binding interpreter: no clock
ID-to-register inference, pinctrl programming, ICE algorithm traversal, SMMU
child-context interpretation, or arbitrary vendor-property reference guessing.
`interrupts-extended` is retained raw and explicitly flagged unsupported if seen.
Register addresses are parent-bus addresses with ancestor cell widths/ranges
preserved, not silently translated MMIO. No source-level driver dependency or ABI
analysis is inferred by the script. The following mapping is manual static work.

## nuwa resource result

Final audit: **32 closure nodes, 59 references, zero supported-reference issues**.
The closure includes non-UFS clock inputs of the shared GCC provider; these are
not assertions that UFS requires those other peripherals. `resources.json` is the
machine-readable complete table; this table is a curated source cross-reference.
All line numbers below refer to the local `live.dts` above.

| Input | nuwa observation / raw cells | Source |
|---|---|---|
| Host / ICE / HWKM | `0x1d84000 + 0x3000`, `0x1d88000 + 0x8000`, `0x1d90000 + 0x9000` bytes | 8976–8979 |
| Address encoding | `/soc` has one address and one size cell; ranges `[0,0,0,0xffffffff]` maps this low bus window identically into the two-cell root | JSON ancestor_bus_metadata |
| IRQ | `[0,0x109,4]`: GICv3 SPI **binding number 0x109 (265)**, flags `0x4` (level-high); no +32 conversion in output | 8980; GIC 973–984 |
| Lanes / reference selector | 2 per direction; `dev-ref-clk-freq=0` is a selector, not measured Hz | 8986–8987 |
| PHY | `0x56 → /soc/ufsphy_mem@1d80000`, reg `0x1d80000 + 0x1934`, 2 lanes; own nine clocks, four supplies, reset back to host `0x55,0` | 8981; 8935–8952 |
| Host clocks | Nine named entries, raw cells listed below; freq table units Hz, Android constraints only | 8988–8990 |
| GCC | `0x37 → /soc/clock-controller@100000`, reg `0x100000 + 0x1f4200`, one clock/reset argument cell | 8777–8787 |
| RPMh clocks | `0x38 → /soc/apps_rsc@17a00000/drv@2/clock-controller`, one clock argument cell | 1019–1022 |
| IOMMU | `[0x3e,0x60,0]`, two provider argument cells; provider `qcom,qsmmu-v500`, windows `0x15000000 + 0x100000`, `0x151fe000 + 0x40` | 8998; 15245–15259 |
| DMA declaration | `dma-coherent` present, Android `qcom,iommu-dma="fastmap"`; neither proves XNU mapping/coherency or UEFI state | 8999–9000 |
| ICE configuration reference | `0x58 → /soc/shared_ice`; resolves node identity, not crypto setup | 9001; 8955–8973 |
| Host power domain supply | `vdd-hba: 0x2bc → /soc/qcom,gdsc@177004` | 9005; 22807–22819 |
| Host regulator supplies | `vcc: 0x2f6 → pm-humu-l17`, `vccq: 0x308 → pm-v6g-l1`, ref-clock `0x30a → pm-v6g-l3`, vccq-parent `0x305 → pm-v6g-s4` | 9006–9013; 1520–1527, 1924–1931, 1960–1967, 1879–1885 |
| Reset GPIO / reset | `[0x79,0xd2,1] → pinctrl@f000000` (GPIO 210, raw flags 1); `[0x37,0x18] → GCC`, name `rst` | 9014–9016; 2982–2992 |

Host clock order (phandle, provider-specific ID), **not UEFI enabled-state facts**:

| Name | Raw pair |
|---|---|
| core_clk | `0x37,0x8a` |
| bus_aggr_clk | `0x37,1` |
| iface_clk | `0x37,0x89` |
| core_clk_unipro | `0x37,0x99` |
| core_clk_ice | `0x37,0x8d` |
| ref_clk | `0x38,4` |
| tx_lane0_sync_clk | `0x37,0x97` |
| rx_lane0_sync_clk | `0x37,0x93` |
| rx_lane1_sync_clk | `0x37,0x95` |

The frequency table has nine min/max pairs: core and UniPro 75–300 MHz,
ICE 100–403 MHz; other entries zero (not evidence of disabled clocks).
Regulator `*-microamp` values are microamperes, voltage `*-uV`/`*-microvolt`
values microvolts; reset/IOMMU specifiers remain raw binding-dependent cells.

## Manual driver-consumer comparison (not automated findings)

Driver paths below are relative to the exact ignored `ShengUfs-<revision>/` input.
Reading the two previously unavailable headers succeeded from this fixed archive.
Their historical sheng comments/constants are **not** nuwa authorization or board
configuration; resource equality below is independently compared with nuwa DTS.

| Consumer / source | Actual behavior | nuwa implication / missing input |
|---|---|---|
| `NativeUfs.cpp:120–151` probe | Platform-root provider matches separately; nub compatible test looks for `qcom,sm8550-ufshc` | Live Android compatible is `qcom,ufshc`; changing a compatible string is not hardware initialization |
| `NativeUfs.cpp:2138–2147` start | Requires nonzero probe/root boot argument **and** IOPlatformExpertDevice; nub match alone returns false without starting hardware | No historical probe is run by this audit; no runtime root personality established here |
| `Info.plist:10–13` | Shows nub IOPlatformDevice personality; root personality is described in source as KernelConfigTables-provided | Do not infer platform-root launch from this plist alone |
| `GccUfs.h:7–24`, `NativeUfs.cpp:180–204,1001–1005` | GCC/host windows are constants, not consumed from DTS `reg`; inspection reads fixed clock/GDSC offsets | nuwa host base/size and GCC base agree numerically; no proof the register semantics/state or power prerequisites agree |
| `GccUfs.h:28–31` | Explicitly leaves reset/RPMh/TCSR/QMP-PHY programming unqualified | Need a nuwa firmware handoff contract or reviewed platform initialization; Android supplies/reset/PHY tables alone cannot close this |
| `NativeUfs.cpp:392,1013–1038` | Fixed SMMU mapping window `0x15000000 + 0xd0000`, physically contiguous un-mapped DMA, fixed stream `0x60`, explicit queue/SMMU takeover | DTS has same provider base/stream argument, larger provider register extent; this does not authorize takeover or establish free context banks |
| `SmmuTakeover.h:20–75,78–115` | Runtime register-based geometry/ownership planning and configuration callbacks | Static phandle resolution cannot satisfy those runtime prerequisites; no implementation changes, Deep required for future DMA/SMMU work |
| `NativeUfs.cpp:906–909`, `RootCommands.h:293`, `TransferPoll.h:17–18` | Polled transport with interrupts masked | SPI resource is recorded but no IRQ registration is established by this inventory |
| `NativeUfs.cpp:133–142,992–1038` | Resource graph is not a generic DTS clock/regulator/PHY consumer interface | No direct auto-conversion from this inventory to driver configuration is justified |
| `components.toml:132–135`, driver `README.md:5–28` | Catalog only declares iPadOS 17 ABI and sheng dependencies; README discusses separate newer source-storage work and qualification limits | Target remains iOS16/8796; neither inventory nor newer README supplies iOS16 ABI compatibility |

Shared `../UniXNU-sm8550-common/dts/sm8550.dtsi:41–52` only declares disabled
host/PHY windows, no usable host resource graph. Its PHY size `0x2000` differs
from the Android capture's `0x1934`; record both, do not choose or edit either.

## Concrete next-input gaps

1. **ABI/build interface**: independent iOS16/8796 storage-family/class/vtable and
   dependency qualification, including the selected driver build entry. No driver
   build was attempted; fixed-source availability is not ABI support.
2. **Platform handoff**: nuwa-specific evidence for power domains, the nine host
   clocks and PHY clocks/supplies/resets at UEFI→XNU handoff, plus controller/queue
   ownership. Existing Android DTS supplies identity/topology, not runtime state.
3. **DMA/SMMU**: explicit reviewed nuwa ownership/coherency/address-domain contract;
   matching `0x60` cannot justify adopting another board's bypass procedure. Future
   implementation needs a bounded Deep brief, not automatic enablement.
4. **Root publication**: nuwa root layout and matching policy must be qualified
   separately. Current stage5 APFS trimming/empty UUID is intentional; unchanged.

Next host task can compare the nuwa firmware's existing UFS initialization/handoff
interface with item 2 and prepare an iOS16 ABI input brief for item 1, read-only
first. No new board values or driver API are invented here.

## Executed checks and boundaries

All final commands above ran in the stated device cwd via WSL: self-test exit 0
(7 checks), final actual audit exit 0 (32 nodes / 59 references / zero issues),
`git diff --check` exit 0 and output ignore check exit 0. Preparation archive
download/extraction exit 0; a prior shell-variable preparation command failed
before any HTTP request, then used literal paths. Initial default-Python import
failure is preserved above, not called a passing test.

Additional self-checks: `python3.11 -m py_compile scripts/audit-nuwa-ufs-inputs.py`
exit 0; PowerShell assertions on host's three registers, nine clocks, SPI265/flags4,
59 references/zero issues and blocked readiness exit 0. Export scan for sensitive
property names found none (not a general anonymization proof). New files remain
untracked, so ordinary `git diff --stat` only reports pre-existing unrelated status
edits. Per-file `git diff --no-index --stat -- NUL <new-file>` includes this task;
corresponding `--check` commands returned difference status 1 with no whitespace
diagnostics, not exit 0. No staging of other sessions' files was done.

Self-tests use real dtc/fdtget with synthetic DTS: valid cyclic references and
cell widths; SPI remains 0x109/flags4; excluded sensitive sentinel does not export;
unresolved phandle, truncated specifier, missing provider width, malformed reg,
duplicate phandle and DTS syntax errors are detected. They do not simulate UFS,
execute source drivers, or establish hardware behavior. The local dtc warning log
is retained; successful compilation is not a claim that all Android binding
warnings are resolved.

**Independent verifier should rerun** the two Python commands with a fresh
`--out out/ufs-input-audit-20261110/verifier`, then `git diff --check` and ignore
checks. This result remains self-checked until that occurs. Final integration and
acceptance belong to the parent orchestrator; no phase/area grade is raised.

## Independent verification (2026-11-10)

Independent verifier (cwd UniXNU-nuwa, fresh out/verifier-ufs-20261110): self-test exit0 (7 checks), full audit exit0 (32 nodes / 59 references / 0 issues, driver_readiness=BLOCKED), py_compile exit0, git diff --check exit0. Offline audit only; no driver readiness, hardware behaviour or device claim.
