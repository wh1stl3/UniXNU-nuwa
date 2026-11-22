# One-shot SpringBoard restart experiment

Host candidate only; reviewer re-review of signal call, process references and
single-trigger guarantee is pending. Cross-thread publication requires
deep_reviewer review. No device operation is authorized by this record.

The touch monitor parses `nuwa-sb-restart` using `PE_parse_boot_argn`; absent
or zero disables it and nonzero values below 60 are clamped to 60 seconds.
On the first existing ten-second census at or after the threshold, it marks
the attempt consumed before scanning. The scan calls `psignal(p, 9)` once for
the first matching SpringBoard, retaining and then releasing the existing
`proc_find` reference. Every non-null scan reference is released once. It logs
the trigger second, PID (zero when absent), and whether `psignal` was called.
The call returns void; neither signal effect nor termination is established.
Only PID 1–4096 is scanned; the short-name lookup and reference are separate
operations and can race with exit or exec.

`SVC xx K=0` means not yet triggered; `K=1` means the call was made;
`K=2` means triggered but no matching process was found. The formatted line
`SVC 3f K=2` is 10 columns, measured on the host, not on the display.
Completion of the scan and banner repaint may be delayed.

At least 30 seconds after triggering, compare `PROC` `SB=` with the original
PID and observe whether a new instance produces a frame. A greater PID is
consistent with a new instance, assuming the reported monotonic PID behavior
and no reuse; an unchanged PID is a clue that the process has not terminated,
not a conclusion, and must be combined with other readings. `SB=-` means a
scan missed it and may reflect a restart window. Census runs every ten seconds
and the banner has an approximately two-second throttle; stalls, PID reuse,
name races and scan range can invalidate a simple interpretation. This can
test whether a later instance produces a frame, not prove the early lookup
hypothesis, service readiness, the signal's effect, or persistent interaction.

The expected launchd response to a killed SpringBoard is restart; repeated
failure can cause a crash loop, so this experiment issues at most one call.
Actual launchd behavior and display behavior remain unverified.

## Host build and packaging — self-checked

Branch base `2cba074`; UniXNU upstream main before and after build
`8542980d02b4d2cc5c32ee3542de1760b2562aac`. Built with the r35l display
recipe in `nuwa-r35l-display-dsp-20261122-observation.md`, adding `--mg-reset`
and output `out/nuwa-sb-restart-20261123-build-r2/`. The first invocation was
accidentally terminated by a one-second background timeout; the fresh r2
build completed. Source-contract, FDR overlay and linked exception/register/
IRQ checks ran. Initial test shell interpolation and FDR missing-argument
errors were corrected before the completed invocations.

`out/nuwa-systemgroup-seed-20261122/repack-sb-restart.py` adapts the existing
seed-only repack for this kernel. Its first run encountered an unterminated
string in the generated wrapper; escaping was corrected. The successful run
rebound CHMH and checked the outer readback against baseline outer SHA-256
`6194d27d6c25ae62497ed1135d4480567a13bebdf37c4ab4b8ba87fbffea396c`.
**Args 相对基线只多这一项：`nuwa-sb-restart=400`**; the comparison was
byte-for-byte, and config changed only by this insertion. Outer-readback seed
SHA-256 remains `692355638b31d347ced5983a5910491f0556156f79675c2e371ebe9987683247`.
Outer-readback FAT `fsck.fat -vn` and `mdir` report 11,673,088 bytes free,
above 8 MiB. Output is
`out/nuwa-systemgroup-seed-20261122/vendor-boot-sb-restart/`.

| Artifact | Digest |
| --- | --- |
| Kernel SHA-256 | `3963008849c395895f1572cce5902ea55436879de2b1a4fd24cb214241202d6e` |
| Outer SHA-256 | `c8abfda398ada2dab8ba915dc34659d2a16f0a9712f4596c62db27aafecc5b2a` |
| CHMH SHA-384 | `0f60caab3556b33b42f79e308eb1e261a49e94feb2a9b029a6899536f1106cc27f06c5eb4239a576b0252e28bc0f5a33` |
| Outer-readback FAT SHA-256 | `e78e3d68fc03c31b066d8eb841e0f0ab0562c9ed3d307a425fca0be74a81ae94` |

Independent verifier should rerun the documented display build with `--mg-reset`,
the source and linked checks, and the local repack with fresh output names;
repeat outer-readback comparison, CHMH audit, `fsck.fat -vn` and `mdir`.
