# Banner priority correction — host only

Relative to `74f5597`, the banner body is limited to the lesser of 24 rows
and the number that fits in the lower half including title and padding.
The top half is not painted by this banner; logo position itself is unverified.
Width remains at most 119 columns, as in `74f5597`, rather than the 80-column
regression in `43f9f21`. Existing rows are generated first and selected before
stack traces are requested. Stack rows use only remaining space and follow the
selected diagnostic rows; the work-interval log is now generated regardless
of stack availability.

When existing rows exceed the budget, selection and display are stable within
each of these priority classes, in order:

1. `CRASH`, `REASON`, `PANIC`, `EXIT`, `XR`, `PROC`, `SVC`, `SC`.
2. `LOAD`, `UFS`, `SCHED`.
3. Other existing rows, including `FB`, `SWAP`, work intervals and `CPU`.
4. `GPU` rows.

Indented continuation rows inherit the immediately preceding row's priority.
Rows within a class retain their original generation order. If class 1 alone
exceeds the budget, its earlier generated rows win. With spare space stack
roles are requested in existing role order with their existing per-role caps.

Thread enumeration is deferred; no `nuwa-sb-dump` argument is added relative to
`74f5597`. No thread count, wait category, user PC, wait_event, or port name
is claimed. No device operation was performed.

## Host package — self-checked

UniXNU upstream HEAD after build: `8542980d02b4d2cc5c32ee3542de1760b2562aac`.
Build: `out/nuwa-banner-priority-20261123-build/`. Wrapper:
`out/nuwa-systemgroup-seed-20261122/repack-banner-priority.py`; output:
`out/nuwa-systemgroup-seed-20261122/vendor-boot-banner-priority/`. The wrapper
checks the existing baseline plus `nuwa-sb-restart=400` and
`nuwa-sb-restart-every=180`; these are already present in `74f5597`.
The seed is unchanged: outer-readback SHA-256
`692355638b31d347ced5983a5910491f0556156f79675c2e371ebe9987683247`.
Outer-readback FAT free space: 11,673,088 bytes.

| Artifact | Digest |
| --- | --- |
| Kernel SHA-256 | `fdfe561ea574a875710a322f9234a5bf30dd98c22112669ba09daceba5a9618e` |
| Outer SHA-256 | `6ea23b3b03eafe18c618bce105d0755dbee42cac17895e58b51cb100de891842` |
| CHMH SHA-384 | `536eca85e9c119feb00461b484631d5c6bf12a32dffb87ffc70dd575dacf0b39c89639340c929ac24020d2c799be31fd` |
| Outer-readback FAT SHA-256 | `6459558378547c28f34201d8cf39cdb4f673ed13da37f6a082667dc1452f278e` |

`python3 -B scripts/test-banner-budget.py` compiles and runs the exact C
selector against crowded and spare-space cases and checks half-screen geometry.
Reviewer must re-review row selection, priorities and width; P1 reference
balance is not applicable. Independent verifier must rerun this test, the
documented r35l display build with `--mg-reset`, and wrapper readback, CHMH,
seed and FAT checks. Device rendering and logo visibility remain unverified.
