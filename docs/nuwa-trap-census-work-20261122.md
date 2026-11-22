# Six-slot process census — host self-checked

The census requests the process name with `proc_name`, which reads `p_comm`.
The exact comparisons are SB `SpringBoard`, bb `backboardd`, lsd `lsd`,
ld `launchd`, lk `lockdownd`, cm `containermanager`. The last is the
16-character prefix of `containermanagerd`, which has 17 characters and is
truncated by `p_comm`'s MAXCOMLEN=16 limit. Another process with the same
16-character prefix can be mistaken for it. None of the other five names
exceed the limit. Names can change during exec; the census remains a sample.
The formatted line has 67 columns for five-digit counts and PIDs.

TRAP is deferred under the requested stop-loss rule. Two earlier combined
builds failed before linking at the filelist object-replacement check. The
existing `build-r35b-kernel.py` exception recipe generates and compiles C
but then substitutes `ux_exception.o` in its link inputs (lines 110–129);
the display build instead replays the pinned r35l link and does not recompile
the exception generator. Thus changing the generator alone cannot affect the
final display kernel without replacing that object/link input. The user ruled
out that replacement and filelist changes. All tentative TRAP code was removed;
the original SpringBoard branch remains unchanged. Generic fault-PC collection,
its PC semantics and exception-path review remain outstanding.
Authentication remains NOT REACHED.

## Host candidate

The compact kernel, CHMH-rebound package and separate outer readback are
self-checked only; no device operation or independent verifier rerun occurred.
The outer readback `unixnu.toml` is byte-identical to
`out/nuwa-handoff-proc-pid-audit-20261122/outer-readback/EFI/UniXNU/unixnu.toml`.
`fsck.fat -vn` and `mdir` report 11,898,368 bytes free, above 8,388,608.
The census source test and r35g/r35k/r35e linked checks ran. Upstream UniXNU
HEAD was `8542980d02b4d2cc5c32ee3542de1760b2562aac` before and after the build.

| Artifact | Digest |
| --- | --- |
| Kernel SHA-256 | `c7fcaabdd9274847f75da48ffcc7aca41b2ec330ba8d2e2b3bf65408f5e1d63d` |
| Outer SHA-256 | `e7a2214b5c5e12089aeb479e0a6320453a62e5fb17aafcf9cd46bf02d26b883e` |
| FAT SHA-256 | `47dd3ebb8ac9870b978c54341c36ac22a157b882ebf3aaf4c44ac49d7d2d0b52` |
| CHMH SHA-384 | `b2197fce7226ff7b48608a9ddba503eb6abe7bd9f4fd764ef675c93aa4bcb92e01a9bbf749bcd380f4476648af7200ca` |

Outputs: `out/nuwa-proc-six-build-20261122/`,
`out/nuwa-proc-six-package-20261122/`, `out/nuwa-proc-six-audit-20261122/`.
The existing exception path was not changed; previously pending deep review
of the r35l exception instrumentation is not closed by this census build.
