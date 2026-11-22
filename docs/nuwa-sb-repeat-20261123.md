# Repeated SpringBoard signal experiment

Host candidate only. Reviewer must re-review repeat boundaries, reference
release, four-attempt cap and line width; deep_reviewer must review concurrent
publication. Independent verifier and device execution are pending.

`nuwa-sb-restart` remains the first boot-time threshold, zero or absent off,
nonzero below 60 clamped to 60 seconds. `nuwa-sb-restart-every` is zero or
absent for one attempt, otherwise clamped to at least 120 seconds. Subsequent
attempts are at least that interval after the preceding actual attempt, on
the existing ten-second census. Four attempts maximum, including misses.
Each logs ordinal, actual boot second and target PID (zero means no match).
The process reference and signal mechanism are unchanged.

`SVC xx K=attemptsxfailures` distinguishes attempted scans and those with no
matching SpringBoard; a signal call does not establish termination. The
maximum `SVC 3f K=4x4` is 12 host-measured columns. Four attempts bound the
possible crash loop and system disruption; even four forced kills can disrupt
service and invalidate stability observations. No device operation is granted.

XR ring is unchanged: deduplication uses PID, name, signal, namespace and code;
different PIDs make separate entries, newest first, capacity four. The handoff
XR line displays **only the newest entry**, and unrelated exits can displace
samples; capture each promptly. Lock contention can drop an exit. PC is saved
only when the exiting PID equals `proc_selfpid()` and registers exist.

Repeated equal low-32-bit PC values are consistent with a fixed blocking point;
different values are consistent with execution, starvation or a loop. Neither
proves those conclusions: samples are from separate process instances and
possibly different threads, and truncation/ASLR can produce differences or
collisions. `f2681ad0` is only the low 32 bits of a user PC, not proof of an
unslid fixed image: even dyld shared caches can have a slide. Mapping identity,
full address and slide must be established before offline symbolication; PIE
slide is one possible reason for different addresses, not a consequence.

## Host build and package — self-checked

Upstream UniXNU main before and after build:
`8542980d02b4d2cc5c32ee3542de1760b2562aac`. The documented r35l display
recipe with `--mg-reset` produced `out/nuwa-sb-repeat-20261123-build-r3`.
An initial run timed out; r2 used the wrong WSL user and could not read the
root-owned CPO; r3 used root and completed.

The local `out/nuwa-systemgroup-seed-20261122/repack-sb-repeat.py` derives
from the previous repack wrapper, rebinding the new kernel and adding
`nuwa-sb-restart-every=180`. Relative to the previous one-shot package args,
this is the only addition; the wrapper checks exact args and config differences
against the same pre-one-shot baseline. Seed SHA-256 remains
`692355638b31d347ced5983a5910491f0556156f79675c2e371ebe9987683247`.
The outer-readback FAT has 11,673,088 bytes free (over 8 MiB). Output:
`out/nuwa-systemgroup-seed-20261122/vendor-boot-sb-repeat/`.

| Artifact | Digest |
| --- | --- |
| Kernel SHA-256 | `3faf7fa0620a4146234b05c865cebae7e35f2dc9a21435c6b1fb4b3f79bea5ef` |
| Outer SHA-256 | `2475ce3c4f61231d95d32a9af0f48776d9f439ed8dd531055c84be07daed1db0` |
| CHMH SHA-384 | `3665bb132b09f45706cc0379db433385c9a8a18e7f08682959be3f8ad168828b7c14fb5d461614f11ed1326cab42d757` |
| Outer-readback FAT SHA-256 | `fa9ba87dafa0d6e78a6ed26da963e48703bafae4857c88abc6b182706b431b1e` |

Independent verifier should rerun the r35l display recipe with `--mg-reset`,
`scripts/test-handoff-proc-census.py`, the local repack wrapper with fresh
output, outer-readback and CHMH checks, and `fsck.fat -vn` plus `mdir`.
