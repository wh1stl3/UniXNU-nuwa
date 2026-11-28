# nuwa cold UFS initialization: offline matrix

Status: **blocked for hardware**, host model self-checked. This compares
dependencies, not an authorization to reset or transfer ownership.

Reference implementation: [MiCode/Xiaomi_Kernel_OpenSource fuxi-t-oss
`7fad87dc178d09489b74a714e4a525d56f546855`,
`drivers/scsi/ufs/ufs-qcom.c`](https://github.com/MiCode/Xiaomi_Kernel_OpenSource/blob/7fad87dc178d09489b74a714e4a525d56f546855/drivers/scsi/ufs/ufs-qcom.c),
GPL-2.0-only. Its `ufs_qcom_host_reset`, `ufs_qcom_power_up_sequence`,
`ufs_qcom_hce_enable_notify` and `ufs_qcom_link_startup_notify` are inspected
as dependencies only; no Linux source is copied. fuxi code is not proof of
the nuwa firmware state or an implementation of XNU platform services.

| Dependency | fuxi reference | nuwa evidence / remaining gap |
| --- | --- | --- |
| reset | host reset asserts/deasserts core reset, disables IRQ and invalidates ICE software state; device reset GPIO is optional | [nuwa live FDT audit](nuwa-ufs-input-audit-20261110.md) records GCC reset and GPIO 210 raw specifiers. Ownership, correct sequence and runtime provider not established. |
| clocks / supplies | lane clocks follow PHY power/calibration; timers use actual core clock and link configuration | live FDT audit lists nine host clocks and regulator references, not their firmware state, active rates, XNU providers or safe votes. |
| PHY / link | power on, calibrate, select UniPro, enable lane clocks, HCE callbacks; link startup configures PHY and timers | audit records two lanes and PHY resources. Mode, calibration, power sequencing and applicable callbacks remain unqualified. |
| ICE | host reset resets ICE registers; HCE callback enables ICE and configures shared ICE | live FDT resolves shared ICE and HWKM resources, not secure-world ownership, key state or reinitialization contract. |
| SMMU / DMA | Linux driver relies on its platform DMA environment; these callbacks do not establish a UEFI-to-XNU fence | nuwa live FDT SID `0x60` is an Android binding, not a fresh-domain authorization or proof old transactions cannot land. |
| producer / queue ownership | Linux initialization assumes its own managed host lifecycle | EBS, a zero doorbell and HCE readback alone do not prove producer exclusion or completion of outstanding transactions; trusted fence and nonoverlapping new queues remain missing. |

The current `KernelPort.inc:12–27` passes an empty reinit permit and
returns empty cold-start evidence; `Provider<CandidatePort, false>` keeps
production Data write admission closed. `Reinit.h` is a host-testable
sequence, not an implemented hardware port.

## Loader binding

The earlier independent fixed-r4 provenance chain is recorded in
[loader-r4-binding-20261111.md](loader-r4-binding-20261111.md): boot image
`692cfcca51af81230fecbba15425cf598182fbe53abb362b6046dec0f24dc2e5`
to FD, DarwinBoot PE, PDB and source commit
`3c75734014cdab0acd9541e88057b7606ee7ae08`. This batch rehashed the local
`.cache/boot-stage12-v4-r4.img` to that same digest, but did not repeat
the extraction/PDB chain. The historical boot flash acknowledgment has no
partition readback, so the running loader identity remains unproven.
The pinned source `DarwinBoot.c:640–705,782,812–821` reads files, closes the
root and calls EBS before `DarwinEnter`; it does not itself establish a
global UFS submission seal or outstanding DMA fence.

## Incremental host fixture

`tests/test-nuwa-ufs-reinit.cpp` now exercises each of the four missing
permit booleans independently and invalid old/fresh identity through the
isolated attempt itself. Every case asserts `PlatformUnproven`, zero mock
stages and reads, then `AlreadyAttempted` even with a valid permit. These
synthetic booleans are not hardware proof.

```sh
c++ -std=c++17 -Wall -Wextra -Werror -fsanitize=undefined \
  tests/test-nuwa-ufs-reinit.cpp -o /tmp/nuwa-ufs-reinit-permits
/tmp/nuwa-ufs-reinit-permits
```

Executed under WSL Ubuntu-22.04: 13 PASS lines including the new group;
self-checked only. No device access, package, new hardware operation or
production write enable. Independent verifier has not rerun this batch.
