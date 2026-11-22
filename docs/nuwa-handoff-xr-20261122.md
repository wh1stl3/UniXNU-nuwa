# Post-handoff XR exit-ring display

XR displays the newest inserted entry independently of
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

Valid PCs are displayed as exactly eight hexadecimal digits, the low 32 bits.
`-` means `pc_valid` is zero, not PC zero. A repeated matching entry does not
move to the front, so the displayed entry is not necessarily the latest exit.

## How to locate a symbol

Obtain the process's runtime image mappings for that same run and locate
the full PC in a mapped range; the suffix by itself cannot identify a mapping.
A range belonging to dyld's shared cache must be resolved against the matching
cache and its constituent image's mapping, not against the standalone
executable. A range belonging to the executable outside the cache uses that
executable's matching Mach-O. UUIDs and mapping ranges are needed to select
the correct images, cache version and symbols.

The slide is aligned to the applicable mapping/ASLR page granularity. Only
bits below that alignment are necessarily unchanged by adding the slide:
matching low 12 bits is not proof of the same instruction (and the actual
granularity must be established for that mapping). For a candidate full PC,
subtract the corresponding image or shared-cache slide to obtain the unslid
VM address, then use the matching Mach-O segment's VM address and file offset
to translate it to a file offset, or symbolicate the unslid VM address.
Cache images may require cache-specific mapping and extraction rules; a
simple executable-base subtraction is not a general file-offset rule.

The display is PC modulo 2^32: all bits above bit 31 are lost, so addresses
separated by 4 GiB collide. An address in the hypothesized
`0x180000000`–`0x1ffffffff` range has omitted high bits `1`, but that range
is not established by this display. Independently establish the full mapping
and verify its low 32 bits before unsliding; no unique full PC or file offset
follows from the displayed value alone.

The existing `exit_lock` protects the read and formatting; no cross-ring
lookup or new capture is introduced. The host test of the generated formatter
measured 82 columns with two maximal-width PIDs, 9-character names, 8-digit
PCs and signal 127, using enlarged test-only buffers to avoid truncation.
One entry measures 41 columns and is used instead. This is self-checked only.
Reviewer re-review of width and truncation semantics is required; the earlier
concurrent ring reading and deduplication review remains pending.
No device operation was performed.

## 32-bit host artifacts

| Artifact | Digest |
| --- | --- |
| Kernel SHA-256 | `2e4437d4e9b26eb2ed896df96e40733a34ec90d7c89de4a382e7b90d9e1c9ada` |
| Outer SHA-256 | `25d6dee727a69155c96f7de09306216c21d6b5cafb9689768056a4c6261aedb4` |
| FAT SHA-256 | `5b43f0e37082b75523d9fcd2b6e2f4430b63f05088d4e440860a966394efef7d` |
| CHMH SHA-384 | `665635959946813556861f6f47fcb0d75e5ccfdb0fd5d756494c5d88caa7fffed84f7864bbc7ad6b028c8bcf85ef2f93` |

The compact build and packaging are self-checked, not independently verified.
Separate outer readback and CHMH audit are self-checked; `fsck.fat -vn` and
`mdir` report 11,898,368 bytes free (minimum 8,388,608). The readback
`unixnu.toml` is byte-identical to the previous six-digit XR audit.
Outputs are `out/nuwa-handoff-xr32-build-root-20261122`,
`out/nuwa-handoff-xr32-package-20261122` and
`out/nuwa-handoff-xr32-audit-20261122`. Build and package flags match the
six-digit recipe below; use a root WSL user for the root-owned compile tree.

## Previous six-digit host artifacts and checks

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
