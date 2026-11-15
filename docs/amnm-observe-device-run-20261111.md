# AMNM observer execution profile — host only

**Executor incremental ordinary reviewer PASS; independent verifier final
notification pending. No device command, real authorization, run or claim.**
This is not an authorization request; applicable safety review gates remain.
Default STOP and explicit continuation profiles retain their previous pins and
state machine. AMNM is opt-in `amnm-observe-20261111-r1`; all three phases retain
their own authorization and one-shot claims. Full per-run stock backup and
readback remain mandatory; historical backups are not reused.

## Frozen identity

The run identity binds run ID, profile, paths, sizes and these full SHA-256s:

| Item | Bytes | SHA-256 |
|---|---:|---|
| `out/amnm-observe-20261111-r1/vendor_boot.img` | 100663296 | `c5784135e3bb03e371808510dc0031fe3641782fd5fedf852fd7401783c0ddef` |
| `out/amnm-observe-20261111-r1/payload.img` | 67108864 | `7074311dc2e2d3e0e71432b150a4bbef557625e27412a98b1464a7736f11c1fa` |
| kernel | 55402496 | `1754a89e8e92e20baafeaf0e1f98361b0d41ddaea8f420dd44d34d1357f2d162` |
| ADT | 13256 | `885094de4597fb2d1734ba4092c805968097d021c8f482653b238436586d27a4` |
| r4 | 1495040 | `692cfcca51af81230fecbba15425cf598182fbe53abb362b6046dec0f24dc2e5` |
| expected stock B | 100663296 | `493ca426964adabb195a00ded4ff49793bc7efd5d7bea2a567bcfd0c970a8dad` |

Arguments are exactly `-v serial=3`. Prepare/boot check actual outer, FAT,
r4 and these frozen evidence bytes before directory/lock/claim/device access:

- derived record `out/amnm-observe-20261111-r1/derived-record.json`:
  `0b26d1f64b417882307b3dd904a95c19d19068e7a56613950156162ecd78e888`.
- package report `out/amnm-observe-20261111-r1/report.json`:
  `410471b127632260331325bc8d326f2d9cb23089d1079ce1cc935c0a3bee8d1d`.
- implementation self-check audit `out/amnm-package-audit-r2-resume-20261111/audit.json`:
  `cb64eeedd79b71e0e1f0b4982b81fa69b1bd2fc3529e05a8f027c1374cdcda2a`.
- audit source `scripts/audit-owner-amnm-observe.py`:
  `283507b2cc44dc9c678c0a64d4d3f4def548681b6a9270e3b9dd88d206d42e48`.

Their shapes and shared identity are checked; the actual outer-to-FAT/member
chain is reused from that audit, not re-extracted at every phase. See
`owner-amnm-observe-20261111.md` for the provenance and historical digest
witness limitation. The package audit's 14 negatives and actual chain have
independently passed, as reported by the parent; the pinned file above remains
the implementation's self-check report, not the independent report. This is
the actual derived format, not a schema2 or
continuation record. Restore checks identity and this run's backup only; missing
candidate, FAT, r4, audit or record must not block restoration. Existing
consumed runs are not migrated or replayed.

## Observation contract

If display and space permit, expect the original panic followed by an AMNM
snapshot summary. `C` is the pair of sampled sequence counters; `L` is the
loss bitmask; `I=1` means association passed the snapshot checks, `I=0` means
it did not. Only without loss are `U` (input u32), `S` (stored byte), and `B`
(branch input u32) emitted. Values are hexadecimal. On loss, events remain
independent; no causal association is inferred. No panic, no snapshot, or no
recovery does not establish success. This says nothing about authentication or
later stages; see `package/diagnostics/amnm-record.c:17-87,104-122`.

Future use requires new user authorization and applicable review/verification.
At most one boot: record video, observe, manually return to fastboot, then use
the separately authorized restore phase. Do not retry or infer automatic
recovery. Device identity, slot, backup, readback and failure-stop gates remain
unchanged.

## Self-check and independent rerun

WSL Ubuntu-22.04 root, cwd `/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa`:

```sh
/home/wh1stl3/.local/bin/python3.11 -B scripts/run-pmap-ret-once.py --self-check
```

Exit 0; 93 total synthetic test groups, not 93 new groups; real subprocess
device execution trapped. File checks in those groups include mocks and fault
injection and do not all read the actual package files.
Also ran AST parsing, actual host-only `Run.host_inputs()` with a trapping
runner, and nine CLI dry runs (three profiles × three phases), all exit 0;
each dry run reported zero device commands and created no run directory.
`out/amnm-executor-selfcheck-r3-20261111/` holds selfcheck, nine results and
source hash. Mock hashes/returns are not real device verification. Earlier
intermediate selfchecks remain separately preserved.

Executor SHA-256 before
`9c4540b8d032fba96dde4307f009b19e29dfa09842b24a4df3f9855fbd54eaa5`, after
`6e0d68a4cb6b922747efffcb8dec50566b29de43e5076f399b00facb9e671cc7`.
The ordinary reviewer passed the executor increment. Independent verifier is
running the final tests; its final notification remains pending. Never run
authorized phases without new user authorization and applicable safety gates.
