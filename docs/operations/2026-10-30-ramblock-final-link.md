# iOS16 RamBlock source-kernel link and initialization

## Scope

Stages S03/S05/S06. This opt-in CI extends the successful private-header build from run 40870837215, commit 4eac58c6064d961e9d8db15245161bdfed49859c. User approved an independent CI branch, scoped commits/pushes and CI on 2026-10-30. No device activity is authorized by this record.

The production 190-slot vtable and private reference are pinned in `config/ramblock-ios16-link-contract.json`. Current CI objects must match both. Eleven original IOBlockStorageDevice bindings refer to the fixed iOS16 donor; they do not supply donor code or make a deployable prelink.

## Implementation

`ramblock_kernel_link_check=true` compiles the production late archive, then runs `scripts/ci/build-ramblock-kernel.py`. It reuses actual baseline make arguments, force-loads platform and late RamBlock archives with the original storage bindings, and enables only the personality and late-registration caller. Existing root/Data mount flags remain unchanged.

The initialization patch loads IOStorageFamily, explicitly registers NativeRamBlock, and only then publishes IOBSD. Failed registration propagates through bsd_autoconf instead of silently continuing. Final checks require resolved symbols, exact donor bindings, direct call order, an explicit constructor call, and absence of duplicate automatic constructor registration.

## Validation and remaining gates

Local six-case make-input/parser tests passed against the real successful CI kernel; workflow YAML parsed; the late-init patch replay and production ABI checks passed. These are not an executed final macOS link. New CI must establish that result.

Even a successful source link does not qualify donor prelink, runtime metaclass/provider matching, complete root/Data mounting, persistence, init execution, or an on-device image. Full OS/SystemOS require their reviewed read-only block windows; the separate packed Data seed remains volatile. PROBE60 and the iOS16 mainline are unchanged.

## CI revision: incremental build and personality validation

Run 41014591773 tests commit 89d2768600a56e0d81063dd1436f191895db62a6. While it builds, review of the per-file compiler rules identified an additional admission requirement: touch only the three modified caller/personality source units in RUNNER_TEMP, preserve their real compiler records, and reject missing/conflicting enabled macros. Read the linked gIOKernelConfigTables pointer and require the unique NativeRamBlock/IOResources/IOBSD personality. Require the Data volume seed export as well as class registration. Eight local tests now pass, including rejection of the old actual kernel without that personality and both actual private-object vtables.

This revision is needed even if the first CI link succeeds; class-symbol presence alone is insufficient. Public source reference: https://raw.githubusercontent.com/apple-oss-distributions/xnu/1b191cb58250d0705d8a51287127505aa4bc0789/makedefs/MakeInc.rule .

## Failure 41014591773 and real-provider correction

The actual kernel make reached ld and failed on exactly the six native_ufs_store_* imports. Archive compilation and both modified kernel callers compiled. Raw artifacts are retained under out/ci-ramblock-link-41014591773. Apple framework weak-linking documentation describes dynamic-loader resolution; it does not establish optional-import resolution for this static kernel invocation (https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPFrameworks/Concepts/WeakLinking.html).

User pointed out the existing real UFS implementation. Rechecked the currently pinned NativeUfs af785c1777161a62931425c2faaa536ce0bebd5b: all six exports exist; open rejects disabled mode or missing host/layout, read/write require an opened bounded window, sync requires write mode/window, and GPT checks reject unavailable host/layout. No volatile-only source modification was applied.

The revised archive build compiles this real source with the current private kernel record and exact forward declarations, strips only verified automatic initializer lists, and explicitly initializes its C++ globals/classes after IOStorageFamily and before RamBlock. A dedicated wrapper checks both new metaclasses, parent identity and class sizes measured from the actual compiled DWARF. Final verification requires actual section-backed UFS functions, inherited block vtable slots, and both explicit constructor calls. There are no zero-address aliases or replacement success functions.

UFS personality and NATIVE_VERIFIED_BLOCK remain disabled. Registering the classes and resolving the interfaces does not start the controller, accept nuwa geometry, open persistence or qualify complete root mounting. The initial plan to remove optional backend code was abandoned before implementation in favor of the existing real provider. Patch replay against the current failed CI's exact 64-patch inputs, eight link tests, four existing private-input tests and the DWARF parser on the real prior NativeRamBlock object passed locally; actual UFS compilation and the next final link remain CI gates.

## Production compiler correction after 41017468209

NativeUfs compilation failed with 19 errors: eight old private-header overloaded-virtual diagnostics, five missing-noreturn suggestions for existing panic-only diagnostic methods, three implicit narrowing diagnostics in be32, and three undeclared diagnostic names when NATIVE_VERIFIED_BLOCK=0. Original output is out/ramblock-ci-41017468209-failed.log.

The copied, pinned source receives a reviewed two-hunk patch: explicit uint8_t byte serialization casts and the same VerifiedRoot conditional around its read-timing diagnostics as around their definitions. The transport call and return stay outside that condition. Original source checkout is unchanged. IOPlatformExpert's historical header diagnostics are scoped in the prelude; missing-noreturn remains visible as warnings for this UFS unit only. No global Werror removal or fake storage API. Patch replay against the exact fixed source and Python syntax passed; actual production compilation remains required.

## Object metadata correction after 41019713342

Real NativeUfs compilation now passed. Its production DWARF reports NativeUfs=0x98 and NativeUfsBlock=0xd8; all 190 block vtable slots and inherited signatures match the reviewed private reference. The initializer conversion failed because Apple's assembly round trip dropped N_COLD_FUNC (0x400) from twenty local .cold.N symbols. All retained section bytes and relocations already matched. LLVM's MachO.h defines this descriptor bit: https://raw.githubusercontent.com/llvm/llvm-project/main/llvm/include/llvm/BinaryFormat/MachO.h .

The conversion now restores only the observed 0x400-to-zero descriptor loss on identical local text symbols, then reruns the unchanged full section/relocation/symbol verifier. It does not ignore symbol differences. Real-object replay changes exactly twenty metadata bytes, preserves ten sections and 2255 relocations, and rejects unrelated descriptor/text mutations. Four regression cases passed. Evidence: reports/desktop-readiness/2026-10-30-ufs-cold-flags-r1/audit.json. Original failed artifact objects remain unchanged.

## Root/Data handoff constraints from actual provider code

The intended source-level sequence is normal IOStorageFamily load, UFS explicit C++ registration, RamBlock explicit registration, IOBSD publication, RamBlock matching/start, then the existing gated Data preparation. The actual Data query finds a unique UUID media backed by NativeRamBlock, calls attachStore, and returns the logical seed identity. With no sheng-data-persist argument, the real provider reports mode 0 and the sparse Data path stays volatile. attachStore records its first attempt; a future persistent configuration must make UFS host/layout ready before that attempt rather than assume it retries later.

The fixed source exports all six store functions. Source guard evidence is reports/desktop-readiness/2026-10-30-ufs-provider-contract-r1/audit.json. The previously captured nuwa DT agrees on controller 0x1d84000/0x3000 and SID 0x60, but its ordinary nub compatible is qcom,ufshc rather than the driver's qcom,sm8550-ufshc. The driver's explicit IOPlatformExpertDevice root/probe route is separate; this mismatch alone does not prove that route unusable. No matching, MMIO, DMA ownership, geometry, identity or *_verified setting was changed.

Complete root still needs qualified read-only OS/SystemOS windows and a real verified-root resolver. The current helper native_verified_block_volume_device resides in NativeVirtioBlock and can delegate authentication to NativeUfs only with the relevant verified implementation. This CI intentionally does not enable the root/Data mount macros or claim that compiling the six persistence interfaces supplies the full root publication/authentication chain.

## Successful final link and offline prelink

Run 41023883615 completed successfully at commit 6c370c6a1b3b025457e2f9b9297691723481d517: https://github.com/wh1stl3/UniXNU-nuwa/actions/runs/41023883615 . Downloaded kernel SHA256 is 969c1b715f7f17cccf810b782983df04b5decf0cb57b16e63e5df16705ae7e15 (20,309,304 bytes). The six UFS exports are real section-backed functions. Actual init call order and constructors, enabled RamBlock personality, production ABI, zero undefined symbols and preserved dormant UFS state passed. The source-link summary is reports/desktop-readiness/2026-10-30-ramblock-final-link-r1/audit.json.

Fresh local analysis prelink f11dc6206141fb931710046788c4ec1500d5adaa19c9890156d88cbff45ad8a5 retains native executable bytes and all 30 donor executable ranges. All 65,348 pointer bindings were reread. A separate audit confirms eleven storage dependencies backed by IOStorageFamily and all 190 slots in each of IOBlockStorageDevice, NativeRamBlock and NativeUfsBlock (570 total). Reports: reports/desktop-readiness/2026-10-30-ramblock-prelink-r1/audit.json and 2026-10-30-ramblock-prelink-abi-r1/audit.json.

Eighteen actual ARM64 guard executions in Unicorn passed for all six UFS APIs with absent/1/2 persistence modes and unready host/layout. Only the boot-argument parser is stubbed; valid non-null I/O buffers are supplied, no controller memory is mapped. This proves these particular guard returns, not C++ constructor execution, UFS readiness or real storage I/O. Evidence: reports/desktop-readiness/2026-10-30-ufs-unready-machine-r1/audit.json.

The prelink remains analysis-only: early security initializer identity/ABI, complete donor/native ABI coverage, runtime ADT/allocation and firmware large-payload transport remain separate gates. Root/Data mount flags and hardware matching are not enabled by this change. PROBE60 is unchanged and unconsumed; no device access occurred.
