# lsd deeper user frames — host candidate, 2026-11-24

Host build, fixture and package checks are **self-checked**, not independently
verified. No device access or flash; authentication NOT REACHED.

The parser retains 12 user PCs per waiting thread instead of four. `f=` still
counts all recorded frames; `!` retains its old meaning (more than four frames
or producer truncation). The first four remain on the original main line.
Continuation rows use `T<n>+<index> U=`, four PCs per row. Capture time, target,
1 MiB buffer, flags, `r=`, `sb`, and `sc` are unchanged.

Correction: the symbolization record's statement that the other frames were
only display-truncated is incorrect: the old parser retained only four PCs,
although it counted 35. Its symbolization conclusion remains limited to the
four observed PCs.

Producer: local xnu-8796.141.3 `osfmk/kern/kern_stackshot.c:225` defines
`MAX_FRAMES=1000`; lines 2355–2377 cap by available kcdata space and call
`backtrace_user`; lines 2380–2388 store an array of `uintptr_t` user LRs.
The parser recognizes `USER_STACKLR64` and `USER_STACKFRAME64` in
`scripts/generate_r35_display_diag.py:68–70,239–249`. Thus 12 is within
the producer limit, not a guarantee of stack depth or remaining space.
The captured kcdata is unchanged: 12 LRs occupy 96 bytes plus the existing
16-byte array header, within 1,048,576 bytes; 1000 occupy 8,000 plus header.
Other tasks, records and threads consume the same shared buffer; no total-fit
guarantee is inferred. Expanding four saved arrays adds 256 static bytes
plus corresponding automatic parser storage, not capture-buffer bytes.

## Actual fixture output

From `test-sb-stack-row.py`, case 35:

```text
SHOT lsd n=1 w=1 r=0 ks=00000000 sc=- sb=-
T0 K=-,- U=100000000,100000001,100000002,100000003 f=35!
T1 -
T2 -
T3 -
T0+4 U=100000004,100000005,100000006,100000007
T0+8 U=100000008,100000009,10000000a,10000000b
```

Case 5 ends `T0+4 U=100000004`. Cases 0, 1, 4, 5, 12 and 35
were exercised in both host fixtures, including parser retention in the row
fixture. Continuation rows measured 16–46 columns; all fixture rows were
at most 78 columns (78 on the pre-existing maximum-count main-line case).

## Row budget

The renderer caps the visible banner at 24 rows and further limits it by
available half-screen height (`generate_r35_display_diag.py:641–643`, before
line shifts). Existing priority 0–3 rows sort ahead of new continuation rows
(priority 4), so new rows cannot displace existing banner rows. In a full
banner the continuations are clipped instead; capture of 12 is not proof all
12 are visible on the physical panel. SHOT and the four main T rows retain
their original order and priority; SHOT2 stays ahead of continuations.
The maximum new continuation count is eight (four threads × two); the row
array and selector were expanded from 48 to 64 to accommodate them.
The fixture checks that a full selection retains SHOT/SHOT2/EXIT/XR/PROC/
SVC/SC/LOAD/UFS/SCHED/SU ahead of continuations. Panel rendering is unobserved.

## Package and readback

| Artifact | Digest |
|---|---|
| kernel SHA-256 | `d3ecdc4623ab5523c66e69d10b938b57d12c9c1e594f57d70f4d69fec24e984a` |
| outer SHA-256 | `ef346e24bea9e61aeef6676b3391eb4a2ffad52845f06b591f3876f73fe95dd6` |
| CHMH SHA-384 | `68c4f20fce03af3ddd4dfffad277eb67be9395483cd0848eab1bec1d10cfd977e42d4771edc6cb6df20b445f8ee2fc74` |
| outer-readback FAT SHA-256 | `7e57d033811a40bf03cb5b2cf22d536c2c60051fdc06e0023ac0de57b63d0302` |

Package `out/nuwa-lsd-deep-20261124-package/vendor_boot.img`; rollback outer
`92494535a871f8406606cd711e2a8d76a01eb82a53ccc6365d2fa0fedb4157dc`.
FAT free 11,648,512 bytes, `fsck.fat -vn` and `mdir` self-checked.
The pure-Python FAT/ADT audit in package `audit2.py` read the outer, checked
required/forbidden args, `display-scale=03000000`, absent `text-fixups`, and
seed SHA-256 `692355638b31d347ced5983a5910491f0556156f79675c2e371ebe9987683247`.
The repacker checked byte-identical 507-byte args to the baseline, SHA-256
`58dc839e9a1a06528ed53304a594d1732cbe85da533af2bb48a51662dabf0d5e`;
no `sheng-smp`. Outer FAT readback and CHMH rebinding were self-checked.

## Reproduction

Use the commands in `nuwa-sb-stack-detail-20261124.md`, with build output
`out/nuwa-lsd-deep-20261124-build`, package
`out/nuwa-lsd-deep-20261124-package`, audit
`out/nuwa-lsd-deep-20261124-audit`, and the kernel hash above. Run both
stack fixtures, both banner fixtures and three linked guard checks listed
there, then package `audit2.py`, `fsck.fat -vn` and `mdir` on the readback.
Independent verifier should rerun with fresh paths; no independent verifier
has run this revision.
