# 20H392 Libm pool escape: bounded stop (self-checked)

**INCONCLUSIVE / no qualification.** The first bounded pass finds additional
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
  Exit 2 denotes inconclusive, not a pass. JSON includes complete module list
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

The script stops tracking at a write to the ADRP register, including ADD to
the same register; it does not follow the resulting slot pointer, reconstruct
all stores or their values, inspect `__mod_init_func` / kmod start, or prove
function entries. Direct ADR uses are not tracked. Thus the two slot hits are
not a complete writer inventory. A1, A2 and A3 are **not established**; no
runtime, ABI, or device conclusion follows. The incomplete implementation is
explicitly fail-closed and exits 2.
