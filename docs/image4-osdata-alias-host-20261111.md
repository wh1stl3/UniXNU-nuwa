# Image4 ADT-backing -> OSData -> reader alias test (2026-11-11)

**Status: self-checked host evidence only.** No device, adb/fastboot, build,
candidate/policy/level change, commit or push was performed. This is not
independently verified and not a live-IORegistry, authentication or
device-overwrite proof. The r2 runner and its evidence are unchanged; this is a
separate narrow runner. Final acceptance remains with the parent orchestrator.

## Scope

`scripts/research-current-image4-osdata-alias.py` connects the real frozen
Image4 initializer entry `0xfffffff0046e98cc` to the AMNM property read through
a real-ADT-backed OSData object. It asks a narrow question: if the OSData value
is backed by the live ADT storage instead of the old Python snapshot fixture,
does changing only the backing AMNM byte change what the real reader sees?
`SecureDTInit` executes, but the AMNM offset comes from Python ADT parsing,
not an actual `SecureDTGetProperty` return.

The new runner reuses `audit-image4-runtime-provider.py` (`Model`,
`parse_adt`), `build-kernel-entry-probe.py` (Mach-O helpers) and
`nuwa_launch_context.py` (ADT codec). Those files and the r2 runner/evidence are
unchanged. No a296 artifact or implementer package is used.

## Inputs and stop control

| Input | Bytes | SHA256 |
| --- | ---: | --- |
| `/root/nuwa-pmap-ret-native-20261111/diagnostic-20261111-r1/renderer-baseline.macho` | 55386112 | `7fd3d933aae66d8e34a0d3ebfa142137978976d7521e04cef20321109750b6f4` |
| `out/owner-pmap-ret-continuation-verifier-final-20261111/adt-generation/final.adt` | 13256 | `885094de4597fb2d1734ba4092c805968097d021c8f482653b238436586d27a4` |
| read-only stop control `out/owner-pmap-ret-package-verifier-final-20261111/adt-generation/final.adt` | 13256 | `ff7d25234c1c6d3ed14e63e3e5489f26fdf65d1f7f649f20b8f6704f8b4ab736` |

Stop control is comparison only, not runner input. Structure, AMNM and
TrustCache are the same; the differing properties are exactly
`/chosen/random-seed` (256 bytes) and `/chosen/manifest-properties/BNCH`
(48 bytes). The known args difference (stage5 removal) has no established
causal chain and is not attributed to the restore RET.

Actual ADT backing:

- `/chosen/mix-n-match-prevention-status`: offset **0x2538**, length **4**,
  value `00000000`, mapped backing address `0xe02538`.
- `/chosen/memory-map/TrustCache`: offset **0x2598**, length **16**.
- `/chosen/manifest-properties/BNCH`: offset **0x260c**, length **48**.
- TrustCache/BNCH do not overlap AMNM. `/chosen/memory-map/DeviceTree` is
  absent in the actual run; `/chosen/random-seed` is offset `0x17c`, length 256.

## Real code and explicit boundary

`MakeReferenceTable` is frozen at `0x78b009c`; its copy=false branch calls
`OSData::withBytesNoCopy` at `0x78b01f4` (copy=true at `0x78b01dc` is
`withBytes`). The full path needs `new IOService`, `init`, the property table,
`OSDictionary`/`OSSymbol`, the DT iterators and the allocator/OSObject
metaclass state; this runner does **not** execute that full path and does not
claim a complete IORegistry.

Bounded real construction instead executes the frozen
`OSData::initWithBytesNoCopy` field instructions
`0x78581b4..0x78581bc`, which write length `+0xc`, capacity `EXTERNAL` `+0x10`
and data pointer `+0x18`. The call to `OSObject::init` at `0x78581ac` /
`0x785569c` (metaclass/refcount/allocator) is the stop boundary. The object
block, real-vtable copy and release no-op are explicit fixtures; the
copy=false field writes and getters are real code, not a complete OSData
constructor or lifecycle.

Real OSData bindings:

| Item | Address |
| --- | --- |
| vtable | `0xfffffff0071ac450` |
| vtable `+0x28` release | `0xfffffff0078553cc` |
| vtable `+0xa0` getLength | `0xfffffff00785854c` |
| vtable `+0xd8` getBytesNoCopy | `0xfffffff0078588c8` |
| `initWithBytesNoCopy` | `0xfffffff007858184` |
| `withBytesNoCopy` | `0xfffffff007858324` |

The real getters are called through the vtable by the reader helper
`0x46f07e8` (capacity 4) and directly during construction. `getLength` reads
`+0xc`; `getBytesNoCopy` reads length `+0xc` and data `+0x18`.

## Cases (fresh state each)

| Case | Model | Backing after | Real alias | Reader input / store / final | Exit |
| --- | --- | --- | --- | --- | --- |
| snapshot-original | old snapshot | `00000000` | n/a | 0 / 1 / 1 | boundary `46e9b2c` |
| alias-original | real alias | `00000000` | length 4, data `0xe02538` | 0 / 1 / 1 | boundary `46e9b2c` |
| snapshot-backing-mutated | old snapshot | `01000000` | n/a; old bytes still `00000000` | 0 / 1 / 1 | boundary `46e9b2c` |
| alias-backing-mutated | real alias | `01000000` | length 4, data `0xe02538` | 1 / 0 / 0 | CHMH panic `46e9f64`, errno 2 |
| alias-length-5 | real alias | `00000000` | real getLength 5, data `0xe02538` | AMNM helper 84; no final read | AMNM panic `46e9f50`, errno 84 |
| alias-length-3 | real alias | `00000000` | real getLength 3, data `0xe02538` | 0 / 1 / 1 | boundary `46e9b2c` |
| alias-wrong-type | real alias | `00000000` | safeMetaCast rejects; no reader getter | AMNM helper 96; no final read | AMNM panic `46e9f50`, errno 96 |

Positive: unchanged backing gives the same store/final/boundary for the real
alias and the old snapshot.

Required negative: after the isolated alias object is constructed, only the
emulator backing AMNM byte is changed to `01`. The real alias reader sees
input 1, stores 0, loads 0 and takes the CHMH panic (errno 2); the old snapshot
still reads its Python copy `00000000`, stores 1 and reaches the boundary. The
candidate/input files are unchanged; this is an emulator-memory perturbation,
not proof that the device has an overwrite.

Length contract: length 5 is rejected by the real helper's capacity-4 check
(errno 84), while length 3 is accepted and the reader still sees a zero u32
because the helper zeroes the capacity and copies 3 bytes. The contract is the
real capacity/read behavior, not a guessed `length == 4` equality.

Wrong object: the existing safeMetaCast fixture rejects the alias object
(errno 96); the real helper error path and AMNM panic are recorded. This does
not execute real metaclass type validation.

## Assertions and negatives

Evidence SHA256 `17b8188510f9080d3ac5e5ff26e1961a10b294b1901751e853cea7872f47b851`.
9 logical semantic check groups; 3 mechanical invariants. They are not a count
of independent semantic proofs.

Negative-check SHA256
`59b9422effda581d818fc6c76beb25fac8cb1e5b89210fd7ddd1c8184c480b10`:
**12/12** single-field tamper mutations rejected, including alias data pointer,
real getLength, capacity, alias/snapshot store, length/type errno, AMNM offset,
input/source hash, comparison flag and stop-control hash.

## Artifacts

| Artifact | SHA256 |
| --- | --- |
| r2 runner (unchanged) | `96265f953dd6194cf8dad5700308e7d5da038c8ff4af0db2c42b79bee240fe7e` |
| r2 evidence (unchanged) | `b14a0a15b6fd6b54bda10d9aed79ac34b39a9062f5a873e668ff91df3f887c77` |
| runner used for historical evidence (before overlap expression fix) | `502aa8289e2b3fa95f8c85a2b7d956c8847b0ebbef523e48e7d5236f1f47e8e6` |
| new evidence | `17b8188510f9080d3ac5e5ff26e1961a10b294b1901751e853cea7872f47b851` |
| new negative check | `59b9422effda581d818fc6c76beb25fac8cb1e5b89210fd7ddd1c8184c480b10` |

Outputs are in the fresh ignored `out/image4-osdata-alias-20261111/`
(`evidence.json`, `negative-checks.json`; earlier `superseded-r0.json` is
retained). The runner refuses to overwrite (`open('x')`).

## Self-check commands

Windows cwd `D:/Code/PortingiOS/nuwa/UniXNU-nuwa`; WSL cwd
`/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa`, `/usr/bin/python3` 3.10.12 with
Unicorn 2.1.4 (`PYTHONPATH=/home/wh1stl3/.local/lib/python3.10/site-packages`).
No network access.

```powershell
wsl -d Ubuntu-22.04 -u root -- env PYTHONPATH=/home/wh1stl3/.local/lib/python3.10/site-packages /usr/bin/python3 -B -m py_compile /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/scripts/research-current-image4-osdata-alias.py

wsl -d Ubuntu-22.04 -u root -- env PYTHONPATH=/home/wh1stl3/.local/lib/python3.10/site-packages /usr/bin/python3 -B /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/scripts/research-current-image4-osdata-alias.py --kernel /root/nuwa-pmap-ret-native-20261111/diagnostic-20261111-r1/renderer-baseline.macho --kernel-sha256 7fd3d933aae66d8e34a0d3ebfa142137978976d7521e04cef20321109750b6f4 --adt /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/owner-pmap-ret-continuation-verifier-final-20261111/adt-generation/final.adt --adt-sha256 885094de4597fb2d1734ba4092c805968097d021c8f482653b238436586d27a4 --stop-adt /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/owner-pmap-ret-package-verifier-final-20261111/adt-generation/final.adt --stop-adt-sha256 ff7d25234c1c6d3ed14e63e3e5489f26fdf65d1f7f649f20b8f6704f8b4ab736 --output /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/image4-osdata-alias-20261111/evidence.json

wsl -d Ubuntu-22.04 -u root -- env PYTHONPATH=/home/wh1stl3/.local/lib/python3.10/site-packages /usr/bin/python3 -B /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/scripts/research-current-image4-osdata-alias.py --kernel /root/nuwa-pmap-ret-native-20261111/diagnostic-20261111-r1/renderer-baseline.macho --kernel-sha256 7fd3d933aae66d8e34a0d3ebfa142137978976d7521e04cef20321109750b6f4 --adt /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/owner-pmap-ret-continuation-verifier-final-20261111/adt-generation/final.adt --adt-sha256 885094de4597fb2d1734ba4092c805968097d021c8f482653b238436586d27a4 --stop-adt /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/owner-pmap-ret-package-verifier-final-20261111/adt-generation/final.adt --stop-adt-sha256 ff7d25234c1c6d3ed14e63e3e5489f26fdf65d1f7f649f20b8f6704f8b4ab736 --negative-self-check /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/image4-osdata-alias-20261111/evidence.json --negative-output /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/image4-osdata-alias-20261111/negative-checks.json
```

Actual exits: `py_compile` 0; main run 0 (9 semantic groups, 3 mechanical
checks); negative run 0 (12/12 rejected).

## Conclusion and limits

The model still runs normally. The backing mutation shows the real alias reader
sees changed storage while the old snapshot does not, but this is an emulator
fixture experiment, not proof that a device or loader has an overwrite. What
remains missing is runtime input / flag write-read / call-order evidence; no
stop probe is designed and no device run is requested.

Limitations:

- Full `MakeReferenceTable`/IOService/OSDictionary/OSSymbol and
  `OSObject::init`/metaclass/allocator are not executed; only the copy=false
  field slice and real getters are.
- The object/vtable/release and the ADT backing are explicit fixtures; the
  IOKit node/registry objects remain the old fixtures.
- The backing mutation is an emulator-memory write only; inputs are unchanged.
- This is not a complete IORegistry, device, authentication or overwrite proof.
- The r2 runner/evidence are untouched; this runner is separate.
- The stop ADT is read-only comparison only; random-seed/BNCH differences have
  no established causal chain and do not blame the restore RET.
