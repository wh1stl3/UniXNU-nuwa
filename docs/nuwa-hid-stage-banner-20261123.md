# HID stand-in stage banner

The `SVC` row ends in `H=<stage>`. This is an atomic, best-effort diagnostic
sample, not a readiness handshake; the row itself can be omitted by the
existing banner selection budget. Without `nuwa-hid-standin=1` the value is
zero and the probe remains disabled; zero can also mean the probe has not run.

| H | Meaning |
| --- | --- |
| 0 | Disabled or probe not yet entered |
| 1 | Enabled, loading HID classes / waiting for resource |
| 2 | IOHIDResource wait timed out |
| 3 | Attach succeeded; start not yet returned |
| 4 | Start returned success; checking child chain |
| 5 | Interface and driver registered, both property writes succeeded |
| 6 | Child chain wait timed out |
| 7 | Kext/class, metaclass, allocation/init/attach/start or child property failure |

Stage 5 is post-registration property publication only, not evidence that
initial matching saw those properties or that backboardd accepted a digitizer.
No input reports are sent. The original HID opt-in and sink stubs are unchanged.

The maximum SVC row using the full uint32 service mask, 8-bit low restart
field, 24-bit high restart field and any defined stage is 31 columns; the
generated format is exercised by `scripts/test-banner-short-values.py`.
The existing selection policy is unchanged. Reviewer must check stage mapping,
off behavior and row width; `deep_reviewer` must examine the relaxed atomic
cross-thread stage observation. Independent verifier and runtime remain pending.

## Host candidate — self-checked

The r35l display recipe was built with `--mg-reset --hid-standin`, followed
by `out/nuwa-systemgroup-seed-20261122/repack-hid-stage.py`. Outer readback
`unixnu.toml` is byte-identical to the `5831157` HID candidate and contains
`nuwa-hid-standin=1`; the readback seed is unchanged. FAT free space is
11,664,896 bytes. No device operation was performed.

| Artifact | Digest |
| --- | --- |
| Kernel SHA-256 | `5ba1be16d8e83c35405ec8d7595e16132be41a22932437e4b23ae90d794ce798` |
| Outer SHA-256 | `01e6e1c71346c05fb7cc9885d1179346b72e296ef3bbd993952017b6edd6479d` |
| CHMH SHA-384 | `d41581c63d672a4229e4c6eb05b79f17f1c4dc1e3d886ecae8b619a0619f946c21ba5f3eee9c6e4e70f8580b22e70b0f` |
| Outer-readback FAT SHA-256 | `3a4057db72144d057971de39a4a0787e364e8fcafe35fd69f475284d1f29463f` |

Verifier should rerun `scripts/test-banner-short-values.py`,
`scripts/test-banner-budget.py`, the r35l build with both flags, and the
packaging wrapper using fresh paths; independently compare outer-readback
args, seed, FAT free space and CHMH. Artifacts remain local under `out/`.
