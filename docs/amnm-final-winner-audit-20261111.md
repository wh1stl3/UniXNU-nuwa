# AMNM final winner range audit r3

**Self-checked only; not independent verification or device approval.** The
parent reports stage3 deep review PASS WITH CONDITIONS, with no required ABI or
publication-protocol remediation. This increment changes the audit only; the
kernel and build artifacts are unchanged. The independent verifier was reading
the previous audit, so the parent must freeze the new audit hash before its
final incremental verification.

Candidate SHA-256: `1754a89e8e92e20baafeaf0e1f98361b0d41ddaea8f420dd44d34d1357f2d162`.
Audit script before: `c3b0b7c14052f0720bcd51930052de13254b81de3559a4b10c0969f00322fd08`;
after: `1c55d23db13bb142a353a2ebdb3eeaa2b47cf1f91592624c93f79ecc8a265fcb`.
New result: `/root/nuwa-amnm-final-audit-r3-20261111/audit.json`.

The r3 audit resolves symbols from the actual final Mach-O, verifies their full
intervals are inside one `__DATA` RW/NX segment and one `S_ZEROFILL` section,
after the segment's file-backed end, outside `__BOOTDATA`, and mutually
non-overlapping. It does not infer runtime initialization from segment metadata.

| Object | Half-open virtual interval | Size |
| --- | --- | ---: |
| record | `[0xfffffff007a85cd8, 0xfffffff007a86458)` | 1920 |
| local panic text | `[0xfffffff007ac3940, 0xfffffff007ac4140)` | 2048 |
| panic winner | `[0xfffffff007ac4140, 0xfffffff007ac4144)` | 4 |

The reviewer closed the static loader initialization binding condition using
the existing independently accepted [fixed-r4 provenance chain](loader-r4-binding-20261111.md)
and the fixed-source check below. This increment did **not** re-extract firmware
or rerun that provenance verification. The r4 image SHA-256 is
`692cfcca51af81230fecbba15425cf598182fbe53abb362b6046dec0f24dc2e5`.

This increment ran read-only `git show` against `UniXNU/drivers/DarwinBoot`
commit `3c75734014cdab0acd9541e88057b7606ee7ae08`, not its working-tree
source. `DarwinBootPkg/Driver/DarwinBoot.c:149–158` reads and validates VM and
file sizes; `:169–184` computes the VM extent and checks segment overlap;
`:724–731` places supplementary ranges after that extent; `:732–740` bounds
`Used`, zeroes the window, then copies each segment's file bytes. This is a
static fixed-source contract, **not** proof that loader execution occurred.
For this candidate the `__DATA` zero-fill interval is
`[0xfffffff0079f4000,0xfffffff007ac8000)`, and `__BOOTDATA` starts at
`0xfffffff007ac8000`; the three table intervals lie inside it.
The parent-reported renderer total stack usage is **1776 bytes**; the snapshot
assertion `<=1600` is not the renderer's total stack. Local text-buffer
integration with the boot-progress banner is not established. Runtime page
tables, available stack margin, LSE execution, and display remain unverified.

Actual command, WSL cwd `/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa`, exit **0**:

```sh
/usr/bin/python3 -B scripts/audit-amnm-final.py --build-result /root/nuwa-amnm-stage3-native-20261111/build-result.json --manifest /root/nuwa-amnm-final-candidate-stage3-20261111/manifest.json --out /root/nuwa-amnm-final-audit-r3-20261111
```

Independent verifier should rerun that command with a fresh `--out`, verify the
frozen script and candidate hashes, and check the resulting three intervals.
No hook matrix was rerun for this audit-only increment.

An in-memory negative self-check using the actual parser and `check_zero_objects`
rejected three mutated winner addresses: overlapping the text buffer, crossing
the DATA end, and lying in file-backed DATA. It did not modify the binary or
replace independent verification. `/usr/bin/python3 -B` exited 0; the three
rejection assertions passed.
