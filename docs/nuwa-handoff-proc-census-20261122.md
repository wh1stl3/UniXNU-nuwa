# Post-handoff process census

The old `PC` line samples the process running at a timer interrupt once per
second; it does not rotate through processes. Not seeing a process there
does not mean it is absent.

The touch monitor performs a census before `touch_overlay()` acquires
`render_busy`. Once BSD processes exist, it scans PID 1 through 4096 with
`proc_find`/`proc_rele` and obtains each name using `proc_name`, which in the
pinned XNU returns void, clears the buffer and itself obtains/releases a
reference. This avoids proc layout dependencies and a direct list-lock/
render-lock nesting. Each non-null outer reference is released. It publishes
five independent atomic PID values;
zero denotes no match. The banner reads only these values and `nprocs`,
and shows `PROC n=... SB=... bb=... lsd=... lcd=... ld=...` where `ld`
means launchd. Before the first census the zero values mean not sampled,
not demonstrated absent. Individual atomics are not a coherent transaction.

Census attempts are ten seconds apart, so a continuously present process is
normally discovered within ten seconds if the worker runs. Banner repaint
also has its existing two-second throttle; scheduling, lock contention or
stalled painting can add unbounded delay. Only PIDs 1–4096 are scanned.
A process that starts and exits between censuses may be missed. A previously displayed PID may already have
exited or been reused. Presence does not establish initialization or display
ownership. Names can change during exec. One scan performs 4096 outer lookups
plus one extra internal lookup per non-null result; actual runtime cost has
not been measured.

Pending reviewer: reference lifetime, two lookup/name synchronization,
atomic publication and banner layout. Independent verifier must
rerun the final build, source-contract tests, CHMH/outer audit and FAT checks.
No device operation.

## Host candidate — self-checked

The compact ON build reused the command and inputs in
`nuwa-r35l-display-dsp-20261122-observation.md` with `--mg-reset`.
Packaging and separate outer audit used `--enable-display --board-window
--enable-mg-reset-resume-only`, with the kernel hash added to the existing
MG allowlist. Outer-readback `unixnu.toml` compares byte-for-byte with
`nuwa-handoff-sc-audit-20261122`; its args retain `sheng-data-persist=2`,
`nuwa-lite=1` and `nuwa-mg-reset=1` without `sheng-data-reset`. The same
packaging profile includes the experimental `display-scale` ADT property.
Outer-readback FAT has 11,898,368 bytes free (minimum 8,388,608).

| Artifact | Digest |
| --- | --- |
| Kernel SHA-256 | `46babd3f23a10295c25fc72b948958f2807926741a0d7b359572a9fbd5846a99` |
| Outer SHA-256 | `ca51c5c4ec584d9cbdd35a38170c1150801e36be4f32f798e809f312012d99a6` |
| Outer-readback FAT SHA-256 | `e86cced9f169d75344fec15352390765c9112ea80318aa0835429ae57aee9eb5` |
| Experimental CHMH SHA-384 | `cf2c005fbdf515a78ca9559ea0fb6de308dc79f73af42c32cb31656003b33ddd832535ac3cb31f5bce5d3d57f1349998` |

Build outputs are in `out/nuwa-handoff-proc-pid-r2-build-20261122/`,
`out/nuwa-handoff-proc-pid-package-20261122/`, and
`out/nuwa-handoff-proc-pid-audit-20261122/`. The native link completed and
contains definitions for `proc_find`, `proc_name`, and `proc_rele`.
Source-contract, FDR overlay and three linked exception/register/IRQ checks,
porting-record, separate packaging audit, `fsck.fat -vn` and `mdir` ran.
UniXNU upstream main was `8542980d02b4d2cc5c32ee3542de1760b2562aac`
before and after build. Actual scan cost and runtime remain unmeasured.

The first PID-census compile failed on the renderer's incompatible `strcpy`
macro; the second fresh build uses direct two-byte assignment. A later
linked-test loop command was malformed by host-shell expansion; the three
individual linked tests were then run explicitly. All completed checks
above are self-checked, not independent verifier results.
