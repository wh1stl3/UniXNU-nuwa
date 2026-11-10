# nuwa AMNM-only chosen policy, 2026-11-10

Status: **self-checked only; NOT independently verified, NOT device-tested;
DEVICE RELEASE PROHIBITED**. Device revision
`73824c65788a7c811f68ad77ef411e57ec032337` plus this board/docs group;
base `693f5d9cae8a408dd18b39f3f9fdc4228c934241`. This configuration/docs group
is closed with one local commit; no push/merge. Artifact audit predates that commit.

## Observed failure and reviewed scope

Parent-delivered device/visual review: old stage5 vendor_boot SHA256
`998d284ad4959aebdb1a7f26d161eea5b2a49fe169264a843f19708ec522bea5`
did not reset; photo confirms `failed to get mix-n-match policy: 2`.
`_panic` displays then parks as intended. Missing AppleImage4-required /chosen
property gives ENOENT=2; reviewed frame `fffffff0046e9f60`. Supports
kernel_bootstrap_thread -> mac_policy_initmach -> KLDBootstrap
loadSecurityExtensions -> OSKext start -> AppleImage4 initialization, **not stage5**.
Ignored evidence: `.cache/media/stage5-panic-20261110-183907/execution.log`
and `visual-frames/text-real.png` under that media directory. Parent reports
18:54:23 return A/TWRP current/active=0; this task did not query devices.

Deep **PASS WITH CONDITIONS** relayed by parent permits only device board table
`[os_overrides."ios-16.7.16-20H392".adt.chosen.u32]`
`mix-n-match-prevention-status=0`. TOML parses without duplicate tables.
Zero means AMNM=true: **non-Apple boot-chain bring-up software policy**, not
donor/fuse fact; relaxes anti-replay-token/chained-manifest-hash constraints,
does not disable AMFI or claim Apple secure boot. Existing generator path used;
no base/donor edits. Existing stage5/panic probes, kernel/prelink, crypto mode
and trust unchanged. Area acceptance levels are unchanged.

## Confirmed device-release blocker (parent-delivered Reviewer)

Current chip `sha2-384 arm ap` descriptor `fffffff005cae660 +8` has
secure-boot-level=0; `_pmap_in_ppl` actually returns 0. Actual
manifest-properties lacks BNCH and DarwinBoot does not inject it. Init
`fffffff0046e9a24–fffffff0046e9a40`: BNCH ENOENT with level 0 determines the
**next panic**. AMNM-only candidate is therefore not suitable for a device run.
CHMH may be absent with AMNM=true; LOVE permits ENOENT. ESEC absent in ap is
not a current mandatory addition. No BNCH/other properties or level changes
were made. Historical Deep ruling (parent-delivered, corrected below): the pinned donor provider
has no demonstrated supported no-AP-token/no-shadow entry point. Open-source
XNU nonce wrappers cannot control earlier BNCH initialization or internal
shadow state; registering a custom runtime does not replace built-in PMAP_CS,
and interface registration is one-shot. The current bare-kernel path supplies
neither an authenticated manifest nor a nonce producer.

Latest Deep correction (user-requested review completed, parent-delivered):
the earlier absolute requirement to obtain AppleImage4 source or wait for an
external provider is withdrawn. A complete Apple production security chain is
not an official bring-up stage 5 prerequisite. An explicitly experimental
software domain may be researched; lifting its gate requires a bounded consumer
closure and sufficient authentication negative-test evidence, not necessarily
closed-source code. Current evidence approves **no BNCH runtime candidate**;
AMNM-only remains barred. Arbitrary values must not be described as real
hardware/donor nonces; initialization success is not authentication success.
Do not fabricate BNCH, change secure-boot level, replace pointers or skip init.
Without new contract evidence, do not repeat guessed BNCH analysis, ineffective
candidate builds or device attempts. Independent local fixes, analysis and host
validation may continue under applicable review gates; this intermediate remains
prohibited from device release, and any future device test needs user confirmation.
Next action: use the [local question checklist](appleimage4-provider-question-draft-20261110.md)
to assess interface evidence and define the experimental domain/consumer and
authentication-negative-test requirements locally. Public material is
read-only: no external messages or publication. The general publication task was
cancelled; no comment/issue was sent and no external write occurred.
Menu auto-down remains a user observation;
OEM SDAM/Reset is only a candidate mechanism. Log-level filtering is confirmed
but not fixed (parent-delivered findings, no new test here). Root AGENTS already
contains the corrected multi-device targeting rule; its gates are unchanged.
Separately, firmware commit `719afa67e3aebbf058c2a8beff4c801057fb2b20`
fixes only the DEBUG component mask `0x8007EE4F` in `nuwa.dsc`: static review
and mechanical checks PASS (parent-reported). Old edksetup is missing; full
EDKII parsing/AutoGen/compilation/device validation remain undone, three dirty
submodules retained. No firmware file is changed by this integration.
Latest offline research review/verifier results and remaining parseable
manifest/apin/state boundary are in [the offline evidence](image4-bnch-offline-20261110.md).
They do not lift this AMNM-only device gate. Historical A/TWRP observation above
is not current status: separate general Android restore/userdata-clear work is
authorized and in progress, final result pending.

## PR187 read-only finding (parent-delivered, 2026-11-10)

Official PR <https://github.com/UniXNU/UniXNU/pull/187> was open, not merged,
at head `7dd07bb46b751108e34bd796153daaf57b28e549`, preceding commit
`fd71284ee795092a2ff325677af798923870cb60`. Its three-file diff is +5/-2;
`devicetree.py:340–341` passes `config.adt.manifest_properties` through
`typed_properties` into `/chosen/manifest-properties`. This is transport only,
not a producer or authentication implementation.

The author reports passing AppleImage4 on NX769J / iOS 16.5, but does not
disclose BNCH provenance or the exact tested configuration. Public profile
`2a265afdbd95d45e4a90664157e793c3bfee3755` lacks that field; this does **not**
refute the author's report. Its 20F66 / XNU 8796.101.5 differs from nuwa's
20H392 / 8796.141.3. No comments or approving reviews were present in the
reported check. This clue does not lift the runtime gate or justify fake BNCH;
passing initialization is not authentication success. The user-requested Deep
re-review has completed with the correction above. This task records supplied evidence only;
it did not independently re-query GitHub or reproduce the author's boot.

## One host assembly

WSL Ubuntu-22.04, cwd `/mnt/d/Code/PortingiOS/UniXNU`;
PATH `/home/wh1stl3/.local/bin:/opt/unixnu-linux/bin:/opt/unixnu-linux/llvm/bin:/usr/local/bin:/usr/bin:/bin`.
Root `R=/home/wh1stl3/nuwa-mix-n-match-20261110`, TMPDIR `$R/tmp`;
`O=$R/out`, `W=$O/nuwa/ios-16.7.16-20H392/nuwa`.
Driver `.cache/run-mix-n-match-host-20261110.sh` invoked with
`wsl -d Ubuntu-22.04 -- bash /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/.cache/run-mix-n-match-host-20261110.sh`.
Ran once 19:07:55–19:08:14 +08:00: payload_rc=0, vendor_boot_rc=0,
driver_rc=0 recorded in `$R/assembly.log`. Commands:

```sh
./unixnu build payload -D /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa --out /home/wh1stl3/nuwa-mix-n-match-20261110/out --kernel /mnt/d/Code/PortingiOS/UniXNU/out/nuwa/ios-16.7.16-20H392/nuwa/kernel/kernel.macho --uefi /mnt/d/Code/PortingiOS/nuwa/uefi-nuwa --trust-cache /mnt/d/Code/PortingiOS/UniXNU/out/ipsw/20H392/087-86698-044.dmg.trustcache.bundle
./unixnu vendor_boot --stock /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/.cache/stock/vendor_boot_b.img --ramdisk /home/wh1stl3/nuwa-mix-n-match-20261110/out/nuwa/ios-16.7.16-20H392/nuwa/payload/payload.img -o /home/wh1stl3/nuwa-mix-n-match-20261110/out/nuwa/ios-16.7.16-20H392/nuwa/vendor_boot/vendor_boot.img
```

Reused feeds symlink/.config and existing prelink; no kernel/prelink/firmware
build. Old stage5 output retained and rehashed against prior recorded hashes.

## Incremental audit and artifacts

`.cache/check-mix-n-match-host-20261110.py` exit **0** (self-checked): extracts
old/new FAT ADT/kernel/trust/menu, rejects duplicate ADT nodes/properties;
unique `/chosen/mix-n-match-prevention-status` is length 4, bytes `00000000`.
Semantic ADT differences are exactly that addition plus `/chosen/random-seed`
(256 bytes each, explicitly permitted). No identity/seed values printed.
At audit time parsed board differed from revision
`73824c65788a7c811f68ad77ef411e57ec032337` only by the chosen u32 addition.
Final kernel/trust/menu are byte-identical to old stage5. Prior panic ABI,
renderer/probe audit is reused by full kernel identity; **not rerun**.
Vendor ramdisk equals payload byte-for-byte; sizes and manifest hashes match.

Host copy: `D:/Code/PortingiOS/nuwa/UniXNU-nuwa/out/mix-n-match-20261110/`.
Payload/vendor paths below are relative to host copy (same under `$W`);
audit artifacts under `$R/audit-final` and host `audit-final`.

| Artifact | Bytes | SHA256 |
| --- | ---: | --- |
| `payload/payload.img` | 67108864 | `8c772467028d4699fd09ee5e183b8e4fd989bc283afbeb4b01127730ab5f15a3` |
| `vendor_boot/vendor_boot.img` | 100663296 | `6c05f02e6db22a301aa5faf14193a121b27aa98566ebe0fc323d6e16e559bca5` |
| `audit-final/new/kernel.macho` | 55357440 | `fb1e796d7357b3e7ff7027bb94377d1cd38eae7283a6c72a7460914a200a0fbd` |
| `audit-final/new/kernel.macho.adt` | 13172 | `9172e0ccd2efe250bcba05ce1e1884a5bb19a9c7d6a86527aaa35c36e5de453b` |
| `audit-final/new/kernel.macho.trustcache` | 66272 | `367e051548f9f0407fa9fe9d40007fa4e7c5ff27c45f5a7a30cedf344e24d98e` |
| `payload/payload.json` | 667 | `845ac7f5bff63f476838185b8c0ea172249809cfe2e0f3b5259ea52b38890262` |
| `vendor_boot/vendor_boot.json` | 411 | `eb71cdba16c0ba835ccd4255fdd565fe7f5e3b1369d066f486858b9c9fda0f83` |

Source prelink hash remains
`da0d660f8336fa87825ec34ce1f48b653d728a6277aaf7d4b03784cf4f73c969`.
Audit retains `artifact-hashes.json` and `adt-diff.json`. Export script
`.cache/export-mix-n-match-host-20261110.py` exit 0, hash-compared four
artifact/manifest copies. An initial inline PowerShell/WSL export wrapper
failed (exit 2, empty `$H` from argument quoting); no artifacts were modified
and no assembly was repeated. Dedicated Python export fixed quoting.
`git check-ignore` confirms output and local scripts ignored. Media/binaries
are local only, not for upload. Shared handoff is updated separately after the
device commit; final integration remains with parent.

## Retained incremental reproduction commands (not a required verifier job)

No full verifier job is requested for this non-bootable intermediate. No
independent verifier rerun occurred. Do not run assembly/export/device scripts
or the unchanged panic full suite. If later needed, the audit compares board
scope to its pre-commit baseline; after commit its `git show HEAD:board.toml`
reference must first be explicitly pinned to the revision recorded above.
Recorded pre-commit commands, from Windows device cwd:

```powershell
wsl -d Ubuntu-22.04 -- env PATH=/home/wh1stl3/.local/bin:/opt/unixnu-linux/bin:/opt/unixnu-linux/llvm/bin:/usr/local/bin:/usr/bin:/bin python3 -u /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/.cache/check-mix-n-match-host-20261110.py /home/wh1stl3/nuwa-mix-n-match-20261110/verifier-audit
wsl -d Ubuntu-22.04 --cd /mnt/d/Code/PortingiOS/UniXNU -- /home/wh1stl3/.local/bin/python3 scripts/porting-record.py check --device ../nuwa/UniXNU-nuwa --base origin/main
git diff --check
Get-FileHash out/mix-n-match-20261110/payload/payload.img,out/mix-n-match-20261110/vendor_boot/vendor_boot.img,out/mix-n-match-20261110/payload/payload.json,out/mix-n-match-20261110/vendor_boot/vendor_boot.json -Algorithm SHA256
```

Any later independent verification should compare final host copies/table,
audit diff and board scope without rebuilding. Final integration/acceptance
remain with parent; this artifact self-check cannot lift the current runtime gate.

Implementer ran the documented record command from base cwd: exit 0,
`nuwa: 14 structured areas checked`; device `git diff --check` exit 0.
Windows `Get-FileHash` of the four candidate/manifest copies matches this table.
These are **self-checked**, not an independent verifier rerun.
