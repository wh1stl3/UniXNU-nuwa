# Post-handoff scanout counters

The live crash banner samples `nuwa_sc_calls`, `nuwa_sc_rejects` and
`nuwa_sc_ok` at each banner paint using the existing relaxed atomic loads.
`SC n=<calls> r=<rejects> o=<ok>` is a best-effort set of independent
samples, not a coherent transaction. `SC +<calls> in <seconds>s` reports
the unsigned call-count change since the previous banner sample, or
`SC interval unavailable` for the first sample. These count bridge calls,
not successful frames or visible updates. If painting stops, its last
displayed values also stop; the banner cannot report its own current failure.

The existing banner signature includes `now/10` and a minimum two-second
interval. Its time-driven refresh is designed for ten-second steps; other
signature changes can cause earlier redraws. A ten-second jump in `t` is
not evidence of load or thread starvation; use the existing `LOAD` and
`SCHED` rows for load observations. This change does not alter throttling.

Reliable current SpringBoard and backboardd PID and elapsed lifetime are
not available from the qualified banner interfaces. The weak
`boot_process_rows` is historical probe text without an established
freshness or process-lifetime contract, and the existing census records
names and aggregate events rather than current per-PID lifetime. Neither
is substituted for live process status.

Deep reviewer must review the independent atomic reads, sample interval,
banner layout and width; independent verifier must rerun the final build
and packaging. No device operation.

## Host candidate — self-checked

The compact ON build used the pinned build command and inputs in
`nuwa-r35l-display-dsp-20261122-observation.md`, adding `--mg-reset`.
Packaging and separate outer audit used `--enable-display --board-window
--enable-mg-reset-resume-only`, as in `nuwa-resume-display-scale-20261122.md`.
The extracted config is byte-identical to that prior candidate. The FAT
read back from the outer image has 11,898,368 bytes free, exceeding 8 MiB.
UniXNU upstream main was `8542980d02b4d2cc5c32ee3542de1760b2562aac`
before and after the build.

| Artifact | Digest |
| --- | --- |
| kernel SHA-256 | `ba1f6913cf0412b3e8714b3f3dfca8daa8922768aa427e12b6d8d0f4cf53729b` |
| outer SHA-256 | `3cb7557d2d18eb36682e7c716e73d9799e730415c7030f0ed92efc9621047d57` |
| outer-readback FAT SHA-256 | `e5c992d16d58202daf30917111f5b86ed5a84bdf33911c579822da5e509e03b4` |
| experimental CHMH SHA-384 | `3b43bddfcc6dbcd88b337ed65ea0b2b248707d6909700de4032bd721495890f17fcde434d3b13ddd3e13a21a225140f3` |

Outputs: `out/nuwa-handoff-sc-build-20261122/`,
`out/nuwa-handoff-sc-package-20261122/`, and
`out/nuwa-handoff-sc-audit-20261122/`. Overlay, MG and watchdog host tests
and linked exception, register and IRQ guard checks ran. Packaging audit,
`fsck.fat -vn` and `mdir` ran. For independent verification repeat the
build and packaging commands in the linked records with fresh output paths,
then rerun `scripts/test-r35-display-fdr.py`, the three linked tests,
`fsck.fat -vn`, `mdir`, and compare the outer-readback config. Authentication
remains NOT REACHED.
