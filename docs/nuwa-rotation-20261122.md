# Experimental rotation property

The parent reports `PROP 007f`, `SC n=0 r=0 o=0`, and SpringBoard SIGTRAP
with PC low bits `0xbd4` after the refresh-step candidate. These readings are
relayed, not independently captured here. The change tests only the missing
rotation property, not a diagnosed cause of the assertion.

Before probe/start and service registration, the display object publishes
`IOFBRotation` as 32-bit OSNumber zero; failure reports stage 3 reason 17 and
unwinds without registering. The existing display refresh dictionary uses
OSNumber for numeric values (see `nuwa-display-abi-20261120.md` §14); canvas
dimensions on the provider are ADT-style OSData, a different object/contract.
Zero is the requested unrotated default. We have not established whether
FBS/QuartzCore reads this property, its required type, or its missing-value
default; OSNumber is a hypothesis, not a confirmed consumer contract. The
existing console gate also requires firmware rotation to be zero.

## Host candidate (self-checked)

Built with `scripts/build-nuwa-display-native.py`, the same base, CPO and
r35 inputs as `nuwa-r35l-display-dsp-20261122-observation.md`, and options
`--cpu-only --no-software-vsync --candidate --mg-reset`. Packaged and audited
with `scripts/build-ufs-apfs-root-chmh-r35-display.py` and
`--enable-display --board-window --enable-mg-reset-resume-only`; the output
`unixnu.toml` compares byte-identical to the previous refresh-step audit.

| Artifact | Digest |
| --- | --- |
| kernel SHA-256 | `0bf8950fba416b9537782df245c43f8099e0e10f7c93c6f2d3fc35e604f50e5a` |
| outer SHA-256 | `426ad39ea6456daa3a9393b4ea43778d7f5087453f64781181eace2eefdaefb1` |
| outer-readback FAT SHA-256 | `f8f3be55c10bb11a5e58e3a3d9805d5e1c4e048c25535e55d63d0b9cce26b060` |
| experimental CHMH SHA-384 | `223ded55e0cef5b18930f47e3b64a419f776ea5a402cdff0d4b4675735e4e6b799b45203f236d51f9b8cfc0896645b7b` |

The audit re-extracted the outer image; `fsck.fat -vn` and `mdir` report
11,898,368 bytes free (minimum 8,388,608). FDR overlay static checks and
linked exception, register and IRQ guard checks ran. `porting-record.py`
checked 14 areas with Python 3.11. Initial use of system Python failed at
`scripts/porting-record.py:10` because it lacks `tomllib`; Python 3.11 was
then used. Upstream UniXNU main was `8542980d02b4d2cc5c32ee3542de1760b2562aac`
before and after the build. The packager's MG allowlist is bound to this exact
kernel. Artifacts are under `out/nuwa-rotation-{build,package,audit}-20261122`.

Pending reviewer/deep_reviewer review and independent verifier; runtime and
authentication NOT REACHED. No device action was performed.
