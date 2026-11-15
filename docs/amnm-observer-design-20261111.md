# AMNM observer: preliminary host design (2026-11-11)

**Status: partial record primitives only; no complete observer, kernel or device result.**
This record does not approve a boot or establish a runtime callee or CPU identity.

## Local frame evidence

The frozen `renderer-baseline.macho` SHA256 is
`7fd3d933aae66d8e34a0d3ebfa142137978976d7521e04cef20321109750b6f4`.
Its initializer at `46e98cc` subtracts `0x190` from SP and establishes FP as
SP+`0x180`. At `46e99d8`, `blr x8` returns to `46e99dc`. Conditional on
that call entering reader `46efe7c`, its prologue subtracts `0x40`, saves
caller FP/LR at reader SP+`0x30`/`0x38`, and establishes reader FP as SP+`0x30`.
The disassembled reader instructions through `46effb8` do not adjust SP; at
`46eff98` the original instruction is `cmp w8, #0`, at `46effb8` it is
`strb w8, [x19]`. At `46e9b04` the original instruction is `cbz w8`.
This is a conditional local frame relationship, not a claim about the dynamic
target or arbitrary control-flow corruption. Final linked sites must be found
and checked anew.

The read-only historical nuwa recovery capture
`../../.cache/device-evidence/20261107-recovery/cpuinfo.txt` lines 3, 12, 21,
30, 39, 48, 57 and 66 reports Linux `atomics` for all eight listed processors.
Capture SHA256: `4f4ece01e20466ffdd6300148c3d366c67a5fae52dcf526a7b6d49c3d7b28999`.
This is historical Linux capability evidence, not a test of an LSE instruction
in the new kernel. Assembly, target architecture flags, emitted opcode and
runtime applicability still require explicit checks.

## Proposed bounded record

Use one lifetime `next_sequence` counter, never reset by the initializer.
Every hook reserves one ticket using a single bounded atomic operation before
any shared payload writes. Tickets 16 and above do not address slots; a
snapshot observing a counter above 16 is overflowed. The bounded short-run
assumption excludes 64-bit wraparound; this is not an unlimited-run guarantee.
Every slot is immutable after a release commit of `ticket+1` and is never
reused. Store-site commit must follow the original byte store.

Do not silently drop fields to fit the nominal 64-byte slot. A straightforward
PRECALL record needs commit and event kind plus seven 64-bit fields (callee,
x0, id, output, SP, FP, original return), i.e. 72 bytes before further
alignment. The partial header uses 96-byte slots, a 128-byte header and a
256-byte summary, totalling 1920 bytes. The payload is not yet wired to hooks.
Record all INPUT and STORE arrivals, including mismatching IDs or outputs.

The panic reader takes an acquire counter snapshot, checks each committed slot
with acquire before reading payload, then takes a second acquire counter
snapshot without retry. Overflow, a missing commit or changed counter forbids
association. A later event after the second read belongs outside that snapshot;
the snapshot is not a claim that execution has stopped. Exactly one ordered
ENTRY/PRECALL/INPUT/STORE/BRANCH and all specified callee, id, output and frame
checks are required for a conditional association. All other cases remain
incomplete or independent events. Panic-screen single-winner arbitration is
separate from log publication.

## Outstanding implementation and review

No trampolines, archive, local renderer, configuration, linked kernel, ABI
equivalence tests, concurrency tests, or independent verification exist as a
result of this design record. Implementation must preserve original registers,
NZCV, SP, BLR LR, store and branch semantics and the ordinary/common panic
format/arguments, then exercise actual generated instructions, not only a
model. The parent must arrange the specified focused high-risk review and
independent verification before any device authorization request.
