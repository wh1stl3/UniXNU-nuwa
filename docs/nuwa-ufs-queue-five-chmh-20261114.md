# Queue-five CHMH host packaging

Host-only experimental unauthenticated identity; authentication NOT REACHED, device release false.
Pinned kernel `eff66a33a097568e3c44f84fb1a7f3365889613cdcb629583944f2c99022012b`
is rebound to a new CHMH using the existing HC and PMGR packers, original parent
ADT, trust cache, r4 loader and stock template. The stock template and the
runtime backup are distinct inputs; the backup is not the template.
Arguments are `-v serial=3 nuwa-pmgr=2 native-ufs-probe=2 native-ufs-root=0`.
Level 0 and no ASMB are enforced by the existing parent ADT checks.

Stage 7 retains the `HC_SNAPSHOT_DONE` label; terminal text is
`QUEUE_ONLY_DONE` with five values. The static capacity is 15 lines; the
dynamic realmarker contributes only two lines. This is not an atomic snapshot
or proof of ownership. No SMMU, queue dereference, NOP or root operation is
performed by this host packaging.

The parent reports kernel incremental independent verifier PASS after the
correct-base correction. Cross-build code is identical; KCID, path string table,
`n_strx` and LINKEDIT metadata differ; there is no LC_CODE_SIGNATURE. The
executor was omitted from the verifier's before snapshot, so its frozen current
hash does not independently prove before/after identity. See
`out/nuwa-ufs-queue-five-verifier-20261114/corrections-20261114.md`.

Packaging ordinary review PASS and independent verifier PASS: the original and
rebuilt outer, FAT, record and ADT are byte-identical; build, original audit
and four negative cases exited 0. Evidence:
`out/nuwa-ufs-queue-five-package-verifier-20261114/verifier-summary.json`.
Outer SHA256:
`44205ea9c123afd1a13109c98329f2c8c0d96e9c2a1021ff9b82cc3920248dc9`.
No executor or device action is authorized by this packaging.
