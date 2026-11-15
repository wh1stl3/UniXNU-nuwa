# PMAP normal-RET observer component (2026-11-11)

Latest normal native/pristine-prelink checkpoint: [new layout evidence](pmap-ret-native-layout-20261111.md)
(self-checked; renderer and branch binding still pending). Component-only notes below are historical scope.

Subsequent [renderer/two-B host candidate](pmap-ret-diagnostic-20261111.md) is now self-checked;
the frozen pristine layout was independently accepted, but the new control flow still awaits independent review/verifier.

Status: **self-checked**, unbound component only; no native/prelink/payload build,
device access, network, commit, base edit or owner-wrapper edit. Deep brief
`ses_e39aecf93ffeDFlaanMmAthY5L` authorizes only the single normal-RET truncation.
Final integration/acceptance remains with the parent; independent verifier and
final-layout review are still required.

## Component contract

Source: `package/diagnostics/pmap-ret-observer.S`. Exported symbols:

| Symbol | Object section / offset |
| --- | --- |
| `_nuwa_pmap_ret_observer` | `__TEXT,__text +0` |
| `_nuwa_pmap_ret_observer_renderer_branch` | `__TEXT,__text +8` |
| `_nuwa_pmap_ret_observer_message` | `__TEXT,__cstring +0` (object address 12) |

The entire text is 12 bytes: `ADRP x0,message@PAGE; ADD x0,x0,message@PAGEOFF;
B .`. Only x0 is changed; SP is untouched (preserves, does not establish, the
required incoming 16-byte alignment). No stores, scratch, calls, threads,
allocation, init registration or caller return. The 53-byte NUL-terminated text
is exactly `DIAG: PMAP initializer normal epilogue reached; STOP`, no format
placeholders. PAGE21/PAGEOFF12 relocations refer to this object's defined
message, not an old native address/slide. No undefined symbol is retained.

The exported branch is the **single final-layout binding slot**, initially word
`0x14000000` (B to itself), not a renderer symbol/stub/cave. This is the minimal
representation of the approved “final B after layout” interface, not a second
hook. Unbound execution stops on this path without printing or resuming boot;
the artifact is not startup-approved. There is no global init interception or
guarantee about other paths. A future packaging gate must reject an unbound
slot; this task does not implement/claim that owner-wrapper gate.

Object `__cstring` uses `S_CSTRING_LITERALS=2` in `__TEXT`; text flags are
`0x80000400` (pure/some instructions). This establishes section intent only,
**not** final segment read-only/RX permissions. Final-link map and segment
permissions must be checked before binding.

## Recipe/config interface and pending board integration

`build-nuwa-pmap-ret-observer.py` defaults to recipe cwd as tree and
`tree.parent/.config`; it consumes only explicit
`CONFIG_XNU_NUWA_PMAP_RET_OBSERVER=y` (last assignment wins). Disabled/missing
switch returns before tool/source discovery or output creation, and leaves
existing outputs untouched. Missing config is an error, not implicit enable.
An environment switch cannot enable it. Disabling an already configured
diagnostic also requires removing its extra linker flags/selecting baseline
defconfig; the builder intentionally does not delete stale outputs.

Enabled outputs: `tree/build/nuwa-pmap-ret-observer/{pmap-ret-observer.o,
libNuwaPmapRetObserver.a}`. Source resolves via normal
`tree/kits/nuwa/diagnostics` mapping, falling back to
`$UNIXNU_DEVICE/package/diagnostics`. Tool defaults follow Linux's existing
`UNIXNU_TOOLCHAIN` / `CROSS_CLANG` / `CLT_PREFIX` contract. No downloads/setup.
The archive contains just this object, made by cctools libtool `-static`.

Read-only base interface checked:

- `scripts/unixnu/config.py:82–107`: quoted strings accepted verbatim, no
  additional escaping needed for the diagnostic linker flag string.
- `scripts/unixnu/kernel.py:17–26`: `{tree}` expansion in XNU environment.
- `kernel.py:141–167`: archive recipes run with tree cwd and UNIXNU_DEVICE;
  inherited `profiles/arch/arm64/configs/common.config:1` enables archive build.
- `scripts/unixnu/tree.py:65–92`: device package maps to kits/nuwa and device
  scripts are copied to tree scripts.
- `scripts/build-xnu-4k-baseline.sh:773–780`: existing extra archive link input.

`configs/nuwa_pmap_ret_defconfig` retains all current nuwa baseline options and
appends the gate plus the complete value:

```text
CONFIG_XNU_EXTRA_LD_ARCHIVES="-Wl,-force_load,{tree}/build/nuwa-pmap-ret-observer/libNuwaPmapRetObserver.a -Wl,-u,_nuwa_pmap_ret_observer -Wl,-map,{tree}/build/nuwa-pmap-ret-observer/native-link.map"
```

Parser and expansion were actually tested; full clang-driver/native linker
consumption was **not** run. Paths used here have no whitespace. Extra archive
flags replace rather than append another CONFIG value: parent must merge any
future diagnostics' inputs deliberately.

Pending exact board hunk (do not apply until owner wrapper completes; retain
the entire other archive list, do not replace it):

```diff
@@ [kernel] archives = [
   "component:ArmCpu",
+  "build-nuwa-pmap-ret-observer.py",
 ]
```

Future isolated configuration entry, **not executed in this task** (Linux cwd
at approved active UniXNU base; use a new dedicated ext4 out root):

```sh
./unixnu defconfig nuwa_pmap_ret_defconfig -D /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa --out /root/nuwa-pmap-ret-native-20261111
./unixnu tree -D /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa --out /root/nuwa-pmap-ret-native-20261111
```

Do not use `release` or `--os`: those can reselect the per-OS defconfig. Resolve
dependencies only from approved existing caches (no fetch authorized here).
Future native order: normal bootstrap compile records if required → normal
ordered archive recipes including this builder → normal native link with
extra archive/map flags → resolve fresh observer/message/slot symbols and
sections → independent layout/PMAP epilogue review → bind the sole original
normal RET to B observer and sole slot to B renderer **ordinary entry** →
audit before any subsequent packaging. Prelink/renderer placement may alter
layout: bind using the actual consuming final image and recheck after every
layout transformation; no historical `fb1e…` or other old address may be reused.

Extra archives are not added to `KERNEL_ARCHIVE_DEPENDENCIES` by this existing
interface. First run needs a fresh isolated tree; later object/archive changes
require **explicit native relink**, not an assumed incremental make rebuild.
Parent must arrange the normal relink mechanism and record it; none was run.

Future binding gates (outside this implementation): preserve full original
PMAP body/canary/restores/error paths; verify the unique normal RET opcode and
aligned SP at that site; both B deltas 4-byte aligned and in signed imm26 range
[-2^27, 2^27-4] bytes, no BL/veneer/new cave; verify renderer entry accepts x0
and is nonreturning fail-stop (not interior +33 bytes or an assumed native
symbol); audit string placement/read permissions, ADRP reach and fixups in
final image. No manual Mach-O segment expansion. Bind both branches together
or reject. Text absence cannot uniquely identify which earlier path failed;
positive text means only normal PMAP epilogue reached, not authentication or
later init/boot success. STOP applies only to the diverted current path.

## Actual self-check and evidence

Windows launch cwd: `D:/Code/PortingiOS/nuwa/UniXNU-nuwa`.
Linux Python cwd: `/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa`.
Final command (exit **0**):

```powershell
wsl -d Ubuntu-22.04 -u root --cd /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa -- /home/wh1stl3/.local/bin/python3.11 -B scripts/test-nuwa-pmap-ret-observer.py --base /mnt/d/Code/PortingiOS/UniXNU --out /root/nuwa-pmap-ret-observer-component-20261111/selfcheck-final
```

The test imports the actual base parser/xnu_env read-only with Python bytecode
writes disabled. It builds only this component in its own ext4 cache, checks
arm64 subtype 0 / MH_OBJECT, exact 3-instruction whitelist, symbols/sections,
two local message relocations, no undefined/init/data sections/runtime calls,
real archive member extraction byte identity, config retention/flag expansion,
enabled cwd/env and mapped source routes, disabled clean and stale-output
immutability, absent switch and last-assignment behavior. Recipe child commands
(exact cwd/argv/exit/stdout/stderr) are in `selfcheck-final/result.json`.

Tools: existing `/opt/unixnu-linux/llvm/bin/clang` 24.0.0git
(`58c46bae21181fb4240cf964461bea738d96d50e`),
`/opt/unixnu-linux/CommandLineTools/usr/bin/libtool`, `/usr/bin/llvm-ar`.
Initial tool discovery found no llvm-ar/llvm-objdump in the installed custom
LLVM bin (ls exit1); existing system LLVM14 tools suffice, no installation.
Initial component check `selfcheck-01` exit0; final check adds explicit missing
switch/environment rejection and inherited archive-enabled assertion.
Additional initial-object `llvm-objdump --macho --disassemble --reloc --syms`
and cctools `nm -u <archive>` both exit0: three instructions as above, only
message relocations, empty undefined list.

Mirrored ignored evidence root:
`out/pmap-ret-observer-component-20261111/` (result, object, archive).
No final native map exists; renderer ABI/termination, final RX/RO layout and
actual binding remain unverified, not assumptions promoted to success.

Independent verifier should rerun the exact final component test with a fresh
`--out /root/nuwa-pmap-ret-observer-component-20261111/verifier-final`, plus
`git diff --check` and scoped file review. Do not run native/prelink/payload or
device commands under this brief. All results here remain **self-checked**
until that independent rerun; parent retains integration and acceptance.

## Relocation-field review follow-up (2026-11-11)

Parent reports component review and independent verifier **PASS WITH
CONDITIONS**, accepting the unbound component. This follow-up changes only
the object-inspection test and this note; observer/builder/config semantics
are unchanged. The incremental result below is **self-checked**.

The test now decodes both relocation records and resolves their symbol-table
indices to the actual defined message symbol. It requires exactly:

| Offset | Type | external | pcrel | length | Target |
| --- | --- | --- | --- | --- | --- |
| 0 | PAGE21 (3) | 1 | 1 | 2 (4 bytes) | `_nuwa_pmap_ret_observer_message` |
| 4 | PAGEOFF12 (4) | 1 | 0 | 2 (4 bytes) | same |

It also checks index bounds and that the message is external N_SECT at the
start of `__cstring`, not an undefined or different-section symbol. Decoded
relocation fields are included in the inspection result.

Incremental check reused the preserved `selfcheck-final` object (no component
rebuild). Windows launch cwd `D:/Code/PortingiOS/nuwa/UniXNU-nuwa`; Linux cwd
`/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa`. Actual command, exit **0**:

```powershell
wsl -d Ubuntu-22.04 -u root --cd /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa -- /home/wh1stl3/.local/bin/python3.11 -B out/pmap-ret-observer-component-20261111/reloc-fields-selfcheck-20261111/check.py
```

Positive object passed; seven one-field mutation negatives were rejected:
offset, target, pcrel, length, external, type, out-of-range target index.
New ext4 evidence:
`/root/nuwa-pmap-ret-observer-component-20261111/reloc-fields-selfcheck-20261111/result.json`.
Ignored Windows evidence/script use the matching new suffix under
`out/pmap-ret-observer-component-20261111/`; all prior evidence remains intact.
An initial inline PowerShell/WSL `python -B -c` invocation returned exit1 with
no diagnostic/output; it is not counted as a test pass. The explicit saved
script command above produced the actual check result.

No board read/change, native/prelink/device/network operation or integration.
No repeated independent verification is claimed for this test-only increment;
if requested, verifier can rerun the saved script using a fresh ext4 output
suffix. Final linked relocation/address binding still needs its independent
audit after the other owner freezes packaging and parent integrates wiring.
