# nuwa UFS handoff observe: isolated startup checkpoint

**self-checked; no device operation or packaging.** This candidate deliberately
reads **zero** of the proposed fourteen registers. It establishes a host-tested
NativeUfs initialization/matching path, not a firmware-state snapshot, working
storage, authentication, or persistent interaction. Ordinary review/verifier and
directed deep review of startup ABI/access list are still required.

## Current evidence and scope

PMGR restoration and dual external-table independent verification are **completed
PASS**, as reported by the independent verifier in
`out/pending-evidence-close-20261113/summary/verifier-summary.md`. This unit reuses
that evidence and the a3/policy inputs; it does not rerun signing or full-image
block verification. The missing whole runner exit and runtime limitations in that
summary remain. No current live-device state is asserted.

Baseline a3 SHA256:
`f173e820b6f4555e94445bcbb18155c7fc228d38f168c8cca82eb0436a0f6f66`.
Current fixed kernel `out/nuwa-ufs-handoff-observe-20261113/run-r4/kernel.macho`,
55,545,856 bytes, SHA256
`4ff463092e79e06eefc6d3a0230e97b8249bf4421985ccafd63fbd7e5de30c0d`.
Old r3 `d1c3786a...728b9cd1` is retained unchanged but **withdrawn as a release
candidate**. Parent reports old verifier work finished/source released and its
evidence sealed withdrawn; it is not acceptance evidence for r4.
No old fixed carrier or other device asset is used as an implementation input.
The inherited renderer/auditors retain their historical provenance checks.

## Access qualification (all denied)

The nuwa firmware DTB gives GCC `0x100000 + 0x1f4200`, and HC
`0x1d84000 + 0x3000`. Common DTS agrees with HC but leaves it disabled.
`GccUfs.h` supplies reference offsets; `NativeUfs.cpp:188-211` supplies the
reference volatile-32-bit read operations. These are not independent proof of
read side effects or permission/completion after ExitBootServices.

| Budget sequence | Register | Candidate physical address | Decision |
|---|---|---|---|
| 1 | UFS_PHY_GDSCR | 0x177004 | deny |
| 2 | AXI_ENABLE | 0x177018 | deny |
| 3 | AHB_ENABLE | 0x177024 | deny |
| 4 | UNIPRO_CORE_ENABLE | 0x177068 | deny |
| 5 | TX_SYMBOL0_ENABLE | 0x177028 | deny |
| 6 | RX_SYMBOL0_ENABLE | 0x17702c | deny |
| 7 | PHY_AUX_ENABLE | 0x1770b0 | deny |
| 8 | UFS_MEM_PHY_GDSCR | 0x19e000 | deny |
| 9 | CAP | 0x1d84000 | deny |
| 10 | VER | 0x1d84008 | deny |
| 11 | IS | 0x1d84020 | deny |
| 12 | HCS | 0x1d84030 | deny |
| 13 | HCE | 0x1d84034 | deny |
| 14 | UTRLBA-low | 0x1d84050 | deny |

GCC prerequisite missing: nuwa post-EBS access/security/interconnect and
side-effect-free read evidence. HC additionally lacks nuwa power/clock/reset and
HC-access evidence. The sheng AHB HW-gating anecdote is explicitly **not** a nuwa
permit. nuwa firmware lists UFSDxe and UFS SMMU configuration, but UFSDxe is a
binary; loading it does not establish post-EBS access ownership or register read
safety. No Samsung/other-board firmware interpretation is borrowed.

Machine-readable per-item width, semantics, prerequisite, deny decision and input
hashes are in `run-r4/access-list.json`. Raw values are **not sampled**, not valid
zeros. No register is mapped, read, decoded, or written; no UTRLBA dereference,
DMA, queue, SMMU, PHY, or power action occurs through this entry.

## Real startup and bounded observation

The device driver patch reuses ShengUfs, not a new driver. `probe/start` accept
only `native-ufs-probe=2`, `native-ufs-root=0`/absent, initialized classes and an
`IOPlatformExpertDevice` provider. Other probe modes and nonzero root refuse.
`start` has no path to hostBringUp/adoptAndRead/startRoot/hostSubmit. Original
transport methods remain dormant, not removed or newly qualified.

The root hook follows the existing nuwa PMGR hook and precedes the original
`registerService`. On the bootstrap thread it loads original IOStorageFamily,
uses actual `OSMetaClass::preModLoad`, invokes the real compiler-generated
NativeUfs/NativeUfsBlock constructor, then `postModLoad`. The existing reviewed
symbol-partition/relocation transform suppresses automatic constructors. A state
guard makes the registration attempt one-shot, including failures. No worker,
locking implementation, or concurrency primitive is changed. Final instruction
records and the single call-site checks are in `handoff-audit.json`; runtime
IOKit lifecycle is not claimed.

### Directed deep finding and minimal fix

Deep review found a High defect in the former driver patch lines 34-35:
`preModLoad(NULL result)` still holds `sStalledClassesLock`. In the actual pinned
`libkern/c++/OSMetaClass.cpp:780-803`, allocation failure clears `sStalled` but
does not unlock; `postModLoad(NULL)` takes the error/finish path at 824-827 and
954-978 and releases the lock. The corrected NULL branch keeps init state **3**,
calls `OSMetaClass::postModLoad(handle)` before return, and invokes the constructor
**zero** times. No private lock operation or retry is added. Only this one driver
source line changes from r3; the XNU hook/personality patch and builder are unchanged.

On a non-NULL handle, postModLoad failure remains state **4** and may leave
partially registered classes. The linked implementation stays resident; it does
not unload, retry, or claim rollback/uninitialized state. A missing runtime
checkpoint is **NOT REACHED**, not evidence of a cause or of this failure mode.

The official root-personality pattern is compiled into KernelConfigTables;
final table bytes are checked exactly, with only one NativeUfs root personality.
It is isolated: neither default series nor product configuration is enabled.
The original payload sheng-pmgr/native-root gate, VMM and UUID remain unchanged;
no fake `_sheng_pmgr_run` is supplied.

`inspect` caches a one-shot terminal checkpoint and panics through the existing
renderer. `attempt=0 completed=0 hc_read=0 terminal=1 init=5` means no MMIO
attempt, with raw values explicitly NOT SAMPLED. This cannot locate a hung MMIO
load. Any future nonempty read whitelist needs reviewed access prerequisites and
a genuinely visible pre-read marker, not just a RAM write followed by final panic.

Bypass record: unproved post-EBS reads / pure startup checkpoint / no register
snapshot value / lift only with per-register nuwa access/read-safety evidence and
pre-read visibility review. The checkpoint's evidence value is reaching original
class registration and NativeUfs root matching/start, not controller readiness.

## Validation and reproduction

WSL Ubuntu-22.04 root, device repository cwd, Python
`/home/wh1stl3/.local/bin/python3.11`, always `-B`:

```sh
P=/home/wh1stl3/.local/bin/python3.11
W=out/nuwa-ufs-handoff-observe-20261113
$P -B $W/build.py --out out/nuwa-ufs-handoff-observe-fix-verifier-20261113
$P -B $W/self-check.py --build out/nuwa-ufs-handoff-observe-fix-verifier-20261113 --pre-null-only
```

Local r4 build and directed self-check exit 0. `selfcheck-commands.json` records
exact argv/cwd/exit; `commands.json` records compiler/linker/patch commands.
The new directed test executes final ARM64 initializer bytes with preModLoad
returning NULL: postModLoad is called **exactly once with x0=0**, constructor zero,
final state3, and the second entry performs no registration/cleanup work (only
the existing two boot-argument parses). All other outgoing paths trap; MMIO is
unmapped. The real postModLoad implementation is not executed by this mock test;
its NULL/unlock contract is checked against the pinned source, not a full IOKit
simulation. `handoff-audit.json` records the NULL CBZ, actual machine bytes and
executed branch path, as well as the constructor-before-matching code.

Coverage wording for ordinary review is restricted to the historical **69**
cases: probe absent/0/1/3-14/0xffffffff/2, root explicitly 0 (plus root=1 refusal),
wrong-provider and init-state/failure cases, with named IOKit calls/constructor
mocked. Root absent, arbitrary malformed arguments, all possible defaults and
complete lifecycle were **not** established by those tests. That old matrix is
not replayed or promoted to r4 verification; this round adds **one** directed
pre-NULL/re-entry case and reuses prior symbolic/source contracts only.

Necessary final-layout increment checks: zero undefined symbols; UFS11 aliases
and 190 slots; PMGR8 aliases and 325 slots (old 10 execution cases not rerun);
52,674 donor pointer bindings;
APFS 4,208 bindings/192 operation-entry pairs; exact relocated signed headers,
anchor/count; seven renderer spans. All are rederived/checked for this layout,
not assumed from a3 addresses. The compile target remains iOS17; it is not proof
of complete iOS16 private ABI compatibility.

The first implementation failure was driver-patch context at the constructor
insertion; malformed context alignment was corrected before the successful
isolated build. Failed `run`/`run-r2` directories are retained, not candidates.

Independent verifier must rebuild into a fresh path and rerun the directed
`self-check.py --pre-null-only` command above;
compare semantic bindings/code rather than path-dependent debug hashes. Parent
retains final integration/acceptance. Next gates: ordinary review + verifier,
then directed deep review of actual startup/constructor ownership and this
empty access whitelist; only then packaging and a new device authorization request.
The kernel changed, so any later CHMH must be newly bound to r4; no packaging is
performed in this unit. Deep closure is requested for this single NULL-cleanup
finding, not a new claim of complete startup/runtime qualification.

## Reuse provenance

- UniXNU/ShengUfs `99d8bcd3e43dd24fc3c8437c67b5d4cc71ab94d0`: existing source
  archive and inspect pattern; repository LICENSE BSD-2-Clause (individual source
  SPDX BSD-2-Clause-Patent retained).
- UniXNU/UniXNU `693f5d9cae8a408dd18b39f3f9fdc4228c934241`, BSD-2-Clause-Patent:
  official `native-aes-personality.patch` pattern and immutable build inputs.
- UniXNU/XnuPrelink `f1d80d37528a33e24643583787123c652b70a268`, BSD-2-Clause-Patent:
  actual donor planner/emitter and Mach-O parser.
- UniXNU/VerifiedRoot `974f043d0c71ba2e60331483a41c6c6d35274ee3`,
  BSD-2-Clause-Patent: unchanged providers/policies from a3.
- Existing local nuwa a3/c1/PMGR builders and auditors on device HEAD
  `029a79bb58a403c0f3441ed991ad312ae1102c39` plus recorded uncommitted inputs:
  preserved mechanism, no repository redistribution license asserted.
- apple-oss-distributions/IOStorageFamily
  `e45fbe30a7879e0b16e26dddb78538f1b00e0bff`, APSL-2.0:
  existing annotation contract only, no second storage implementation.

Official checkout/pins are read-only. Read-only upstream HEAD before work was
`7d85ede80092050f4d87f72ac7229bb605ce07fb`; final check is recorded in the manifest.
