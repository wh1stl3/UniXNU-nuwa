# nuwa SpringBoard thread sample — 2026-11-28

The build and checks described here were host-only, with no device access or
flash at that stage. The `--sb-threads` build flag requires the existing
single-core `--post-event` profile. It adds no boot argument and does not
enable the unsupported `boot_ui_trace_*` stubs.
Device source baseline `964d7e09c9397dcc306caba88fdbacc2ab82f35f`; UniXNU build
base `693f5d9cae8a408dd18b39f3f9fdc4228c934241`. Remote HEADs before and after
the build: UniXNU `e7bddb9a7eecdcf81f36da9fa38bd9d4d3f155c2`, device
`fe6b859367cc7b0641e9ae7dda46d8b5c6fc4fb0`.

## Readout

The existing process worker matches the full `p_comm` `SpringBoard` every
two seconds. `SBTH none` means no match in that walk. `SBTH denied` means
a matched task or thread could not be sampled, the list exceeded 128,
or the renderer encountered an in-progress publication. No partial census
or stale PC rows are substituted on failure.

The summary reports only `SBTH n=<thread count>`. The PC rows rank unique
saved user PCs by count, then by address. LR and SP come from the first
thread seen for that PC. `non-atomic` marks four independent CPSR/PC/LR/SP
loads that can span preemption: the result is a best-effort PC census,
not a consistent register capture or unwind. No user address is followed,
and no thread is stopped for a sample.

Reviewer rejected r4 outer `03b7f6eabe5532079d4a212fea3c2aa0decf0215375375d9f18046a8e8c13747`:
`thread_info(THREAD_BASIC_INFO)` can call `SCHED(update_priority)` under
the target thread lock. r5 removes the call and all scheduler-state
buckets; it does not substitute zero counts.

The summary occupies the previously unpainted row 0 and survives the
panic renderer's top-eighth preservation. Critical exit can repaint
only that summary even when the diagnostic display has unbound. Four
detail rows occupy rows 48–51 on the boot page, before the retained
pixel comb. Normal drawing obeys the current binding and yield gates.
The details are not copied to the live banner, persistent log, or
panic screen. DATA, PIX, PROC, and UFS TIME are unchanged.

Reuse: Apple XNU 8796 (pinned 20H392 build tree; APSL 2.0)
`fill_taskthreadlist`, `task_findtid`, and `get_user_regs`;
nuwa's existing process worker and post-event paint
are BSD-2-Clause-Patent. No private `struct thread` offsets or XNU patches
are added. The added consumer takes and releases references and uses
the helpers' existing locks; it adds no new target lock or scheduler
operation.

## Reproduction

Use the [no-glyph build and package commands](nuwa-no-glyph-examples-20261128.md#build-and-package)
with `--sb-threads` appended to the build, and these fresh output paths:

```sh
b=out/nuwa-sbth-20261128-build-r5
pkg=out/nuwa-sbth-20261128-package-r5
$p -B tests/test-nuwa-sb-threads.py --build "$b" \
  --baseline out/nuwa-no-glyph-20261128-build/BootProgress.c \
  --outer "$pkg/vendor_boot.img" \
  --baseline-outer out/nuwa-no-glyph-20261128-package/vendor_boot.img
$p -B scripts/test-nuwa-postevent.py --renderer "$b/BootProgress.c" --kernel "$b/native-with-stabs.macho"
$p -B tests/test-nuwa-pixsig.py
$p -B tests/test-nuwa-crashcap.py "$b/kernel.macho"
$p -B scripts/package-nuwa-crashcap.py --base "$base" --kernel "$b/kernel.macho" \
  --out "$pkg" --disposable-data-template "$template" --post-event --audit-only
fsck.fat -vn "$pkg/readback-fat.img"
$p -B "$base/scripts/porting-record.py" check --device "$PWD"
```

## Results — self-checked

Final build, package, the SBTH fixture and disassembly audit, post-event,
PIX, crashcap, package audit, `fsck.fat -vn`, and the device record check
each exited 0. The r5 audit saved `sbth-sample.disasm.txt` and
`sbth-linked.disasm.txt`. The sampler's frame is 5,248 bytes including
saved registers, plus callees. The linked PID1 probe, SpringBoard callback
and sampler contain no `_thread_info` call; the sampler's direct call
allowlist confirms it uses only existing enumeration and reference helpers
and `get_user_regs`, plus local publication and compiler support. The four
separate `ldr` instructions read CPSR, PC, LR and SP from the user PCB.
The fixture executes the real collection and formatting bodies with mock
kernel helpers; it does not model real kernel scheduling or the panel.

| Artifact | Bytes | Digest |
| --- | ---: | --- |
| `vendor_boot.img` | 100,663,296 | SHA-256 `2c36f34a1d7b1d8371a96cb29a62d36ea7bc36142eaef9f0d7d453398a3ee677` |
| `kernel.macho` | 52,207,616 | SHA-256 `d2a673dc5b7c91f7cddafd8b33c54097815ad71cbab091b1444afee04098729c` |
| `readback-fat.img` | 67,108,864 | SHA-256 `1c554cdc51fc3c75107636df918f8c29f7c8ab6677b82c2e530941bdb2145727` |
| Experimental CHMH | 48 | SHA-384 `b0fba4753e02a9ef53cbc1670271ff3b2c802ea807e85444295ff536d3e26fc70785d81f486a8cc5ef9b7d83dc8d734b` |

FAT free: 11,021,312 bytes. Compared with the pinned no-glyph outer,
the header, tail, and all FAT file contents except the kernel and ADT are
byte-identical. The 602-byte args, seed and trust cache did not change.
Subsequently, the ordinary reviewer returned PASS WITH CONDITIONS and r5 was
flashed once; screen results remain unobserved. This incremental review did
not use `deep_reviewer`; the independent verifier rerun remains pending.
The full review and device observation are recorded in
`docs/nuwa-sbth-flash-20261128-observation.md`, branch
`research/nuwa-sb0-wr-20261126` at `a0a6a3abc74304256ac07361b685b6457c93dbcd`.

The outer inherits the FUA-permissive disposable Data profile; only the
new thread probe is read-only. This is not a read-only-boot claim or an
authorization to use the outer on a device. Authentication remains
NOT REACHED.
