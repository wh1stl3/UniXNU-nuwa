# BootWatchdogPolicy for nuwa (ported)

- Upstream: `https://github.com/Allenwdk/UniXNU-uke`, `package/BootWatchdogPolicy.c`,
  commit `55909f42b5e473628245b0eafb00d853555f4bb2` (the file there is 13,818 B,
  sha256 `4888975ea21e567a1098aa81e273aa5c541e7ae1bc380ead5b1a69290d129b42`).
- Licence: MIT (`// SPDX-License-Identifier: MIT` at the head of the upstream file).
- Why not vendored byte-for-byte: the upstream file carries uke-specific code this board cannot
  use and drops the parts we do not need. The port keeps the part that matters here — writing
  launchd's disabled list after the Data mount — and is otherwise a rewrite, so it lives as a
  separate file (`nuwa_watchdog_policy.c`) rather than as a patched copy.

## Kept from upstream

- The write path and format: `/private/var/db/com.apple.xpc.launchd/disabled.plist` as an XML
  plist, `com.apple.watchdogd` and `com.apple.watchdog` = true, mode 0644 root:root, replaced
  by same-directory rename when requested, `O_NOFOLLOW`, and a `disabled.migrated` marker created `O_EXCL` so
  launchd picks the modern override loader.
- The in-kernel syscall route (`copyout` a path into the initproc scratch page, then
  `mkdir`/`open`/`write`/`fchown`/`fchmod`/`fsync`/`sys_fstat64`/`sys_close`/`rename`), including the
  scratch layout (+0x200 for the payload, +0x800 for the stat buffer) and the
  `st_uid/st_gid/mode/size` re-check before the write counts as successful. Failed transactions
  attempt to unlink their temp file; a cleanup failure is logged. Existing markers are checked.
- The label-character restriction, so a boot argument cannot inject plist markup.

## Dropped or changed

| upstream | here |
| --- | --- |
| `sheng-disable-watchdogd`, `sheng-disable-jobs`, `sheng-lite`, `sheng-setup`, `sheng-data-reset` | `disable-watchdogd`, `disable-jobs` and `nuwa-lite`; the `sheng-` spellings are aliases only for the first two |
| `sheng_boot_setup_reset()` (rewrites Setup/first-boot plists) | not ported: the Data seed is written on the host |
| `uke_gunyah_wdt_*` petting and `autoreset` | not ported: this board has no Gunyah backend and no autoreset path |
| `sheng-lite` daemon list | list borrowed from `UniXNU/UniXNU-sheng@460179565a018c741b93e0b1efa07c55d4de497a`, `package/BootWatchdogPolicy.c` (MIT); nuwa defines its own `nuwa-lite` semantics and does not accept `sheng-lite` |
| `sheng_watchdog_policy_status` | `nuwa_watchdog_policy_status` (errno), `nuwa_watchdog_policy_committed` (rename succeeded), and `nuwa_watchdog_policy_labels` |
| prints "sheng bring-up watchdogd launch policy" | prints "nuwa: launchd disabled policy: <errno> labels=<n> (watchdogd=<0|1>)" |

## Effect

When requested, watchdogd is disabled so it cannot `brk #1` on a board without IOWatchdog.
`nuwa-lite=1` adds the 30 upstream labels; `nuwa-lite=2` also disables
`com.apple.iconservices.iconservicesagent` (icons can disappear). Other values and absence do
not enable lite. Explicit `disable-jobs=` is additive and duplicates are suppressed.
Neither SpringBoard nor mobileactivationd is in the list; this does not fix their SIGTRAP.

Bypass ledger: observed SpringBoard/mobileactivationd SIGTRAP and limited resources during
bring-up / opt-in disable background jobs to reduce competition, not a demonstrated fix /
losses include identity, location, cellular, Bluetooth, photo and media analysis, iCloud,
Find My, family, finance, software updates, mail, ads, FairPlay, Wallet, device erasure,
Siri, suggestions, metrics and power statistics / remove the bypass after normal services
and the interaction path are qualified. Actual functional effects on nuwa are unverified.

The policy is assembled before opening the file; if the 2048-byte XML buffer cannot hold
the complete plist, the call fails with `ENAMETOOLONG` and records that errno in
`nuwa_watchdog_policy_status`. A failed build does not rewrite the previous plist.
**No automatic restoration:** with no policy arguments the function does not touch the
persistent `disabled.plist` or `disabled.migrated`; prior disabled jobs remain. If another
policy argument is supplied, the plist is replaced with that boot's requested labels, so
omitted lite labels are no longer present. No explicit restore command or preservation of
pre-existing unrelated overrides is implemented; recovery requires separately authorized
offline editing/restoration of the plist, preserving unrelated overrides as appropriate.
