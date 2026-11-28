# nuwa UFS owner-side interface inventory

Status: **static inspection / self-checked**, no device access or new boot.
Device repository baseline `8aa2a4eb4133ef5fc23d46dfe4d63202dc88458c`;
the uncommitted cold-read decision in the separate
`worktree-cold-read-decision-20261126` was an input, not copied or changed.
Its no-boot boundary and `e75e3c1` ownership investigation remain in force.
This is a bounded source inventory, not proof that no undisclosed vendor
interface exists or that a particular loader is currently on the device.

## Result

No inspected implementation establishes a supported, XNU-callable service
that continues ordinary userdata LBA I/O across EBS, or a complete,
controllable exclusive handoff. Consequently no interface fixture or host
adapter was invented. Preserve ShengUfs and the existing read-root path;
do not open the production write gate. The external dependency is an
authoritative contract or source from the actual Qualcomm/OEM firmware
owner, tied to the installed chain: either a supported runtime ordinary
LBA service and its XNU calling/lifetime contract, **or** a verifiable
exclusive producer/DMA handoff including error and timeout paths. Both
alternatives must identify every earlier producer and its lifetime.

## Candidate and owner boundaries

| Candidate / owner | Evidence and caller / lifetime | Disposition |
| --- | --- | --- |
| XBL and ABL / earlier Qualcomm or OEM firmware | Their actual UFS implementation and producer-stop interface are not in the inspected source. The public alternative's XBL-initialized assumption does not specify a drain; the chain also includes ABL before Mu. See `nuwa-ufs-ownership-research-20261126.md` §§ Actual firmware, Follow-up. | No supported runtime LBA service or explicit complete handoff established. Do not infer closed-source behavior. |
| OEM UFSDxe / Mu firmware | At local `uefi-nuwa` commit `121df32d292df1499fb75638bfc19e1a041bd2a9`, `Binaries/nuwa/QcomPkg/Drivers/UFSDxe/UFSDxe.inf:3–11` declares `DXE_DRIVER`, selects `UFSDxe.patched.efi`; `Platforms/Xiaomi/nuwaPkg/Include/DXE.inc:39–45` lists DiskIo, Partition, FAT and this driver, while `APRIORI.inc:44` also lists it. The package README identifies a firmware version and patch, not a public source or callable runtime contract. Configuration is not proof of the loaded binary, dependencies, actual protocol publication, or exit callback. | A boot-driver declaration is not a runtime LBA ABI. Its Stop/EBS behavior and all older producers remain unknown. |
| DiskIo, Partition, FAT and Block I/O / Mu | Listed as boot-time media stack in the above include. DarwinBoot closes `Root` before EBS and enters XNU only after successful EBS (`UniXNU` local `693f5d9`, `drivers/DarwinBoot/DarwinBootPkg/Driver/DarwinBoot.c:779–783,812–821`). UEFI Block I/O and SCSI pass-through are not post-EBS runtime storage services; see ownership investigation § Contract boundaries. | Cannot legally retain boot-protocol pointers as an XNU runtime backend. Source path is the checked-out loader, not a binary-to-device identity proof. |
| RuntimeDxe, variable and capsule / Mu | `DXE.inc:6–21` lists runtime core, variable, capsule, reset and clock modules. Their names/configuration identify runtime infrastructure, not an ordinary LBA protocol. `UniXNU/package/UniXNUPkg/Test/HelloPayload/HelloPayload.c:206` calls `GetVariable` from an EFI test payload, not an XNU block client. | Variable/capsule services are not general userdata LBA I/O; no published vendor LBA runtime ABI or XNU adapter was found in inspected paths. |
| Qualcomm SCM / secure firmware | `DXE.inc:12–14` includes SCM/TZ components. `Silicon/Qualcomm/QcomPkg/Include/Protocol/EFIScm.h:177–194,226–240` describes generic secure-app messages and RPMB provisioning/erase; `scm_sip_interface.h:269` names RPMB. Neither describes ordinary userdata LBA service, runtime availability, or a producer drain. | RPMB/secure-message names do not establish a usable ordinary-LUN backend. No secure call was made. |
| Public Qcom + EDK II DXE replacement / new Mu owner | Pinned sources and initial queue replacement, stop/timeout limitations, and integration mismatch are documented in `nuwa-ufs-ownership-research-20261126.md` §§ A concrete upstream alternative and Follow-up. It assumes earlier initialization and creates new queues without an established prior-owner seal. | Source availability does not solve earlier XBL/ABL → Mu ownership; not a safe explicit transfer implementation for this board. |
| ShengUfs / XNU | Existing native root is the requested consumer, not evidence that firmware transferred ownership. Existing retained/reinit host models in `package/nuwa-data-write/` do not implement the firmware-side seal; `KernelPort.inc:35` retains `Provider<CandidatePort, false>`. | Keep existing read-root behavior, no new queue admission or hardware changes. Prior successful root observation does not prove all old producers excluded or safe writes. |

No Samsung driver found in the common firmware tree is evidence of a nuwa
provider: it is in `Silicon/Samsung/SamsungPkg`, outside the inspected nuwa
include graph. No claims are made about uninspected proprietary binaries,
other possible secure services, or a complete built FD manifest.

## Next gate and exact review question

Obtain the actual owner-provided interface/contract, chain identity and
implementations first. If it offers runtime I/O, establish ABI, runtime code
and memory mapping, reentrancy, buffer ownership, ordinary-LUN authorization,
completion/timeout and flush durability; otherwise establish producer seal,
all outstanding DMA completion including timeout and secure/bypass paths,
memory lifetime, and the exact handoff point. No external disk is a
replacement for local `userdata`.

Before any implementation touching boot-chain or DMA, request deep review:
for `UniXNU-nuwa` branch `research/nuwa-ufs-owner-api-20261126`, and the
specific newly supplied firmware repository/revision and handoff symbols,
does that owner-provided implementation cover **all** prior XBL/ABL and
OEM/Mu producers, in-flight UFS and fabric DMA, failure/timeout, mappings
and lifetime before `DarwinBoot.c:819–821` enters XNU? Identify the first
unsafe operation and prove exclusivity without relying on EBS, successful
reads or instantaneous controller status. No such new hardware change is
authorized or proposed by this document.

Inspection used local source only, plus `git ls-remote` to check upstream:
UniXNU `main` `e7bddb9a7eecdcf81f36da9fa38bd9d4d3f155c2`, device
`origin/main` `4548bbd2be0d7bccc0c789ca62934842026c6384`; neither was
merged. This is not an EDK II build, runtime test, device inventory or
independent verifier result.
