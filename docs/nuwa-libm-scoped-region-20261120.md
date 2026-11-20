# 20H392 scoped Libm qualified data region — self-checked

Pending reviewer **方案 B 审查，未经 deep_reviewer**. This is a qualified
data region, not a bypass ledger entry, runtime qualification or device release.

## Identity and implementation

XnuPrelink `f1d80d37528a33e24643583787123c652b70a268`,
`emit_prelink.py` SHA256 `c3eddb81759dd4511c2f77a6fc3f2cf22282f29bd3688ded7855599d98405439`.
Device-side `scripts/scoped_libm_emitter.py` applies a pinned in-memory source
transformation; the base remains read-only. It preserves `pc_relative_target`
and adds one exact range through the existing `literals`/`known_inline_data`.
Binding requires donor SHA256
`2ec297bac95bcba01046fd0148e97e7e5885c05a6c18827f39f534ba375c1221`,
module `com.apple.kec.Libm`, `__TEXT_EXEC` VA `0xfffffff005b8b000`,
region `[0xfffffff005b8c054,0xfffffff005b8c51c)`, file offsets
`[0x1740054,0x174051c)`, size 1224, and full SHA256
`12d22dca8e3a79e476ab128f73e28f630bf902d5189ed1d5317589930c0c8622`.
Original refusal was `0xfffffff005b8c1cc`, word `0xf09d5f48`.
`register_dataflow_qualified` remains false.

Previous bounded 33-candidate classification: 20 literal reads, 5 ADR data
reads, 3 pool-internal self-decodes, 3 x0 return escapes, and 2 live aliases at
unconditional branches. These are candidates, not proof of dataflow closure.

## Mechanical gate

`python3 scripts/gate-libm-data-region.py --base /mnt/d/Code/PortingiOS/UniXNU`:
221 parsable kexts plus parent `__TEXT_EXEC`; outside source → inside target:
direct branches 0, ADR 10, ADRP 0, literal 20. Libm `LC_FUNCTION_STARTS`:
absent, not a positive function-start test. `LC_SYMTAB` has `nsyms=0`, so no
N_SECT symbols including locals and no data label at the start. The script
fails closed if this metadata changes. `__PLK_TEXT_EXEC` parent gaps are not
covered.

The following are all 17 direct branch decodings with source in the region,
without asserting they are executable. Columns are PC, word, target:

```
0xfffffff005b8c07c 0x37cc7355 0xfffffff005b84ee4
0xfffffff005b8c088 0x36364fed 0xfffffff005b88a84
0xfffffff005b8c294 0x54000000 0xfffffff005b8c294
0xfffffff005b8c32c 0x34ddc0db 0xfffffff005b47b44
0xfffffff005b8c414 0x35000000 0xfffffff005b8c414
0xfffffff005b8c43c 0xb53361de 0xfffffff005bf3074
0xfffffff005b8c44c 0xb53361de 0xfffffff005bf3084
0xfffffff005b8c45c 0xb53361de 0xfffffff005bf3094
0xfffffff005b8c470 0x37db6c52 0xfffffff005b931f8
0xfffffff005b8c480 0x37db6c52 0xfffffff005b93208
0xfffffff005b8c490 0xb7b24eb5 0xfffffff005b90e64
0xfffffff005b8c4a0 0xb7b24eb5 0xfffffff005b90e74
0xfffffff005b8c4b0 0x37ab6295 0xfffffff005b93100
0xfffffff005b8c4c0 0xb78275a9 0xfffffff005b91374
0xfffffff005b8c4d4 0x96540c13 0xffffffefff08f520
0xfffffff005b8c4dc 0xb49e3a5b 0xfffffff005ac8c24
0xfffffff005b8c4ec 0x9499342c 0xfffffff0081d959c
```

## Strict emit and controls

`python3 scripts/test-scoped-libm-emitter.py --base /mnt/d/Code/PortingiOS/UniXNU`
uses actual display native SHA256
`c690783526424828e23aae3e279f0db0b0141bb60af21a98233c13162b9a7c1c`,
the board roots plus IOMobileGraphicsFamily and slide `-0x1000000`.
The actual strict `emit` returns SHA256
`c18372f79e9a6eaa94172b05c0d41eb444fbbc3c53d26289a69452a6397a43f2`;
all 1224 emitted bytes equal donor bytes, and the output is not persisted.
This is not a full build or device test.

The affected builder was also replayed with the real r35 inputs, CPU-only and
no-software-vsync, in fresh `out/nuwa-display-scoped-libm-20261120-02`; it
completed its linked audits and strict emitter, including its emitted-region
comparison. Native SHA256
`c4578fcc56b9e28b739674e7d846e51404923f17fc7e69ec82ca02e056055c51`;
emitted SHA256
`6736e4aebcf706ac51f31edf7b06d64643c6849452b8c632a854cd9f11b1e74f`.
The first invocation failed before linking because PowerShell expanded the
shell variable in the CPO argument to `/iokit/DEVELOPMENT/IOPMGR.cpo.json`;
the replay used the explicit recorded CPO path.

All controls were rejected: region-byte flip; injected outside external branch;
external ADRP immediately before and after; same bytes with different module
and with different segment VA; different donor SHA. For byte mutations the
test intentionally binds the changed full donor digest in memory, except for
the donor-SHA control, to exercise the range hash and outside instruction
checks independently rather than passing solely due to changed donor identity.

Dataflow remains unproven: the three x0 return paths and two alias callers are
not closed. IOAudioCodecs 27 BL sites are a superset observation, not 27 proven
pool-address callers. The parent `__PLK_TEXT_EXEC` gaps remain unscanned.
