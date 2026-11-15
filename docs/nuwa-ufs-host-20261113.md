# nuwa NativeUfs isolated host object — 2026-11-13

**self-checked; explicit storage-binding and policy-input gaps.** No driver enablement,
kernel link, hardware access, or storage readiness is implied.

Input is the existing ShengUfs commit archive for
`99d8bcd3e43dd24fc3c8437c67b5d4cc71ab94d0`, SHA256
`56579a870f62974c47458cab36f8ffb441915f7d391542944ff3b2839146f366`.
All 31 archive files matched the extracted input byte-for-byte. `NativeUfs.cpp`
SHA256 is `8e99199aa87dc2ccebfe3366a0f6896fc8937d57670117af66c10ee52b1b28cd`.
Archive provenance is HTTPS commit archive, not git-signature authentication.

The host build reuses the existing 8796 IOPMGR compilation record, its target and
include tree, the existing `build/storage-abi/include` headers, and official
`UniXNU/scripts/build-sheng-source-drivers.py:140-142` VerifiedRoot defines and
includes. The local UniXNU base is pinned at `693f5d9cae8a408dd18b39f3f9fdc4228c934241`;
this was not an invocation of the official complete driver builder. No iOS17
vtable or board settings were substituted. The exact replay command and its cwd
are retained in ignored `out/ufs-host-20261113/command.txt`; replay there with
WSL root `bash out/ufs-host-20261113/command.txt` from the device repository.
Clang `/opt/unixnu-linux/llvm/bin/clang-24` returned 0 with 19 warnings.
The isolated unmodified object is 498480 bytes, SHA256
`f673df6258caa1e41f84526ba054ddf7241961f2c42e899683ce54b2c88cac01`.
This compiles against headers; it does not establish the 20H392 class ABI.

The original `symbol-classification.tsv` is superseded by the exhaustive
symbol-by-symbol audit below; the 8796 unstripped nm hit alone is not an export.

VerifiedRoot is not removable merely because owner manifest is disabled:
with the official build defines, `NativeUfs.cpp:1698-1779` selects a signed
policy and calls `vr_open`, and `:1870-1884` calls `vr_verify_block` on the
read path. The six `vr_*`/`verified_root_*` symbols require the corresponding
VerifiedRoot implementation, crypto and configured policy/key inputs. The
VirtioMmioBlock include supplies `VerifiedBlockPolicy.h`; this observation alone
does not establish that its driver object is required. Policy and root layout
must be independently qualified, not silently bypassed.

For startup, `NativeUfs.cpp:2138-2147,2251-2252` accepts nonzero
`native-ufs-root` only from an `IOPlatformExpertDevice` provider and invokes
`startRoot` when probe is zero. The official `patches/xnu/native-aes-personality.patch`
contains the `NativeUfsRoot` personality; its presence and execution in the
8796 final kernel are not established by this object. Separately, official
`scripts/unixnu/payload.py:56-73` rejects non-VMM native-root payloads unless
there is exactly `sheng-pmgr=2` and defined `_sheng_pmgr_run`. The nuwa bridge
instead uses `nuwa-pmgr` and `_nuwa_pmgr_run` (`package/NuwaPlatformPower.cpp:69-72`):
they are not interchangeable and renaming a string would not satisfy the
contract. That software bridge does not power UFS hardware. A future integration
requires a reviewed nuwa-specific gate and actual provider/consumer evidence.

Firmware UFS DXE loading does not prove that ExitBootServices preserves DMA
mapping, queues, ownership, clocks or PHY state. DMA/SMMU takeover and runtime
concurrency are outside this work item. VFS bridge prior independent evidence is
not rerun; APFS prelink and final kernel have not been built here.

## Symbol audit and remaining link inputs

`out/ufs-symbol-audit-20261113-r2/symbols.json` inventories all 269 imports;
SHA256 `f30f298237aee06693859a223fdb483a9cf0b19db04d93de48a617812e1b0068`.
Each entry records the native link-map object, native and current prelink
exports, donor parent and storage-module exports, provider, link condition and
gap. The r5 native and prelink SHA256 are respectively
`98c4f8bd18bbf0829846e191039811d5feba12ad7ad4a1082e0a9402bc3f4185` and
`62d3efb13d8fcf59fd38c5095cb0a33ca1ba6d109ea2e6aab285ffaaeb6f581a`.
246 have matching external native/prelink addresses and concrete link-map
objects. This does not mean the new object has been linked or its C++ ABI
qualified. The map SHA256 is
`90d1d88f1d1d694f0a219fd3e1c8c3c51180948b5bb4dea58de9d1bc60789e49`.

Five of the previous six unlocated symbols are defined globally by linked
objects but hidden from the final external exports: `_kmem_alloc_guard` and
`_kmem_free_guard` in `osfmk/DEVELOPMENT/vm_kern.o` (`osfmk/vm/vm_kern.c`),
`_nprocs` in `bsd/DEVELOPMENT/param.o`, and the add/sub minimal UBSan handlers in
`san/DEVELOPMENT/ubsan_minimal.o` (`san/memory/ubsan_minimal.c`). `llvm-nm -g
--defined-only` checked those objects. They can resolve in a static link retaining
the objects, not as exports from the already linked kernel. `_boot_progress_poll`
is an absent weak import in this object: `NativeUfs.cpp:46-55,1894-1896` tests it
before calling. Final linker handling is untested; if a definition is required,
the reviewed weak no-op must honor its nonblocking/no-transport contract. The
official source-storage builder documents a weak-default approach but is not an
8796 build.

The remaining eleven are the exact IOBlockStorageDevice symbols in the JSON.
The 20H392 donor SHA256
`2ec297bac95bcba01046fd0148e97e7e5885c05a6c18827f39f534ba375c1221`
contains `com.apple.iokit.IOStorageFamily` version 2.1, `Local-Root`, at
`/System/Library/Extensions/IOStorageFamily.kext`; its `IOBlockStorageDriver`
personality names `IOBlockStorageDevice` as provider. That bundle's Mach-O
external symbol table has zero entries: these eleven addresses cannot be
resolved by symbol name. This is a concrete binding gap, not evidence the class
is absent. Local `refer/IOStorageFamily/IOBlockStorageDevice.cpp` is a source
candidate. Official `scripts/audit-storage-interface.py` shows a reference-object
and vtable matching method, but its Darwin 23/iOS17 assumptions and results
cannot be transferred to 20H392. Same-donor annotation and constructor,
metaclass and vtable qualification are required before selecting a provider.

The six VerifiedRoot imports map to `kits/VerifiedRoot/src/verified_root.c`
(`vr_open`, `vr_verify_block`), `kits/VerifiedRoot/adapters/xnu_crypto.c`
(`vr_xnu_crypto`), generated `RootAnchor.c` (independent 395-byte trusted key;
`scripts/build-sheng-source-storage.py:160-166`), and an authenticated policy
array/count provider. `scripts/build-verified-root-probe.py:95-118` generates a
test-only explicit table. The production source builder lists device inputs
`SourceRootPolicies.cpp` and `SourceRootBinding.cpp` but refuses non-arm64e or
iOS <26; it is not directly usable for nuwa. A nuwa policy table and key have
not been established. This object enables `NATIVE_VERIFIED_BLOCK` and
`NATIVE_VERIFIED_BLOCK_MULTI_POLICY`, not `NATIVE_VERIFIED_POLICY_HANDOFF`, so
the policy header declares a **const** table and count. The adapter's SHA256 and
RSA functions are native exports; `ccoid_sha256` is a literal macro in this
8796 tree's corecrypto header. Build the real provider objects and inspect
their transitive imports before claiming closure. Crypto registration and
authentication were not exercised. The Virtio policy header is used, but none
of the 269 imports names a Virtio driver symbol; its object is not established as
an input to this object.

Reproduce with WSL Ubuntu-22.04 root, cwd
`/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa`:

```sh
/home/wh1stl3/.local/bin/python3.11 -B scripts/audit-nuwa-ufs-symbols.py --out out/ufs-symbol-audit-20261113-r2
```

Exit 0. The first attempt failed on non-UTF8 bytes in the link map; using
`surrogateescape` fixed the reader, then r1 and expanded r2 exited 0. This uses
the existing UniXNU XnuPrelink `native_prelink.py` parser from the pinned build
tree and `/usr/bin/llvm-nm`; the UFS object was not rebuilt. Next: qualify eleven
same-donor bindings and full class ABI; supply and validate VerifiedRoot objects,
const policy table and key; resolve weak observer handling and transitive imports;
then perform a separately reviewed native static link.

Independent verifier: rerun the command with a fresh `--out` and compare the
JSON, recheck object and donor hashes and provider nm, then run `git diff --check`
and the porting-record check with `--base origin/feat/step7-kernel-patches-8796`.

## Task A: current-donor storage binding contract (self-checked)

`out/ufs-storage-contract-20261113-r3/contract.json`, SHA256
`2ff52dd7508bfd023eed8d884840edb3e49235591f1cd5fd3425504975937443`,
supersedes only the eleven-address gap above. The NativeUfs object remains
`f673df6258caa1e41f84526ba054ddf7241961f2c42e899683ce54b2c88cac01`;
it was **not rebuilt**. Donor and r5 prelink hashes remain those above.
No final kernel link, driver enablement, hardware/device access, VerifiedRoot
change or second IOBlockStorageDevice implementation was made.

No matching reference was found in the current build/storage-abi tree or the
bounded device out/build/reports reference-object search. The new annotation-only
reference compiles the existing local IOStorageFamily source using the complete
NativeUfs command, replacing **only source and output paths**. Exact argv/cwd are
in `reference-command.json`; compile log is retained. Both objects' actual
LC_BUILD_VERSION is platform 2, minimum `0x110000` (**iOS17.0**), despite using
the 8796 source/build configuration. No version field or deployment flag was
rewritten. Reference SHA256 is
`0f21ffa4a747c6d3cb05fa5652b2e4f7c744fe72e8a4dc75190a9a72a67d8e27`.
It is never linked or executed. Output-path-bearing debug data means a fresh
verifier directory need not reproduce this reference-object hash.

### Eleven concrete annotations

All addresses below are hexadecimal; slot numbers exclude the two vtable header
words. Names are the reference's mangled annotations, not recovered donor exports;
the full exact symbols/signatures and all 190 donor/current targets are in JSON.
The public declarations return `bool` for init, `OSObject*` for getProperty and
`IOReturn` for the other five methods; mangled names alone do not encode these
return types. These are compiled-reference declarations, not donor debug types.

| Binding | Donor VA | Segment + offset | Current r5 prelink VA |
| --- | --- | --- | --- |
| slot 21 `init(OSDictionary*)` | `fffffff0055d9e30` | `__TEXT_EXEC+2e30` | `fffffff0045d9e30` |
| slot 33 `getProperty(OSSymbol const*) const` | `fffffff0055d9e88` | `__TEXT_EXEC+2e88` | `fffffff0045d9e88` |
| slot 44 `setProperties(OSObject*)` | `fffffff0055d9f38` | `__TEXT_EXEC+2f38` | `fffffff0045d9f38` |
| slot 185 `requestIdle()` | `fffffff0055da050` | `__TEXT_EXEC+3050` | `fffffff0045da050` |
| slot 186 `doUnmap(IOBlockStorageDeviceExtent*, unsigned int, unsigned int)` | `fffffff0055da05c` | `__TEXT_EXEC+305c` | `fffffff0045da05c` |
| slot 187 `doSetPriority(IOBlockStorageDeviceExtent*, unsigned int, unsigned char)` | `fffffff0055da068` | `__TEXT_EXEC+3068` | `fffffff0045da068` |
| slot 189 `doGetProvisionStatus(unsigned long long, unsigned long long, unsigned int*, IOBlockStorageProvisionDeviceExtent*, unsigned long long)` | `fffffff0055da08c` | `__TEXT_EXEC+308c` | `fffffff0045da08c` |
| `gMetaClass` | `fffffff007a091d0` | `__DATA+1d0` | `fffffff006a091d0` |
| protected `C2(OSMetaClass const*)` | `fffffff0055d9d98` | `__TEXT_EXEC+2d98` | `fffffff0045d9d98` |
| base `D2()` | `fffffff0055d9db8` | `__TEXT_EXEC+2db8` | `fffffff0045d9db8` |
| vtable (header) | `fffffff006c73f50` | `__DATA_CONST+12d0` | `fffffff005c73f50` |

These eleven exactly equal the preserved object's eleven storage imports.
`layout-bound-bindings.o` exports eleven N_ABS aliases checked by llvm-nm;
SHA256 `652cbe6d2c5b3b74937611e84f7f6e836acae0f83e07583021d9e5e2b97dd799`.
This is an **offline alias instrument**, not a linked provider or accepted
production archive. Any layout change requires recomputing donor-segment-offset
mapping against the new prelink; the script rejects a different r5 hash. The
historical `2bceb…` kernel and its addresses are never read or copied.

### Class and 190-slot evidence

The historical native class scanner is executed directly through an adapter to
the existing XnuPrelink parser, independently on this donor and r5 prelink. Three
metaclass constructors name `IOBlockStorageDevice`, load the actual exported
`IOService::gMetaClass` parent and pass instance size **0x90**. Reference DWARF
also gives 0x90. This is a static constructor/compiled-size check, not a captured
live OSMetaClass or instance observation.

C2 calls the actual IOService C2 import thunk, then stores the storage vptr
(`r5 0xfffffff005c73f60`) at `[x0]`. D2 is the separate instruction at
`r5 0xfffffff0045d9db8`, tail-branching through the IOService D2 thunk.
The adjacent abstract D1/D0 trap slots are **not** used as D2 aliases.
Both donor/r5 instruction records and thunk pointer targets are retained.

All **190** reference relocations match the actual table shape: **176**
kernel-resolved slots (162 inherited plus 14 pure-virtual), and 14 owned entries.
Each donor kernel target maps to the same named current native export; every
owned target maps to its actual IOStorageFamily segment offset. The entire
83,976-byte storage executable matches donor bytes except declared prelink
pointer bindings. NativeUfsBlock has 190 slots, no pure-virtual target and **23**
own overrides: 0, 1, 7, 14, 86, 168-184, 188. Other slots, including the seven
method imports above, retain their reference signatures. Non-destructor override
signatures are compared after demangling; full rows retain both signatures.
Public-reference naming of stripped owned entries remains an annotation, not a
proof of every donor method's complete semantic/type ABI.

Four real in-memory mutations of the current prelink were executed and rejected:
wrong parent (`Parent identity`), inconsistent class size, replacing the actual
D2 branch with RET (`Base destructor tailcall`), and replacing slot 2 with zero
(`Unique actual storage dispatch required`). This reuses the historical bounded
negative cases, not a rerun of the old full transport matrix.

### Reuse provenance and reproduction

- `UniXNU/UniXNU@693f5d9cae8a408dd18b39f3f9fdc4228c934241`,
  BSD-2-Clause-Patent: official `audit-storage-interface.py` identification method.
- `UniXNU/XnuPrelink@f1d80d37528a33e24643583787123c652b70a268`,
  BSD-2-Clause-Patent: existing `native_prelink.py` parser; no new Mach-O parser.
- `wh1stl3/UniXNU-nuwa@378a27b24318cc34e9b67b034ceccff8496fe774`:
  historical `audit-ios16-storage-class.py`, `audit-ramblock-production-abi.py`,
  `build-ramblock-analysis-archive.py` and read-dispatch helpers. No repository
  LICENSE was found; no external redistribution license is asserted.
- `UniXNU/ShengUfs@99d8bcd3e43dd24fc3c8437c67b5d4cc71ab94d0`,
  BSD-2-Clause: preserved object/source input, no reimplementation or rebuild.
- `apple-oss-distributions/IOStorageFamily@e45fbe30a7879e0b16e26dddb78538f1b00e0bff`,
  APSL-2.0: existing local source/headers for annotation only, not a second linked
  provider. Header hashes and TargetConditionals provenance remain recorded.

Self-check command (WSL Ubuntu-22.04 root, device repository cwd):

```sh
/home/wh1stl3/.local/bin/python3.11 -B scripts/audit-nuwa-ufs-storage-contract.py --out out/ufs-storage-contract-20261113-r3
```

Exit 0. Initial r1 stopped at new script line 191 because the dwarfdump executable
path was wrong; corrected to existing `/usr/bin/llvm-dwarfdump`. r2 and final r3
exited 0; final r3 includes independent donor identification, all-slot relocation mapping
and complete storage-executable preservation check. No download was attempted.
Independent verifier must rerun the final command with a **fresh** `--out`,
compare all eleven binding records, 190 slot rows and four rejected negatives,
recheck preserved NativeUfs/donor/prelink hashes, and run the record/diff checks
above. Runtime registration, complete private ABI, final integration/link and
storage readiness remain unverified; acceptance stays with the parent.

Final local checks: script AST and porting TOML parsing exit 0; `git diff --check`
exit 0; official porting-record check with the base above exited 0 and reported
14 structured areas. These are self-checks, not independent verifier results.

## Task B: isolated VerifiedRoot providers (self-checked)

Reused `UniXNU/VerifiedRoot@974f043d0c71ba2e60331483a41c6c6d35274ee3`,
BSD-2-Clause-Patent, unmodified `src/verified_root.c` and `adapters/xnu_crypto.c`.
The existing 8796 `bsd_init.o.json` C compile recipe was adapted as in the
official probe, without invoking or changing the guarded iOS26 storage builder.
Both Mach-O objects are ordinary ARM64, platform iOS, minimum 17.0, not arm64e.
Compilation exited 0 with warnings, including the existing missing libsa include
directory. This deployment field does not prove iOS16 runtime compatibility.

Ignored output `out/verified-root-provider-20261113/` contains exact commands,
logs, symbol listings, `audit.json`, and:

| Artifact | SHA256 |
| --- | --- |
| `verified_root.o` | `ac8382699bc15233bd78268127e1cdcf57ff6bfedc3d91a35a4707de427e72e6` |
| `xnu_crypto.o` | `2ada0890701a1487943666cca8c5456132370d68eab793e7beee6c6a66b319b6` |
| `libVerifiedRootProviders.a` | `144ea75698720db92f523ab7bf72cba78f619951646aff0d28f6cf8a1dc908f4` |

The preserved NativeUfs object remains `f673df6258caa1e41f84526ba054ddf7241961f2c42e899683ce54b2c88cac01`. The new objects define
`_vr_open`, `_vr_open_header`, `_vr_verify_block` and `_vr_xnu_crypto`.
Their eight undefined symbols map by matching native export address and link-map:
`___stack_chk_fail`, `___stack_chk_guard` to `stack_protector.o`;
`_SHA256_Init`, `_SHA256_Update`, `_SHA256_Final` to `corecrypto_sha2.o`;
`_rsa_make_pub`, `_rsa_verify_pkcs1v15` to `corecrypto_rsa.o`; and `_bzero`
to `bzero.o`. These are static provider matches, not a link or crypto runtime test.

Three original imports remain without inputs: `_verified_root_key`, a separately
trusted 395-byte public anchor; `_verified_root_policies`, a const array of
`{const uint8_t *manifest; uint64_t manifestBytes;}` pointing to genuine signed
policy material; and `_verified_root_policy_count`, a const `uint64_t` matching
that array. The selected OS/SystemOS images, their image digests and actual volume
identities, signed manifests and independently trusted owner public anchor must
be established and verified together; signing requires an authorized matching
owner private key, or already signed verified material. No private key was read,
generated or copied. Mutable handoff is incompatible with this object's const
contract. No six-import closure or final kernel link is claimed.

Bounded input search: `UniXNU/profiles/os/ios-16.7.16-20H392/profile.toml:20-28`
names OS `087-86698-044.dmg` (4730814044 bytes) and optional SystemOS
`087-86593-047.dmg` (2743074816 bytes), but fetch selects only KernelCache,
DeviceTree and StaticTrustCache; its root UUID is the explicit placeholder
`REQUIRED_ROOT_VOLUME_UUID`. The existing `UniXNU/out/ipsw/20H392/` holds
`kernelcache.decompressed`, DeviceTree and `087-86698-044.dmg.trustcache`, not
either named image or the full IPSW. That trustcache is not the OS image.
The WSL build tree's `.cache/firmware` points to the device repository cache;
the targeted cache and `UniXNU/build/verified-root-20H392` did not provide root
images, signed policy or owner-key metadata. No whole-machine absence is claimed.
Historical Image4 test certificates/keys are unrelated and not a root owner anchor.
Ask for the selected nuwa root image(s), actual volume UUID(s), and existing
authorized matching signed policy/public anchor or owner signing arrangement.

Official `tests/check.py:20-36` generates private test keys and signed synthetic
input, so it was not run under the no-key-generation scope. The official probe
also requires verified image/signature inputs; no authentication test was faked.
To reproduce in a fresh ignored directory, copy `build.py` there and run it with
WSL root `/home/wh1stl3/.local/bin/python3.11 -B <fresh>/build.py`; compare
symbols, source hashes, recipe and archive members (debug output paths can change
object hashes). Independent verifier should rerun this build, inspect the map and
exports, recheck preserved NativeUfs SHA, and rerun diff/record checks below.
