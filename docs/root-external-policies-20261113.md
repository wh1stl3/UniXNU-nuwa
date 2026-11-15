# External root policies — 2026-11-13

**Host-only, self-checked implementation evidence.** Parent reports ordinary
identity review PASS WITH CONDITIONS and independent read-only full-window/chain
verification; the follow-up implementation uses those fixed approved inputs.
No device access, final kernel/FAT/executor build, commit or push. Original OS
signature, userdata, owner key and concurrent verifier dependencies are unchanged.

## Actual SystemOS identity (new branch for reviewer)

Input report:
`out/root-inputs-20261113/nuwa/ios-16.7.16-20H392/nuwa/userdata/userdata-root.json`.
Its SystemOS window starts at 5637144576 and is 2743074816 bytes, SHA256
`9cd738f3b0169055549df84ad6d8d13e50a2da39af618ce0522ca4e06df86849`.
The source is `out/root-inputs-20261113/ipsw/20H392/087-86593-047.dmg`.
Unlike OS, this is a raw APFS container starting at byte 0, not a GPT disk:
NXSB magic is at byte 32, block size 4096, block count 669696.

The existing bounded inspector was adapted **only in the exclusive output** to
accept raw-container framing and report identities without requiring role 1.
Checkpoint, object checksum/type/OID/xid, mapping and node-format checks are
unchanged. No new B-tree format or traversal was implemented.

| Evidence | Observed value |
| --- | --- |
| Container UUID (not volume UUID) | `07490CBA-83EE-4F50-A415-3DE222723455` |
| Highest complete checkpoint | paddr 647678, xid 24 |
| Descriptor ring | base 647669, count 32, index 8, length 2 |
| Complete checkpoint map | paddr 647677, xid 24, flags 1, count 5 |
| Container OMAP | paddr/OID 650187, xid 24 |
| OMAP tree | single leaf paddr 650188, level 0, flags 7, one key |
| Only fs OID / mapping | 1026 / xid 24, flags 0, size 4096, paddr 650186 |
| APSB absolute offset | 2663161856 |
| APSB name | `SydneyUpdate20H392.D22D221SystemCryptex` |
| APSB role | **0**, not OS SYSTEM role 1 |
| Actual volume UUID | `96096B28-B6DC-4BC7-9D3A-2632A0FE53F1` |
| APSB SHA256 | `6b02996dea5ed4369ed9cbc6e5b36c3748ad909f0c306de45cda44abb312be93` |

Full evidence: `out/root-external-policies-20261113/systemos-identity.json`.
Six in-memory controls rejected checksum damage, invalid checkpoint positions,
missing mapping, deleted mapping, APSB OID mismatch and APSB xid mismatch;
`systemos-negative.jsons` records exact rejection reasons. This proves neither
Apple authentication nor filesystem mountability.

The parent approved this unique role-0 SystemCryptex volume UUID as the SystemOS
owner-policy identity, using the complete 2743074816-byte raw window. No signing
was performed before that confirmation. No UUID or role was fabricated.
The inspector's legacy `candidate_natural_match` field is OS-only historical
output and is **not consumed** by this signing workflow. `build-external.py`
asserts the exact approved name, role, UUID, size, SHA256 and chain, plus the
profile/member-report/window association; inspector success alone never selects
an arbitrary first volume. The full-window source/userdata comparison completed: all
2743074816 bytes are identical and the recomputed SHA256 matches the input
report. `systemos-input-comparison.json` retains the result. Python compilation
of the three task-local scripts and `git diff --check` also completed successfully.

## Reuse and capacity route

No driver modification is required: existing ShengUfs (BSD-2-Clause)
`99d8bcd3e43dd24fc3c8437c67b5d4cc71ab94d0` `NativeUfs.cpp:1671-1690`
requires exact `<window>.vroot` name and table length; `:1735-1781` reconstructs
the complete manifest and calls `vr_open`. Size matching is unique only when
both real window sizes have their own policies. Source OS policy alone remains
insufficient for the required OS/SystemOS publication set.
The reused RootLayout/RootPublication headers carry
`SPDX-License-Identifier: BSD-2-Clause-Patent`.

Official UniXNU (BSD-2-Clause-Patent) local base is
`693f5d9cae8a408dd18b39f3f9fdc4228c934241`; its
`scripts/unixnu/userdata.py:119-180` supports `--object NAME=FILE:544`, version 2,
flags 3, block size 4096, MiB object alignment and partition-capacity checks.
Upstream HEAD was queried read-only as
`7d85ede80092050f4d87f72ac7229bb605ce07fb`; no checkout or pin was changed.
Signing reuses VerifiedRoot
`974f043d0c71ba2e60331483a41c6c6d35274ee3`, BSD-2-Clause-Patent,
`tools/manifest.py` and the existing owner key; neither was changed here.
The reused task-local inspector originates from
`out/root-inputs-20261113/apfs-inspect/inspect_apfs.py`, with source SHA256 in
`inspector-source-sha256.txt`; its upstream local author license is unknown.
It remains an ignored analysis copy, not a newly distributed dependency.

## Implementation and remaining boundaries

- `build-external.py` invokes the official manifest CLI with the existing owner
  key, generation 1 (same official convention as `build-owner-os-policy.py:53`),
  and the fixed approved SystemOS UUID. These are software-owner signatures,
  not Apple authentication or persistent anti-rollback. OS is never re-signed.
- Candidate construction calls the unchanged official `unixnu.userdata.build`.
  Only IPSW acquisition is replaced with a task-local adapter returning the
  already acquired cached DMGs. No ZIP/identity extraction is newly claimed;
  source association is checked against the prior reports and selected profile.
  Official UDIF decoding, disk layout, table copy with `:544`, hashing and
  partition-capacity checks execute unchanged, without network access.
- The archive contains the original RootAnchor.o and newly compiled two-entry
  RootPolicies.o. Provider/NativeUfs objects are reused without recompilation;
  `reused-inputs.json` records their exact hashes. Policy compilation retains
  the original ARM64/iOS17.0 target; it does not qualify iOS16 runtime ABI.
- `test-external.py` compiles exact extracted production `readPolicyTable` and
  capacity-selection code with a read-only file transport, plus the unchanged
  RootPublication plan header. Crypto is the existing real C provider/OpenSSL
  adapter. This is host testing, not production UFS transport execution.
  UUID authorization is the official caller's comparison against the real C
  verifier's authenticated `vr_view.volume_uuid`; `vr_open` does not receive an
  externally expected UUID and is not claimed to reject that mismatch itself.
- Final link, runtime allocation/read-only protection and UFS lifetime/transport
  boundaries remain outside this host-input task. External tables reduce boot
  payload size but do **not** remove full manifest RAM allocations in the driver.

Exact commands and exit codes are retained in `commands.json` and
`test-commands.json`; build output is in `build.log`. Artifacts and final test
results are recorded below.

## Built artifacts (self-checked)

Signing, initial real C verification of all 669696 SystemOS blocks, official
builder invocation, policy compilation, archiving, nm and objdump all exited 0.
Build wrapper also completed successfully. `artifacts.json` records:

| Artifact under `out/root-external-policies-20261113/` | Bytes | SHA256 |
| --- | ---: | --- |
| `systemos-signed/manifest.bin` | 21430816 | `9b9d655dab427c65d7cf421f8043cbd9bd74700da3aad5c7f7fbec452bf6fa9d` |
| `systemos-signed/hashes.bin` | 21430272 | `276c3563e6d5b71e87e63a908a747ccab4fb31fc8b220a82f1a43ba6027ca56c` |
| `OS.header.bin` | 544 | `58e556a380c066db50af9dbec3bbbdbeda47ed39e353c47d6c3ec85fe2f4af65` |
| `SystemOS.header.bin` | 544 | `23637c901e6971f64c3596fa60f06b385c85ce401f739ade9ecfba19d20625a7` |
| `RootPolicies.o` | 1736 | `8d0e701b738cefc9e8e07406d562ea5c4689911afb06c4f322f0e489f8b8aa7f` |
| `libNuwaRootInputs.a` | 2944 | `dc975e12945ef567763d530a5aac427f58ad321e5ff3b223db7998bf82388c57` |
| `candidate/userdata/userdata-root.img` | 8446279680 | `da429da64b4d91a08b8adb1d3162f8348b37b358509ab1bd5d8bf09abdbf68d7` |

`archive-audit.json` confirms exactly two archive members and byte-for-byte
equality with the original RootAnchor.o and new RootPolicies.o. The independent
post-build eight-input hash comparison is in `reuse-preservation.json`.

The OS complete manifest remains SHA256
`349efb16d2aa56b82317bfa0535d0036afa1067b810d664413fba73ce55da594`.
The two data objects are:

| Object | userdata-relative offset | Exact table bytes |
| --- | ---: | ---: |
| `OS.vroot` | 8380219392 | 44024096 |
| `SystemOS.vroot` | 8424259584 | 21430272 |

The candidate is below nuwa userdata capacity 240597577728 B. Both original
window offsets, sizes and SHA256s match the old userdata report. SHNGROOT version
is 2; objects use flags 3 / block size 4096, while both windows remain flags 1 /
block size 512. Acquisition is reported `local` by the offline adapter; original
DMG provenance remains the earlier `remote` member reports.

No final kernel capacity claim is made: the small 2944-byte archive replaces the
embedded table input, not an already linked kernel. Driver allocation remains
`round_page(manifestBytes) + 4096` **per window**, with complete reconstructed
manifest sizes 44024640 and 21430816 B. Runtime page geometry, allocation success,
transport scratch ownership, read-only protection and lifetime remain untested.
After this long build upstream HEAD was rechecked unchanged at
`7d85ede80092050f4d87f72ac7229bb605ce07fb`.

## Completed candidate tests (self-checked)

The final `test-external.py` job completed, exit 0. `external-tests.json`
records the assertions; `test-commands.json` retains subprocess exit codes and
stdout/stderr. Both **actual candidate objects**, read through the unchanged
production table-loading function, reconstruct manifests byte-for-byte equal
to the OS original and newly signed SystemOS manifest. The official verifier
then authenticated the reconstructed envelopes and every original block:

| Window | Real C verified blocks | Official verifier exit |
| --- | ---: | ---: |
| OS | 1375753 | 0 |
| SystemOS | 669696 | 0 |

Both signed UUIDs and complete image hashes match the fixed approved inputs.
The two container-UUID authorization controls exited 1 as expected; these are
caller identity rejections, not failures of the genuine volume signatures.

For **each** table: missing object, wrong object name and both short/long object
lengths are refused by the extracted production loader. Real C verifier controls
return 4 for a changed table, 1 for truncated reconstructed manifest, 3 for
signature mutation, 2 for anchor-digest mismatch, and 5 for changed image block.
Minimum generation 2 rejects these generation-1 headers with status 1. The
anchor control is a one-bit mutation of the actual public anchor, not a second
independent RSA key.

OS table final physical 4K read ends at userdata-relative 8424247296, includes
3808 zero padding bytes, and remains below SystemOS.vroot at 8424259584.
SystemOS table is 4K-exact and ends at 8445689856, below image end 8446279680.
Both destination canaries remain unchanged. Every emitted window/object digest
was independently recalculated, padded extents do not overlap, and the image
fits the measured nuwa partition capacity.

The exact production capacity-selection block accepts each real capacity once;
old single-OS policy rejects SystemOS, and duplicate OS capacity is refused.
The unchanged RootPublication plan accepts the distinct OS/SystemOS window set,
orders SystemOS before OS, and rejects missing, duplicate and wrong names.
Objects are not counted as windows. Mach-O section bytes independently show
both 544-byte headers, count 2, two pointer relocations, and 1128 total const
bytes. Final linking/publication, runtime table allocation and full IOKit/UFS
execution remain untested.

## Independent verifier commands

From the device repository under WSL, use a fresh output copy for the inspector
if preserving these result files is required:

```sh
python3 out/root-external-policies-20261113/inspect-systemos.py --image out/root-inputs-20261113/ipsw/20H392/087-86593-047.dmg --base-offset 0 --span 2743074816 --negative-tests
python3 out/root-external-policies-20261113/check-systemos-input.py
/home/wh1stl3/.local/bin/python3.11 out/root-external-policies-20261113/test-external.py --out out/root-external-policies-verifier-20261113
git diff --check
# From the UniXNU checkout:
/home/wh1stl3/.local/bin/python3.11 scripts/porting-record.py check --device /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa --base origin/feat/step7-kernel-patches-8796
```

The default Windows `python` alias was absent; the actual checks used WSL Python.
Final build/test verification and integration acceptance remain with the parent
and independent verifier.

The porting-record check above exited 0 (14 structured areas); no production
configuration or porting record was modified by this task.
The final ad-hoc hash/diff wrapper first stopped at `<stdin>:13`: it incorrectly
required exit 0 from `git diff --no-index --check` on an added document (normal
diff exit 1, no whitespace diagnostics). The corrected check accepts normal
diff status only when stdout/stderr are empty; no artifact or test was changed.

The final test command uses an independent report/output directory and no
private key. It reruns the unchanged official C full-block verifier against
both manifests reconstructed from the actual candidate objects. To rebuild the
candidate rather than only retest it, copy `build-external.py` and
`inspect_apfs_systemos.py` into a fresh sibling `out/` directory and run the
build script there; it intentionally refuses to overwrite signing/candidate
outputs. That rebuild requires the already authorized existing owner key and
must not generate a new key.
