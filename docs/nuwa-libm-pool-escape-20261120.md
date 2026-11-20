# 20H392 Libm pool escape: bounded stop (self-checked)

2026-11-20 scoped-region follow-up (self-checked, plan B review pending):
see `docs/nuwa-libm-scoped-region-20261120.md`; dataflow remains unqualified.

**NOT-QUALIFIED / no data-area qualification.** The first bounded pass finds additional
pool references and unresolved ADR uses; the requested exact-five criterion
is not established. Per stop condition, no whitelist or scanner change.
This is an incomplete candidate inventory, not a proof that the unresolved
references escape or are reachable instructions.

## Inputs and reproducibility

* Donor `D:/Code/PortingiOS/UniXNU/out/ipsw/20H392/kernelcache.decompressed`,
  SHA256 `2ec297bac95bcba01046fd0148e97e7e5885c05a6c18827f39f534ba375c1221`.
* Real display native
  `out/nuwa-display-ignore-loh-02/HOST-ONLY-display-native.unstripped`,
  SHA256 `c690783526424828e23aae3e279f0db0b0141bb60af21a98233c13162b9a7c1c`.
* Pool `[0xfffffff005b8c054,0xfffffff005b8c51c)`, SHA256
  `12d22dca8e3a79e476ab128f73e28f630bf902d5189ed1d5317589930c0c8622`.
* `build-nuwa-display-native.py:362–368` passes board roots plus
  `com.apple.iokit.IOMobileGraphicsFamily` to `emit`; it does not pass a
  profile or selection file. This audit calls the same `native_prelink.plan`
  against the real linked native and donor, at slide `-0x1000000`. The
  resulting 30 executable modules, their original bundle paths and load VAs
  are printed by the audit. This is the actual planner output, not a new
  selection policy. Kernel `__TEXT_EXEC` is included separately.
* XnuPrelink `f1d80d37528a33e24643583787123c652b70a268`;
  `native_prelink.py` SHA256
  `a2da7ea8a4431f6c26418ecab9be718c0fbd2f0aa2334ba8d32c2270d2ac81dc`.
  Capstone Python runtime `5.0.7`, pip package metadata `5.0.9`. Known ADR,
  ADD and LDP decoded as expected in a preliminary test.
* Re-run from this repo in WSL:
  `python3 scripts/audit-libm-pool-escape.py > /tmp/libm-audit.json`.
  Exit 2 denotes not-qualified, not a pass. JSON includes complete module list
  and raw hit table; output is not required for input or stored in Git.

## A1 candidate hits

All entries below are `com.apple.kec.Libm`. Addresses have common prefix
`0xfffffff005b8`. Literal loads are shown as raw candidates, **not** classified
as safe merely from their opcode. ADRs have unresolved subsequent use.
The three candidates located inside the candidate pool are decoded data
possibilities, not established instructions.

| PC suffix | target suffix | candidate |
|---|---|---|
| bc90 | c05c | ldr w3 |
| bc98 | c060 | ldr w3 |
| bca8 | c070 | ldr s2 |
| bcc0 | c054 | ldr w3 |
| bcd8 | c0c4 | adr x1, unresolved |
| bcf4 | c064 | ldr w3 |
| bd00 | c07c | adr x0, unresolved |
| bd44 | c078 | ldr s2 |
| bd48 | c074 | ldr s4 |
| bd6c | c058 | ldr w3 |
| bd74 | c060 | ldr w3 |
| bd84 | c070 | ldr s2 |
| bd94 | c068 | adr x1, unresolved |
| bdb8 | c07c | adr x1, unresolved |
| be0c | c088 | adr x1, unresolved |
| be50 | c054 | ldr w3 |
| be68 | c0c4 | adr x1, unresolved |
| be98 | c09c | adr x0, unresolved |
| becc | c064 | ldr w3 |
| bed8 | c088 | adr x0, unresolved |
| bf0c | c078 | ldr s2 |
| bf10 | c074 | ldr s4 |
| bf40 | c058 | ldr w3 |
| bf48 | c064 | ldr w3 |
| bf5c | c4c4 | ldr d2 |
| bf78 | c4cc | adr x1, unresolved |
| bfdc | c054 | ldr w3 |
| bff8 | c0c4 | adr x1, unresolved |
| c020 | c078 | ldr s2 |
| c024 | c074 | ldr s4 |
| c384 | c387 | adr x0, inside candidate pool |
| c394 | c397 | adr x0, inside candidate pool |
| c3a4 | c3a7 | adr x0, inside candidate pool |

Raw 4/8-byte scans of file-backed segments named `__DATA` and `__DATA_CONST`
returned no matching full pool or slot values. This does not cover all
coalesced parent data names or reconstructed/encoded pointers.

## A2/A3 candidates and limitations

| PC | target | observation |
|---|---|---|
| `0xfffffff005b8e980` | `0xfffffff007a3d488` | ADRP+ADD, subsequent use not traced |
| `0xfffffff005b8e9cc` | `0xfffffff007a3d490` | ADRP+ADD, subsequent use not traced |

Both in Libm. Initial slot values are `0xfffffff005b8b000` and
`0xfffffff005b8b008` respectively, both in Libm executable file backing and
outside the pool. Function-entry status is **unproven**.

In the initial pass the script stopped tracking at a write to the ADRP register, including ADD to
the same register; it does not follow the resulting slot pointer, reconstruct
all stores or their values, inspect `__mod_init_func` / kmod start, or prove
function entries. Direct ADR uses were not yet tracked. Thus the two slot hits
were not a complete writer inventory. A1, A2 and A3 were **not established**; no
runtime, ABI, or device conclusion follows. The incomplete implementation is
initial pass was explicitly fail-closed and exited 2. The continuation below
supersedes these initial method limitations where explicitly stated.

## Continuation: bounded address tracing (self-checked)

The current script carries address-register aliases through an ADD and
post-indexed data loads, for up to 16 instructions. Its output replaces the
earlier classifications in the table, but not the candidate addresses.
Of the 33 candidates: 20 literal reads; 4 ADR-derived data reads whose
tracked lifetime terminates in the bounded trace; 6 ADR-derived reads with a
remaining live address at a branch or the 16-instruction limit; and 3
pool-internal self-reference candidates. The last 3 are not demonstrated
instructions: treating them as data would assume the conclusion.

| ADR PC | observed uses | unresolved boundary |
|---|---|---|
| `0xfffffff005b8bcd8` | ADD `0xfffffff005b8bcdc`, LDP `0xfffffff005b8bce0` | branch `0xfffffff005b8bcf0`, address remains live |
| `0xfffffff005b8bd94` | LDP `0xfffffff005b8bd98` | conditional branch `0xfffffff005b8bdb4`, address remains live |
| `0xfffffff005b8bdb8` | LDP `0xfffffff005b8bdbc`, LDR `0xfffffff005b8bdc0` | 16-instruction limit, address remains live |
| `0xfffffff005b8be68` | ADD `0xfffffff005b8be6c`, LDP `0xfffffff005b8be70` | 16-instruction limit, address remains live |
| `0xfffffff005b8bf78` | LD1 `0xfffffff005b8bf7c`, `0xfffffff005b8bf80`, `0xfffffff005b8bf94` | conditional branch `0xfffffff005b8bfac`, address remains live |
| `0xfffffff005b8bff8` | ADD `0xfffffff005b8bffc`, LDP `0xfffffff005b8c000` | branch `0xfffffff005b8c01c`, address remains live |

The JSON has an instruction-by-instruction use list for every ADR. None of
the six table entries has an observed address escape in its bounded window;
the missing fact is what happens to its still-live alias beyond that window
or branch. The three interior candidates `c384/c394/c3a4` are raw decodings,
not proof of pool entry. This conservative result does not establish that
an actual escape occurs.

Slot path tracing now shows:

| path | actual instructions | writer evidence |
|---|---|---|
| start | `e97c` ADRP; `e980` ADD; `e984` LDR x2; `e988` CBZ; `e98c` BR x2 | read and indirect branch, **not** a store |
| stop | `e9c8` ADRP; `e9cc` ADD; `e9d0` LDR x2; `e9d4` CBZ; `e9d8` BR x2 | read and indirect branch, **not** a store |

PCs in the table have prefix `0xfffffff005b8`. The module has no
`__mod_init_func` section. Its `_PrelinkKmodInfo` is
`0xfffffff007a3d3c0`; the standard packed kmod start/stop fields at +180
are `0xfffffff005b8e97c` and `0xfffffff005b8e9c8`, respectively.
Neither local path writes a slot. The page-derived scan with ADD propagation
found no STR/STP to either slot, but is not a complete indirect-writer proof:
the exact missing fact is whether any selected code writes either slot
through a pointer obtained by another route, including passed parameters or
memory-derived aliases. No particular such writer has been established.

Libm has no `LC_FUNCTION_STARTS` and its symbol table has zero entries.
Each initial slot points to a distinct aligned `mov w0,#0; ret` two-word
stub, and each is used as the initial target of the respective start/stop
indirect branch. That cross-check supports the entry interpretation, but does
not provide function-start metadata or establish later slot values.

**Final qualification: NOT-QUALIFIED.** The six live-address boundaries
above and the unclosed indirect-writer set prevent proving no pool-address
escape or future control-flow target. The observed initial slot values being
outside the pool is insufficient. No whitelist, production scanner, device,
or runtime was changed or exercised.

## Continuation: 256-instruction CFG and donor-wide coverage

**Result: NOT-QUALIFIED.** This section supersedes the preceding six-boundary
classification. The ADR analysis now follows both sides of conditional
branches, through alias clobber, RET or an unconditional branch, up to 256
instructions. No pool-address argument to BL/BLR was encountered in these
candidate traces, so no pool-address callee was available to follow.

The 33 raw candidates now classify as 20 literal reads, 5 ADR-derived data
reads, 3 pool-internal possible self-decodings, 3 raw return-register
escapes, and 2 live aliases at unconditional branches. In particular:

| ADR | observed endpoint | fact and remaining question |
|---|---|---|
| `0xfffffff005b8bd00` | RET `0xfffffff005b8bd40` | x0 still contains `0xfffffff005b8c084` after post-index data read |
| `0xfffffff005b8be98` | RET `0xfffffff005b8bec8` | x0 still contains `0xfffffff005b8c0bc` after post-index data read |
| `0xfffffff005b8bed8` | RET `0xfffffff005b8bf08` | x0 still contains `0xfffffff005b8c098` after post-index data reads |
| `0xfffffff005b8bcd8` | B `0xfffffff005b8bcf0` → `0xfffffff005b8be78` | x0 and x1 remain live across the requested terminal |
| `0xfffffff005b8bff8` | B `0xfffffff005b8c01c` → `0xfffffff005b8bf70` | x1 remains live across the requested terminal |

The three RETs physically leave pool-derived values in x0. The routines
produce floating-point results, so this is **not** evidence that a caller
uses x0 as a pointer or branches to it; caller consumption is unproven.
Nonetheless it is an unclassified address escape under the requested
conservative criterion. No actual pool instruction fetch has been shown.

The scan now includes the parent kernel and all donor metadata entries with
file-backed non-resource executable images: 221 kexts plus kernel, with
zero unparsed modules. The 30 actually selected kexts are marked `selected`
in JSON; the other 191 are the donor-wide superset. JSON `scan_coverage`
lists every segment name, VA, file size and owner: 892 executable/data
segment observations, including overlapping parent coalesced data and
embedded module views. Raw scans cover file-backed `__TEXT`, `__DATA`,
`__DATA_CONST`, `__PRELINK_DATA`, `__PLK_DATA_CONST`, `__LASTDATA_CONST`,
`__KLDDATA`, and `__BOOTDATA`. There are no matching raw full-width pool or
slot pointers. A 4-byte raw word cannot equal these 64-bit addresses; encoded,
relative, reconstructed, or dynamically supplied pointers remain uncovered.
Executable scanning covers parent and kext `__TEXT_EXEC`; the parent
coalesced `__PLK_TEXT_EXEC` is covered only where an embedded kext owns it,
not its unowned gaps. Other parent segments are not treated as executable.

The slot-address scan reports only the two known ADD/LDR paths, **but cannot
establish that no other code materializes the slots**: it records 1078
slot-page tracking boundaries at calls or unconditional branches. One concrete
boundary is IOAVFamily `0xfffffff005b91010` (ADRP slot page), ADD
`0xfffffff005b91014` produces `0xfffffff007a3d8c8` in x2, then BL
`0xfffffff005b9101c` → in-image stub `0xfffffff005bedc98`; the stub loads
the pointer at `0xfffffff006dd3410` and branches to
`0xfffffff0076dfc74` (`OSMetaClass::OSMetaClass`, kernel symbol
`__ZN11OSMetaClassC2EPKcPKS_j`). This argument is not itself either slot,
and no store is established; its callee's full alias use is not audited.
The other boundaries likewise are not proven writers. Thus neither those
boundaries nor the unowned executable gaps may be presented as a clean
writer-absence proof. No scanner, whitelist, or device was changed.

## Continuation: candidate callers and tail paths

**NOT-QUALIFIED remains.** Libm has no `LC_FUNCTION_STARTS` and its
`LC_SYMTAB` contains zero symbols. Two instruction-shape/CFG entry
candidates cover the three ADRs, not three independently established entries:

* `0xfffffff005b8bc80`: `stp x29,x30,[sp,#-0x10]!; mov x29,sp`, reaching
  ADR `0xfffffff005b8bd00` and the shared `be78` tail. Its immediate
  predecessor `bc7c` is not RET; this prologue does not prove the entry.
* `0xfffffff005b8bd5c`: same prologue immediately after RET at
  `0xfffffff005b8bd58`, reaching ADR `0xfffffff005b8bed8` and the shared
  tail's `0xfffffff005b8be98`. Branch `0xfffffff005b8bcf0` also enters
  that tail; other entry paths are not excluded.

Donor-wide raw scanning finds zero direct BLs to either candidate. Two
distinct pointers in `com.apple.driver.IOAudioCodecs` `__DATA_CONST` are
`0xfffffff006f41448 → 0xfffffff005b8bc80` and
`0xfffffff006f414a0 → 0xfffffff005b8bd5c`; they are also seen through the
overlapping parent segment. Stubs `0xfffffff00667e7a0` and
`0xfffffff00667e824` load these into x16 and `br x16`. The scan finds 27 BLs
and zero direct B instructions to these stubs. IOAudioCodecs belongs to
the donor superset, not the 30 selected prelink modules.

The following table lists each BL; suffixes have prefix `0xfffffff006`.
Target A is `0xfffffff00667e7a0`, B is `0xfffffff00667e824`.
`N` = passed to the next known stub, whose initial target overwrites `w0`
with `s0` within four instructions; `K` = overwritten in the caller;
`R` = still live in x0 at caller RET. Multiple letters indicate CFG paths.
JSON records each exact terminal address/instruction.

| BL suffix | target | paths |
|---|---|---|
| 648330 | A | N |
| 648340 | A | N |
| 648350 | A | N |
| 648374 | B | N |
| 648380 | B | N |
| 64838c | B | K / N |
| 64b334 | B | R / K |
| 64c3e8 | B | R / K |
| 64de5c | A | N |
| 64de6c | B | N |
| 64de84 | A | N |
| 64de98 | B | K / N |
| 64dfb8 | A | N |
| 64dfc8 | B | N |
| 64dfe0 | A | N |
| 64dff4 | B | N |
| 64e00c | A | N |
| 64e020 | B | N |
| 64e038 | A | N |
| 64e04c | B | K / N |
| 65cd24 | A | N |
| 65cd34 | B | N |
| 65cd40 | A | K / N |
| 65cd70 | A | N |
| 65cd80 | B | K / N |
| 65ce10 | A | N |
| 65ce20 | B | R / N |

Path endpoints, not unique callsites: 25 N, 11 K, 3 R. R is observed at BL
`0xfffffff00664b334` → RET `0xfffffff00664b82c`,
`0xfffffff00664c3e8` → RET `0xfffffff00664c33c`, and
`0xfffffff00665ce20` → RET `0xfffffff00665ce48`. Next-level callers have
not been traced; no observed endpoint is a data-pointer read, storage, or
control-flow use. N assumes the slots retain their donor initial values;
the indirect-writer gap is not closed.

There are 167928 raw BLR-decoding word sites in scanned executable segments;
some may be inline data and register targets were not resolved. Thus the 27
calls are not an exhaustive BL/BLR caller set. For example,
`0xfffffff0071b42dc: blr x8` has an unresolved runtime target. Return to
the next caller and unqualified alternative entries also prevent closing
the three return-address cases. CFG tracing is bounded to 256 instructions
per path and is static evidence only.

ADR `0xfffffff005b8bcd8` goes through B `0xfffffff005b8bcf0` to
`0xfffffff005b8be78`: the derived x0 is overwritten by ADR `be98` before
data loads `be9c`/`bea0`; the prior x1 alias has no observed use on that
tail before RET `bec8`. The new x0 is the separate `be98` return case.
ADR `0xfffffff005b8bff8` goes through B `0xfffffff005b8c01c` to
`0xfffffff005b8bf70`: x0 was overwritten by `fcvtns x0,d4` at `c00c`,
and x1 is overwritten by ADR `bf78`, then used for LD1 data reads at
`bf7c`, `bf80`, `bf94`. Neither tail demonstrates control-flow use of
the original aliases.

Capstone runtime 5.0.7 reports `lsl x0,x8,#3` at
`0xfffffff0066483bc` as reading and writing x0; its decoded source is x8,
so it overwrites x0. The caller classifier explicitly corrects this LSL
form; other Capstone access metadata has not been independently qualified.
