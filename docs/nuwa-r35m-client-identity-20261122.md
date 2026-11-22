# r35m client identity — host candidate

The display callback reads `proc_selfname` only when its task equals
`current_task()`. Otherwise, or if the name is empty, it marks identity
unavailable. `pid_from_task` is retained as an independent last PID reference;
it is not paired with the entry count. No `proc_find` is called. Exact
`backboardd` name equality sets a sticky bit. A second sticky bit records
unavailable identity; a high-word counter tracks lookups in progress. The
renderer samples the 64-bit word atomically and shows `?` if either the
unavailable bit or in-progress count is nonzero, even if the hit bit is set.

| Page | Interpretation |
| --- | --- |
| `bb=1` | At least one completed probe observed the exact process name `backboardd`; this is a name observation, not executable authentication or successful open. |
| `bb=0` | Through this sample, all completed instrumented entries had available names and none matched; entries not reaching this callback are not covered. |
| `bb=?` | No negative conclusion: a lookup is in progress, the task differed from the current task, or its name was unavailable. |

The page remains `DSP ... CLI in=... out=... ret=... bb=...`; the previous
last entry type remains stored but is no longer displayed. The maximum line
using 32-bit counters, full 32-bit return and 8-bit DSP fields is 66 columns.
Counters and identity are independently sampled; a page can be stale or absent
after panic or scanout. The probe observes entries, not final userspace opens.

ABI fingerprint comparison retains its strict prior baseline after separately
requiring the four new strong board imports `_current_task`, `_pid_from_task`,
`_proc_selfname`, `_strcmp`; no imports were removed relative to the HID r4
archive. The packager adds only the exact kernel SHA below to its allowlist.

## Host results

All results are **self-checked**, not independent verifier or device results.
The ON build and separate packager audit used the commands in
`nuwa-r35l-display-dsp-20261122-observation.md`, with candidate path
`out/nuwa-r35m-bb-on-compact-r2`, package `out/nuwa-r35m-bb-package` and
audit `out/nuwa-r35m-bb-audit`. The outer readback config was byte-identical
to `out/nuwa-r35l-cli-canvas-audit-20261122/outer-readback/EFI/UniXNU/unixnu.toml`.
`fsck.fat -vn` reported 105751/129022 clusters used; `mdir` reported
11,914,752 free bytes, above 8 MiB.

| Artifact | Digest |
| --- | --- |
| Kernel SHA-256 | `daa0288fb7786a0b6078a0608b2d09fc5c4a71252a5d4a42944ac5b7da14293b` |
| Outer SHA-256 | `b427c698d0bee11ff6f660601ba10aa2bd01304d29e545a197bc91d1ba4cb8c8` |
| FAT SHA-256 | `5e8264ee7b6b630c7ba1b631dbbc40482c90d23f805ee2e141c91c1c40db345c` |
| Rebound CHMH SHA-384 | `a17fb0da392cac35098771e35e265f5468e087009c2d167d137b9dc48036a8b0dbf79e3b11e315406f9c70b0a3da882e` |

Outer-readback kernel SHA-256 matches the table. `backboardd\0` occurs at file
offsets `0x8aab7`, `0xef78f0`, `0x10bff2c`, `0x128ecd2`; string presence
alone does not prove callback execution.

`test-r35-display-fdr.py` on the pinned r35l renderer and `git diff --check`
passed. The porting-record check requires Python 3.11; an initial invocation
with system Python failed to import `tomllib`, then Python 3.11 checked 14
areas. Reviewer and deep_reviewer must review atomic ordering, sampling and
calling-context availability. Independent verifier and runtime remain pending.
No device operation or authentication claim.
