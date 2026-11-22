# Post-handoff XR exit-ring display

XR displays up to two entries, in existing ring order, independently of
the CRASH lines: no association with a CRASH line is asserted. Entries are
deduplicated by PID, name, signal, namespace and reason code; the first
record is retained and a matching later exit only increments its count.
Thus a later crash with the same key and PID does not add an entry. PID reuse
can also make an entry differ from the most recent crash. Entries are ordered
by first insertion, not necessarily by the latest repeat.

`pc` and `pc_valid` come from `bp_exit_ring_entry`; the existing
`proc_prepareexit` hook saves the current thread's user state PC when
the exiting PID is the current process and saved state is available.
It is not guaranteed to belong to the fatal exception thread. In a
single-threaded process it is more likely to be the triggering instruction;
an exit initiated by a kernel thread or another thread invalidates that
inference. It is a user virtual address; matching it to symbols may require
unsliding using the corresponding process image mapping.

Valid PCs are displayed as exactly six hexadecimal digits, the low 24 bits.
`-` means `pc_valid` is zero, not PC zero. The full address cannot be
reconstructed from the suffix alone: obtain the omitted high bits from an
independent process mapping or full PC, and check that the resulting address
has the displayed low 24 bits before applying the image slide.

The existing `exit_lock` protects the read and formatting; no cross-ring
lookup or new capture is introduced. Host formatter test measured 78 columns
for two maximal-width PIDs, 9-character names, 6-digit PCs and signal 127.
This is self-checked only. Reviewer re-review of concurrent ring reading and
deduplication semantics is required. No device operation was performed.

## Host artifacts and checks

| Artifact | Digest |
| --- | --- |
| Kernel SHA-256 | `22af086c04d463f9be74ae302a180fa20c31346ee124a32dcd1791e89595ddc1` |
| Outer SHA-256 | `bf7056634ca116782275432cb75331cbcee07ad03fef52c0917b0826a1c66dd5` |
| FAT SHA-256 | `4a02f97b36c29d521fcfb7a469e66fa8b4630a8f053c5d59c7ea902d321184fc` |
| CHMH SHA-384 | `583b57aefe4a2caac7fffb0555e6f882b4754cb70edf8c119908d4a85860598a9adb2c24ba1d708b148d61e8613fc740` |

Build, CHMH rebinding and separate outer readback are self-checked. Readback
`unixnu.toml` compared byte for byte with `out/nuwa-proc-six-audit-20261122`;
`fsck.fat -vn` and `mdir` showed 11,898,368 bytes free (minimum 8,388,608).
The XR formatter, process census and FDR source tests and r35g/r35k/r35e
linked checks were self-checked. Outputs are `out/nuwa-handoff-xr-build-20261122`,
`out/nuwa-handoff-xr-package-20261122`, and
`out/nuwa-handoff-xr-audit-20261122`. The profile and build command are those
in `nuwa-r35l-display-dsp-20261122-observation.md`, with `--mg-reset` for
the build and `--enable-display --board-window --enable-mg-reset-resume-only`
for the package and audit.
