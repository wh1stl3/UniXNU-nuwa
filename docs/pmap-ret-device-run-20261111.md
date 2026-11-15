# PMAP-return diagnostic: single-attempt device executor (2026-11-11)

**Status: self-checked host implementation only. No device commands ran during
implementation. No current authorization to prepare/write, switch slots or boot.**
This new high-risk executor requires parent acceptance, static review (including
the applicable deep_reviewer gate), independent verifier rerun, and the user's
explicit authorization for each device phase. Flags are execution interlocks,
not a substitute for that authorization. Do not use historical permissions.

## Frozen scope

Script: `scripts/run-pmap-ret-once.py` (Python 3.10+ standard library).
Default executables: `D:/AndroidPhoneStuff/platform-tools/adb.exe` and
`D:/AndroidPhoneStuff/platform-tools/fastboot.exe`; `--adb`/`--fastboot` may
select trusted host tools, not device paths, hashes or shell commands.

**Profile compatibility (2026-11-11):** the script now defaults to the stop
profile `pmap-ret-stop-20261111-r1`; `--profile pmap-ret-continue-20261111-r1`
selects the separately documented continuation outer
(`docs/pmap-ret-continuation-device-run-20261111.md`). Legacy run directories
without `run-identity.json` remain stop-profile only and are never migrated;
consumed claims (including `pmap-ret-20261111-r4`) stay consumed. The rest of
this document describes the default/stop semantics unchanged.

| Input | Bytes | SHA256 |
| --- | ---: | --- |
| `out/owner-vendor-boot-20261111-final/vendor_boot.img` | 100663296 | `a4d789f06d74d2b8ea1aa9dff3b25556fcfae894454b766d7bf92f072567bfd0` |
| `.cache/boot-stage12-v4-r4.img` | 1495040 | `692cfcca51af81230fecbba15425cf598182fbe53abb362b6046dec0f24dc2e5` |
| This run's full stock B backup | 100663296 | `493ca426964adabb195a00ded4ff49793bc7efd5d7bea2a567bcfd0c970a8dad` |

Prepare/boot check both frozen host inputs before any device command. Restore
checks only its full stock backup: a damaged/missing diagnostic input must not
disable the independent restore path. No candidate/r4 reconstruction occurs.
Only direct block-write destination: **`/dev/block/by-name/vendor_boot_b`**.
There are no direct userdata/misc block writes. The authorized workflow does
allow this run's `/data/local/tmp` temporary files and bootloader metadata
updates needed for slot switching. No direct block writes target vendor_boot_a,
boot, init_boot, dtbo, recovery or super.
This does not imply that booting a diagnostic has no firmware/runtime effects.

## CLI and authorization

From the device repository, these examples are **dry-run only**:

```text
python scripts/run-pmap-ret-once.py --phase prepare --run-id <unique-id>
python scripts/run-pmap-ret-once.py --phase boot --run-id <same-id>
python scripts/run-pmap-ret-once.py --phase restore --run-id <same-id>
```

Without the matching `--authorize-prepare`, `--authorize-boot` or
`--authorize-restore`, the script only prints whitelist command templates; it
does not invoke either executable or create a run directory. A different
phase's flag does not authorize the selected phase. Do not add an authorization
flag until the user explicitly authorizes that phase after review.

Run IDs: 1–48 ASCII letters/digits/underscore/hyphen, first character alphanumeric.
Do not use a serial number or any personal/device identifier as the run ID.
State, command events, backup and readback files are local ignored artifacts in
`out/pmap-ret-run-<id>/`. All artifact creation is exclusive (`x`/`xb`), not
overwrite. Claims/events are flushed and fsynced before returning. Do not delete
claims, change run IDs to evade consumption, or overwrite backups.

## State and exclusion

Nominal forward-only path:

```text
identified -> backup_verified -> candidate_verified_on_B
 -> bootloader_stable -> set_B_accepted -> boot_attempt_consumed
 -> set_A_accepted -> android_A_confirmed -> B_restored_verified
```

The retained state name `bootloader_stable` means **bootloader identified only**
(bootloader 已识别，非持续驻留验证), not a sustained-residency or stability test.
It is kept unchanged for existing run evidence compatibility.

State files are append-only `state-<name>.json`. Restore can branch from any
earlier state if a full hash-valid stock backup exists. Direct Android-A restore
skips unobserved bootloader/set-slot states; it never records an unexecuted
`set_active a` as accepted. Partial prepare with no complete backup cannot restore.

`prepare.claim`, `boot.claim`, and `restore.claim` are independent one-shot phase
claims. `boot-attempt.claim` is exclusively consumed **before** the sole actual
`fastboot boot` call. Failure/timeout does not free it. Boot-phase failure never
consumes the restore claim. Phase replay is refused even when a failure preceded
the boot attempt; do not automatically retry a failed phase.

`active.lock` excludes concurrent phases for the same run. Normal completion or
handled failure releases this host lock; a killed/crashed process leaves it
behind. Such a lock or failed restore requires independent investigation, not
automatic removal/replay. The executor does not coordinate unrelated programs;
the operator must ensure no other device writer is running.

## Identity and data handling

Each phase enumerates the relevant transport and queries product separately on
every listed device, always with explicit `-s`. Non-target devices receive only
product queries. Exactly one nuwa is required; malformed/failed product queries,
offline/unauthorized transports, zero or multiple nuwa stop the phase. Reconfirm
the selected product before pushes, slot changes, boot and reboot. Across a
transport change the in-memory serial must match. A successful ADB process exit
alone is insufficient: remote error text and expected values are also checked.

Enumeration stdout/stderr stay only in memory; persisted enumeration events are
withheld summaries. Device serials are never persisted; command templates replace
them with `<REDACTED>` and all other recorded streams are sanitized using every
enumerated serial. Process exceptions are never rendered with their argv/repr.
The script does not collect account data/IMEI or directly read personal-data
block devices; its permitted staging files reside on `/data`.
Across separate processes, uniqueness/model checks do not cryptographically prove
the same physical unit: keep the intended nuwa connected and physically controlled.

## Phases and exact command families

Commands below are templates, **not instructions to execute now**. `T` means the
validated `/data/local/tmp/pmap-ret-run-<id>` directory. Remote su commands are
one fixed command string passed using a subprocess argv list; no host shell/text
pipeline is used. For `adb shell`, the string retains the reviewed literal outer
single quotes for that shell layer. For `adb exec-out`, the final `su -c`
argument is the raw command string, **without** literal outer quote characters.

| Purpose | Allowed command family |
| --- | --- |
| Inventory/identity | `adb devices -l`; `fastboot devices`; targeted ADB `shell getprop ro.product.device`; targeted fastboot `getvar product` |
| Android-A gate | targeted `shell su -c 'id'`, `'getprop sys.boot_completed'`, `'getprop ro.boot.slot_suffix'`; require uid0, 1, `_a` |
| Geometry/hash | su `readlink -f /dev/block/by-name/vendor_boot_b`; `blockdev --getsize64` same path; `sha256sum` same path or `T/{candidate,restore}.img` |
| Binary backup/readback | argv tail `['exec-out', 'su', '-c', 'dd if=/dev/block/by-name/vendor_boot_b bs=1048576 2>/dev/null']`; displayed Python string delimiters are not transmitted quote characters |
| Staging | targeted `adb shell mkdir -m 755 T` (no `-p`; existing directory stops); push only frozen candidate to `T/candidate.img` or this run's verified backup to `T/restore.img` |
| Uploaded-file initial mode | immediately after push, targeted `adb shell chmod 600 T/candidate.img` or `adb shell chmod 600 T/restore.img` for that phase's fixed file, then stat/hash validation; no other chmod path or mode allowed |
| Staging checks | su `stat -c %F:%u:%a T` and either fixed file; su `ls -A T`; unknown entries, symlinks, wrong owner/modes stop with no permission-repair retry/chcon/setenforce |
| Write B | su `dd if=T/{candidate,restore}.img of=/dev/block/by-name/vendor_boot_b bs=1048576 conv=fsync`; separate su `sync`; su `echo 3 > /proc/sys/vm/drop_caches` |
| Writer safety | su `pidof dd`, before any writer and after a failed/timed-out dd |
| Boot | targeted `adb reboot bootloader`; fastboot `getvar current-slot`, `set_active b`, `boot <frozen-r4>` |
| Restore transport | targeted fastboot `set_active a`, `reboot`; bounded ADB identification/readiness attempts |
| Cleanup | revalidate T and its entries; su `rm T/candidate.img` and/or `rm T/restore.img` only for validated existing files; require empty T then su `rmdir T`; host backup retained |

No arbitrary shell string, device path, `dd of=` destination, alternate boot
image, fallback set-slot syntax, fastboot flash, continue, root/remount, or other
command passes the whitelist. `pidof dd` is the narrowly scoped process-status
query required by the timeout brief, not a kill operation.

### prepare

1. Frozen host hashes; exclusive new run; unique nuwa; Android fully booted on A
   with su uid0. Resolve B link and require exact 100663296-byte capacity.
2. Require B's full device hash == stock. Capture binary backup directly to a
   new host file (not a text pipe), require child exit0, exact length/hash, and a
   second device stock hash. Only then record `backup_verified`.
3. Reconfirm Android A, geometry, no observable dd writer; stage candidate,
   verify device-side upload SHA; reconfirm Android A before the sole B write.
4. dd/fsync, sync/cache-drop; device full-partition hash == candidate; independent
   exec-out full binary host readback == candidate; Android still booted on A
   and su still usable. Only then record `candidate_verified_on_B`.

Remote dd stderr is redirected at its source, before exec-out can merge it into
the raw byte stream. Length/hash/returncode and both device-side stock hash
checks remain required; suppressed dd statistics are not evidence of success.
Staging creation uses `mkdir -m 755 T` and must succeed exclusively. It does not
create a directory first and chmod it afterwards, or automatically repair a
rejected directory. Before push, after push, and before
cleanup, require a non-symlink directory owned by uid2000 with mode700/750/755.
Only `candidate.img`/`restore.img` may be present; each must be a non-symlink
regular uid2000 file with mode600/400/640; 644 and 666 are rejected. Immediately
after pushing the phase's file, the mode600 assignment applies only
to this run's exact `candidate.img` or `restore.img`, before its stat/hash checks. It is not an
automatic recovery from denied access or SELinux policy. No chmod of a directory,
unrelated file, or other mode is permitted. Restore reuses only a directory with
this run's matching local creation marker, or creates a fresh directory if no
marker exists. A pre-existing directory without this run's provenance, unsafe
entries or unexpected content are not repaired or deleted.

### boot

Require exact candidate state, intact stock backup and frozen inputs. Reidentify
Android A and rehash B before the explicit reboot to bootloader. Require one
valid nuwa product response there, on the same serial. Migration permits at most
three discovery rounds with at most two five-second gaps and a shared **75-second
time budget**; every child timeout is clipped to the remaining budget. Only
absent targets are waited for; failed/malformed identity responses stop, with no
reboot fallback. Query current-slot before switching. Only exit1 with the entire
failure line `FAILED (remote: 'unknown command')` becomes `unreadable`; it may
be accompanied by at most one complete `Finished.` or
`Finished. Total time: <decimal>s` timing line (timing text is case-insensitive).
Blank surrounding lines/whitespace are ignored. No other wrapper text is allowed.
The retained `out/nuwa-readonly-identify-20261111/` contains only an ADB result
JSON and no exact slot-count failure text; no missing-variable spelling is
guessed or accepted. Other errors, hints containing `unsupported`, failure plus
a valid slot value, extra failure lines (even with exit0), and same-line mixed
errors all stop. Successful slot responses likewise permit only one exact slot
line and the optional timing line, not unrelated information.
Timeout, OSError, offline, generic FAILED or malformed success stop immediately,
with no subsequent product/set_active/boot call in that phase. `set_active b`
must exit0 with OKAY and Finished. If current-slot was readable, read it back
after switching and require exactly `b`; malformed/failing/mismatched readback
stops without boot. Only a previously explicitly unsupported query permits
acknowledgement-only fallback. Reconfirm product, consume boot claim, boot once.

**Before authorization, tell the user to prepare video.** Record 60 seconds and
look for exactly `DIAG: PMAP initializer normal epilogue reached; STOP`.
After that command the executor never continue/reboot/retries; user observation
is separate from the command return code and is not synthesized by the tool.
After the video observation, **manually enter bootloader, then separately run the
restore phase with its own authorization; do not rerun boot**. The boot success
message repeats this instruction. It does not authorize restore automatically.

### restore

Works directly while Android A remains online after prepare failure, or after
the user **manually returns the device to bootloader**. In the latter case,
confirm unique nuwa, query current-slot, accept `set_active a`
(exit0+OKAY+Finished), and apply the same readability rule: when readable, its
post-switch response must be exactly `a` before any reboot. Then reboot once.
ADB discovery/readiness has at most **six rounds**, at most five five-second
gaps, and a shared **150-second time budget**, covering enumeration, every
per-device identity query and readiness commands. Each subprocess timeout and
gap is clipped to the remaining budget. These are elapsed-time budgets, not
hard-real-time guarantees about host scheduling/logging overhead. Identity
errors, ambiguity and authorization failures stop rather than being ignored.
Stop at the attempt or time limit, whichever is reached first; never reboot to retry.

Require boot_completed1, slot `_a`, uid0. Verify this run's stock backup, geometry
and writer absence; upload and hash it; write only B with the same flush/hash/
independent binary-readback checks, require stock SHA. Reconfirm Android A,
record `B_restored_verified`, then clean only `T`. Preserve all host evidence.

## Stops and recovery limits

- Wrong input/backup size/hash: no device command. No backup: no restore I/O.
- Failed device/stream hash, partial binary read, failed upload, uid/slot/size
  mismatch: no following reboot or slot switch; retain evidence and request
  restore authorization while Android is still available.
- A dd timeout/failed process leaves a writer claim; query `pidof dd`. Only an
  explicit exit1 with empty stdout/stderr is accepted as no observed dd process.
  Anything else forbids another writer. Even when absence is observed, the
  failed phase stops; it never retries dd automatically. Process observation is
  not proof of media health or of quiescence of unrelated firmware activity.
- Fastboot timeout/drop/FAILED/missing product: no slot change/boot. Only explicit
  retained whole-line current-slot failure is downgraded; loss of readability after a readable
  pre-switch query is a stop, not a new downgrade. Missing
  set-slot acknowledgement: no fallback syntax or retry. Boot failure/timeout:
  attempt stays consumed; manual observation/return and independently authorized
  restore remain separate.
- Cleanup failure does not erase the verified-restored state; retained temporary
  files are reported as a failure, not silently claimed cleaned.
- Every command logs its real child returncode (null for timeout/spawn failure).
  Text commands have a 20-second timeout, binary partition reads 120 seconds.
  A command timeout kills the host client, not necessarily its remote child.

## Host checks and independent handoff

Implementation checks use Windows Python 3.13.14 at
`C:/Program Files/WorkBuddy/resources/vendor/python/python.exe`, device repo cwd:

```powershell
& 'C:/Program Files/WorkBuddy/resources/vendor/python/python.exe' scripts/run-pmap-ret-once.py --self-check
& 'C:/Program Files/WorkBuddy/resources/vendor/python/python.exe' -m py_compile scripts/run-pmap-ret-once.py
git diff --check
git diff --no-index --check -- NUL scripts/run-pmap-ret-once.py
git diff --no-index --check -- NUL docs/pmap-ret-device-run-20261111.md
```

Latest restore-mode revision uses the existing WSL Python3.11 (same repository
cwd, no device executables are invoked):

```powershell
wsl -d Ubuntu-22.04 --cd /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa -- /home/wh1stl3/.local/bin/python3.11 -B scripts/run-pmap-ret-once.py --self-check
wsl -d Ubuntu-22.04 --cd /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa -- /home/wh1stl3/.local/bin/python3.11 -B -m py_compile scripts/run-pmap-ret-once.py
git diff --check
```

The no-index checks cover these still-untracked new files; report their actual
exit codes separately (Git may return1 for the file differences even without
whitespace diagnostics). Do not mistake an empty tracked diff for checking them.

Self-check replaces subprocess with a trap and injects only a synthetic runner,
synthetic host artifacts and synthetic serials; it does not access real device
executables even if authorization flags are also present. Fixture file validation
is replaced in general state-machine models. Separate real host-file tests keep
the production check_file implementation, with success/length/hash cases and
CR/LF/NUL/high-bit byte streams; appended dd statistics, short reads and timeouts
cannot promote backup_verified. These are model tests, not runtime
proof of Android su, dd semantics, flash persistence, fastboot support or PMAP.
Synthetic evidence is retained in a fresh ignored `out/pmap-ret-selfcheck-*`
directory reported by the test; no bulk tree removal is performed.

Covered branches include nominal three-phase progression; direct Android restore;
all-phase dry runs; zero/multiple target; uid/slot/geometry/readiness refusal;
bad pre/post-write and host/binary hashes; fastboot product/slot/boot failures;
consumed boot replay; independent restore; uncertain writer refusal; no backup;
exclusive claims/cross-phase stale lock; run-ID/command injection; bounded wait;
serial redaction including synthetic serials in response streams.
Revision checks also cover explicit slot unsupported versus timeout/OSError/
offline/other FAILED; both-slot post-set mismatches and malformed responses;
staging collision/symlink/owner/mode/extra-entry refusal; safe cleanup refusal;
real binary backup streams and exception/console redaction; and clipped shared
wait budgets plus bounded bootloader migration.
The final strict-line tests reject mixed same-line permission errors, ordinary
unsupported hints, valid-slot mixtures, appended failures including exit0, and
timing lines with appended text; none may issue another product/set_active/boot.

## Stage-1 read failure and argv correction (self-checked)

Run `pmap-ret-20261111-r1` stopped at `identified`, before backup_verified or any
push/block write: its purported backup was 105 B, not 100663296 B. Old run and
claims are retained and must not be replayed. The captured bytes decode to:

```text
/system/bin/sh: dd if=/dev/block/by-name/vendor_boot_b bs=1048576 2>/dev/null: inaccessible or not found
```

The error names the entire spaced command as a program. `exec-out` passed the
extra literal outer quotes through to the su command's shell, making the whole
dd string one command word; this was not a su permission refusal. Host process
exit0 did not make those error bytes a valid backup. The size/hash gate stopped it.

Bounded read-only diagnosis is saved in ignored
`out/pmap-ret-backup-read-diagnose-20261111/result.json` (serials redacted).
On the selected nuwa with Magisk uid0, all these child processes returned0:

| Trial argv tail | stdout bytes | Meaning |
| --- | ---: | --- |
| exec-out su -c with literal `'id'` | 61 | uid0; a quoted single word does not expose the spaced-command error |
| exec-out su -c with raw `id` | 61 | uid0 |
| shell su -c with literal `'id'` | 62 | uid0, CRLF; not a binary backup transport |
| exec-out su -c with literal outer quotes around dd, count=1 | 113 | inaccessible/not-found error text, not partition bytes |
| exec-out su -c with raw dd string, count=1 | 1048576 | binary sample SHA256 `76e71e64d612cab73ba5049f77870a855f54564ad38144b1b7b7e62721bbbb89` |

Both dd trials used only `if=/dev/block/by-name/vendor_boot_b`, bs1048576,
count1 and `2>/dev/null`; no sample partition bytes were saved. This proves the
one-MiB read form on this transport, not a full-partition backup. The production
read removes only the literal outer quotes, keeps the exact path/bs/stderr
redirection, and keeps all full-size, SHA, device-before/after and binary-readback
gates. Shell commands are unchanged. Mock tests assert the exact raw exec-out
argv and reject the old quoted form, added count arguments, and other partitions.
No corrected prepare was executed. A new run ID and renewed acceptance after
review are required before another prepare; no write/restore/boot is authorized
by this read-only diagnosis.

## r2 staging-mode stop (self-checked)

Run `pmap-ret-20261111-r2` obtained the full hash-valid stock backup, then stopped
at `backup_verified`: default `mkdir` produced `directory:2000:777`, correctly
rejected before push or any block write. Creation now explicitly requests mode755
using the exact argv `['shell', 'mkdir', '-m', '755', T]`, without `-p`.
The post-creation non-symlink/uid2000/mode700-or-750-or-755 checks remain unchanged;
777 and existing directories must still stop. Mock tests assert the creation argv
and refusal of the old no-mode form, `-p`, and mode777.

Old r1/r2 directories, claims, the valid r2 host backup and its empty device-side
staging directory remain untouched. Any subsequently accepted prepare must use
a new run ID (r3); this host-only change executes no authorized phase and does
not authorize cleanup, reboot, slot switching or restore.

## r3 upload-mode stop and r4 preparation change (self-checked)

Run r3 retained a verified stock backup and stopped at `backup_verified`, before
block writes: the uploaded candidate was `regular file:2000:666`. Old r1–r3
artifacts and device staging are not modified or cleaned by this change.
The newly authorized candidate-mode assignment is exactly
`['shell', 'chmod', '600', T + '/candidate.img']` after push and before validation.
Directory validation, full-length/hash gates and both readback paths are unchanged.
Mock checks assert that argv and ordering, reject chmod path/mode escapes, and
still stop on mode666/644 even if chmod returned success. No chcon/setenforce or
permission-repair loop is added. The subsequent host-only restore correction now
adds the matching exact `['shell', 'chmod', '600', T + '/restore.img']` after
restore push and before stat/hash, fixing the former missing assignment. It does
not widen accepted file permissions or add chcon/setenforce. Mock uploads begin
at666; successful chmod must precede stat/hash. Failed chmod or unsafe post-chmod
stat stops before a restore dd, retaining restore.claim and refusing replay.

Only after the required host checks pass may the already-authorized prepare use
the fresh r4 run ID. It must stop after phase1; no boot/restore/cleanup authorization
is conveyed by the staging-file mode assignment.

## Restore failure before dd: claim handling (no retry implementation)

`restore.claim` is created before the phase starts, so a chmod/hash/stat failure
before dd still consumes this phase claim. Tests retain it and the verified stock
backup, leave `android_A_confirmed` in place, create no restore-writer.claim, and
confirm a second invocation stops before any device command. No retry option,
new claim naming scheme, or claim reset has been implemented here.

Safe next steps are **review, not executable retry instructions**:

1. Parent/reviewer inspect existing events and state, independently confirm the
   exact pre-dd stop, absence of a restore-writer.claim and the full stock backup
   size/hash. A missing writer claim alone is not a substitute for event review.
   Preserve the entire run and every old claim; if writer status is uncertain,
   do not permit another writer.
2. Obtain a new, scoped restore-attempt authorization only after independent
   review and verification. Do not rerun boot or prepare, switch run IDs merely
   to evade claims, delete/rename restore.claim, or manually regress state files.
3. A future reviewed recovery mechanism could keep the same run/backup, append
   an exclusive `restore-attempt-02.claim` (or similar), and revalidate Android A,
   writer absence, geometry, staging and backup. It must explicitly handle the
   already-recorded monotonic states instead of replaying advance calls. Simply
   renaming the existing claim is not sufficient and is not supported by this
   executor. Until that mechanism or a separately reviewed recovery procedure
   exists, this version cannot safely grant a fresh same-run restore attempt.

This note performs no manual reset and conveys no current device authorization.

Parent: request static review of the final two-file diff and applicable deep
review before device acceptance. Verifier: rerun the host commands above
and unauthorised CLI dry-runs; **do not add authorization flags or query devices**.
No commit/push or device acceptance is part of this implementation task.
