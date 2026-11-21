# r35h layout and PID-aware exit aggregation

Host-only candidate, self-checked; no device command. Independent verifier has
not rerun the final build and tests, and layout, aggregation semantics, stack
and locks have not received deep_reviewer review. Authentication remains NOT
REACHED.

## Release disposition and device evidence

The parent reports **plan B ordinary review PASS, without deep_reviewer**.
Acceptance is: no text on row 0; row 1 retains the build tag and counters;
EX1 is fixed on row 2, X1 on row 6, and stg on row 7. Full-screen clearing
on the first bind/resume is permitted. This disposition does not imply that
the physical crop boundary has been measured or that the interactive milestone
has been reached.

Outer SHA-256
`aee06fad56c6ea21ffd872abd961223bdeb4a76f844ffcad9f4d6d1e105f341e`
is a **single-use diagnostic candidate**, pending explicit authorization for
that device round; it is not authorization to operate the device.
The device-round record must include the full outer hash, the exact
authorization text, the continuous video hash, and a line-by-line
transcription. Mark anything not observed as `未见`. Matching the PID in X1
and EX is recorded only as correlation, not proof of the same event.

`n=` is the number of same-key observations while that slot is retained,
not a cumulative crash count. The modeled 74-column EX/X1 cases fit the
80-column, 1440-pixel width at scale 3; this is a host calculation, not
physical display verification.

Row 0 is suppressed by the diagnostic line/bar wrappers. Row 1 has the fixed
`[nuwa-r35]` tag and t/m/np; rows 2–5 are EX1–EX4, row 6 X1 and row 7 stg.
The main counter line falls back to t/m/np when the full line exceeds 80
characters; an overlong AKS suffix falls back to stage text. NS remains in the
ring but is not displayed; EX displays PID, comm6, sig, low 32 bits of code,
n and PC. The complete 64-bit code remains part of the aggregation key.

The aggregation key is (pid, comm, sig, ns, code). Different PIDs consume
separate slots, increasing rotation; same-key repeats increment the existing
slot in place rather than refreshing its position. Thus these are four
distinct retained keys, not necessarily the four most recent exit events or
four distinct PIDs. Matching X1 and EX PID is correlation, not proof of the
same event. PID reuse, separate rings and lost observations remain possible.
Existing try-lock and snapshot operations are unchanged in the source delta,
subject to deep review. No claim that the physical crop boundary was measured.

The Python source model checks the wrappers, format, row mapping and a model of
aggregation; it does not compile or execute the renderer. For 5-digit PID and
maximum displayed numeric values the model reports:

| Row | Content | Columns | scale 1 y/width | scale 2 y/width | scale 3 y/width |
|---:|---|---:|---:|---:|---:|
| 1 | counter | 56 | 14/336 | 28/672 | 42/1008 |
| 2 | EX1 | 74 | 28/444 | 56/888 | 84/1332 |
| 3 | EX2 | 74 | 42/444 | 84/888 | 126/1332 |
| 4 | EX3 | 74 | 56/444 | 112/888 | 168/1332 |
| 5 | EX4 | 74 | 70/444 | 140/888 | 210/1332 |
| 6 | X1 | 74 | 84/444 | 168/888 | 252/1332 |
| 7 | stg | 67 | 98/402 | 196/804 | 294/1206 |

Full SHA-256 `f280ca9850343ef9335190315f758bb9cbcbaae5983abde148cad133f79b0bb4`
and compact SHA-256 `19d16ca35c356fa5e45b7c0191d13f399327db82c6ce05cdb4b0492dd5711c42`.
Same-source debug-strip audit matched 49,615 non-debug symbols and 52,674
prelink bindings. Linked audit returned `ALL PASS`; outer SHA-256
`aee06fad56c6ea21ffd872abd961223bdeb4a76f844ffcad9f4d6d1e105f341e`,
CHMH SHA-384
`3a6580d9b72156f35d4fc1e83415830e1ab997260305a6f4db27ba4a37c1232581014e8ce663c7b63574ac459b084cdc`.
Outer readback matched packaged FAT SHA-256
`ff58ab81a4f55918b31df21eed251cae6b16d71c05425b9e9aef16dfa9b08039`;
FAT/FSInfo/fsck reported 12,070,400 free bytes, above 8,388,608.

## Reproduction

Use the commands in `docs/nuwa-r35g-ux-exception-20261121.md`, with fresh
full/compact/package/audit siblings and add `--layout-r35h` to both build
commands. Run `test-r35h-layout.py FULL/BootProgress.c` instead of the r35g
source replay; run the package test with `NUWA_LAYOUT_R35H=1` in addition to
the documented `NUWA_DETAIL_*` environment. Output paths must be absolute.
The Python model is an assumption-limited host check, not an execution of the
compiled renderer. Firmware scanout and physical display remain unverified.
