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

Revision 2: elevate the T0 continuations and required diagnostics. From the
previous generated `BootProgress.c:1649–1677`, the old selector was:

```c
  if (s[0]==' ') return previous;
  if (s[0]=='T' && s[1]>='0' && s[1]<='3' && s[2]=='+') return 4;
  if (!strncmp(s,"CRASH",5) || !strncmp(s,"REASON",6) ||
      !strncmp(s,"PANIC",5) || !strncmp(s,"EXIT",4) ||
      !strncmp(s,"XR",2) || !strncmp(s,"PROC",4) ||
      !strncmp(s,"SVC",3) || !strncmp(s,"SC ",3) ||
      // Temporary: keep the stackshot readout ahead of normal diagnostics.
      !strncmp(s,"SHOT",4) || (s[0]=='T' && s[1]>='0' && s[1]<='3' && s[2]==' ')) return 0;
  if (!strncmp(s,"LOAD",4) || !strncmp(s,"UFS",3) ||
      !strncmp(s,"SCHED",5)) return 1;
  if (!strncmp(s,"GPU",3)) return 3;
  return 2;
```

After stable ascending sorting, the old selector returned:

```c
  return n<budget?n:budget;
```

Consequently old T0 continuations are clipped whenever 24 higher-priority
rows precede them. The runtime row population at t=360 is not fully captured
in the available input, so this is a demonstrated full-banner failure, not a
claim that the prior device actually showed 24 higher-priority rows.

The generated `BootProgress.c:1864–1869` computes
`cell=14*display.scale`, `half=display.height/2`,
`budget=(half-8)/cell-2`, capped at 24. With the recorded portrait
1440×3200 framebuffer (`package/boot-progress-r12/SOURCE-r12.md:24`) and
`boot-progress-scale=3`, this is `min(24,(1600-8)/42-2)=24`.
It is a host calculation based on that recorded geometry, not a new physical
measurement. Runtime framebuffer geometry and paint completion remain unobserved.

The following is the explicit t=360 scenario from the supplied previous
observation (two threads, T0 has 35 captured entries, 3 EXIT, 1 XR), plus
conditional rows that depend on runtime state:

| Source in generated BootProgress.c | Scenario rows | Conditions / boundary |
|---|---:|---|
| `bp_shot_format`, call 1693–1701 | 8 | SHOT 1, T0–T3 main/placeholders 4, T0+4/+8 2, SHOT2 1 if high bits; second thread has one frame |
| EXIT 1713 | 3 | `min(failed,3)`; additional exits do not add rows |
| XR 1714–1726 | 1 | zero if exit ring empty |
| census PROC 1729–1739 | 1 | unconditional |
| SVC 1741–1747 | 1 | unconditional |
| SC 1748–1758 | 2 | one if weak counters unavailable |
| LOAD 1811–1819 | 1 | only if host statistics succeeds |
| UFS 1820–1831 | 1 | only if weak UFS counters present |
| SCHED 1833–1845 | 1 | unconditional |
| subtotal | **19** | conditional assumptions above; does not count optional rows below |
| CRASH/REASON 1705–1712 | 0–4 here | generated before EXIT and constrained by `n<10` / `n<12`; runtime content unknown |
| FB / SWAP / GPUC / GPUW 1760–1801 | 0–4 | runtime counters |
| extra PROC 1802–1806 | 0–10 | matching process rows, constrained by `n<22` |
| work-interval log / CPU 1846–1851 | 0–4 | log up to 3, CPU up to 1; SS/SU are possible log text |
| GPU extension / PANIC 1852–1863 | 0–11 | up to 8 GPU rows and 3 panic rows, subject to `n<48` |
| later trace rows 1870–1877 | 0–remaining | only filled after banner selection, cannot displace selected rows |

With 19 base rows, seven or more existing higher-priority optional rows put
both old T0 continuations beyond row 24; six put the second beyond
it. Multiple other-thread continuations are also lowest priority and consume
remaining space. No claim is made that all optional maxima coexist.

New selector classes, stable within each class, highest first:

0. SHOT/SHOT2, T0 main and T0 continuations, all EXIT, all PROC, SC and LOAD;
1. CRASH/REASON/PANIC, XR, SVC and T1–T3 main rows;
2. UFS and SCHED;
3. other rows including SS/SU;
4. GPU rows;
5. T1–T3 continuations.

At most 22 class-0 rows can be generated: SHOT+SHOT2 2, T0 main+two
continuations 3, EXIT 3, PROC summary+up to 10 details 11, SC 2, LOAD 1.
Therefore all class-0 rows fit the calculated 24-row budget. Smaller
framebuffers, display yield, failure to paint, missing source records, and
an unsuccessful capture are not covered by that selection guarantee.
The full-banner fixture synthesizes 35 frames for all four threads, 3 EXIT,
10 extra PROC, SC, LOAD and surplus rows; it asserts T0 main/+4/+8 and all
required diagnostics survive 24-row selection. The user's requested “three
continuations” was clarified as information completeness: the existing
12-frame format necessarily uses two four-frame continuations after the main
four-frame row. No 13th–16th frame is retained.

## Package and readback

| Artifact | Digest |
|---|---|
| kernel SHA-256 | `a16c1629b63ef666995c5fcaa9c088495621d856a73d8ed4c40b8fea51d41424` |
| outer SHA-256 | `02fb3bebced7516e714f4719b6c0f76d704d2789be8c35ee15df9dbcc7428897` |
| CHMH SHA-384 | `b11c162e9620b45fd9556934618d2bca62c781414f0a6389844423e0531799663bba843f685a7c810271a474ff411813` |
| outer-readback FAT SHA-256 | `40d56d566ef2abec61c0586ef46deac88e7b049fd2bfc2257060663d4dbd31a9` |

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
`out/nuwa-lsd-deep-priority-r2-20261124-build`, package
`out/nuwa-lsd-deep-20261124-package`, audit
`out/nuwa-lsd-deep-priority-r2-20261124-audit`, and the kernel hash above. Run both
stack fixtures, both banner fixtures and three linked guard checks listed
there, then package `audit2.py`, `fsck.fat -vn` and `mdir` on the readback.
Independent verifier should rerun with fresh paths; no independent verifier
has run this revision.
