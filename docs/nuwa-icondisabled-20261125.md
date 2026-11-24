# Explicit IconServices job disable — 2026-11-25

Host candidate **self-checked**; no device access or flash. Deep review and
independent verifier remain pending. The changed boot identity is experimental,
not authentication; authentication NOT REACHED.

## Policy mechanism

`package/nuwa-data/nuwa_data_mount.c:512–515` calls the policy after Data mount
verification and before initproc exec. The policy constructs a new dictionary,
not a merge with the existing seed plist. Its relevant original code in
`package/nuwa-watchdog/nuwa_watchdog_policy.c:127–150`:

```c
nuwa_policy[0] = 0;
nuwa_watchdog_policy_labels = 0;
if (strlcat(nuwa_policy, nuwa_policy_head, sizeof(nuwa_policy)) >= sizeof(nuwa_policy)) {
    return ENAMETOOLONG;
}
if (disable_watchdogd) {
    cursor = "com.apple.watchdogd,com.apple.watchdog";
    while (*cursor) {
        if ((error = nuwa_policy_append(&cursor)) != 0) return error;
    }
}
if (lite == 1 || lite == 2) {
    cursor = nuwa_lite_jobs;
    while (*cursor) {
        if ((error = nuwa_policy_append(&cursor)) != 0) return error;
    }
}
if (lite == 2) {
    cursor = "com.apple.iconservices.iconservicesagent";
    if ((error = nuwa_policy_append(&cursor)) != 0) return error;
}
while (*jobs) {
    if ((error = nuwa_policy_append(&jobs)) != 0) return error;
}
```

Lines 197–203 parse `disable-jobs`, falling back to `sheng-disable-jobs`
only when the unprefixed name is absent. Lines 239–250 create a same-directory
exclusive temp; 340–347 replace the target after successful preparation:

```c
struct rename_args rn = { .from = scratch + 0x100, .to = scratch };
error = rename(p, &rn, &result);
if (!error) {
    tmp_created = 0;
    nuwa_watchdog_policy_committed = 1;
}
```

This replacement occurs only if the mount and policy steps actually succeed;
it does not prove the runtime policy was committed in an observed run.
The seed's entry would be overwritten by a successful baseline
`nuwa-lite=1` policy, so appending the explicit job is the smallest intended
change while retaining all prior lite and watchdog jobs.

### Complete lite lists

`nuwa_lite_jobs` in `nuwa_watchdog_policy.c:45–52` supplies the following
30 labels for **both** `nuwa-lite=1` and `nuwa-lite=2`:

```text
com.apple.identityservicesd
com.apple.locationd
com.apple.CommCenter
com.apple.bluetoothd
com.apple.photoanalysisd
com.apple.mediaanalysisd
com.apple.mediastream.mstreamd
com.apple.icloud.searchpartyd
com.apple.findmy.findmybeaconingd
com.apple.familycircled
com.apple.financed
com.apple.softwareupdateservicesd
com.apple.ndoagent
com.apple.biomesyncd
com.apple.email.maild
com.apple.amsengagementd
com.apple.adid
com.apple.eyereliefd
com.apple.fairplayd.A2
com.apple.passd
com.apple.mobile.obliteration
com.apple.coreduetd
com.apple.PerfPowerServices
com.apple.PerfPowerServicesExtended
com.apple.perfpowermetricd
com.apple.siriinferenced
com.apple.siriknowledged
com.apple.siriactionsd
com.apple.duetexpertd
com.apple.modelcatalogd
```

`nuwa-lite=2` adds `com.apple.iconservices.iconservicesagent`
(`nuwa_watchdog_policy.c:144–146`). Independently, baseline
`disable-watchdogd=1` adds `com.apple.watchdogd` and `com.apple.watchdog`
(`:132–136`). `disable-jobs` appends entries after these; duplicate labels
are deduplicated (`:85–96`). Values are comma-separated, each label is
1–127 ASCII alphanumeric, dot or hyphen (`:66–83`), and the argument buffer
is 400 bytes (`:55,197–203`). `PE_parse_boot_argn_internal` in xnu-8796
`pexpert/gen/bootargs.c:90–109,140–175` continues scanning after a string
match; repeated same-name arguments overwrite the buffer, so the last wins,
not a merged list. Use one argument with comma-separated values.

The policy exposes `nuwa_watchdog_policy_status` (initial -1, then errno/0),
`nuwa_watchdog_policy_labels` and `nuwa_watchdog_policy_committed` (successful
rename), at `nuwa_watchdog_policy.c:57–59,183,347,356`. They are not printed
in the current banner. An additional row is feasible with suitable symbol
binding, paint priority and atomic/snapshot review, but is not in this package.

## Argument delta and package

Only one token was appended to the baseline 507-byte args:

```diff
+disable-jobs=com.apple.iconservices.iconservicesagent
```

All 26 previous tokens remain byte-for-byte and in order; new length is 561
bytes, below xnu-8796 `pexpert/pexpert/arm64/boot.h:26`'s 608-byte command
line buffer. The existing `nuwa-lite=1`, `disable-watchdogd=1`,
`nuwa-sb-stack=360`, `nuwa-hid-standin=1`, `nuwa-mg-reset=1`,
`sheng-data-persist=2` and eight `offline-*` tokens are unchanged. Kernel,
PEER, 12-frame probe and encoded seed are unchanged; CHMH was recomputed using
the existing `build-chmh-only-payload.py:digest_material` and verified against
the old digest before rebinding. This is an unauthenticated experiment.

| Artifact | Bytes | Digest |
|---|---:|---|
| kernel SHA-256 | 52,203,520 | `44158f0fea54fc54b48c243aed864ec7567e5c566bafb4bdaeaad1e11184cc94` |
| outer SHA-256 | 100,663,296 | `a2243ee872a11aa34dab3f9d778625e9fa1ec8112cb3637e08ac1ec96ba344fc` |
| CHMH SHA-384 | 48 | `62dca8a43531f893b2156d5f4e3357a83ad40cba7cd71afa926f710667e270f19eb6d747c941433c48f329a538e6ae00` |
| outer-readback FAT SHA-256 | 67,108,864 | `316f2becce82f2e435a7f9fd1cf68da10e93881513a7ff0a50bcb80df08289b5` |
| encoded seed SHA-256 | 2,744,480 | `3c81135b384d8e090521205f2d69b3c197521e6d03c63682419d021bf0f24e5e` |

Package `out/nuwa-icondisabled-20261125-package/vendor_boot.img`; rollback
outer SHA-256 `01ffdf9b607e1acfbe91867ad5d7a38fec32ea388fd273bf43443939ec13ac5d`.
Pure-Python outer/FAT audit checked all files: only `unixnu.toml` and
`kernel.macho.adt` contents differ; the config is exactly baseline plus the
one token, ADT differs only at CHMH, old and new CHMH recompute, `display-scale`
is `03000000`, `text-fixups` absent, required/forbidden args and seed match.
`fsck.fat -vn` and `mdir` self-checked; FAT free **11,025,920 B**.
The host policy and atomic fixtures ran; an additional in-memory variant of
the actual policy fixture asserted that watchdog + lite 1 + the requested
explicit label yields 33 deduplicated labels. Kernel boot-arg parser and
on-device policy execution were not exercised.

## Future interpretation

| Observation | Interpretation |
|---|---|
| `PEER icon=-` and lsd leaves the `_init` chain | Intended observable outcome; not by itself proof of causality or globally absent agent. |
| `PEER icon=<pid>` | Intended absence not observed; inspect policy status, commit, effective mounted Data and launchd loading. |
| `PEER icon=-` and same `_init` chain | Candidate absence in census but same visible wait; no conclusion about actual XPC peer. |
| lsd disappears without later-stage evidence | Inconclusive; do not count as progress. |

The PID census only scans 1–4096 and consists of independently sampled slots.
The sampled XPC peer and actual device policy commit remain unproven.

For the independent verifier, rerun the policy and atomic fixtures,
`python3 -B out/nuwa-icondisabled-20261125-work/audit.py`,
`fsck.fat -vn out/nuwa-icondisabled-20261125-package/readback-fat.img` and
`mdir` on that FAT; reproduce the one-token packaging with fresh output and
recompute both CHMH values. Local `out/` scripts and images are ignored host
artifacts, not committed source evidence.
