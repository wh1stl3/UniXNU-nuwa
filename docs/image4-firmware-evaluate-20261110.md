# Native generic firmware evaluation and digest-helper increment (2026-11-10)

**Bounded Data-ledger independent mechanical execution and schema verification
completed (parent-reported); static review NOT completed because the service
returned `cyber_policy`. Research code is not integrated.**
Digest-helper increment has static review PASS and independent verifier PASS
(parent-reported); authentication was not established.
The previous NULL-descriptor boundary and corrected exit propagation have
independently passed (parent-reported). Their evidence remains unchanged below.
This is a bounded PMAP_CS generic firmware experiment, not an XNU object install,
trusted positive, nonce closure or device-release candidate. No device commands,
input-image writes, payload/firmware/kernel builds, external writes, commit or
push. Previously PASS BNCH/consumer fixtures were not rerun or modified.

## Inputs, contract and self-authored DER

New source: `scripts/research-current-image4-firmware-evaluate.py`.
Kernel SHA256 remains
`fb1e796d7357b3e7ff7027bb94377d1cd38eae7283a6c72a7460914a200a0fbd`
(55357440 bytes). ADT SHA256 remains
`9172e0ccd2efe250bcba05ce1e1884a5bb19a9c7d6a86527aaa35c36e5de453b`.
Read-only original payload:
`D:/Code/PortingiOS/UniXNU/out/ipsw/20H392/087-86698-044.dmg.trustcache`,
66289-byte IM4P, **trst**, version string `1`, 66264-byte inner payload.
Its tag was not changed to apin. SHA256
`63e01c03b31e1532a5581a24865490673f0b5c297b0199fe0095637c6100ef4b`;
whole IM4P SHA384
`6aa93bf357fd7a96470428b72cd736062688cff7dbc5683ce7ef542426bd1348a43fbbdf55c8907af17dac02e74b8b89`.
Paths/hashes are explicit CLI inputs; unsupported pins fail.

Public header read-only reference:
<https://raw.githubusercontent.com/apple-oss-distributions/xnu/xnu-8796.141.3/EXTERNAL_HEADERS/img4/firmware.h>.
It defines init_from_buff, six-argument void init, void attach, and
`errno_t img4_firmware_evaluate(fw, chip, nullable_nonce)`. Evaluate requires an
attached manifest; nullable nonce is conditional on the environment, not proof
that this constructed chip environment supports nonce-free authentication.

Locally generated, **untrusted/self-authored** DER structure:

```text
SEQUENCE {
  IA5 IM4M, INTEGER 0,
  SET { PRIVATE MANB { SEQUENCE { IA5 MANB, SET {
    PRIVATE MANP { SEQUENCE { IA5 MANP, SET {} } },
    PRIVATE trst { SEQUENCE { IA5 trst, SET {
      PRIVATE DGST { SEQUENCE { IA5 DGST, OCTET whole-IM4P-SHA384 } }
    } } }
  } } } },
  OCTET 256 zero bytes (deliberately invalid signature),
  SEQUENCE { locally self-signed X509 certificate }
}
```

DER length encoding and SET ordering are constructed in our code. Empty MANP
is explicitly not guessed board identity. OpenSSL 3.0.2 generates RSA-2048,
SHA384, one-day self-signed certificate, CN `nuwa-offline-untrusted-negative`,
CA:TRUE. No trust root is installed or accepted. Key, cert and manifest stay in
ignored output; source contains none of those products or Apple instructions.
Python/OpenSSL acceptance alone is not donor parsing evidence: the native
payload, manifest and context return observations below supply that distinction.

## Original constructed state and real interface calls (pre-helper history)

Same file-segment bytes plus otherwise-zero mapped memory, synthetic stack and
allowed ADT-backed IORegistry/OSData boundaries as the previously reviewed
fixture. This is not a real boot snapshot or hardware measurement. The exact
ADT is changed **only in emulator input** to supply the already-researched
48-byte experimental CSPRNG session BNCH; it is not a hardware/donor nonce or
persisted candidate. Original SecureDT setup and initializer run continuously
in the same emulator before evaluation. No saved runtime snapshot, security
level, provider pointer or cache state is injected. This does not prove that
the full runtime or cryptographic subsystem has initialized.

Original donor registration site `0xfffffff0046f1834–183c` calls the original
thunk and `_img4_interface_register` once, writing the initially NULL `_img4if`
slot through the original register instruction, not a fixture slot write.
Table `0xfffffff005cb1578` version 18 bindings checked:

| Offset | Native target |
| --- | --- |
| +0x130 init_from_buff | `0xfffffff0046e6ad4` |
| +0x138 init | `0xfffffff0046e62f0` |
| +0x140 attach | `0xfffffff0046e6d90` |
| +0x1c0 evaluate | `0xfffffff0046e7214` |
| +0x198 PMAP_CS | `0xfffffff005cad070` |
| +0x100 personalized chip | `0xfffffff0046f0f30` |

Native chip selector returned `0xfffffff005cae660` in this constructed state.
Firmware storage is `0x3000000`, size **0x500**. Execution context at
`0x3001000` is version **1**, callback/context **NULL**, evaluate-only.
Payload/manifest descriptors at `0x3001100`/`0x3001120` use version0,
real pointer/length, NULL deallocator. Init passes X0=firmware, X1=PMAP_CS,
X2=execution context, X3=`trst`, X4=payload descriptor, X5=**flags0**.
Attach passes a non-NULL manifest descriptor. Evaluate passes firmware,
the native chip, **nonce NULL**. Void init/attach X0 values are recorded but
never interpreted as errno. No void firmware execute is invoked.

Modeled setup boundaries are exactly the reused registry/property/release,
OSData length/bytes, safeMetaCast and Darwin logging primitives. During
**evaluate**, only bound PMAP_CS log `0xfffffff0046e9fa8` is stubbed.
No parser, digest, certificate, signature, comparison, nonce result or security
return is replaced. Synchronization acquisition, panic, execute/install and
the observed missing-state boundary are stops, not success stubs.

## Preserved pre-helper evidence: BLOCKED, not signature rejection

Final local report:
`out/image4-firmware-evaluate-20261110/final/report.json`.
It records all per-phase PCs, donor instruction coverage excluding stubs/stopped
instructions, call arguments/returns, each stub, registration write and observed
native boundaries. Evaluate visited 1532 PCs, executing 1460 donor PCs.
Native schema parser `0xfffffff0046f3abc` is present in coverage.

| Boundary | Native observation |
| --- | --- |
| payload parse return `0xfffffff0046e76a8` | **0** |
| manifest parse return `0xfffffff0046e7740` | **0** |
| context return `0xfffffff0046e77b8` | **0** |
| verifier call `0xfffffff0046e6a38` → `0xfffffff0046f6824` | reached with trst tag |
| native digest call `0xfffffff0046f6908` → `0xfffffff0046f85e0` | reached, no result stub |
| native SHA384 descriptor-cache load `0xfffffff0046f8620` | slot **`0xfffffff005cb06d8` contains NULL** |
| **stop `0xfffffff0046f8624`** | X0=0, before native conditional NULL branch |

Final status **BLOCKED**, process exit **2**. Evaluate has **not returned**;
its errno is **NULL/unavailable**, not zero or an invented error. No invalid
memory access occurred. This is the first precise missing native digest-descriptor
state in this constructed initialization, not evidence of broken device state.
No slot or crypto implementation pointer was filled to continue.

Certificate call/entry `0xfffffff0046f6968`/`0xfffffff0046f7cf8` and signature
call/entry `0xfffffff0046f69bc`/`0xfffffff0046f6f10` are **NOT REACHED**;
verifier and digest callbacks have not returned at the stopped final run.
Actual chip-table certificate/signature pointers at `0xfffffff005cb48f0` +8/+16
are bound and untouched. No certificate-chain rejection or signature rejection
is claimed. Nonce closure, payload digest comparison, authenticated execution
and PMAP installation are not established. There is no trusted positive.

An initial diagnostic run (`run1/report.json`) allowed the native NULL branch
to return through the verifier and evaluate, observing errno **80**. It did not
reach certificate/signature callbacks either. Coverage localized the earlier
digest-descriptor NULL check; the final instrumented run now stops at that precise
state boundary. **80 is not described as signature or nontrusted-chain rejection.**
No manifest fields were iteratively guessed or security result replaced.
The old report's `method_slot`/`method_pointer` labels were imprecise: this is
a SHA384 **digest descriptor cache**, not a directly callable function pointer.

The next bounded work at that checkpoint was to establish the legitimate initializer/provenance for
the native SHA384 descriptor-cache slot `0xfffffff005cb06d8` before further evaluation. This
deliverable does not authorize patching that slot, inventing runtime state or
expanding into kernel/cryptographic-subsystem emulation. Parent review decides
any next scope; BNCH device gate and explicit device authorization remain intact.

## Actual commands and independent incremental rerun

Windows cwd `D:/Code/PortingiOS/nuwa/UniXNU-nuwa`; WSL cwd
`/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa`, Ubuntu-22.04 `/usr/bin/python3 -B`,
Unicorn 2.1.4 / Capstone 5.0.7. No installation or network download beyond the
read-only header fetch. Script records exact OpenSSL argv and exit codes;
both certificate commands exited **0**. Final script command below used
`--work out/image4-firmware-evaluate-20261110/final` and exited **2/BLOCKED**,
log `out/image4-firmware-evaluate-20261110/final-run.log`.

Necessary additional self-check exited **0**, log
`out/image4-firmware-evaluate-20261110/selfcheck.log`: syntax compile without
pyc, report/source/dependency hashes, registration once, three native return0
observations, exact NULL-descriptor stop with no errno, no cert/signature calls,
no invalid memory. OpenSSL `asn1parse -inform DER -in
out/image4-firmware-evaluate-20261110/final/self-authored.im4m -noout` also
exited **0**; this is only DER syntax corroboration, not authentication.

Historical pre-helper reproduction only; already independently checked, **do
not repeat it for the helper increment**. These older commands apply only to
the preserved pre-helper script: substitute
`.cache/image4-firmware-evaluate-before-sha384-helper.py` for
`scripts/research-current-image4-firmware-evaluate.py` below if a historical
repeat is ever needed. Run the
following as a **standalone PowerShell invocation**: it deliberately propagates
the native status with `exit`, so the shell process must exit **2**. Do not
append the validation commands in that same invocation after `exit`.

```powershell
wsl -d Ubuntu-22.04 --cd /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa -- /usr/bin/python3 -B scripts/research-current-image4-firmware-evaluate.py --kernel out/mix-n-match-20261110/audit-final/new/kernel.macho --kernel-sha256 fb1e796d7357b3e7ff7027bb94377d1cd38eae7283a6c72a7460914a200a0fbd --payload /mnt/d/Code/PortingiOS/UniXNU/out/ipsw/20H392/087-86698-044.dmg.trustcache --payload-sha256 63e01c03b31e1532a5581a24865490673f0b5c297b0199fe0095637c6100ef4b --adt out/mix-n-match-20261110/audit-final/new/kernel.macho.adt --adt-sha256 9172e0ccd2efe250bcba05ce1e1884a5bb19a9c7d6a86527aaa35c36e5de453b --work out/image4-firmware-evaluate-20261110/verifier-exitcode; $rc=$LASTEXITCODE; exit $rc
```

Then validate the report in a **separate invocation**, expected exit **0**:

```powershell
wsl -d Ubuntu-22.04 --cd /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa -- /usr/bin/python3 -B -c 'import json; from pathlib import Path; r=json.loads(Path("out/image4-firmware-evaluate-20261110/verifier-exitcode/report.json").read_text()); c=r["result"]; assert c["status"]=="BLOCKED" and c["errno"] is None; assert c["terminal_pc"]=="0xfffffff0046f8624" and c["blocked"]["method_slot"]=="0xfffffff005cb06d8"; assert all(c["checks"][n]==0 for n in ("payload_parse_return","manifest_parse_return","context_return")); assert all(c["checks"][n]=="NOT REACHED" for n in ("certificate_entry","signature_entry")); assert len(c["slot_writes"])==1 and not c["calls"][-1]["returned"]'; $rc=$LASTEXITCODE; exit $rc
```

Separate repository-only checks:

```powershell
git diff --check
git check-ignore out/image4-firmware-evaluate-20261110/final/report.json out/image4-firmware-evaluate-20261110/final/self-authored.im4m
```

Fresh self-signed certificate/key/manifest hashes vary across runs. Compare
bound inputs, native observations and stop condition, not generated DER hash
equality. This historical checkpoint was initially self-checked; later
independent mechanical results are recorded below, not full static acceptance.
Only this script and this new evidence document were edited; unrelated Android
state documents, old fixtures and all input/boot images remain untouched.

## Preserved exit-code propagation correction (independently checked)

Parent verifier reproduced the same boundary in `verifier/report.json`, but
reported outer process exit 1. That report's invocation/source hash was checked:
harness SHA256 remains
`30c6d53a29d0c52840b3ea7a68ed95213142e2d0f2f2f5ae634ba8c7761f5fc2`.
It has three native return0 observations, NULL digest-descriptor state, cert/sign
NOT REACHED and no evaluate errno. No verifier stdout/stderr or complete outer
PowerShell command was present alongside that report; its historical wrapper
cannot be reconstructed from the report argv alone.

Controlled process-level evidence, before changing these commands:

- `out/image4-firmware-evaluate-20261110/exitcode-audit/audit.json`: a Linux
  Python parent used `subprocess.run` with the recorded verifier argv (only a
  fresh work directory substituted). **Actual research-script returncode=2**,
  captured stdout complete, stderr empty/no traceback, source hash unchanged.
  The same BLOCKED state was checked. Thus this run did not fail after writing
  its report and the native Python status was not 1.
- `exitcode-audit/pwsh-propagation.json`: nested `pwsh -NoProfile -NonInteractive
  -Command` with `wsl ... python3 -B -c "raise SystemExit(2)"` exits **1**;
  the same command followed immediately by `; exit $LASTEXITCODE` exits **2**.
  This reproduces the standalone documented command's PowerShell normalization
  of nonzero native status, rather than WSL losing the native status. It is a
  demonstrated mechanism matching the discrepancy, not a claim that the missing
  original verifier wrapper was recovered.

The fix is explicit capture/propagation and separate validation invocations,
not changing BLOCKED to success or changing Python's exit code. The exact
corrected standalone command was self-checked with fresh work directory
`exitcode-document` (same inputs/flags), outer process **2**, native report
unchanged semantically; its separate validation exited **0**. Evidence:
`exitcode-document/report.json`, `exitcode-document.log`. No research-script or
digest-slot edit was required. Parent subsequently reported independent PASS:
corrected standalone outer exit2, separate validation0, exact old NULL boundary.
Do not repeat that historical job or old matrices for the new helper increment.

## Preserved descriptor-helper increment (review/verifier PASS)

Reviewer PASS WITH CONDITIONS bound the omitted legitimate prerequisite:
startup `0xfffffff0046f1418` calls `0xfffffff0046ef814`, followed at
`0xfffffff0046f141c` by the original runtime initializer. We now execute, in
one emulator instance: SecureDT setup → **helper once** → original PMAP init →
original interface registration → native chip selection → firmware storage/init/
attach/evaluate. No crypto configuration, runtime/provider table, secure-boot
level or selector return is altered; `register_crypto_functions` is not called.

Before editing, the exact previous script was preserved as ignored
`.cache/image4-firmware-evaluate-before-sha384-helper.py`, SHA256
`30c6d53a29d0c52840b3ea7a68ed95213142e2d0f2f2f5ae634ba8c7761f5fc2`.
Its original ROOT calculation remains valid there. Old `final`, `verifier`,
`verifier-exitcode`, exit-code audits and reports were not overwritten.

The helper has no arguments, SP=`0xf08000` (16-byte aligned), LR=unexecuted
host marker, budget 1000. Both descriptor-cache slots are asserted NULL before
the call. A write hook **observes/restricts**, never supplies, the native writes:

| Original write PC | Cache slot | Original selector result |
| --- | --- | --- |
| `0xfffffff0046ef824` | `0xfffffff005cb06d0` | `0xfffffff005ca82b0` |
| `0xfffffff0046ef830` | `0xfffffff005cb06d8` | `0xfffffff005ca6f00` |

Helper coverage is 22 PCs, including native import thunks and both original
three-instruction corecrypto selectors. The exact two writes, final values,
one call and restored SP are required. Original chains are
`046f9e54 → GOT05cab9d8 → 046cf6ec → desc05ca82b0` and
`046f9e60 → GOT05cab9e0 → 046d76e8 → desc05ca6f00` (all `fffffff0` prefix).
The second cached object is a **SHA384 digest descriptor**, not a direct
function pointer: output48/state64/block128, OID `0609608648016503040202`,
compress `0xfffffff0046a8c90`, final `0xfffffff0046d3d44`. These file-backed
fields and original call edges are checked, not patched.

### Actual result, separated by native stage

Only one new emulation run was made:
`out/image4-firmware-evaluate-20261110/helper1/report.json`.
Inputs/flags/nonce=NULL, self-authored DER construction and constructed-state
qualification remain as above. New certificate/manifest hashes vary naturally;
no alternative manifest fields or security results were tried.

| Native stage | Actual observation |
| --- | --- |
| payload/manifest/context return PCs `046e76a8/7740/77b8` | all **0** |
| digest callback `046f85e0`, return `046f690c` | **0**, completed |
| original SHA384 compress/final | both executed, present in full PC coverage |
| certificate call `046f6968` | actual X8 target **`0xfffffff0046f7cf8`** |
| certificate callback return `046f696c` | raw W0 **`0xffffffff`** (signed32 -1) |
| verifier return `046e6a3c` | raw W0 **`0xffffffff`** |
| evaluate native return to host marker | errno **80** |
| signature call/entry/return | **NOT REACHED** |

The first native digest callback reads the constructed manifest at `0x3030000`,
1220 bytes in this run, and produces 48 bytes. The fixture reads that input and
computes host SHA384 for **comparison only**, then reads the native output after
native return0; the hashes match. Nothing is filled into the native output.
This is not a native verification of the payload's DGST property: certificate
failure prevents the subsequent signature/object stages from executing.

Evaluate coverage: 3888 visited PCs, with 2098 in the inherited Image4
`donor_pcs` window. That window excludes corecrypto; **all_pcs** includes the
original SHA384 compress/final. The helper's full PCs, exact cache writes,
digest input/output/host comparison and every callback boundary are in JSON.
During evaluate the only stub remains the bound pure PMAP log. Synthetic
registry/OSData boundaries are confined to existing setup/native-chip selection;
no digest, certificate, signature or security return is stubbed. No invalid
memory events or new unmet-state boundary occurred.

This is a **certificate-callback-stage nonzero result**, not a signature
rejection or proof that an Apple trust-anchor comparison was reached. The
internal reason for the certificate callback's -1 is not resolved here; it
must not be relabeled simply as a nontrusted-chain rejection. Generic evaluate
is not XNU object installation. No firmware execute, authenticated callback,
PMAP install, nonce closure, trusted positive or device release is established.
The script exits **0** for recording this nonzero negative result, not because
authentication succeeded. Unexpected evaluate0 still exits2 for investigation;
new unfulfilled state boundaries remain BLOCKED/exit2.

### Necessary self-check and independent incremental command

Same cwd/interpreter as above. Single new execution exit **0**, log
`out/image4-firmware-evaluate-20261110/helper1-run.log`. Additional read-only
syntax/source/dependency/report checks exit **0**, log `helper1-selfcheck.log`:
exact helper write PCs/descriptors and one call; native SHA3840 with read-only
host match and compress/final coverage; native certificate/verifier rawffffffff;
evaluate80, signature NOT REACHED; no invalid memory; registration once; only
pure evaluate logs; old fixed snapshot hash intact. No old matrix rerun.

Historical helper-only reproduction: already independently PASS; do not repeat
for the Issuer increment. These commands require replacing the script path with
`.cache/image4-firmware-evaluate-before-issuer-name.py` (SHA256
`5d65959447a6cfc81c9cc0405b4c1d9c5c348373e07598d23b4d4dbb4b655120`).
That preserved version has no Issuer input arguments. Its expected outer
exit **0**, then separately validate the result. Explicit native-status
propagation is retained (run each block in its own shell invocation):

```powershell
wsl -d Ubuntu-22.04 --cd /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa -- /usr/bin/python3 -B scripts/research-current-image4-firmware-evaluate.py --kernel out/mix-n-match-20261110/audit-final/new/kernel.macho --kernel-sha256 fb1e796d7357b3e7ff7027bb94377d1cd38eae7283a6c72a7460914a200a0fbd --payload /mnt/d/Code/PortingiOS/UniXNU/out/ipsw/20H392/087-86698-044.dmg.trustcache --payload-sha256 63e01c03b31e1532a5581a24865490673f0b5c297b0199fe0095637c6100ef4b --adt out/mix-n-match-20261110/audit-final/new/kernel.macho.adt --adt-sha256 9172e0ccd2efe250bcba05ce1e1884a5bb19a9c7d6a86527aaa35c36e5de453b --work out/image4-firmware-evaluate-20261110/verifier-helper; $rc=$LASTEXITCODE; exit $rc
```

```powershell
wsl -d Ubuntu-22.04 --cd /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa -- /usr/bin/python3 -B -c 'import json; from pathlib import Path; r=json.loads(Path("out/image4-firmware-evaluate-20261110/verifier-helper/report.json").read_text()); c=r["result"]; assert c["status"]=="self-checked" and c["errno"]==80 and c["blocked"] is None; assert len(c["helper_writes"])==2; assert [w["descriptor"] for w in c["helper_writes"]]==["0xfffffff005ca82b0","0xfffffff005ca6f00"]; assert all(c["checks"][n]==0 for n in ("payload_parse_return","manifest_parse_return","context_return","native_digest_return")); assert c["native_digest_calls"][0]["host_sha384_equal"]; assert c["checks"]["certificate_return"]==0xffffffff and c["checks"]["verifier_return"]==0xffffffff; assert c["checks"]["signature_entry"]=="NOT REACHED" and c["calls"][-1]["returned"]'; $rc=$LASTEXITCODE; exit $rc
```

Do not rerun the pre-helper jobs or modify their stored reports. The next
research question, if separately scoped, is the exact native certificate
callback rejection path, not bypassing it. This helper increment received
independent static-review/verifier **PASS** (parent-reported). This is not
authentication PASS. No config/pointer
patch, image build, device operation, unrelated-document edit, commit or push.

## Preserved Issuer-Name input increment: preemption-state boundary

Reviewer located helper1's certificate -1 at the original Name length check:
native root Subject content75 versus our own Issuer content42, before memcmp
or certificate-link verification. This was a Name connection failure, **not
cryptographic rejection**. The one new input change is the own certificate's
Issuer Name. The retained key and all other TBSCertificate fields, public key,
serial, validity, extensions and signature AlgorithmIdentifier remain identical.
DER lengths and the certificate signature are necessarily recomputed, using
the **same own key**, not Apple's key.

Baseline local certificate SHA256:
`5b6dbcbe8868cc61f504fbdddb5684dfca7323d86682b4fd1c36cf4a09681015`;
retained own key SHA256:
`39c75ab3d5c60185cdc3e929a2fa5731019b7bbd4300732773af586d3ae23b27`.
They are explicit pinned CLI inputs, read-only from `helper1/`. No new key,
trust anchor or certificate attributes were guessed. The native root certificate
is read from the same pinned kernel at `0xfffffff003e1aa30`, length1374 from
`0xfffffff003e1af90`; its Subject Name is parsed as DER, not embedded in source.
The native TBS schema reference remains `0xfffffff003e1d6c8`. Only the required
Name field is retained in ignored output, not a new whole Apple certificate
copy. The resulting own-key certificate remains **explicitly untrusted**:
Issuer-name equality confers no Apple signature or trust. Do not publish any
generated certificate, manifest, key or derived Apple Name artifact.

Source asserts every TBS field except Issuer is byte-identical, the outer
algorithm is unchanged and the retained own key's public DER equals the baseline
SPKI. Local OpenSSL re-signs the modified TBS with the own key. A read-only host
verification of that signature under the own public key exits0; it is only a
construction check, **not native chain/signature acceptance**. PMAP_CS, helper,
hash bindings, trst payload/tag, flags0, nullable nonce and existing setup remain
unchanged. No verifier, comparator, digest, signature or trust store is changed.

### Actual single run and exact boundary

`out/image4-firmware-evaluate-20261110/issuer1/report.json`; process **exit2**,
status **BLOCKED**, evaluate **not returned**, errno **NULL/unavailable**.

| Original PC/stage | Actual observation |
| --- | --- |
| payload/manifest/context returns | all 0 |
| `0xfffffff0046f7a30/34` length CMP/branch | root Subject75, Issuer75; original branch permits continuation |
| Name pointers | root `0xfffffff003e1aac5`, own Issuer `0x30301bf` |
| `0xfffffff0046f7a48` original memcmp return | 0; no comparison result hook |
| `0xfffffff0046f7a6c` → `0xfffffff0046f7778` | certificate-link verification entered |
| actual X0/X1/X2 there | `0xf07b58`, `0xf07918`, `0xfffffff005cb48f0`; bounded pointed structures in JSON |
| native SHA384 callbacks | two return0, both read-only host matches (manifest1253 bytes, certificate TBS578 bytes) |
| **stop `0xfffffff0073e94e8`** | native `__disable_preemption` reads unmapped `0x1d0` (4 bytes) |

The exact bound native symbol is `__disable_preemption=0xfffffff0073e94e4`:
`MRS X8, TPIDR_EL1` followed at the stopped PC by `LDR W9,[X8,#0x1d0]`.
The observed address implies X8/current-thread base0 in this constructed state;
it is not a cryptographic rejection or a measured device defect. No synthetic
thread, TPIDR, preemption counter, lock success or allocator state was supplied
to bypass it. This is the next precise kernel-state prerequisite, and execution
stopped without extending the fixture into scheduler/kernel emulation.

`certificate_link_validation_return` at `046f7a70`, outer certificate callback
return and verifier/evaluate return are **NOT REACHED**. The shared native
signature-helper entry `0xfffffff0046f6f10` **was visited within certificate-link
verification**, but did not return. This must not be confused with the manifest
signature callsite `0xfffffff0046f69bc`, which is **NOT REACHED**. No signature
failure/success is available. Authentication, nonce closure, XNU object
installation, authenticated execution, PMAP install and device release remain
unestablished. All evaluate stubs are still pure bound PMAP logs.

### Self-check and incremental reproduction

Single run exit2 log `out/image4-firmware-evaluate-20261110/issuer1-run.log`.
Necessary read-only/host construction self-check exit0 log `issuer1-selfcheck.log`:
source hash/syntax, Issuer-only TBS change, retained key/SPKI and valid own-key
re-signature, actual native Name75/75 and memcmp0, two native digest0/host
matches, exact preemption-state stop, no returned evaluate errno. Old helper1,
verifier-helper, NULL-boundary and exit-code reports were not overwritten.

Historical Issuer-only reproduction below uses preserved source
`.cache/image4-firmware-evaluate-before-allocator-observe.py`, SHA256
`e3003181ad6dac31e275ad1fe03b221117f67e1008407909ab3af0850823f499`.
Substitute that path for the script path below to reproduce the old preemption
stop; do not rerun that job for the allocator-entry observation. Its expected
**exit2/BLOCKED**. Full argv/cwd and OpenSSL argv/exits are stored in JSON.

```powershell
wsl -d Ubuntu-22.04 --cd /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa -- /usr/bin/python3 -B scripts/research-current-image4-firmware-evaluate.py --kernel out/mix-n-match-20261110/audit-final/new/kernel.macho --kernel-sha256 fb1e796d7357b3e7ff7027bb94377d1cd38eae7283a6c72a7460914a200a0fbd --payload /mnt/d/Code/PortingiOS/UniXNU/out/ipsw/20H392/087-86698-044.dmg.trustcache --payload-sha256 63e01c03b31e1532a5581a24865490673f0b5c297b0199fe0095637c6100ef4b --adt out/mix-n-match-20261110/audit-final/new/kernel.macho.adt --adt-sha256 9172e0ccd2efe250bcba05ce1e1884a5bb19a9c7d6a86527aaa35c36e5de453b --certificate out/image4-firmware-evaluate-20261110/helper1/self-authored-cert.der --certificate-sha256 5b6dbcbe8868cc61f504fbdddb5684dfca7323d86682b4fd1c36cf4a09681015 --key out/image4-firmware-evaluate-20261110/helper1/self-authored-key.pem --key-sha256 39c75ab3d5c60185cdc3e929a2fa5731019b7bbd4300732773af586d3ae23b27 --work out/image4-firmware-evaluate-20261110/verifier-issuer; $rc=$LASTEXITCODE; exit $rc
```

In a separate shell invocation, expected validation exit0:

```powershell
wsl -d Ubuntu-22.04 --cd /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa -- /usr/bin/python3 -B -c 'import json; from pathlib import Path; c=json.loads(Path("out/image4-firmware-evaluate-20261110/verifier-issuer/report.json").read_text())["result"]; assert c["status"]=="BLOCKED" and c["errno"] is None and not c["calls"][-1]["returned"]; assert c["terminal_pc"]=="0xfffffff0073e94e8"; e=next(e for e in c["events"] if e["boundary"]=="issuer_name_length_compare"); assert e["root_subject_length"]==e["issuer_length"]==75; assert c["checks"]["issuer_name_memcmp_return"]==0; assert c["checks"]["certificate_link_validation_return"]=="NOT REACHED" and c["checks"]["signature_call"]=="NOT REACHED"; assert len(c["native_digest_calls"])==2 and all(d["native_return"]==0 and d["host_sha384_equal"] for d in c["native_digest_calls"])'; $rc=$LASTEXITCODE; exit $rc
```

This historical Issuer increment was subsequently independently rerun
(parent-reported); no authentication acceptance follows.
No old matrix rerun, field sweep, device action, image build, external write,
commit, trust-store edit or other state-document edit was performed.

## Preserved minimal allocator-entry observation

This increment only stops earlier at the **first instruction** of original
`_IOMallocData_external=0xfffffff0078a9e98`. It does not supply Data memory,
return an allocation result, enter zone allocation, change donor code or execute
the allocator's first instruction. The approved future Data-memory boundary is
not implemented in this round. Input pins and all generated certificate/manifest
hashes match issuer1 exactly; original parse/digest/Name execution is retained.

### Static expectation, explicitly separate from dynamic sampling

The pinned kernel's root RSA public DER at `0xfffffff003e1ab28`, length526,
has INTEGER content513 with leading0, leaving modulus512 bytes. Read-only DER
analysis therefore predicts `n=(512+7)>>3=64`, capacity `5*n+3=323` and request
`40*n+24=2584`. These are stored under
`binding.allocator_provenance.static_expectation`, **not copied into emulator
memory or used as runtime observations**. Native `046f6de4–6e18/6e38` executes
normally; the resulting context's first qword is read later at the stop.

### Actual dynamic values

New independent directory:
`out/image4-firmware-evaluate-20261110/allocator-observe1/report.json`.
Status **BLOCKED / observation complete**, outer process **exit2**. Evaluate
has **not returned** and its errno is **NULL/unavailable**, not authentication
failure. `result.allocation_observation` contains raw captures:

| Dynamic field | Actual value |
| --- | --- |
| PC, before first instruction | `0xfffffff0078a9e98`, true |
| X0 request / wrapper-saved X19 request | **2584 / 2584** |
| LR | `0xfffffff00469f86c` |
| SP | `0xf07020` |
| `[SP+0x18]`, saved workspace LR | `0xfffffff0046d45a4` |
| `[SP+8]`, saved caller X19 / pubkey ctx | `0xf070e0` |
| **read `[ctx]`**, native n | **64** |
| breadcrumb `0xfffffff0046d45a0` | X0=2584, X19=`0xf070e0`, `[X19]`=64 |

From the **sampled** n64, host integer arithmetic derives capacity323 and
request2584 and checks 64-bit overflow for `5*n+3`, `40*n+24` and `8*capacity`.
Actual X0 equals `40*n+24`, wrapper X19 equals X0, and both saved return addresses
match. Capacity323 here is a **derived check**, not a claim that a later native
workspace capacity field was already written. No n/request was pre-filled.

Provenance is a raw-image binding **and** dynamic source whitelist, not merely
matching an API address: original BL `0xfffffff00469f868` → original thunk
`0xfffffff0046d89a4/89a8/89ac` → GOT `0xfffffff005ca6888` → target
`0xfffffff0078a9e98`. The symbol, BL, thunk operands and actual GOT value are
validated; all source PCs were visited, LR is the BL return, and the saved
workspace return is consistent with the original caller. No return/pointer is
replaced. The stopped PC is visited but **not executed**; PC `078a9e9c` and the
old `__disable_preemption` fault PC are not visited. Invalid-memory list is empty.

Payload/manifest/context return0, Name75/75 and native memcmp0 remain observed.
The same two original SHA384 operations return0 with read-only host matches.
Certificate-link validation and its shared signature helper were entered but
have not returned. Manifest signature callsite, verifier/evaluate return,
authenticated execution and installation remain NOT REACHED. This is dynamic
allocation-request observation, **not authentication rejection or acceptance**.

### Necessary self-check and independent incremental rerun

Same cwd/interpreter as preceding sections. Single new execution exit2 log
`allocator-observe1-run.log`; new-field/source/dependency/input-hash/stop checks
exit0 log `allocator-observe1-selfcheck.log`. Checks require the exact six-field
check set (not vacuous iteration), raw request/n/stack values, breadcrumb/ctx
agreement, overflow/formula, complete thunk/GOT whitelist, no allocator next
instruction or old preemption fault, no invalid memory and no evaluate errno.
Both logs are under `out/image4-firmware-evaluate-20261110/`.

Historical observer command only: the original observation is retained and
re-exercised by each ledger case below; **do not rerun it as a separate job**.
The default `observe` mode remains available and never supplies memory. Its
directory, standalone shell expected **exit2**:

```powershell
wsl -d Ubuntu-22.04 --cd /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa -- /usr/bin/python3 -B scripts/research-current-image4-firmware-evaluate.py --kernel out/mix-n-match-20261110/audit-final/new/kernel.macho --kernel-sha256 fb1e796d7357b3e7ff7027bb94377d1cd38eae7283a6c72a7460914a200a0fbd --payload /mnt/d/Code/PortingiOS/UniXNU/out/ipsw/20H392/087-86698-044.dmg.trustcache --payload-sha256 63e01c03b31e1532a5581a24865490673f0b5c297b0199fe0095637c6100ef4b --adt out/mix-n-match-20261110/audit-final/new/kernel.macho.adt --adt-sha256 9172e0ccd2efe250bcba05ce1e1884a5bb19a9c7d6a86527aaa35c36e5de453b --certificate out/image4-firmware-evaluate-20261110/helper1/self-authored-cert.der --certificate-sha256 5b6dbcbe8868cc61f504fbdddb5684dfca7323d86682b4fd1c36cf4a09681015 --key out/image4-firmware-evaluate-20261110/helper1/self-authored-key.pem --key-sha256 39c75ab3d5c60185cdc3e929a2fa5731019b7bbd4300732773af586d3ae23b27 --work out/image4-firmware-evaluate-20261110/verifier-allocator-observe; $rc=$LASTEXITCODE; exit $rc
```

Separate validation shell, expected exit0:

```powershell
wsl -d Ubuntu-22.04 --cd /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa -- /usr/bin/python3 -B -c 'import hashlib,json; from pathlib import Path; r=json.loads(Path("out/image4-firmware-evaluate-20261110/verifier-allocator-observe/report.json").read_text()); assert r["harness_sha256"]==hashlib.sha256(Path("scripts/research-current-image4-firmware-evaluate.py").read_bytes()).hexdigest(); assert all(hashlib.sha256((Path("scripts")/n).read_bytes()).hexdigest()==v for n,v in r["dependencies"].items()); c=r["result"]; a=c["allocation_observation"]; assert c["status"]=="BLOCKED" and c["errno"] is None and not c["calls"][-1]["returned"] and c["blocked"]["observation_complete"]; assert c["terminal_pc"]=="0xfffffff0078a9e98" and a["before_first_instruction"]; assert a["request_x0"]==a["saved_request_x19"]==2584 and a["ctx_n"]==64; assert a["lr"]=="0xfffffff00469f86c" and a["workspace_lr_sp18"]=="0xfffffff0046d45a4"; assert len(a["checks"])==6 and all(a["checks"].values()) and not c["invalid_memory"]'; $rc=$LASTEXITCODE; exit $rc
```

No old matrix rerun, allocator simulation, new memory, zone/scheduler work,
donor patch, candidate build, device action, external write or commit. The
original observer self-check is historical; combined independent mechanical
ledger execution/schema results are recorded below. Static review remains open.

## Explicit bounded Data allocator modes (current increment)

Deep PASS WITH CONDITIONS permits a host Data-memory boundary for exactly the
observed request, not a generic heap, zone, scheduler or VM model. The script
adds explicit `--allocator-mode ledger` and `--allocator-mode oom`; default
`observe` still stops without providing memory. Original `allocator-observe1`
and all older reports remain intact. Pre-model source is preserved locally as
`.cache/image4-firmware-evaluate-before-data-ledger.py` (SHA256
`729a7bcfe2c2f8824c741af7fd52e529186cc24cf606a8e2efd7829f346a970e`).

### Model policy, not donor guarantees

- The only admitted allocation ABI is original `IOMallocData_external` at
  `0xfffffff0078a9e98`, X0=request → pointer/NULL. It is **not**
  `IOMalloc_internal(heap,size,flags)`. Admission requires the already sampled
  wrapper LR `0469f86c`, saved workspace LR `046d45a4`, complete thunk/GOT chain,
  real saved ctx and n64, request2584 and matching breadcrumb. One admitted
  attempt, one allocation maximum, per-request and total **2584-byte limits**.
  Any new source/size/count/purpose stops BLOCKED before supplying memory.
- The single host-private page is `0x4000000`, payload pointer `0x4000100`,
  **16-byte alignment is a fixture condition**, not a donor guarantee. Whole
  page starts nonzero poison `0xa5`; it is not pre-zeroed. Exact requested
  interval `[ptr,ptr+2584)` is the only accessible Data interval. Both adjacent
  pages stay unmapped; poisoned prefix/suffix include immediate canaries and
  all page padding. Guest read/write/fetch hooks reject padding/guard access,
  bounds violations, execution and UAF; writers and per-phase byte coverage are
  recorded. Host full-page checks catch corruption outside the exact request.
- Private ledger tracks pointer/exact original request/liveness and count.
  Overlap, double free, interior/foreign free, wrong size, UAF, incomplete native
  clear/coverage or canary damage are immediate RESOURCE_FAILURE/exit1. No
  resource condition is relaxed for a green result. Normal evaluation return
  requires closed Data/workspace lifetime; a new native state boundary retains
  any live allocation without inventing cleanup.
- Only new Data-region bytes, private bookkeeping and Data ABI return registers/
  PC are synthetic. Native crypto, certificate/signature/nonce comparisons,
  original panic/special branches and security returns are untouched. No
  preemption success is stubbed. Only the prior bound logs remain additionally
  modeled during evaluation.

### Supplied-memory run: first workspace closed, new request refused

Final evidence `out/image4-firmware-evaluate-20261110/ledger-final/report.json`,
outer **exit2/BLOCKED**, evaluate **not returned**, errno **NULL**. First dynamic
n64/request2584 and original source chain match `allocator-observe1`. The model
returns poisoned pointer `0x4000100` only at the admitted Data ABI.

Actual original steps, not fixture-filled workspace fields:

1. Wrapper `0469f874–87c` calls original `_bzero=0xfffffff00799f8c0` for 2584
   bytes. Entry reads all-poison memory; original writes cover **2584/2584**
   bytes and result is zero. No DCZVA or zeroizer hook supplies the result.
2. At `046d45d4`, original workspace is `[ptr,323,0,0469f8b4,0469f8f8,0469f934]`:
   native capacity323, used0 and native callbacks. They are only read/checked.
3. Original clear `046d45f0 → 0469f8f8 → 0469f920–930 → 046b6a70` reaches
   `_memset_s=0xfffffff00799ee60` with actual ABI `(ptr,2584,0,2584)`.
   Original clear writes cover **2584/2584** bytes; native status is recorded.
4. Original free path `046d45fc → 0469f934 → 0469f95c–964 → 0469f768 → ordinary
   0469f7d0–e0 → thunk046d8998/GOT05ca6880 → IOFreeData=0xfffffff0078a9ec0`
   reaches the bound void ABI with original ptr, original size2584, LR0469f968.
   The ledger records the **actual full zero content**, hash, size and intact
   guards **before** revoking page permissions. Host-after-free hygiene is
   separately marked `native:false`; it is not native zeroization evidence.
5. Original stores at `0469f968/96c` clear capacity/used/pointer; at `0469f970`
   native fields read `[0,0,0]`. The first fixture allocation is ledger-freed at
   the admitted ABI and the original workspace is closed; IOFreeData's kernel
   body is not emulated. Read/write monitor counts are 34592/33282; all stayed
   within the exact interval. No invalid memory or resource failure occurred.

Next native Data request is **5152 bytes**, same wrapper LR0469f86c but saved
caller return **046cf9ec**, not approved workspace LR046d45a4. This second
purpose is refused at `0xfffffff0078a9e98` before its allocator executes.
The new saved X19 is **not decoded as a pubkey ctx**: its n/formula fields are
NULL/not applicable. Two native requests were observed, but only one was
admitted; there is no second allocation. First workspace had already been
closed by original cleanup, so no forced free is needed at the new boundary.
The shared signature helper and certificate/link/verifier calls have not
returned. No authentication success or signature rejection is established.

### NULL first request: original internal OOM propagation

Final evidence `oom-final/report.json`, outer **exit0** for recording a native
negative result, evaluate native errno **80**. Same pinned inputs and same first
source/n64/request2584; the Data ABI returns NULL, without mapping any Data page.
Original `0469f870 → 0469f880 → 046d45d4 → 046d4604` executes. At `046d4608`,
actual W19=`0xfffffff3`, signed **internal -13**; at original return `046d4630`,
X0=`0xfffffff3`. This is **not POSIX errno13** and not a signature rejection.
The shared helper returns rawffffffff; certificate/link callback and verifier
return rawffffffff; evaluate returns80. Manifest signature callsite046f69bc
is NOT REACHED. There is **no successful allocation or free**, no bzero/clear
of modeled Data, and no live allocation. No safety result is filled by Python.

### Necessary model negatives and final self-check

`--ledger-self-test` actually passed **13 isolated model negatives**: overrun,
underrun, page-padding access, overlap, wrong free size, interior free, nonzero
free, double free, UAF, count budget, single-request limit, damaged canary and
missing native write coverage. These deliberately exercise model predicates
with isolated preparation; **none is a donor authentication negative**.

Final logs (same cwd/interpreter as above): `ledger-final-run.log` exit2,
`oom-final-run.log` exit0, `ledger-final-selftest.log` exit0,
`data-final-selfcheck.log` exit0. Both reports bind final source SHA256
`94d09c6bebd7367d3b3211eb54fbd7453756af5742d78a366b965d6a48c7e73c`, exact
dependency set/hashes and identical input hashes, including `allocator-observe1`.
Checks cover original zeroizer write coverage/full free content, lifecycle
closure, new-source refusal, and actual OOM -13 propagation without heap success.
Development `ledger1`/`oom1` are retained; the final sampler avoids interpreting
an unrelated caller's saved X19 as a pubkey ctx. No limit/source was broadened.

### One combined independent incremental check

Retained reproduction commands: independent verifier has executed the dynamic
sample/model cases and isolated tests; do not rerun for this records update.
The block below checks native exit codes immediately; its own exit0 means the
expected experiment outcomes were recorded, never authentication PASS. Use
fresh directories. Kernel/ADT/payload and baseline certificate/key remain local.

```powershell
$common=@('-d','Ubuntu-22.04','--cd','/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa','--','/usr/bin/python3','-B','scripts/research-current-image4-firmware-evaluate.py','--kernel','out/mix-n-match-20261110/audit-final/new/kernel.macho','--kernel-sha256','fb1e796d7357b3e7ff7027bb94377d1cd38eae7283a6c72a7460914a200a0fbd','--payload','/mnt/d/Code/PortingiOS/UniXNU/out/ipsw/20H392/087-86698-044.dmg.trustcache','--payload-sha256','63e01c03b31e1532a5581a24865490673f0b5c297b0199fe0095637c6100ef4b','--adt','out/mix-n-match-20261110/audit-final/new/kernel.macho.adt','--adt-sha256','9172e0ccd2efe250bcba05ce1e1884a5bb19a9c7d6a86527aaa35c36e5de453b','--certificate','out/image4-firmware-evaluate-20261110/helper1/self-authored-cert.der','--certificate-sha256','5b6dbcbe8868cc61f504fbdddb5684dfca7323d86682b4fd1c36cf4a09681015','--key','out/image4-firmware-evaluate-20261110/helper1/self-authored-key.pem','--key-sha256','39c75ab3d5c60185cdc3e929a2fa5731019b7bbd4300732773af586d3ae23b27')
wsl @common --allocator-mode ledger --work out/image4-firmware-evaluate-20261110/verifier-data-ledger
$ledgerExit=$LASTEXITCODE
if($ledgerExit -ne 2){throw "Expected new-source BLOCKED/2, got $ledgerExit"}
wsl @common --allocator-mode oom --work out/image4-firmware-evaluate-20261110/verifier-data-oom
$oomExit=$LASTEXITCODE
if($oomExit -ne 0){throw "Expected recorded OOM-negative/0, got $oomExit"}
wsl -d Ubuntu-22.04 --cd /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa -- /usr/bin/python3 -B scripts/research-current-image4-firmware-evaluate.py --ledger-self-test
$testExit=$LASTEXITCODE
if($testExit -ne 0){exit $testExit}
Write-Output "ledger=$ledgerExit oom=$oomExit isolated-tests=$testExit"
exit 0
```

Read the two new JSONs: require exact provenance/hash agreement, first n64/
request2584, full native bzero/clear coverage2584, original free-size/content,
native workspace fields `[0,0,0]`, one admitted allocation/free and second5152
source refused with no ctx decode. OOM must show only a NULL attempt, actual
internal-13 and no successful alloc/free. Never accept empty/missing evidence
as passing. `RESOURCE_FAILURE` is a failed model run, not a native auth result.
No new 5152-byte admission is authorized. No model resource policy, crypto,
donor/config, image build, device action, external write or commit was widened.

### Independent result and remaining review gate (parent-reported)

Independent verifier report references, relative to
`out/image4-firmware-evaluate-20261110/`:

| Report | `harness_sha256` | Status / errno | Command exit |
| --- | --- | --- | ---: |
| `verifier-data-ledger/report.json` | `94d09c6bebd7367d3b3211eb54fbd7453756af5742d78a366b965d6a48c7e73c` | `BLOCKED` / null | 2 |
| `verifier-data-oom/report.json` | `94d09c6bebd7367d3b3211eb54fbd7453756af5742d78a366b965d6a48c7e73c` | `self-checked` / 80 | 0 |

The OOM report's `self-checked` is its literal script status, not a denial of
the independent rerun. Corrected read-only JSON assertions exited **0**,
checking dependencies individually; the 13 model-negative tests exited **0**.
Command exits are retained only in the session tool replies. The assertions
have no separately saved independent log; `data-final-selfcheck.log` above is
implementer evidence and must not be cited as an independent verification log.

Helper and Issuer boundaries were independently rerun. The ledger run confirms
native bzero/clear coverage **2584 each**, zero content and exact size at free,
first workspace closure, then new **5152-byte source BLOCKED**. OOM confirms
original internal **-13 -> evaluate80**, no successful allocation/free;
**13 isolated model negatives PASS**. These are not authentication negatives.

The first verifier JSON check raised `KeyError` from an incorrect field path;
only the JSON validation was corrected and rerun, exit **0**, including actual
source/dependency hash checks. Actual paths are
`result.allocation_observations`,
`result.data_ledger.native_write_coverage` and `result.data_ledger.events`.
Independent mechanical/schema completion is not authentication PASS or completed
static review: the latter was blocked by service `cyber_policy`. Do not integrate
research code or expand the model/resource gate on this evidence. No trusted
positive, nonce closure or device release is established.
