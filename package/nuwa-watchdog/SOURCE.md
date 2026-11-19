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
  plist, `com.apple.watchdogd` and `com.apple.watchdog` = true, mode 0644 root:root, rewritten
  in place every boot, `O_NOFOLLOW`, and a `disabled.migrated` marker created `O_EXCL` so
  launchd picks the modern override loader.
- The in-kernel syscall route (`copyout` a path into the initproc scratch page, then
  `mkdir`/`open`/`write`/`fchown`/`fchmod`/`fsync`/`sys_fstat64`/`sys_close`), including the
  scratch layout (+0x200 for the payload, +0x800 for the stat buffer) and the
  `st_uid/st_gid/mode/size` re-check before the write counts as successful.
- The label-character restriction, so a boot argument cannot inject plist markup.

## Dropped or changed

| upstream | here |
| --- | --- |
| `sheng-disable-watchdogd`, `sheng-disable-jobs`, `sheng-lite`, `sheng-setup`, `sheng-data-reset` | `disable-watchdogd`, `disable-jobs` (the unprefixed names this kernel documents); the `sheng-` spellings are still accepted as aliases for `disable-watchdogd`/`disable-jobs` |
| `sheng_boot_setup_reset()` (rewrites Setup/first-boot plists) | not ported: the Data seed is written on the host |
| `uke_gunyah_wdt_*` petting and `autoreset` | not ported: this board has no Gunyah backend and no autoreset path |
| `sheng-lite` daemon list | not ported: no radios/accounts on this board yet; use `disable-jobs=` explicitly when needed |
| `sheng_watchdog_policy_status` | `nuwa_watchdog_policy_status` (plus `nuwa_watchdog_policy_labels` for the console line) |
| prints "sheng bring-up watchdogd launch policy" | prints "nuwa: launchd disabled policy: <errno> labels=<n> (watchdogd=<0|1>)" |

## Effect

watchdogd never starts, so it cannot `brk #1` on a board without IOWatchdog. Nothing else is
disabled unless a caller passes `disable-jobs=`. The file is rewritten on every boot from the
current boot arguments, so removing the argument restores the daemon on the next boot (the
marker is harmless and stays).
