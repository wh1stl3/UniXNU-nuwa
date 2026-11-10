# Current-image BNCH instruction fixture (2026-11-10)

**Independent verifier PASS: BNCH four-case matrix plus 26 evidence-robustness
checks, and consumer-parse increment (parent-reported).** Static review limits
BNCH findings to the constructed initial state; consumer-parse static review
PASS required no changes. Neither is a real runtime/authentication result;
BNCH device gate unchanged. Host integration groups the three scripts, this
evidence and device records in one local commit; no push or external publication.
The separate Android recovery/userdata task remains in progress, not completed
by this host milestone. This implementation performs no device operation/build.

## Scope and binding

`scripts/research-current-image4-bnch.py` accepts explicit kernel/ADT paths and
hashes; supports only the current pinned layout, with no historical-input or
address fallback. No Apple instructions or input copies are embedded in source.
It imports existing parser/object-boundary definitions, never their CLI,
builder, historical INPUT or adapter-installation paths. Dependency hashes are
recorded in the local JSON.

Inputs (relative to device repo):

| Input | Size | SHA256 |
| --- | ---: | --- |
| `out/mix-n-match-20261110/audit-final/new/kernel.macho` | 55357440 | `fb1e796d7357b3e7ff7027bb94377d1cd38eae7283a6c72a7460914a200a0fbd` |
| same path + `.adt` | 13172 | `9172e0ccd2efe250bcba05ce1e1884a5bb19a9c7d6a86527aaa35c36e5de453b` |

Actual provider tables at `0xfffffff005cad070` (PMAP_CS) and
`0xfffffff005cb14d8` (Darwin) both have version **5**. PMAP_CS +0x10 selects
initializer `0xfffffff0046e98cc`; +0x58 selects Darwin, not a fixture-replaced
pointer. The initializer's actual BL at `0xfffffff0046e9a24` binds reader
`0xfffffff0046eae28`. Table values, relevant native symbol addresses, and
disassembly windows are retained only in ignored output. Actual chip descriptor
is `0xfffffff005cae660`, secure-boot level 0; original `_pmap_in_ppl` instructions
returned 0 in every initialization run **under the constructed offline initial
state**, not as hardware measurements. Neither result was stubbed or changed.

### Constructed offline initial state

The existing `Model` maps a contiguous zero-initialized emulated address range
covering Mach-O segments, then copies each segment's file-backed bytes to its VA.
Non-file-backed memory, gaps and synthetic stack/heap start zero; they are not a
snapshot of a live booted kernel. IORegistry nodes and OSData objects/vtables are
synthetic, populated from the decoded ADT at the allowed object boundaries.
The original ADT bytes (or an in-memory BNCH-only variant) are mapped separately;
original `_SecureDTInit` and `_SecureDTLookupEntry` set up lookup state and find
`/chosen/manifest-properties`. Reader calls set X0 to that node, X1 to `BNCH`,
X2 to the guarded synthetic buffer, X3 to a u32 capacity initialized to 48.
Initializer calls set X0 to the bound PMAP_CS table, SP to synthetic stack
`0xf08000`, LR to return sentinel `0xf00000`. Other register/kernel state is
emulator/setup state, not reconstructed device state. Source-file-backed tables
remain intact; donor writes occur only in emulator memory.

Hypothesis: BNCH instruction acceptance is a capacity/copy contract, not proof
of a producer, nonce identity or authentication. Error cases distinguish native
missing/oversized input handling; successful cases permit bounded continuation
without treating initialization as authentication.

## Actual execution

Revised final evidence: ignored `out/image4-bnch-offline-20261110/matrix-reviewed.json`.
Each case has exact donor PC coverage, all visited PCs, boundary stub calls,
raw errno, output writes, guards, panic/terminal PC, callback and unreached checks.
Coverage excludes stubbed instructions and terminal panic; sentinel `0xf00000`
is a fixture return address, not a donor instruction.

| Emulated BNCH | Reader errno | Output length | Reader/init donor PCs | Initializer outcome |
| --- | ---: | ---: | ---: | --- |
| absent (actual baseline) | 2 | 48 unchanged | 25 / 1385 | original panic, PC `0xfffffff0046fa028`, level/errno `[0,2]` |
| present, length 0 | 0 | 0 | 41 / 1730 | this initializer path returns to sentinel |
| experimental CSPRNG 48 bytes | 0 | 48 | 41 / 1720 | this initializer path returns to sentinel |
| experimental 49 bytes | 84 | 48 unchanged | 28 / 1386 | original panic, same PC, level/errno `[0,84]` |

Panic format: `failed to read boot nonce hash: secure boot level = %#llx: %d`.
Reader and initializer both use original SecureDT lookup/property and native
zero/copy instructions. Successful reads zero the capacity then copy the actual
length; errors leave the reader output unchanged. Write hooks and adjacent
canaries found **no output-buffer overrun** in this matrix; invalid-memory lists
are empty. This is finite-input evidence, not a universal memory-safety proof.

Only modeled boundaries: IORegistry `fromPath`, property/release, OSData
length/bytes, `safeMetaCast`, and runtime logging. No allocator, lock, signature,
digest, nonce comparison, authentication-result or PMAP_CS check was stubbed.
The actual spinlock initializer ran; synchronization acquisition entries are
stop boundaries, not success stubs, and none was reached.
Executing this initializer path through return is **not complete real runtime
initialization**: publication, live kernel state and real object lifecycle are
not reproduced. The harness now requires reader/initializer lengths to be 48
on failures and 0/48 on successes, plus the exact native panic format and
`[0, errno]` stack arguments on both failures.

The CSPRNG token is only an experimental process-session-epoch input in emulated
memory. **48 is capacity, not a proven producer contract** (zero length also
returns). There is no hardware anti-rollback, donor identity or device value.
Epoch rolling/rejection is **not implemented**, so no donor or fixture epoch
rejection is claimed. Python input-gate tests below are not donor negatives.

## Precise next boundary and limitations

The bound is initialization, not authentication: zero/48-byte cases returned;
there is no authentication termination PC or callback because no authenticated
consumer entry was invoked. Nonce equal/different/old-epoch checks, AMNM-related
consumer comparison and signature/digest validation are all **NOT REACHED**.
AMNM=true may bypass a later comparison; this fixture does not force one.

Next execution needs a current-image, interface-bound consumer entry and its
object/runtime-state preconditions. Specifically bind the firmware/manifest
API through the current exported interface and establish a documented missing-
manifest error contract before any no-manifest negative invocation. Do not
guess an address or call `img4_firmware_execute` without a manifest; its void
result would require observing the actual result callback, not a return errno.
No signed IM4M/IMG4 positive is available in the supplied 20H392 evidence; this
task did not claim an exhaustive new IPSW search. It does not test bad signatures
or authorize emulating arbitrary kernel/security state to reach a consumer.
Missing positive/real state or a need to replace a security judgment remains a
stop condition. Closed-source provider source is **not** asserted as a necessary
prerequisite; the Deep correction stands. Device release remains prohibited.

## Commands and independent rerun

Windows cwd `D:/Code/PortingiOS/nuwa/UniXNU-nuwa`; WSL cwd
`/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa`, Ubuntu-22.04 `/usr/bin/python3 -B`,
Unicorn 2.1.4 / Capstone 5.0.7. No dependencies installed.

Revised final run used the first command below with output `matrix-reviewed.json`;
exit **0**, log `out/image4-bnch-offline-20261110/run-reviewed.log`.
Retained independent reproduction commands (already PASS; do not routinely rerun):

```powershell
wsl -d Ubuntu-22.04 --cd /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa -- /usr/bin/python3 -B scripts/research-current-image4-bnch.py --kernel out/mix-n-match-20261110/audit-final/new/kernel.macho --kernel-sha256 fb1e796d7357b3e7ff7027bb94377d1cd38eae7283a6c72a7460914a200a0fbd --adt out/mix-n-match-20261110/audit-final/new/kernel.macho.adt --adt-sha256 9172e0ccd2efe250bcba05ce1e1884a5bb19a9c7d6a86527aaa35c36e5de453b --output out/image4-bnch-offline-20261110/verifier-reviewed-matrix.json
wsl -d Ubuntu-22.04 --cd /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa -- /usr/bin/python3 -B scripts/test-current-image4-bnch-evidence.py --matrix out/image4-bnch-offline-20261110/verifier-reviewed-matrix.json --kernel out/mix-n-match-20261110/audit-final/new/kernel.macho --adt out/mix-n-match-20261110/audit-final/new/kernel.macho.adt --output out/image4-bnch-offline-20261110/verifier-reviewed-robustness.json
git diff --check
git check-ignore out/image4-bnch-offline-20261110/matrix-reviewed.json
```

Actual revised robustness run used the source test entry above with
`--matrix .../matrix-reviewed.json --output .../robustness-reviewed.json`; exit
**0**, **26 fixture evidence robustness checks**, log
`out/image4-bnch-offline-20261110/robustness-reviewed.log`. It requires
the exact four-case set, current harness/dependency hashes and input pins before
checking outcomes. Targeted negative tests reject empty/missing/extra cases,
wrong/missing source provenance, incorrect reader/initializer lengths for each
case, wrong panic format/arguments and empty coverage. Retained checks reject
unsupported pins, wrong content/count and truncated ADT, verify BNCH-only
mutation, compile both entrypoints, and test CLI refusal to overwrite evidence.
These are **fixture evidence robustness checks, not donor authentication
negatives**; hash matching binds files but is not an attestation of execution.
The previous eight-check ignored driver is obsolete; no reproduction depends
on it. Both revised entrypoints received independent verifier PASS for the
four-case matrix and 26 checks (parent-reported); no further rerun requested.
Revised `git diff --check` and both output `git check-ignore` checks exited **0**.

Earlier exploratory output stopped conservatively at spin initialization;
`matrix-complete.json` superseded it after actual instructions continued safely;
`matrix-reviewed.json` now supersedes both with the stronger assertions.
An initial binding assertion incorrectly named that import `_lck_mtx_init`;
the actual current GOT/symbol identified `_lck_spin_init`, corrected before
the final run. No input image was changed. The first inline robustness-driver
attempt exited 1 without producing evidence; the retained ignored driver above
subsequently ran successfully. Earlier implementer runs were self-checked;
the final BNCH revision subsequently received independent verifier PASS.

Reviewer should inspect entry provenance, imported boundary definitions, PC
coverage semantics and the explicit consumer/authentication gap. No build or
device command belongs in verification. Final integration/acceptance is the
parent's responsibility. BNCH static review accepts only the constructed-state
scope: missing errno 2/panic, zero/48 return, 49 errno 84/panic. Nonce and
authentication are NOT REACHED. The consumer increment independently passed
its own static review and verifier, as recorded below (parent-reported).

## Bounded real consumer manifest-parse negative (new increment)

`scripts/research-current-image4-consumer-parse.py` uses the same pinned kernel
and file-backed/otherwise-zero emulator mapping described above, with synthetic
stack/heap/buffers. Unlike the BNCH fixture it does not need or invoke SecureDT,
synthetic IORegistry/OSData or the runtime initializer. This early parse path
does not establish real runtime initialization or hardware state.

Interface bindings (all checked against current image/symbols):

- Real Image4 interface `0xfffffff005cb1578`, version **18**; +0x218 is
  `runtime_execute_object=0xfffffff0046e4d88`, +0x198 is PMAP_CS
  `0xfffffff005cad070`, +0x208 is supplemental-root spec `0xfffffff005cadca0`,
  with its actual **apin** tag.
- `_img4if=0xfffffff0071aa1d8` starts NULL in this mapped initial state. Execute
  donor registration instructions `0xfffffff0046f1834–183c`: ADRP/ADD load the
  real table; BL enters actual import thunk `0xfffffff0046f9ea8`, whose GOT
  `0xfffffff005caba18` binds `_img4_interface_register=0xfffffff0078950d0`.
  The actual register instruction at `0xfffffff0078950dc` writes the slot once.
  No fixture write replaces the table/slot or skips registration.
- `_xnu_image4_execute_object=0xfffffff00771c1a8` is called with X0=index **1**,
  X1=payload descriptor, X2=non-NULL manifest descriptor. The actual wrapper
  dispatches X0=PMAP_CS, X1=supplemental spec, X2/X3=the descriptors. This is not
  invalid-index errno 2, nor an index-3/lpol experiment.

Payload input is the existing **original IM4P**, not the `.bundle`:
`D:/Code/PortingiOS/UniXNU/out/ipsw/20H392/087-86698-044.dmg.trustcache`,
66289 bytes, SHA256
`63e01c03b31e1532a5581a24865490673f0b5c297b0199fe0095637c6100ef4b`.
It has trst type and is **not an apin positive**. No original was copied into
source or a new artifact. Kernel/payload paths and expected hashes are CLI
parameters; unsupported pins fail. The manifest is the script's fixed,
self-authored malformed bytes `nuwa-offline-malformed-im4m\n` (28 bytes), not
an Apple component; its hex/hash are recorded in ignored evidence.

Real emulated buffers: payload pointer `0x2000000`, length 66289; manifest
pointer `0x2020000`, length 28. Descriptors `0x2021000` and `0x2021020` each
have 32-byte layout version0 at +0, pointer +8, true length +16, NULL deallocator
+24. Their bytes and both input byte arrays remain unchanged after the call.
SP=`0xf08000`; LR=`0xf00000` is only an unexecuted host return marker, not a
fabricated callback or a substituted function.

### Observed result and boundaries

Final evidence `out/image4-bnch-offline-20261110/consumer-parse-final.json`
contains registration PCs/slot writes, full consumer PCs, donor PCs, every
logging stub, and original parser/mapper/wrapper observations:

| Actual instruction boundary | Observed value |
| --- | --- |
| `0xfffffff0046e4fb8–4fc0` loads/calls manifest parser | pointer `0x2020000`, length 28 |
| parser returns at `0xfffffff0046e4fc4` | raw parser result **3** |
| native error mapper entry `0xfffffff0046f3160` | X0 **3** |
| mapper returns at `0xfffffff0046e4fd0` | X0 **92** |
| donor returns to wrapper `0xfffffff00771c1fc` | X0 **92** |
| XNU printf entry `0xfffffff007292e10` | saved X19 **92**, unchanged by stub |
| original wrapper returns to host marker `0xf00000` | W0 errno **92** |

Errno was observed, not preselected or synthesized. Coverage: 11 registration
PCs, 374 executed donor consumer PCs, 436 visited consumer PCs including logs.
Only three log calls were stubbed: PMAP_CS log `0xfffffff0046e9fa8` twice, and
the bound XNU printf once. Pure log stubs return only a logging result and leave
X19 intact; original instructions restore the error into X0. Native parser,
error mapper, comparisons, digests, signatures and security returns are not
hooked. There were no invalid-memory events. Normal PMAP installation return
45 is neither exercised nor changed to zero or called a signature failure.

These points are guarded stops if reached, and actually **NOT REACHED**:
firmware construction `0xfffffff0046e5224`, firmware execute
`0xfffffff0046e5268`, internal authentication callback `0xfffffff0046e5288`,
PMAP install `0xfffffff0046ea69c`. Nonce comparison/authentication are also
**NOT REACHED**, callback NULL/uninvoked. No no-manifest firmware-execute call
was made. An unexpected guarded state boundary produces BLOCKED/exit 2, not
success. The current hard boundary is malformed manifest parsing; proceeding
requires an appropriate apin payload and signed manifest/state contract, not
fabrication of a security result. This early parse negative does **not** prove
nonce closure, bad-signature rejection, authentication or device release.

### Incremental self-check and verifier command

Same Windows/WSL cwd and interpreter as above. Actual new script execution
exited **0**, log `out/image4-bnch-offline-20261110/consumer-parse-final.log`.
Assertions cover exact bindings/registration once, real dispatch/parse ABI,
nonzero parser result through native mapper and wrapper, preserved saved errno,
unchanged input bytes/descriptors and all unreached guarded boundaries. The
additional syntax/report-provenance/result/coverage self-check exited **0**,
log `out/image4-bnch-offline-20261110/consumer-parse-selfcheck.log`. The
first development run failed at the slot-write guard because Unicorn supplied
a signed 64-bit hook value; normalizing that value to uint64 fixed the guard,
without touching register behavior or input image bytes.

Retained consumer-increment reproduction command; independent verifier PASS
and static review PASS are parent-reported. Review required no source changes;
do not repeat this or the already-PASS BNCH matrix/26 checks for integration:

```powershell
wsl -d Ubuntu-22.04 --cd /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa -- /usr/bin/python3 -B scripts/research-current-image4-consumer-parse.py --kernel out/mix-n-match-20261110/audit-final/new/kernel.macho --kernel-sha256 fb1e796d7357b3e7ff7027bb94377d1cd38eae7283a6c72a7460914a200a0fbd --payload /mnt/d/Code/PortingiOS/UniXNU/out/ipsw/20H392/087-86698-044.dmg.trustcache --payload-sha256 63e01c03b31e1532a5581a24865490673f0b5c297b0199fe0095637c6100ef4b --output out/image4-bnch-offline-20261110/verifier-consumer-parse.json
git diff --check
git check-ignore out/image4-bnch-offline-20261110/consumer-parse-final.json
```

Independent evidence confirms registration once/version18, index1/apin dispatch,
native malformed-manifest parser 3 -> mapper 92 -> wrapper actual 92, with
only three pure-log stubs. Firmware construction/execute/auth callback/PMAP
install, nonce and authentication remain NOT REACHED; trst is not an apin
positive and no signed positive exists. No acceptance/device release follows.

Next local action: establish a parseable manifest, matching apin payload and
real-state preconditions; if unavailable, record that interface/input boundary.
Do not guess values, substitute security results or claim authentication PASS.
No input image, firmware or payload was modified; integration acceptance
remains with parent. Public material remains read-only, no external messages.
