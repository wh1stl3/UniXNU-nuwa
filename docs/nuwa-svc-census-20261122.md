# Service census bitmap — host candidate

The existing ten-second PID 1–4096 census publishes `SVC xx` with only the
low six bits used. Before the first scan zero means not sampled. Each set bit
means that during the scan a PID existed and its short name matched; it does
not establish service readiness, listening, or ability to respond to
SpringBoard. PID reuse and matching-name collisions remain possible.

| Bit | Service | Exact short-name match |
| --- | --- | --- |
| 0 | runningboardd | `runningboardd` |
| 1 | distnoted | `distnoted` |
| 2 | cfprefsd | `cfprefsd` |
| 3 | notifyd | `notifyd` |
| 4 | securityd | `securityd` |
| 5 | mobileactivationd | `mobileactivation` |

`mobileactivationd` has 17 characters; the MAXCOMLEN=16 short-name
representation is the 16-character prefix `mobileactivation`, which can
also match another executable with that prefix. The string prefix was
measured on the host; runtime behavior has not been newly measured.

The new row is 6 columns. From the parent-reported baseline values, the
actual `PROC n=141 SB=25 bb=54 lsd=93 ld=1 lk=69 cm=61` example is 46
columns. A synthetic example using the actual SCHED format,
`SCHED 30ms sleeps since last: n=1000 mean_late_us=500 max_late_us=50000 >50ms=2 | irq timer=10000 ipi=100`,
is 105 columns; these values are illustrative, not device measurements.
The longest actual banner row is unmeasured; each formatted row has a
119-column buffer limit and display width can clip it.
One additional row is reserved from the dynamically sized stack-trace area;
this can reduce the number of stack-trace lines displayed.

## Host packaging — self-checked

The post-build upstream HEAD check was skipped after a TLS receive error;
the local base pin remained `693f5d9cae8a408dd18b39f3f9fdc4228c934241`.
No further upstream HEAD request was made. The existing local seed-only
packaging recipe was adapted in
`out/nuwa-systemgroup-seed-20261122/repack-svc-candidate.py`: it uses the
new kernel, binds the existing SystemGroup seed, accepts the kernel hash in
memory without changing the committed packager, and compares against baseline
outer `6194d27d6c25ae62497ed1135d4480567a13bebdf37c4ab4b8ba87fbffea396c`.
Output: `out/nuwa-systemgroup-seed-20261122/vendor-boot-svc-candidate/`.
The outer readback config is byte-identical to that baseline; the 470-byte
args SHA-256 is `3d65e3183ae6e25bfea61aadc4e31941741a378f821a9fb43ba7d6d18c771720`.
The outer-readback encoded seed SHA-256 is
`692355638b31d347ced5983a5910491f0556156f79675c2e371ebe9987683247`.
The existing packager rebinds and audits CHMH. `fsck.fat -vn` and `mdir`
report 11,673,088 bytes free, above 8 MiB.

| Artifact | Digest |
| --- | --- |
| Kernel SHA-256 | `d500c5b3b9ab03312e6862b944d91c7cc2afca0f0db23ffe774c3ccf25fe0153` |
| Outer SHA-256 | `750cd0f8d27e54ee03562bbba0df597048f41733dcf3da27d93dad067f5c3d38` |
| CHMH SHA-384 | `5568c3a1a5ce2d22d1825ed59b6f55b67143fa5862aca69254539752f5c50ee4d7b65c6a23e440f5d6b0e85c9f2da800` |
| FAT SHA-256 | `c882ed27ce5251ce688edd7951905fa0654dc9c37c9476e6cde3b0ebff0bf898` |

Reviewer re-review of truncation, bit order and line width is pending;
deep_reviewer review of cross-thread publication is pending. Independent
verifier and device execution are pending. Authentication remains NOT REACHED.
