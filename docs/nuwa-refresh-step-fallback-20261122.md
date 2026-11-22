# Refresh step software fallback

20H392 consumer analysis in `nuwa-display-abi-20261120.md` §14 shows
MediaToolbox uses `10^9 / displayRefreshStep`, while QuartzCore converts
`displayRefreshStepMachTime` from Mach ticks to seconds. The former is
nanoseconds; the latter is ticks. Other consumers have not been established.

The explicit software fallback is 60 Hz, not a measured panel rate:
round(10^9 / 60) = 16,666,667 ns. At the measured 19,200,000 Hz
timebase, integer truncation of 16,666,667 * 19,200,000 / 10^9 gives
320,000 ticks. The implementation uses the existing kernel timebase
conversion rather than hard-coding the frequency. Existing min/max keys
remain unchanged.

If the actual panel is not 60 Hz, consumers using these fields synthesize
timing at 60 Hz; this is an intentional software fallback. Replace it when
qualified panel timing and its consumer behavior are established.
## Combined PROP/SC host candidate

Base includes `888d610` (held property reads and scanout counters). The
resume-only compact build uses `--cpu-only --no-software-vsync --candidate
--mg-reset`; packaging uses `--enable-display --board-window
--enable-mg-reset-resume-only`. The previous PROP/SC outer-readback
`unixnu.toml` and this candidate's outer-readback file compare byte-for-byte
identical, including absence of `sheng-data-reset`. The page retains
`PROP %04x FDR %us st=%u sig=%u` / `PROP %04x FDR no exit seen` and
`SC n=%u r=%u o=%u`.

| Artifact | Digest |
| --- | --- |
| kernel SHA-256 | `8358b013cf9f28a7fb8649491cd7f0b9931ab4750f05260ff7ef1e178ac94f1c` |
| outer SHA-256 | `be7034b58bf85be7807062f07fcc1af5683d802b404f68a5368f89aadc2d39e4` |
| outer-readback FAT SHA-256 | `acbaf208b71224b1f5cf84af281fcf41f0d6e25a1b1e2b7d4d27f4962d3ecb88` |
| experimental rebound CHMH SHA-384 | `844e580cbf9b4c83ea630ac9ed2715057bd02f266d9e54c2f8f77d843e08284a4ca5e74e41f2e1930e7fec80f4bd29c1` |

Build, package and audit are in `out/nuwa-refresh-step-{build,package,audit}-20261122`.
Outer audit re-extracted and checked the payload; `fsck.fat -vn` and `mdir`
report 11,898,368 free bytes, above 8 MiB. The formatter/reader C++ fixture,
FDR overlay and linked exception, register and IRQ guard checks ran. The
packager's MG hash allowlist was extended by this exact kernel hash after the
initial rejection; this pin and existing PROP/SC lifetime and atomics require
deep_reviewer review. Upstream `UniXNU` main was
`8542980d02b4d2cc5c32ee3542de1760b2562aac` before and after the build.
Host results are self-checked only; independent verifier and runtime remain
pending. Authentication NOT REACHED.
