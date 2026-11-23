# Compact UFS and scheduler banner — host candidate

The two existing second-priority rows remain single rows and retain their
existing selection policy; neither has a guaranteed seat.

* `UFS L r=... rd=... T r=... rd=...`: `L` is since the last paint;
  `T` is cumulative. `r` is the read-request count; `rd` is transport
  read time in milliseconds.
* `SCHED n=... m=... x=... >50=...`: all are since the last paint.
  These describe the 30 ms monitor sleeps: `n` is their count, `m` and
  `x` are mean and maximum lateness in microseconds, `>50` is the count
  over 50 ms late. The pre-existing zero-count mean convention remains.

Counts up to 999999 and times up to 9999 in their base unit are exact.
Above that the formatter repeatedly divides by 1000, rounding down, until
the value is at most 999; `k`, `M`, `G`, `T`, `P`, `E` indicate powers
1000¹ through 1000⁶. A prefixed value is an approximation, not an exact
value, including when its truncated remainder happens to be zero. `999kms`
means approximately 999000 ms; `50kus` means approximately 50000 us.
The unit suffix is part of the six-character limit. Exact large values
require a future separate output. Existing tick-to-ms arithmetic is unchanged.

UFS blocks and verify times and scheduler timer/ipi counts are omitted from
the banner, not redirected to another new output. If needed they require a
future separate diagnostic line or output; counters themselves are unchanged.

For synthetic examples, not device readings:

* Before UFS (102 columns):
  `UFS   since last: verify=22ms read=37ms blocks=123 reqs=45 | total verify=5447ms read=9210ms reqs=3210`
  After (37): `UFS L r=45 rd=37ms T r=3210 rd=9210ms`.
* Before SCHED (105 columns):
  `SCHED 30ms sleeps since last: n=1000 mean_late_us=500 max_late_us=50000 >50ms=2 | irq timer=10000 ipi=100`
  After (34): `SCHED n=1000 m=500us x=50kus >50=2`.

Worst-case four six-character values plus fixed text: UFS 24+21=45;
SCHED 24+19=43. `scripts/test-banner-short-values.py` compiles the actual
generated C helper and measures those 45/43-column rows; it checks maximum
uint64 and boundary values. `scripts/test-banner-budget.py` covers unchanged
selection and geometry. Host checks are self-checked; device rendering,
reviewer field/readability review and independent verifier remain pending.

## Host build and package — self-checked

UniXNU upstream HEAD before and after build:
`8542980d02b4d2cc5c32ee3542de1760b2562aac`. The r35l display
recipe in `nuwa-r35l-display-dsp-20261122-observation.md` was run with
`--mg-reset --out out/nuwa-banner-compact-20261123-build-r4`. The local
wrapper `out/nuwa-systemgroup-seed-20261122/repack-banner-short-values.py`
derives from the prior banner-priority wrapper with only the output, build
path and kernel pin changed. Output is
`out/nuwa-systemgroup-seed-20261122/vendor-boot-banner-short-values/`.
The wrapper performed outer readback and CHMH checking.

| Artifact | Hash |
| --- | --- |
| Kernel SHA-256 | `6c6b3750cbe7a8ae24581f7021271418b6784dfa68c88aa2451d78b06a532792` |
| Outer SHA-256 | `7d9f09cb26eded61e2fdfc9b90ae137a45c7fa9baba4c3687de1a57246dbea49` |
| CHMH SHA-384 | `4ac27373418912a1b58168f8bfd964a4bc83c92ba5ed3d1175b80ddc230ba1babb7278d4e330364f63945d4233ec46d9` |
| Outer-readback FAT SHA-256 | `f4c63cd37a15e9b643c43cb009973b941d31aa06bd652df01cce5fdaee55ec61` |

Outer-readback FAT free space: 11,673,088 bytes (minimum 8 MiB). The seed
read back as SHA-256 `692355638b31d347ced5983a5910491f0556156f79675c2e371ebe9987683247`,
unchanged from `caf50cc`. Outer-readback config SHA-256
`bf4947068b1f9452575ee8b39d7542ddb3dd3e1befc24ffd2eb78cdc9aa8e0c5`
equals the prior banner-priority package config: it includes
`nuwa-sb-restart=400`, `nuwa-sb-restart-every=180`, and no `nuwa-sb-dump`.
No device operation occurred; authentication remains NOT REACHED.

Reviewer must re-review field selection, readability and worst-case width.
Verifier should rerun both banner tests, the r35l display build with
`--mg-reset`, and the package wrapper, outer readback, CHMH, seed and FAT
checks. Final acceptance belongs to the parent.
